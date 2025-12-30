"""
Unified Razorpay Webhook Handler
Routes webhook events to appropriate handlers based on transaction_type
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
import json
import traceback
import logging

from IDBOOKAPI.mixins import StandardResponseMixin, LoggingMixin
from apps.payment_gateways.mixins.razorpay_mixins import RazorpayMixin
from apps.log_management.utils.db_utils import create_wallet_payment_log, create_booking_payment_log

logger = logging.getLogger(__name__)


@method_decorator(csrf_exempt, name='dispatch')
class UnifiedRazorpayWebhookView(APIView, StandardResponseMixin, LoggingMixin):
    """
    Unified Razorpay Webhook Endpoint
    
    This endpoint handles all Razorpay webhook events and routes them
    to appropriate handlers based on transaction_type in order notes.
    
    Transaction types supported:
    - wallet_recharge: Wallet recharge payments
    - flight_booking_payment: Flight booking payments
    - ticket_issuance_payment: Flight ticket issuance payments
    - reschedule_payment: Flight reschedule payments
    - ssr_payment: Flight SSR (ancillary services) payments
    - hotel_booking_payment: Hotel booking payments (identified by booking_type)
    """
    permission_classes = [AllowAny]

    def post(self, request):
        """Handle Razorpay webhook POST request"""
        try:
            self.log_info("=== UNIFIED RAZORPAY WEBHOOK ENDPOINT CALLED ===")
            self.log_info(f"Request headers: {dict(request.META)}")
            self.log_info(f"Request body: {request.body}")
            
            payment_log = {}
            
            # Get raw body for signature verification
            raw_body = request.body
            signature = request.META.get("HTTP_X_RAZORPAY_SIGNATURE", "")
            # Store signature for use in handlers
            self._current_signature = signature
            
            self.log_info(f"Webhook signature received: {signature[:20] if signature else 'None'}...")
            
            razorpay_mixin = RazorpayMixin()
            
            # Verify webhook signature
            if signature and not razorpay_mixin.verify_webhook_signature(raw_body, signature):
                self.log_error("Invalid webhook signature")
                # Store error in request/response JSON fields (valid model fields)
                payment_log["request"] = {"error": "Invalid webhook signature", "signature": signature[:20] if signature else None}
                payment_log["response"] = {"error": "Invalid webhook signature"}
                try:
                    create_wallet_payment_log(payment_log)
                except Exception as log_error:
                    self.log_error(f"Failed to create payment log: {str(log_error)}")
                return self.get_error_response(
                    message="Invalid webhook signature",
                    status="error",
                    errors=[],
                    error_code="INVALID_SIGNATURE",
                    status_code=status.HTTP_400_BAD_REQUEST,
                )
            
            self.log_info("Webhook signature verified successfully")
            
            # Parse payload
            try:
                if isinstance(request.data, dict):
                    payload = request.data
                else:
                    payload = json.loads(raw_body.decode('utf-8'))
            except (json.JSONDecodeError, AttributeError):
                payload = json.loads(raw_body.decode('utf-8'))
            
            event = payload.get("event")
            self.log_info(f"Webhook event: {event}")
            # Store event in request JSON field (valid model field)
            payment_log["request"] = {"event": event, "payload": payload}
            
            if event == "payment.captured":
                return self._handle_payment_captured(payload, razorpay_mixin, payment_log)
            elif event == "payment.failed":
                return self._handle_payment_failed(payload, razorpay_mixin, payment_log)
            else:
                self.log_info(f"Unhandled webhook event: {event}")
                return self.get_response(
                    status="success",
                    data={"received": True, "event": event},
                    message="Webhook received but event not processed",
                    status_code=status.HTTP_200_OK,
                )
                
        except Exception as e:
            self.log_error(f"Exception in unified Razorpay webhook: {str(e)}")
            self.log_error(traceback.format_exc())
            return self.get_error_response(
                message=f"Webhook processing failed: {str(e)}",
                status="error",
                errors=[],
                error_code="WEBHOOK_ERROR",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
    
    def _handle_payment_captured(self, payload, razorpay_mixin, payment_log):
        """Handle payment.captured event"""
        self.log_info("Processing payment.captured event")
        
        payment_entity = payload.get("payload", {}).get("payment", {}).get("entity", {})
        razorpay_payment_id = payment_entity.get("id")
        razorpay_order_id = payment_entity.get("order_id")
        amount = float(payment_entity.get("amount", 0)) / 100
        
        self.log_info(f"Payment details - payment_id: {razorpay_payment_id}, order_id: {razorpay_order_id}, amount: {amount}")
        
        # Store payment details in request JSON field (valid model fields)
        if not payment_log.get("request"):
            payment_log["request"] = {}
        payment_log["request"]["razorpay_payment_id"] = razorpay_payment_id
        payment_log["request"]["razorpay_order_id"] = razorpay_order_id
        payment_log["merchant_transaction_id"] = ""  # Will be set later from notes
        
        # Get order details to determine transaction type
        self.log_info(f"Fetching order details for order_id: {razorpay_order_id}")
        order_result = razorpay_mixin.get_order_details(razorpay_order_id)
        
        if not order_result.get("success"):
            self.log_error(f"Failed to fetch order details for order_id: {razorpay_order_id}")
            return self.get_error_response(
                message="Failed to fetch order details",
                status="error",
                errors=[],
                error_code="ORDER_FETCH_ERROR",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        
        order_data = order_result.get("order", {})
        notes = order_data.get("notes", {})
        transaction_type = notes.get("transaction_type", "")
        booking_type = notes.get("booking_type", "")
        
        self.log_info(f"Order notes - transaction_type: {transaction_type}, booking_type: {booking_type}")
        self.log_info(f"Full order notes: {notes}")
        
        # Route to appropriate handler based on transaction_type
        if transaction_type == "wallet_recharge":
            return self._handle_wallet_recharge_webhook(
                razorpay_payment_id, razorpay_order_id, amount, notes, payment_log
            )
        elif transaction_type in ("flight_booking_payment", "ticket_issuance_payment", "reschedule_payment", "ssr_payment"):
            # Get signature from request (stored earlier in post method)
            signature = getattr(self, '_current_signature', '')
            return self._handle_flight_payment_webhook(
                razorpay_payment_id, razorpay_order_id, amount, notes, transaction_type, payment_log, signature
            )
        elif booking_type == "HOTEL":
            return self._handle_hotel_booking_webhook(
                razorpay_payment_id, razorpay_order_id, amount, notes, payment_log
            )
        else:
            self.log_warning(f"Unknown transaction type: {transaction_type}, booking_type: {booking_type}")
            # Try to handle as generic booking payment
            return self._handle_generic_booking_webhook(
                razorpay_payment_id, razorpay_order_id, amount, notes, payment_log
            )
    
    def _handle_payment_failed(self, payload, razorpay_mixin, payment_log):
        """Handle payment.failed event"""
        self.log_warning("Processing payment.failed event")
        
        payment_entity = payload.get("payload", {}).get("payment", {}).get("entity", {})
        razorpay_payment_id = payment_entity.get("id")
        razorpay_order_id = payment_entity.get("order_id")
        
        self.log_info(f"Failed payment - payment_id: {razorpay_payment_id}, order_id: {razorpay_order_id}")
        
        # Get order details
        order_result = razorpay_mixin.get_order_details(razorpay_order_id)
        if order_result.get("success"):
            order_data = order_result.get("order", {})
            notes = order_data.get("notes", {})
            transaction_type = notes.get("transaction_type", "")
            booking_type = notes.get("booking_type", "")
            
            # Route to appropriate failure handler
            if transaction_type == "wallet_recharge":
                merchant_transaction_id = notes.get("merchant_transaction_id")
                if merchant_transaction_id:
                    from apps.customer.utils.db_utils import update_wallet_transaction_detail
                    update_wallet_transaction_detail(
                        merchant_transaction_id,
                        {
                            "transaction_id": razorpay_payment_id,
                            "code": "PAYMENT_FAILED",
                            "transaction_details": "Razorpay webhook payment failed",
                            "is_transaction_success": False,
                            "status": "Failed",
                        }
                    )
            elif transaction_type in ("flight_booking_payment", "ticket_issuance_payment", "reschedule_payment", "ssr_payment"):
                # Update flight booking payment
                from apps.payment_gateways.models import RazorpayOrder
                try:
                    razorpay_order = RazorpayOrder.objects.get(rp_id=razorpay_order_id)
                    razorpay_order.payment_id = razorpay_payment_id
                    razorpay_order.payment_status = "failed"
                    razorpay_order.status = "failed"
                    razorpay_order.save()
                    
                    merchant_transaction_id = notes.get("merchant_transaction_id")
                    if merchant_transaction_id:
                        from apps.booking.utils.db_utils import update_booking_payment_details
                        update_booking_payment_details(
                            merchant_transaction_id,
                            {
                                "transaction_id": razorpay_payment_id,
                                "code": "PAYMENT_FAILED",
                                "message": "Razorpay payment failed",
                                "is_transaction_success": False,
                            }
                        )
                except Exception as e:
                    self.log_error(f"Error updating failed flight payment: {str(e)}")
            elif booking_type == "HOTEL":
                # Update hotel booking payment
                from apps.payment_gateways.models import RazorpayOrder
                try:
                    razorpay_order = RazorpayOrder.objects.get(rp_id=razorpay_order_id)
                    razorpay_order.payment_id = razorpay_payment_id
                    razorpay_order.payment_status = "failed"
                    razorpay_order.status = "failed"
                    razorpay_order.save()
                except Exception as e:
                    self.log_error(f"Error updating failed hotel payment: {str(e)}")
        
        payment_log["response"] = {"success": False, "event": "payment.failed"}
        # Set merchant_transaction_id if available
        merchant_transaction_id = notes.get("merchant_transaction_id", "") if order_result.get("success") else ""
        if merchant_transaction_id:
            payment_log["merchant_transaction_id"] = merchant_transaction_id
        try:
            create_wallet_payment_log(payment_log)
        except Exception as log_error:
            self.log_error(f"Failed to create payment log: {str(log_error)}")
        
        return self.get_response(
            status="success",
            data={"received": True},
            message="Payment failed event processed",
            status_code=status.HTTP_200_OK,
        )
    
    def _handle_wallet_recharge_webhook(self, razorpay_payment_id, razorpay_order_id, amount, notes, payment_log):
        """Handle wallet recharge webhook"""
        self.log_info("Routing to wallet recharge handler")
        
        # Import wallet webhook handler logic
        from apps.customer.viewsets import WalletViewSet
        wallet_viewset = WalletViewSet()
        wallet_viewset.log_info = self.log_info
        wallet_viewset.log_error = self.log_error
        wallet_viewset.log_warning = self.log_warning
        
        # Create a mock request object with the webhook data
        from django.test import RequestFactory
        factory = RequestFactory()
        webhook_data = {
            "event": "payment.captured",
            "payload": {
                "payment": {
                    "entity": {
                        "id": razorpay_payment_id,
                        "order_id": razorpay_order_id,
                        "amount": int(amount * 100),  # Convert to paise
                    }
                }
            }
        }
        
        # Call the wallet webhook handler directly
        # We'll extract the logic instead
        return self._process_wallet_recharge(
            razorpay_payment_id, razorpay_order_id, amount, notes, payment_log
        )
    
    def _process_wallet_recharge(self, razorpay_payment_id, razorpay_order_id, amount, notes, payment_log):
        """Process wallet recharge webhook"""
        try:
            merchant_transaction_id = notes.get("merchant_transaction_id")
            user_id = notes.get("user_id")
            company_id = notes.get("company_id")
            
            self.log_info(f"Wallet recharge - merchant_transaction_id: {merchant_transaction_id}, user_id: {user_id}, company_id: {company_id}")
            
            if company_id:
                try:
                    company_id = int(company_id)
                except (ValueError, TypeError):
                    company_id = None
            
            if user_id:
                try:
                    user_id = int(user_id)
                except (ValueError, TypeError):
                    user_id = None
            
            # Update wallet transaction
            from apps.customer.utils.db_utils import update_wallet_transaction_detail, update_wallet_recharge_details
            payment_details = {
                "transaction_id": razorpay_payment_id,
                "code": "PAYMENT_SUCCESS",
                "transaction_details": f"Razorpay webhook payment successful. Payment ID: {razorpay_payment_id}",
                "payment_type": "PAYMENT GATEWAY",
                "payment_medium": "RAZORPAY",
                "amount": amount,
                "is_transaction_success": True,
                "status": "Completed",
            }
            
            self.log_info(f"Updating wallet transaction: {payment_details}")
            update_wallet_transaction_detail(merchant_transaction_id, payment_details)
            
            # Get user_id and company_id from WalletTransaction if not in notes
            if not user_id and not company_id:
                from apps.customer.models import WalletTransaction
                wallet_txn = WalletTransaction.objects.filter(
                    transaction_id=merchant_transaction_id
                ).first()
                if wallet_txn:
                    if wallet_txn.user:
                        user_id = wallet_txn.user.id
                    company_id = wallet_txn.company_id if wallet_txn.company_id else None
            
            # Recharge wallet
            if user_id or company_id:
                update_wallet_recharge_details(user_id, company_id, amount)
                
                # Send SMS notification
                from apps.booking.tasks import send_booking_sms_task
                from apps.customer.models import Wallet
                from apps.authentication.models import User
                
                if user_id and not company_id:
                    wallet = Wallet.objects.filter(user__id=user_id, company_id__isnull=True).first()
                    wallet_balance = wallet.balance if wallet else 0
                    user = User.objects.get(id=user_id)
                    if user and user.mobile_number:
                        send_booking_sms_task.apply_async(
                            kwargs={
                                "notification_type": "WALLET_RECHARGE_CONFIRMATION",
                                "params": {
                                    "user_id": user_id,
                                    "recharge_amount": float(amount),
                                    "wallet_balance": wallet_balance,
                                },
                            }
                        )
                elif company_id and user_id:
                    wallet = Wallet.objects.filter(company_id=company_id).first()
                    wallet_balance = wallet.balance if wallet else 0
                    user = User.objects.get(id=user_id)
                    if user and user.mobile_number:
                        send_booking_sms_task.apply_async(
                            kwargs={
                                "notification_type": "WALLET_RECHARGE_CONFIRMATION",
                                "params": {
                                    "user_id": user_id,
                                    "recharge_amount": float(amount),
                                    "wallet_balance": wallet_balance,
                                    "company_id": company_id,
                                },
                            }
                        )
            
            payment_log["response"] = {"success": True, "transaction_type": "wallet_recharge"}
            # Set merchant_transaction_id if available
            if merchant_transaction_id:
                payment_log["merchant_transaction_id"] = merchant_transaction_id
            try:
                create_wallet_payment_log(payment_log)
            except Exception as log_error:
                self.log_error(f"Failed to create payment log: {str(log_error)}")
            self.log_info(f"=== WALLET RECHARGE WEBHOOK SUCCESS - Payment ID: {razorpay_payment_id} ===")
            
            return self.get_response(
                status="success",
                data={"received": True, "transaction_type": "wallet_recharge"},
                message="Wallet recharge webhook processed",
                status_code=status.HTTP_200_OK,
            )
        except Exception as e:
            self.log_error(f"Error processing wallet recharge webhook: {str(e)}")
            self.log_error(traceback.format_exc())
            raise
    
    def _handle_flight_payment_webhook(self, razorpay_payment_id, razorpay_order_id, amount, notes, transaction_type, payment_log, signature=""):
        """Handle flight payment webhook (booking, ticket, reschedule, SSR)"""
        self.log_info(f"Routing to flight payment handler - transaction_type: {transaction_type}")
        
        # Import flight webhook handler
        from apps.booking.subviews.enhanced_flight_viewset import EnhancedFlightBookingViewSet
        flight_viewset = EnhancedFlightBookingViewSet()
        
        # Update RazorpayOrder
        from apps.payment_gateways.models import RazorpayOrder
        try:
            razorpay_order = RazorpayOrder.objects.get(rp_id=razorpay_order_id)
            razorpay_order.payment_id = razorpay_payment_id
            razorpay_order.payment_status = "captured"
            razorpay_order.status = "paid"
            razorpay_order.save()
        except RazorpayOrder.DoesNotExist:
            self.log_warning(f"RazorpayOrder not found: {razorpay_order_id}")
        
        # Update booking payment detail
        merchant_transaction_id = notes.get("merchant_transaction_id")
        if merchant_transaction_id:
            from apps.booking.utils.db_utils import update_booking_payment_details
            update_booking_payment_details(
                merchant_transaction_id,
                {
                    "transaction_id": razorpay_payment_id,
                    "code": "PAYMENT_SUCCESS",
                    "message": "Razorpay webhook payment successful",
                    "is_transaction_success": True,
                    "payment_type": "PAYMENT GATEWAY",
                    "payment_medium": "RAZORPAY",
                    "amount": amount,
                }
            )
        
        # Route to specific handler based on transaction_type
        booking_id = notes.get("booking_id")
        if booking_id:
            try:
                booking_id = int(booking_id)
                from apps.booking.models import Booking
                booking = Booking.objects.get(id=booking_id)
                
                if transaction_type == "ticket_issuance_payment":
                    # Process ticket issuance (method signature: booking, amount, payment_id, order_id)
                    try:
                        result = flight_viewset._process_ticket_issuance_after_razorpay(
                            booking, amount, razorpay_payment_id, razorpay_order_id
                        )
                        # Method returns Response object, extract data if needed
                        if hasattr(result, 'data') and result.status_code == 200:
                            self.log_info("Ticket issuance processed successfully")
                    except Exception as e:
                        self.log_error(f"Error processing ticket issuance: {str(e)}")
                        self.log_error(traceback.format_exc())
                elif transaction_type == "reschedule_payment":
                    # Process reschedule (method signature: booking, merchant_transaction_id, amount, payment_id, order_id)
                    try:
                        result = flight_viewset._process_reschedule_after_razorpay(
                            booking, merchant_transaction_id, amount, razorpay_payment_id, razorpay_order_id
                        )
                        # Method returns Response object, extract data if needed
                        if hasattr(result, 'data') and result.status_code == 200:
                            self.log_info("Reschedule processed successfully")
                    except Exception as e:
                        self.log_error(f"Error processing reschedule: {str(e)}")
                        self.log_error(traceback.format_exc())
                elif transaction_type == "ssr_payment":
                    # Process SSR (method signature: booking, merchant_transaction_id, amount, payment_id, order_id)
                    try:
                        result = flight_viewset._process_ssr_after_razorpay(
                            booking, merchant_transaction_id, amount, razorpay_payment_id, razorpay_order_id
                        )
                        # Method returns Response object, extract data if needed
                        if hasattr(result, 'data') and result.status_code == 200:
                            self.log_info("SSR processed successfully")
                    except Exception as e:
                        self.log_error(f"Error processing SSR: {str(e)}")
                        self.log_error(traceback.format_exc())
                else:
                    # Default flight booking payment - same flow as PhonePe callback
                    self.log_info(f"=== Processing flight booking payment for booking_id: {booking_id} ===")
                    from apps.booking.utils.flight_payment_utils import handle_flight_payment_success
                    
                    # Use merchant_transaction_id (not razorpay_payment_id) for transaction_id
                    # This matches how PhonePe callback works - it uses merchantTransactionId
                    payment_details_dict = {
                        "amount": amount,
                        "transaction_id": merchant_transaction_id,  # Use merchant_transaction_id, not razorpay_payment_id
                        "payment_channel": "RAZORPAY",  # Match PhonePe structure
                        "payment_method": "RAZORPAY",
                        "payment_medium": "RAZORPAY",
                        "razorpay_order_id": razorpay_order_id,
                        "razorpay_payment_id": razorpay_payment_id,
                        "payment_data": {  # Match PhonePe structure
                            "razorpay_order_id": razorpay_order_id,
                            "razorpay_payment_id": razorpay_payment_id,
                            "amount": amount,
                            "merchant_transaction_id": merchant_transaction_id,
                        },
                    }
                    self.log_info(f"Calling handle_flight_payment_success with booking_id: {booking_id}")
                    self.log_info(f"Payment details: amount={amount}, transaction_id={merchant_transaction_id}, razorpay_payment_id={razorpay_payment_id}")
                    try:
                        success = handle_flight_payment_success(booking_id, payment_details_dict)
                        if success:
                            self.log_info(f"✓ Flight booking {booking_id} confirmed and ticket issued automatically via Razorpay webhook")
                        else:
                            self.log_error(f"✗ handle_flight_payment_success returned False for booking {booking_id}")
                    except Exception as callback_error:
                        self.log_error(f"✗ Exception in handle_flight_payment_success for booking {booking_id}: {str(callback_error)}")
                        self.log_error(traceback.format_exc())
            except Exception as e:
                self.log_error(f"Error processing flight payment: {str(e)}")
                self.log_error(traceback.format_exc())
        
        # Create booking payment log (not wallet log) for flight payments
        booking_payment_log = {}
        booking_payment_log["merchant_transaction_id"] = merchant_transaction_id or ""
        booking_payment_log["x_verify"] = signature  # Store Razorpay signature in x_verify field
        
        # Store webhook data in request JSON field
        booking_payment_log["request"] = {
            "event": "payment.captured",
            "razorpay_payment_id": razorpay_payment_id,
            "razorpay_order_id": razorpay_order_id,
            "amount": amount,
            "transaction_type": transaction_type,
            "notes": notes,
        }
        
        # Store processing result in response JSON field
        booking_payment_log["response"] = {
            "success": True,
            "transaction_type": transaction_type,
            "message": "Flight payment webhook processed successfully",
        }
        
        # Set booking object if available
        booking_id = notes.get("booking_id")
        if booking_id:
            try:
                from apps.booking.models import Booking
                booking = Booking.objects.get(id=int(booking_id))
                booking_payment_log["booking"] = booking
            except Exception as e:
                self.log_error(f"Failed to get booking for log: {str(e)}")
        
        try:
            create_booking_payment_log(booking_payment_log)
        except Exception as log_error:
            self.log_error(f"Failed to create booking payment log: {str(log_error)}")
            self.log_error(traceback.format_exc())
        
        self.log_info(f"=== FLIGHT PAYMENT WEBHOOK SUCCESS - Type: {transaction_type}, Payment ID: {razorpay_payment_id} ===")
        
        return self.get_response(
            status="success",
            data={"received": True, "transaction_type": transaction_type},
            message="Flight payment webhook processed",
            status_code=status.HTTP_200_OK,
        )
    
    def _handle_hotel_booking_webhook(self, razorpay_payment_id, razorpay_order_id, amount, notes, payment_log):
        """Handle hotel booking webhook"""
        self.log_info("Routing to hotel booking handler")
        
        # Update RazorpayOrder
        from apps.payment_gateways.models import RazorpayOrder
        try:
            razorpay_order = RazorpayOrder.objects.get(rp_id=razorpay_order_id)
            razorpay_order.payment_id = razorpay_payment_id
            razorpay_order.payment_status = "captured"
            razorpay_order.status = "paid"
            razorpay_order.save()
            
            booking = razorpay_order.booking
            if booking and booking.status != "confirmed":
                # Update booking payment detail
                payment_details = booking.booking_payment.filter(
                    transaction_details__razorpay_order_id=razorpay_order_id
                ).first()
                
                if payment_details:
                    from apps.booking.utils.db_utils import update_booking_payment_details
                    update_booking_payment_details(
                        payment_details.merchant_transaction_id,
                        {
                            "transaction_id": razorpay_payment_id,
                            "code": "PAYMENT_SUCCESS",
                            "message": "Payment captured via Razorpay webhook",
                            "is_transaction_success": True,
                        }
                    )
                
                # Confirm booking
                from apps.booking.viewsets import BookingViewSet
                booking_viewset = BookingViewSet()
                booking_viewset.set_booking_as_confirmed(booking.id, amount)
        except RazorpayOrder.DoesNotExist:
            self.log_warning(f"RazorpayOrder not found: {razorpay_order_id}")
        except Exception as e:
            self.log_error(f"Error processing hotel booking webhook: {str(e)}")
            self.log_error(traceback.format_exc())
        
        payment_log["response"] = {"success": True, "booking_type": "HOTEL"}
        # Set merchant_transaction_id if available from notes
        merchant_transaction_id = notes.get("merchant_transaction_id", "")
        if merchant_transaction_id:
            payment_log["merchant_transaction_id"] = merchant_transaction_id
        try:
            create_wallet_payment_log(payment_log)
        except Exception as log_error:
            self.log_error(f"Failed to create payment log: {str(log_error)}")
        self.log_info(f"=== HOTEL BOOKING WEBHOOK SUCCESS - Payment ID: {razorpay_payment_id} ===")
        
        return self.get_response(
            status="success",
            data={"received": True, "booking_type": "HOTEL"},
            message="Hotel booking webhook processed",
            status_code=status.HTTP_200_OK,
        )
    
    def _handle_generic_booking_webhook(self, razorpay_payment_id, razorpay_order_id, amount, notes, payment_log):
        """Handle generic booking webhook (fallback)"""
        self.log_info("Routing to generic booking handler (fallback)")
        
        # Try to find RazorpayOrder and update it
        from apps.payment_gateways.models import RazorpayOrder
        try:
            razorpay_order = RazorpayOrder.objects.get(rp_id=razorpay_order_id)
            razorpay_order.payment_id = razorpay_payment_id
            razorpay_order.payment_status = "captured"
            razorpay_order.status = "paid"
            razorpay_order.save()
            
            booking = razorpay_order.booking
            if booking:
                # Update booking payment detail
                payment_details = booking.booking_payment.filter(
                    transaction_details__razorpay_order_id=razorpay_order_id
                ).first()
                
                if payment_details:
                    from apps.booking.utils.db_utils import update_booking_payment_details
                    update_booking_payment_details(
                        payment_details.merchant_transaction_id,
                        {
                            "transaction_id": razorpay_payment_id,
                            "code": "PAYMENT_SUCCESS",
                            "message": "Payment captured via Razorpay webhook",
                            "is_transaction_success": True,
                        }
                    )
        except RazorpayOrder.DoesNotExist:
            self.log_warning(f"RazorpayOrder not found: {razorpay_order_id}")
        except Exception as e:
            self.log_error(f"Error processing generic booking webhook: {str(e)}")
        
        payment_log["response"] = {"success": True}
        # Set merchant_transaction_id if available
        merchant_transaction_id = notes.get("merchant_transaction_id", "")
        if merchant_transaction_id:
            payment_log["merchant_transaction_id"] = merchant_transaction_id
        try:
            create_wallet_payment_log(payment_log)
        except Exception as log_error:
            self.log_error(f"Failed to create payment log: {str(log_error)}")
        
        return self.get_response(
            status="success",
            data={"received": True},
            message="Generic booking webhook processed",
            status_code=status.HTTP_200_OK,
        )
