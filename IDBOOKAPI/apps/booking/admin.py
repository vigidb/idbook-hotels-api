from django.contrib import admin
from .models import (
    Booking, HotelBooking, HolidayPackageBooking,
    VehicleBooking, FlightBooking, TaxRule,
    BookingPaymentDetail, Review)

# Register your models here.

class BookingAdmin(admin.ModelAdmin):
    list_display = ('user','booking_type', 'confirmation_code', 'invoice_id')
    #search_fields = ('company_name', 'company_phone', 'company_email', 'district', 'state', 'country', 'pin_code')
    #list_filter = ('state', 'country')
    
admin.site.register(Booking, BookingAdmin)
admin.site.register(HotelBooking)
admin.site.register(HolidayPackageBooking)
admin.site.register(VehicleBooking)
admin.site.register(FlightBooking)
admin.site.register(TaxRule)
admin.site.register(BookingPaymentDetail)
admin.site.register(Review)
