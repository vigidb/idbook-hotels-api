from apps.booking.models import Booking, BookingPaymentDetail
from datetime import datetime, timedelta
from pytz import timezone
from django.db.models import Sum

def property_checkin_count(property_id, date=None, start_date=None, end_date=None):
    booking_analyt_obj = Booking.objects.filter(
        status='confirmed', hotel_booking__confirmed_property=property_id)

    date_checkin_count = 0
    drange_checkin_count = 0

    if date:
        booking_analyt_date_obj = booking_analyt_obj.filter(
            hotel_booking__confirmed_checkin_time__date=date)
        date_checkin_count = booking_analyt_date_obj.count()

    if start_date and end_date:
        
        booking_analyt_drange_obj = booking_analyt_obj.filter(
            hotel_booking__confirmed_checkin_time__date__lte=end_date,
            hotel_booking__confirmed_checkin_time__date__gte=start_date)

        drange_checkin_count = booking_analyt_drange_obj.count()

    property_checkin_analytics = {"date_checkin_count": date_checkin_count,
                              "drange_checkin_count": drange_checkin_count}

    return property_checkin_analytics

def get_property_revenue(property_id, date=None, start_date=None, end_date=None):
    booking_revenue_obj = BookingPaymentDetail.objects.filter(is_transaction_success=True,
                                                              booking__hotel_booking__confirmed_property=property_id)

    date_revenue_total = 0
    drange_revenue_total = 0

    if date:
        booking_revenue_date_obj = booking_revenue_obj.filter(created__date=date)
        date_revenue_total = booking_revenue_date_obj.aggregate(Sum('amount')).get('amount__sum', 0)
        if date_revenue_total:
            date_revenue_total = float(date_revenue_total)
        else:
            date_revenue_total = 0

    if start_date and end_date:
        booking_revenue_drange_obj = booking_revenue_obj.filter(created__date__lte=end_date,
                                                                created__date__gte=start_date)
        drange_revenue_total = booking_revenue_drange_obj.aggregate(Sum('amount')).get('amount__sum', 0)
        if drange_revenue_total:
            drange_revenue_total = float(drange_revenue_total)
        else:
            drange_revenue_total = 0

    property_revenue_analytics = {"date_revenue_total":date_revenue_total,
                                  "drange_revenue_total":drange_revenue_total}

    return property_revenue_analytics
        
    

        
        
        

    
    
