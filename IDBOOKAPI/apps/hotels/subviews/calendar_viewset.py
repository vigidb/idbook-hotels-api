from .__init__ import *

from apps.hotels.submodels.raw_sql_models import CalendarRoom
from apps.hotels.serializers import CalendarRoomSerializer
from apps.hotels.utils.hotel_utils import get_room_for_calendar

class PropertyCalendarViewSet(viewsets.ModelViewSet, StandardResponseMixin, LoggingMixin):
    queryset = CalendarRoom.objects.all()
    serializer_class = CalendarRoomSerializer
    permission_classes = [IsAuthenticated,]

    def list(self, request, *args, **kwargs):

        start_date = self.request.query_params.get('start_date', '')
        end_date = self.request.query_params.get('end_date', '')
        property_id = self.request.query_params.get('property_id', '')

        start_date = start_date.replace(' ', '+')
        end_date = end_date.replace(' ', '+')

        queryset = get_room_for_calendar(start_date, end_date, property_id)
        
        # queryset = queryset[offset:offset+limit]
        serializer = CalendarRoomSerializer(queryset, many=True)
        data = {"room_booked_details": serializer.data}
        custom_response = self.get_response(
            status="success",
            data=data,  # Use the data from the default response
            message="List Retrieved",
            count=len(serializer.data),
            status_code=status.HTTP_200_OK,
            )
        return custom_response

    
