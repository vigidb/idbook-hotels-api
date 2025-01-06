# booking
from apps.booking.models import (
    Booking, HotelBooking, TaxRule,
    Review, BookingPaymentDetail, Review)

from IDBOOKAPI.utils import get_unique_id_from_time
from django.db.models import Avg
from datetime import datetime
from pytz import timezone

from django.db.models import Q

def get_booking(booking_id):
    try:
        booking = Booking.objects.get(id=booking_id)
        return booking
    except Exception as e:
        return None

def get_user_based_booking(user_id, booking_id):
    booking = Booking.objects.filter(
        id=booking_id,user__id=user_id).first()
    return booking

def get_booked_room(check_in, check_out, is_slot_price_enabled=False):
    on_hold_end_time = datetime.now(timezone('UTC'))
    # status_list = ['confirmed', 'on_hold']

    if is_slot_price_enabled:

        booked_hotel = Booking.objects.filter(
            Q(status='confirmed', hotel_booking__confirmed_checkin_time__lt=check_out,
              hotel_booking__confirmed_checkout_time__gt=check_in) | Q(
                  status='on_hold', hotel_booking__confirmed_checkin_time__lt=check_out,
                  hotel_booking__confirmed_checkout_time__gt=check_in,
                  on_hold_end_time__gte=on_hold_end_time))

        
##        booked_hotel = Booking.objects.filter(
##            status__in=status_list, hotel_booking__confirmed_checkin_time__lt=check_out,
##            hotel_booking__confirmed_checkout_time__gt=check_in,
##            on_hold_end_time__gte=on_hold_end_time)
    else:
        booked_hotel = Booking.objects.filter(
            Q(status='confirmed', hotel_booking__confirmed_checkin_time__date__lt=check_out,
              hotel_booking__confirmed_checkout_time__date__gt=check_in) | Q(
                  status='on_hold', hotel_booking__confirmed_checkin_time__date__lt=check_out,
                  hotel_booking__confirmed_checkout_time__date__gt=check_in,
                  on_hold_end_time__gte=on_hold_end_time))
##        booked_hotel = Booking.objects.filter(
##            status__in=status_list, hotel_booking__confirmed_checkin_time__date__lt=check_out,
##            hotel_booking__confirmed_checkout_time__date__gt=check_in,
##            on_hold_end_time__gte=on_hold_end_time)
    
##    booked_hotel = HotelBooking.objects.filter(
##        confirmed_checkin_time__date__lt=check_out,
##        confirmed_checkout_time__date__gt=check_in)

##    print("booked hotel query---------", booked_hotel.query)
   
    booked_hotel = booked_hotel.values(
        'hotel_booking__confirmed_property_id', 'hotel_booking__room_id', 'hotel_booking__confirmed_room_details')
    return booked_hotel

def check_room_booked_details(check_in, check_out, property_id,
                              is_slot_price_enabled=False, booking_id=None):
    on_hold_end_time = datetime.now(timezone('UTC'))
    if is_slot_price_enabled:
        booked_hotel = Booking.objects.filter(
            Q(status='confirmed', hotel_booking__confirmed_checkin_time__lt=check_out,
              hotel_booking__confirmed_checkout_time__gt=check_in,
              hotel_booking__confirmed_property_id=property_id) | Q(
                  status='on_hold', hotel_booking__confirmed_checkin_time__lt=check_out,
                  hotel_booking__confirmed_checkout_time__gt=check_in,
                  hotel_booking__confirmed_property_id=property_id,
                  on_hold_end_time__gte=on_hold_end_time))
        
##        booked_hotel = Booking.objects.filter(
##            status='confirmed', hotel_booking__confirmed_checkin_time__lt=check_out,
##            hotel_booking__confirmed_checkout_time__gt=check_in,
##            hotel_booking__confirmed_property_id=property_id)

        if booking_id:
            booked_hotel = booked_hotel.exclude(Q(status='on_hold', id=booking_id))

    else:
        booked_hotel = Booking.objects.filter(
            Q(status='confirmed', hotel_booking__confirmed_checkin_time__date__lt=check_out,
            hotel_booking__confirmed_checkout_time__date__gt=check_in,
            hotel_booking__confirmed_property_id=property_id) | Q(
                status='on_hold', hotel_booking__confirmed_checkin_time__date__lt=check_out,
                hotel_booking__confirmed_checkout_time__date__gt=check_in,
                hotel_booking__confirmed_property_id=property_id,
                on_hold_end_time__gte=on_hold_end_time))
        
##        booked_hotel = Booking.objects.filter(
##            status='confirmed', hotel_booking__confirmed_checkin_time__date__lt=check_out,
##            hotel_booking__confirmed_checkout_time__date__gt=check_in,
##            hotel_booking__confirmed_property_id=property_id)

        if booking_id:
            booked_hotel = booked_hotel.exclude(Q(status='on_hold', id=booking_id))

   
    booked_hotel = booked_hotel.values(
        'id', 'hotel_booking__confirmed_property_id', 'hotel_booking__confirmed_room_details')
    return booked_hotel

def get_booking_based_tax_rule(booking_type):
    tax_rules = TaxRule.objects.filter(booking_type=booking_type).values(
        'id', 'math_compare_symbol', 'tax_rate_in_percent',
        'amount1', 'amount2')
    return tax_rules

def check_review_exist_for_booking(booking_id):
    review_exist = Review.objects.filter(booking_id=booking_id).exists()
    return review_exist

def get_user_based_applied_coupon(user_id):
    booking_coupon = Booking.objects.filter(
        user__id=user_id, status='confirmed').exclude(
            coupon_code="").values_list('coupon_code', flat=True)
    return list(booking_coupon)

def check_user_used_coupon(coupon_code, user_id):
    coupon_used = Booking.objects.filter(
        user__id=user_id, coupon_code=coupon_code,
        status='confirmed').exists()
    return coupon_used


def is_merchant_transactionid_exist(merchant_transaction_id):
    is_exist = BookingPaymentDetail.objects.filter(
        merchant_transaction_id=merchant_transaction_id).exists()
    return is_exist

def check_booking_and_transaction(booking_id, merchant_transaction_id):
    is_exist = BookingPaymentDetail.objects.filter(booking_id=booking_id,
        merchant_transaction_id=merchant_transaction_id).exists()
    return is_exist

def create_booking_payment_details(booking_id, append_id):
    merchant_transaction_id = None
    
    while True:
        merchant_transaction_id = get_unique_id_from_time(append_id)
        if not is_merchant_transactionid_exist(
            merchant_transaction_id):
            break
        merchant_transaction_id = None
            
    booking_payment_detail = BookingPaymentDetail.objects.create(
        booking_id=booking_id, merchant_transaction_id=merchant_transaction_id)
    return booking_payment_detail

def get_booking_from_payment(merchant_transaction_id):
    booking_payment = BookingPaymentDetail.objects.get(
        merchant_transaction_id=merchant_transaction_id)
    return booking_payment.booking.id

def update_booking_payment_details(
    merchant_transaction_id, booking_payment_details:dict):
    
    booking_payment_detail = BookingPaymentDetail.objects.filter(
        merchant_transaction_id=merchant_transaction_id).update(**booking_payment_details)

        
  
def get_property_based_review_count(property_id):
    total_review_count = Review.objects.filter(
        property_id=property_id,
        overall_rating__isnull=False).count()
    return total_review_count

def get_property_rating_average(property_id):
    rating_average_dict = Review.objects.filter(
        property_id=property_id,
        overall_rating__isnull=False).aggregate(Avg('overall_rating'))
    if rating_average_dict:
        rating_average = rating_average_dict.get('overall_rating__avg', 0)
        return rating_average
    else:
        return 0

def change_onhold_status():
    try:
        on_hold_end_time = datetime.now(timezone('UTC'))
        result = Booking.objects.filter(
            status='on_hold', on_hold_end_time__lt=on_hold_end_time).update(status='pending')
    except Exception as e:
        print("change on hold status::", e)
    
    
