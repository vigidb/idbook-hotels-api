from django.shortcuts import render
from datetime import datetime

from rest_framework import viewsets
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated

from IDBOOKAPI.mixins import StandardResponseMixin, LoggingMixin

from apps.analytics.models import PropertyAnalytics
from apps.analytics.serializers import PropertyAnalyticsSerializer
from apps.analytics.utils.db_utils import get_property_visit




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

        if date:
            date = date.replace(' ', '+')
            date = datetime.strptime(date, '%Y-%m-%dT%H:%M%z').date()

        
        property_visit_analytics = get_property_visit(property_id, date=date, no_of_days=days)
        analytics = {'property_visit': property_visit_analytics}
        
        response = self.get_response(
            data=analytics, status="success", message="Retrieve Property Analytics Success",
            count=1,
            status_code=status.HTTP_200_OK,
            )
        return response

    
