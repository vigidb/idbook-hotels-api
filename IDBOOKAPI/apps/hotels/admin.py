from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import AbstractUser, Group, Permission
from django.contrib.auth.admin import GroupAdmin, UserAdmin
# from django.contrib.auth.forms import UserChangeForm, UserCreationForm
from .models import (
    Property, Room, Gallery, FinancialDetail,
    HotelAmenityCategory, HotelAmenity, RoomAmenityCategory, RoomAmenity,
    RoomGallery, PropertyGallery, BlockedProperty, PolicyDetails,
    PayAtHotelSpendLimit, MonthlyPayAtHotelEligibility
)
from apps.hotels.submodels.related_models import (
    DynamicRoomPricing, TopDestinations, UnavailableProperty,
    PropertyCommission)


class PropertyAdmin(admin.ModelAdmin):
    list_display = ('name', 'service_category', 'address', 'email', 'phone_no')
    search_fields = ('name', 'email', 'phone_no')


admin.site.register(Property, PropertyAdmin)


class RoomAdmin(admin.ModelAdmin):
    list_display = ('custom_id', 'room_type')
    list_filter = ('room_type',)
    # search_fields = ('property__name', 'room_type__name')

class UnavailablePropertyAdmin(admin.ModelAdmin):
    list_display = ('search_term', 'full_params', 'created_at')
    search_fields = ('search_term',)

class PayAtHotelSpendLimitAdmin(admin.ModelAdmin):
    list_display = ('start_limit', 'end_limit', 'spend_limit', 'created', 'updated')
    list_filter = ('created', 'updated')
    search_fields = ('start_limit', 'end_limit')

class MonthlyPayAtHotelEligibilityAdmin(admin.ModelAdmin):
    list_display = ('user', 'month', 'is_eligible', 'eligible_limit', 'total_booking_count', 'created')
    list_filter = ('is_eligible', 'month')
    search_fields = ('user__email', 'month')

admin.site.register(PayAtHotelSpendLimit, PayAtHotelSpendLimitAdmin)
admin.site.register(MonthlyPayAtHotelEligibility, MonthlyPayAtHotelEligibilityAdmin)
admin.site.register(UnavailableProperty, UnavailablePropertyAdmin)

admin.site.register(Room, RoomAdmin)

admin.site.register(Gallery)
# admin.site.register(Review)
admin.site.register(FinancialDetail)
admin.site.register(HotelAmenity)
admin.site.register(HotelAmenityCategory)
admin.site.register(RoomAmenity)
admin.site.register(RoomAmenityCategory)
admin.site.register(RoomGallery)
admin.site.register(PropertyGallery)
admin.site.register(BlockedProperty)
admin.site.register(DynamicRoomPricing)
admin.site.register(PolicyDetails)
admin.site.register(TopDestinations)
admin.site.register(PropertyCommission)
