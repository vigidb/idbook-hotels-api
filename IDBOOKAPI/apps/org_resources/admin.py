from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import AbstractUser, Group, Permission
from django.contrib.auth.admin import GroupAdmin, UserAdmin
# from django.contrib.auth.forms import UserChangeForm, UserCreationForm
from .models import (
    CompanyDetail, AmenityCategory, Amenity, RoomType, Occupancy, Enquiry, BankDetail,
    AboutUs, PrivacyPolicy, RefundAndCancellationPolicy,
    TermsAndConditions, Legality, Career, FAQs, Address, CountryDetails, UserNotification,
    Subscriber, MessageTemplate
)


class RoomTypeAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'created', 'active')
    list_filter = ('active', 'created', 'updated')
    search_fields = ('id', 'title')


admin.site.register(RoomType, RoomTypeAdmin)


class CompanyDetailAdmin(admin.ModelAdmin):
    list_display = ('company_name', 'company_phone', 'company_email', 'district', 'state',
                    'country', 'pin_code', 'contact_email_address')
    search_fields = ('company_name', 'company_phone', 'company_email', 'district', 'state', 'country', 'pin_code')
    list_filter = ('state', 'country')


admin.site.register(CompanyDetail, CompanyDetailAdmin)


class AmenityCategoryAdmin(admin.ModelAdmin):
    list_display = ('title', 'active', 'created', 'updated')
    search_fields = ('title',)
    list_filter = ('active', 'created', 'updated')


admin.site.register(AmenityCategory, AmenityCategoryAdmin)


class AmenityAdmin(admin.ModelAdmin):
    list_display = ('title', 'amenity_category', 'active', 'created', 'updated')
    search_fields = ('title', 'amenity_category__title')
    list_filter = ('amenity_category', 'active', 'created', 'updated')


admin.site.register(Amenity, AmenityAdmin)


class OccupancyAdmin(admin.ModelAdmin):
    list_display = ('title', 'active', 'created', 'updated')
    search_fields = ('title',)
    list_filter = ('active', 'created', 'updated')


admin.site.register(Occupancy, OccupancyAdmin)


class BankDetailAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'bank_name', 'account_holder_name', 'account_number', 'ifsc', 'upi', 'active', 'created', 'updated')
    list_filter = ('user', 'active')
    search_fields = ('user__username', 'bank_name', 'account_holder_name', 'account_number', 'ifsc', 'upi')
    readonly_fields = ('created', 'updated')


admin.site.register(BankDetail, BankDetailAdmin)


class MessageTemplateAdmin(admin.ModelAdmin):
    list_display = ('temp_id', 'temp_description', 'temp_message')
    search_fields = ('temp_id', 'temp_description')
    list_editable = ('temp_description', 'temp_message')

admin.site.register(MessageTemplate, MessageTemplateAdmin) 

admin.site.register(Enquiry)
admin.site.register(Subscriber)
admin.site.register(Address)
admin.site.register(AboutUs)
admin.site.register(PrivacyPolicy)
admin.site.register(RefundAndCancellationPolicy)
admin.site.register(TermsAndConditions)
admin.site.register(Legality)
admin.site.register(Career)
admin.site.register(FAQs)
admin.site.register(CountryDetails)
admin.site.register(UserNotification)

