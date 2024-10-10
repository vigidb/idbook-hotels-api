from django.contrib import admin
from .models import (
    Booking, HotelBooking, HolidayPackageBooking,
    VehicleBooking, FlightBooking)

# Register your models here.
admin.site.register(Booking)
admin.site.register(HotelBooking)
admin.site.register(HolidayPackageBooking)
admin.site.register(VehicleBooking)
admin.site.register(FlightBooking)
