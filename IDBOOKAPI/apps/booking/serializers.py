from rest_framework import serializers, status
# from django.contrib.auth.models import Permission, Group
from django.core.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.permissions import BasePermission

# from apps.authentication.models import *
from .models import (
    Booking, HotelBooking, HolidayPackageBooking,
    VehicleBooking, FlightBooking, AppliedCoupon)


# from booking.models import *
# from carts.models import *
# from coupons.models import *
# from customer.models import *
# from holiday_package.models import *
# from hotel_managements.models import *
# from hotels.models import *
# from org_managements.models import *
# from apps.org_resources.models import *
# from payment_gateways.models import *
# from IDBOOKAPI.utils import format_custom_id


class BookingSerializer(serializers.ModelSerializer):
    class Meta:
        model = Booking
        fields = '__all__'

    def create_hotel_booking(self, data):
        room_type = data.get('room_type', 'DELUXE')
        checkin_time = data.get('checkin_time', '')
        print("check in time::", checkin_time)
        checkout_time = data.get('checkout_time', '')
        bed_count = data.get('bed_count', 1)
        
        enquired_property = data.get('enquired_property', '')
        booking_slot = data.get('booking_slot', '24 HOURS')

        hotel_booking = HotelBooking.objects.create(
            room_type=room_type, checkin_time=checkin_time,
            checkout_time=checkout_time, bed_count=bed_count,
            enquired_property=enquired_property,
            booking_slot=booking_slot
            )
        return hotel_booking

    def create_holidaypack_booking(self, data):
        enquired_holidaypack = data.get('enquired_holidaypack', '')
        no_days = data.get('no_days', 0)
        available_start_date = data.get('available_start_date', '')
        holidaypack_booking = HolidayPackageBooking.objects.create(
            enquired_holiday_package=enquired_holidaypack, no_days=no_days,
            available_start_date=available_start_date)
        return holidaypack_booking

    def create_vehicle_booking(self, data):
        pickup_addr = data.get('pickup_addr', '')
        dropoff_addr = data.get('dropoff_addr', '')
        pickup_time = data.get('pickup_time', '')
        vehicle_type = data.get('vehicle_type', 'CAR')

        vehicle_booking = VehicleBooking.objects.create(
            pickup_addr=pickup_addr, dropoff_addr=dropoff_addr,
            pickup_time=pickup_time, vehicle_type=vehicle_type)

        return vehicle_booking
    
    def create_flight_booking(self, data):
        flight_trip = data.get('flight_trip', 'ROUND')
        flight_class = data.get('flight_class', 'ECONOMY')
        departure_date = data.get('departure_date', '')
        return_date = data.get('return_date', '')
        flying_from = data.get('flying_from', '')
        flying_to = data.get('flying_to', '')

        flight_booking = FlightBooking.objects.create(
            flight_trip=flight_trip, flight_class=flight_class,
            departure_date=departure_date, return_date=return_date,
            flying_from=flying_from, flying_to=flying_to)

        return flight_booking   
        

    def create(self, validated_data):
        request = self.context.get('request')
        user = request.user
        
        hotel_booking, holidaypack_booking = None, None
        vehicle_booking, flight_booking = None, None
        
        booking_type = validated_data.get('booking_type', 'HOTEL')
        adult_count = validated_data.get('adult_count', 1)
        child_count = validated_data.get('child_count', 0)
        infant_count = validated_data.get('infant_count', 0)

        
        if booking_type == 'HOTEL':
            hotel_booking = self.create_hotel_booking(request.data)
            
        elif booking_type == 'HOLIDAYPACK':
            holidaypack_booking = self.create_holidaypack_booking(request.data)
            
        elif booking_type == 'VEHICLE':
            vehicle_booking = self.create_vehicle_booking(request.data)
            
        elif booking_type == 'FLIGHT':
            flight_booking = self.create_flight_booking(request.data)

        company_detail = Booking(
            user=user, booking_type=booking_type, hotel_booking=hotel_booking,
            holiday_package_booking=holidaypack_booking,
            vehicle_booking =vehicle_booking, flight_booking=flight_booking,
            adult_count=adult_count, child_count=child_count, infant_count=infant_count)
        company_detail.save()
        return company_detail

        #raise serializers.ValidationError({'message': 'Internal Server Error'})          




class AppliedCouponSerializer(serializers.ModelSerializer):
    class Meta:
        model = AppliedCoupon
        fields = '__all__'
