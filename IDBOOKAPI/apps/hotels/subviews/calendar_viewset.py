from .__init__ import *

from apps.hotels.submodels.raw_sql_models import CalendarRoom
from apps.hotels.submodels.related_models import DynamicRoomPricing
from apps.hotels.serializers import (
    CalendarRoomSerializer, DynamicRoomPricingSerializer)

from apps.hotels.utils.hotel_utils import get_room_for_calendar
from apps.hotels.utils.db_utils import (
    check_is_room_dynamic_price_set, get_dynamic_pricing)

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
        dynamic_pricing_obj = get_dynamic_pricing(property_id, start_date, end_date)
        
        # queryset = queryset[offset:offset+limit]
        serializer = CalendarRoomSerializer(queryset, many=True)
        pricing_serializer = DynamicRoomPricingSerializer(
            dynamic_pricing_obj, many=True)
        data = {"room_booked_details": serializer.data,
                "room_dynamic_pricing": pricing_serializer.data}
        
        custom_response = self.get_response(
            status="success",
            data=data,  # Use the data from the default response
            message="List Retrieved",
            count=0,
            status_code=status.HTTP_200_OK,
            )
        return custom_response


class RoomPricingCalendarViewset(viewsets.ModelViewSet, StandardResponseMixin, LoggingMixin):
    queryset = DynamicRoomPricing.objects.all()
    serializer_class = DynamicRoomPricingSerializer
    permission_classes = [IsAuthenticated,]

    def validate_create_parameters(self):
        error_list = []
        dynamic_pricing_dict = {}
        
        for_property = self.request.data.get('for_property', None)
        for_room = self.request.data.get('for_room', None)
        room_price = self.request.data.get('room_price', None)
        start_date = self.request.data.get('start_date', None)
        end_date = self.request.data.get('end_date', None)

        if not for_property:
            error_list.append({"field":"for_property", "message": "Missing property",
                               "error_code":"MISSING_PROPERTY"})
        if not for_room:
            error_list.append({"field":"for_room", "message": "Missing room",
                               "error_code":"MISSING_ROOM"})
        if not room_price:
            error_list.append({"field":"room_price", "message": "Missing room price",
                               "error_code":"MISSING_ROOM_PRICE"})

        is_start_date_valid = validate_date(start_date)
        if not is_start_date_valid:
            error_list.append({"field":"start_date", "message": "Wrong date format",
                               "error_code":"FORMAT_ERROR"})

        is_end_date_valid = validate_date(end_date)
        if not is_end_date_valid:
            error_list.append({"field":"end_date", "message": "Wrong date format",
                               "error_code":"FORMAT_ERROR"})

        if not error_list:
            is_price_set = check_is_room_dynamic_price_set(for_room, start_date, end_date)
            if is_price_set:
                error_list.append({"field":"unknown", "message": "Pricing overlaps for the given date range",
                                       "error_code":"PRICE_OVERLAPS"})

        if not error_list:
            dynamic_pricing_dict = {"for_property_id": for_property, "for_room_id":for_room,
                                    "room_price": room_price, "start_date":start_date,
                                    "end_date":end_date}


        return error_list, dynamic_pricing_dict

    def validate_update_parameters(self, instance):
        error_list = []
        
        room_price = self.request.data.get('room_price', None)
        start_date = self.request.data.get('start_date', None)
        end_date = self.request.data.get('end_date', None)

        if not room_price:
            error_list.append({"field":"room_price", "message": "Missing room price",
                               "error_code":"MISSING_ROOM_PRICE"})

        is_start_date_valid = validate_date(start_date)
        if not is_start_date_valid:
            error_list.append({"field":"start_date", "message": "Wrong date format",
                               "error_code":"FORMAT_ERROR"})

        is_end_date_valid = validate_date(end_date)
        if not is_end_date_valid:
            error_list.append({"field":"end_date", "message": "Wrong date format",
                               "error_code":"FORMAT_ERROR"})

        if not error_list:
            is_price_set = check_is_room_dynamic_price_set(instance.for_room, start_date, end_date,
                                                           instance_id=instance.id)
            if is_price_set:
                error_list.append({"field":"unknown", "message": "Pricing overlaps for the given date range",
                                       "error_code":"PRICE_OVERLAPS"})

        if not error_list:
            instance.room_price = room_price
            instance.start_date = start_date
            instance.end_date = end_date

        return error_list, instance

    def create(self, request, *args, **kwargs):
        
        error_list, dynamic_pricing_dict = self.validate_create_parameters()
        if error_list:
            response = self.get_error_response(
                message="Validation Error", status="error",
                errors=error_list, error_code="VALIDATION_ERROR",
                status_code=status.HTTP_400_BAD_REQUEST)
            return response

        
        dynamic_pricing_obj = DynamicRoomPricing.objects.create(**dynamic_pricing_dict)
        serializer = DynamicRoomPricingSerializer(dynamic_pricing_obj)

        response = self.get_response(data=serializer.data, count=1,
                                     status="success", message="Pricing Created",
                                     status_code=status.HTTP_201_CREATED)
        return response

    def partial_update(self, request, *args, **kwargs):

        # Get the object to be updated
        instance = self.get_object()
        
        error_list, instance = self.validate_update_parameters(instance)
        if error_list:
            response = self.get_error_response(
                message="Validation Error", status="error",
                errors=error_list, error_code="VALIDATION_ERROR",
                status_code=status.HTTP_400_BAD_REQUEST)
            return response

        # update data
        instance.save()
        
        serializer = DynamicRoomPricingSerializer(instance)
        response = self.get_response(data=serializer.data, count=1,
                                     status="success", message="Updated Successfully",
                                     status_code=status.HTTP_200_OK)
        return response


    @action(detail=True, methods=['PATCH'], url_path='active',
            url_name='active', permission_classes=[])
    def make_active_or_inactive(self, request, pk):
        
        active = request.data.get('active', None)
        if active is None:
            response = self.get_error_response(
                message="missing active field", status="error",
                errors=[], error_code="VALIDATION_ERROR",
                status_code=status.HTTP_400_BAD_REQUEST)
            return response

        # update active status
        instance = self.get_object()

        if active:
            is_price_set = check_is_room_dynamic_price_set(
                instance.for_room, instance.start_date, instance.end_date,
                instance_id=instance.id)
            if is_price_set:
                message = "Pricing overlaps for the given date range.You can't make it active"
                response = self.get_error_response(
                    message=message, status="error",
                    errors=[], error_code="VALIDATION_ERROR",
                status_code=status.HTTP_400_BAD_REQUEST)
                return response
        # change status
        instance.active = active
        instance.save()
        
        serializer = DynamicRoomPricingSerializer(instance)
        response = self.get_response(data=serializer.data, count=1,
                                     status="success", message="Status change success",
                                     status_code=status.HTTP_200_OK)
        return response

##    def list(self, request, *args, **kwargs):
##
##        start_date = self.request.query_params.get('start_date', '')
##        end_date = self.request.query_params.get('end_date', '')
##        property_id = self.request.query_params.get('property_id', '')
##
##        start_date = start_date.replace(' ', '+')
##        end_date = end_date.replace(' ', '+')
##
##        queryset = get_room_for_calendar(start_date, end_date, property_id)
##        
##        # queryset = queryset[offset:offset+limit]
##        serializer = CalendarRoomSerializer(queryset, many=True)
##        data = {"room_booked_details": serializer.data}
##        custom_response = self.get_response(
##            status="success",
##            data=data,  # Use the data from the default response
##            message="List Retrieved",
##            count=len(serializer.data),
##            status_code=status.HTTP_200_OK,
##            )
##        return custom_response

    
