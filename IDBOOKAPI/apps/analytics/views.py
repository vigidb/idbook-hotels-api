from django.shortcuts import render
from datetime import datetime

from rest_framework import viewsets
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from IDBOOKAPI.mixins import StandardResponseMixin, LoggingMixin

from apps.analytics.models import PropertyAnalytics
from apps.analytics.serializers import PropertyAnalyticsSerializer
from apps.analytics.utils.db_utils import get_property_visit

from apps.analytics.utils.analytics_utils import property_checkin_count, get_property_revenue, get_booking_stats

from datetime import datetime, timedelta
from pytz import timezone
import pytz
from django.db.models import Count, Sum, Q
from apps.booking.models import Booking

class PropertyAnalyticsViewSet(viewsets.ModelViewSet, StandardResponseMixin, LoggingMixin):
    queryset = PropertyAnalytics.objects.all()
    serializer_class = PropertyAnalyticsSerializer
    permission_classes = [IsAuthenticated]

    http_method_names = ['get']

    @action(detail=False, methods=['GET'], permission_classes=[IsAuthenticated],
            url_path='dashboard', url_name='dashboard')
    def property_analytics_dashboard(self, request):
        
        property_id = self.request.query_params.get('property', None)
        date = self.request.query_params.get('date', None)
        days = self.request.query_params.get('days', None)
        start_date, end_date = None, None

        if date:
            date = date.replace(' ', '+')
            date = datetime.strptime(date, '%Y-%m-%dT%H:%M%z').date()

        if days:
            # calculate the start and end date based on days
            end_date = datetime.now(timezone('UTC'))
            start_date = datetime.now(timezone('UTC')) - timedelta(days=int(days))
            end_date = end_date.date()
            start_date = start_date.date()


        # property visit count analytics
        property_visit_analytics = get_property_visit(property_id, date=date, start_date=start_date, end_date=end_date)
        # property check in count analytics
        property_checkin_analytics = property_checkin_count(property_id, date=date, start_date=start_date, end_date=end_date)
        # property revenue total
        property_revenue_analytics = get_property_revenue(property_id, date=date, start_date=start_date, end_date=end_date)
        
        analytics = {'property_visit': property_visit_analytics, 'property_checkin':property_checkin_analytics,
                     'property_revenue': property_revenue_analytics}
        
        
        response = self.get_response(
            data=analytics, status="success", message="Retrieve Property Analytics Success",
            count=1,
            status_code=status.HTTP_200_OK,
            )
        return response

    @action(detail=False, methods=['GET'], url_path='stats', 
        url_name='stats', permission_classes=[IsAuthenticated])
    def get_property_stats(self, request):
        property_id = request.query_params.get('property', None)
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        limit = int(request.query_params.get('limit', 10))  # Default limit to 10 days
        offset = int(request.query_params.get('offset', 0))

        if not property_id:
            return Response({'error': 'Property ID is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        if not start_date or not end_date:
            return Response({'error': 'Start date and end date are required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            india_tz = pytz.timezone('Asia/Kolkata')
            start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
            end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
        except ValueError:
            return Response({'error': 'Invalid date format. Use YYYY-MM-DD'}, status=status.HTTP_400_BAD_REQUEST)

        today = datetime.now(india_tz).date()
        week_start = today - timedelta(days=today.weekday())
        month_start = today.replace(day=1)

        def create_date_filter(start, end):
            return Q(created__date__gte=start, created__date__lte=end)

        date_range_filter = create_date_filter(start_date_obj, end_date_obj)
        today_filter = Q(created__date=today)
        week_filter = create_date_filter(week_start, today)
        month_filter = create_date_filter(month_start, today)

        stats = {
            'date_range_stats': get_booking_stats(property_id, date_range_filter, start_date_obj, end_date_obj),
            'today_stats': get_booking_stats(property_id, today_filter, today, today),
            'week_stats': get_booking_stats(property_id, week_filter, week_start, today),
            'month_stats': get_booking_stats(property_id, month_filter, month_start, today)
        }
        
        daily_stats = []
        date_range = (end_date_obj - start_date_obj).days + 1
        
        all_dates = [start_date_obj + timedelta(days=i) for i in range(date_range)]
        paginated_dates = all_dates[offset:offset+limit]
        
        bookings = Booking.objects.filter(hotel_booking__confirmed_property_id=property_id)
        
        day_counter = offset + 1  # Start day counter from offset + 1
        for current_date in paginated_dates:
            checkins = bookings.filter(
                hotel_booking__confirmed_checkin_time__date=current_date,
                is_checkin=True
            ).count()
            
            checkouts = bookings.filter(
                hotel_booking__confirmed_checkout_time__date=current_date,
                is_checkout=True
            ).count()
            
            # day_name = f"Day {day_counter} {current_date.strftime('%A')}"
            day_name = f"{current_date.strftime('%A')}"
            
            daily_stats.append({
                "day": day_name,
                "checkIn": checkins,
                "checkOut": checkouts
            })
            
            day_counter += 1
        
        weekly_stats = []
        
        week_start = start_date_obj
        week_count = 1
        
        while week_start <= end_date_obj:
            week_end = min(week_start + timedelta(days=6), end_date_obj)
            
            week_checkins = bookings.filter(
                hotel_booking__confirmed_checkin_time__date__gte=week_start,
                hotel_booking__confirmed_checkin_time__date__lte=week_end,
                is_checkin=True
            ).count()
            
            week_checkouts = bookings.filter(
                hotel_booking__confirmed_checkout_time__date__gte=week_start,
                hotel_booking__confirmed_checkout_time__date__lte=week_end,
                is_checkout=True
            ).count()

            week_name = f"Week {week_count}"
            # week_name = f"Week {week_count} ({week_start.strftime('%d %b')} - {week_end.strftime('%d %b')})"
            
            weekly_stats.append({
                "day": week_name,
                "checkIn": week_checkins,
                "checkOut": week_checkouts
            })
            
            week_start = week_end + timedelta(days=1)
            week_count += 1
        
        monthly_stats = []
        
        current_month = datetime(start_date_obj.year, start_date_obj.month, 1).date()
        last_month = datetime(end_date_obj.year, end_date_obj.month, 1).date()
        
        month_count = 1
        while current_month <= last_month:
            if current_month.month == 12:
                next_month = datetime(current_month.year + 1, 1, 1).date()
            else:
                next_month = datetime(current_month.year, current_month.month + 1, 1).date()
            
            month_end = next_month - timedelta(days=1)
            
            effective_start = max(current_month, start_date_obj)
            effective_end = min(month_end, end_date_obj)
            
            month_checkins = bookings.filter(
                hotel_booking__confirmed_checkin_time__date__gte=effective_start,
                hotel_booking__confirmed_checkin_time__date__lte=effective_end,
                is_checkin=True
            ).count()
            
            month_checkouts = bookings.filter(
                hotel_booking__confirmed_checkout_time__date__gte=effective_start,
                hotel_booking__confirmed_checkout_time__date__lte=effective_end,
                is_checkout=True
            ).count()
            
            # month_name = f"Month {month_count} {current_month.strftime('%b %Y')}"
            month_name = f"{current_month.strftime('%b')}"
            
            monthly_stats.append({
                "day": month_name,
                "checkIn": month_checkins,
                "checkOut": month_checkouts
            })
            
            if current_month.month == 12:
                current_month = datetime(current_month.year + 1, 1, 1).date()
            else:
                current_month = datetime(current_month.year, current_month.month + 1, 1).date()
            
            month_count += 1
        
        stats['data'] = {
            "daily": daily_stats,
            "weekly": weekly_stats,
            "monthly": monthly_stats
        }
        
        stats['pagination'] = {
            "total_days": date_range,
            "limit": limit,
            "offset": offset
        }

        return Response(stats)
 