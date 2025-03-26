from apps.booking.models import Booking, BookingPaymentDetail
from datetime import datetime, timedelta
from pytz import timezone
from django.db.models import Count, Sum, Q
import pytz
from apps.booking.models import Booking, BookingMetaInfo
from apps.hotels.models import Property

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
        
def get_booking_stats(property_id, filter_condition, start_date=None, end_date=None):
    bookings = Booking.objects.filter(hotel_booking__confirmed_property_id=property_id).filter(filter_condition)
    
    # Status counts from Booking model
    status_counts = bookings.values('status').annotate(count=Count('id'))
    status_dict = {item['status']: item['count'] for item in status_counts}
    
    # Get meta info for bookings within the filter condition
    meta_bookings = BookingMetaInfo.objects.filter(
        booking__hotel_booking__confirmed_property_id=property_id,
        booking_created_date__date__gte=start_date,
        booking_created_date__date__lte=end_date
    )

    # Counting meta info bookings by their states
    meta_status_counts = {
        'booking_created': meta_bookings.filter(booking_created_date__isnull=False).count(),
        'booking_confirmed': meta_bookings.filter(booking_confirmed_date__isnull=False).count(),
        'booking_cancelled': meta_bookings.filter(booking_cancelled_date__isnull=False).count(),
        'booking_completed': meta_bookings.filter(booking_completed_date__isnull=False).count(),
    }

    # Construct room stats
    room_stats = {
        'total_bookings': bookings.count(),
        'booked_rooms': bookings.aggregate(total_rooms=Sum('hotel_booking__requested_room_no'))['total_rooms'] or 0,
        
        # Booking status from Booking model
        'booking_status': {
            'pending': status_dict.get('pending', 0),
            'confirmed': status_dict.get('confirmed', 0),
            'cancelled': status_dict.get('canceled', 0),
            'completed': status_dict.get('completed', 0)
        },
        
        # Additional meta info booking counts
        'booking_done_status': {
            'booking_created': meta_status_counts['booking_created'],
            'booking_confirmed': meta_status_counts['booking_confirmed'],
            'booking_cancelled': meta_status_counts['booking_cancelled'],
            'booking_completed': meta_status_counts['booking_completed'],
        }
    }

    revenue_data = get_property_revenue(
        property_id, 
        date=start_date if start_date == end_date else None, 
        start_date=start_date, 
        end_date=end_date
    )

    total_revenue = revenue_data['date_revenue_total'] if start_date == end_date else revenue_data['drange_revenue_total']

    return {
        **room_stats,
        'checkins': bookings.filter(is_checkin=True).count(),
        'checkouts': bookings.filter(is_checkout=True).count(),
        'total_revenue': total_revenue,
    }


        
        
        

    
    
