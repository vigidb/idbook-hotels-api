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
    RoomGallery, PropertyGallery, BlockedProperty, PolicyDetails
)
from apps.hotels.submodels.related_models import (
    DynamicRoomPricing, TopDestinations)


class PropertyAdmin(admin.ModelAdmin):
    list_display = ('name', 'service_category', 'address', 'email', 'phone_no')
    search_fields = ('name', 'email', 'phone_no')


admin.site.register(Property, PropertyAdmin)


class RoomAdmin(admin.ModelAdmin):
    list_display = ('custom_id', 'room_type')
    list_filter = ('room_type',)
    # search_fields = ('property__name', 'room_type__name')


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
