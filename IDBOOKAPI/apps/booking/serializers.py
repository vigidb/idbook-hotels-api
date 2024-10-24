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
    def holiday_package_representation(self, holidaypack_booking):
        holiday_package_json = {}
        confirmed_hpackage_json = {}
        no_days = holidaypack_booking.no_days
        available_start_date = holidaypack_booking.available_start_date
        enquired_holiday_package = holidaypack_booking.enquired_holiday_package
        confirmed_hpackage = holidaypack_booking.confirmed_holiday_package
        if confirmed_hpackage:
            id = confirmed_hpackage.id
            trip_id = confirmed_hpackage.trip_id
            trip_name = confirmed_hpackage.trip_name
            tour_duration = confirmed_hpackage.tour_duration
            total_booking_amount = confirmed_hpackage.total_booking_amount
            confirmed_hpackage_json = {
                "trip_id":trip_id, "trip_name":trip_name,
                "tour_duration":tour_duration, "total_booking_amount":total_booking_amount}
        
        holiday_package_json = {
            'id':holidaypack_booking.id,
            'no_days':no_days, 'available_start_date':available_start_date,
            'enquired_holiday_package':enquired_holiday_package,
            'confirmed_holiday_package':confirmed_hpackage_json}
        
        return holiday_package_json

    def hotel_representation(self, hotel_booking):
        hotel_json = {}
        confirmed_property_json = {}
        room_json = {}
        
        enquired_property = hotel_booking.enquired_property
        booking_slot = hotel_booking.booking_slot
        room_type = hotel_booking.room_type
        checkin_time = hotel_booking.checkin_time
        checkout_time = hotel_booking.checkout_time
        bed_count = hotel_booking.bed_count
        
        confirmed_property = hotel_booking.confirmed_property
        if confirmed_property:
            service_category = confirmed_property.service_category
            address = confirmed_property.address
            name = confirmed_property.name
            display_name = confirmed_property.display_name
            confirmed_property_json = {
                "id":confirmed_property.id,
                "service_category":service_category,
                "name":name,
                "display_name":display_name
            }
            
        room = hotel_booking.room
        if room:
            room_type = room.room_type
            room_view = room.room_view
            bed_type = room.bed_type
            room_json = {'id':room.id, 'room_type':room_type, 'room_view':room_view,
                         'bed_type':bed_type}
        
        hotel_json = {
            'enquired_property':enquired_property, 'booking_slot':booking_slot,
            'room_type':room_type, 'checkin_time': checkin_time,
            'checkout_time':checkout_time, 'bed_count':bed_count,
            'confirmed_property':confirmed_property_json,'room':room_json}
         
        return hotel_json

    def vehicle_representation(self, vehicle_booking):
        pickup_addr = vehicle_booking.pickup_addr
        dropoff_addr = vehicle_booking.dropoff_addr
        pickup_time = vehicle_booking.pickup_time
        vehicle_type = vehicle_booking.vehicle_type

        vehicle_json = {
            'pickup_addr':pickup_addr, 'dropoff_addr':dropoff_addr,
            'pickup_time':pickup_time, 'vehicle_type':vehicle_type
        }
        return vehicle_json
             
    def flight_representation(self, flight_booking):
        flight_trip = flight_booking.flight_trip
        flight_class = flight_booking.flight_class
        departure_date = flight_booking.departure_date
        return_date = flight_booking.return_date
        flying_from = flight_booking.flying_from
        flying_to = flight_booking.flying_to

        flight_json = {'flight_trip':flight_trip, 'flight_class':flight_class,
                       'departure_date':departure_date, 'return_date':return_date,
                       'flying_from':flying_from, 'flying_to': flying_to}
        return flight_json
          

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        booking_type = instance.booking_type
        if instance:
            if booking_type == 'HOLIDAYPACK':
                holidaypack_booking = instance.holiday_package_booking
                if holidaypack_booking:
                    holiday_package_json = self.holiday_package_representation(
                        holidaypack_booking)
                    representation['holiday_package_booking'] = holiday_package_json          
            elif booking_type == 'HOTEL':
                hotel_booking = instance.hotel_booking
                if hotel_booking:
                    hotel_json = self.hotel_representation(hotel_booking)
                    representation['hotel_booking'] = hotel_json
            elif booking_type == 'VEHICLE':
                vehicle_booking = instance.vehicle_booking
                if vehicle_booking:
                    vehicle_json = self.vehicle_representation(vehicle_booking)
                    representation['vehicle_booking'] = vehicle_json
                
            elif booking_type == 'FLIGHT':
                flight_booking = instance.flight_booking
                if flight_booking:
                    flight_json = self.flight_representation(flight_booking)
                    representation['flight_booking'] = flight_json

        return representation




class AppliedCouponSerializer(serializers.ModelSerializer):
    class Meta:
        model = AppliedCoupon
        fields = '__all__'
