from django.db import models
from django.core.validators import MinValueValidator
from django.core.exceptions import ValidationError
import random
import string

from IDBOOKAPI.basic_resources import BOOKING_TYPE, DISCOUNT_TYPE

from apps.hotels.models import Property


class CouponPartner(models.Model):
    """External organisation (matrimony, bank, etc.) for partner-funded campaigns."""

    name = models.CharField(max_length=200)
    partner_type = models.CharField(
        max_length=50,
        blank=True,
        default="",
        help_text="e.g. bank, pg, media, matrimony",
    )
    display_name = models.CharField(max_length=200, blank=True, default="")
    contact_email = models.EmailField(blank=True, default="")
    notes = models.TextField(blank=True, default="")
    active = models.BooleanField(default=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class CouponCampaign(models.Model):
    """Shared rules, slabs, and budgets for one or more coupon codes."""

    partner = models.ForeignKey(
        CouponPartner,
        on_delete=models.CASCADE,
        related_name="campaigns",
        null=True,
        blank=True,
    )
    name = models.CharField(max_length=200)
    internal_code = models.CharField(
        max_length=100,
        blank=True,
        default="",
        help_text="Optional reference for ops",
    )
    allowed_booking_types = models.JSONField(
        default=list,
        blank=True,
        help_text="Subset of BOOKING_TYPE values, e.g. ['HOLIDAYPACK','HOTEL']. Empty = all types.",
    )
    max_redemptions_total = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Stop after this many successful redemptions (campaign-wide).",
    )
    max_redemptions_per_user = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Max redemptions per user for this campaign.",
    )
    max_total_discount_budget = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Sum of discount_applied across redemptions must not exceed this.",
    )
    campaign_valid_from = models.DateTimeField(null=True, blank=True)
    campaign_valid_to = models.DateTimeField(null=True, blank=True)
    funding_source = models.CharField(max_length=100, blank=True, default="")
    terms_url = models.URLField(blank=True, default="")
    active = models.BooleanField(default=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created"]

    def __str__(self):
        return self.name


class CouponAmountSlab(models.Model):
    """Tiered discount by booking amount for a campaign."""

    campaign = models.ForeignKey(
        CouponCampaign,
        on_delete=models.CASCADE,
        related_name="slabs",
    )
    sort_order = models.PositiveSmallIntegerField(default=0)
    min_amount = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        validators=[MinValueValidator(0)],
    )
    max_amount = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Upper bound exclusive; null = no upper limit",
    )
    discount_type = models.CharField(
        max_length=20,
        choices=DISCOUNT_TYPE,
        default="AMOUNT",
    )
    discount_value = models.DecimalField(
        max_digits=15,
        decimal_places=4,
        validators=[MinValueValidator(0)],
    )
    max_discount_per_booking = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Cap discount for this slab",
    )

    class Meta:
        ordering = ["campaign", "sort_order", "id"]

    def clean(self):
        if self.max_amount is not None and self.max_amount <= self.min_amount:
            raise ValidationError("max_amount must be greater than min_amount")


class Coupon(models.Model):
    code = models.CharField(max_length=64, unique=True, db_index=True)
    name = models.CharField(max_length=200, blank=True, default="")
    campaign = models.ForeignKey(
        CouponCampaign,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="coupons",
    )
    partner = models.ForeignKey(
        CouponPartner,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="coupons",
    )
    is_stay_date = models.BooleanField(default=False)
    stay_start_date = models.DateField(null=True)
    stay_end_date = models.DateField(null=True)
    is_booking_date = models.BooleanField(default=False)
    booking_start_date = models.DateField(null=True)
    booking_end_date = models.DateField(null=True)
    discount_type = models.CharField(
        max_length=20, choices=DISCOUNT_TYPE, default="AMOUNT"
    )
    discount = models.DecimalField(
        max_digits=15, decimal_places=4, validators=[MinValueValidator(0)]
    )
    use_coupon_value_override = models.BooleanField(
        default=False,
        help_text=(
            "If true, when campaign slabs are configured, coupon.discount is used as a maximum "
            "discount cap (slabs still apply)."
        ),
    )
    max_redemptions_total = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Maximum successful redemptions allowed for this coupon code.",
    )
    max_redemptions_per_user = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Maximum times the same user can redeem this coupon code.",
    )
    max_total_discount_budget = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Total discount amount allowed for this coupon code across all redemptions.",
    )
    active = models.BooleanField(default=True)
    property = models.ForeignKey(
        Property, on_delete=models.CASCADE, null=True, related_name="property_coupon"
    )
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.code or str(self.pk)

    def generate_unique_code(self, length=6, prefix=""):
        characters = string.ascii_uppercase + string.digits
        while True:
            body = "".join(random.choice(characters) for _ in range(length))
            code = f"{prefix}{body}" if prefix else body
            if not Coupon.objects.filter(code=code).exists():
                return code


class CouponRedemption(models.Model):
    """Ledger row when a coupon discount is committed to a booking."""

    class RedemptionStatus(models.TextChoices):
        CONFIRMED = "confirmed", "Confirmed"
        REVERSED = "reversed", "Reversed"

    coupon = models.ForeignKey(
        Coupon, on_delete=models.CASCADE, related_name="redemptions"
    )
    booking = models.ForeignKey(
        "booking.Booking",
        on_delete=models.CASCADE,
        related_name="coupon_redemptions",
    )
    user = models.ForeignKey(
        "authentication.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="coupon_redemptions",
    )
    booking_type = models.CharField(max_length=25, choices=BOOKING_TYPE, default="HOTEL")
    booking_subtotal = models.DecimalField(
        max_digits=20,
        decimal_places=6,
        validators=[MinValueValidator(0)],
    )
    discount_applied = models.DecimalField(
        max_digits=20,
        decimal_places=6,
        validators=[MinValueValidator(0)],
    )
    status = models.CharField(
        max_length=20,
        choices=RedemptionStatus.choices,
        default=RedemptionStatus.CONFIRMED,
    )
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["booking", "coupon"],
                name="unique_coupon_redemption_per_booking",
            )
        ]
        indexes = [
            models.Index(fields=["coupon", "status"]),
            models.Index(fields=["booking", "status"]),
        ]

    def __str__(self):
        return f"{self.coupon.code} → booking {self.booking_id}"
