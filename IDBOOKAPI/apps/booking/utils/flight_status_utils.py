"""
Flight booking status tracking and retrieval utilities
Handles booking status updates, AirIQ integration, and booking details retrieval
"""

from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
from django.utils import timezone
from django.db.models import Q, F, Value, Case, When
from django.db.models.functions import Concat
from django.conf import settings
import logging

from ..models import (
    Booking, FlightBooking, FlightPassenger, FlightAncillaryService,
    BookingPaymentDetail, Invoice, BookingMetaInfo
)
from apps.flights.services.airiq_service import AirIQService
from IDBOOKAPI.basic_resources import BOOKING_STATUS_CHOICES

logger = logging.getLogger(__name__)


class FlightBookingStatusTracker:
    """
    Handles flight booking status tracking and updates
    Integrates with AirIQ for real-time status updates
    """
    
    def __init__(self, booking: Booking = None, booking_id: int = None):
        if booking:
            self.booking = booking
        elif booking_id:
            self.booking = Booking.objects.filter(
                id=booking_id, 
                booking_type='FLIGHT'
            ).select_related('flight_booking', 'user').first()
        else:
            raise ValueError("Either booking object or booking_id must be provided")
            
        if not self.booking or not self.booking.flight_booking:
            raise ValueError("Valid flight booking not found")
            
        self.flight_booking = self.booking.flight_booking
        self.airiq = AirIQService()
    
    def get_current_status(self) -> Dict:
        """Get current booking status with detailed information"""
        
        status_info = {
            'booking_id': self.booking.id,
            'booking_status': self.booking.status,
            'flight_status': self.flight_booking.status,
            'confirmation_code': self.booking.confirmation_code or '',
            'airiq_pnr': self.flight_booking.airiq_pnr or '',
            'airline_pnr': self.flight_booking.airline_pnr or '',
            'last_updated': self.booking.updated.isoformat(),
            'flight_details': self._get_flight_details(),
            'payment_status': self._get_payment_status(),
            'ticket_status': self._get_ticket_status()
        }
        
        # Add status-specific information
        if self.booking.status == 'confirmed':
            status_info['confirmed_at'] = self.flight_booking.confirmed_at.isoformat() if self.flight_booking.confirmed_at else None
        elif self.booking.status == 'canceled':
            status_info['cancelled_at'] = self.flight_booking.cancelled_at.isoformat() if self.flight_booking.cancelled_at else None
        elif self.flight_booking.status == 'HELD':
            status_info['hold_expires_at'] = self.flight_booking.hold_expires_at.isoformat() if self.flight_booking.hold_expires_at else None
        
        return status_info
    
    def update_status_from_airiq(self) -> Dict:
        """Update booking status from AirIQ system"""
        
        try:
            if not self.flight_booking.airiq_track_id:
                return {
                    'success': False,
                    'error': 'No AirIQ tracking ID found',
                    'error_code': 'MISSING_TRACKING_ID'
                }
            
            # Get status from AirIQ
            airiq_status = self.airiq.get_booking_status(self.flight_booking.airiq_track_id)
            
            if not airiq_status.get('success'):
                return {
                    'success': False,
                    'error': 'Failed to get status from AirIQ',
                    'error_code': 'AIRIQ_STATUS_FAILED',
                    'airiq_response': airiq_status
                }
            
            # Parse AirIQ status and update booking
            booking_data = airiq_status.get('data', {})
            self._update_from_airiq_data(booking_data)
            
            return {
                'success': True,
                'status_updated': True,
                'current_status': self.get_current_status(),
                'airiq_data': booking_data
            }
            
        except Exception as e:
            logger.error(f"Error updating status from AirIQ: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'error_code': 'STATUS_UPDATE_ERROR'
            }
    
    def check_flight_schedule_updates(self) -> Dict:
        """Check for flight schedule updates from AirIQ"""
        
        try:
            if not self.flight_booking.airiq_pnr:
                return {
                    'success': False,
                    'error': 'No AirIQ PNR found',
                    'error_code': 'MISSING_AIRIQ_PNR'
                }
            
            # Get flight details from AirIQ
            flight_details = self.airiq.get_flight_details(self.flight_booking.airiq_pnr)
            
            if not flight_details.get('success'):
                return {
                    'success': False,
                    'error': 'Failed to get flight details from AirIQ',
                    'error_code': 'AIRIQ_DETAILS_FAILED',
                    'airiq_response': flight_details
                }
            
            # Check for schedule changes
            schedule_changes = self._check_schedule_changes(flight_details.get('data', {}))
            
            if schedule_changes:
                # Notify customer about changes
                self._notify_schedule_changes(schedule_changes)
            
            return {
                'success': True,
                'schedule_changes': schedule_changes,
                'flight_details': flight_details.get('data', {})
            }
            
        except Exception as e:
            logger.error(f"Error checking flight schedule updates: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'error_code': 'SCHEDULE_CHECK_ERROR'
            }
    
    def get_booking_timeline(self) -> List[Dict]:
        """Get booking timeline with all status changes"""
        
        timeline = []
        
        # Booking creation
        timeline.append({
            'event': 'Booking Created',
            'timestamp': self.booking.created.isoformat(),
            'status': 'pending',
            'description': f'Flight booking created for {self.flight_booking.flying_from} to {self.flight_booking.flying_to}'
        })
        
        # Payment events
        payments = BookingPaymentDetail.objects.filter(booking=self.booking).order_by('created')
        for payment in payments:
            if payment.is_transaction_success:
                timeline.append({
                    'event': 'Payment Successful',
                    'timestamp': payment.created.isoformat(),
                    'status': 'paid',
                    'description': f'Payment of ₹{payment.amount} via {payment.payment_medium}'
                })
            elif payment.code == 'PAYMENT_INITIATED':
                timeline.append({
                    'event': 'Payment Initiated',
                    'timestamp': payment.created.isoformat(),
                    'status': 'payment_pending',
                    'description': f'Payment initiated via {payment.payment_medium}'
                })
        
        # Booking confirmation
        if self.booking.status == 'confirmed' and hasattr(self.booking, 'meta_info'):
            if self.booking.meta_info.booking_confirmed_date:
                timeline.append({
                    'event': 'Booking Confirmed',
                    'timestamp': self.booking.meta_info.booking_confirmed_date.isoformat(),
                    'status': 'confirmed',
                    'description': f'Booking confirmed with code {self.booking.confirmation_code}'
                })
        
        # Ticket issuance
        if self.flight_booking.flight_ticket:
            timeline.append({
                'event': 'Ticket Issued',
                'timestamp': self.flight_booking.updated.isoformat(),
                'status': 'ticket_issued',
                'description': 'Flight ticket issued and attached to booking'
            })
        
        # Cancellation
        if self.booking.status == 'canceled':
            timeline.append({
                'event': 'Booking Cancelled',
                'timestamp': self.flight_booking.cancelled_at.isoformat() if self.flight_booking.cancelled_at else self.booking.updated.isoformat(),
                'status': 'canceled',
                'description': 'Booking cancelled by customer'
            })
        
        # Flight departure (estimated)
        if self.flight_booking.departure_date and self.flight_booking.departure_date > timezone.now():
            timeline.append({
                'event': 'Flight Departure (Scheduled)',
                'timestamp': self.flight_booking.departure_date.isoformat(),
                'status': 'scheduled',
                'description': f'Flight departure from {self.flight_booking.flying_from}'
            })
        
        return sorted(timeline, key=lambda x: x['timestamp'])
    
    def _get_flight_details(self) -> Dict:
        """Get comprehensive flight details"""
        
        return {
            'flight_no': self.flight_booking.flight_no or 'TBD',
            'airline_code': self.flight_booking.airline_code or '',
            'flying_from': self.flight_booking.flying_from,
            'flying_to': self.flight_booking.flying_to,
            'flight_class': self.flight_booking.flight_class,
            'flight_trip': self.flight_booking.flight_trip,
            'departure_date': self.flight_booking.departure_date.isoformat() if self.flight_booking.departure_date else None,
            'arrival_date': self.flight_booking.arrival_date.isoformat() if self.flight_booking.arrival_date else None,
            'return_date': self.flight_booking.return_date.isoformat() if self.flight_booking.return_date else None,
            'booking_mode': self.flight_booking.booking_mode
        }
    
    def _get_payment_status(self) -> Dict:
        """Get payment status details"""
        
        latest_payment = BookingPaymentDetail.objects.filter(
            booking=self.booking
        ).order_by('-created').first()
        
        if not latest_payment:
            return {
                'status': 'no_payment',
                'total_amount': float(self.booking.final_amount),
                'paid_amount': float(self.booking.total_payment_made),
                'pending_amount': float(self.booking.final_amount - self.booking.total_payment_made)
            }
        
        return {
            'status': 'paid' if latest_payment.is_transaction_success else 'failed',
            'payment_method': latest_payment.payment_medium,
            'transaction_id': latest_payment.transaction_id or '',
            'total_amount': float(self.booking.final_amount),
            'paid_amount': float(self.booking.total_payment_made),
            'pending_amount': float(self.booking.final_amount - self.booking.total_payment_made),
            'last_payment_date': latest_payment.created.isoformat()
        }
    
    def _get_ticket_status(self) -> Dict:
        """Get ticket issuance status"""
        
        return {
            'issued': bool(self.flight_booking.flight_ticket),
            'ticket_url': self.flight_booking.flight_ticket.url if self.flight_booking.flight_ticket else None,
            'e_ticket_number': self.flight_booking.airline_pnr or '',
            'can_download': bool(self.flight_booking.flight_ticket)
        }
    
    def _update_from_airiq_data(self, airiq_data: Dict):
        """Update booking from AirIQ status data"""
        
        try:
            # Update flight booking fields based on AirIQ data
            updates_made = False
            
            # Update PNRs if available
            if 'AirlinePNR' in airiq_data and airiq_data['AirlinePNR'] != self.flight_booking.airline_pnr:
                self.flight_booking.airline_pnr = airiq_data['AirlinePNR']
                updates_made = True
            
            # Update flight status
            if 'Status' in airiq_data:
                new_status = self._map_airiq_status(airiq_data['Status'])
                if new_status != self.flight_booking.status:
                    self.flight_booking.status = new_status
                    updates_made = True
            
            # Update flight details if available
            if 'FlightDetails' in airiq_data:
                flight_details = airiq_data['FlightDetails']
                
                if 'FlightNumber' in flight_details and flight_details['FlightNumber'] != self.flight_booking.flight_no:
                    self.flight_booking.flight_no = flight_details['FlightNumber']
                    updates_made = True
                
                # Update departure/arrival times if changed
                if 'DepartureTime' in flight_details:
                    new_departure = datetime.fromisoformat(flight_details['DepartureTime'])
                    if new_departure != self.flight_booking.departure_date:
                        self.flight_booking.departure_date = new_departure
                        updates_made = True
                
                if 'ArrivalTime' in flight_details:
                    new_arrival = datetime.fromisoformat(flight_details['ArrivalTime'])
                    if new_arrival != self.flight_booking.arrival_date:
                        self.flight_booking.arrival_date = new_arrival
                        updates_made = True
            
            if updates_made:
                self.flight_booking.save()
                logger.info(f"Updated flight booking {self.booking.id} from AirIQ data")
                
        except Exception as e:
            logger.error(f"Error updating booking from AirIQ data: {str(e)}")
    
    def _map_airiq_status(self, airiq_status: str) -> str:
        """Map AirIQ status to internal flight booking status"""
        
        status_mapping = {
            'CONFIRMED': 'CONFIRMED',
            'TICKETED': 'TICKETED',
            'CANCELLED': 'CANCELLED',
            'PENDING': 'PENDING',
            'HOLD': 'HELD',
            'EXPIRED': 'EXPIRED',
            'REFUNDED': 'REFUNDED'
        }
        
        return status_mapping.get(airiq_status.upper(), 'UNKNOWN')
    
    def _check_schedule_changes(self, airiq_flight_data: Dict) -> List[Dict]:
        """Check for flight schedule changes"""
        
        changes = []
        
        try:
            if 'FlightDetails' in airiq_flight_data:
                flight_details = airiq_flight_data['FlightDetails']
                
                # Check departure time change
                if 'DepartureTime' in flight_details:
                    new_departure = datetime.fromisoformat(flight_details['DepartureTime'])
                    if self.flight_booking.departure_date and abs((new_departure - self.flight_booking.departure_date).total_seconds()) > 300:  # 5 minutes threshold
                        changes.append({
                            'type': 'departure_time_change',
                            'field': 'departure_date',
                            'old_value': self.flight_booking.departure_date.isoformat(),
                            'new_value': new_departure.isoformat(),
                            'description': f'Departure time changed from {self.flight_booking.departure_date.strftime("%Y-%m-%d %H:%M")} to {new_departure.strftime("%Y-%m-%d %H:%M")}'
                        })
                
                # Check arrival time change
                if 'ArrivalTime' in flight_details:
                    new_arrival = datetime.fromisoformat(flight_details['ArrivalTime'])
                    if self.flight_booking.arrival_date and abs((new_arrival - self.flight_booking.arrival_date).total_seconds()) > 300:
                        changes.append({
                            'type': 'arrival_time_change',
                            'field': 'arrival_date',
                            'old_value': self.flight_booking.arrival_date.isoformat(),
                            'new_value': new_arrival.isoformat(),
                            'description': f'Arrival time changed from {self.flight_booking.arrival_date.strftime("%Y-%m-%d %H:%M")} to {new_arrival.strftime("%Y-%m-%d %H:%M")}'
                        })
                
                # Check flight number change
                if 'FlightNumber' in flight_details:
                    new_flight_no = flight_details['FlightNumber']
                    if new_flight_no != self.flight_booking.flight_no:
                        changes.append({
                            'type': 'flight_number_change',
                            'field': 'flight_no',
                            'old_value': self.flight_booking.flight_no,
                            'new_value': new_flight_no,
                            'description': f'Flight number changed from {self.flight_booking.flight_no} to {new_flight_no}'
                        })
        
        except Exception as e:
            logger.error(f"Error checking schedule changes: {str(e)}")
        
        return changes
    
    def _notify_schedule_changes(self, changes: List[Dict]):
        """Notify customer about schedule changes"""
        
        try:
            from apps.booking.tasks import send_flight_booking_task
            
            # Send notification about schedule changes
            # This would typically send an email/SMS to the customer
            
            logger.info(f"Schedule changes detected for booking {self.booking.id}: {len(changes)} changes")
            
            # You could implement specific notification logic here
            # For now, we'll log the changes
            for change in changes:
                logger.info(f"Schedule change: {change['description']}")
                
        except Exception as e:
            logger.error(f"Error notifying schedule changes: {str(e)}")


class FlightBookingRetriever:
    """
    Handles flight booking data retrieval with comprehensive details
    """
    
    @staticmethod
    def get_booking_details(booking_id: int, user=None) -> Dict:
        """Get comprehensive flight booking details"""
        
        try:
            # Base query with necessary joins
            booking = Booking.objects.select_related(
                'flight_booking',
                'user',
                'meta_info'
            ).prefetch_related(
                'flight_booking__flight_passengers',
                'flight_booking__flight_ancillary_services',
                'booking_payment'
            ).filter(
                id=booking_id,
                booking_type='FLIGHT'
            ).first()
            
            if not booking:
                return {
                    'success': False,
                    'error': 'Flight booking not found',
                    'error_code': 'BOOKING_NOT_FOUND'
                }
            
            # Check user access (if user is provided)
            if user and booking.user != user and not user.is_staff:
                return {
                    'success': False,
                    'error': 'Access denied',
                    'error_code': 'ACCESS_DENIED'
                }
            
            # Get status tracker for real-time status
            status_tracker = FlightBookingStatusTracker(booking=booking)
            current_status = status_tracker.get_current_status()
            
            # Build comprehensive response
            booking_details = {
                'success': True,
                'booking': {
                    'id': booking.id,
                    'confirmation_code': booking.confirmation_code or '',
                    'reference_code': booking.reference_code or '',
                    'status': booking.status,
                    'booking_type': booking.booking_type,
                    'created': booking.created.isoformat(),
                    'updated': booking.updated.isoformat()
                },
                'flight_details': FlightBookingRetriever._get_flight_details(booking.flight_booking),
                'passenger_details': FlightBookingRetriever._get_passenger_details(booking.flight_booking),
                'pricing_details': FlightBookingRetriever._get_pricing_details(booking),
                'payment_details': FlightBookingRetriever._get_payment_details(booking),
                'ancillary_services': FlightBookingRetriever._get_ancillary_services(booking.flight_booking),
                'status_info': current_status,
                'timeline': status_tracker.get_booking_timeline(),
                'user_details': FlightBookingRetriever._get_user_details(booking.user) if booking.user else None
            }
            
            # Add invoice details if available
            if booking.invoice_id:
                booking_details['invoice_details'] = FlightBookingRetriever._get_invoice_details(booking)
            
            return booking_details
            
        except Exception as e:
            logger.error(f"Error retrieving booking details: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'error_code': 'RETRIEVAL_ERROR'
            }
    
    @staticmethod
    def get_user_flight_bookings(user, filters: Dict = None) -> Dict:
        """Get user's flight bookings with filters"""
        
        try:
            # Base query
            queryset = Booking.objects.select_related(
                'flight_booking',
                'user'
            ).filter(
                user=user,
                booking_type='FLIGHT'
            ).order_by('-created')
            
            # Apply filters
            if filters:
                # Status filter
                if 'status' in filters:
                    queryset = queryset.filter(status=filters['status'])
                
                # Date range filter
                if 'date_from' in filters:
                    queryset = queryset.filter(created__gte=filters['date_from'])
                if 'date_to' in filters:
                    queryset = queryset.filter(created__lte=filters['date_to'])
                
                # Route filter
                if 'origin' in filters:
                    queryset = queryset.filter(flight_booking__flying_from__icontains=filters['origin'])
                if 'destination' in filters:
                    queryset = queryset.filter(flight_booking__flying_to__icontains=filters['destination'])
            
            # Get bookings
            bookings = []
            for booking in queryset[:50]:  # Limit to 50 bookings
                bookings.append({
                    'id': booking.id,
                    'confirmation_code': booking.confirmation_code or '',
                    'status': booking.status,
                    'flight_route': f"{booking.flight_booking.flying_from} → {booking.flight_booking.flying_to}",
                    'departure_date': booking.flight_booking.departure_date.isoformat() if booking.flight_booking.departure_date else None,
                    'amount': float(booking.final_amount),
                    'created': booking.created.isoformat(),
                    'flight_class': booking.flight_booking.flight_class
                })
            
            return {
                'success': True,
                'count': len(bookings),
                'bookings': bookings
            }
            
        except Exception as e:
            logger.error(f"Error retrieving user bookings: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'error_code': 'USER_BOOKINGS_ERROR'
            }
    
    @staticmethod
    def _get_flight_details(flight_booking: FlightBooking) -> Dict:
        """Get detailed flight information"""
        
        return {
            'flight_no': flight_booking.flight_no or 'TBD',
            'airline_code': flight_booking.airline_code or '',
            'flying_from': flight_booking.flying_from,
            'flying_to': flight_booking.flying_to,
            'flight_class': flight_booking.flight_class,
            'flight_trip': flight_booking.flight_trip,
            'departure_date': flight_booking.departure_date.isoformat() if flight_booking.departure_date else None,
            'arrival_date': flight_booking.arrival_date.isoformat() if flight_booking.arrival_date else None,
            'return_date': flight_booking.return_date.isoformat() if flight_booking.return_date else None,
            'return_arrival_date': flight_booking.return_arrival_date.isoformat() if flight_booking.return_arrival_date else None,
            'airiq_pnr': flight_booking.airiq_pnr or '',
            'airline_pnr': flight_booking.airline_pnr or '',
            'status': flight_booking.status,
            'booking_mode': flight_booking.booking_mode,
            'flight_ticket_url': flight_booking.flight_ticket.url if flight_booking.flight_ticket else None
        }
    
    @staticmethod
    def _get_passenger_details(flight_booking: FlightBooking) -> List[Dict]:
        """Get passenger details"""
        
        passengers = []
        for passenger in flight_booking.flight_passengers.all():
            passengers.append({
                'passenger_reference': passenger.passenger_reference,
                'passenger_type': passenger.passenger_type,
                'title': passenger.title,
                'first_name': passenger.first_name,
                'last_name': passenger.last_name,
                'full_name': f"{passenger.first_name} {passenger.last_name}",
                'date_of_birth': passenger.date_of_birth.isoformat() if passenger.date_of_birth else None,
                'gender': passenger.gender,
                'passport_number': passenger.passport_number or '',
                'passport_expiry': passenger.passport_expiry.isoformat() if passenger.passport_expiry else None
            })
        
        return passengers
    
    @staticmethod
    def _get_pricing_details(booking: Booking) -> Dict:
        """Get pricing breakdown"""
        
        return {
            'subtotal': float(booking.subtotal),
            'gst_amount': float(booking.gst_amount),
            'gst_percentage': float(booking.gst_percentage) if booking.gst_percentage else 0,
            'gst_type': booking.gst_type or '',
            'service_tax': float(booking.service_tax) if booking.service_tax else 0,
            'discount': float(booking.discount) if booking.discount else 0,
            'pro_member_discount': float(booking.pro_member_discount_value) if booking.pro_member_discount_value else 0,
            'final_amount': float(booking.final_amount),
            'total_payment_made': float(booking.total_payment_made),
            'balance_due': float(booking.final_amount - booking.total_payment_made)
        }
    
    @staticmethod
    def _get_payment_details(booking: Booking) -> List[Dict]:
        """Get payment history"""
        
        payments = []
        for payment in booking.booking_payment.all().order_by('-created'):
            payments.append({
                'transaction_id': payment.transaction_id or '',
                'merchant_transaction_id': payment.merchant_transaction_id,
                'amount': float(payment.amount) if payment.amount else 0,
                'payment_type': payment.payment_type or '',
                'payment_medium': payment.payment_medium or '',
                'status': 'success' if payment.is_transaction_success else 'failed',
                'code': payment.code or '',
                'message': payment.message or '',
                'created': payment.created.isoformat(),
                'transaction_for': payment.transaction_for or ''
            })
        
        return payments
    
    @staticmethod
    def _get_ancillary_services(flight_booking: FlightBooking) -> List[Dict]:
        """Get ancillary services"""
        
        services = []
        for service in flight_booking.flight_ancillary_services.all():
            services.append({
                'service_type': service.service_type,
                'service_description': service.service_description or '',
                'service_price': float(service.service_price) if service.service_price else 0,
                'passenger_name': f"{service.passenger.first_name} {service.passenger.last_name}" if service.passenger else '',
                'airiq_service_id': service.airiq_service_id or ''
            })
        
        return services
    
    @staticmethod
    def _get_user_details(user) -> Dict:
        """Get user information"""
        
        return {
            'id': user.id,
            'name': user.name or '',
            'email': user.email or '',
            'mobile_number': user.mobile_number or '',
            'is_guest': getattr(user, 'is_guest', False)
        }
    
    @staticmethod
    def _get_invoice_details(booking: Booking) -> Dict:
        """Get invoice information"""
        
        try:
            from ..models import Invoice
            invoice = Invoice.objects.filter(invoice_number=booking.invoice_id).first()
            
            if invoice:
                return {
                    'invoice_number': invoice.invoice_number,
                    'invoice_date': invoice.invoice_date.isoformat() if invoice.invoice_date else None,
                    'due_date': invoice.due_date.isoformat() if invoice.due_date else None,
                    'status': invoice.status or '',
                    'total_amount': float(invoice.total_amount) if invoice.total_amount else 0,
                    'invoice_pdf_url': invoice.invoice_pdf.url if invoice.invoice_pdf else None
                }
        except Exception as e:
            logger.error(f"Error getting invoice details: {str(e)}")
        
        return {}