from django.db import models


class RazorpayOrder(models.Model):
    user = models.ForeignKey(
        "authentication.User", on_delete=models.CASCADE, related_name="razorpay_user"
    )
    booking = models.ForeignKey(
        "booking.Booking",
        on_delete=models.CASCADE,
        related_name="razorpay_orders",
        null=True,
        blank=True,
    )
    rp_id = models.CharField(max_length=250)  # Razorpay order ID
    entity = models.CharField(max_length=50)
    amount = models.PositiveIntegerField(default=0)  # Amount in paise
    amount_due = models.PositiveIntegerField(default=0)  # Amount due in paise
    currency = models.CharField(max_length=50, default="INR")
    receipt = models.CharField(max_length=50, blank=True, null=True)
    offer_id = models.CharField(max_length=50, blank=True, null=True)
    status = models.CharField(max_length=50)  # created, attempted, paid, etc.
    payment_id = models.CharField(
        max_length=250, blank=True, null=True
    )  # Razorpay payment ID
    payment_status = models.CharField(
        max_length=50, blank=True, null=True
    )  # captured, failed, etc.
    attempts = models.PositiveSmallIntegerField(default=0)
    notes = models.JSONField(default=dict, blank=True, null=True)
    created_at = models.CharField(max_length=50, blank=True, null=True)

    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "payment_gateways"
        ordering = ["-created"]
        db_table = "payment_gateways_razorpayorder"

    def __str__(self):
        return f"RazorpayOrder {self.rp_id} - {self.user.email if self.user else 'No User'}"


class RazorpayPayout(models.Model):
    user = models.ForeignKey(
        "authentication.User", on_delete=models.CASCADE, related_name="razorpay_payout_user"
    )
    razorpay_customer_id = models.CharField(max_length=50, blank=True)
    razorpay_order_id = models.CharField(max_length=50, blank=True)
    razorpay_payment_id = models.CharField(max_length=50, blank=True)
    razorpay_contact_id = models.CharField(max_length=50, blank=True)
    razorpay_vpa_fund_account_id = models.CharField(
        max_length=50, blank=True, null=True
    )
    razorpay_bank_fund_account_id = models.CharField(
        max_length=50, blank=True, null=True
    )
    razorpay_payout_id = models.CharField(max_length=50, blank=True)
    razorpay_transaction_id = models.CharField(max_length=50, blank=True)
    razorpay_utr_no = models.CharField(max_length=50, blank=True)
    entity = models.CharField(max_length=50, blank=True, null=True)
    mode = models.CharField(max_length=50, blank=True, null=True)
    amount = models.FloatField(default=0)
    currency = models.CharField(max_length=50)

    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "payment_gateways"
        db_table = "payment_gateways_razorpaypayout"

    def __str__(self):
        return str(self.user.email)


class PaymentGateway(models.Model):
    provider = models.CharField(max_length=50, blank=True, null=True)
    enabled = models.BooleanField(default=False)

    active = models.BooleanField(default=False)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "payment_gateways"
        db_table = "payment_gateways_paymentgateway"

    def __str__(self):
        return str(self.provider)
