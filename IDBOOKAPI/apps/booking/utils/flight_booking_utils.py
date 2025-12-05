"""
Flight booking business logic utilities
Handles authentication flow, pricing, GST, validations, refunds, and booking processing
"""

from decimal import Decimal
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
from django.utils import timezone
from django.conf import settings
from django.db import transaction
import uuid
import logging

from ..models import (
    Booking, FlightBooking, FlightPassenger, FlightAncillaryService,
    BookingPaymentDetail, Invoice, BookingMetaInfo
)
from apps.customer.models import Wallet, WalletTransaction
from apps.authentication.models import User, UserOtp
from apps.authentication.utils.db_utils import get_user_from_email, create_user
from apps.authentication.utils.authentication_utils import add_group_for_guest_user
from apps.org_managements.models import BusinessDetail
from IDBOOKAPI.basic_resources import BOOKING_STATUS_CHOICES
from IDBOOKAPI.utils import calculate_tax, get_unique_id_from_time

logger = logging.getLogger(__name__)


def process_ssr_success(booking: Booking, flight_booking: FlightBooking, airiq_resp: dict, 
                        meals: list, baggage: list, seats: list, other: list, 
                        payment_amount: Decimal) -> Dict:
    """
    Process successful SSR addition - update booking and persist services
    
    Args:
        booking: Booking instance
        flight_booking: FlightBooking instance
        airiq_resp: AirIQ AddSSR response
        meals: List of meal SSR items
        baggage: List of baggage SSR items
        seats: List of seat SSR items
        other: List of other SSR items
        payment_amount: Payment amount for SSR
        
    Returns:
        Dict with processing result
    """
    try:
        # Update flight booking track and PNR from response if available
        try:
            retr = airiq_resp.get('Retrieveresponse') or airiq_resp.get('Retriveresponse') or {}
            itins = (retr.get('ItinearyDetails') or [])
            if itins:
                item0 = (itins[0].get('Item') or [None])[0] or {}
                fb_updates = {}
                maybe_track = item0.get('BookingTrackId')
                if maybe_track:
                    fb_updates['airiq_track_id'] = maybe_track
                maybe_airiq_pnr = item0.get('AirIqPNR') or item0.get('AiriqPNR')
                if maybe_airiq_pnr:
                    fb_updates['airiq_pnr'] = maybe_airiq_pnr
                try:
                    trav_items = (item0.get('TravellerInfo') or {}).get('Item') or []
                    if trav_items:
                        seginfo = trav_items[0].get('SegmentInformation') or {}
                        seg_items = seginfo.get('Item') or []
                        if seg_items:
                            airline_pnr_new = seg_items[0].get('AirlinePNR')
                            if airline_pnr_new:
                                fb_updates['airline_pnr'] = airline_pnr_new
                except Exception:
                    pass
                if fb_updates:
                    for k, v in fb_updates.items():
                        setattr(flight_booking, k, v)
                    flight_booking.save(update_fields=list(fb_updates.keys()))
        except Exception:
            pass

        # Persist ancillary selections to DB
        def _map_service_type(key: str) -> str:
            return {
                'MealsSSR': 'MEAL',
                'BaggSSR': 'BAGGAGE',
                'SeatsSSR': 'SEAT',
                'OtherSSR': 'OTHER',
            }.get(key, 'OTHER')

        selections = [
            ('MealsSSR', meals),
            ('BaggSSR', baggage),
            ('SeatsSSR', seats),
            ('OtherSSR', other),
        ]

        pax_map = {p.passenger_reference: p for p in flight_booking.passengers.all()}
        created_count = 0
        for key, items in selections:
            service_type = _map_service_type(key)
            for it in (items or []):
                pax_ref = it.get('PaxRefId') or it.get('PaxRefNumber') or it.get('PaxRef')
                pax_ref_int = None
                try:
                    pax_ref_int = int(pax_ref) if pax_ref is not None else None
                except Exception:
                    pax_ref_int = None
                passenger = pax_map.get(pax_ref_int) if pax_ref_int else None
                if not passenger:
                    continue
                code = (it.get('MealId') or it.get('BaggId') or it.get('SeatId') or it.get('OtherSSRId') or '')
                desc = it.get('Description') or str(code)
                price = Decimal(str(it.get('Amount') or it.get('SeatAmount') or 0)) if 'Amount' in it or 'SeatAmount' in it else Decimal('0')
                segment_ref = int(it.get('SegmentNo') or it.get('SegRef') or 1)
                FlightAncillaryService.objects.create(
                    flight_booking=flight_booking,
                    passenger=passenger,
                    service_type=service_type,
                    airiq_service_id=str(code),
                    service_code=str(code),
                    service_description=str(desc)[:200],
                    segment_reference=segment_ref,
                    service_price=price,
                )
                created_count += 1

        # Update booking amount
        if payment_amount > 0:
            booking.final_amount = (booking.final_amount or Decimal('0')) + payment_amount
            booking.total_payment_made = (booking.total_payment_made or Decimal('0')) + payment_amount
            booking.save(update_fields=['final_amount', 'total_payment_made'])

        # Send SSR services added SMS notification
        try:
            from apps.booking.tasks import send_booking_sms_task
            send_booking_sms_task.delay(
                notification_type='FLIGHT_SERVICES_ADDED',
                params={
                    'booking_id': booking.id,
                    'additional_charge': float(payment_amount)
                }
            )
            logger.info(f"SSR services added SMS notification queued for booking {booking.id}")
        except Exception as e:
            logger.error(f"Error queuing SSR services SMS notification: {str(e)}")

        return {
            'success': True,
            'created_services': created_count,
            'payment_amount': float(payment_amount),
            'airiq_response': airiq_resp,
        }
    except Exception as e:
        logger.error(f"Error processing SSR success: {str(e)}")
        raise


def process_reschedule_success(booking: Booking, flight_booking: FlightBooking, airiq_resp: dict, 
                                remarks: str = '', pnr_index: int = None, old_airiq_pnr: str = None) -> Dict:
    """
    Process successful reschedule - update booking details
    
    Args:
        booking: Booking instance
        flight_booking: FlightBooking instance
        airiq_resp: AirIQ reschedule response
        remarks: Reschedule remarks
        pnr_index: Index of PNR being rescheduled (for multiple PNRs)
        old_airiq_pnr: Original AirIQ PNR being rescheduled
        
    Returns:
        Dict with processing result
    """
    try:
        # Extract new booking amount from response
        new_booking_amount = Decimal(str(airiq_resp.get('NewBookingAmount', 0) or 0))
        old_booking_amount = Decimal(str(airiq_resp.get('OldBookingAmount', 0) or 0))
        penalty = Decimal(str(airiq_resp.get('Penalty', 0) or 0))
        fare_difference = Decimal(str(airiq_resp.get('FareDifference', 0) or 0))
        new_pnr = airiq_resp.get('New_PNR', '')
        
        # Get or initialize reschedule status tracking
        reschedule_status = flight_booking.airiq_response_data.get('reschedule_status', {}) or {}
        if not isinstance(reschedule_status, dict):
            reschedule_status = {}
        
        # Track this reschedule
        reschedule_record = {
            'old_airiq_pnr': old_airiq_pnr or flight_booking.airiq_pnr,
            'new_airiq_pnr': new_pnr,
            'old_booking_amount': float(old_booking_amount),
            'new_booking_amount': float(new_booking_amount),
            'penalty': float(penalty),
            'fare_difference': float(fare_difference),
            'status': 'success',
            'rescheduled_at': timezone.now().isoformat(),
            'remarks': remarks[:255] if remarks else ''
        }
        
        # Store per PNR if multiple PNRs
        if pnr_index is not None:
            reschedule_status[f'pnr_{pnr_index}'] = reschedule_record
        elif old_airiq_pnr:
            reschedule_status[old_airiq_pnr] = reschedule_record
        else:
            reschedule_status['latest'] = reschedule_record
        
        # Update flight booking with reschedule status
        if not flight_booking.airiq_response_data:
            flight_booking.airiq_response_data = {}
        flight_booking.airiq_response_data['reschedule_status'] = reschedule_status
        
        # Update booking final amount if new amount is provided
        if new_booking_amount > 0:
            booking.final_amount = new_booking_amount
            booking.save(update_fields=['final_amount'])
        
        # Update flight booking status and PNRs
        # Only mark as RESCHEDULED if all PNRs are rescheduled, otherwise keep as CONFIRMED
        airiq_pnrs = flight_booking.airiq_pnrs or []
        if not airiq_pnrs and flight_booking.airiq_pnr:
            airiq_pnrs = [flight_booking.airiq_pnr]
        
        # Check if all PNRs have been rescheduled
        all_rescheduled = True
        if len(airiq_pnrs) > 1:
            for idx in range(len(airiq_pnrs)):
                pnr_key = f'pnr_{idx}'
                if pnr_key not in reschedule_status or reschedule_status[pnr_key].get('status') != 'success':
                    all_rescheduled = False
                    break
        
        if all_rescheduled:
            flight_booking.status = 'RESCHEDULED'
        # If partial, keep status as CONFIRMED but track reschedule status
        
        if remarks:
            flight_booking.reschedule_remark = remarks[:255]
        
        # Update PNR if new PNR is provided
        if new_pnr:
            # Update in list if using multiple PNRs
            if flight_booking.airiq_pnrs:
                # Replace old PNR with new one at the same index
                if pnr_index is not None and 0 <= pnr_index < len(flight_booking.airiq_pnrs):
                    flight_booking.airiq_pnrs[pnr_index] = new_pnr
                elif old_airiq_pnr and old_airiq_pnr in flight_booking.airiq_pnrs:
                    idx = flight_booking.airiq_pnrs.index(old_airiq_pnr)
                    flight_booking.airiq_pnrs[idx] = new_pnr
                else:
                    # Append if not found (shouldn't happen, but handle gracefully)
                    flight_booking.airiq_pnrs.append(new_pnr)
            else:
                flight_booking.airiq_pnr = new_pnr
                flight_booking.airiq_pnrs = [new_pnr]
        
        flight_booking.save(update_fields=['status', 'reschedule_remark', 'airiq_pnr', 'airiq_pnrs', 'airiq_response_data'])
        
        # Send reschedule SMS notification
        try:
            from apps.booking.tasks import send_booking_sms_task
            # Format new departure datetime
            new_departure_str = ''
            if flight_booking.departure_date:
                new_departure_str = flight_booking.departure_date.strftime('%B %d, %Y %I:%M %p')
            
            send_booking_sms_task.delay(
                notification_type='FLIGHT_BOOKING_RESCHEDULED',
                params={
                    'booking_id': booking.id,
                    'new_departure': new_departure_str
                }
            )
            logger.info(f"Reschedule SMS notification queued for booking {booking.id}")
        except Exception as e:
            logger.error(f"Error queuing reschedule SMS notification: {str(e)}")
        
        return {
            'success': True,
            'new_booking_amount': float(new_booking_amount),
            'old_booking_amount': float(old_booking_amount),
            'penalty': float(penalty),
            'fare_difference': float(fare_difference),
            'new_pnr': new_pnr,
            'old_pnr': old_airiq_pnr or flight_booking.airiq_pnr,
            'pnr_index': pnr_index,
            'all_rescheduled': all_rescheduled,
            'airiq_response': airiq_resp,
        }
    except Exception as e:
        logger.error(f"Error processing reschedule success: {str(e)}")
        raise


def record_reschedule_failure(flight_booking: FlightBooking, old_airiq_pnr: str, error: str, 
                              pnr_index: int = None) -> None:
    """
    Record reschedule failure for a specific PNR
    
    Args:
        flight_booking: FlightBooking instance
        old_airiq_pnr: Original AirIQ PNR that failed to reschedule
        error: Error message
        pnr_index: Index of PNR (for multiple PNRs)
    """
    try:
        reschedule_status = flight_booking.airiq_response_data.get('reschedule_status', {}) or {}
        if not isinstance(reschedule_status, dict):
            reschedule_status = {}
        
        failure_record = {
            'old_airiq_pnr': old_airiq_pnr,
            'status': 'failed',
            'error': str(error)[:500],
            'failed_at': timezone.now().isoformat()
        }
        
        if pnr_index is not None:
            reschedule_status[f'pnr_{pnr_index}'] = failure_record
        else:
            reschedule_status[old_airiq_pnr] = failure_record
        
        if not flight_booking.airiq_response_data:
            flight_booking.airiq_response_data = {}
        flight_booking.airiq_response_data['reschedule_status'] = reschedule_status
        flight_booking.save(update_fields=['airiq_response_data'])
    except Exception as e:
        logger.error(f"Error recording reschedule failure: {str(e)}")


def extract_route_info_from_airiq_response(flight_booking: FlightBooking) -> Dict:
    """
    Extract route information (flying_from, flying_to, return_from, return_to) 
    from AirIQ booking response data stored in flight_booking
    
    Returns:
        Dict with route information:
        {
            'onward_origin': 'HYD',
            'onward_destination': 'DEL',
            'return_origin': 'DEL',
            'return_destination': 'HYD',
            'itineraries': [
                {
                    'index': 0,
                    'base_origin': 'HYD',
                    'base_destination': 'DEL',
                    'trip_type': 'O',
                    'airiq_pnr': 'AF16GB0030',
                    'segments': [
                        {'origin': 'HYD', 'destination': 'BLR'},
                        {'origin': 'BLR', 'destination': 'DEL'}
                    ]
                },
                ...
            ]
        }
    """
    route_info = {
        'onward_origin': '',
        'onward_destination': '',
        'return_origin': '',
        'return_destination': '',
        'itineraries': []
    }
    
    try:
        # Get AirIQ response data
        airiq_response = flight_booking.airiq_response_data or {}
        booking_response = airiq_response.get('Bookingresponse', {})
        itinerary_details = booking_response.get('ItinearyDetails', [])
        
        if not itinerary_details:
            # Fallback to booked_itineraries if available
            booked_itineraries = flight_booking.booked_itineraries or []
            if booked_itineraries:
                for idx, itin in enumerate(booked_itineraries):
                    base_origin = itin.get('base_origin', '').strip()
                    base_dest = itin.get('base_destination', '').strip()
                    
                    if idx == 0:
                        route_info['onward_origin'] = base_origin
                        route_info['onward_destination'] = base_dest
                    else:
                        route_info['return_origin'] = base_origin
                        route_info['return_destination'] = base_dest
                    
                    route_info['itineraries'].append({
                        'index': idx,
                        'base_origin': base_origin,
                        'base_destination': base_dest,
                        'trip_type': 'O' if idx == 0 else 'R',
                        'airiq_pnr': itin.get('airiq_pnr', ''),
                        'segments': itin.get('segments', [])
                    })
            return route_info
        
        # Extract from AirIQ response structure
        for idx, itin_detail in enumerate(itinerary_details):
            items = itin_detail.get('Item', [])
            if not items:
                continue
            
            # Get first item (usually contains the main booking info)
            item = items[0] if isinstance(items, list) else items
            
            base_origin = (item.get('BaseOrigin', '') or '').strip()
            base_dest = (item.get('BaseDestination', '') or '').strip()
            trip_type = item.get('TripType', 'O')
            airiq_pnr = item.get('AirIqPNR', '')
            
            # Extract segments from TravellerInfo
            segments = []
            traveller_info = item.get('TravellerInfo', {})
            traveller_items = traveller_info.get('Item', [])
            
            if traveller_items:
                # Get segments from first traveller
                first_traveller = traveller_items[0] if isinstance(traveller_items, list) else traveller_items
                segment_info = first_traveller.get('SegmentInformation', {})
                segment_items = segment_info.get('Item', [])
                
                for seg in (segment_items if isinstance(segment_items, list) else [segment_items]):
                    if seg:
                        segments.append({
                            'origin': (seg.get('Origin', '') or '').strip(),
                            'destination': (seg.get('Destination', '') or '').strip()
                        })
            
            # Determine if this is onward or return based on index and trip_type
            # For roundtrip with multiple itineraries:
            # - First itinerary is usually onward
            # - Second itinerary is usually return
            # But we also check the BaseOrigin/Destination to be sure
            
            if idx == 0:
                route_info['onward_origin'] = base_origin
                route_info['onward_destination'] = base_dest
            else:
                # For return, check if this is actually the return journey
                # by comparing with onward destination
                if base_origin == route_info['onward_destination'] or not route_info['return_origin']:
                    route_info['return_origin'] = base_origin
                    route_info['return_destination'] = base_dest
            
            route_info['itineraries'].append({
                'index': idx,
                'base_origin': base_origin,
                'base_destination': base_dest,
                'trip_type': trip_type,
                'airiq_pnr': airiq_pnr,
                'segments': segments
            })
        
        # If we still don't have return info and there's only one itinerary,
        # it might be a single PNR roundtrip - check segments to determine return
        if not route_info['return_origin'] and len(route_info['itineraries']) == 1:
            itin = route_info['itineraries'][0]
            segments = itin.get('segments', [])
            if len(segments) > 1:
                # Find the return segment (destination of onward = origin of return)
                onward_dest = route_info['onward_destination']
                for seg in segments:
                    if seg.get('origin') == onward_dest:
                        route_info['return_origin'] = seg.get('origin', '')
                        route_info['return_destination'] = seg.get('destination', '')
                        break
        
    except Exception as e:
        logger.error(f"Error extracting route info from AirIQ response: {str(e)}")
    
    return route_info


def process_multi_pnr_reschedule_availability(flight_booking: FlightBooking, reschedule_requests: list, airiq_service) -> Dict:
    """
    Process reschedule availability for multiple PNRs (onward and return)
    
    Args:
        flight_booking: FlightBooking instance
        reschedule_requests: List of reschedule requests, each with:
            - airiq_pnr: AirIQ PNR for this segment
            - airline_pnr: Airline PNR for this segment (optional)
            - trip_type: 'O' for onward, 'R' for return
            - flight_segments: List of flight segments
            - remarks: Remarks for this segment
        airiq_service: AirIQService instance
        
    Returns:
        Dict with aggregated availability responses
    """
    try:
        all_responses = []
        errors = []
        
        for idx, req in enumerate(reschedule_requests):
            try:
                # Validate segments before API call
                flight_segments = req.get('flight_segments', [])
                if not flight_segments:
                    errors.append({
                        'segment_index': idx,
                        'trip_type': req['trip_type'],
                        'airiq_pnr': req['airiq_pnr'],
                        'error': 'No flight segments provided for this PNR'
                    })
                    continue
                
                # Validate each segment has required fields
                for seg_idx, seg in enumerate(flight_segments):
                    if not all([seg.get('departure_station'), seg.get('arrival_station'), seg.get('flight_date')]):
                        errors.append({
                            'segment_index': idx,
                            'segment_number': seg_idx + 1,
                            'trip_type': req['trip_type'],
                            'airiq_pnr': req['airiq_pnr'],
                            'error': f'Segment {seg_idx + 1} missing required fields (departure_station, arrival_station, or flight_date)'
                        })
                        break
                
                if errors and any(e.get('segment_index') == idx for e in errors):
                    continue
                
                resp = airiq_service.reschedule_availability(
                    trip_type=req['trip_type'],
                    flight_segments=flight_segments,
                    airiq_pnr=req['airiq_pnr'],
                    remarks=req.get('remarks', '')
                )
                all_responses.append({
                    'segment_index': idx,
                    'pnr_index': idx,  # Add for tracking
                    'trip_type': req['trip_type'],
                    'airiq_pnr': req['airiq_pnr'],
                    'old_airiq_pnr': req['airiq_pnr'],  # Store original PNR
                    'segments_count': len(flight_segments),
                    'response': resp
                })
            except Exception as e:
                errors.append({
                    'segment_index': idx,
                    'pnr_index': idx,
                    'trip_type': req['trip_type'],
                    'airiq_pnr': req['airiq_pnr'],
                    'error': str(e)
                })
        
        return {
            'success': len(errors) == 0,
            'responses': all_responses,
            'errors': errors,
            'total_segments': len(reschedule_requests)
        }
    except Exception as e:
        logger.error(f"Error processing multi-PNR reschedule availability: {str(e)}")
        return {
            'success': False,
            'error': str(e),
            'responses': [],
            'errors': [{'error': str(e)}]
        }


def process_multi_pnr_reschedule_confirm(flight_booking: FlightBooking, reschedule_requests: list, 
                                         airiq_service, flag: str = 'CHECKFARE') -> Dict:
    """
    Process reschedule confirm for multiple PNRs (onward and return)
    
    Args:
        flight_booking: FlightBooking instance
        reschedule_requests: List of reschedule requests, each with:
            - airiq_pnr: AirIQ PNR for this segment
            - track_id: Track ID from availability response
            - trip_type: 'O' for onward, 'R' for return
            - flight_details: Flight details dict
            - contact_no: Contact number
            - remarks: Remarks for this segment
        airiq_service: AirIQService instance
        flag: 'CHECKFARE' or 'CONFIRM'
        
    Returns:
        Dict with aggregated responses, penalties, and fare differences
    """
    try:
        all_responses = []
        total_penalty = Decimal('0')
        total_fare_difference = Decimal('0')
        errors = []
        
        for idx, req in enumerate(reschedule_requests):
            try:
                resp = airiq_service.reschedule_booking(
                    airiq_pnr=req['airiq_pnr'],
                    track_id=req['track_id'],
                    flight_details=req['flight_details'],
                    contact_no=req['contact_no'],
                    remarks=req.get('remarks', ''),
                    flag=flag
                )
                
                # Extract penalty and fare difference
                penalty = Decimal(str(resp.get('Penalty', 0) or 0))
                fare_difference = Decimal(str(resp.get('FareDifference', 0) or 0))
                
                total_penalty += penalty
                total_fare_difference += fare_difference
                
                all_responses.append({
                    'segment_index': idx,
                    'pnr_index': idx,  # Add for tracking
                    'trip_type': req['trip_type'],
                    'airiq_pnr': req['airiq_pnr'],
                    'old_airiq_pnr': req['airiq_pnr'],  # Store original PNR
                    'penalty': float(penalty),
                    'fare_difference': float(fare_difference),
                    'response': resp
                })
            except Exception as e:
                errors.append({
                    'segment_index': idx,
                    'pnr_index': idx,
                    'trip_type': req['trip_type'],
                    'airiq_pnr': req['airiq_pnr'],
                    'error': str(e)
                })
        
        total_payment = total_penalty + total_fare_difference
        
        return {
            'success': len(errors) == 0,
            'responses': all_responses,
            'errors': errors,
            'total_penalty': float(total_penalty),
            'total_fare_difference': float(total_fare_difference),
            'total_payment': float(total_payment),
            'total_segments': len(reschedule_requests)
        }
    except Exception as e:
        logger.error(f"Error processing multi-PNR reschedule confirm: {str(e)}")
        return {
            'success': False,
            'error': str(e),
            'responses': [],
            'errors': [{'error': str(e)}],
            'total_penalty': 0,
            'total_fare_difference': 0,
            'total_payment': 0
        }


def process_reschedule_refund(booking: Booking, refund_amount: Decimal, reschedule_details: dict) -> Dict:
    """
    Process refund for reschedule when new fare is less than old fare
    
    Args:
        booking: Booking instance
        refund_amount: Amount to refund (should be positive)
        reschedule_details: Details about the reschedule operation
        
    Returns:
        Dict with refund processing result
    """
    try:
        from apps.booking.utils.booking_utils import refund_wallet_payment
        from apps.booking.utils.db_utils import create_booking_payment_details, update_booking_payment_details
        
        if refund_amount <= 0:
            return {
                'success': True,
                'message': 'No refund required',
                'refund_amount': 0
            }
        
        # Get original payment details to determine refund method
        original_payment = booking.booking_payment.filter(
            is_transaction_success=True
        ).order_by('-id').first()
        
        if not original_payment:
            return {
                'success': False,
                'error': 'No successful payment found for refund',
                'error_code': 'NO_PAYMENT_FOUND'
            }
        
        # Prepare refund details
        refund_details = {
            'reason': 'Reschedule fare difference refund',
            'reschedule_details': reschedule_details,
            'timestamp': timezone.now().isoformat(),
            'refund_type': 'reschedule_refund'
        }
        
        # Process refund based on original payment method
        if original_payment.payment_medium == 'Idbook' or original_payment.payment_type == 'WALLET':
            # Refund to wallet
            refund_ok, refund_status, refund_data = refund_wallet_payment(
                booking, refund_amount, refund_details
            )
            
            if refund_ok:
                return {
                    'success': True,
                    'refund_method': 'wallet',
                    'refund_amount': float(refund_amount),
                    'refund_status': refund_status,
                    'transaction_id': refund_data.get('merchant_refund_id'),
                    'message': 'Refund processed to wallet successfully'
                }
            else:
                return {
                    'success': False,
                    'error': 'Wallet refund failed',
                    'error_code': 'WALLET_REFUND_FAILED',
                    'refund_status': refund_status
                }
        else:
            # For gateway payments (PhonePe, etc.), mark for manual/gateway refund
            # Create refund record for tracking
            append_id = f"RSRF{booking.user.id if booking.user else 'GUEST'}"
            refund_payment = create_booking_payment_details(booking.id, append_id)
            refund_payment.amount = float(refund_amount)
            refund_payment.transaction_for = 'booking_refund'
            refund_payment.transaction_details = {
                'refund_type': 'reschedule_refund',
                'original_payment_id': original_payment.merchant_transaction_id,
                'original_payment_method': original_payment.payment_medium,
                'reschedule_details': reschedule_details,
                'refund_status': 'pending_gateway_refund'
            }
            refund_payment.code = 'REFUND_PENDING'
            refund_payment.message = 'Refund pending - gateway refund required'
            refund_payment.is_transaction_success = False
            refund_payment.save()
            
            return {
                'success': True,
                'refund_method': 'gateway',
                'refund_amount': float(refund_amount),
                'refund_status': 'pending_gateway_refund',
                'transaction_id': refund_payment.merchant_transaction_id,
                'message': 'Refund marked for gateway processing. Please contact support.',
                'note': 'Gateway refunds require manual processing'
            }
            
    except Exception as e:
        logger.error(f"Error processing reschedule refund: {str(e)}")
        return {
            'success': False,
            'error': f'Refund processing failed: {str(e)}',
            'error_code': 'REFUND_PROCESSING_ERROR'
        }


class FlightBookingAuthManager:
    """
    Manages authentication flow for flight bookings
    Handles both authenticated users and guest bookings with email verification
    """
    
    def __init__(self, request_data: dict, user=None):
        self.request_data = request_data
        self.user = user
        # Primary (hotel-style) fields
        self.contact_email = request_data.get('contact', {}).get('email', '')
        self.contact_phone = request_data.get('contact', {}).get('phone', '')
        # Fallback to AirIQ-style fields from AddressDetails
        addr = request_data.get('AddressDetails') or {}
        if not self.contact_email:
            self.contact_email = addr.get('EmailID', '')
        if not self.contact_phone:
            # ensure string
            self.contact_phone = str(addr.get('ContactNumber', '') or '')
        
    def validate_user_eligibility(self) -> Tuple[bool, str, User]:
        """
        Validate user eligibility for booking
        Returns: (is_eligible, message, user_object)
        """
        if self.user and self.user.is_authenticated:
            # Authenticated user - can book directly
            return True, "User authenticated", self.user
        
        # Guest booking - email verification required
        if not self.contact_email:
            return False, "Email is required for guest bookings", None
            
        # Check if user exists with this email
        existing_user = get_user_from_email(self.contact_email)
        if existing_user:
            # Allow guest flow for existing active users via OTP verification (align with hotel flow)
            if existing_user.is_active:
                return True, "Existing account - email verification required", existing_user
            else:
                return False, "Account exists but is inactive. Please contact support", existing_user
        
        # Guest user - needs email verification
        return True, "Guest booking - email verification required", None
    
    def initiate_guest_booking(self) -> Tuple[bool, str, dict]:
        """
        Initiate guest booking process with email verification
        Returns: (success, message, verification_data)
        """
        from apps.authentication.utils.authentication_utils import email_generate_otp_process
        from django.template.loader import get_template
        from IDBOOKAPI.email_utils import send_otp_email
        
        # Generate OTP for email verification
        otp = self.generate_otp()
        
        # Try async path (hotel flow). If broker/enqueue fails, send synchronously as fallback.
        email_generate_otp_process(otp, self.contact_email, 'VERIFY-GUEST')
        
        verification_data = {
            'email': self.contact_email,
            'verification_required': True,
            'message': 'OTP sent to your email for verification'
        }
        
        logger.info(f"Guest booking verification initiated for {self.contact_email}")
        return True, "Verification email sent", verification_data
    
    def verify_guest_booking_otp(self, otp: str) -> Tuple[bool, str, User]:
        """
        Verify OTP for guest booking and create temporary user
        Returns: (success, message, user_object)
        """
        from apps.authentication.utils.db_utils import check_email_otp
        
        # Check OTP
        otp_record = check_email_otp(self.contact_email, otp, 'VERIFY-GUEST')
        if not otp_record:
            return False, "Invalid or expired OTP", None
        
        # Check OTP expiry (15 minutes)
        if timezone.now() > otp_record.created + timedelta(minutes=15):
            return False, "OTP has expired", None
        
        # On OTP success: if user exists, return it; otherwise create guest user
        try:
            from apps.authentication.utils.db_utils import get_user_from_email
            existing_user = get_user_from_email(self.contact_email)
            if existing_user and existing_user.is_active:
                guest_user = existing_user
            else:
                guest_user = self.create_guest_user()
            
            # Delete the OTP record
            otp_record.delete()
            
            logger.info(f"Guest user verified for {self.contact_email}")
            return True, "Guest user verified", guest_user
        except Exception as e:
            logger.error(f"Error creating guest user: {str(e)}")
            return False, f"Error creating user account: {str(e)}", None
    
    def create_guest_user(self) -> User:
        """Create a guest user account for booking"""
        pax_list = self.request_data.get('passengers') or self.request_data.get('PaxDetailsInfo') or [{}]
        passenger_data = pax_list[0] if pax_list else {}
        
        first_name = passenger_data.get('first_name') or passenger_data.get('FirstName', '')
        last_name = passenger_data.get('last_name') or passenger_data.get('LastName', '')
        full_name = (first_name + ' ' + last_name).strip()
        
        user_data = {
            'email': self.contact_email,
            'mobile_number': self.contact_phone or '',
            'first_name': first_name,
            'last_name': last_name,
            'name': full_name
        }
        
        guest_user = create_user(user_data)
        
        # Add to guest user group (also marks active post-verification like hotel flow)
        add_group_for_guest_user(guest_user)
        
        return guest_user
    
    def generate_otp(self) -> str:
        """Generate 6-digit OTP"""
        import random
        return str(random.randint(100000, 999999))


class FlightBookingProcessor:
    """
    Main processor for flight booking operations
    Handles the complete booking flow with validation and business logic
    """
    
    def __init__(self, user, booking_data: dict):
        self.user = user
        self.booking_data = booking_data
        self.errors = []
        
    def validate_booking_data(self) -> bool:
        """Comprehensive validation of booking data"""
        
        # Validate passenger counts
        adult_count = self.booking_data.get('adult_count', 0)
        child_count = self.booking_data.get('child_count', 0)
        infant_count = self.booking_data.get('infant_count', 0)
        
        if adult_count + child_count > 9:
            self.errors.append("Total adults and children cannot exceed 9")
            
        if infant_count > adult_count:
            self.errors.append("Number of infants cannot exceed number of adults")
            
        # Validate required fields
        required_fields = ['pricing_token', 'track_id', 'flight_segments', 'passengers', 'contact']
        for field in required_fields:
            if not self.booking_data.get(field):
                self.errors.append(f"Field '{field}' is required")
        
        # Validate passenger details
        passengers = self.booking_data.get('passengers', [])
        expected_count = adult_count + child_count + infant_count
        
        if len(passengers) != expected_count:
            self.errors.append(f"Expected {expected_count} passengers, got {len(passengers)}")
        
        # Validate GST info if provided
        gst_info = self.booking_data.get('gst_info', {})
        if gst_info and gst_info.get('gst_number'):
            required_gst_fields = ['company_name', 'address', 'email', 'mobile']
            for field in required_gst_fields:
                if not gst_info.get(field):
                    self.errors.append(f"GST {field} is required when GST number is provided")
        
        return len(self.errors) == 0
    
    def calculate_pricing(self) -> Dict[str, Decimal]:
        """Calculate comprehensive pricing using AirIQ response data"""
        
        # Use AirIQ pricing data if available (from enhanced flight booking flow)
        gst_breakdown = self.booking_data.get('gst_breakdown', {})
        if gst_breakdown:
            # Use AirIQ provided GST breakdown
            basic_amount = Decimal(str(gst_breakdown.get('basic_amount', 0)))
            gross_amount = Decimal(str(gst_breakdown.get('gross_amount', 0)))
            total_gst = Decimal(str(gst_breakdown.get('total_gst', 0)))
            service_tax = Decimal(str(gst_breakdown.get('service_tax_amount', 0)))
            
            # Calculate ancillary services total
            ancillary_amount = Decimal('0.00')
            for service_type in ['seats', 'baggage', 'meals', 'other_services']:
                services = self.booking_data.get(service_type, [])
                for service in services:
                    service_price = Decimal(str(service.get('price', 0)))
                    ancillary_amount += service_price
            
            # Subtotal is basic amount + ancillary services
            subtotal = basic_amount + ancillary_amount
            
            return {
                'subtotal': subtotal,
                'gst_amount': total_gst,
                'gst_percentage': Decimal(str(gst_breakdown.get('gst_percentage', 0))),
                'gst_type': gst_breakdown.get('gst_type', ''),
                'cgst': Decimal(str(gst_breakdown.get('cgst_amount', 0))),
                'sgst': Decimal(str(gst_breakdown.get('sgst_amount', 0))),
                'igst': Decimal(str(gst_breakdown.get('igst_amount', 0))),
                'service_tax': service_tax,
                'ancillary_amount': ancillary_amount,
                'final_amount': gross_amount + ancillary_amount
            }
        
        # Fallback to legacy calculation for backward compatibility
        base_amount = Decimal(str(self.booking_data.get('total_amount', 0)))
        
        # Validate that we have valid pricing data
        if base_amount <= 0:
            raise ValueError("Invalid or missing total_amount. Flight pricing data is required for booking creation.")
        
        # Calculate ancillary services total
        ancillary_amount = Decimal('0.00')
        for service_type in ['seats', 'baggage', 'meals', 'other_services']:
            services = self.booking_data.get(service_type, [])
            for service in services:
                service_price = Decimal(str(service.get('price', 0)))
                ancillary_amount += service_price
        
        # For legacy bookings, assume GST is included in total_amount
        # This is a simplified calculation
        subtotal = base_amount + ancillary_amount
        gst_amount = base_amount * Decimal('0.05')  # Assume 5% GST
        service_tax = Decimal('0.00')
        
        return {
            'subtotal': subtotal - gst_amount,
            'gst_amount': gst_amount,
            'gst_percentage': Decimal('5.0'),
            'gst_type': 'IGST',  # Default assumption
            'cgst': Decimal('0'),
            'sgst': Decimal('0'),
            'igst': gst_amount,
            'service_tax': service_tax,
            'ancillary_amount': ancillary_amount,
            'final_amount': subtotal
        }
    
    def generate_confirmation_code(self) -> str:
        """Generate unique confirmation code"""
        return f"FL{datetime.now().strftime('%Y%m%d')}{uuid.uuid4().hex[:8].upper()}"
    
    @transaction.atomic
    def create_booking(self, airiq_response: dict = None) -> Tuple[Booking, FlightBooking]:
        """Create booking and flight booking records with AirIQ integration"""
        
        # Calculate pricing
        pricing = self.calculate_pricing()
        
        # Create FlightBooking first
        flight_booking_data = {
            'flight_no': self.booking_data['flight_segments'][0].get('flight_number', ''),
            'airline_code': self.booking_data['flight_segments'][0].get('flight_number', '')[:2],
            'flying_from': self.booking_data.get('base_origin', ''),
            'flying_to': self.booking_data.get('base_destination', ''),
            'flight_trip': self.booking_data.get('trip_type', 'O'),
            'booking_reference': self.generate_confirmation_code(),
            'status': 'CONFIRMED' if not self.booking_data.get('block_pnr') else 'HELD',
            'booking_mode': 'REALTIME',
            'selected_flight_data': {
                'segments': self.booking_data['flight_segments'],
                'pricing_token': self.booking_data['pricing_token']
            },
            'search_session_data': {
                'track_id': self.booking_data['track_id'],
                'trip_type': self.booking_data.get('trip_type', 'O'),
                'passenger_counts': {
                    'adults': self.booking_data.get('adult_count', 1),
                    'children': self.booking_data.get('child_count', 0),
                    'infants': self.booking_data.get('infant_count', 0)
                }
            }
        }
        
        # Add AirIQ response data if available
        if airiq_response:
            flight_booking_data.update({
                'airiq_pnr': airiq_response.get('AirIqPNR', ''),
                'airline_pnr': airiq_response.get('AirlinePNR', ''),
                'airiq_track_id': airiq_response.get('BookingTrackId', ''),
            })
            
            # Set hold expiry if booking is blocked
            if self.booking_data.get('block_pnr') and airiq_response.get('HoldExpiry'):
                from django.utils.dateparse import parse_datetime
                hold_expiry = airiq_response['HoldExpiry']
                try:
                    # Try parsing if it's a string
                    if isinstance(hold_expiry, str):
                        flight_booking_data['hold_expires_at'] = parse_datetime(hold_expiry)
                    else:
                        flight_booking_data['hold_expires_at'] = hold_expiry
                except Exception:
                    # Fallback to 24 hours from now
                    from django.utils import timezone
                    from datetime import timedelta
                    flight_booking_data['hold_expires_at'] = timezone.now() + timedelta(hours=24)
        
        flight_booking = FlightBooking.objects.create(**flight_booking_data)
        
        # Create main Booking record
        booking_data = {
            'user': self.user,
            'booking_type': 'FLIGHT',
            'flight_booking': flight_booking,
            'adult_count': self.booking_data.get('adult_count', 1),
            'child_count': self.booking_data.get('child_count', 0),
            'infant_count': self.booking_data.get('infant_count', 0),
            'confirmation_code': flight_booking.booking_reference,
            'status': 'pending' if flight_booking.status == 'HELD' else 'confirmed',
            'subtotal': pricing['subtotal'],
            'gst_amount': pricing['gst_amount'],
            'gst_percentage': pricing['gst_percentage'],
            'gst_type': pricing['gst_type'],
            'service_tax': pricing['service_tax'],
            'final_amount': pricing['final_amount']
        }
        
        booking = Booking.objects.create(**booking_data)
        
        # Update user profile with contact information from booking request
        if booking.user and self.booking_data.get('contact'):
            from apps.booking.utils.contact_utils import update_user_contact_info
            contact = self.booking_data.get('contact', {})
            # Get name from first passenger if not in contact
            contact_name = contact.get('name')
            if not contact_name:
                passengers = self.booking_data.get('passengers', [])
                if passengers:
                    first_pax = passengers[0]
                    first_name = first_pax.get('first_name') or first_pax.get('FirstName', '')
                    last_name = first_pax.get('last_name') or first_pax.get('LastName', '')
                    contact_name = (first_name + ' ' + last_name).strip()
            
            update_user_contact_info(
                user=booking.user,
                contact_email=contact.get('email'),
                contact_phone=contact.get('phone'),
                contact_name=contact_name
            )
        
        # Store contact information in flight_booking for SMS/email retrieval
        if booking.flight_booking and self.booking_data.get('contact'):
            contact = self.booking_data.get('contact', {})
            # Get name from first passenger if not in contact
            contact_name = contact.get('name')
            if not contact_name:
                passengers = self.booking_data.get('passengers', [])
                if passengers:
                    first_pax = passengers[0]
                    first_name = first_pax.get('first_name') or first_pax.get('FirstName', '')
                    last_name = first_pax.get('last_name') or first_pax.get('LastName', '')
                    contact_name = (first_name + ' ' + last_name).strip()
            
            # Store contact info in selected_flight_data for easy retrieval
            if not booking.flight_booking.selected_flight_data:
                booking.flight_booking.selected_flight_data = {}
            if 'contact' not in booking.flight_booking.selected_flight_data:
                booking.flight_booking.selected_flight_data['contact'] = {}
            
            booking.flight_booking.selected_flight_data['contact'].update({
                'email': contact.get('email', ''),
                'phone': contact.get('phone', ''),
                'name': contact_name or ''
            })
            booking.flight_booking.save(update_fields=['selected_flight_data'])
        
        # Generate access token for all bookings (includes user group info)
        if booking.user:
            from apps.booking.utils.booking_utils import generate_guest_access_token
            # Generate token with user information (includes group info)
            max_attempts = 10
            for attempt in range(max_attempts):
                guest_token = generate_guest_access_token(booking.id, user=booking.user)
                # Check if token already exists (very unlikely but handle it)
                if not Booking.objects.filter(guest_access_token=guest_token).exists():
                    booking.guest_access_token = guest_token
                    booking.save(update_fields=['guest_access_token'])
                    break
        
        # Create booking meta info
        BookingMetaInfo.objects.create(
            booking=booking,
            booking_confirmed_date=timezone.now() if booking.status == 'confirmed' else None
        )
        
        # Send booking confirmation notifications if confirmed
        if booking.status == 'confirmed':
            self._send_booking_notifications(booking)
        
        return booking, flight_booking
    
    @transaction.atomic
    def create_booking_without_airiq(self) -> Tuple[Booking, FlightBooking]:
        """Create booking and flight booking records without AirIQ integration (payment pending)"""
        
        # Calculate pricing
        pricing = self.calculate_pricing()
        
        # Create FlightBooking first (without AirIQ data)
        flight_booking_data = {
            'flight_no': '',  # Will be populated from request data
            'airline_code': '',  # Will be populated from request data
            'flying_from': self.booking_data.get('base_origin', ''),
            'flying_to': self.booking_data.get('base_destination', ''),
            'flight_trip': self.booking_data.get('trip_type', 'O'),
            'booking_reference': '',  # Will be set in enhanced viewset
            'status': 'PENDING_PAYMENT',
            'booking_mode': 'REALTIME',
            'selected_flight_data': {
                'segments': self.booking_data['flight_segments'],
                'pricing_token': self.booking_data.get('pricing_token', '')
            },
            'search_session_data': {
                'track_id': self.booking_data['track_id'],
                'trip_type': self.booking_data.get('trip_type', 'O'),
                'passenger_counts': {
                    'adults': self.booking_data.get('adult_count', 1),
                    'children': self.booking_data.get('child_count', 0),
                    'infants': self.booking_data.get('infant_count', 0)
                }
            },
            # Store original request data for later AirIQ integration
            'airiq_request_data': {},  # Will be set in enhanced viewset
            'pricing_validation_data': {}  # Will be set in enhanced viewset
        }
        
        flight_booking = FlightBooking.objects.create(**flight_booking_data)
        
        # Create main Booking record
        booking_data = {
            'user': self.user,
            'booking_type': 'FLIGHT',
            'flight_booking': flight_booking,
            'adult_count': self.booking_data.get('adult_count', 1),
            'child_count': self.booking_data.get('child_count', 0),
            'infant_count': self.booking_data.get('infant_count', 0),
            'confirmation_code': '',  # Will be set in enhanced viewset
            'status': 'pending',
            'subtotal': pricing['subtotal'],
            'gst_amount': pricing['gst_amount'],
            'gst_percentage': pricing['gst_percentage'],
            'gst_type': pricing['gst_type'],
            'service_tax': pricing['service_tax'],
            'final_amount': pricing['final_amount']
        }
        
        booking = Booking.objects.create(**booking_data)
        
        # Update user profile with contact information from booking request
        if booking.user and self.booking_data.get('contact'):
            from apps.booking.utils.contact_utils import update_user_contact_info
            contact = self.booking_data.get('contact', {})
            # Get name from first passenger if not in contact
            contact_name = contact.get('name')
            if not contact_name:
                passengers = self.booking_data.get('passengers', [])
                if passengers:
                    first_pax = passengers[0]
                    first_name = first_pax.get('first_name') or first_pax.get('FirstName', '')
                    last_name = first_pax.get('last_name') or first_pax.get('LastName', '')
                    contact_name = (first_name + ' ' + last_name).strip()
            
            update_user_contact_info(
                user=booking.user,
                contact_email=contact.get('email'),
                contact_phone=contact.get('phone'),
                contact_name=contact_name
            )
        
        # Store contact information in flight_booking for SMS/email retrieval
        if booking.flight_booking and self.booking_data.get('contact'):
            contact = self.booking_data.get('contact', {})
            # Get name from first passenger if not in contact
            contact_name = contact.get('name')
            if not contact_name:
                passengers = self.booking_data.get('passengers', [])
                if passengers:
                    first_pax = passengers[0]
                    first_name = first_pax.get('first_name') or first_pax.get('FirstName', '')
                    last_name = first_pax.get('last_name') or first_pax.get('LastName', '')
                    contact_name = (first_name + ' ' + last_name).strip()
            
            # Store contact info in selected_flight_data for easy retrieval
            if not booking.flight_booking.selected_flight_data:
                booking.flight_booking.selected_flight_data = {}
            if 'contact' not in booking.flight_booking.selected_flight_data:
                booking.flight_booking.selected_flight_data['contact'] = {}
            
            booking.flight_booking.selected_flight_data['contact'].update({
                'email': contact.get('email', ''),
                'phone': contact.get('phone', ''),
                'name': contact_name or ''
            })
            booking.flight_booking.save(update_fields=['selected_flight_data'])
        
        # Generate access token for all bookings (includes user group info)
        if booking.user:
            from apps.booking.utils.booking_utils import generate_guest_access_token
            # Generate token with user information (includes group info)
            max_attempts = 10
            for attempt in range(max_attempts):
                guest_token = generate_guest_access_token(booking.id, user=booking.user)
                # Check if token already exists (very unlikely but handle it)
                if not Booking.objects.filter(guest_access_token=guest_token).exists():
                    booking.guest_access_token = guest_token
                    booking.save(update_fields=['guest_access_token'])
                    break
        
        # Create booking meta info (without confirmation date)
        BookingMetaInfo.objects.create(
            booking=booking,
            booking_confirmed_date=None  # Will be set after payment confirmation
        )
        
        # No notifications sent until payment is confirmed
        
        return booking, flight_booking
    
    def create_passengers(self, booking: Booking, flight_booking: FlightBooking) -> List[FlightPassenger]:
        """Create passenger records"""
        passengers = []
        
        for passenger_data in self.booking_data.get('passengers', []):
            # Convert date strings to proper date objects
            date_of_birth = self._convert_date_string(passenger_data.get('date_of_birth'))
            passport_expiry = self._convert_date_string(passenger_data.get('passport_expiry'))
            passport_issued_date = self._convert_date_string(passenger_data.get('passport_issued_date'))
            
            passenger = FlightPassenger.objects.create(
                flight_booking=flight_booking,
                booking=booking,
                passenger_reference=passenger_data['passenger_ref'],
                passenger_type=passenger_data['passenger_type'],
                title=passenger_data['title'],
                first_name=passenger_data['first_name'],
                last_name=passenger_data['last_name'],
                date_of_birth=date_of_birth,
                gender=passenger_data['gender'].lower(),
                passport_number=passenger_data.get('passport_number', ''),
                passport_expiry=passport_expiry,
                passport_issued_date=passport_issued_date,
                passport_country_code=passenger_data.get('passport_country_code', ''),
                infant_with_passenger=self._convert_infant_ref(passenger_data.get('infant_ref'))
            )
            passengers.append(passenger)
        
        return passengers
    
    def _convert_date_string(self, date_string):
        """Convert date string to date object, handling multiple formats"""
        if not date_string:
            return None
            
        if isinstance(date_string, str):
            from datetime import datetime
            
            # Try different input formats
            formats = ['%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y', '%Y/%m/%d', '%m/%d/%Y']
            
            for fmt in formats:
                try:
                    dt = datetime.strptime(date_string, fmt)
                    return dt.date()
                except ValueError:
                    continue
            
            # If no format matched, raise an error
            raise ValueError(f"Unable to parse date: {date_string}. Expected formats: DD/MM/YYYY, YYYY-MM-DD, DD-MM-YYYY, YYYY/MM/DD, MM/DD/YYYY")
        
        return date_string
    
    def _convert_infant_ref(self, infant_ref):
        """Convert infant reference to integer or None"""
        if not infant_ref or infant_ref == '':
            return None
        
        try:
            return int(infant_ref)
        except (ValueError, TypeError):
            return None
    
    def create_ancillary_services(self, flight_booking: FlightBooking, passengers: List[FlightPassenger]) -> List[FlightAncillaryService]:
        """Create ancillary service records"""
        services = []
        passenger_map = {p.passenger_reference: p for p in passengers}
        
        # Process different service types
        service_types_map = {
            'seats': 'SEAT',
            'baggage': 'BAGGAGE', 
            'meals': 'MEAL',
            'other_services': 'OTHER'
        }
        
        for service_key, service_type in service_types_map.items():
            service_list = self.booking_data.get(service_key, [])
            
            for service_data in service_list:
                passenger_ref = service_data['passenger_ref']
                passenger = passenger_map.get(passenger_ref)
                
                if passenger:
                    service = FlightAncillaryService.objects.create(
                        flight_booking=flight_booking,
                        passenger=passenger,
                        service_type=service_type,
                        airiq_service_id=service_data['service_id'],
                        service_code=service_data['service_id'],
                        service_description=f"{service_type.title()} Service",
                        service_price=Decimal('0.00')  # This would come from AirIQ response
                    )
                    services.append(service)
        
        return services
    
    def _send_booking_notifications(self, booking: Booking):
        """Send booking confirmation notifications"""
        try:
            # Import here to avoid circular imports
            from apps.booking.tasks import (
                send_flight_booking_task, send_booking_email_task, create_invoice_task
            )
            
            # Send flight-specific SMS notifications
            send_flight_booking_task.delay(booking.id, 'confirmed')
            
            # Send booking email (uses existing email template)
            send_booking_email_task.delay(booking.id, 'confirmed-booking')
            
            # Create invoice
            create_invoice_task.delay(booking.id, send_email=False)
            
            logger.info(f"Booking notifications sent for flight booking {booking.id}")
            
        except Exception as e:
            logger.error(f"Error sending booking notifications for {booking.id}: {str(e)}")


class FlightCancellationManager:
    """
    Handles flight booking cancellations and refunds
    Similar to hotel booking cancellation flow
    """
    
    def __init__(self, booking: Booking):
        self.booking = booking
        self.flight_booking = booking.flight_booking
        
    def get_cancellation_policy(self) -> dict:
        """Get cancellation policy for the flight"""
        # This would typically come from AirIQ fare rules
        # For now, using default policy
        
        hours_to_departure = self.calculate_hours_to_departure()
        
        if hours_to_departure >= 24:
            return {
                'policy_name': '24+ Hours Before',
                'refund_percentage': 85,
                'cancellation_fee': float(self.booking.final_amount * Decimal('0.15')),
                'is_refundable': True
            }
        elif hours_to_departure >= 2:
            return {
                'policy_name': '2-24 Hours Before', 
                'refund_percentage': 50,
                'cancellation_fee': float(self.booking.final_amount * Decimal('0.50')),
                'is_refundable': True
            }
        else:
            return {
                'policy_name': 'Less than 2 Hours',
                'refund_percentage': 0,
                'cancellation_fee': float(self.booking.final_amount),
                'is_refundable': False
            }
    
    def calculate_hours_to_departure(self) -> float:
        """Calculate hours to flight departure"""
        if not self.flight_booking.departure_date:
            return 0
        
        now = timezone.now()
        departure = self.flight_booking.departure_date
        
        if departure <= now:
            return 0
        
        time_diff = departure - now
        return time_diff.total_seconds() / 3600
    
    def calculate_refund_amount(self, cancellation_policy: dict) -> Tuple[Decimal, dict]:
        """Calculate refund amount based on policy"""
        from apps.booking.utils.booking_utils import calculate_refund_amount
        from django.db import models
        
        # Get total payment made
        payment_details = self.booking.booking_payment.filter(
            is_transaction_success=True
        ).aggregate(total=models.Sum('amount'))['total'] or Decimal('0')
        
        if payment_details == 0:
            return Decimal('0'), {
                'total_paid': 0,
                'refund_amount': 0,
                'cancellation_fee': 0,
                'reason': 'No payment found'
            }
        
        refund_amount, refund_details = calculate_refund_amount(
            total_payment_made=payment_details,
            applicable_policy=cancellation_policy
        )
        
        return refund_amount, refund_details
    
    def process_cancellation(self, remarks: str = '') -> Tuple[bool, dict]:
        """Process flight booking cancellation"""
        try:
            # Get cancellation policy
            policy = self.get_cancellation_policy()
            
            # Calculate refund amount
            refund_amount, refund_details = self.calculate_refund_amount(policy)
            
            # Update booking status
            self.booking.status = 'canceled'
            self.booking.save()
            
            # Update flight booking status
            self.flight_booking.status = 'CANCELLED'
            self.flight_booking.cancelled_at = timezone.now()
            self.flight_booking.save()
            
            # Create cancellation details
            cancellation_details = {
                'cancelled_at': timezone.now().isoformat(),
                'cancelled_by': self.booking.user.email if self.booking.user else 'System',
                'cancellation_policy': policy,
                'refund_details': refund_details,
                'remarks': remarks
            }
            
            # Process refund if applicable
            if refund_amount > 0:
                success, refund_status, refund_data = self.process_refund(
                    refund_amount, cancellation_details
                )
                cancellation_details['refund_status'] = refund_status
                cancellation_details['refund_data'] = refund_data
            else:
                cancellation_details['refund_status'] = 'no_refund'
            
            logger.info(f"Flight booking {self.booking.id} cancelled successfully")
            
            # Send cancellation notifications
            self._send_cancellation_notifications(refund_amount)
            
            return True, cancellation_details
            
        except Exception as e:
            logger.error(f"Error cancelling flight booking {self.booking.id}: {str(e)}")
            return False, {'error': str(e)}
    
    def process_refund(self, refund_amount: Decimal, cancellation_details: dict) -> Tuple[bool, str, dict]:
        """Process refund for cancelled booking"""
        from apps.booking.utils.booking_utils import refund_wallet_payment
        
        # Get payment details
        payment_details = self.booking.booking_payment.filter(
            is_transaction_success=True
        ).first()
        
        if not payment_details:
            return False, 'no_payment_found', {'error': 'No successful payment found'}
        
        # Process refund based on payment method
        if payment_details.payment_medium == 'Idbook':  # Wallet payment
            return refund_wallet_payment(self.booking, refund_amount, cancellation_details)
        else:
            # For other payment methods (PhonePe, etc.), use existing refund mechanism
            return self.process_gateway_refund(payment_details, refund_amount, cancellation_details)
    
    def process_gateway_refund(self, payment_details: BookingPaymentDetail, 
                             refund_amount: Decimal, cancellation_details: dict) -> Tuple[bool, str, dict]:
        """Process refund through payment gateway"""
        # Similar to hotel booking refund process
        # This would integrate with PhonePe/PayU refund APIs
        
        try:
            # Generate refund transaction ID
            append_id = f"FLRF{self.booking.user.id}"
            merchant_refund_id = get_unique_id_from_time(append_id)
            
            # Create refund payment record
            refund_payment = BookingPaymentDetail.objects.create(
                booking=self.booking,
                merchant_transaction_id=merchant_refund_id,
                transaction_id='',
                code='REFUND_INITIATED',
                message='Flight booking refund initiated',
                payment_type=payment_details.payment_type,
                payment_medium=payment_details.payment_medium,
                amount=refund_amount,
                is_transaction_success=False,  # Will be updated after gateway response
                transaction_for='booking_refund',
                transaction_details={
                    'original_transaction_id': payment_details.merchant_transaction_id,
                    'refund_amount': float(refund_amount),
                    'refund_reason': 'Flight booking cancellation'
                }
            )
            
            # Here you would integrate with payment gateway refund API
            # For now, marking as pending
            
            return True, 'refund_initiated', {
                'merchant_refund_id': merchant_refund_id,
                'refund_amount': float(refund_amount),
                'status': 'initiated'
            }
            
        except Exception as e:
            logger.error(f"Error processing gateway refund: {str(e)}")
            return False, 'refund_failed', {'error': str(e)}
    
    def _send_cancellation_notifications(self, refund_amount: Decimal):
        """Send cancellation and refund notifications"""
        try:
            # Import here to avoid circular imports
            from apps.booking.tasks import (
                send_flight_booking_task, send_cancelled_booking_task
            )
            
            # Send flight-specific cancellation SMS with refund amount
            send_flight_booking_task.delay(
                self.booking.id, 
                'cancelled',
                refund_amount=float(refund_amount) if refund_amount else 0
            )
            
            # Send general cancellation email
            send_cancelled_booking_task.delay(self.booking.id)
            
            logger.info(f"Cancellation notifications sent for flight booking {self.booking.id}")
            
        except Exception as e:
            logger.error(f"Error sending cancellation notifications for {self.booking.id}: {str(e)}")


def send_flight_ticket_notification(booking_id: int):
    """Helper function to send flight ticket issued notifications"""
    try:
        from apps.booking.tasks import send_flight_booking_task
        
        # Verify booking is a flight booking
        from apps.booking.models import Booking
        booking = Booking.objects.filter(
            id=booking_id, 
            booking_type='FLIGHT'
        ).first()
        
        if booking:
            send_flight_booking_task.delay(booking_id, 'ticket_issued')
            logger.info(f"Flight ticket notification sent for booking {booking_id}")
        else:
            logger.error(f"Flight booking not found for booking_id: {booking_id}")
            
    except Exception as e:
        logger.error(f"Error sending ticket notification for {booking_id}: {str(e)}")


def calculate_flight_booking_gst(amount: Decimal, is_business: bool = False, 
                               origin_state: str = 'DL', destination_state: str = 'DL') -> dict:
    """
    Calculate GST for flight bookings
    
    Args:
        amount: Base booking amount
        is_business: Whether it's a business booking (GST applicable)
        origin_state: Origin state code
        destination_state: Destination state code
    
    Returns:
        dict: GST calculation details
    """
    if not is_business:
        return {
            'gst_rate': Decimal('0'),
            'cgst': Decimal('0'),
            'sgst': Decimal('0'),
            'igst': Decimal('0'),
            'total_gst': Decimal('0'),
            'gst_type': 'NO_GST'
        }
    
    # 5% GST for domestic flight bookings
    gst_rate = Decimal('5.00')
    
    if origin_state == destination_state:
        # Intrastate - CGST + SGST
        cgst = sgst = (amount * gst_rate / 2) / Decimal('100')
        igst = Decimal('0')
        gst_type = 'CGST/SGST'
    else:
        # Interstate - IGST
        igst = (amount * gst_rate) / Decimal('100')
        cgst = sgst = Decimal('0')
        gst_type = 'IGST'
    
    return {
        'gst_rate': gst_rate,
        'cgst': cgst,
        'sgst': sgst,
        'igst': igst,
        'total_gst': cgst + sgst + igst,
        'gst_type': gst_type
    }


def validate_flight_booking_eligibility(user, booking_data: dict) -> Tuple[bool, List[str]]:
    """
    Validate if user is eligible for flight booking
    
    Returns:
        Tuple[bool, List[str]]: (is_eligible, error_messages)
    """
    errors = []
    
    # Check authentication requirements
    auth_manager = FlightBookingAuthManager(booking_data, user)
    is_eligible, message, validated_user = auth_manager.validate_user_eligibility()
    
    if not is_eligible:
        errors.append(message)
        return False, errors
    
    # Additional validations can be added here
    # - Credit checks
    # - Booking limits
    # - Blacklist checks
    # - etc.
    
    return len(errors) == 0, errors


def get_flight_booking_stats(user, date_from=None, date_to=None) -> dict:
    """
    Get flight booking statistics for user/admin
    """
    from django.db.models import Count, Sum, Avg
    from datetime import datetime, timedelta
    
    if not date_to:
        date_to = datetime.now()
    if not date_from:
        date_from = date_to - timedelta(days=30)
    
    bookings = Booking.objects.filter(
        booking_type='FLIGHT',
        created__date__range=[date_from, date_to]
    )
    
    if user and not user.is_staff:
        bookings = bookings.filter(user=user)
    
    stats = bookings.aggregate(
        total_bookings=Count('id'),
        confirmed_bookings=Count('id', filter=models.Q(status='confirmed')),
        cancelled_bookings=Count('id', filter=models.Q(status='canceled')),
        pending_bookings=Count('id', filter=models.Q(status='pending')),
        total_revenue=Sum('final_amount'),
        average_booking_value=Avg('final_amount')
    )
    
        # Get top routes
    from django.db import models
    top_routes = bookings.filter(
        flight_booking__isnull=False
    ).values(
        'flight_booking__flying_from',
        'flight_booking__flying_to'
    ).annotate(
        booking_count=Count('id'),
        total_revenue=Sum('final_amount')
    ).order_by('-booking_count')[:10]
    
    # Monthly trends
    monthly_trends = []
    for i in range(6):  # Last 6 months
        month_start = (date_to.replace(day=1) - timedelta(days=i*30)).replace(day=1)
        month_end = month_start.replace(day=28) + timedelta(days=4)
        month_end = month_end.replace(day=1) - timedelta(days=1)
        
        month_stats = bookings.filter(
            created__date__range=[month_start.date(), month_end.date()]
        ).aggregate(
            bookings=Count('id'),
            revenue=Sum('final_amount')
        )
        
        monthly_trends.append({
            'month': month_start.strftime('%B %Y'),
            'bookings': month_stats['bookings'] or 0,
            'revenue': float(month_stats['revenue'] or 0)
        })
    
    return {
        'total_bookings': stats['total_bookings'] or 0,
        'confirmed_bookings': stats['confirmed_bookings'] or 0,
        'cancelled_bookings': stats['cancelled_bookings'] or 0,
        'pending_bookings': stats['pending_bookings'] or 0,
        'total_revenue': stats['total_revenue'] or Decimal('0'),
        'average_booking_value': stats['average_booking_value'] or Decimal('0'),
        'top_routes': list(top_routes),
        'monthly_trends': monthly_trends
    }