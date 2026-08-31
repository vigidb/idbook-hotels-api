import razorpay
import hmac
import hashlib
import logging
from django.conf import settings

logger = logging.getLogger(__name__)


class RazorpayMixin:
    """Mixin class for Razorpay payment gateway integration"""

    def __init__(self):
        # Initialize Razorpay client
        self.razorpay_key = getattr(settings, "RAZORPAY_KEY_ID", None)
        self.razorpay_secret = getattr(settings, "RAZORPAY_KEY_SECRET", None)
        self.webhook_secret = getattr(settings, "RAZORPAY_WEBHOOK_SECRET", None)

        if not self.razorpay_key or not self.razorpay_secret:
            logger.warning(
                "Razorpay credentials not configured. Payment operations will fail."
            )

        self.client = razorpay.Client(
            auth=(self.razorpay_key, self.razorpay_secret)
        )

    def create_razorpay_order(
        self, amount, currency="INR", receipt=None, notes=None
    ):
        """
        Create a Razorpay order

        Args:
            amount: Amount in rupees (will be converted to paise)
            currency: Currency code (default: INR)
            receipt: Receipt ID for the order
            notes: Additional notes/metadata

        Returns:
            dict: Order details from Razorpay API
        """
        try:
            # Convert amount to paise (Razorpay expects amount in smallest currency unit)
            amount_in_paise = int(float(amount) * 100)

            order_data = {
                "amount": amount_in_paise,
                "currency": currency,
            }

            if receipt:
                order_data["receipt"] = receipt

            if notes:
                order_data["notes"] = notes

            # Create order via Razorpay API
            order = self.client.order.create(data=order_data)

            logger.info(
                f"Razorpay order created: {order.get('id')} for amount {amount}"
            )

            return {
                "success": True,
                "order": order,
                "order_id": order.get("id"),
                "amount": order.get("amount"),
                "currency": order.get("currency"),
                "status": order.get("status"),
            }

        except razorpay.errors.BadRequestError as e:
            logger.error(f"Razorpay BadRequestError: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "error_code": "RAZORPAY_BAD_REQUEST",
            }
        except razorpay.errors.ServerError as e:
            logger.error(f"Razorpay ServerError: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "error_code": "RAZORPAY_SERVER_ERROR",
            }
        except Exception as e:
            logger.error(f"Razorpay order creation error: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "error_code": "RAZORPAY_ORDER_ERROR",
            }

    def verify_payment_signature(self, order_id, payment_id, signature):
        """
        Verify Razorpay payment signature

        Args:
            order_id: Razorpay order ID
            payment_id: Razorpay payment ID
            signature: Signature received from Razorpay

        Returns:
            bool: True if signature is valid, False otherwise
        """
        try:
            if not self.razorpay_secret:
                logger.error("Razorpay secret not configured")
                return False

            # Create message to verify
            message = f"{order_id}|{payment_id}"

            # Generate expected signature
            generated_signature = hmac.new(
                self.razorpay_secret.encode("utf-8"),
                message.encode("utf-8"),
                hashlib.sha256,
            ).hexdigest()

            # Compare signatures
            is_valid = hmac.compare_digest(generated_signature, signature)

            if is_valid:
                logger.info(
                    f"Payment signature verified for order: {order_id}, payment: {payment_id}"
                )
            else:
                logger.warning(
                    f"Invalid payment signature for order: {order_id}, payment: {payment_id}"
                )

            return is_valid

        except Exception as e:
            logger.error(f"Error verifying payment signature: {str(e)}")
            return False

    def capture_payment(self, payment_id, amount=None):
        """
        Capture an authorized payment

        Args:
            payment_id: Razorpay payment ID
            amount: Amount to capture (in rupees). If None, captures full amount.

        Returns:
            dict: Capture details
        """
        try:
            capture_data = {}
            if amount:
                # Convert to paise
                capture_data["amount"] = int(float(amount) * 100)

            payment = self.client.payment.capture(payment_id, capture_data)

            logger.info(f"Payment captured: {payment_id}")

            return {
                "success": True,
                "payment": payment,
                "payment_id": payment.get("id"),
                "status": payment.get("status"),
            }

        except razorpay.errors.BadRequestError as e:
            logger.error(f"Razorpay capture BadRequestError: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "error_code": "RAZORPAY_CAPTURE_BAD_REQUEST",
            }
        except Exception as e:
            logger.error(f"Razorpay capture error: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "error_code": "RAZORPAY_CAPTURE_ERROR",
            }

    def get_payment_details(self, payment_id):
        """
        Fetch payment details from Razorpay

        Args:
            payment_id: Razorpay payment ID

        Returns:
            dict: Payment details
        """
        try:
            payment = self.client.payment.fetch(payment_id)

            return {
                "success": True,
                "payment": payment,
                "payment_id": payment.get("id"),
                "order_id": payment.get("order_id"),
                "amount": payment.get("amount"),
                "currency": payment.get("currency"),
                "status": payment.get("status"),
                "method": payment.get("method"),
                "created_at": payment.get("created_at"),
            }

        except razorpay.errors.NotFoundError:
            logger.error(f"Payment not found: {payment_id}")
            return {
                "success": False,
                "error": "Payment not found",
                "error_code": "PAYMENT_NOT_FOUND",
            }
        except Exception as e:
            logger.error(f"Error fetching payment details: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "error_code": "RAZORPAY_FETCH_ERROR",
            }

    def refund_payment(self, payment_id, amount=None, notes=None, speed="normal"):
        """
        Process a refund for a payment

        Args:
            payment_id: Razorpay payment ID
            amount: Amount to refund (in rupees). If None, refunds full amount.
            notes: Refund notes
            speed: Refund speed - 'normal' or 'optimum'

        Returns:
            dict: Refund details
        """
        try:
            refund_data = {"speed": speed}

            if amount:
                # Convert to paise
                refund_data["amount"] = int(float(amount) * 100)

            if notes:
                refund_data["notes"] = notes

            refund = self.client.payment.refund(payment_id, refund_data)

            logger.info(f"Refund processed: {refund.get('id')} for payment: {payment_id}")

            return {
                "success": True,
                "refund": refund,
                "refund_id": refund.get("id"),
                "amount": refund.get("amount"),
                "status": refund.get("status"),
            }

        except razorpay.errors.BadRequestError as e:
            logger.error(f"Razorpay refund BadRequestError: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "error_code": "RAZORPAY_REFUND_BAD_REQUEST",
            }
        except Exception as e:
            logger.error(f"Razorpay refund error: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "error_code": "RAZORPAY_REFUND_ERROR",
            }

    def verify_webhook_signature(self, payload, signature):
        """
        Verify Razorpay webhook signature
        According to Razorpay documentation: https://razorpay.com/docs/webhooks/validate/

        Args:
            payload: Webhook payload (string or bytes)
            signature: Webhook signature from X-Razorpay-Signature header

        Returns:
            bool: True if signature is valid, False otherwise
        """
        try:
            if not self.webhook_secret:
                logger.warning("Webhook secret not configured, skipping verification")
                return True  # Allow if webhook secret not configured

            # Ensure payload is bytes
            if isinstance(payload, str):
                payload_bytes = payload.encode("utf-8")
            else:
                payload_bytes = payload

            # Ensure webhook secret is bytes
            secret_bytes = self.webhook_secret.encode("utf-8")

            # Generate expected signature using HMAC SHA256
            expected_signature = hmac.new(
                secret_bytes,
                payload_bytes,
                hashlib.sha256,
            ).hexdigest()

            # Compare signatures using constant-time comparison
            is_valid = hmac.compare_digest(expected_signature, signature)

            if not is_valid:
                logger.warning(
                    f"Invalid webhook signature. Expected: {expected_signature[:20]}..., Got: {signature[:20]}..."
                )

            return is_valid

        except Exception as e:
            logger.error(f"Error verifying webhook signature: {str(e)}")
            return False

    def get_order_details(self, order_id):
        """
        Fetch order details from Razorpay

        Args:
            order_id: Razorpay order ID

        Returns:
            dict: Order details
        """
        try:
            order = self.client.order.fetch(order_id)

            return {
                "success": True,
                "order": order,
                "order_id": order.get("id"),
                "amount": order.get("amount"),
                "currency": order.get("currency"),
                "status": order.get("status"),
                "receipt": order.get("receipt"),
            }

        except razorpay.errors.NotFoundError:
            logger.error(f"Order not found: {order_id}")
            return {
                "success": False,
                "error": "Order not found",
                "error_code": "ORDER_NOT_FOUND",
            }
        except Exception as e:
            logger.error(f"Error fetching order details: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "error_code": "RAZORPAY_ORDER_FETCH_ERROR",
            }


