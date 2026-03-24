from django.contrib import admin

from .models import (
    Coupon,
    CouponPartner,
    CouponCampaign,
    CouponAmountSlab,
    CouponRedemption,
)


@admin.register(CouponPartner)
class CouponPartnerAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "partner_type", "active")
    search_fields = ("name", "display_name", "contact_email")


class CouponAmountSlabInline(admin.TabularInline):
    model = CouponAmountSlab
    extra = 0


@admin.register(CouponCampaign)
class CouponCampaignAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "partner", "active", "created")
    list_filter = ("active",)
    search_fields = ("name", "internal_code")
    inlines = [CouponAmountSlabInline]


@admin.register(CouponAmountSlab)
class CouponAmountSlabAdmin(admin.ModelAdmin):
    list_display = ("id", "campaign", "sort_order", "min_amount", "max_amount", "discount_type")


@admin.register(CouponRedemption)
class CouponRedemptionAdmin(admin.ModelAdmin):
    list_display = ("id", "coupon", "booking", "discount_applied", "status", "created")
    list_filter = ("status", "booking_type")
    raw_id_fields = ("coupon", "booking", "user")


class CouponAdmin(admin.ModelAdmin):
    list_display = ("id", "code", "name", "campaign", "discount", "active")
    list_filter = ("active",)
    search_fields = ("code", "name")
    raw_id_fields = ("campaign", "partner", "property")


admin.site.register(Coupon, CouponAdmin)
