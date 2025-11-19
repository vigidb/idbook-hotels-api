"""
Flight booking payment utilities
Integrates flight bookings with existing payment gateways (PhonePe, PayU) and wallet system
"""

from decimal import Decimal
from datetime import datetime, timedelta
from typing import Dict, Tuple, Optional
from django.utils import timezone
from django.conf import settings
from django.db import transaction
import logging

from ..models import (
    Booking, FlightBooking, BookingPaymentDetail, Invoice
)
from apps.customer.models import Wallet, WalletTransaction
from apps.payment_gateways.mixins.phonepay_mixins import PhonePayMixin
from apps.payment_gateways.mixins.payu_mixins import PayUMixin
from apps.booking.utils.db_utils import (
    create_booking_payment_details, update_booking_payment_details,
    check_booking_and_transaction, get_booking_from_payment
)
from apps.booking.utils.booking_utils import (
    check_wallet_balance_for_booking, deduct_booking_amount, 
    generate_booking_confirmation_code, refund_wallet_payment
)
from apps.booking.tasks import (
    send_flight_booking_task, create_invoice_task, send_booking_sms_task
)
from apps.log_management.utils.db_utils import create_booking_payment_log
from IDBOOKAPI.utils import get_unique_id_from_time

logger = logging.getLogger(__name__)


class FlightPaymentProcessor:
    """
    Handles payment processing for flight bookings
    Integrates with existing payment gateways and wallet system
    """
    
    def __init__(self, booking: Booking, user, payment_data: dict):
        self.booking = booking
        self.user = user
        self.payment_data = payment_data
        self.flight_booking = booking.flight_booking
        self.last_error_message: Optional[str] = None
        
    def validate_payment_data(self) -> Tuple[bool, list]:
        """Validate payment request data"""
        errors = []
        
        # Check required fields
        required_fields = ['amount', 'payment_channel']
        for field in required_fields:
            if field not in self.payment_data:
                errors.append(f"Field '{field}' is required")
        
        # Validate amount matches booking total
        if 'amount' in self.payment_data:
            try:
                request_amount = Decimal(str(self.payment_data['amount']))
                if request_amount != self.booking.final_amount:
                    errors.append(f"Amount mismatch. Expected: {self.booking.final_amount}, Got: {request_amount}")
            except (ValueError, TypeError):
                errors.append("Invalid amount format")
        
        # Check if booking is eligible for payment
        if self.booking.status == 'confirmed':
            errors.append("Booking is already confirmed")
        
        if self.booking.status == 'canceled':
            errors.append("Cannot process payment for cancelled booking")
            
        # Flight-specific validations
        if not self.flight_booking:
            errors.append("Flight booking details not found")
        elif self.flight_booking.status == 'CANCELLED':
            errors.append("Cannot process payment for cancelled flight")
            
        return len(errors) == 0, errors
    
    def initiate_payment(self) -> Dict:
        """Initiate payment based on selected payment channel"""
        
        # Validate payment data
        is_valid, errors = self.validate_payment_data()
        if not is_valid:
            return {
                'success': False,
                'errors': errors,
                'error_code': 'VALIDATION_ERROR'
            }
        
        payment_channel = self.payment_data['payment_channel'].upper()
        amount = Decimal(str(self.payment_data['amount']))
        
        # Create payment detail record
        try:
            payment_detail = self._create_payment_detail_record(amount)
        except Exception as e:
            logger.error(f"Error creating payment detail: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'error_code': 'PAYMENT_RECORD_ERROR'
            }
        
        # Route to appropriate payment method
        if payment_channel == 'WALLET':
            return self._process_wallet_payment(amount, payment_detail)
        elif payment_channel == 'PHONE PAY':
            return self._process_phonepe_payment(amount, payment_detail)
        elif payment_channel == 'PAYU':
            return self._process_payu_payment(amount, payment_detail)
        else:
            return {
                'success': False,
                'error': f'Unsupported payment channel: {payment_channel}',
                'error_code': 'UNSUPPORTED_PAYMENT_CHANNEL'
            }
    
    def _create_payment_detail_record(self, amount: Decimal) -> BookingPaymentDetail:
        """Create payment detail record for the booking"""
        
        # Generate unique merchant transaction ID
        append_id = f"FL{self.user.id}" if self.user else "FLGUEST"
        payment_detail = create_booking_payment_details(self.booking.id, append_id)
        
        # Update with flight-specific details
        payment_detail.amount = float(amount)
        payment_detail.transaction_for = "flight_booking_payment"
        payment_detail.save()
        
        return payment_detail
    
    def _process_wallet_payment(self, amount: Decimal, payment_detail: BookingPaymentDetail) -> Dict:
        """Process payment via wallet"""
        
        try:
            print("Processing wallet payment")
            # Check wallet balance
            company_id = self.user.company_id if hasattr(self.user, 'company_id') else None
            print("company_id:", company_id)
            can_pay, balance_info = check_wallet_balance_for_booking(
                self.booking, self.user, company_id=company_id
            )
            print("Can pay:", can_pay, "Balance info:", balance_info)
            
            if not can_pay:
                return {
                    'success': False,
                    'error': 'Insufficient wallet balance',
                    'error_code': 'INSUFFICIENT_WALLET_BALANCE',
                    'balance_info': float(balance_info) if balance_info is not None else 0.0
                }
            
            # Deduct amount from wallet
            deduct_success = deduct_booking_amount(
                self.booking, company_id=company_id
            )
            
            if not deduct_success:
                return {
                    'success': False,
                    'error': 'Wallet deduction failed',
                    'error_code': 'WALLET_DEDUCTION_FAILED'
                }
            
            # Update payment details as paid (wallet deducted)
            update_booking_payment_details(payment_detail.merchant_transaction_id, {
                'code': 'PAYMENT_SUCCESS',
                'message': 'Payment successful via wallet',
                'payment_type': 'WALLET',
                'payment_medium': 'Idbook',
                'is_transaction_success': True,
                'transaction_id': payment_detail.merchant_transaction_id
            })
            
            # Confirm booking (calls AirIQ Book); if it fails, refund wallet and revert states
            confirmed = self._confirm_flight_booking()
            if not confirmed:
                # Refund wallet since supplier booking failed
                refund_details = {
                    'reason': 'AirIQ booking failed after wallet deduction',
                    'timestamp': timezone.now().isoformat(),
                    'airiq_error': self.last_error_message
                }
                refund_ok, refund_status, refund_data = refund_wallet_payment(self.booking, Decimal(self.booking.final_amount), refund_details)
                # Revert booking/flight statuses back to pending
                self.booking.status = 'pending'
                self.booking.total_payment_made = Decimal('0.0')
                self.booking.save(update_fields=['status', 'total_payment_made'])
                self.flight_booking.status = 'PENDING_PAYMENT'
                self.flight_booking.save(update_fields=['status'])
                # Update payment record to reflect refund
                update_booking_payment_details(payment_detail.merchant_transaction_id, {
                    'code': 'BOOKING_FAILED_REFUNDED',
                    'message': 'Supplier booking failed; wallet refunded',
                    'transaction_details': {
                        'refund_status': refund_status,
                        'refund_data': refund_data,
                        'airiq_error': self.last_error_message
                    }
                })
                return {
                    'success': False,
                    'error': self.last_error_message or 'Supplier booking failed; wallet refunded',
                    'error_code': 'AIRIQ_BOOKING_FAILED',
                    'refund_status': refund_status
                }
            
            # Send notifications only on confirmed
            self._send_booking_notifications()
            
            return {
                'success': True,
                'payment_method': 'wallet',
                'transaction_id': payment_detail.merchant_transaction_id,
                'message': 'Payment successful via wallet'
            }
            
        except Exception as e:
            print("Error processing wallet payment:", str(e))
            logger.error(f"Wallet payment error: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'error_code': 'WALLET_PAYMENT_ERROR'
            }
    
    def _process_phonepe_payment(self, amount: Decimal, payment_detail: BookingPaymentDetail) -> Dict:
        """Process payment via PhonePe"""
        
        try:
            phonepe_mixin = PhonePayMixin()
            
            # Prepare PhonePe payload
            merchant_id = settings.MERCHANT_ID
            redirect_url = self.payment_data.get('redirect_url', settings.DEFAULT_REDIRECT_URL)
            callback_url = f"{settings.CALLBACK_URL}/api/v1/booking/flight-payment/phonepe-callback/"
            
            payload = {
                "merchantId": merchant_id,
                "merchantTransactionId": payment_detail.merchant_transaction_id,
                "merchantUserId": str(self.user.id) if self.user else "guest",
                "amount": int(amount * 100),  # PhonePe expects amount in paise
                "redirectUrl": redirect_url,
                "redirectMode": "REDIRECT",
                "callbackUrl": callback_url,
                "paymentInstrument": {"type": "PAY_PAGE"}
            }
            
            # Log payment request
            payment_log = {
                'booking_id': self.booking.id,
                'merchant_transaction_id': payment_detail.merchant_transaction_id,
                'request': payload
            }
            
            # Get encrypted headers and make request
            req, auth_header = phonepe_mixin.get_encrypted_header_and_payload(payload)
            response = phonepe_mixin.post_pay_page(req, auth_header)
            
            if response.status_code == 200:
                data_json = response.json()
                payment_log['response'] = data_json
                
                # Update payment detail
                update_booking_payment_details(payment_detail.merchant_transaction_id, {
                    'payment_type': 'PAYMENT GATEWAY',
                    'payment_medium': 'PHONE PAY',
                    'code': 'PAYMENT_INITIATED',
                    'message': 'Payment initiated via PhonePe'
                })
                
                # Create payment log
                create_booking_payment_log(payment_log)
                
                # Extract payment URL
                instrument_response = data_json.get('data', {}).get('instrumentResponse', {})
                payment_url = instrument_response.get('redirectInfo', {}).get('url', '')
                
                return {
                    'success': True,
                    'payment_method': 'phonepe',
                    'payment_url': payment_url,
                    'transaction_id': payment_detail.merchant_transaction_id,
                    'message': 'PhonePe payment initiated successfully'
                }
            else:
                payment_log['response'] = {'error': response.text}
                create_booking_payment_log(payment_log)
                
                return {
                    'success': False,
                    'error': response.text,
                    'error_code': 'PHONEPE_INITIATION_FAILED'
                }
                
        except Exception as e:
            logger.error(f"PhonePe payment error: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'error_code': 'PHONEPE_PAYMENT_ERROR'
            }
    
    def _process_payu_payment(self, amount: Decimal, payment_detail: BookingPaymentDetail) -> Dict:
        """Process payment via PayU"""
        
        try:
            payu_mixin = PayUMixin()
            
            # Prepare PayU payload
            payload = {
                'key': settings.PAYU_KEY,
                'txnid': payment_detail.merchant_transaction_id,
                'amount': str(amount),
                'productinfo': f'Flight Booking - {self.flight_booking.flying_from} to {self.flight_booking.flying_to}',
                'firstname': self.user.first_name if self.user else 'Guest',
                'email': self.user.email if self.user else self.payment_data.get('email', ''),
                'phone': self.user.mobile_number if self.user else self.payment_data.get('phone', ''),
                'surl': f"{settings.CALLBACK_URL}/api/v1/booking/flight-payment/payu-success/",
                'furl': f"{settings.CALLBACK_URL}/api/v1/booking/flight-payment/payu-failure/",
            }
            
            # Generate hash
            hash_string = f"{payload['key']}|{payload['txnid']}|{payload['amount']}|{payload['productinfo']}|{payload['firstname']}|{payload['email']}|||||||||||{settings.PAYU_SALT}"
            payload['hash'] = payu_mixin.generate_hash(hash_string)
            
            # Update payment detail
            update_booking_payment_details(payment_detail.merchant_transaction_id, {
                'payment_type': 'PAYMENT GATEWAY',
                'payment_medium': 'PAYU',
                'code': 'PAYMENT_INITIATED',
                'message': 'Payment initiated via PayU'
            })
            
            return {
                'success': True,
                'payment_method': 'payu',
                'payment_url': settings.PAYU_URL,
                'payload': payload,
                'transaction_id': payment_detail.merchant_transaction_id,
                'message': 'PayU payment initiated successfully'
            }
            
        except Exception as e:
            logger.error(f"PayU payment error: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'error_code': 'PAYU_PAYMENT_ERROR'
            }
    
    def _confirm_flight_booking(self) -> bool:
        """Confirm the flight booking after successful payment: call AirIQ Book, update, then auto-issue ticket.
        Returns True if supplier booking succeeded (PNRs obtained), False otherwise.
        """
        
        # 1) Call AirIQ Booking API using stored request data
        self.last_error_message = None
        airiq_success = False
        try:
            from apps.flights.services.airiq_service import airiq_service, AirIQException
            req = self.flight_booking.airiq_request_data or {}
            if not req:
                logger.warning(f"No AirIQ request data found for booking {self.booking.id}; skipping AirIQ booking call")
            else:
                booking_data, track_id, block_pnr = self._build_airiq_booking_payload_from_stored_request(req)
                airiq_resp = airiq_service.create_booking(
                    booking_data=booking_data,
                    track_id=track_id,
                    block_pnr=block_pnr
                )
                # Persist the exact booking payload and AirIQ response for audit/debug
                try:
                    fb = self.flight_booking
                    # Append last used booking payload inside airiq_request_data for traceability
                    req_blob = fb.airiq_request_data or {}
                    req_blob['airiq_booking_payload'] = {
                        'booking_data': booking_data,
                        'track_id': track_id,
                        'block_pnr': block_pnr,
                    }
                    fb.airiq_request_data = req_blob
                    fb.airiq_response_data = airiq_resp
                    fb.save(update_fields=['airiq_request_data', 'airiq_response_data'])
                except Exception:
                    pass
                # Always attempt to store identifiers (TrackId etc.)
                self._update_flight_booking_from_airiq_response(airiq_resp)
                
                # Determine success from AirIQ response
                status_info = (airiq_resp or {}).get('Status') or {}
                result_code = str(status_info.get('ResultCode') or '').strip()
                error_msg = status_info.get('Error') or ''
                if error_msg:
                    self.last_error_message = error_msg
                
                # Success if code indicates success AND we have PNR
                has_pnr = bool(self.flight_booking.airiq_pnr or self.flight_booking.airline_pnr)
                code_success = result_code in ('1', '01', 1)
                airiq_success = bool(code_success and has_pnr)
                if not airiq_success and not self.last_error_message:
                    self.last_error_message = 'AirIQ booking failed'
        except AirIQException as e:
            self.last_error_message = str(e)
            logger.error(f"AirIQ booking failed for booking {self.booking.id}: {e}")
        except Exception as e:
            self.last_error_message = str(e)
            logger.error(f"Unexpected error during AirIQ booking for {self.booking.id}: {e}")
        
        # 2) Generate confirmation code and mark booking confirmed
        booking_id = self.booking.id
        booking_type = self.booking.booking_type
        
        while True:
            confirmation_code = generate_booking_confirmation_code(booking_id, booking_type)
            # Check if confirmation code already exists
            from apps.booking.utils.db_utils import check_booking_confirmation_code
            if not check_booking_confirmation_code(confirmation_code):
                break
        
        if airiq_success:
            # Update booking only on AirIQ success
            self.booking.confirmation_code = confirmation_code
            self.booking.status = 'confirmed'
            self.booking.total_payment_made = self.booking.final_amount
            self.booking.save()
            
            # Update booking meta info
            if hasattr(self.booking, 'meta_info'):
                self.booking.meta_info.booking_confirmed_date = timezone.now()
                self.booking.meta_info.save()
            
            # Update flight booking status
            self.flight_booking.status = 'CONFIRMED'
            self.flight_booking.confirmed_at = timezone.now()
            self.flight_booking.save()
            
            logger.info(f"Flight booking {self.booking.id} confirmed with code {confirmation_code}")
            
            # Skip auto-issuing tickets; can be issued later via API if required
            # if (self.flight_booking.airiq_track_id and self.flight_booking.airiq_pnr and self.flight_booking.airline_pnr):
            #     self._auto_issue_ticket()
            return True
        else:
            logger.error(f"AirIQ booking failed; not confirming booking {self.booking.id}")
            return False

    def _build_airiq_booking_payload_from_stored_request(self, req: dict):
        """Map stored airiq_request_data to AirIQService.create_booking booking_data payload.
        Supports multiple ItineraryFlightsInfo (domestic RT) and single-item international RT.
        """
        # Adults/children/infants
        adults = int(req.get('AdultCount', 1) or 0)
        children = int(req.get('ChildCount', 0) or 0)
        infants = int(req.get('InfantCount', 0) or 0)
        
        itin_list = req.get('ItineraryFlightsInfo') or []
        itineraries = []
        total_amount_sum = 0.0
        for item in itin_list:
            token = item.get('Token', '')
            flights = item.get('FlighstInfo') or item.get('FlightsInfo') or []
            seats_list = []
            meals_list = []
            bagg_list = []
            other_list = item.get('OtherSSRInfo', []) or []
            for s in item.get('SeatsSSRInfo', []) or []:
                seats_list.append({
                    'seat_id': s.get('SeatID'),
                    'passenger_ref': int(s.get('PaxRefNumber') or 0) if s.get('PaxRefNumber') else None
                })
            for b in item.get('BaggSSRInfo', []) or []:
                bagg_list.append({
                    'baggage_id': b.get('BaggageID'),
                    'passenger_ref': int(b.get('PaxRefNumber') or 0) if s.get('PaxRefNumber') else None
                })
            for m in item.get('MealsSSRInfo', []) or []:
                meals_list.append({
                    'meal_id': m.get('MealID'),
                    'passenger_ref': int(m.get('PaxRefNumber') or 0) if m.get('PaxRefNumber') else None
                })
            pay = (item.get('PaymentInfo') or [{}])[0]
            item_total = pay.get('TotalAmount')
            try:
                total_amount_sum += float(item_total or 0)
            except Exception:
                pass
            itineraries.append({
                'token': token,
                'flight_segments': flights,
                'seats': seats_list,
                'meals': meals_list,
                'baggage': bagg_list,
                'other_services': other_list,
                'payment_total': item_total
            })
        # If no itinerary items, fallback to empty structure
        if not itineraries:
            itineraries = [{
                'token': '', 'flight_segments': [], 'seats': [], 'meals': [], 'baggage': [], 'other_services': [], 'payment_total': None
            }]
        
        # Passengers: map AirIQ style to service input
        pax_src = req.get('PaxDetailsInfo') or []
        passengers = []
        for p in pax_src:
            passengers.append({
                'title': p.get('Title', ''),
                'first_name': p.get('FirstName', ''),
                'last_name': p.get('LastName', ''),
                'date_of_birth': p.get('DOB', ''),
                'gender': p.get('Gender', ''),
                'pax_type': p.get('PaxType', ''),
                'passport_number': p.get('PassportNo', ''),
                'passport_expiry': p.get('PassportExpiry', ''),
                'passport_issued_date': p.get('PassportIssuedDate', ''),
                'passport_country_code': p.get('PassportCountryCode', ''),
                'infant_ref': p.get('InfantRef', '')
            })
        
        # Contact/GST
        addr = req.get('AddressDetails') or {}
        contact = {
            'country_code': addr.get('CountryCode', '91'),
            'phone': addr.get('ContactNumber', ''),
            'email': addr.get('EmailID', '')
        }
        gst_src = req.get('GSTInfo') or {}
        gst = {
            'number': gst_src.get('GSTNumber', ''),
            'company_name': gst_src.get('GSTCompanyName', ''),
            'address': gst_src.get('GSTAddress', ''),
            'email': gst_src.get('GSTEmailID', ''),
            'mobile': gst_src.get('GSTMobileNumber', '')
        }
        
        booking_data = {
            'itineraries': itineraries,
            'passengers': passengers,
            'contact': contact,
            'gst': gst,
            'adults': adults,
            'children': children,
            'infants': infants,
            'origin': req.get('BaseOrigin'),
            'destination': req.get('BaseDestination'),
            'trip_type': req.get('TripType', 'O'),
            'total_amount': total_amount_sum or None
        }
        track_id = req.get('TrackId') or req.get('TrackID') or ''
        block_pnr = bool(req.get('BlockPNR', False))
        return booking_data, track_id, block_pnr

    def _update_flight_booking_from_airiq_response(self, airiq_resp: dict) -> None:
        """Persist PNRs/Track IDs (supporting multiple itineraries), tickets and SSRs per segment.
        Handles both domestic RT (two itinerary items) and international RT (single itinerary with both legs).
        """
        try:
            from decimal import Decimal as _D
            booking_resp = airiq_resp.get('Bookingresponse') or {}
            itineraries = booking_resp.get('ItinearyDetails') or []

            airiq_pnrs_set, airline_pnrs_set, track_ids_set = set(), set(), set()
            all_ticket_numbers = []
            booked_itins = []

            # Helper: normalize NA values
            def _norm(val: str) -> str:
                try:
                    s = (val or '').strip()
                    return '' if s.upper() in ('N/A', 'NA', 'NULL') else s
                except Exception:
                    return ''

            # Quick passenger cache for matching
            pax_qs = list(self.flight_booking.passengers.all())
            def match_passenger(t: dict):
                title = (t.get('Title') or '').upper()
                first = (t.get('FirstName') or '').strip().upper()
                last = (t.get('LastName') or '').strip().upper()
                dob_str = t.get('DateOfBirth') or ''
                dob_norm = None
                if dob_str:
                    from datetime import datetime as _dt
                    for fmt in ('%d/%m/%Y','%Y-%m-%d','%d-%m-%Y'):
                        try:
                            dob_norm = _dt.strptime(dob_str, fmt).date()
                            break
                        except Exception:
                            continue
                for p in pax_qs:
                    if p.title.upper() == title and p.first_name.strip().upper() == first and p.last_name.strip().upper() == last:
                        if not dob_norm or (p.date_of_birth == dob_norm):
                            return p
                return None

            # Iterate all itinerary containers
            for itin_container in itineraries:
                items = itin_container.get('Item') or []
                for item in items:
                    # PNRs and Track ID at itinerary level
                    ai_pnr = _norm(item.get('AirIqPNR') or item.get('AiriqPNR'))
                    trk = _norm( airiq_resp.get('TrackId') or item.get('BookingTrackId') )
                    # Determine airline PNR with nested preference
                    nested_airline_pnr = ''
                    trav = item.get('TravellerInfo', {})
                    trav_items = trav.get('Item') or []
                    if trav_items:
                        seg0 = (trav_items[0].get('SegmentInformation') or {}).get('Item') or []
                        if seg0:
                            nested_airline_pnr = seg0[0].get('AirlinePNR') or ''
                    airline_pnr = _norm(nested_airline_pnr) or _norm(item.get('AirlinePNR')) or _norm(item.get('CRSPNR'))

                    if ai_pnr:
                        airiq_pnrs_set.add(ai_pnr)
                    if airline_pnr:
                        airline_pnrs_set.add(airline_pnr)
                    if trk:
                        track_ids_set.add(trk)

                    # Base route updates (optional)
                    base_origin = item.get('BaseOrigin') or ''
                    base_dest = item.get('BaseDestination') or ''
                    if base_origin:
                        self.flight_booking.flying_from = base_origin
                    if base_dest:
                        self.flight_booking.flying_to = base_dest

                    # Build booked_itinerary entry
                    pay_items = ((item.get('PaymentDetails') or {}).get('Item') or [])
                    total_amount = _D('0')
                    for pi in pay_items:
                        try:
                            total_amount += _D(str(pi.get('Amount') or '0'))
                        except Exception:
                            pass

                    # Derive segment summaries from first passenger's segments to avoid duplication
                    segment_summaries = []
                    seen_seg_keys = set()
                    if trav_items:
                        any_seg_items = (trav_items[0].get('SegmentInformation') or {}).get('Item') or []
                        for idx, s in enumerate(any_seg_items, start=1):
                            key = (
                                (s.get('Origin') or ''),
                                (s.get('Destination') or ''),
                                (s.get('CarrierCode') or ''),
                                (s.get('FlightNumber') or ''),
                                (s.get('DepartureDateTime') or ''),
                            )
                            if key in seen_seg_keys:
                                continue
                            seen_seg_keys.add(key)
                            segment_summaries.append({
                                'seg_ref': s.get('SegRef') or s.get('SegmentRef') or idx,
                                'origin': s.get('Origin') or '',
                                'destination': s.get('Destination') or '',
                                'carrier': s.get('CarrierCode') or '',
                                'flight_number': s.get('FlightNumber') or '',
                                'dep_time': s.get('DepartureDateTime') or '',
                                'arr_time': s.get('ArrivalDateTime') or '',
                                'class_code': s.get('ClassCode') or '',
                            })

                    booked_itins.append({
                        'airiq_pnr': ai_pnr,
                        'airline_pnr': airline_pnr,
                        'track_id': trk,
                        'base_origin': base_origin,
                        'base_destination': base_dest,
                        'amount': str(total_amount),
                        'segments': segment_summaries,
                    })

                    # Persist per-passenger tickets and SSRs for all segments
                    from apps.booking.models import FlightAncillaryService as _FAS
                    for t in trav_items:
                        passenger = match_passenger(t)
                        if not passenger:
                            continue
                        tn = t.get('TicketNumber') or t.get('TicketNo')
                        if tn:
                            all_ticket_numbers.append(tn)
                            if not passenger.ticket_number:
                                passenger.ticket_number = tn
                        seginfo = t.get('SegmentInformation') or {}
                        seg_items = seginfo.get('Item') or []
                        for sidx, s in enumerate(seg_items, start=1):
                            seg_ref = s.get('SegRef') or s.get('SegmentRef') or sidx
                            # Update flight/airline meta only from first seen segment
                            if not self.flight_booking.flight_no and (s.get('FlightNumber') or ''):
                                self.flight_booking.flight_no = s.get('FlightNumber')
                            if not self.flight_booking.airline_code and (s.get('CarrierCode') or ''):
                                self.flight_booking.airline_code = s.get('CarrierCode')

                            seat_pref = (s.get('SeatPreference') or '').strip()
                            seat_amt = s.get('SeatAmount') or '0'
                            meal_pref = (s.get('MealsPreference') or '').strip()
                            meal_amt = s.get('MealsAmount') or '0'
                            bag_pref = (s.get('BaggagePreference') or '').strip()
                            bag_amt = s.get('BaggageAmount') or '0'

                            # Set seat number if available
                            if seat_pref and not passenger.seat_number:
                                passenger.seat_number = seat_pref
                            passenger.save(update_fields=['ticket_number','seat_number'])

                            def ensure_service(stype, code, desc, amt):
                                if not desc and not code:
                                    return
                                try:
                                    price = _D(str(amt or 0))
                                except Exception:
                                    price = _D('0')
                                exists = _FAS.objects.filter(
                                    flight_booking=self.flight_booking,
                                    passenger=passenger,
                                    service_type=stype,
                                    service_description=(desc or code)[:200],
                                    segment_reference=seg_ref,
                                ).exists()
                                if not exists:
                                    _FAS.objects.create(
                                        flight_booking=self.flight_booking,
                                        passenger=passenger,
                                        service_type=stype,
                                        airiq_service_id=str(code or ''),
                                        service_code=str(code or ''),
                                        service_description=(desc or str(code))[:200],
                                        segment_reference=seg_ref,
                                        service_price=price,
                                    )

                            if seat_pref:
                                ensure_service('SEAT', seat_pref, f"Seat {seat_pref}", seat_amt)
                            if meal_pref:
                                ensure_service('MEAL', '', meal_pref, meal_amt)
                            if bag_pref:
                                ensure_service('BAGGAGE', '', bag_pref, bag_amt)

            # Persist collected fields to model
            updates = []
            # Single-value fallbacks for backward-compat
            if airiq_pnrs_set and not self.flight_booking.airiq_pnr:
                self.flight_booking.airiq_pnr = next(iter(airiq_pnrs_set))
                updates.append('airiq_pnr')
            if airline_pnrs_set and not self.flight_booking.airline_pnr:
                self.flight_booking.airline_pnr = next(iter(airline_pnrs_set))
                updates.append('airline_pnr')
            if track_ids_set and not self.flight_booking.airiq_track_id:
                self.flight_booking.airiq_track_id = next(iter(track_ids_set))
                updates.append('airiq_track_id')

            # List fields
            if airiq_pnrs_set:
                self.flight_booking.airiq_pnrs = sorted(list(airiq_pnrs_set))
                updates.append('airiq_pnrs')
            if airline_pnrs_set:
                self.flight_booking.airline_pnrs = sorted(list(airline_pnrs_set))
                updates.append('airline_pnrs')
            if track_ids_set:
                self.flight_booking.airiq_track_ids = sorted(list(track_ids_set))
                updates.append('airiq_track_ids')
            if booked_itins:
                self.flight_booking.booked_itineraries = booked_itins
                # self.flight_booking.booked_itineraries = airiq_resp.get('Bookingresponse', {}).get('ItinearyDetails', [])
                updates.append('booked_itineraries')
            if all_ticket_numbers:
                # de-dup preserving order
                seen = set()
                uniq = []
                for tn in all_ticket_numbers:
                    if tn and tn not in seen:
                        seen.add(tn)
                        uniq.append(tn)
                self.flight_booking.ticket_numbers = uniq
                updates.append('ticket_numbers')

            for f in ('flight_no','airline_code','flying_from','flying_to'):
                if getattr(self.flight_booking, f, None) and f not in updates:
                    updates.append(f)

            if updates:
                self.flight_booking.save(update_fields=updates)
            
            
        except Exception as e:
            logger.error(f"Failed to update flight booking from AirIQ response for {self.booking.id}: {e}")
    
    def _auto_issue_ticket(self):
        """Automatically issue ticket after successful payment and confirmation"""
        
        try:
            # Check if we have required data for ticketing
            if not all([self.flight_booking.airiq_track_id, 
                       self.flight_booking.airiq_pnr, 
                       self.flight_booking.airline_pnr]):
                logger.warning(f"Cannot auto-issue ticket for booking {self.booking.id}: Missing PNR data")
                return False
            
            # Check if already ticketed
            if self.flight_booking.status == 'TICKETED':
                logger.info(f"Booking {self.booking.id} already ticketed")
                return True
            
            # Import AirIQ service
            from apps.flights.services.airiq_service import airiq_service, AirIQException
            
            # Issue ticket via AirIQ
            ticket_response = airiq_service.issue_ticket(
                booking_track_id=self.flight_booking.airiq_track_id,
                airiq_pnr=self.flight_booking.airiq_pnr,
                airline_pnr=self.flight_booking.airline_pnr,
                booking_amount=float(self.booking.final_amount)
            )
            
            # Update flight booking with ticket details
            self.flight_booking.status = 'TICKETED'
            
            # Extract ticket numbers if available
            if 'TicketNumbers' in ticket_response:
                self.flight_booking.ticket_numbers = ticket_response['TicketNumbers']
            
            self.flight_booking.save()
            
            logger.info(f"Ticket auto-issued for booking {self.booking.id}")
            return True
            
        except AirIQException as e:
            logger.error(f"AirIQ error auto-issuing ticket for booking {self.booking.id}: {str(e)}")
            # Don't fail the confirmation, just log the error
            return False
        except Exception as e:
            logger.error(f"Error auto-issuing ticket for booking {self.booking.id}: {str(e)}")
            return False
    
    def _send_booking_notifications(self):
        """
        Queue the standard notification fan-out for confirmed bookings:
        1) Invoice generation via `create_invoice_task`
        2) Email via `send_booking_email_task`
        3) SMS (which also creates Notification entries) via `send_flight_booking_task`
        """
        try:
            from apps.booking.tasks import (
                send_booking_email_task,
                send_flight_booking_task,
                create_invoice_task,
            )

            booking_id = self.booking.id
            print(f"Preparing to send booking notifications for booking {booking_id}")
            # 1. Invoice generation (same flow as hotel bookings)
            create_invoice_task.delay(booking_id, send_email=False)

            # 2. Email confirmation (handles HTML email + Notification model entry)
            send_booking_email_task.delay(booking_id, 'confirmed-booking')

            # 3. SMS confirmation (also logs Notification via message templates)
            send_flight_booking_task.delay(booking_id, 'confirmed')



            logger.info(f"Flight booking notifications queued for booking {booking_id}")

        except Exception as e:
            print(f"Error queuing flight booking notifications for booking {self.booking.id}: {str(e)}")
            logger.error(f"Error queuing booking notifications: {str(e)}")


def handle_flight_payment_success(booking_id: int, payment_details: dict) -> bool:
    """
    Standalone function to handle payment success for flight bookings
    This can be called by payment gateway callbacks
    
    Args:
        booking_id: The booking ID
        payment_details: Dictionary containing payment information
        
    Returns:
        bool: True if successful, False otherwise
    """
    
    try:
        from ..models import Booking
        
        # Get the booking
        booking = Booking.objects.select_related('flight_booking', 'user').get(
            id=booking_id, booking_type='FLIGHT'
        )
        
        if not booking.flight_booking:
            logger.error(f"Flight booking details not found for booking {booking_id}")
            return False
        
        # Create processor instance
        processor = FlightPaymentProcessor(booking, booking.user, payment_details)
        
        # Confirm booking and auto-issue ticket
        with transaction.atomic():
            processor._confirm_flight_booking()
            
            # Send notifications
            processor._send_booking_notifications()
        
        logger.info(f"Successfully processed payment success for flight booking {booking_id}")
        return True
        
    except Exception as e:
        logger.error(f"Error handling payment success for booking {booking_id}: {str(e)}")
        return False


class FlightPaymentCallbackProcessor:
    """
    Handles payment gateway callbacks for flight bookings
    """
    
    @staticmethod
    def process_phonepe_callback(callback_data: dict) -> Dict:
        """Process PhonePe payment callback"""
        
        try:
            # Decode and parse callback data (similar to existing hotel booking callback)
            import base64
            import json
            
            response = callback_data.get('response')
            if not response:
                return {
                    'success': False,
                    'error': 'Invalid callback data',
                    'error_code': 'INVALID_CALLBACK'
                }
            
            # Decode base64 response
            data = base64.b64decode(response)
            decoded_data = data.decode('utf-8')
            json_data = json.loads(decoded_data)
            
            # Extract transaction details
            code = json_data.get('code', '')
            message = json_data.get('message', '')
            sub_json_data = json_data.get('data', {})
            
            amount = sub_json_data.get('amount', 0) / 100
            merchant_transaction_id = sub_json_data.get('merchantTransactionId', '')
            transaction_id = sub_json_data.get('transactionId', '')
            state = sub_json_data.get('state', '')
            
            # Get booking from payment details
            booking_id = get_booking_from_payment(merchant_transaction_id)
            booking = Booking.objects.get(id=booking_id)
            
            # Update payment details
            booking_payment_details = {
                'transaction_id': transaction_id,
                'code': code,
                'message': message,
                'amount': amount,
                'transaction_details': sub_json_data,
                'is_transaction_success': code == "PAYMENT_SUCCESS" and state == "COMPLETED"
            }
            
            update_booking_payment_details(merchant_transaction_id, booking_payment_details)
            
            # If payment successful, confirm booking
            if booking_payment_details['is_transaction_success']:
                processor = FlightPaymentProcessor(booking, booking.user, {})
                processor._confirm_flight_booking()
                processor._send_booking_notifications()
                
                # Send payment success SMS
                send_booking_sms_task.delay(
                    notification_type='PAYMENT_PROCEED_INFO',
                    params={
                        'booking_id': booking.id,
                        'amount': amount,
                        'payment_purpose': 'Flight Booking',
                        'transaction_id': transaction_id
                    }
                )
            else:
                # Send payment failure SMS
                send_booking_sms_task.delay(
                    notification_type='PAYMENT_FAILED_INFO',
                    params={
                        'booking_id': booking.id,
                        'failed_amount': amount,
                        'payment_purpose': 'Flight Booking'
                    }
                )
            
            return {
                'success': True,
                'payment_success': booking_payment_details['is_transaction_success'],
                'booking_id': booking.id,
                'transaction_id': transaction_id,
                'amount': amount
            }
            
        except Exception as e:
            logger.error(f"PhonePe callback processing error: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'error_code': 'CALLBACK_PROCESSING_ERROR'
            }
    
    @staticmethod
    def process_payu_callback(callback_data: dict, is_success: bool) -> Dict:
        """Process PayU payment callback"""
        
        try:
            # Extract PayU callback data
            txnid = callback_data.get('txnid', '')
            amount = float(callback_data.get('amount', 0))
            status_msg = callback_data.get('status', '')
            
            # Get booking from payment details
            booking_id = get_booking_from_payment(txnid)
            booking = Booking.objects.get(id=booking_id)
            
            # Update payment details
            booking_payment_details = {
                'transaction_id': callback_data.get('mihpayid', ''),
                'code': status_msg,
                'message': callback_data.get('error_Message', ''),
                'amount': amount,
                'transaction_details': callback_data,
                'is_transaction_success': is_success
            }
            
            update_booking_payment_details(txnid, booking_payment_details)
            
            # Process based on success/failure
            if is_success:
                processor = FlightPaymentProcessor(booking, booking.user, {})
                processor._confirm_flight_booking()
                processor._send_booking_notifications()
            
            return {
                'success': True,
                'payment_success': is_success,
                'booking_id': booking.id,
                'transaction_id': callback_data.get('mihpayid', ''),
                'amount': amount
            }
            
        except Exception as e:
            logger.error(f"PayU callback processing error: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'error_code': 'CALLBACK_PROCESSING_ERROR'
            }


def validate_flight_booking_for_payment(booking: Booking) -> Tuple[bool, str]:
    """Validate if flight booking is ready for payment"""
    
    if not booking:
        return False, "Booking not found"
    
    if booking.booking_type != 'FLIGHT':
        return False, "Not a flight booking"
    
    if not booking.flight_booking:
        return False, "Flight booking details not found"
    
    if booking.status in ['confirmed', 'canceled']:
        return False, f"Booking is already {booking.status}"
    
    if booking.flight_booking.status == 'CANCELLED':
        return False, "Flight booking is cancelled"
    
    return True, "Valid for payment"


def get_flight_payment_methods(user=None) -> list:
    """Get available payment methods for flight bookings"""
    
    payment_methods = [
        {
            'code': 'PHONE PAY',
            'name': 'PhonePe',
            'type': 'gateway',
            'enabled': True
        },
        {
            'code': 'PAYU',
            'name': 'PayU',
            'type': 'gateway',
            'enabled': True
        }
    ]
    
    # Add wallet option if user has sufficient balance
    if user and user.is_authenticated:
        try:
            from apps.customer.utils.db_utils import get_wallet_balance, get_company_wallet_balance
            
            balance = 0
            if hasattr(user, 'company_id') and user.company_id:
                balance = get_company_wallet_balance(user.company_id)
            else:
                balance = get_wallet_balance(user.id)
            
            payment_methods.append({
                'code': 'WALLET',
                'name': 'Wallet',
                'type': 'wallet',
                'enabled': balance > 0,
                'balance': float(balance)
            })
        except Exception as e:
            logger.error(f"Error getting wallet balance: {str(e)}")
    
    return payment_methods