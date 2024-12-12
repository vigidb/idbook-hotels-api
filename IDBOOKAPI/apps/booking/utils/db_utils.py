# booking
from apps.booking.models import (
    Booking, HotelBooking, TaxRule, Review)

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

def get_booked_room(check_in, check_out):
    booked_hotel = HotelBooking.objects.filter(
        confirmed_checkin_time__lt=check_out,
        confirmed_checkout_time__gt=check_in)
   
    booked_hotel = booked_hotel.values('confirmed_property_id', 'room_id')
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
    

        
  
        
    
    
