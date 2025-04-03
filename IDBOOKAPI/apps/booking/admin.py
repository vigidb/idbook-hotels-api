from django.contrib import admin
from .models import (
    Booking, HotelBooking, HolidayPackageBooking,
    VehicleBooking, FlightBooking, TaxRule,
    BookingPaymentDetail, Review, BookingCommission)

# Register your models here.

class BookingAdmin(admin.ModelAdmin):
    list_display = ('id', 'user','booking_type', 'confirmation_code', 'invoice_id', 'status',
                    'created', 'updated')
    #search_fields = ('company_name', 'company_phone', 'company_email', 'district', 'state', 'country', 'pin_code')
    #list_filter = ('state', 'country')

class BookingPaymentAdmin(admin.ModelAdmin):
    list_display = ('id', 'booking', 'is_transaction_success', 'created', 'updated')
    
admin.site.register(Booking, BookingAdmin)
admin.site.register(HotelBooking)
admin.site.register(HolidayPackageBooking)
admin.site.register(VehicleBooking)
admin.site.register(FlightBooking)
admin.site.register(TaxRule)
admin.site.register(BookingPaymentDetail, BookingPaymentAdmin)
admin.site.register(Review)
admin.site.register(BookingCommission)
