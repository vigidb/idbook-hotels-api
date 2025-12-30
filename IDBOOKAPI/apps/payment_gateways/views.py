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
from decimal import Decimal
from django.utils import timezone

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
            elif event in ("refund.processed", "refund.created"):
                return self._handle_refund_processed(payload, razorpay_mixin, payment_log)
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
        print("=" * 80)
        print("=== _handle_payment_captured CALLED ===")
        self.log_info("Processing payment.captured event")
        logger.info("Processing payment.captured event")
        
        payment_entity = payload.get("payload", {}).get("payment", {}).get("entity", {})
        razorpay_payment_id = payment_entity.get("id")
        razorpay_order_id = payment_entity.get("order_id")
        amount = float(payment_entity.get("amount", 0)) / 100
        
        print(f"Payment details - payment_id: {razorpay_payment_id}, order_id: {razorpay_order_id}, amount: {amount}")
        self.log_info(f"Payment details - payment_id: {razorpay_payment_id}, order_id: {razorpay_order_id}, amount: {amount}")
        logger.info(f"Payment details - payment_id: {razorpay_payment_id}, order_id: {razorpay_order_id}, amount: {amount}")
        
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
        print(f"Transaction type: {transaction_type}, Booking type: {booking_type}")
        logger.info(f"Transaction type: {transaction_type}, Booking type: {booking_type}")
        
        if transaction_type == "wallet_recharge":
            print("Routing to wallet recharge handler")
            return self._handle_wallet_recharge_webhook(
                razorpay_payment_id, razorpay_order_id, amount, notes, payment_log
            )
        elif transaction_type in ("flight_booking_payment", "ticket_issuance_payment", "reschedule_payment", "ssr_payment"):
            print(f"Routing to flight payment handler for transaction_type: {transaction_type}")
            logger.info(f"Routing to flight payment handler for transaction_type: {transaction_type}")
            # Get signature from request (stored earlier in post method)
            signature = getattr(self, '_current_signature', '')
            return self._handle_flight_payment_webhook(
                razorpay_payment_id, razorpay_order_id, amount, notes, transaction_type, payment_log, signature
            )
        elif booking_type == "HOTEL":
            print(f"Routing to hotel booking handler for booking_type: {booking_type}")
            logger.info(f"Routing to hotel booking handler for booking_type: {booking_type}")
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
    
    def _handle_refund_processed(self, payload, razorpay_mixin, payment_log):
        """Handle refund.processed or refund.created event"""
        print("=" * 80)
        print("=== _handle_refund_processed CALLED ===")
        self.log_info("Processing refund event")
        logger.info("Processing refund event")
        
        refund_entity = payload.get("payload", {}).get("refund", {}).get("entity", {})
        refund_id = refund_entity.get("id")
        payment_id = refund_entity.get("payment_id")
        refund_status = refund_entity.get("status")
        refund_amount = float(refund_entity.get("amount", 0)) / 100  # Convert from paise
        
        print(f"Refund details - refund_id: {refund_id}, payment_id: {payment_id}, status: {refund_status}, amount: {refund_amount}")
        self.log_info(f"Refund details - refund_id: {refund_id}, payment_id: {payment_id}, status: {refund_status}, amount: {refund_amount}")
        
        if refund_status != "processed":
            self.log_info(f"Refund status is {refund_status}, not processed yet. Ignoring.")
            return self.get_response(
                status="success",
                data={"received": True, "status": refund_status},
                message="Refund event received but not processed yet",
                status_code=status.HTTP_200_OK,
            )
        
        # Get payment details to find the booking
        try:
            payment_result = razorpay_mixin.get_payment_details(payment_id)
            if not payment_result.get("success"):
                self.log_error(f"Failed to fetch payment details for payment_id: {payment_id}")
                return self.get_error_response(
                    message="Failed to fetch payment details",
                    status="error",
                    errors=[],
                    error_code="PAYMENT_FETCH_ERROR",
                    status_code=status.HTTP_400_BAD_REQUEST,
                )
            
            payment_data = payment_result.get("payment", {})
            order_id = payment_data.get("order_id")
            
            # Get order details to find booking
            order_result = razorpay_mixin.get_order_details(order_id)
            if not order_result.get("success"):
                self.log_error(f"Failed to fetch order details for order_id: {order_id}")
                return self.get_error_response(
                    message="Failed to fetch order details",
                    status="error",
                    errors=[],
                    error_code="ORDER_FETCH_ERROR",
                    status_code=status.HTTP_400_BAD_REQUEST,
                )
            
            order_data = order_result.get("order", {})
            notes = order_data.get("notes", {})
            booking_id = notes.get("booking_id")
            merchant_transaction_id = notes.get("merchant_transaction_id")
            
            if not booking_id:
                self.log_warning(f"No booking_id found in refund webhook for payment {payment_id}")
                return self.get_response(
                    status="success",
                    data={"received": True},
                    message="Refund processed but no booking found",
                    status_code=status.HTTP_200_OK,
                )
            
            booking_id = int(booking_id)
            from apps.booking.models import Booking
            
            try:
                booking = Booking.objects.select_related("flight_booking", "hotel_booking").get(id=booking_id)
                
                # Handle based on booking type
                if booking.booking_type == "FLIGHT":
                    # Update booking status to refunded
                    booking.status = "refunded"
                    booking.total_payment_made = Decimal("0.0")
                    booking.save(update_fields=["status", "total_payment_made"])
                    
                    # Update flight booking status if exists
                    if booking.flight_booking:
                        booking.flight_booking.status = "REFUNDED"
                        booking.flight_booking.save(update_fields=["status"])
                elif booking.booking_type == "HOTEL":
                    # For hotel bookings, update cancellation_details instead of status
                    # Status should remain "canceled" (not "refunded")
                    if booking.hotel_booking and booking.hotel_booking.cancellation_details:
                        cancellation_details = booking.hotel_booking.cancellation_details
                        cancellation_details["refund_status"] = "refund_completed"
                        cancellation_details["refund_id"] = refund_id
                        cancellation_details["refund_amount"] = refund_amount
                        cancellation_details["refund_processed_at"] = timezone.now().isoformat()
                        booking.hotel_booking.cancellation_details = cancellation_details
                        booking.hotel_booking.save(update_fields=["cancellation_details"])
                    
                    # Update booking total_payment_made
                    booking.total_payment_made = Decimal("0.0")
                    booking.save(update_fields=["total_payment_made"])
                
                # Update payment details
                if merchant_transaction_id:
                    from apps.booking.utils.db_utils import update_booking_payment_details
                    update_booking_payment_details(
                        merchant_transaction_id,
                        {
                            "code": "REFUND_PROCESSED",
                            "message": f"Refund processed successfully. Refund ID: {refund_id}",
                            "is_transaction_success": False,
                            "transaction_details": {
                                "refund_id": refund_id,
                                "refund_status": "processed",
                                "refund_amount": refund_amount,
                                "payment_id": payment_id,
                            },
                        },
                    )
                
                # Update RazorpayOrder if exists
                from apps.payment_gateways.models import RazorpayOrder
                try:
                    razorpay_order = RazorpayOrder.objects.get(rp_id=order_id)
                    razorpay_order.status = "refunded"
                    razorpay_order.save(update_fields=["status"])
                except RazorpayOrder.DoesNotExist:
                    pass
                
                # For hotel bookings, also update BookingRefundLog if exists
                if booking.booking_type == "HOTEL":
                    from apps.log_management.models import BookingRefundLog
                    try:
                        # Try to find refund log by merchant_refund_id from cancellation_details
                        if booking.hotel_booking and booking.hotel_booking.cancellation_details:
                            merchant_refund_id = booking.hotel_booking.cancellation_details.get("merchant_refund_id")
                            if merchant_refund_id:
                                refund_log_entry = BookingRefundLog.objects.filter(
                                    merchant_refund_id=merchant_refund_id
                                ).first()
                                if refund_log_entry:
                                    refund_log_entry.status = "completed"
                                    refund_log_entry.transaction_id = refund_id
                                    refund_log_entry.response_code = "SUCCESS"
                                    refund_log_entry.response_message = "Refund processed successfully"
                                    refund_log_entry.save()
                    except Exception as e:
                        self.log_warning(f"Failed to update BookingRefundLog: {str(e)}")
                
                if booking.booking_type == "FLIGHT":
                    print(f"✓ Flight booking {booking_id} status updated to refunded")
                    self.log_info(f"Flight booking {booking_id} status updated to refunded. Refund ID: {refund_id}")
                    logger.info(f"Flight booking {booking_id} status updated to refunded. Refund ID: {refund_id}")
                elif booking.booking_type == "HOTEL":
                    print(f"✓ Hotel booking {booking_id} refund processed successfully")
                    self.log_info(f"Hotel booking {booking_id} refund processed. Refund ID: {refund_id}")
                    logger.info(f"Hotel booking {booking_id} refund processed. Refund ID: {refund_id}")
                
            except Booking.DoesNotExist:
                self.log_error(f"Booking {booking_id} not found for refund processing")
                return self.get_error_response(
                    message="Booking not found",
                    status="error",
                    errors=[],
                    error_code="BOOKING_NOT_FOUND",
                    status_code=status.HTTP_404_NOT_FOUND,
                )
            
        except Exception as e:
            self.log_error(f"Error processing refund webhook: {str(e)}")
            self.log_error(traceback.format_exc())
            return self.get_error_response(
                message=f"Refund processing failed: {str(e)}",
                status="error",
                errors=[],
                error_code="REFUND_PROCESSING_ERROR",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        
        # Create payment log
        booking_payment_log = {}
        booking_payment_log["merchant_transaction_id"] = merchant_transaction_id or ""
        booking_payment_log["x_verify"] = getattr(self, '_current_signature', '')
        booking_payment_log["request"] = {
            "event": payload.get("event"),
            "refund_id": refund_id,
            "payment_id": payment_id,
            "refund_amount": refund_amount,
            "refund_status": refund_status,
        }
        booking_payment_log["response"] = {
            "success": True,
            "message": "Refund processed successfully",
        }
        
        if booking_id:
            try:
                booking_payment_log["booking"] = booking
            except:
                pass
        
        try:
            create_booking_payment_log(booking_payment_log)
        except Exception as log_error:
            self.log_error(f"Failed to create payment log: {str(log_error)}")
        
        return self.get_response(
            status="success",
            data={"received": True, "refund_id": refund_id, "booking_id": booking_id},
            message="Refund processed successfully",
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
        print(f"=== _handle_flight_payment_webhook CALLED - transaction_type: {transaction_type} ===")
        self.log_info(f"Routing to flight payment handler - transaction_type: {transaction_type}")
        logger.info(f"Routing to flight payment handler - transaction_type: {transaction_type}")
        
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
                    print(f"=== Processing flight booking payment for booking_id: {booking_id} ===")
                    self.log_info(f"=== Processing flight booking payment for booking_id: {booking_id} ===")
                    logger.info(f"=== Processing flight booking payment for booking_id: {booking_id} ===")
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
        """Handle hotel booking webhook - same flow as PhonePe callback"""
        print("=" * 80)
        print("=== _handle_hotel_booking_webhook CALLED ===")
        print(f"Notes: {notes}")
        self.log_info("Routing to hotel booking handler")
        logger.info("Routing to hotel booking handler")
        
        # Get booking_id and merchant_transaction_id from notes
        booking_id = notes.get("booking_id")
        merchant_transaction_id = notes.get("merchant_transaction_id")
        
        print(f"booking_id from notes: {booking_id}, merchant_transaction_id: {merchant_transaction_id}")
        
        if not booking_id:
            self.log_error("No booking_id found in hotel booking webhook notes")
            print("ERROR: No booking_id found in notes")
            return self.get_error_response(
                message="Booking ID not found in webhook",
                status="error",
                errors=[],
                error_code="BOOKING_ID_MISSING",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        
        booking_id = int(booking_id)
        print(f"Processing hotel booking {booking_id}")
        
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
        
        # Get booking
        from apps.booking.models import Booking
        try:
            booking = Booking.objects.select_related("hotel_booking", "meta_info").get(id=booking_id, booking_type="HOTEL")
            print(f"Booking found: {booking.id}, current status: {booking.status}")
            self.log_info(f"Booking found: {booking.id}, current status: {booking.status}")
        except Booking.DoesNotExist:
            self.log_error(f"Hotel booking {booking_id} not found")
            print(f"ERROR: Hotel booking {booking_id} not found")
            return self.get_error_response(
                message="Booking not found",
                status="error",
                errors=[],
                error_code="BOOKING_NOT_FOUND",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        
        # Update booking payment detail
        if merchant_transaction_id:
            from apps.booking.utils.db_utils import update_booking_payment_details
            print(f"Updating payment details for merchant_transaction_id: {merchant_transaction_id}")
            update_booking_payment_details(
                merchant_transaction_id,
                {
                    "transaction_id": razorpay_payment_id,
                    "code": "PAYMENT_SUCCESS",
                    "message": "Payment captured via Razorpay webhook",
                    "is_transaction_success": True,
                    "payment_type": "PAYMENT GATEWAY",
                    "payment_medium": "RAZORPAY",
                    "amount": amount,
                }
            )
            print("Payment details updated")
        
        # Confirm booking if not already confirmed - same as PhonePe callback
        print(f"Checking booking status: {booking.status}, needs confirmation: {booking.status != 'confirmed'}")
        if booking.status != "confirmed":
            print(f"Confirming hotel booking {booking_id}...")
            try:
                # Extract confirmation logic directly (avoid instantiating BookingViewSet)
                from apps.booking.utils.booking_utils import (
                    generate_booking_confirmation_code,
                    commission_calculation,
                    process_subscription_cashback,
                )
                from apps.booking.utils.db_utils import (
                    check_booking_confirmation_code,
                    add_or_update_booking_commission,
                )
                from apps.hotels.utils.hotel_utils import process_property_confirmed_booking_total
                from apps.booking.tasks import create_invoice_task
                from apps.hotels.tasks import send_hotel_receipt_email_task
                from datetime import datetime
                
                # Generate confirmation code
                booking_type = booking.booking_type
                print(f"Generating confirmation code for booking {booking_id}...")
                while True:
                    confirmation_code = generate_booking_confirmation_code(booking.id, booking_type)
                    is_exist = check_booking_confirmation_code(confirmation_code)
                    if not is_exist:
                        break
                
                print(f"Confirmation code generated: {confirmation_code}")
                
                # Update booking
                booking.confirmation_code = confirmation_code
                booking.total_payment_made = amount
                booking.status = "confirmed"
                booking.save()
                print(f"Booking status updated to confirmed")
                
                # Update meta_info
                if booking.meta_info:
                    booking.meta_info.booking_confirmed_date = datetime.now()
                    booking.meta_info.save()
                    print(f"Meta info updated")
                
                # Save booking commission details (only for hotel bookings)
                if booking.booking_type == "HOTEL" and booking.hotel_booking:
                    property_id = booking.hotel_booking.confirmed_property_id
                    if property_id:
                        print(f"Calculating commission for property {property_id}...")
                        commission_details = commission_calculation(
                            property_id,
                            booking.subtotal,
                            booking.total_discount,
                            booking.final_amount,
                            booking.gst_amount,
                        )
                        if commission_details:
                            add_or_update_booking_commission(booking.id, commission_details)
                            print(f"Commission details saved")
                        
                        # Update property confirmed booking count
                        process_property_confirmed_booking_total(property_id)
                        print(f"Property confirmed booking count updated")
                
                # Create invoice task
                create_invoice_task.apply_async(args=[booking.id])
                print(f"Invoice task scheduled")
                
                # Send receipt email
                send_hotel_receipt_email_task.apply_async(args=[booking.id])
                print(f"Receipt email task scheduled")
                
                # Process cashback
                try:
                    cashback_applied = process_subscription_cashback(booking.user, booking.id)
                    if cashback_applied:
                        print(f"Cashback applied for booking {booking_id}")
                except Exception as cashback_error:
                    print(f"Cashback processing failed (non-critical): {str(cashback_error)}")
                
                print(f"✓ Hotel booking {booking_id} confirmed successfully")
                self.log_info(f"Hotel booking {booking_id} confirmed successfully")
            except Exception as confirm_error:
                print(f"✗ Error confirming booking: {str(confirm_error)}")
                print(traceback.format_exc())
                self.log_error(f"Error confirming hotel booking {booking_id}: {str(confirm_error)}")
                self.log_error(traceback.format_exc())
                # Re-raise to see the error in webhook response
                raise
            
            # Send SMS notifications - same as PhonePe callback
            from apps.booking.tasks import send_booking_sms_task
            from apps.hotels.tasks import send_hotel_sms_task
            
            send_booking_sms_task.apply_async(
                kwargs={
                    "notification_type": "HOTEL_BOOKING_CONFIRMATION",
                    "params": {"booking_id": booking_id},
                }
            )
            send_hotel_sms_task.apply_async(
                kwargs={
                    "notification_type": "HOTELIER_BOOKING_NOTIFICATION",
                    "params": {"booking_id": booking_id},
                }
            )
            send_booking_sms_task.apply_async(
                kwargs={
                    "notification_type": "PAYMENT_PROCEED_INFO",
                    "params": {
                        "booking_id": booking_id,
                        "amount": float(amount),
                        "payment_purpose": "Hotel Booking",
                        "transaction_id": razorpay_payment_id,
                    },
                }
            )
            print(f"✓ Hotel booking {booking_id} confirmed and SMS notifications scheduled")
            self.log_info(f"Hotel booking {booking_id} confirmed and SMS notifications scheduled")
        
        # Create booking payment log (not wallet log)
        booking_payment_log = {}
        booking_payment_log["merchant_transaction_id"] = merchant_transaction_id or ""
        booking_payment_log["x_verify"] = getattr(self, '_current_signature', '')
        booking_payment_log["request"] = {
            "event": "payment.captured",
            "razorpay_payment_id": razorpay_payment_id,
            "razorpay_order_id": razorpay_order_id,
            "amount": amount,
            "booking_type": "HOTEL",
            "notes": notes,
        }
        booking_payment_log["response"] = {
            "success": True,
            "booking_type": "HOTEL",
            "message": "Hotel booking webhook processed successfully",
        }
        booking_payment_log["booking"] = booking
        
        try:
            create_booking_payment_log(booking_payment_log)
        except Exception as log_error:
            self.log_error(f"Failed to create booking payment log: {str(log_error)}")
            self.log_error(traceback.format_exc())
        
        self.log_info(f"=== HOTEL BOOKING WEBHOOK SUCCESS - Payment ID: {razorpay_payment_id}, Booking ID: {booking_id} ===")
        
        return self.get_response(
            status="success",
            data={"received": True, "booking_type": "HOTEL", "booking_id": booking_id},
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
