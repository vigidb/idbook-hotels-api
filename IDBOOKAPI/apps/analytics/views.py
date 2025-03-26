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

        if not property_id:
            return Response({'error': 'Property ID is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        if not start_date or not end_date:
            return Response({'error': 'Start date and end date are required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            india_tz = pytz.timezone('Asia/Kolkata')
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
        except ValueError:
            return Response({'error': 'Invalid date format. Use YYYY-MM-DD'}, status=status.HTTP_400_BAD_REQUEST)

        today = datetime.now(india_tz).date()
        week_start = today - timedelta(days=today.weekday())
        month_start = today.replace(day=1)

        def create_date_filter(start, end):
            return Q(created__date__gte=start, created__date__lte=end)

        date_range_filter = create_date_filter(start_date, end_date)
        today_filter = Q(created__date=today)
        week_filter = create_date_filter(week_start, today)
        month_filter = create_date_filter(month_start, today)

        stats = {
            'date_range_stats': get_booking_stats(property_id, date_range_filter, start_date, end_date),
            'today_stats': get_booking_stats(property_id, today_filter, today, today),
            'week_stats': get_booking_stats(property_id, week_filter, week_start, today),
            'month_stats': get_booking_stats(property_id, month_filter, month_start, today)
        }

        return Response(stats)

    
