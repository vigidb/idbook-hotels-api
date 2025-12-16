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

from ..models import Booking, FlightBooking, BookingPaymentDetail, Invoice
from apps.customer.models import Wallet, WalletTransaction
from apps.payment_gateways.mixins.phonepay_mixins import PhonePayMixin
from apps.payment_gateways.mixins.payu_mixins import PayUMixin
from apps.payment_gateways.mixins.razorpay_mixins import RazorpayMixin
from apps.booking.utils.db_utils import (
    create_booking_payment_details,
    update_booking_payment_details,
    check_booking_and_transaction,
    get_booking_from_payment,
)
from apps.booking.utils.booking_utils import (
    check_wallet_balance_for_booking,
    deduct_booking_amount,
    generate_booking_confirmation_code,
    refund_wallet_payment,
)
from apps.booking.tasks import (
    send_flight_booking_task,
    create_invoice_task,
    send_booking_sms_task,
)
from apps.log_management.utils.db_utils import create_booking_payment_log
from IDBOOKAPI.utils import get_unique_id_from_time

logger = logging.getLogger(__name__)


class FlightPaymentProcessor:
    """
    Handles payment processing for flight bookings
    Integrates with existing payment gateways and wallet system
    """

    def __init__(self, booking: Booking, user, payment_data: dict, request=None):
        self.booking = booking
        self.user = user
        self.payment_data = payment_data
        self.flight_booking = booking.flight_booking
        self.request = request  # Store request for active_group extraction
        self.last_error_message: Optional[str] = None

    def validate_payment_data(self, allow_confirmed: bool = False) -> Tuple[bool, list]:
        """Validate payment request data

        Args:
            allow_confirmed: If True, allows payment for confirmed bookings (for reschedule/SSR)
        """
        errors = []

        # Check required fields
        required_fields = ["amount", "payment_channel"]
        for field in required_fields:
            if field not in self.payment_data:
                errors.append(f"Field '{field}' is required")

        # Validate amount
        if "amount" in self.payment_data:
            try:
                request_amount = Decimal(str(self.payment_data["amount"]))
                if request_amount <= 0:
                    errors.append("Amount must be greater than zero")
                # For reschedule/SSR, amount may not match booking total
                if not allow_confirmed and request_amount != self.booking.final_amount:
                    errors.append(
                        f"Amount mismatch. Expected: {self.booking.final_amount}, Got: {request_amount}"
                    )
            except (ValueError, TypeError):
                errors.append("Invalid amount format")

        # Check if booking is eligible for payment
        if not allow_confirmed:
            if self.booking.status == "confirmed":
                errors.append("Booking is already confirmed")

        if self.booking.status == "canceled":
            errors.append("Cannot process payment for cancelled booking")

        # Flight-specific validations
        if not self.flight_booking:
            errors.append("Flight booking details not found")
        elif self.flight_booking.status == "CANCELLED":
            errors.append("Cannot process payment for cancelled flight")

        return len(errors) == 0, errors

    def initiate_payment(self, allow_confirmed: bool = False) -> Dict:
        """Initiate payment based on selected payment channel

        Args:
            allow_confirmed: If True, allows payment for confirmed bookings (for reschedule/SSR)
        """

        # Validate payment data
        is_valid, errors = self.validate_payment_data(allow_confirmed=allow_confirmed)
        if not is_valid:
            return {
                "success": False,
                "errors": errors,
                "error_code": "VALIDATION_ERROR",
            }

        payment_channel = self.payment_data["payment_channel"].upper()
        amount = Decimal(str(self.payment_data["amount"]))

        # Create payment detail record
        try:
            transaction_type = self.payment_data.get(
                "transaction_type", "flight_booking_payment"
            )
            metadata = self.payment_data.get("metadata", {})
            payment_detail = self._create_payment_detail_record(
                amount, transaction_type, metadata
            )
        except Exception as e:
            logger.error(f"Error creating payment detail: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "error_code": "PAYMENT_RECORD_ERROR",
            }

        # Route to appropriate payment method
        if payment_channel == "WALLET":
            return self._process_wallet_payment(amount, payment_detail)
        elif payment_channel == "PHONE PAY":
            return self._process_phonepe_payment(amount, payment_detail)
        elif payment_channel == "PAYU":
            return self._process_payu_payment(amount, payment_detail)
        elif payment_channel == "RAZORPAY":
            return self._process_razorpay_payment(amount, payment_detail)
        else:
            return {
                "success": False,
                "error": f"Unsupported payment channel: {payment_channel}",
                "error_code": "UNSUPPORTED_PAYMENT_CHANNEL",
            }

    def _create_payment_detail_record(
        self,
        amount: Decimal,
        transaction_type: str = "flight_booking_payment",
        metadata: dict = None,
    ) -> BookingPaymentDetail:
        """Create payment detail record for the booking

        Args:
            amount: Payment amount
            transaction_type: Type of transaction (flight_booking_payment, reschedule_payment, ssr_payment)
            metadata: Additional metadata to store in transaction_details
        """

        # Generate unique merchant transaction ID
        prefix = {
            "flight_booking_payment": "FL",
            "reschedule_payment": "RS",
            "ssr_payment": "SSR",
        }.get(transaction_type, "FL")
        append_id = f"{prefix}{self.user.id}" if self.user else f"{prefix}GUEST"
        payment_detail = create_booking_payment_details(self.booking.id, append_id)

        # Update with flight-specific details
        payment_detail.amount = float(amount)
        payment_detail.transaction_for = "others"
        if metadata:
            payment_detail.transaction_details = metadata
        payment_detail.save()

        return payment_detail

    def _process_wallet_payment(
        self, amount: Decimal, payment_detail: BookingPaymentDetail
    ) -> Dict:
        """Process payment via wallet

        Automatically determines wallet type (company vs personal) based on user's group.
        Corporate users: company wallet (company_id required)
        B2C users: personal wallet
        """

        try:
            print("Processing wallet payment")
            # Check wallet balance - deduct_booking_amount will determine wallet type automatically
            # But we still need to check balance first
            company_id = None
            if self.user:
                # Get company_id from user if corporate user
                user_default_group = getattr(self.user, "default_group", "") or ""
                if user_default_group in ("CORP-ADMIN", "CORP-EMP", "CORPORATE-GRP"):
                    company_id = getattr(self.user, "company_id", None)

            can_pay, balance_info = check_wallet_balance_for_booking(
                self.booking, self.user, company_id=company_id
            )
            print("Can pay:", can_pay, "Balance info:", balance_info)

            if not can_pay:
                return {
                    "success": False,
                    "error": "Insufficient wallet balance",
                    "error_code": "INSUFFICIENT_WALLET_BALANCE",
                    "balance_info": (
                        float(balance_info) if balance_info is not None else 0.0
                    ),
                }

            # Deduct amount from wallet - function will automatically determine wallet type
            # based on user's active group from token (corporate vs B2C)
            from apps.booking.utils.booking_utils import deduct_booking_amount

            deduct_success = deduct_booking_amount(
                self.booking, company_id=company_id, request=self.request
            )

            if not deduct_success:
                return {
                    "success": False,
                    "error": "Wallet deduction failed",
                    "error_code": "WALLET_DEDUCTION_FAILED",
                }

            # Update payment details as paid (wallet deducted)
            update_booking_payment_details(
                payment_detail.merchant_transaction_id,
                {
                    "code": "PAYMENT_SUCCESS",
                    "message": "Payment successful via wallet",
                    "payment_type": "WALLET",
                    "payment_medium": "Idbook",
                    "is_transaction_success": True,
                    "transaction_id": payment_detail.merchant_transaction_id,
                },
            )

            # For reschedule/SSR/ticket issuance, update booking amount and skip AirIQ booking
            transaction_type = self.payment_data.get(
                "transaction_type", "flight_booking_payment"
            )
            if transaction_type in (
                "reschedule_payment",
                "ssr_payment",
                "ticket_issuance_payment",
            ):
                # Update booking total payment made
                self.booking.total_payment_made = (
                    self.booking.total_payment_made or Decimal("0")
                ) + amount
                self.booking.save(update_fields=["total_payment_made"])

                # For ticket issuance, update flight booking status if still PENDING_PAYMENT
                if (
                    transaction_type == "ticket_issuance_payment"
                    and self.flight_booking
                ):
                    if self.flight_booking.status == "PENDING_PAYMENT":
                        # Check if this was a BlockPNR booking
                        airiq_request = self.flight_booking.airiq_request_data or {}
                        if airiq_request.get("BlockPNR", False):
                            self.flight_booking.status = "HELD"
                        else:
                            self.flight_booking.status = "CONFIRMED"
                        self.flight_booking.save(update_fields=["status"])

                # Only send notifications for reschedule/SSR (ticket issuance will send after ticket is issued)
                if transaction_type != "ticket_issuance_payment":
                    self._send_booking_notifications()
                return {
                    "success": True,
                    "payment_method": "wallet",
                    "transaction_id": payment_detail.merchant_transaction_id,
                    "message": "Payment successful via wallet",
                }

            # Confirm booking (calls AirIQ Book); if it fails, refund wallet and revert states
            confirmed = self._confirm_flight_booking()
            if not confirmed:
                # Refund wallet since supplier booking failed
                refund_details = {
                    "reason": "AirIQ booking failed after wallet deduction",
                    "timestamp": timezone.now().isoformat(),
                    "airiq_error": self.last_error_message,
                }
                refund_ok, refund_status, refund_data = refund_wallet_payment(
                    self.booking, Decimal(self.booking.final_amount), refund_details
                )
                # Revert booking/flight statuses back to pending
                self.booking.status = "pending"
                self.booking.total_payment_made = Decimal("0.0")
                self.booking.save(update_fields=["status", "total_payment_made"])
                self.flight_booking.status = "PENDING_PAYMENT"
                self.flight_booking.save(update_fields=["status"])
                # Update payment record to reflect refund
                update_booking_payment_details(
                    payment_detail.merchant_transaction_id,
                    {
                        "code": "BOOKING_FAILED_REFUNDED",
                        "message": "Supplier booking failed; wallet refunded",
                        "transaction_details": {
                            "refund_status": refund_status,
                            "refund_data": refund_data,
                            "airiq_error": self.last_error_message,
                        },
                    },
                )
                return {
                    "success": False,
                    "error": self.last_error_message
                    or "Supplier booking failed; wallet refunded",
                    "error_code": "AIRIQ_BOOKING_FAILED",
                    "refund_status": refund_status,
                }

            # Send notifications only on confirmed
            self._send_booking_notifications()

            return {
                "success": True,
                "payment_method": "wallet",
                "transaction_id": payment_detail.merchant_transaction_id,
                "message": "Payment successful via wallet",
            }

        except Exception as e:
            print("Error processing wallet payment:", str(e))
            logger.error(f"Wallet payment error: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "error_code": "WALLET_PAYMENT_ERROR",
            }

    def _process_phonepe_payment(
        self, amount: Decimal, payment_detail: BookingPaymentDetail
    ) -> Dict:
        """Process payment via PhonePe"""

        try:
            phonepe_mixin = PhonePayMixin()

            # Prepare PhonePe payload
            merchant_id = settings.MERCHANT_ID
            redirect_url = self.payment_data.get("redirect_url") or getattr(
                settings, "FRONTEND_URL", ""
            )

            # Determine callback URL based on transaction type
            # Handle trailing slash in CALLBACK_URL to avoid double slashes
            base_url = settings.CALLBACK_URL.rstrip("/")
            transaction_type = self.payment_data.get(
                "transaction_type", "flight_booking_payment"
            )

            # IMPORTANT: For ticket issuance payments, use the specific ticket callback URL
            # Do NOT use default flight payment callback URL
            # This is critical - ticket issuance must use its own callback endpoint
            if transaction_type == "ticket_issuance_payment":
                callback_url = f"{base_url}/api/v1/booking/flight-bookings/ticket/phonepe-callback/"
                logger.info(
                    f"TICKET ISSUANCE: Using ticket callback URL: {callback_url}"
                )
                print(
                    f"=== PhonePe Payment: TICKET ISSUANCE - Using ticket callback URL: {callback_url} ==="
                )
            elif transaction_type in ("reschedule_payment", "ssr_payment"):
                # For reschedule and SSR, use their specific callbacks
                if transaction_type == "reschedule_payment":
                    callback_url = f"{base_url}/api/v1/booking/flight-bookings/reschedule/phonepe-callback/"
                else:  # ssr_payment
                    callback_url = f"{base_url}/api/v1/booking/flight-bookings/ancillary/phonepe-callback/"
                logger.info(
                    f"{transaction_type.upper()}: Using callback URL: {callback_url}"
                )
                print(
                    f"=== PhonePe Payment: {transaction_type.upper()} - Using callback URL: {callback_url} ==="
                )
            else:
                # Default flight booking payment callback
                callback_url = (
                    f"{base_url}/api/v1/booking/flight-payment/phonepe-callback/"
                )
                logger.info(
                    f"DEFAULT: Using flight payment callback URL: {callback_url}"
                )
                print(
                    f"=== PhonePe Payment: DEFAULT - Using flight payment callback URL: {callback_url} ==="
                )

            # Log transaction type to verify it's being passed correctly
            logger.info(
                f"PhonePe payment - Transaction type: {transaction_type}, Callback URL: {callback_url}"
            )
            print(f"=== PhonePe Payment Details ===")
            print(f"Transaction Type: {transaction_type}")
            print(f"Callback URL: {callback_url}")
            print(f"Merchant Transaction ID: {payment_detail.merchant_transaction_id}")
            print(f"Amount: {amount}")
            print("=" * 50)

            # CRITICAL CHECK: Verify ticket issuance is using correct callback
            if transaction_type == "ticket_issuance_payment":
                expected_callback = f"{base_url}/api/v1/booking/flight-bookings/ticket/phonepe-callback/"
                if callback_url != expected_callback:
                    error_msg = f"CRITICAL ERROR: Ticket issuance callback URL mismatch! Expected: {expected_callback}, Got: {callback_url}"
                    logger.error(error_msg)
                    print(f"ERROR: {error_msg}")
                    raise ValueError(error_msg)

            payload = {
                "merchantId": merchant_id,
                "merchantTransactionId": payment_detail.merchant_transaction_id,
                "merchantUserId": str(self.user.id) if self.user else "guest",
                "amount": int(amount * 100),  # PhonePe expects amount in paise
                "redirectUrl": redirect_url,
                "redirectMode": "REDIRECT",
                "callbackUrl": callback_url,
                "paymentInstrument": {"type": "PAY_PAGE"},
            }

            # Log the complete payload (without sensitive data)
            logger.info(
                f"PhonePe payload - Callback URL: {payload.get('callbackUrl')}, Transaction Type: {transaction_type}"
            )
            print(f"=== PhonePe Payload Callback URL: {payload.get('callbackUrl')} ===")

            # Log payment request
            payment_log = {
                "booking_id": self.booking.id,
                "merchant_transaction_id": payment_detail.merchant_transaction_id,
                "request": payload,
            }

            # Get encrypted headers and make request
            req, auth_header = phonepe_mixin.get_encrypted_header_and_payload(payload)
            response = phonepe_mixin.post_pay_page(req, auth_header)

            if response.status_code == 200:
                data_json = response.json()
                payment_log["response"] = data_json

                # Update payment detail
                update_booking_payment_details(
                    payment_detail.merchant_transaction_id,
                    {
                        "payment_type": "PAYMENT GATEWAY",
                        "payment_medium": "PHONE PAY",
                        "code": "PAYMENT_INITIATED",
                        "message": "Payment initiated via PhonePe",
                    },
                )

                # Create payment log
                create_booking_payment_log(payment_log)

                # Extract payment URL
                instrument_response = data_json.get("data", {}).get(
                    "instrumentResponse", {}
                )
                payment_url = instrument_response.get("redirectInfo", {}).get("url", "")

                return {
                    "success": True,
                    "payment_method": "phonepe",
                    "payment_url": payment_url,
                    "transaction_id": payment_detail.merchant_transaction_id,
                    "message": "PhonePe payment initiated successfully",
                }
            else:
                payment_log["response"] = {"error": response.text}
                create_booking_payment_log(payment_log)

                return {
                    "success": False,
                    "error": response.text,
                    "error_code": "PHONEPE_INITIATION_FAILED",
                }

        except Exception as e:
            logger.error(f"PhonePe payment error: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "error_code": "PHONEPE_PAYMENT_ERROR",
            }

    def _process_payu_payment(
        self, amount: Decimal, payment_detail: BookingPaymentDetail
    ) -> Dict:
        """Process payment via PayU"""

        try:
            payu_mixin = PayUMixin()

            # Prepare PayU payload - handle trailing slash in CALLBACK_URL
            base_url = settings.CALLBACK_URL.rstrip("/")

            payload = {
                "key": settings.PAYU_KEY,
                "txnid": payment_detail.merchant_transaction_id,
                "amount": str(amount),
                "productinfo": f"Flight Booking - {self.flight_booking.flying_from} to {self.flight_booking.flying_to}",
                "firstname": self.user.first_name if self.user else "Guest",
                "email": (
                    self.user.email if self.user else self.payment_data.get("email", "")
                ),
                "phone": (
                    self.user.mobile_number
                    if self.user
                    else self.payment_data.get("phone", "")
                ),
                "surl": f"{base_url}/api/v1/booking/flight-payment/payu-success/",
                "furl": f"{base_url}/api/v1/booking/flight-payment/payu-failure/",
            }

            # Generate hash
            hash_string = f"{payload['key']}|{payload['txnid']}|{payload['amount']}|{payload['productinfo']}|{payload['firstname']}|{payload['email']}|||||||||||{settings.PAYU_SALT}"
            payload["hash"] = payu_mixin.generate_hash(hash_string)

            # Update payment detail
            update_booking_payment_details(
                payment_detail.merchant_transaction_id,
                {
                    "payment_type": "PAYMENT GATEWAY",
                    "payment_medium": "PAYU",
                    "code": "PAYMENT_INITIATED",
                    "message": "Payment initiated via PayU",
                },
            )

            return {
                "success": True,
                "payment_method": "payu",
                "payment_url": settings.PAYU_URL,
                "payload": payload,
                "transaction_id": payment_detail.merchant_transaction_id,
                "message": "PayU payment initiated successfully",
            }

        except Exception as e:
            logger.error(f"PayU payment error: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "error_code": "PAYU_PAYMENT_ERROR",
            }

    def _process_razorpay_payment(
        self, amount: Decimal, payment_detail: BookingPaymentDetail
    ) -> Dict:
        """Process payment via Razorpay"""

        try:
            razorpay_mixin = RazorpayMixin()

            # Get redirect URL from payment data or use default
            redirect_url = self.payment_data.get(
                "redirect_url",
                f"{settings.CALLBACK_URL.rstrip('/')}/api/v1/booking/payment/razorpay/success/",
            )

            # Determine transaction type
            transaction_type = self.payment_data.get(
                "transaction_type", "flight_booking_payment"
            )

            # Prepare notes for Razorpay order
            notes = {
                "booking_id": str(self.booking.id),
                "booking_type": self.booking.booking_type,
                "transaction_type": transaction_type,
                "merchant_transaction_id": payment_detail.merchant_transaction_id,
            }

            if self.flight_booking:
                notes.update(
                    {
                        "flight_booking_id": str(self.flight_booking.id),
                        "flying_from": self.flight_booking.flying_from or "",
                        "flying_to": self.flight_booking.flying_to or "",
                    }
                )

            # Create Razorpay order
            receipt_id = payment_detail.merchant_transaction_id
            order_result = razorpay_mixin.create_razorpay_order(
                amount=float(amount),
                currency="INR",
                receipt=receipt_id,
                notes=notes,
            )

            if not order_result.get("success"):
                return {
                    "success": False,
                    "error": order_result.get("error", "Failed to create Razorpay order"),
                    "error_code": order_result.get("error_code", "RAZORPAY_ORDER_ERROR"),
                }

            # Store Razorpay order in database
            from apps.payment_gateways.models import RazorpayOrder

            razorpay_order = RazorpayOrder.objects.create(
                user=self.user if self.user else None,
                booking=self.booking,
                rp_id=order_result["order_id"],
                entity="order",
                amount=order_result["amount"],  # Amount in paise
                amount_due=order_result["amount"],
                currency=order_result["currency"],
                receipt=receipt_id,
                status=order_result["status"],
                notes=notes,
                created_at=str(int(timezone.now().timestamp())),
            )

            # Update payment detail
            update_booking_payment_details(
                payment_detail.merchant_transaction_id,
                {
                    "payment_type": "PAYMENT GATEWAY",
                    "payment_medium": "RAZORPAY",
                    "code": "PAYMENT_INITIATED",
                    "message": "Payment initiated via Razorpay",
                    "transaction_details": {
                        "razorpay_order_id": order_result["order_id"],
                        "razorpay_order_status": order_result["status"],
                    },
                },
            )

            # Create payment log
            payment_log = {
                "booking_id": self.booking.id,
                "merchant_transaction_id": payment_detail.merchant_transaction_id,
                "razorpay_order_id": order_result["order_id"],
                "amount": float(amount),
            }
            create_booking_payment_log(payment_log)

            # Get Razorpay public key for frontend
            razorpay_key = getattr(settings, "RAZORPAY_KEY_ID", "")

            return {
                "success": True,
                "payment_method": "razorpay",
                "order_id": order_result["order_id"],
                "razorpay_key": razorpay_key,
                "amount": order_result["amount"],  # Amount in paise
                "currency": order_result["currency"],
                "name": self.user.first_name if self.user else "Guest",
                "email": (
                    self.user.email
                    if self.user
                    else self.payment_data.get("email", "")
                ),
                "contact": (
                    self.user.mobile_number
                    if self.user and hasattr(self.user, "mobile_number")
                    else self.payment_data.get("phone", "")
                ),
                "redirect_url": redirect_url,
                "transaction_id": payment_detail.merchant_transaction_id,
                "message": "Razorpay payment order created successfully",
            }

        except Exception as e:
            logger.error(f"Razorpay payment error: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "error_code": "RAZORPAY_PAYMENT_ERROR",
            }

    def _confirm_flight_booking(self) -> bool:
        """Confirm the flight booking after successful payment: call AirIQ Book, update, then auto-issue ticket.
        Returns True if supplier booking succeeded (PNRs obtained), False otherwise.
        """

        # 1) Call AirIQ Booking API using stored request data
        self.last_error_message = None
        airiq_success = False
        try:
            from apps.flights.services.airiq_service import (
                airiq_service,
                AirIQException,
            )

            req = self.flight_booking.airiq_request_data or {}
            if not req:
                logger.warning(
                    f"No AirIQ request data found for booking {self.booking.id}; skipping AirIQ booking call"
                )
            else:
                booking_data, track_id, block_pnr = (
                    self._build_airiq_booking_payload_from_stored_request(req)
                )
                airiq_resp = airiq_service.create_booking(
                    booking_data=booking_data, track_id=track_id, block_pnr=block_pnr
                )
                # Persist the exact booking payload and AirIQ response for audit/debug
                try:
                    fb = self.flight_booking
                    # Append last used booking payload inside airiq_request_data for traceability
                    req_blob = fb.airiq_request_data or {}
                    req_blob["airiq_booking_payload"] = {
                        "booking_data": booking_data,
                        "track_id": track_id,
                        "block_pnr": block_pnr,
                    }
                    fb.airiq_request_data = req_blob
                    fb.airiq_response_data = airiq_resp
                    fb.save(update_fields=["airiq_request_data", "airiq_response_data"])
                except Exception:
                    pass
                # Always attempt to store identifiers (TrackId etc.)
                self._update_flight_booking_from_airiq_response(airiq_resp)

                # Determine success from AirIQ response
                status_info = (airiq_resp or {}).get("Status") or {}
                result_code = str(status_info.get("ResultCode") or "").strip()
                error_msg = status_info.get("Error") or ""
                if error_msg:
                    self.last_error_message = error_msg

                # Success if code indicates success AND we have PNR
                has_pnr = bool(
                    self.flight_booking.airiq_pnr or self.flight_booking.airline_pnr
                )
                code_success = result_code in ("1", "01", 1)
                airiq_success = bool(code_success and has_pnr)
                if not airiq_success and not self.last_error_message:
                    self.last_error_message = "AirIQ booking failed"
        except AirIQException as e:
            self.last_error_message = str(e)
            logger.error(f"AirIQ booking failed for booking {self.booking.id}: {e}")
        except Exception as e:
            self.last_error_message = str(e)
            logger.error(
                f"Unexpected error during AirIQ booking for {self.booking.id}: {e}"
            )

        # 2) Generate confirmation code and mark booking confirmed
        booking_id = self.booking.id
        booking_type = self.booking.booking_type

        while True:
            confirmation_code = generate_booking_confirmation_code(
                booking_id, booking_type
            )
            # Check if confirmation code already exists
            from apps.booking.utils.db_utils import check_booking_confirmation_code

            if not check_booking_confirmation_code(confirmation_code):
                break

        if airiq_success:
            # Update booking only on AirIQ success
            self.booking.confirmation_code = confirmation_code
            self.booking.status = "confirmed"
            self.booking.total_payment_made = self.booking.final_amount
            self.booking.save()

            # Update booking meta info
            if hasattr(self.booking, "meta_info"):
                self.booking.meta_info.booking_confirmed_date = timezone.now()
                self.booking.meta_info.save()

            # Update flight booking status
            self.flight_booking.status = "CONFIRMED"
            self.flight_booking.confirmed_at = timezone.now()
            self.flight_booking.save()

            logger.info(
                f"Flight booking {self.booking.id} confirmed with code {confirmation_code}"
            )

            # Skip auto-issuing tickets; can be issued later via API if required
            # if (self.flight_booking.airiq_track_id and self.flight_booking.airiq_pnr and self.flight_booking.airline_pnr):
            #     self._auto_issue_ticket()
            return True
        else:
            logger.error(
                f"AirIQ booking failed; not confirming booking {self.booking.id}"
            )
            return False

    def _build_airiq_booking_payload_from_stored_request(self, req: dict):
        """Map stored airiq_request_data to AirIQService.create_booking booking_data payload.
        Supports multiple ItineraryFlightsInfo (domestic RT) and single-item international RT.
        """
        # Adults/children/infants
        adults = int(req.get("AdultCount", 1) or 0)
        children = int(req.get("ChildCount", 0) or 0)
        infants = int(req.get("InfantCount", 0) or 0)

        itin_list = req.get("ItineraryFlightsInfo") or []
        itineraries = []
        total_amount_sum = 0.0
        for item in itin_list:
            token = item.get("Token", "")
            flights = item.get("FlighstInfo") or item.get("FlightsInfo") or []
            seats_list = []
            meals_list = []
            bagg_list = []
            other_list = item.get("OtherSSRInfo", []) or []
            for s in item.get("SeatsSSRInfo", []) or []:
                seats_list.append(
                    {
                        "seat_id": s.get("SeatID"),
                        "passenger_ref": (
                            int(s.get("PaxRefNumber") or 0)
                            if s.get("PaxRefNumber")
                            else None
                        ),
                    }
                )
            for b in item.get("BaggSSRInfo", []) or []:
                bagg_list.append(
                    {
                        "baggage_id": b.get("BaggageID"),
                        "passenger_ref": (
                            int(b.get("PaxRefNumber") or 0)
                            if s.get("PaxRefNumber")
                            else None
                        ),
                    }
                )
            for m in item.get("MealsSSRInfo", []) or []:
                meals_list.append(
                    {
                        "meal_id": m.get("MealID"),
                        "passenger_ref": (
                            int(m.get("PaxRefNumber") or 0)
                            if m.get("PaxRefNumber")
                            else None
                        ),
                    }
                )
            pay = (item.get("PaymentInfo") or [{}])[0]
            item_total = pay.get("TotalAmount")
            try:
                total_amount_sum += float(item_total or 0)
            except Exception:
                pass
            itineraries.append(
                {
                    "token": token,
                    "flight_segments": flights,
                    "seats": seats_list,
                    "meals": meals_list,
                    "baggage": bagg_list,
                    "other_services": other_list,
                    "payment_total": item_total,
                }
            )
        # If no itinerary items, fallback to empty structure
        if not itineraries:
            itineraries = [
                {
                    "token": "",
                    "flight_segments": [],
                    "seats": [],
                    "meals": [],
                    "baggage": [],
                    "other_services": [],
                    "payment_total": None,
                }
            ]

        # Passengers: map AirIQ style to service input
        pax_src = req.get("PaxDetailsInfo") or []
        passengers = []
        for p in pax_src:
            passengers.append(
                {
                    "title": p.get("Title", ""),
                    "first_name": p.get("FirstName", ""),
                    "last_name": p.get("LastName", ""),
                    "date_of_birth": p.get("DOB", ""),
                    "gender": p.get("Gender", ""),
                    "pax_type": p.get("PaxType", ""),
                    "passport_number": p.get("PassportNo", ""),
                    "passport_expiry": p.get("PassportExpiry", ""),
                    "passport_issued_date": p.get("PassportIssuedDate", ""),
                    "passport_country_code": p.get("PassportCountryCode", ""),
                    "infant_ref": p.get("InfantRef", ""),
                }
            )

        # Contact/GST
        addr = req.get("AddressDetails") or {}
        contact = {
            "country_code": addr.get("CountryCode", "91"),
            "phone": addr.get("ContactNumber", ""),
            "email": addr.get("EmailID", ""),
        }
        gst_src = req.get("GSTInfo") or {}
        gst = {
            "number": gst_src.get("GSTNumber", ""),
            "company_name": gst_src.get("GSTCompanyName", ""),
            "address": gst_src.get("GSTAddress", ""),
            "email": gst_src.get("GSTEmailID", ""),
            "mobile": gst_src.get("GSTMobileNumber", ""),
        }

        booking_data = {
            "itineraries": itineraries,
            "passengers": passengers,
            "contact": contact,
            "gst": gst,
            "adults": adults,
            "children": children,
            "infants": infants,
            "origin": req.get("BaseOrigin"),
            "destination": req.get("BaseDestination"),
            "trip_type": req.get("TripType", "O"),
            "total_amount": total_amount_sum or None,
        }
        track_id = req.get("TrackId") or req.get("TrackID") or ""
        block_pnr = bool(req.get("BlockPNR", False))
        return booking_data, track_id, block_pnr

    def _update_flight_booking_from_airiq_response(self, airiq_resp: dict) -> None:
        """Persist PNRs/Track IDs (supporting multiple itineraries), tickets and SSRs per segment.
        Handles both domestic RT (two itinerary items) and international RT (single itinerary with both legs).
        """
        try:
            from decimal import Decimal as _D

            booking_resp = airiq_resp.get("Bookingresponse") or {}
            itineraries = booking_resp.get("ItinearyDetails") or []

            airiq_pnrs_set, airline_pnrs_set, track_ids_set = set(), set(), set()
            all_ticket_numbers = []
            booked_itins = []

            # Helper: normalize NA values
            def _norm(val: str) -> str:
                try:
                    s = (val or "").strip()
                    return "" if s.upper() in ("N/A", "NA", "NULL") else s
                except Exception:
                    return ""

            # Quick passenger cache for matching
            pax_qs = list(self.flight_booking.passengers.all())

            def match_passenger(t: dict):
                title = (t.get("Title") or "").upper()
                first = (t.get("FirstName") or "").strip().upper()
                last = (t.get("LastName") or "").strip().upper()
                dob_str = t.get("DateOfBirth") or ""
                dob_norm = None
                if dob_str:
                    from datetime import datetime as _dt

                    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
                        try:
                            dob_norm = _dt.strptime(dob_str, fmt).date()
                            break
                        except Exception:
                            continue
                for p in pax_qs:
                    if (
                        p.title.upper() == title
                        and p.first_name.strip().upper() == first
                        and p.last_name.strip().upper() == last
                    ):
                        if not dob_norm or (p.date_of_birth == dob_norm):
                            return p
                return None

            # Iterate all itinerary containers
            for itin_container in itineraries:
                items = itin_container.get("Item") or []
                for item in items:
                    # PNRs and Track ID at itinerary level
                    ai_pnr = _norm(item.get("AirIqPNR") or item.get("AiriqPNR"))
                    trk = _norm(airiq_resp.get("TrackId") or item.get("BookingTrackId"))
                    # Determine airline PNR with nested preference
                    nested_airline_pnr = ""
                    trav = item.get("TravellerInfo", {})
                    trav_items = trav.get("Item") or []
                    if trav_items:
                        seg0 = (trav_items[0].get("SegmentInformation") or {}).get(
                            "Item"
                        ) or []
                        if seg0:
                            nested_airline_pnr = seg0[0].get("AirlinePNR") or ""
                    airline_pnr = (
                        _norm(nested_airline_pnr)
                        or _norm(item.get("AirlinePNR"))
                        or _norm(item.get("CRSPNR"))
                    )

                    if ai_pnr:
                        airiq_pnrs_set.add(ai_pnr)
                    if airline_pnr:
                        airline_pnrs_set.add(airline_pnr)
                    if trk:
                        track_ids_set.add(trk)

                    # Base route updates (optional)
                    base_origin = item.get("BaseOrigin") or ""
                    base_dest = item.get("BaseDestination") or ""
                    if base_origin:
                        self.flight_booking.flying_from = base_origin
                    if base_dest:
                        self.flight_booking.flying_to = base_dest

                    # Build booked_itinerary entry
                    pay_items = (item.get("PaymentDetails") or {}).get("Item") or []
                    total_amount = _D("0")
                    for pi in pay_items:
                        try:
                            total_amount += _D(str(pi.get("Amount") or "0"))
                        except Exception:
                            pass

                    # Derive segment summaries from first passenger's segments to avoid duplication
                    segment_summaries = []
                    seen_seg_keys = set()
                    if trav_items:
                        any_seg_items = (
                            trav_items[0].get("SegmentInformation") or {}
                        ).get("Item") or []
                        for idx, s in enumerate(any_seg_items, start=1):
                            key = (
                                (s.get("Origin") or ""),
                                (s.get("Destination") or ""),
                                (s.get("CarrierCode") or ""),
                                (s.get("FlightNumber") or ""),
                                (s.get("DepartureDateTime") or ""),
                            )
                            if key in seen_seg_keys:
                                continue
                            seen_seg_keys.add(key)
                            segment_summaries.append(
                                {
                                    "seg_ref": s.get("SegRef")
                                    or s.get("SegmentRef")
                                    or idx,
                                    "origin": s.get("Origin") or "",
                                    "destination": s.get("Destination") or "",
                                    "carrier": s.get("CarrierCode") or "",
                                    "flight_number": s.get("FlightNumber") or "",
                                    "dep_time": s.get("DepartureDateTime") or "",
                                    "arr_time": s.get("ArrivalDateTime") or "",
                                    "class_code": s.get("ClassCode") or "",
                                }
                            )

                    booked_itins.append(
                        {
                            "airiq_pnr": ai_pnr,
                            "airline_pnr": airline_pnr,
                            "track_id": trk,
                            "base_origin": base_origin,
                            "base_destination": base_dest,
                            "amount": str(total_amount),
                            "segments": segment_summaries,
                        }
                    )

                    # Persist per-passenger tickets and SSRs for all segments
                    from apps.booking.models import FlightAncillaryService as _FAS

                    for t in trav_items:
                        passenger = match_passenger(t)
                        if not passenger:
                            continue
                        tn = t.get("TicketNumber") or t.get("TicketNo")
                        if tn:
                            all_ticket_numbers.append(tn)
                            if not passenger.ticket_number:
                                passenger.ticket_number = tn
                        seginfo = t.get("SegmentInformation") or {}
                        seg_items = seginfo.get("Item") or []
                        for sidx, s in enumerate(seg_items, start=1):
                            seg_ref = s.get("SegRef") or s.get("SegmentRef") or sidx
                            # Update flight/airline meta only from first seen segment
                            if not self.flight_booking.flight_no and (
                                s.get("FlightNumber") or ""
                            ):
                                self.flight_booking.flight_no = s.get("FlightNumber")
                            if not self.flight_booking.airline_code and (
                                s.get("CarrierCode") or ""
                            ):
                                self.flight_booking.airline_code = s.get("CarrierCode")

                            seat_pref = (s.get("SeatPreference") or "").strip()
                            seat_amt = s.get("SeatAmount") or "0"
                            meal_pref = (s.get("MealsPreference") or "").strip()
                            meal_amt = s.get("MealsAmount") or "0"
                            bag_pref = (s.get("BaggagePreference") or "").strip()
                            bag_amt = s.get("BaggageAmount") or "0"

                            # Set seat number if available
                            if seat_pref and not passenger.seat_number:
                                passenger.seat_number = seat_pref
                            passenger.save(
                                update_fields=["ticket_number", "seat_number"]
                            )

                            def ensure_service(stype, code, desc, amt):
                                if not desc and not code:
                                    return
                                try:
                                    price = _D(str(amt or 0))
                                except Exception:
                                    price = _D("0")
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
                                        airiq_service_id=str(code or ""),
                                        service_code=str(code or ""),
                                        service_description=(desc or str(code))[:200],
                                        segment_reference=seg_ref,
                                        service_price=price,
                                    )

                            if seat_pref:
                                ensure_service(
                                    "SEAT", seat_pref, f"Seat {seat_pref}", seat_amt
                                )
                            if meal_pref:
                                ensure_service("MEAL", "", meal_pref, meal_amt)
                            if bag_pref:
                                ensure_service("BAGGAGE", "", bag_pref, bag_amt)

            # Persist collected fields to model
            updates = []
            # Single-value fallbacks for backward-compat
            if airiq_pnrs_set and not self.flight_booking.airiq_pnr:
                self.flight_booking.airiq_pnr = next(iter(airiq_pnrs_set))
                updates.append("airiq_pnr")
            if airline_pnrs_set and not self.flight_booking.airline_pnr:
                self.flight_booking.airline_pnr = next(iter(airline_pnrs_set))
                updates.append("airline_pnr")
            if track_ids_set and not self.flight_booking.airiq_track_id:
                self.flight_booking.airiq_track_id = next(iter(track_ids_set))
                updates.append("airiq_track_id")

            # List fields
            if airiq_pnrs_set:
                self.flight_booking.airiq_pnrs = sorted(list(airiq_pnrs_set))
                updates.append("airiq_pnrs")
            if airline_pnrs_set:
                self.flight_booking.airline_pnrs = sorted(list(airline_pnrs_set))
                updates.append("airline_pnrs")
            if track_ids_set:
                self.flight_booking.airiq_track_ids = sorted(list(track_ids_set))
                updates.append("airiq_track_ids")
            if booked_itins:
                self.flight_booking.booked_itineraries = booked_itins
                # self.flight_booking.booked_itineraries = airiq_resp.get('Bookingresponse', {}).get('ItinearyDetails', [])
                updates.append("booked_itineraries")
            if all_ticket_numbers:
                # de-dup preserving order
                seen = set()
                uniq = []
                for tn in all_ticket_numbers:
                    if tn and tn not in seen:
                        seen.add(tn)
                        uniq.append(tn)
                self.flight_booking.ticket_numbers = uniq
                updates.append("ticket_numbers")

            for f in ("flight_no", "airline_code", "flying_from", "flying_to"):
                if getattr(self.flight_booking, f, None) and f not in updates:
                    updates.append(f)

            if updates:
                self.flight_booking.save(update_fields=updates)

        except Exception as e:
            logger.error(
                f"Failed to update flight booking from AirIQ response for {self.booking.id}: {e}"
            )

    def _auto_issue_ticket(self):
        """Automatically issue ticket after successful payment and confirmation"""

        try:
            # Check if we have required data for ticketing
            if not all(
                [
                    self.flight_booking.airiq_track_id,
                    self.flight_booking.airiq_pnr,
                    self.flight_booking.airline_pnr,
                ]
            ):
                logger.warning(
                    f"Cannot auto-issue ticket for booking {self.booking.id}: Missing PNR data"
                )
                return False

            # Check if already ticketed
            if self.flight_booking.status == "TICKETED":
                logger.info(f"Booking {self.booking.id} already ticketed")
                return True

            # Import AirIQ service
            from apps.flights.services.airiq_service import (
                airiq_service,
                AirIQException,
            )

            # Issue ticket via AirIQ
            ticket_response = airiq_service.issue_ticket(
                booking_track_id=self.flight_booking.airiq_track_id,
                airiq_pnr=self.flight_booking.airiq_pnr,
                airline_pnr=self.flight_booking.airline_pnr,
                booking_amount=float(self.booking.final_amount),
            )

            # Update flight booking with ticket details
            self.flight_booking.status = "TICKETED"

            # Extract ticket numbers if available
            if "TicketNumbers" in ticket_response:
                self.flight_booking.ticket_numbers = ticket_response["TicketNumbers"]

            self.flight_booking.save()

            logger.info(f"Ticket auto-issued for booking {self.booking.id}")
            return True

        except AirIQException as e:
            logger.error(
                f"AirIQ error auto-issuing ticket for booking {self.booking.id}: {str(e)}"
            )
            # Don't fail the confirmation, just log the error
            return False
        except Exception as e:
            logger.error(
                f"Error auto-issuing ticket for booking {self.booking.id}: {str(e)}"
            )
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
            send_booking_email_task.delay(booking_id, "confirmed-booking")

            # 3. SMS confirmation (also logs Notification via message templates)
            send_flight_booking_task.delay(booking_id, "confirmed")

            logger.info(f"Flight booking notifications queued for booking {booking_id}")

        except Exception as e:
            print(
                f"Error queuing flight booking notifications for booking {self.booking.id}: {str(e)}"
            )
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
        from ..models import Booking, BookingPaymentDetail

        # Get the booking
        booking = Booking.objects.select_related("flight_booking", "user").get(
            id=booking_id, booking_type="FLIGHT"
        )

        if not booking.flight_booking:
            logger.error(f"Flight booking details not found for booking {booking_id}")
            return False

        # Get transaction type from payment detail if available
        transaction_id = payment_details.get("transaction_id", "")
        transaction_type = "flight_booking_payment"
        if transaction_id:
            try:
                payment_detail = BookingPaymentDetail.objects.filter(
                    merchant_transaction_id=transaction_id
                ).first()
                if payment_detail and payment_detail.transaction_details:
                    metadata = payment_detail.transaction_details
                    if metadata.get("reschedule_type"):
                        transaction_type = "reschedule_payment"
                    elif metadata.get("ssr_type"):
                        transaction_type = "ssr_payment"
            except Exception:
                pass

        # For reschedule/SSR payments, just update booking amounts
        if transaction_type in ("reschedule_payment", "ssr_payment"):
            amount = Decimal(str(payment_details.get("amount", 0)))
            booking.total_payment_made = (
                booking.total_payment_made or Decimal("0")
            ) + amount
            booking.save(update_fields=["total_payment_made"])

            if transaction_type == "reschedule_payment" and booking.flight_booking:
                booking.flight_booking.status = "RESCHEDULED"
                booking.flight_booking.save(update_fields=["status"])

            logger.info(
                f"Successfully processed {transaction_type} payment for booking {booking_id}"
            )
            return True

        # For initial booking payments, confirm booking
        processor = FlightPaymentProcessor(booking, booking.user, payment_details)

        # Confirm booking and auto-issue ticket
        with transaction.atomic():
            confirmed = processor._confirm_flight_booking()
            
            if not confirmed:
                # AirIQ booking failed - need to refund payment
                logger.error(
                    f"AirIQ booking failed for booking {booking_id} after payment. Initiating refund..."
                )
                
                # Get payment details to determine payment method
                payment_id = payment_details.get("payment_id") or payment_details.get("razorpay_payment_id")
                payment_medium = payment_details.get("payment_medium", "")
                
                # Check if payment was via Razorpay
                if payment_medium.upper() == "RAZORPAY" and payment_id:
                    try:
                        from apps.payment_gateways.mixins.razorpay_mixins import RazorpayMixin
                        from apps.booking.utils.db_utils import update_booking_payment_details
                        from decimal import Decimal
                        
                        razorpay_mixin = RazorpayMixin()
                        refund_amount = Decimal(str(booking.final_amount))
                        
                        # Prepare refund notes
                        refund_notes = {
                            "reason": "AirIQ booking failed after payment",
                            "booking_id": str(booking.id),
                            "airiq_error": processor.last_error_message or "AirIQ booking failed",
                            "timestamp": timezone.now().isoformat(),
                        }
                        
                        # Process refund via Razorpay
                        refund_result = razorpay_mixin.refund_payment(
                            payment_id=payment_id,
                            amount=float(refund_amount),
                            notes=refund_notes,
                            speed="normal"
                        )
                        
                        if refund_result.get("success"):
                            # Refund successful
                            logger.info(
                                f"Razorpay refund successful for booking {booking_id}. Refund ID: {refund_result.get('refund_id')}"
                            )
                            
                            # Revert booking/flight statuses
                            booking.status = "pending"
                            booking.total_payment_made = Decimal("0.0")
                            booking.save(update_fields=["status", "total_payment_made"])
                            
                            if booking.flight_booking:
                                booking.flight_booking.status = "PENDING_PAYMENT"
                                booking.flight_booking.save(update_fields=["status"])
                            
                            # Update payment record to reflect refund
                            transaction_id = payment_details.get("transaction_id", "")
                            if transaction_id:
                                update_booking_payment_details(
                                    transaction_id,
                                    {
                                        "code": "BOOKING_FAILED_REFUNDED",
                                        "message": "Supplier booking failed; payment refunded",
                                        "transaction_details": {
                                            "refund_status": "refunded",
                                            "refund_id": refund_result.get("refund_id"),
                                            "refund_amount": float(refund_amount),
                                            "airiq_error": processor.last_error_message,
                                            "refund_data": refund_result,
                                        },
                                    },
                                )
                            
                            logger.warning(
                                f"Booking {booking_id} refunded due to AirIQ booking failure"
                            )
                            return False
                        else:
                            # Refund failed - log error but don't fail the transaction
                            logger.error(
                                f"Razorpay refund failed for booking {booking_id}: {refund_result.get('error')}"
                            )
                            
                            # Mark booking as failed and payment for manual refund
                            booking.status = "failed"
                            booking.save(update_fields=["status"])
                            
                            transaction_id = payment_details.get("transaction_id", "")
                            if transaction_id:
                                update_booking_payment_details(
                                    transaction_id,
                                    {
                                        "code": "BOOKING_FAILED_REFUND_REQUIRED",
                                        "message": "Supplier booking failed; manual refund required",
                                        "transaction_details": {
                                            "refund_status": "refund_failed",
                                            "refund_error": refund_result.get("error"),
                                            "airiq_error": processor.last_error_message,
                                            "refund_required": True,
                                        },
                                    },
                                )
                            
                            return False
                            
                    except Exception as refund_error:
                        logger.error(
                            f"Error processing Razorpay refund for booking {booking_id}: {str(refund_error)}"
                        )
                        # Mark booking as failed
                        booking.status = "failed"
                        booking.save(update_fields=["status"])
                        return False
                else:
                    # Payment method is not Razorpay or payment_id not available
                    logger.warning(
                        f"AirIQ booking failed for booking {booking_id}, but payment method ({payment_medium}) doesn't support automatic refund or payment_id missing"
                    )
                    # Mark booking as failed - manual refund required
                    booking.status = "failed"
                    booking.save(update_fields=["status"])
                    
                    transaction_id = payment_details.get("transaction_id", "")
                    if transaction_id:
                        from apps.booking.utils.db_utils import update_booking_payment_details
                        update_booking_payment_details(
                            transaction_id,
                            {
                                "code": "BOOKING_FAILED_REFUND_REQUIRED",
                                "message": "Supplier booking failed; manual refund required",
                                "transaction_details": {
                                    "airiq_error": processor.last_error_message,
                                    "refund_required": True,
                                },
                            },
                        )
                    
                    return False

            # Send notifications only on confirmed booking
            processor._send_booking_notifications()

        logger.info(
            f"Successfully processed payment success for flight booking {booking_id}"
        )
        return True

    except Exception as e:
        logger.error(
            f"Error handling payment success for booking {booking_id}: {str(e)}"
        )
        return False


def process_reschedule_phonepe_callback(callback_data: dict) -> Dict:
    """
    Process PhonePe callback for reschedule payment

    Args:
        callback_data: PhonePe callback data from request

    Returns:
        Dict with processing result
    """
    try:
        import base64
        import json as _json
        from apps.flights.services.airiq_service import airiq_service, AirIQException
        from .flight_booking_utils import process_reschedule_success

        response = callback_data.get("response")
        if not response:
            return {
                "success": False,
                "error": "Invalid callback data",
                "error_code": "INVALID_CALLBACK",
            }

        data = base64.b64decode(response)
        decoded = data.decode("utf-8")
        json_data = _json.loads(decoded)
        sub = json_data.get("data", {})
        merchant_txn = sub.get("merchantTransactionId", "")
        code = json_data.get("code", "")
        state = sub.get("state", "")
        amount = Decimal(str((sub.get("amount", 0) or 0) / 100))

        # Update payment details
        is_success = code == "PAYMENT_SUCCESS" and state == "COMPLETED"
        update_booking_payment_details(
            merchant_txn,
            {
                "code": code,
                "message": json_data.get("message", ""),
                "transaction_id": sub.get("transactionId", ""),
                "amount": float(amount),
                "is_transaction_success": is_success,
            },
        )

        booking_id = get_booking_from_payment(merchant_txn)
        booking = Booking.objects.select_related("flight_booking").get(id=booking_id)
        bpd = booking.booking_payment.filter(
            merchant_transaction_id=merchant_txn
        ).first()

        # Check if this is reschedule payment
        if bpd and bpd.transaction_details:
            metadata = bpd.transaction_details
            if metadata.get("reschedule_type") == "reschedule":
                reschedule_req = metadata.get("reschedule_request") or {}
                reschedule_resp = metadata.get("reschedule_response") or {}
                if is_success:
                    # Payment successful - NOW call AirIQ Reschedule Confirm
                    # (Payment completed first, then CONFIRM is called)
                    try:
                        flight_booking = booking.flight_booking

                        # Check if multiple PNRs need to be rescheduled
                        if metadata.get("multi_pnr") and metadata.get(
                            "reschedule_requests"
                        ):
                            # Multiple PNRs: call API for each segment
                            from .flight_booking_utils import (
                                process_multi_pnr_reschedule_confirm,
                            )

                            confirm_result = process_multi_pnr_reschedule_confirm(
                                flight_booking=flight_booking,
                                reschedule_requests=metadata["reschedule_requests"],
                                airiq_service=airiq_service,
                                flag="CONFIRM",
                            )

                            # Handle partial success
                            successful_confirmations = confirm_result.get(
                                "responses", []
                            )
                            failed_confirmations = confirm_result.get("errors", [])

                            if not successful_confirmations:
                                # All failed - mark for refund
                                update_booking_payment_details(
                                    merchant_txn,
                                    {
                                        "code": "RESCHEDULE_FAILED",
                                        "message": f"Reschedule failed for all segments: {failed_confirmations}",
                                        "is_transaction_success": False,
                                        "transaction_details": {
                                            **metadata,
                                            "airiq_errors": failed_confirmations,
                                            "refund_required": True,
                                        },
                                    },
                                )
                                return {
                                    "success": False,
                                    "error": f"Reschedule failed after payment for all segments. Please contact support for refund.",
                                    "error_code": "RESCHEDULE_FAILED",
                                    "refund_required": True,
                                }

                            # Process success for each successful confirmation
                            from .flight_booking_utils import (
                                process_reschedule_success,
                                record_reschedule_failure,
                            )

                            all_new_pnrs = flight_booking.airiq_pnrs or []
                            if not all_new_pnrs and flight_booking.airiq_pnr:
                                all_new_pnrs = [flight_booking.airiq_pnr]

                            successful_count = 0
                            for resp_item in successful_confirmations:
                                pnr_idx = resp_item.get("pnr_index")
                                old_pnr = resp_item.get(
                                    "old_airiq_pnr"
                                ) or resp_item.get("airiq_pnr")
                                airiq_resp = resp_item.get("response", {})
                                new_pnr = airiq_resp.get("New_PNR", "")

                                if new_pnr and pnr_idx is not None:
                                    if pnr_idx < len(all_new_pnrs):
                                        all_new_pnrs[pnr_idx] = new_pnr

                                    remarks = (
                                        metadata.get("reschedule_requests", [{}])[
                                            0
                                        ].get("remarks", "")
                                        if metadata.get("reschedule_requests")
                                        else ""
                                    )
                                    process_reschedule_success(
                                        booking,
                                        flight_booking,
                                        airiq_resp,
                                        remarks,
                                        pnr_index=pnr_idx,
                                        old_airiq_pnr=old_pnr,
                                    )
                                    successful_count += 1

                            # Record failures
                            for err_item in failed_confirmations:
                                pnr_idx = err_item.get("pnr_index")
                                old_pnr = err_item.get("airiq_pnr")
                                error_msg = err_item.get("error", "Unknown error")
                                if pnr_idx is not None and old_pnr:
                                    record_reschedule_failure(
                                        flight_booking,
                                        old_pnr,
                                        error_msg,
                                        pnr_index=pnr_idx,
                                    )

                            # Update PNRs
                            if all_new_pnrs:
                                flight_booking.airiq_pnrs = all_new_pnrs
                                flight_booking.save(update_fields=["airiq_pnrs"])

                            # Mark for partial refund if some failed
                            if failed_confirmations:
                                update_booking_payment_details(
                                    merchant_txn,
                                    {
                                        "code": "PARTIAL_RESCHEDULE_SUCCESS",
                                        "message": f"Reschedule successful for {successful_count} of {len(successful_confirmations) + len(failed_confirmations)} segments",
                                        "is_transaction_success": True,
                                        "transaction_details": {
                                            **metadata,
                                            "successful_segments": successful_count,
                                            "failed_segments": len(
                                                failed_confirmations
                                            ),
                                            "failed_details": failed_confirmations,
                                            "partial_refund_required": True,
                                        },
                                    },
                                )

                            return {
                                "success": True,
                                "payment_success": True,
                                "reschedule_processed": True,
                                "successful_segments": successful_count,
                                "failed_segments": len(failed_confirmations),
                                "partial_success": len(failed_confirmations) > 0,
                                "message": f"Reschedule successful for {successful_count} of {len(successful_confirmations) + len(failed_confirmations)} segments",
                            }
                        else:
                            # Single PNR case
                            airiq_resp = airiq_service.reschedule_booking(
                                airiq_pnr=reschedule_req.get("airiq_pnr"),
                                track_id=reschedule_req.get("track_id"),
                                flight_details=reschedule_req.get("flight_details"),
                                contact_no=reschedule_req.get("contact_no"),
                                remarks=reschedule_req.get("remarks", ""),
                                flag="CONFIRM",
                            )
                            # Process success
                            result = process_reschedule_success(
                                booking,
                                flight_booking,
                                airiq_resp,
                                reschedule_req.get("remarks", ""),
                            )
                            return {
                                "success": True,
                                "payment_success": True,
                                "reschedule_processed": True,
                                **result,
                            }
                    except AirIQException as e:
                        # AirIQ failed - mark for refund
                        update_booking_payment_details(
                            merchant_txn,
                            {
                                "code": "RESCHEDULE_FAILED",
                                "message": f"Reschedule failed: {str(e)}",
                                "is_transaction_success": False,
                                "transaction_details": {
                                    **metadata,
                                    "airiq_error": str(e),
                                    "refund_required": True,
                                },
                            },
                        )
                        return {
                            "success": False,
                            "error": f"Reschedule failed after payment: {str(e)}. Please contact support for refund.",
                            "error_code": "RESCHEDULE_FAILED",
                            "refund_required": True,
                        }
                    except Exception as e:
                        update_booking_payment_details(
                            merchant_txn,
                            {
                                "code": "RESCHEDULE_ERROR",
                                "message": f"Unexpected error: {str(e)}",
                                "is_transaction_success": False,
                            },
                        )
                        return {
                            "success": False,
                            "error": f"Unexpected error processing reschedule: {str(e)}",
                            "error_code": "RESCHEDULE_ERROR",
                        }
                else:
                    # Payment failed
                    return {
                        "success": True,
                        "payment_success": False,
                        "message": "Payment failed",
                    }

        return {
            "success": True,
            "payment_success": is_success,
            "message": "Callback processed",
        }
    except Exception as e:
        logger.error(f"Reschedule PhonePe callback error: {str(e)}")
        return {
            "success": False,
            "error": f"Callback processing failed: {str(e)}",
            "error_code": "CALLBACK_ERROR",
        }


def process_ticket_issuance_phonepe_callback(callback_data: dict) -> Dict:
    """
    Process PhonePe callback for ticket issuance payment

    Args:
        callback_data: PhonePe callback data from request

    Returns:
        Dict with processing result
    """
    # Use print for immediate visibility
    print("=" * 80)
    print("=== process_ticket_issuance_phonepe_callback CALLED ===")
    print(f"Callback data type: {type(callback_data)}")
    print(f"Callback data: {callback_data}")
    print("=" * 80)

    try:
        import base64
        import json as _json
        from apps.flights.services.airiq_service import airiq_service, AirIQException
        from django.utils import timezone

        logger.info("=== Ticket Issuance PhonePe Callback Started ===")
        logger.info(f"Callback data received: {callback_data}")
        print("=== Ticket Issuance PhonePe Callback Started ===")
        print(f"Callback data received: {callback_data}")

        response = callback_data.get("response")
        if not response:
            logger.error("No response data in callback")
            return {
                "success": False,
                "error": "Invalid callback data",
                "error_code": "INVALID_CALLBACK",
            }

        data = base64.b64decode(response)
        decoded = data.decode("utf-8")
        json_data = _json.loads(decoded)
        sub = json_data.get("data", {})
        merchant_txn = sub.get("merchantTransactionId", "")
        code = json_data.get("code", "")
        state = sub.get("state", "")
        amount = Decimal(str((sub.get("amount", 0) or 0) / 100))

        logger.info(f"Merchant Transaction ID: {merchant_txn}")
        logger.info(f"Payment Code: {code}, State: {state}, Amount: {amount}")

        # Update payment details
        is_success = code == "PAYMENT_SUCCESS" and state == "COMPLETED"
        update_booking_payment_details(
            merchant_txn,
            {
                "code": code,
                "message": json_data.get("message", ""),
                "transaction_id": sub.get("transactionId", ""),
                "amount": float(amount),
                "is_transaction_success": is_success,
            },
        )

        booking_id = get_booking_from_payment(merchant_txn)
        logger.info(f"Booking ID from payment: {booking_id}")
        print(f"Booking ID from payment: {booking_id}")

        # Refresh booking from database to get latest data
        booking = Booking.objects.select_related("flight_booking").get(id=booking_id)
        booking.refresh_from_db()
        flight_booking = booking.flight_booking

        if not flight_booking:
            logger.error(f"Flight booking not found for booking {booking_id}")
            print(f"ERROR: Flight booking not found for booking {booking_id}")
            return {
                "success": False,
                "error": "Flight booking not found",
                "error_code": "BOOKING_NOT_FOUND",
            }

        # Refresh flight_booking to get latest data
        flight_booking.refresh_from_db()

        # Verify this is a ticket issuance payment by checking transaction_details
        payment_detail = BookingPaymentDetail.objects.filter(
            merchant_transaction_id=merchant_txn
        ).first()
        if payment_detail and payment_detail.transaction_details:
            transaction_type = payment_detail.transaction_details.get(
                "transaction_type"
            )
            logger.info(f"Transaction type from payment detail: {transaction_type}")
            print(f"Transaction type from payment detail: {transaction_type}")
            if transaction_type != "ticket_issuance_payment":
                logger.warning(
                    f"Payment {merchant_txn} is not a ticket issuance payment (type: {transaction_type})"
                )
                return {
                    "success": False,
                    "error": f"This callback is not for ticket issuance payment. Transaction type: {transaction_type}",
                    "error_code": "INVALID_TRANSACTION_TYPE",
                }
        else:
            logger.warning(
                f"Could not find payment detail or transaction_details for {merchant_txn}"
            )
            print(
                f"WARNING: Could not find payment detail or transaction_details for {merchant_txn}"
            )

        # Log current flight booking status and PNR data
        logger.info(f"Flight booking status: {flight_booking.status}")
        logger.info(
            f"Flight booking PNR data - track_id: {flight_booking.airiq_track_id}, airiq_pnr: {flight_booking.airiq_pnr}, airline_pnr: {flight_booking.airline_pnr}"
        )
        print(f"Flight booking status: {flight_booking.status}")
        print(f"Flight booking PNR data:")
        print(f"  - track_id: {flight_booking.airiq_track_id}")
        print(f"  - airiq_pnr: {flight_booking.airiq_pnr}")
        print(f"  - airline_pnr: {flight_booking.airline_pnr}")
        print(f"  - airiq_pnrs (array): {flight_booking.airiq_pnrs}")
        print(f"  - airline_pnrs (array): {flight_booking.airline_pnrs}")

        if not flight_booking:
            return {
                "success": False,
                "error": "Flight booking not found",
                "error_code": "BOOKING_NOT_FOUND",
            }

        if is_success:
            logger.info(
                f"Payment successful for booking {booking_id}. Proceeding to ticket issuance..."
            )

            # Update booking total payment made (similar to wallet payment flow)
            booking.total_payment_made = (
                booking.total_payment_made or Decimal("0")
            ) + amount
            booking.save(update_fields=["total_payment_made"])
            logger.info(
                f"Updated booking total_payment_made to {booking.total_payment_made}"
            )

            # Payment successful - proceed directly to ticket issuance
            # For HELD bookings, we don't need to call Book API again
            # We'll directly call IssueTicket API after payment
            try:
                # Check if already ticketed
                if flight_booking.status == "TICKETED":
                    logger.info(
                        f"Booking {booking_id} is already ticketed. Skipping ticket issuance."
                    )
                    return {
                        "success": True,
                        "payment_success": True,
                        "ticket_issued": True,
                        "message": "Payment successful. Ticket already issued.",
                        "booking_id": booking_id,
                    }

                # Get PNRs and track IDs - support both single fields and arrays (same logic as issue_ticket endpoint)
                airiq_pnr = flight_booking.airiq_pnr
                airline_pnr = flight_booking.airline_pnr
                airiq_track_id = flight_booking.airiq_track_id

                # Fallback to arrays if single fields are empty (same as issue_ticket endpoint)
                if not airiq_pnr:
                    airiq_pnrs_list = flight_booking.airiq_pnrs or []
                    if airiq_pnrs_list:
                        airiq_pnr = (
                            airiq_pnrs_list[0]
                            if isinstance(airiq_pnrs_list, list)
                            else str(airiq_pnrs_list)
                        )
                        logger.info(f"Using airiq_pnr from array: {airiq_pnr}")
                        print(f"Using airiq_pnr from array: {airiq_pnr}")

                if not airline_pnr:
                    airline_pnrs_list = flight_booking.airline_pnrs or []
                    if airline_pnrs_list:
                        airline_pnr = (
                            airline_pnrs_list[0]
                            if isinstance(airline_pnrs_list, list)
                            else str(airline_pnrs_list)
                        )
                        logger.info(f"Using airline_pnr from array: {airline_pnr}")
                        print(f"Using airline_pnr from array: {airline_pnr}")

                if not airiq_track_id:
                    airiq_track_ids_list = flight_booking.airiq_track_ids or []
                    if airiq_track_ids_list:
                        airiq_track_id = (
                            airiq_track_ids_list[0]
                            if isinstance(airiq_track_ids_list, list)
                            else str(airiq_track_ids_list)
                        )
                        logger.info(
                            f"Using airiq_track_id from array: {airiq_track_id}"
                        )
                        print(f"Using airiq_track_id from array: {airiq_track_id}")

                # Check if we have all required PNR data
                if not all([airiq_track_id, airiq_pnr, airline_pnr]):
                    logger.error(
                        f"Missing PNR data for booking {booking_id}: track_id={airiq_track_id}, airiq_pnr={airiq_pnr}, airline_pnr={airline_pnr}"
                    )
                    print(f"ERROR: Missing PNR data for booking {booking_id}")
                    print(f"  track_id: {airiq_track_id}")
                    print(f"  airiq_pnr: {airiq_pnr}")
                    print(f"  airline_pnr: {airline_pnr}")
                    return {
                        "success": False,
                        "error": f"Missing required PNR or track ID for ticket issuance. track_id={airiq_track_id}, airiq_pnr={airiq_pnr}, airline_pnr={airline_pnr}",
                        "error_code": "MISSING_PNR_DATA",
                    }

                logger.info(f"Calling AirIQ issue_ticket API for booking {booking_id}")
                logger.info(
                    f"Track ID: {airiq_track_id}, AirIQ PNR: {airiq_pnr}, Airline PNR: {airline_pnr}"
                )
                print(f"Calling AirIQ issue_ticket API for booking {booking_id}")
                print(
                    f"Track ID: {airiq_track_id}, AirIQ PNR: {airiq_pnr}, Airline PNR: {airline_pnr}"
                )

                ticket_response = airiq_service.issue_ticket(
                    booking_track_id=airiq_track_id,
                    airiq_pnr=airiq_pnr,
                    airline_pnr=airline_pnr,
                    booking_amount=float(booking.final_amount),
                    payment_mode="T",  # Always use "T" for Agent Deposit
                )

                logger.info(
                    f"AirIQ issue_ticket API response received for booking {booking_id}"
                )

                # Save ticket response using FlightPaymentProcessor
                processor = FlightPaymentProcessor(booking, booking.user, {})
                processor.flight_booking = flight_booking

                # Use the existing method to update from AirIQ response
                processor._update_flight_booking_from_airiq_response(ticket_response)

                # Update status to TICKETED
                flight_booking.status = "TICKETED"
                flight_booking.ticketed_at = timezone.now()

                # Persist ticket response in airiq_response_data
                blob = flight_booking.airiq_response_data or {}
                blob["ticket_response"] = ticket_response
                flight_booking.airiq_response_data = blob

                # Save all updates
                flight_booking.save()
                logger.info(
                    f"Flight booking {flight_booking.id} status updated to TICKETED"
                )

                # Update main booking status
                booking.status = "confirmed"
                booking.save()
                logger.info(f"Booking {booking_id} status updated to confirmed")

                logger.info(
                    f"=== Ticket Issuance PhonePe Callback Completed Successfully for booking {booking_id} ==="
                )

                return {
                    "success": True,
                    "payment_success": True,
                    "ticket_issued": True,
                    "ticket_response": ticket_response,
                    "booking_id": booking_id,
                    "message": "Payment successful and ticket issued",
                }

            except AirIQException as e:
                logger.error(
                    f"AirIQ error during ticket issuance callback for booking {booking_id}: {str(e)}"
                )
                import traceback

                logger.error(traceback.format_exc())
                return {
                    "success": False,
                    "error": f"Ticket issuance failed: {str(e)}",
                    "error_code": "TICKET_ISSUANCE_FAILED",
                    "payment_success": True,  # Payment was successful
                }
            except Exception as e:
                logger.error(
                    f"Error during ticket issuance callback for booking {booking_id}: {str(e)}"
                )
                import traceback

                logger.error(traceback.format_exc())
                return {
                    "success": False,
                    "error": f"Unexpected error: {str(e)}",
                    "error_code": "TICKET_ISSUANCE_ERROR",
                    "payment_success": True,
                }
        else:
            # Payment failed
            logger.warning(
                f"Payment failed for booking {booking_id}. Code: {code}, State: {state}"
            )
            return {
                "success": True,
                "payment_success": False,
                "message": "Payment failed",
            }

    except Exception as e:
        logger.error(f"Ticket issuance PhonePe callback error: {str(e)}")
        import traceback

        logger.error(traceback.format_exc())
        return {
            "success": False,
            "error": f"Callback processing failed: {str(e)}",
            "error_code": "CALLBACK_ERROR",
        }


def process_ssr_phonepe_callback(callback_data: dict) -> Dict:
    """
    Process PhonePe callback for SSR (ancillary services) payment

    Args:
        callback_data: PhonePe callback data from request

    Returns:
        Dict with processing result
    """
    try:
        import base64
        import json as _json
        from apps.flights.services.airiq_service import airiq_service, AirIQException
        from .flight_booking_utils import process_ssr_success

        response = callback_data.get("response")
        if not response:
            return {
                "success": False,
                "error": "Invalid callback data",
                "error_code": "INVALID_CALLBACK",
            }

        data = base64.b64decode(response)
        decoded = data.decode("utf-8")
        json_data = _json.loads(decoded)
        sub = json_data.get("data", {})
        merchant_txn = sub.get("merchantTransactionId", "")
        code = json_data.get("code", "")
        state = sub.get("state", "")
        amount = Decimal(str((sub.get("amount", 0) or 0) / 100))

        # Update payment details
        is_success = code == "PAYMENT_SUCCESS" and state == "COMPLETED"
        update_booking_payment_details(
            merchant_txn,
            {
                "code": code,
                "message": json_data.get("message", ""),
                "transaction_id": sub.get("transactionId", ""),
                "amount": float(amount),
                "is_transaction_success": is_success,
            },
        )

        booking_id = get_booking_from_payment(merchant_txn)
        booking = Booking.objects.select_related("flight_booking").get(id=booking_id)
        bpd = booking.booking_payment.filter(
            merchant_transaction_id=merchant_txn
        ).first()

        # Check if this is SSR payment
        if bpd and bpd.transaction_details:
            metadata = bpd.transaction_details
            if metadata.get("ssr_type") == "ancillary_services":
                anc = metadata.get("ancillary_request") or {}
                if is_success:
                    # Payment successful - call AirIQ AddSSR
                    try:
                        flight_booking = booking.flight_booking
                        airiq_resp = airiq_service.add_ssr_services(
                            airiq_pnr=anc.get("AirIqPNR") or flight_booking.airiq_pnr,
                            airline_pnr=anc.get("AirlinePNR")
                            or flight_booking.airline_pnr,
                            track_id=anc.get("TracKID")
                            or flight_booking.airiq_track_id,
                            meals_ssr=anc.get("MealsSSR") or [],
                            baggage_ssr=anc.get("BaggSSR") or [],
                            seats_ssr=anc.get("SeatsSSR") or [],
                            other_ssr=anc.get("OtherSSR") or [],
                            payment_amount=float(amount),
                            remarks=anc.get("Remarks") or "",
                        )
                        # Process success
                        result = process_ssr_success(
                            booking,
                            flight_booking,
                            airiq_resp,
                            anc.get("MealsSSR") or [],
                            anc.get("BaggSSR") or [],
                            anc.get("SeatsSSR") or [],
                            anc.get("OtherSSR") or [],
                            amount,
                        )
                        return {
                            "success": True,
                            "payment_success": True,
                            "ssr_processed": True,
                            **result,
                        }
                    except AirIQException as e:
                        # AirIQ failed - mark for refund
                        update_booking_payment_details(
                            merchant_txn,
                            {
                                "code": "SSR_FAILED",
                                "message": f"AddSSR failed: {str(e)}",
                                "is_transaction_success": False,
                                "transaction_details": {
                                    **metadata,
                                    "airiq_error": str(e),
                                    "refund_required": True,
                                },
                            },
                        )
                        return {
                            "success": False,
                            "error": f"AddSSR failed after payment: {str(e)}. Please contact support for refund.",
                            "error_code": "SSR_FAILED",
                            "refund_required": True,
                        }
                    except Exception as e:
                        update_booking_payment_details(
                            merchant_txn,
                            {
                                "code": "SSR_ERROR",
                                "message": f"Unexpected error: {str(e)}",
                                "is_transaction_success": False,
                            },
                        )
                        return {
                            "success": False,
                            "error": f"Unexpected error processing SSR: {str(e)}",
                            "error_code": "SSR_ERROR",
                        }
                else:
                    # Payment failed
                    return {
                        "success": True,
                        "payment_success": False,
                        "message": "Payment failed",
                    }

        return {
            "success": True,
            "payment_success": is_success,
            "message": "Callback processed",
        }
    except Exception as e:
        logger.error(f"SSR PhonePe callback error: {str(e)}")
        return {
            "success": False,
            "error": f"Callback processing failed: {str(e)}",
            "error_code": "CALLBACK_ERROR",
        }


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

            response = callback_data.get("response")
            if not response:
                return {
                    "success": False,
                    "error": "Invalid callback data",
                    "error_code": "INVALID_CALLBACK",
                }

            # Decode base64 response
            data = base64.b64decode(response)
            decoded_data = data.decode("utf-8")
            json_data = json.loads(decoded_data)

            # Extract transaction details
            code = json_data.get("code", "")
            message = json_data.get("message", "")
            sub_json_data = json_data.get("data", {})

            amount = sub_json_data.get("amount", 0) / 100
            merchant_transaction_id = sub_json_data.get("merchantTransactionId", "")
            transaction_id = sub_json_data.get("transactionId", "")
            state = sub_json_data.get("state", "")

            # Get booking from payment details
            booking_id = get_booking_from_payment(merchant_transaction_id)
            booking = Booking.objects.get(id=booking_id)

            # Update payment details
            booking_payment_details = {
                "transaction_id": transaction_id,
                "code": code,
                "message": message,
                "amount": amount,
                "transaction_details": sub_json_data,
                "is_transaction_success": code == "PAYMENT_SUCCESS"
                and state == "COMPLETED",
            }

            update_booking_payment_details(
                merchant_transaction_id, booking_payment_details
            )

            # If payment successful, confirm booking
            if booking_payment_details["is_transaction_success"]:
                processor = FlightPaymentProcessor(booking, booking.user, {})
                processor._confirm_flight_booking()
                processor._send_booking_notifications()

                # Send payment success SMS
                send_booking_sms_task.delay(
                    notification_type="PAYMENT_PROCEED_INFO",
                    params={
                        "booking_id": booking.id,
                        "amount": amount,
                        "payment_purpose": "Flight Booking",
                        "transaction_id": transaction_id,
                    },
                )
            else:
                # Send payment failure SMS - use flight-specific template
                send_booking_sms_task.delay(
                    notification_type="FLIGHT_BOOKING_FAILED",
                    params={
                        "booking_id": booking.id,
                        "failure_reason": "payment gateway error",
                        "refund_amount": amount,
                    },
                )

            return {
                "success": True,
                "payment_success": booking_payment_details["is_transaction_success"],
                "booking_id": booking.id,
                "transaction_id": transaction_id,
                "amount": amount,
            }

        except Exception as e:
            logger.error(f"PhonePe callback processing error: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "error_code": "CALLBACK_PROCESSING_ERROR",
            }

    @staticmethod
    def process_payu_callback(callback_data: dict, is_success: bool) -> Dict:
        """Process PayU payment callback"""

        try:
            # Extract PayU callback data
            txnid = callback_data.get("txnid", "")
            amount = float(callback_data.get("amount", 0))
            status_msg = callback_data.get("status", "")

            # Get booking from payment details
            booking_id = get_booking_from_payment(txnid)
            booking = Booking.objects.get(id=booking_id)

            # Update payment details
            booking_payment_details = {
                "transaction_id": callback_data.get("mihpayid", ""),
                "code": status_msg,
                "message": callback_data.get("error_Message", ""),
                "amount": amount,
                "transaction_details": callback_data,
                "is_transaction_success": is_success,
            }

            update_booking_payment_details(txnid, booking_payment_details)

            # Process based on success/failure
            if is_success:
                processor = FlightPaymentProcessor(booking, booking.user, {})
                processor._confirm_flight_booking()
                processor._send_booking_notifications()

            return {
                "success": True,
                "payment_success": is_success,
                "booking_id": booking.id,
                "transaction_id": callback_data.get("mihpayid", ""),
                "amount": amount,
            }

        except Exception as e:
            logger.error(f"PayU callback processing error: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "error_code": "CALLBACK_PROCESSING_ERROR",
            }


def validate_flight_booking_for_payment(booking: Booking) -> Tuple[bool, str]:
    """Validate if flight booking is ready for payment"""

    if not booking:
        return False, "Booking not found"

    if booking.booking_type != "FLIGHT":
        return False, "Not a flight booking"

    if not booking.flight_booking:
        return False, "Flight booking details not found"

    if booking.status in ["confirmed", "canceled"]:
        return False, f"Booking is already {booking.status}"

    if booking.flight_booking.status == "CANCELLED":
        return False, "Flight booking is cancelled"

    return True, "Valid for payment"


def get_flight_payment_methods(user=None) -> list:
    """Get available payment methods for flight bookings"""

    payment_methods = [
        {"code": "PHONE PAY", "name": "PhonePe", "type": "gateway", "enabled": True},
        {"code": "PAYU", "name": "PayU", "type": "gateway", "enabled": True},
        {"code": "RAZORPAY", "name": "Razorpay", "type": "gateway", "enabled": True},
    ]

    # Add wallet option if user has sufficient balance
    if user and user.is_authenticated:
        try:
            from apps.customer.utils.db_utils import (
                get_wallet_balance,
                get_company_wallet_balance,
            )

            balance = 0
            if hasattr(user, "company_id") and user.company_id:
                balance = get_company_wallet_balance(user.company_id)
            else:
                balance = get_wallet_balance(user.id)

            payment_methods.append(
                {
                    "code": "WALLET",
                    "name": "Wallet",
                    "type": "wallet",
                    "enabled": balance > 0,
                    "balance": float(balance),
                }
            )
        except Exception as e:
            logger.error(f"Error getting wallet balance: {str(e)}")

    return payment_methods


def handle_reschedule_wallet_payment(
    booking: Booking,
    flight_booking: FlightBooking,
    user,
    reschedule_request: dict,
    reschedule_response: dict,
    payment_amount: Decimal,
    request=None,
) -> Dict:
    """Handle wallet payment for reschedule: deduct -> call AirIQ -> update or refund"""
    try:
        from apps.booking.utils.booking_utils import (
            check_wallet_balance_for_booking,
            deduct_booking_amount,
            refund_wallet_payment,
        )
        from apps.booking.utils.db_utils import (
            create_booking_payment_details,
            update_booking_payment_details,
        )
        from apps.flights.services.airiq_service import airiq_service, AirIQException
        from .flight_booking_utils import process_reschedule_success

        company_id = None
        if user:
            user_default_group = getattr(user, "default_group", "") or ""
            if user_default_group in ("CORP-ADMIN", "CORP-EMP", "CORPORATE-GRP"):
                company_id = getattr(user, "company_id", None)

        # Check wallet balance
        can_pay, balance_info = check_wallet_balance_for_booking(
            booking, user, company_id=company_id
        )
        if not can_pay:
            return {
                "success": False,
                "error": "Insufficient wallet balance",
                "error_code": "INSUFFICIENT_WALLET_BALANCE",
            }

        # Create payment detail record
        append_id = f"RS{user.id}" if user else "RSGUEST"
        payment_detail = create_booking_payment_details(booking.id, append_id)
        payment_detail.amount = float(payment_amount)
        payment_detail.transaction_for = "others"
        payment_detail.transaction_details = {
            "reschedule_type": "reschedule",
            "reschedule_request": reschedule_request,
            "reschedule_response": reschedule_response,
        }
        payment_detail.save()

        # Step 1: Deduct from wallet FIRST (payment must complete before CONFIRM)
        deduct_success = deduct_booking_amount(
            booking, company_id=company_id, request=request
        )
        if not deduct_success:
            return {
                "success": False,
                "error": "Wallet deduction failed",
                "error_code": "WALLET_DEDUCTION_FAILED",
            }

        # Step 2: Update payment detail as paid (payment completed)
        update_booking_payment_details(
            payment_detail.merchant_transaction_id,
            {
                "code": "PAYMENT_SUCCESS",
                "message": "Payment successful via wallet",
                "payment_type": "WALLET",
                "payment_medium": "Idbook",
                "is_transaction_success": True,
                "transaction_id": payment_detail.merchant_transaction_id,
            },
        )

        # Step 3: NOW call AirIQ Reschedule Confirm (only after payment is successful)
        try:
            # Check if multiple PNRs need to be rescheduled
            if reschedule_request.get("multi_pnr") and reschedule_request.get(
                "reschedule_requests"
            ):
                # Multiple PNRs: call API for each segment
                from .flight_booking_utils import process_multi_pnr_reschedule_confirm

                confirm_result = process_multi_pnr_reschedule_confirm(
                    flight_booking=flight_booking,
                    reschedule_requests=reschedule_request["reschedule_requests"],
                    airiq_service=airiq_service,
                    flag="CONFIRM",
                )

                # Handle partial success
                successful_confirmations = confirm_result.get("responses", [])
                failed_confirmations = confirm_result.get("errors", [])

                if not successful_confirmations:
                    # All failed - refund wallet
                    refund_details = {
                        "reason": f"AirIQ reschedule failed for all segments: {failed_confirmations}",
                        "timestamp": timezone.now().isoformat(),
                        "airiq_errors": failed_confirmations,
                    }
                    refund_ok, refund_status, refund_data = refund_wallet_payment(
                        booking, payment_amount, refund_details
                    )

                    update_booking_payment_details(
                        payment_detail.merchant_transaction_id,
                        {
                            "code": "RESCHEDULE_FAILED_REFUNDED",
                            "message": f"Reschedule failed for all segments; wallet refunded",
                            "is_transaction_success": False,
                            "transaction_details": {
                                "refund_status": refund_status,
                                "refund_data": refund_data,
                                "airiq_errors": failed_confirmations,
                            },
                        },
                    )

                    return {
                        "success": False,
                        "error": f"Reschedule failed for all segments; wallet refunded",
                        "error_code": "AIRIQ_RESCHEDULE_FAILED",
                        "refund_status": refund_status,
                    }

                # Process success for each successful confirmation
                from .flight_booking_utils import (
                    process_reschedule_success,
                    record_reschedule_failure,
                )

                all_new_pnrs = flight_booking.airiq_pnrs or []
                if not all_new_pnrs and flight_booking.airiq_pnr:
                    all_new_pnrs = [flight_booking.airiq_pnr]

                successful_count = 0
                for resp_item in successful_confirmations:
                    pnr_idx = resp_item.get("pnr_index")
                    old_pnr = resp_item.get("old_airiq_pnr") or resp_item.get(
                        "airiq_pnr"
                    )
                    airiq_resp = resp_item.get("response", {})
                    new_pnr = airiq_resp.get("New_PNR", "")

                    if new_pnr and pnr_idx is not None:
                        if pnr_idx < len(all_new_pnrs):
                            all_new_pnrs[pnr_idx] = new_pnr

                        process_reschedule_success(
                            booking,
                            flight_booking,
                            airiq_resp,
                            reschedule_request.get("remarks", ""),
                            pnr_index=pnr_idx,
                            old_airiq_pnr=old_pnr,
                        )
                        successful_count += 1

                # Record failures
                for err_item in failed_confirmations:
                    pnr_idx = err_item.get("pnr_index")
                    old_pnr = err_item.get("airiq_pnr")
                    error_msg = err_item.get("error", "Unknown error")
                    if pnr_idx is not None and old_pnr:
                        record_reschedule_failure(
                            flight_booking, old_pnr, error_msg, pnr_index=pnr_idx
                        )

                # Update PNRs
                if all_new_pnrs:
                    flight_booking.airiq_pnrs = all_new_pnrs
                    flight_booking.save(update_fields=["airiq_pnrs"])

                # Calculate partial refund if some failed
                partial_refund_amount = Decimal("0")
                if failed_confirmations:
                    # Calculate refund for failed segments (proportional)
                    total_segments = len(successful_confirmations) + len(
                        failed_confirmations
                    )
                    if total_segments > 0:
                        failed_ratio = Decimal(
                            str(len(failed_confirmations))
                        ) / Decimal(str(total_segments))
                        partial_refund_amount = payment_amount * failed_ratio

                        if partial_refund_amount > 0:
                            refund_details = {
                                "reason": f"Partial reschedule failure: {len(failed_confirmations)} of {total_segments} segments failed",
                                "timestamp": timezone.now().isoformat(),
                                "failed_segments": failed_confirmations,
                            }
                            refund_ok, refund_status, refund_data = (
                                refund_wallet_payment(
                                    booking, partial_refund_amount, refund_details
                                )
                            )

                return {
                    "success": True,
                    "payment_method": "wallet",
                    "transaction_id": payment_detail.merchant_transaction_id,
                    "message": f"Reschedule successful via wallet for {successful_count} of {len(successful_confirmations) + len(failed_confirmations)} segments",
                    "successful_segments": successful_count,
                    "failed_segments": len(failed_confirmations),
                    "partial_refund": (
                        float(partial_refund_amount) if partial_refund_amount > 0 else 0
                    ),
                    "partial_success": len(failed_confirmations) > 0,
                }
            else:
                # Single PNR case
                airiq_resp = airiq_service.reschedule_booking(
                    airiq_pnr=reschedule_request.get("airiq_pnr"),
                    track_id=reschedule_request.get("track_id"),
                    flight_details=reschedule_request.get("flight_details"),
                    contact_no=reschedule_request.get("contact_no"),
                    remarks=reschedule_request.get("remarks", ""),
                    flag="CONFIRM",
                )

                # Process success
                result = process_reschedule_success(
                    booking,
                    flight_booking,
                    airiq_resp,
                    reschedule_request.get("remarks", ""),
                )
                return {
                    "success": True,
                    "payment_method": "wallet",
                    "transaction_id": payment_detail.merchant_transaction_id,
                    "message": "Reschedule successful via wallet",
                    **result,
                }

        except AirIQException as e:
            # AirIQ failed - refund wallet
            refund_details = {
                "reason": f"AirIQ reschedule failed: {str(e)}",
                "timestamp": timezone.now().isoformat(),
                "airiq_error": str(e),
            }
            refund_ok, refund_status, refund_data = refund_wallet_payment(
                booking, payment_amount, refund_details
            )

            update_booking_payment_details(
                payment_detail.merchant_transaction_id,
                {
                    "code": "RESCHEDULE_FAILED_REFUNDED",
                    "message": f"Reschedule failed; wallet refunded: {str(e)}",
                    "is_transaction_success": False,
                    "transaction_details": {
                        "refund_status": refund_status,
                        "refund_data": refund_data,
                        "airiq_error": str(e),
                    },
                },
            )

            return {
                "success": False,
                "error": f"Reschedule failed; wallet refunded: {str(e)}",
                "error_code": "AIRIQ_RESCHEDULE_FAILED",
                "refund_status": refund_status,
            }
        except Exception as e:
            # Unexpected error - refund wallet
            refund_details = {
                "reason": f"Unexpected error: {str(e)}",
                "timestamp": timezone.now().isoformat(),
            }
            refund_ok, refund_status, refund_data = refund_wallet_payment(
                booking, payment_amount, refund_details
            )

            update_booking_payment_details(
                payment_detail.merchant_transaction_id,
                {
                    "code": "RESCHEDULE_ERROR_REFUNDED",
                    "message": f"Unexpected error; wallet refunded: {str(e)}",
                    "is_transaction_success": False,
                },
            )

            return {
                "success": False,
                "error": f"Unexpected error; wallet refunded: {str(e)}",
                "error_code": "RESCHEDULE_ERROR",
            }
    except Exception as e:
        logger.error(f"Reschedule wallet payment error: {str(e)}")
        return {
            "success": False,
            "error": f"Wallet payment processing failed: {str(e)}",
            "error_code": "WALLET_PAYMENT_ERROR",
        }


def handle_reschedule_phonepe_payment(
    booking: Booking,
    flight_booking: FlightBooking,
    user,
    reschedule_request: dict,
    reschedule_response: dict,
    payment_amount: Decimal,
    request=None,
) -> Dict:
    """Handle PhonePe payment for reschedule: save request data -> initiate payment -> handle in callback"""
    try:
        from apps.booking.utils.db_utils import (
            create_booking_payment_details,
            update_booking_payment_details,
        )
        from apps.payment_gateways.mixins.phonepay_mixins import PhonePayMixin
        from django.conf import settings

        # Create payment detail record
        append_id = f"RS{user.id}" if user else "RSGUEST"
        payment_detail = create_booking_payment_details(booking.id, append_id)
        payment_detail.amount = float(payment_amount)
        payment_detail.transaction_for = "others"

        # Save reschedule request data (support both single and multi-PNR)
        transaction_details = {
            "reschedule_type": "reschedule",
            "reschedule_response": reschedule_response,
        }

        # If multi-PNR, save the full structure; otherwise save single request
        if reschedule_request.get("multi_pnr"):
            transaction_details["multi_pnr"] = True
            transaction_details["reschedule_requests"] = reschedule_request.get(
                "reschedule_requests", []
            )
        else:
            transaction_details["reschedule_request"] = reschedule_request

        payment_detail.transaction_details = transaction_details
        payment_detail.save()

        # Initiate PhonePe payment
        phonepe = PhonePayMixin()
        payload = {
            "merchantId": settings.MERCHANT_ID,
            "merchantTransactionId": payment_detail.merchant_transaction_id,
            "merchantUserId": (
                str(user.id) if user and user.is_authenticated else "guest"
            ),
            "amount": int(payment_amount * 100),
            "redirectUrl": (request.data.get("redirect_url") if request else None)
            or getattr(settings, "FRONTEND_URL", ""),
            "redirectMode": "REDIRECT",
            "callbackUrl": f"{settings.CALLBACK_URL.rstrip('/')}/api/v1/booking/flight-bookings/reschedule/phonepe-callback/",
            "paymentInstrument": {"type": "PAY_PAGE"},
        }

        req, headers = phonepe.get_encrypted_header_and_payload(payload)
        resp = phonepe.post_pay_page(req, headers)

        if resp.status_code != 200:
            return {
                "success": False,
                "error": "Failed to initiate PhonePe payment",
                "error_code": "PHONEPE_INITIATION_FAILED",
            }

        data_json = resp.json()
        pay_url = (
            data_json.get("data", {})
            .get("instrumentResponse", {})
            .get("redirectInfo", {})
            .get("url", "")
        )

        update_booking_payment_details(
            payment_detail.merchant_transaction_id,
            {
                "code": "PAYMENT_INITIATED",
                "message": "Payment initiated via PhonePe",
                "payment_type": "PAYMENT GATEWAY",
                "payment_medium": "PHONE PAY",
            },
        )

        return {
            "success": True,
            "payment_method": "phonepe",
            "payment_url": pay_url,
            "transaction_id": payment_detail.merchant_transaction_id,
            "message": "Reschedule payment initiated",
        }
    except Exception as e:
        logger.error(f"Reschedule PhonePe payment initiation error: {str(e)}")
        return {
            "success": False,
            "error": f"Failed to initiate PhonePe payment: {str(e)}",
            "error_code": "PHONEPE_INITIATION_ERROR",
        }


def process_ssr_payment(
    booking: Booking,
    user,
    payment_data: dict,
    ssr_amount: Decimal,
    ssr_details: dict = None,
    request=None,
) -> Dict:
    """Process payment for SSR (ancillary services) addition

    Args:
        booking: The booking instance
        user: User making the payment
        payment_data: Payment details (amount, payment_channel, etc.)
        ssr_amount: Total amount for SSR services
        ssr_details: Details about SSR services added
        request: Django request object

    Returns:
        Dict with payment processing result
    """
    if ssr_amount <= 0:
        return {"success": True, "message": "No payment required for SSR", "amount": 0}

    # Update payment_data with SSR metadata
    payment_data["amount"] = float(ssr_amount)
    payment_data["transaction_type"] = "ssr_payment"
    payment_data["metadata"] = {
        "ssr_amount": float(ssr_amount),
        "ssr_details": ssr_details or {},
        "ssr_type": "ancillary_services",
    }

    processor = FlightPaymentProcessor(booking, user, payment_data, request=request)
    result = processor.initiate_payment(allow_confirmed=True)

    if result.get("success"):
        # Update booking final amount
        booking.final_amount = (booking.final_amount or Decimal("0")) + ssr_amount
        booking.total_payment_made = (
            booking.total_payment_made or Decimal("0")
        ) + ssr_amount
        booking.save(update_fields=["final_amount", "total_payment_made"])

    return result
