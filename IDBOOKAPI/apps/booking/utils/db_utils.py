# booking
from apps.booking.models import (
    Booking, HotelBooking, TaxRule,
    Review, BookingPaymentDetail, Review,
    BookingCommission, Invoice)

from IDBOOKAPI.utils import get_unique_id_from_time
from datetime import datetime
from pytz import timezone
from apps.log_management.models import BookingRefundLog
from django.db.models import Q
from django.db.models import FloatField
from django.db.models.fields.json import KT
from django.db.models import Avg
from django.db.models.functions import Cast, Coalesce
from apps.org_managements.utils import get_active_business
import json

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

def get_booked_hotel_booking(check_in, check_out, property_id):
    on_hold_end_time = datetime.now(timezone('UTC'))

    # filter based on check in and check out
    booked_hotel = Booking.objects.filter(
        hotel_booking__confirmed_checkin_time__lt=check_out,
        hotel_booking__confirmed_checkout_time__gt=check_in).exclude(hotel_booking__confirmed_property_id__isnull=True)

    # filter based on property id
    if property_id:
        booked_hotel = booked_hotel.filter(hotel_booking__confirmed_property_id=property_id)
   
##    booked_hotel = Booking.objects.filter(
##        Q(status='confirmed', hotel_booking__confirmed_checkin_time__lt=check_out,
##          hotel_booking__confirmed_checkout_time__gt=check_in,
##          hotel_booking__confirmed_property_id=property_id) | Q(
##              status='on_hold', hotel_booking__confirmed_checkin_time__lt=check_out,
##              hotel_booking__confirmed_checkout_time__gt=check_in,
##              hotel_booking__confirmed_property_id=property_id,
##              on_hold_end_time__gte=on_hold_end_time))

    # filter based on status and on hold time
    booked_hotel = booked_hotel.filter(
        Q(status='confirmed') | Q(status='on_hold', on_hold_end_time__gte=on_hold_end_time))

    #print(booked_hotel.query)

    if property_id:
        hotel_booking_ids = booked_hotel.values_list('hotel_booking__id', flat=True)
        return list(hotel_booking_ids)
    else:
        hotel_booking_ids = booked_hotel.values_list('hotel_booking__id', flat=True)
        property_ids = booked_hotel.values_list(
            'hotel_booking__confirmed_property_id', flat=True).distinct()
        return list(hotel_booking_ids), list(property_ids)
        

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
        booking_id=booking_id, merchant_transaction_id=merchant_transaction_id, transaction_for= "booking_confirmed")
    return booking_payment_detail

def create_booking_refund_details(booking_id, original_transaction_id, append_id):
    merchant_refund_id = None
    
    while True:
        merchant_refund_id = get_unique_id_from_time(append_id)
        if not is_merchant_refundid_exist(merchant_refund_id):
            break
        merchant_refund_id = None
    
    # Create the refund log entry
    refund_log = BookingRefundLog.objects.create(
        booking_id=booking_id,
        merchant_refund_id=merchant_refund_id,
        original_transaction_id=original_transaction_id,
        status=''
    )
    
    return refund_log

def is_merchant_refundid_exist(merchant_refund_id):
    return BookingRefundLog.objects.filter(merchant_refund_id=merchant_refund_id).exists()

def get_refund_log_by_merchant_id(merchant_refund_id):
    try:
        return BookingRefundLog.objects.get(merchant_refund_id=merchant_refund_id)
    except BookingRefundLog.DoesNotExist:
        return None
    except BookingRefundLog.MultipleObjectsReturned:
        return BookingRefundLog.objects.filter(merchant_refund_id=merchant_refund_id).order_by('-created').first()

def get_booking_from_payment(merchant_transaction_id):
    booking_payment = BookingPaymentDetail.objects.get(
        merchant_transaction_id=merchant_transaction_id)
    return booking_payment.booking.id

def update_booking_payment_details(
    merchant_transaction_id, booking_payment_details:dict):
    
    booking_payment_detail = BookingPaymentDetail.objects.filter(
        merchant_transaction_id=merchant_transaction_id).update(**booking_payment_details)

def refund_create_booking_payment_details(merchant_transaction_id, booking_payment_details: dict):

    refund_log = BookingRefundLog.objects.filter(
        merchant_refund_id=merchant_transaction_id
    ).first()
    
    if refund_log and refund_log.booking:
        return BookingPaymentDetail.objects.create(
            booking=refund_log.booking,
            merchant_transaction_id=merchant_transaction_id,
            **booking_payment_details
        )
    else:
        print(f"Error: Cannot create payment detail for {merchant_transaction_id}, booking not found in refund logs")
        return None
  
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

def get_total_property_confirmed_booking(property_id):
    total_confirmed_booking = Booking.objects.filter(
        hotel_booking__confirmed_property=property_id,
        status='confirmed').count()
    return total_confirmed_booking

def get_overall_booking_rating(property_id):
    review_obj = Review.objects.filter(
        property_id=property_id, active=True)

    # property rating
    property_review_list = review_obj.annotate(
        check_in=Cast(KT('property_review__check_in_rating'), FloatField()),
        food=Cast(KT('property_review__food_rating'), FloatField()),
        cleanliness=Cast(KT('property_review__cleanliness_rating'), FloatField()),
        comfort=Cast(KT('property_review__comfort_rating'), FloatField()),
        hotel_staff=Cast(KT('property_review__hotel_staff_rating'), FloatField()),
        facilities=Cast(KT('property_review__facilities_rating'), FloatField()),
        overall=Cast('overall_rating', FloatField())
        ).aggregate(
            check_in_rating=Coalesce(Avg('check_in'), 0, output_field=FloatField()),
            food_rating=Coalesce(Avg('food'), 0, output_field=FloatField()),
            cleanliness_rating=Coalesce(Avg('cleanliness'), 0, output_field=FloatField()),
            comfort_rating=Coalesce(Avg('comfort'), 0, output_field=FloatField()),
            hotel_staff_rating=Coalesce(Avg('hotel_staff'), 0, output_field=FloatField()),
            facilities_rating=Coalesce(Avg('facilities'), 0, output_field=FloatField()),
            overall_rating=Coalesce(Avg('overall'), 0, output_field=FloatField())
            )

    agency_review_list = review_obj.annotate(
        booking_experience=Cast(KT('agency_review__booking_experience_rating'), FloatField()),
        cancellation_experience=Cast(KT('agency_review__cancellation_experience_rating'), FloatField()),
        search_property_experience=Cast(KT('agency_review__search_property_experience_rating'), FloatField()),
        overall_agency=Cast('overall_agency_rating', FloatField())
        ).aggregate(
            booking_experience_rating=Coalesce(
                Avg('booking_experience'), 0, output_field=FloatField()),
            cancellation_experience_rating=Coalesce(
                Avg('cancellation_experience'), 0, output_field=FloatField()),
            search_property_experience_rating=Coalesce(
                Avg('search_property_experience'), 0, output_field=FloatField()),
            overall_agency_rating=Coalesce(
                Avg('overall_agency'), 0, output_field=FloatField())
            
            )

    return property_review_list, agency_review_list

def check_booking_reference_code(reference_code):
    is_exist = Booking.objects.filter(
        reference_code=reference_code).exists()
    return is_exist

def check_booking_confirmation_code(confirmation_code):
    is_exist = Booking.objects.filter(
        confirmation_code=confirmation_code).exists()
    return is_exist

def add_or_update_booking_commission(booking_id, commission_detail):
    try:
        booking_commission = BookingCommission.objects.filter(booking=booking_id)
        if booking_commission:
            booking_commission.update(**commission_detail)
        else:
            commission_detail['booking_id'] = booking_id
            booking_commission = BookingCommission(**commission_detail)
            booking_commission.save()
    except Exception as e:
        print(e)

def get_booking_commission(booking_id):
     booking_commission = BookingCommission.objects.filter(
         booking=booking_id).first()
     return booking_commission
    
def save_invoice_to_database(booking, payload_json, invoice_number):
    """
    Save invoice data to the Invoice model
    """
    try:
        payload = json.loads(payload_json)
        billed_by = get_active_business()
        
        if booking.user:
            billed_to = booking.user
        else:
            return None
        
        items = payload.get('items', [])
        
        # Calculate total_tax and total from items
        total_tax = 0
        total = 0
        gst_percentage = 0
        
        for item in items:
            if 'tax' in item and item['tax']:
                total_tax += float(item['tax'])
            if 'amount' in item and item['amount']:
                total += float(item['amount'])
            if 'gst' in item and item['gst'] and not gst_percentage:
                gst_percentage = float(item['gst'])

        # Create Invoice object
        invoice = Invoice(
            logo=payload.get('logo', ''),
            header=payload.get('header', ''),
            footer=payload.get('footer', ''),
            invoice_number=invoice_number,
            invoice_date=datetime.fromisoformat(payload.get('invoiceDate')),
            due_date=datetime.fromisoformat(payload.get('dueDate')) if payload.get('dueDate') else None,
            notes=payload.get('notes', ''),
            billed_by=billed_by,
            billed_by_details=payload.get('billedBy', {}),
            billed_to=billed_to,
            billed_to_details=payload.get('billedTo', {}),
            supply_details=payload.get('supplyDetails', {}),
            items=items,
            discount=payload.get('discount', 0),
            GST=gst_percentage,
            GST_type=payload.get('GSTType', 'CGST/SGST'),
            total=total,
            total_amount=total + total_tax,
            total_tax=total_tax,
            status=payload.get('status', 'Pending'),
            next_schedule_date=datetime.fromisoformat(payload.get('nextScheduleDate')) if payload.get('nextScheduleDate') else None,
            tags=','.join(payload.get('tags', [])),
            reference='Booking',
            created_by=str(booking.user.id) if booking.user else '',  # Use user ID
        )
        
        invoice.save()
        
        return invoice
    except Exception as e:
        print(f"Error saving invoice to database: {e}")
        return None

def update_invoice_in_database(invoice_number, payload, booking):
    """
    Update an existing invoice in the database
    """
    try:
        # If payload is a string, parse it
        if isinstance(payload, str):
            payload = json.loads(payload)
        
        # Find the invoice
        invoice = Invoice.objects.filter(invoice_number=invoice_number).first()
        if not invoice:
            return None
        
        # Update fields
        invoice.logo = payload.get('logo', invoice.logo)
        invoice.notes = payload.get('notes', invoice.notes)
        invoice.billed_by_details = payload.get('billedBy', invoice.billed_by_details)
        invoice.billed_to_details = payload.get('billedTo', invoice.billed_to_details)
        invoice.supply_details = payload.get('supplyDetails', invoice.supply_details)

        if 'items' in payload:
            items = payload.get('items', [])
            invoice.items = items

            # Recalculate total and tax
            total = 0
            total_tax = 0
            gst_percentage = 0

            for item in items:
                try:
                    if 'amount' in item:
                        total += float(item['amount'])
                    if 'tax' in item:
                        total_tax += float(item['tax'])
                    if 'gst' in item and not gst_percentage:
                        gst_percentage = float(item['gst'])
                except (ValueError, TypeError):
                    pass

            invoice.total = total
            invoice.total_tax = total_tax
            invoice.total_amount = total + total_tax
            invoice.GST = gst_percentage
        invoice.discount = payload.get('discount', invoice.discount)
        invoice.GST_type = payload.get('GSTType', invoice.GST_type)
        invoice.status = payload.get('status', invoice.status)
        
        if 'nextScheduleDate' in payload:
            invoice.next_schedule_date = datetime.fromisoformat(payload['nextScheduleDate']) if payload['nextScheduleDate'] else None

        if 'tags' in payload:
            invoice.tags = ','.join(payload['tags'])
        invoice.reference = 'Booking'
        invoice.updated_by = str(booking.user.id) if booking.user else ''
        invoice.save()

        return invoice

    except Exception as e:
        print(f"Error updating invoice in database: {e}")
        return None


def update_payment_details(booking, invoice):
    """
    Update booking payment details with invoice reference
    """
    try:
        payment_details = BookingPaymentDetail.objects.filter(booking=booking)
        
        for payment in payment_details:
            if not payment.invoice:
                payment.invoice = invoice
                payment.reference = 'Booking'

                payment.save()
            else:
                print("Invoice already exists. Skipping.")      
        return True
    except Exception as e:
        print(f"Error updating payment details: {e}")
        return False

def get_room_by_id(room_id):
    try:
        return Room.objects.get(id=room_id)
    except Room.DoesNotExist:
        return None

def get_hotelier_amount_payout(property_id):
    booking_obj = Booking.objects.filter(
        hotel_booking__confirmed_property=property_id).prefetch_related(
            'commission_info')
    booking_obj = booking_obj.filter(commission_info__booking__isnull=False,
                                     commission_info__is_payment_approved=True)
    booking_obj = booking_obj.filter(Q(commission_info__payout_status='PENDING')
                                     | Q(commission_info__payout_status='INIT-FAIL'))

    return booking_obj

            
            
    
