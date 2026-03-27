from rest_framework import serializers

from .models import (
    Coupon,
    CouponPartner,
    CouponCampaign,
    CouponAmountSlab,
    CouponRedemption,
    UserCouponClaim,
)
from apps.coupons.services.redemption import normalize_coupon_code
from apps.booking.models import AppliedCoupon


class CouponAmountSlabSerializer(serializers.ModelSerializer):
    campaign_name = serializers.CharField(source="campaign.name", read_only=True)

    class Meta:
        model = CouponAmountSlab
        fields = "__all__"


class CouponCampaignSerializer(serializers.ModelSerializer):
    slabs = CouponAmountSlabSerializer(many=True, read_only=True)
    partner_name = serializers.CharField(source="partner.name", read_only=True)

    class Meta:
        model = CouponCampaign
        fields = "__all__"


class CouponPartnerSerializer(serializers.ModelSerializer):
    class Meta:
        model = CouponPartner
        fields = "__all__"


class CouponRedemptionSerializer(serializers.ModelSerializer):
    coupon_code = serializers.CharField(source="coupon.code", read_only=True)
    coupon_name = serializers.CharField(source="coupon.name", read_only=True)
    campaign_id = serializers.IntegerField(source="coupon.campaign_id", read_only=True)
    campaign_name = serializers.CharField(source="coupon.campaign.name", read_only=True)
    partner_id = serializers.IntegerField(source="coupon.partner_id", read_only=True)
    partner_name = serializers.CharField(source="coupon.partner.name", read_only=True)
    user_name = serializers.CharField(source="user.name", read_only=True)

    class Meta:
        model = CouponRedemption
        fields = "__all__"


class CouponSerializer(serializers.ModelSerializer):
    code = serializers.CharField(required=False, allow_blank=True)
    partner_name = serializers.CharField(source="partner.name", read_only=True)
    campaign_name = serializers.CharField(source="campaign.name", read_only=True)

    class Meta:
        model = Coupon
        fields = "__all__"

    def create(self, validated_data):
        raw_code = validated_data.pop("code", None)
        if raw_code:
            code = normalize_coupon_code(raw_code)
            if not code:
                validated_data["code"] = Coupon().generate_unique_code()
            elif Coupon.objects.filter(code__iexact=code).exists():
                raise serializers.ValidationError({"code": "This code already exists"})
            else:
                validated_data["code"] = code
        else:
            validated_data["code"] = Coupon().generate_unique_code()
        return Coupon.objects.create(**validated_data)


class CouponClaimSerializer(serializers.ModelSerializer):
    """
    Booking-applied coupon (legacy "claimed" tab in admin).
    """

    coupon_code = serializers.CharField(source="coupon.code", read_only=True)
    coupon_name = serializers.CharField(source="coupon.name", read_only=True)
    campaign_id = serializers.IntegerField(source="coupon.campaign_id", read_only=True)
    campaign_name = serializers.CharField(source="coupon.campaign.name", read_only=True)
    partner_id = serializers.IntegerField(source="coupon.partner_id", read_only=True)
    partner_name = serializers.CharField(source="coupon.partner.name", read_only=True)
    booking_id = serializers.IntegerField(source="booking.id", read_only=True)
    user_id = serializers.IntegerField(source="booking.user_id", read_only=True)
    user_name = serializers.CharField(source="booking.user.name", read_only=True)
    user_email = serializers.CharField(source="booking.user.email", read_only=True)

    class Meta:
        model = AppliedCoupon
        fields = "__all__"


class UserCouponClaimSerializer(serializers.ModelSerializer):
    coupon_code = serializers.CharField(source="coupon.code", read_only=True)
    coupon_name = serializers.CharField(source="coupon.name", read_only=True)
    campaign_id = serializers.IntegerField(source="coupon.campaign_id", read_only=True)
    campaign_name = serializers.CharField(source="coupon.campaign.name", read_only=True)
    partner_id = serializers.IntegerField(source="coupon.partner_id", read_only=True)
    partner_name = serializers.CharField(source="coupon.partner.name", read_only=True)
    user_id = serializers.IntegerField(source="user.id", read_only=True)
    user_name = serializers.CharField(source="user.name", read_only=True)
    user_email = serializers.CharField(source="user.email", read_only=True)
    redeemed_discount_so_far = serializers.SerializerMethodField()
    remaining_discount_budget = serializers.SerializerMethodField()

    class Meta:
        model = UserCouponClaim
        fields = "__all__"

    def _effective_claim_budget(self, obj):
        if obj.claimed_discount_budget is not None:
            return obj.claimed_discount_budget
        coupon = getattr(obj, "coupon", None)
        if not coupon:
            return None
        if coupon.max_total_discount_budget is not None:
            return coupon.max_total_discount_budget
        if (
            getattr(coupon, "use_coupon_value_override", False)
            and str(getattr(coupon, "discount_type", "")).upper() == "AMOUNT"
            and getattr(coupon, "discount", None) is not None
        ):
            return coupon.discount
        return None

    def get_redeemed_discount_so_far(self, obj):
        from decimal import Decimal
        from django.db.models import Sum

        s = (
            obj.coupon.redemptions.filter(
                user_id=obj.user_id,
                status="confirmed",
            ).aggregate(v=Sum("discount_applied"))["v"]
            or Decimal("0")
        )
        return str(s)

    def get_remaining_discount_budget(self, obj):
        from decimal import Decimal

        effective_budget = self._effective_claim_budget(obj)
        if effective_budget is None:
            return None
        redeemed = Decimal(str(self.get_redeemed_discount_so_far(obj) or "0"))
        rem = Decimal(str(effective_budget or 0)) - redeemed
        if rem < 0:
            rem = Decimal("0")
        return str(rem)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        effective_budget = self._effective_claim_budget(instance)
        if effective_budget is not None:
            data["claimed_discount_budget"] = str(effective_budget)
        return data
