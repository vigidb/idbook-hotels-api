from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import viewsets
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import views, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.generics import (
    CreateAPIView, ListAPIView, GenericAPIView, RetrieveAPIView, UpdateAPIView
)
from IDBOOKAPI.mixins import StandardResponseMixin, LoggingMixin
from IDBOOKAPI.permissions import HasRoleModelPermission, AnonymousCanViewOnlyPermission
from IDBOOKAPI.utils import (
    paginate_queryset, validate_date, get_dates_from_range,
    get_date_from_string)

from .serializers import (
    PropertySerializer, GallerySerializer, RoomSerializer, RuleSerializer, InclusionSerializer,
    FinancialDetailSerializer, HotelAmenityCategorySerializer,
    RoomAmenityCategorySerializer, PropertyGallerySerializer, RoomGallerySerializer,
    PropertyListSerializer, PropertyRetrieveSerializer, PropertyBankDetailsSerializer,
    MonthlyPayAtHotelEligibilitySerializer)
from .serializers import BlockedPropertySerializer, RoomNameSerializer, PayAtHotelSpendLimitSerializer

from .models import (Property, Gallery, Room, Rule, Inclusion,
                     FinancialDetail, HotelAmenityCategory,
                     RoomAmenityCategory, FavoriteList,
                     PropertyBankDetails, BlockedProperty,
                     MonthlyPayAtHotelEligibility)

from .models import RoomGallery, PropertyGallery, PayAtHotelSpendLimit

from apps.hotels.utils import db_utils as hotel_db_utils
from apps.hotels.utils import hotel_policies_utils
from apps.hotels.utils import hotel_utils
from apps.booking.utils.db_utils import change_onhold_status, get_booking_based_tax_rule
from apps.analytics.utils.db_utils import create_or_update_property_count
from rest_framework.decorators import action
from apps.booking.models import Booking, HotelBooking
from django.db.models import Q, Sum
from django.contrib.auth import get_user_model
from datetime import datetime
from functools import reduce
import traceback
from .tasks import send_hotel_sms_task, send_hotel_email_task
from .mixins.validation_mixins import ValidationMixin
from apps.booking.mixins.booking_mixins import BookingMixins
User = get_user_model()

class PropertyViewSet(viewsets.ModelViewSet, StandardResponseMixin, LoggingMixin, BookingMixins):
    queryset = Property.objects.all()
    serializer_class = PropertySerializer
    serializer_action_classes = {'list': PropertyListSerializer, 'retrieve': PropertyRetrieveSerializer}
    # permission_classes = [AnonymousCanViewOnlyPermission,]
##    filter_backends = [DjangoFilterBackend]
##    filterset_fields = ['name', 'display_name', 'service_category', 'area_name', 'city_name', 'starting_price', 'rating',]
    http_method_names = ['get', 'post', 'put', 'patch']
    #lookup_field = 'custom_id'

    def get_serializer_class(self):
        try:
            return self.serializer_action_classes[self.action]
        except (KeyError, AttributeError):
            return self.serializer_class

    permission_classes_by_action = {'create': [IsAuthenticated], 'update': [IsAuthenticated],
                                    'partial_update': [IsAuthenticated],
                                    'destroy': [IsAuthenticated], 'list':[AllowAny], 'retrieve':[AllowAny]}

    def get_permissions(self):
        try: 
            return [permission() for permission in self.permission_classes_by_action[self.action]]
        except KeyError: 
            # action is not set return default permission_classes
            return [permission() for permission in self.permission_classes]

    def property_json_filter_ops(self):
        property_amenity = self.request.query_params.get('property_amenity', '')
        room_amenity = self.request.query_params.get('room_amenity', '')
        policies = self.request.query_params.get('policies', '')

        if property_amenity:
            query_prop_amenity = Q()

            property_amenity_list = property_amenity.split(',')

            for prop_amenity in property_amenity_list:
                query_prop_amenity &= Q(
                    amenity_details__contains=[{'hotel_amenity':[
                        {'title': prop_amenity.strip(), 'detail':[{'Yes': []}] }] }])

            self.queryset = self.queryset.filter(query_prop_amenity)
##        self.queryset = self.queryset.filter(
##            Q(amenity_details__contains=[{'hotel_amenity':[{'title':'Laundry', 'detail':[{'Yes': []}] }] }])
##            & Q(amenity_details__contains=[{'hotel_amenity':[{'title':'Air Conditioning', 'detail':[{'Yes': []}] }] }]))

        if room_amenity:
            property_list = hotel_db_utils.filter_property_by_room_amenity(room_amenity)
            self.queryset = self.queryset.filter(id__in=property_list)

        if policies:
            # policies_filter_dict = {"policies__property_rules__guest_profile__is_allowed_unmarried_couples__contains": "Yes"}
            # policies_filter_dict = {"policies__property_rules__property_restrictions__is_smoking_allowed__contains": "No"}

            policies_list = policies.split(',')
            query_prop_policies = Q()
            
            for policy in policies_list:
                altered_policies = "policies__" + policy.strip() + "__contains"
                policies_filter_dict = {altered_policies: "Yes"}
                query_prop_policies &= Q(**policies_filter_dict)

            self.queryset = self.queryset.filter(query_prop_policies)

##            property.filter(Q(policies__property_rules__guest_profile__is_allowed_unmarried_couples__contains='No')
##                            & Q(policies__property_rules__property_restrictions__is_smoking_allowed__contains='No'))
            


    def property_filter_ops(self):
        filter_dict = {}
        location = self.request.query_params.get('location', '')
        # user_id = self.request.query_params.get('user_id', None)
        
##        checkin_date = self.request.query_params.get('checkin', '')
##        checkout_date = self.request.query_params.get('checkout', '')

        param_dict= self.request.query_params
        for key in param_dict:
            param_value = param_dict[key]

            if key == 'location':
                loc_list = param_value.split(',')
                    
##                self.queryset = self.queryset.filter(
##                    Q(country__in=loc_list) | Q(state__in=loc_list)
##                    | Q(city_name__in=loc_list) | Q(area_name__in=loc_list))

##                query = reduce(lambda a, b: a | b,
##                               (Q(country=loc.strip()) | Q(state=loc.strip())
##                                | Q(city_name=loc.strip())
##                                | Q(area_name__icontains=loc.strip()) for loc in loc_list),)

                query = reduce(lambda a, b: a | b,
                               (Q(area_name__icontains=loc.strip())
                                | Q(city_name=loc.strip())
                                | Q(state=loc.strip())
                                | Q(country=loc.strip())
                                | Q(name__icontains=param_value.strip())
                                | Q(title__icontains=param_value.strip()) for loc in loc_list),)

##                query = reduce(lambda a, b: a | b,
##                               (Q(city_name=loc) for loc in loc_list),)
##                print("query::", query)
                self.queryset = self.queryset.filter(query)
                
##                self.queryset = self.queryset.filter(
##                    Q(country__icontains=param_value) | Q(state__icontains=param_value)
##                    | Q(city_name__icontains=param_value) | Q(area_name__icontains=param_value))

            if key == 'property_search':
                query = Q(name__icontains=param_value.strip()) | Q(title__icontains=param_value.strip())
                self.queryset = self.queryset.filter(query)

            if key == 'property_id':
                self.queryset = self.queryset.filter(id=param_value)

            if key == 'is_favorite':
                if param_value == "True":
                    self.queryset = self.queryset.filter(id__in=self.favorite_list)
                elif param_value == "False":
                    self.queryset = self.queryset.exclude(id__in=self.favorite_list)
                
                
            if key == 'user':
                user_filter = Q(added_by=param_value) | Q(managed_by=param_value)
                self.queryset = self.queryset.filter(user_filter)

            if key == 'rating':
                rating_list = param_value.split(',')
                filter_dict['rating__in'] = rating_list

            if key == 'property_type':
                property_type_list = param_value.split(',')
                filter_dict['property_type__in'] = property_type_list

            if key == 'room_type':
                room_type_list = param_value.split(',')
                filter_dict['property_room__room_type__in'] = room_type_list

            if key == 'room_view':
                room_view_list = param_value.split(',')
                filter_dict['property_room__room_view__in'] = room_view_list

            if key == 'start_review_star':
               start_review_star = param_value
               filter_dict['review_star__gte'] = start_review_star
            if key == 'end_review_star':
               end_review_star = param_value
               filter_dict['review_star__lt'] = end_review_star 

            if key in ('country', 'state', 'city_name', 'area_name', 'status'):
                filter_dict[key] = param_value

            if key == 'pay_at_hotel':
                if param_value.lower() == 'true':
                    filter_dict['pay_at_hotel'] = True
                elif param_value.lower() == 'false':
                    filter_dict['pay_at_hotel'] = False

            if key.startswith('policies__'):
                policies_value_list = param_value.split(',')
                query_policy = Q()
                for policies_value in policies_value_list:
                    policies_contains = key + "__contains"
                    policies_filter_dict = {policies_contains: policies_value}
                    query_policy|= Q(**policies_filter_dict)

                self.queryset = self.queryset.filter(query_policy) 
                

        # filter based on price range
        start_price = self.request.query_params.get('start_price', None)
        end_price = self.request.query_params.get('end_price', None)
        if start_price is not None and end_price is not None:
            property_list = hotel_db_utils.get_property_from_price_range(int(start_price), int(end_price))
            self.queryset = self.queryset.filter(id__in=property_list)

        # filter based on slot based property
        is_slot_price_enabled = self.request.query_params.get('is_slot_price_enabled', 'false')
        is_slot_price_enabled = True if is_slot_price_enabled == "true" else False
        
        if is_slot_price_enabled:
            property_slot_list = hotel_db_utils.get_slot_price_enabled_property()
            self.queryset = self.queryset.filter(id__in=property_slot_list)

        if filter_dict:
            self.queryset = self.queryset.filter(**filter_dict)


    def property_order_ops(self):
        ordering_params = self.request.query_params.get('ordering', None)
        if ordering_params:
            ordering_list = ordering_params.split(',')
            self.queryset = self.queryset.order_by(*ordering_list)
            # print(self.queryset.query)

        

    def checkin_checkout_based_filter(self):
        checkin_date = self.request.query_params.get('checkin', '')
        checkout_date = self.request.query_params.get('checkout', '')
##        is_slot_price_enabled = self.request.query_params.get('is_slot_price_enabled', 'false')
##        is_slot_price_enabled = True if is_slot_price_enabled == "true" else False
        
        self.checkin_date = checkin_date
        
        available_property_dict = {}
        nonavailable_property_list = []

        if checkin_date and checkout_date:
            
##            if not is_slot_price_enabled:
##                checkin_date = datetime.strptime(checkin_date, '%Y-%m-%d').date()
##                checkout_date = datetime.strptime(checkout_date, '%Y-%m-%d').date()
##            else:
##                checkin_date = checkin_date.replace(' ', '+')
##                checkout_date = checkout_date.replace(' ', '+')
##                checkin_date = datetime.strptime(checkin_date, '%Y-%m-%dT%H:%M%z')
##                checkout_date = datetime.strptime(checkout_date, '%Y-%m-%dT%H:%M%z')
            
            checkin_date = checkin_date.replace(' ', '+')
            checkout_date = checkout_date.replace(' ', '+')
            checkin_date = datetime.strptime(checkin_date, '%Y-%m-%dT%H:%M%z')
            checkout_date = datetime.strptime(checkout_date, '%Y-%m-%dT%H:%M%z')

            self.checkin_date = checkin_date
            self.checkin_datetime = checkin_date
            self.checkout_datetime = checkout_date
##            booked_hotel_dict = hotel_utils.get_booked_property(checkin_date, checkout_date, True)
            
            nonavailable_property_list, available_property_dict = hotel_utils.get_filled_property_list(checkin_date, checkout_date)
            # print("booked hotel dict::", booked_hotel_dict)
            # property details from booking
            
##            nonavailable_property_list, available_property_dict = \
##                                        hotel_utils.get_available_property(booked_hotel_dict)

            
##            print("Non available property list::", nonavailable_property_list)
##            print("available property list::", available_property_dict)

            
            # exclude non available property list
##            if nonavailable_property_list:
##                self.queryset = self.queryset.exclude(id__in=nonavailable_property_list)

        return available_property_dict, nonavailable_property_list

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context.update({"slug": self.slug})
        return context

    def calculate_complete_pricing_details(self, request, queryset, available_property_dict, nonavailable_property_list):
        adult_count = int(request.query_params.get('adult_count', 1))
        child_count = int(request.query_params.get('child_count', 0))
        child_age_list = request.query_params.get('child_age_list', [])
        booking_slot = request.query_params.get('booking_slot', '24 Hrs')

        if isinstance(child_age_list, str) and child_age_list:
            try:
                child_age_list = [int(age.strip()) for age in child_age_list.split(',')]
            except:
                child_age_list = []

        complete_pricing_details = {}

        for property_obj in queryset:
            property_id = property_obj.id
            
            try:
                self.property_id = property_id
                self.adult_count = adult_count
                self.child_count = child_count
                self.child_age_list = child_age_list
                self.booking_slot = booking_slot
                self.no_of_days = (self.checkout_datetime - self.checkin_datetime).days

                mock_request = type('obj', (object,), {'data': {'adult_count': adult_count, 'child_count': child_count, 'booking_slot': booking_slot}})
                is_allocated, allocation_response = self.auto_room_allocation(mock_request, property_id)
                
                if not is_allocated:
                    error_message = getattr(allocation_response.data, 'message', 'Could not find enough rooms to accommodate all guests')
                    error_code = getattr(allocation_response.data, 'error_code', 'INADEQUATE_ROOMS')
                    
                    complete_pricing_details[property_id] = {
                        'status': 'error',
                        'error': {
                            'message': error_message,
                            'error_code': error_code
                        }
                    }
                    continue
                
                self.room_dprice_dict, self.date_list, self.dprice_roomids = self.get_dynamic_pricing_applicable_room(
                    self.checkin_datetime.date(), self.checkout_datetime.date())

                is_status, allocation_response = self.room_allocation()
                if not is_status:
                    error_message = getattr(allocation_response.data, 'message', 'Room allocation failed')
                    error_code = getattr(allocation_response.data, 'error_code', 'ALLOCATION_ERROR')
                    
                    complete_pricing_details[property_id] = {
                        'status': 'error',
                        'error': {
                            'message': error_message,
                            'error_code': error_code
                        }
                    }
                    continue
                
                self.confirmed_room_details = []
                self.final_amount = 0
                self.final_tax_amount = 0
                self.subtotal = 0
                self.tax_rules_dict = get_booking_based_tax_rule('HOTEL')

                is_cal_status, calculation_response = self.amount_calculation()
                if not is_cal_status:
                    error_message = getattr(calculation_response.data, 'message', 'Price calculation failed')
                    error_code = getattr(calculation_response.data, 'error_code', 'CALCULATION_ERROR')
                    
                    complete_pricing_details[property_id] = {
                        'status': 'error',
                        'error': {
                            'message': error_message,
                            'error_code': error_code
                        }
                    }
                    continue
                
                total_final_amount = sum(room_detail.get('final_room_total', 0) for room_detail in self.confirmed_room_details)
                
                complete_pricing_details[property_id] = {
                    'status': 'success',
                    'room_list': self.room_list,
                    'detailed_pricing': {
                        'rooms_pricing': self.confirmed_room_details,
                        'subtotal': self.subtotal,
                        'gst_amount': self.final_tax_amount,
                        'final_amount': total_final_amount
                    }
                }

            except Exception as e:
                print(f"Error calculating complete pricing for property {property_id}: {str(e)}")
                complete_pricing_details[property_id] = {
                    'status': 'error',
                    'error': {
                        'message': f"An error occurred during calculation: {str(e)}",
                        'error_code': "CALCULATION_EXCEPTION"
                    }
                }
        
        return complete_pricing_details
            

    def create(self, request, *args, **kwargs):
        self.log_request(request)  # Log the incoming request

        #self.get_serializer_context()
        
        city_name = request.data.get('city_name', '')
        name = request.data.get('name', '')
        slug = request.data.get('slug', '')
        
        if slug:
            slug_exist, slug = hotel_db_utils.check_property_slug(slug)
            if slug_exist:
                custom_response = self.get_error_response(
                    message="Duplicate slug", status="error",
                    errors=[],error_code="DUPLICATE_SLUG",
                    status_code=status.HTTP_400_BAD_REQUEST)
                return custom_response       
            
        if name and not slug:
            slug_exist, slug = hotel_db_utils.check_property_slug(name)
            if slug_exist and city_name:
                slug = f"{name}-{city_name}"
                slug_exist, slug = hotel_db_utils.check_property_slug(slug)

            if slug_exist:
                custom_response = self.get_error_response(
                    message="Duplicate slug", status="error",
                    errors=[],error_code="DUPLICATE_SLUG",
                    status_code=status.HTTP_400_BAD_REQUEST)
                return custom_response
                    
                
        self.slug = slug
        # Create an instance of your serializer with the request data
        serializer = self.get_serializer(data=request.data)

        if serializer.is_valid():
            # If the serializer is valid, perform the default creation logic
            response = super().create(request, *args, **kwargs)

            city = response.data.get('city_name', '')
            state = response.data.get('state', '')
            country = response.data.get('country', '')
            prop_status = response.data.get('status', '')
            location_list = [city, state, country]
            if prop_status=='Active' and (city or state or country):
                hotel_db_utils.process_property_based_topdest_count(location_list)

            # Create a custom response
            custom_response = self.get_response(
                data=response.data,  # Use the data from the default response
                count=1,
                status="success",
                message="Property Created",
                status_code=status.HTTP_201_CREATED,  # 201 for successful creation

            )
        else:
            # If the serializer is not valid, create a custom response with error details
            serializer_errors = self.custom_serializer_error(serializer.errors)
            custom_response = self.get_error_response(message="Validation Error", status="error",
                                                      errors=serializer_errors,error_code="VALIDATION_ERROR",
                                                      status_code=status.HTTP_400_BAD_REQUEST)

        self.log_response(custom_response)  # Log the custom response before returning
        return custom_response

    def update(self, request, *args, **kwargs):
        self.log_request(request)  # Log the incoming request

        # Get the object to be updated
        instance = self.get_object()
        
        # Create an instance of your serializer with the request data and the object to be updated
        serializer = self.get_serializer(instance, data=request.data)

        if serializer.is_valid():
            # If the serializer is valid, perform the default update logic
            response = super().update(request, *args, **kwargs)

            # Create a custom response
            custom_response = self.get_response(
                data=response.data,  # Use the data from the default response
                count=1,
                status="success",
                message="Property Updated",
                status_code=status.HTTP_200_OK,  # 200 for successful update

            )
        else:
            # If the serializer is not valid, create a custom response with error details
            serializer_errors = self.custom_serializer_error(serializer.errors)
            custom_response = self.get_error_response(message="Validation Error", status="error",
                                                      errors=serializer_errors,error_code="VALIDATION_ERROR",
                                                      status_code=status.HTTP_400_BAD_REQUEST)

        self.log_response(custom_response)  # Log the custom response before returning
        return custom_response

    def partial_update(self, request, *args, **kwargs):
        # self.log_request(request)  # Log the incoming request
        # print(dir(self))
        # Get the object to be updated
        instance = self.get_object()
        
        slug = request.data.get('slug', '')
        if slug:
            slug_exist, slug = hotel_db_utils.check_property_slug(
                slug, exclude=instance.id)
            if slug_exist:
                custom_response = self.get_error_response(
                    message="Duplicate slug", status="error",
                    errors=[],error_code="DUPLICATE_SLUG",
                    status_code=status.HTTP_400_BAD_REQUEST)
                return custom_response 
        
        self.slug = ""
        # Create an instance of your serializer with the request data and the object to be updated
        serializer = self.get_serializer(instance, data=request.data, partial=True)

        if serializer.is_valid():
            # If the serializer is valid, perform the default update logic
            #response = super().partial_update(request, *args, **kwargs)
            response = self.perform_update(serializer)

            city = serializer.data.get('city_name', '')
            state = serializer.data.get('state', '')
            country = serializer.data.get('country', '')
            prop_status = request.data.get('status', '')
            location_list = [city, state, country]
            
            if prop_status=='Active' and (city or state or country):
                hotel_db_utils.process_property_based_topdest_count(location_list)

            if prop_status == 'Active':
                send_hotel_sms_task.apply_async(
                    kwargs={'notification_type': 'HOTEL_PROPERTY_ACTIVATION', 'params': {'property_id': instance.id}}
                )

                send_hotel_email_task.apply_async(
                    kwargs={'notification_type': 'HOTEL_PROPERTY_ACTIVATION', 'params': {'property_id': instance.id}}
                )
            elif prop_status == 'In-Active':
                send_hotel_sms_task.apply_async(
                    kwargs={'notification_type': 'HOTEL_PROPERTY_DEACTIVATION', 'params': {'property_id': instance.id}}
                )

            elif prop_status == 'Completed':
                send_hotel_sms_task.apply_async(
                    kwargs={'notification_type': 'HOTEL_PROPERTY_SUBMISSION', 'params': {'property_id': instance.id}}
                )
            # Create a custom response
            custom_response = self.get_response(
                data=serializer.data,  # Use the data from the default response
                count=1,
                status="success",
                message="Property Updated",
                status_code=status.HTTP_200_OK,  # 200 for successful update

            )
        else:
            # If the serializer is not valid, create a custom response with error details
            serializer_errors = self.custom_serializer_error(serializer.errors)
            custom_response = self.get_error_response(message="Validation Error", status="error",
                                                      errors=serializer_errors,error_code="VALIDATION_ERROR",
                                                      status_code=status.HTTP_400_BAD_REQUEST)

        # self.log_response(custom_response)  # Log the custom response before returning
        return custom_response

    def list(self, request, *args, **kwargs):
        self.log_request(request)  # Log the incoming request
        self.favorite_list = []

        # update the on hold status to pending 
        change_onhold_status()

        if request.user and request.user.id:
            self.favorite_list = hotel_db_utils.get_favorite_property(request.user.id)
        
        # apply property filter
        self.property_filter_ops()
        self.property_json_filter_ops()



        # filter for checkin checkout
        available_property_dict, nonavailable_property_list = self.checkin_checkout_based_filter()

        # self.queryset = self.queryset.distinct('id')
        
        # duplicate entry created due to filter based join operation
        # fetch distint property id
        self.queryset = self.queryset.distinct()

        # fetch the lowest price
        booking_slot = self.request.query_params.get('booking_slot', '24 Hrs')
        self.queryset = hotel_db_utils.get_lowest_property_pricing(self.queryset, self.checkin_date, booking_slot)

        # fetch based on nearby location
        nearby_latitude = self.request.query_params.get('nearby_latitude', '')
        nearby_longitude = self.request.query_params.get('nearby_longitude', '')
        if nearby_latitude and nearby_longitude:
            self.queryset = hotel_db_utils.get_property_distance(
                self.queryset, nearby_latitude, nearby_longitude)
            self.queryset = self.queryset.order_by('distance')
            

        # ordering
        self.property_order_ops()
        
        # paginate the result
        count, self.queryset = paginate_queryset(self.request,  self.queryset)
##        self.queryset = self.queryset.values('id','name', 'title', 'property_type',
##                                             'rental_form', 'review_star', 'review_count',
##                                             'additional_fields', 'area_name',
##                                             'city_name', 'state', 'country',
##                                             'rating', 'status', 'current_page',
##                    is_slot_price_enabled                         'address')
        if count == 0:
            hotel_db_utils.save_unavailable_property_search(request.query_params)

        complete_pricing_details = self.calculate_complete_pricing_details(
            request, self.queryset, available_property_dict, nonavailable_property_list
        )
        
        # Perform the default listing logic
        response = PropertyListSerializer(
            self.queryset, many=True,
            context={
                'available_property_dict': available_property_dict,
                'favorite_list': self.favorite_list,
                'nonavailable_property_list': nonavailable_property_list,
                'complete_pricing_details': complete_pricing_details
            })

        custom_response = self.get_response(
            count=count, status="success",
            data=response.data,
            message="List Retrieved",
            status_code=status.HTTP_200_OK
        )

        self.log_response(custom_response)
        return custom_response

    def retrieve(self, request, *args, **kwargs):
        self.log_request(request)  # Log the incoming request
        
        pk = kwargs.get('pk')
        if isinstance(pk, str) and not pk.isdigit():
            instance = Property.objects.filter(slug=pk)
        else:
            instance = Property.objects.filter(id=pk)

        if not instance:
            custom_response = self.get_error_response(message="Property not found", status="error",
                                                      errors=[],error_code="PROPERTY_MISSING",
                                                      status_code=status.HTTP_404_NOT_FOUND)
            return custom_response

        

        checkin_date = self.request.query_params.get('checkin', '')
        checkout_date = self.request.query_params.get('checkout', '')
        booking_slot = self.request.query_params.get('booking_slot', '24 Hrs')
        start_date = ''

        
        
        if checkin_date and checkout_date:
            checkin_date = checkin_date.replace(' ', '+')
            checkout_date = checkout_date.replace(' ', '+')
            
            start_date = get_date_from_string(checkin_date)
            end_date = get_date_from_string(checkout_date)
            
            if not start_date or not end_date:
                custom_response = self.get_error_response(
                    message="Error in Date Format", status="error",
                    errors=[],error_code="DATE_FORMAT_ERROR",
                    status_code=status.HTTP_400_BAD_REQUEST)
                return custom_response
                
            date_list = get_dates_from_range(start_date.date(), end_date.date())
            if len(date_list) >= 2:
                date_list.pop()
            #date_list={"date_list": date_list}
        else:
            date_list=[]
            
        instance = hotel_db_utils.get_lowest_property_pricing(instance, start_date, booking_slot)
        instance = instance.first()
           
        user_id = request.user.id
        context={"date_list": date_list, "user_id":user_id} 
        response = PropertyRetrieveSerializer(instance,  context=context)

        property_id = instance.id
        if user_id and property_id:
            create_or_update_property_count(property_id, user_id)

        custom_response = self.get_response(
            count=1, status="success",
            data=response.data,  # Use the data from the default response
            message="List Retrieved",
            status_code=status.HTTP_200_OK,  # 200 for successful listing
            )

        return custom_response

##        print("-----", request.data.get('sample'))
##        available_rooms = self.request.query_params.get('available_rooms')
##        print("--- available rooms", type(available_rooms))
##
##        available_room_after_booking = {"1": 5, "2": 3}
##
##        instance = self.get_object()
##        response = PropertyRetrieveSerializer(
##            instance, context={'available_room_after_booking': available_room_after_booking})

##        custom_response = self.get_response(
##            count=1, status="success",
##            data=response.data,  # Use the data from the default response
##            message="List Retrieved",
##            status_code=status.HTTP_200_OK,  # 200 for successful listing
##            )

##        # Perform the default retrieval logic
##        response = super().retrieve(request, *args, **kwargs)
##
##        if response.status_code == status.HTTP_200_OK:
##            # If the response status code is OK (200), it's a successful retrieval
##            custom_response = self.get_response(
##                data=response.data,  # Use the data from the default response,
##                count=1,
##                status="success",
##                message="Item Retrieved",
##                status_code=status.HTTP_200_OK,  # 200 for successful retrieval
##
##            )
##            property_id = response.data.get('id', None)
##            if user_id and property_id:
##                create_or_update_property_count(property_id, user_id)
##        else:
##            # If the response status code is not OK, it's an error
##            custom_response = self.get_error_response(message="Error Occured", status="error",
##                                                      errors=[],error_code="ERROR",
##                                                      status_code=response.status_code)
##
##        self.log_response(custom_response)  # Log the custom response before returning
##        return custom_response

    @action(detail=False, methods=['POST'], url_path='media',
            url_name='media', permission_classes=[IsAuthenticated])
    def upload_media(self, request):
        self.log_request(request)
        
        property_id = request.data.get('property', None)
        property_gallery_list = []
        media = request.FILES
        media_count = 0

        if not media:
            response = self.get_error_response(message="Media file missing",
                                               status="error",
                                               errors=[],error_code="MEDIA_FILE_MISSING",
                                               status_code=status.HTTP_400_BAD_REQUEST)
            self.log_response(response)
            return response

        property_details = hotel_db_utils.get_property_by_id(property_id)
        if not property_details:
            response = self.get_error_response(message="Property not found", status="error",
                                               errors=[],error_code="PROPERTY_NOT_FOUND",
                                               status_code=status.HTTP_400_BAD_REQUEST)
            
            self.log_response(response)
            return response

        # Bulk upload media
        try:
            for media_data in media.values():
                image_name = media_data.name
                property_gallery = PropertyGallery(media=media_data, property_id=property_id)
                property_gallery_list.append(property_gallery)
        
            if property_gallery_list:
                bulk_create = PropertyGallery.objects.bulk_create(property_gallery_list)
                media_count = len(bulk_create)
        except Exception as e:
            response = self.get_error_response(message=str(e), status="error",
                                               errors=[],error_code="INTERNAL_SERVER_ERROR",
                                               status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
            self.log_response(response)
            return response

            
        if media_count:
            gallery_objs = PropertyGallery.objects.filter(property_id=property_id)
            count = gallery_objs.count()
            serializer = PropertyGallerySerializer(gallery_objs, many=True)
            response = self.get_response(data=serializer.data, count=count,
                                         status="success", message="Media Upload Success",
                                         status_code=status.HTTP_200_OK)

        else:
            response = self.get_error_response(message="Media not uploaded",
                                               status="error",
                                               errors=[],error_code="MEDIA_UPLOAD_ERROR",
                                               status_code=status.HTTP_400_BAD_REQUEST)
            
        self.log_response(response)
        return response

    @action(detail=False, methods=['GET'], url_path='media/list',
            url_name='media-list', permission_classes=[AllowAny])
    def list_media(self, request):
        self.log_request(request)
        property_id = self.request.query_params.get('property', None)
        
        property_gallery = hotel_db_utils.get_property_gallery(property_id)
        count, property_gallery = paginate_queryset(self.request,  property_gallery)
        serializer = PropertyGallerySerializer(property_gallery, many=True)
        
        response = self.get_response(data=serializer.data, count = count,
                                     status="success", message="List Property Gallery",
                                     status_code=status.HTTP_200_OK)
        return response

    @action(detail=False, methods=['POST'], url_path='media/inactive',
            url_name='media-inactive', permission_classes=[IsAuthenticated])
    def make_media_inactive(self, request):

        image_ids = request.data.get('image_ids', [])
        active = request.data.get('active', False)
        
        if not image_ids and not isinstance(image_ids, list):
            custom_response = self.get_error_response(
                message="Invalid Ids", status="error", errors=[],
                error_code="INVALID_ID", status_code=status.HTTP_400_BAD_REQUEST)
            return custom_response

        # make media active or inactive
        update_status = PropertyGallery.objects.filter(id__in=image_ids).update(active=active)
            
        custom_response = self.get_response(
            data={},  # Use the data from the default response
            message="Success",
            count=update_status,
            status_code=status.HTTP_200_OK,  # 200 for successful update
        )
        return custom_response 

    @action(detail=False, methods=['GET'], url_path='favorite/list',
            url_name='favorite', permission_classes=[IsAuthenticated])
    def get_favorite_property(self, request):
        user = self.request.user
        
        queryset = FavoriteList.objects.filter(user_id=user.id, property__isnull=False)
        count, queryset = paginate_queryset(self.request, queryset)

        favorite_list = list(queryset.values_list('property_id', flat=True))
        print("favorite list::", favorite_list)
        
        self.queryset = self.queryset.filter(id__in = favorite_list)
##        .values(
##            'id','name', 'title', 'area_name', 'city_name',
##            'state', 'country','rating', 'status')

        response = PropertyListSerializer(
            self.queryset, many=True)
        # response = super().list(request, *args, **kwargs)

        custom_response = self.get_response(
            count=count, status="success",
            data=response.data,  # Use the data from the default response
            message="Favorite Property List Retrieved",
            status_code=status.HTTP_200_OK,  # 200 for successful listing
            )

        self.log_response(custom_response)  # Log the custom response before returning
        return custom_response

    @action(detail=False, methods=['POST'], url_path='favorite',
            url_name='add-favorite', permission_classes=[IsAuthenticated])
    def add_favorite_property(self, request):
        user = request.user
        property_id = request.data.get('property', None)

        if not property_id:
            response = self.get_error_response(message="Property missing",
                                               status="error",
                                               errors=[],error_code="PROPERTY_MISSING",
                                               status_code=status.HTTP_400_BAD_REQUEST)
            self.log_response(response)
            return response
        try:
            favorite_list = FavoriteList.objects.filter(user=user, property_id=property_id)
            if favorite_list:
                favorite_list.delete()
                response = self.get_response(data=None, count=1,
                                             status="success", message="Property removed from favorite list",
                                             status_code=status.HTTP_200_OK)
                return response
                
            else:
                FavoriteList.objects.create(user=user, property_id=property_id)
                response = self.get_response(data=None, count=1,
                                             status="success", message="Property added to favorite list",
                                             status_code=status.HTTP_200_OK)
                return response
        except Exception as e:
            response = self.get_error_response(message=str(e),
                                               status="error",
                                               errors=[],error_code="ERROR",
                                               status_code=status.HTTP_400_BAD_REQUEST)
            self.log_response(response)
            return response

    @action(detail=False, methods=['GET'], url_path='price-range',
            url_name='price-range', permission_classes=[AllowAny])
    def get_price_range(self, request):
        try:
            location = request.query_params.get('location', '')
            slot = request.query_params.get('slot', '24 Hrs')
            location_list = []
            if location:
                location_list = location.split(',')
                
            min_price, max_price = hotel_db_utils.get_price_range(
                location_list=location_list, slot=slot)
            if min_price:
                min_price = int(min_price.get('min', 0))
            else:
                min_price = 0

            if max_price:
                max_price = int(max_price.get('max', 0))
            else:
                max_price = 0
                
            price_range = {"min_price":min_price, "max_price":max_price}
            response = self.get_response(data=price_range, count=1,
                                         status="success", message="Price range",
                                         status_code=status.HTTP_200_OK)
        except Exception as e:
            print(traceback.format_exc())
            response = self.get_error_response(message=str(e), status="error",
                                               errors=[],error_code="PRICE_ERROR",
                                               status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
        return response     
        

    @action(detail=False, methods=['GET'], url_path='policy/structure',
            url_name='policy-structure', permission_classes=[AllowAny])
    def get_policy_data_structure(self, request):
        self.log_request(request)
        hotel_policies = hotel_policies_utils.default_hotel_policy_json()
        response = self.get_response(data=hotel_policies, count = 1,
                                     status="success", message="List Hotel Policies Data Structure",
                                     status_code=status.HTTP_200_OK)
        return response

    @action(detail=False, methods=['GET'], url_path='location/autosuggest',
            url_name='location-autosuggest', permission_classes=[AllowAny])
    def get_location_suggestion(self, request):
        location = self.request.query_params.get('location', '')
        user_query = self.request.query_params.get('user_query', '')
        property_status = self.request.query_params.get('status', '')
        autosuggest_list = []
        autosuggest_dict = {}

        if location:
            location = location.strip()

        if user_query:
            user_query = user_query.strip()
            location = user_query
            #property_info = user_query

        if property_status:
            self.queryset = self.queryset.filter(status=property_status)

        # city highlighted queryset
        location_queryset = self.queryset.filter(Q(city_name__icontains=location)
                                                 | Q(state__icontains=location)
                                                 | Q(country__icontains=location)).exclude(state='', country='')
        if location_queryset.count():
            obj_list = location_queryset.values('city_name', 'state', 'country').distinct(
                'city_name', 'state', 'country').order_by('city_name')
            
            for obj_dict in obj_list:
                    
                country = obj_dict.get('country', '')
                state = obj_dict.get('state', '')
                city_name = obj_dict.get('city_name', '')
                
                if autosuggest_dict.get(country, {}):
                    country_dict = autosuggest_dict.get(country, {})
                    if country_dict.get(state, {}):
                        country_dict[state].append(city_name)
                    else:
                        country_dict[state] = [city_name]
                else:
                    autosuggest_dict = {country: {state:[city_name]}}


            if not user_query:
                response = self.get_response(
                    data=autosuggest_dict, count=1, status="success",
                    message="Location Autosuggest", status_code=status.HTTP_200_OK)
                return response
        
        if user_query:
            
            property_info_dict = self.queryset.filter(
                Q(name__icontains=user_query) | Q(title__icontains=user_query)).values(
                    'id', 'name', 'title').distinct('id').order_by('id')

            user_suggest_dict = {"location": autosuggest_dict,
                                 "property_info": property_info_dict}

            response = self.get_response(
                data=user_suggest_dict, count=1, status="success",
                message="Location or Property Autosuggest", status_code=status.HTTP_200_OK)
            return response
        
        response = self.get_response(data=[], count=0, status="success", message="Location Autosuggest",
                                     status_code=status.HTTP_200_OK)
        return response

    @action(detail=False, methods=['GET'], url_path='location/list',
            url_name='location-list', permission_classes=[])
    def get_property_location(self, request):

        
        obj_list = self.queryset.filter(status='Active').values(
            'city_name', 'state', 'country').distinct(
                'city_name', 'state', 'country').order_by('city_name')

        location_dict = {}
            
        for obj_dict in obj_list:
                
            country = obj_dict.get('country', '')
            state = obj_dict.get('state', '')
            city_name = obj_dict.get('city_name', '')
            
            if location_dict.get(country, {}):
                country_dict = location_dict.get(country, {})
                if country_dict.get(state, {}):
                    country_dict[state].append(city_name)
                else:
                    country_dict[state] = [city_name]
            else:
                location_dict = {country: {state:[city_name]}}

        response = self.get_response(
            data=location_dict, count=1, status="success",
            message="Location List", status_code=status.HTTP_200_OK)
        return response
        
    @action(detail=True, methods=['GET'], url_path='insights',
        url_name='property_insights', permission_classes=[IsAuthenticated])
    def property_insights(self, request, pk=None):
        try:
            property_obj = self.get_object()

            # Get total rooms for this property
            total_rooms = Room.objects.filter(property=property_obj).count()

            # Get total unique customers for this property
            total_customers = HotelBooking.objects.filter(
                confirmed_property=property_obj
            ).values('booking__user').distinct().count()

            # Get total transaction amount for this property
            total_transactions = Booking.objects.filter(
                hotel_booking__confirmed_property=property_obj,
                status__in=['confirmed']
            ).aggregate(
                total_amount=Sum('final_amount')
            )['total_amount'] or 0

            # Get total concierges for this property
            total_concierges = User.objects.filter(
                property_manager__id=property_obj.id
            ).count()

            statistics = {
                'total_rooms': total_rooms,
                'total_customers': total_customers,
                'total_transactions': float(total_transactions),
                'total_concierges': total_concierges
            }

            custom_response = self.get_response(
                data=statistics,
                count=1,
                status="success",
                message="Property Insights Retrieved",
                status_code=status.HTTP_200_OK
            )

            return custom_response

        except Property.DoesNotExist:
            custom_response = self.get_error_response(
                message="Property not found",
                status="error",
                errors=[],
                error_code="PROPERTY_NOT_FOUND",
                status_code=status.HTTP_404_NOT_FOUND
            )
            return custom_response
        except Exception as e:
            custom_response = self.get_error_response(
                message=str(e),
                status="error",
                errors=[],
                error_code="INTERNAL_SERVER_ERROR",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
            return custom_response

    @action(detail=False, methods=['POST'], url_path='set/spend-limit', 
        url_name='set-spend-limit', permission_classes=[IsAuthenticated])
    def set_pay_at_hotel_spend_limit(self, request):
        is_many = isinstance(request.data, list)
        
        serializer = PayAtHotelSpendLimitSerializer(data=request.data, many=is_many)
        
        if serializer.is_valid():
            serializer.save()

            all_data = PayAtHotelSpendLimit.objects.all().order_by('start_limit')
            response_data = PayAtHotelSpendLimitSerializer(all_data, many=True).data

            return self.get_response(
                data=response_data,
                count=len(response_data),
                message="Spend limit saved successfully",
                status_code=status.HTTP_201_CREATED
            )

        return self.get_error_response(
            message="Validation Failed",
            status="error",
            errors=serializer.errors,
            error_code="VALIDATION_ERROR",
            status_code=status.HTTP_400_BAD_REQUEST
    )

    
    
    @action(detail=False, methods=['PATCH'], url_path='update/spend-limit',
        url_name='update-spend-limit', permission_classes=[IsAuthenticated])
    def update_pay_at_hotel_spend_limit(self, request):
        """
        Update a spend limit based on ID or start/end limit range
        """
        id = request.data.get('id')
        start_limit = request.data.get('start_limit')
        end_limit = request.data.get('end_limit')
        
        try:
            if id is not None:
                spend_limit = PayAtHotelSpendLimit.objects.get(id=id)
            elif start_limit is not None and end_limit is not None:
                spend_limit = PayAtHotelSpendLimit.objects.get(start_limit=start_limit, end_limit=end_limit)
            else:
                return self.get_error_response(
                    message="Either 'id' or both 'start_limit' and 'end_limit' must be provided",
                    status="error",
                    errors={"non_field_errors": ["Either 'id' or both 'start_limit' and 'end_limit' must be provided"]},
                    error_code="VALIDATION_ERROR",
                    status_code=status.HTTP_400_BAD_REQUEST
                )
            
            update_data = request.data.copy()
            
            if 'start_limit' not in update_data:
                update_data['start_limit'] = spend_limit.start_limit
            if 'end_limit' not in update_data:
                update_data['end_limit'] = spend_limit.end_limit
            if 'spend_limit' not in update_data:
                update_data['spend_limit'] = spend_limit.spend_limit
                

            if PayAtHotelSpendLimit.objects.filter(
                start_limit__lte=update_data['end_limit'],
                end_limit__gte=update_data['start_limit']
            ).exclude(id=spend_limit.id).exists():
                return self.get_error_response(
                    message="Validation Failed",
                    status="error",
                    errors={"non_field_errors": ["Overlapping booking range already exists"]},
                    error_code="VALIDATION_ERROR",
                    status_code=status.HTTP_400_BAD_REQUEST
                )
                
            if update_data['end_limit'] < update_data['start_limit']:
                return self.get_error_response(
                    message="Validation Failed",
                    status="error",
                    errors={"non_field_errors": ["End limit cannot be less than start limit"]},
                    error_code="VALIDATION_ERROR",
                    status_code=status.HTTP_400_BAD_REQUEST
                )
                
            for key, value in update_data.items():
                if key != 'id':
                    setattr(spend_limit, key, value)
            spend_limit.save()
            
            all_data = PayAtHotelSpendLimit.objects.all().order_by('start_limit')
            response_data = PayAtHotelSpendLimitSerializer(all_data, many=True).data
            return self.get_response(
                data=response_data,
                count=len(response_data),
                message="Spend limit updated successfully",
                status_code=status.HTTP_200_OK
            )
            
        except PayAtHotelSpendLimit.DoesNotExist:
            return self.get_error_response(
                message="Spend limit not found",
                status="error",
                errors={"non_field_errors": ["Spend limit not found"]},
                error_code="NOT_FOUND",
                status_code=status.HTTP_404_NOT_FOUND
            )

    @action(detail=False, methods=['POST'], url_path='delete/spend-limit',
        url_name='delete-spend-limit', permission_classes=[IsAuthenticated])
    def delete_pay_at_hotel_spend_limit(self, request):
        """
        Delete a spend limit based on ID using POST method
        """
        id = request.data.get('id')
        
        if not id:
            return self.get_error_response(
                message="'id' parameter is required",
                status="error",
                errors={"non_field_errors": ["'id' parameter is required"]},
                error_code="VALIDATION_ERROR",
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            spend_limit = PayAtHotelSpendLimit.objects.get(id=id)
            spend_limit.delete()
            
            all_data = PayAtHotelSpendLimit.objects.all().order_by('start_limit')
            response_data = PayAtHotelSpendLimitSerializer(all_data, many=True).data
            return self.get_response(
                data=response_data,
                count=len(response_data),
                message="Spend limit deleted successfully",
                status_code=status.HTTP_200_OK
            )
        except PayAtHotelSpendLimit.DoesNotExist:
            return self.get_error_response(
                message="Spend limit not found",
                status="error",
                errors={"non_field_errors": ["Spend limit not found"]},
                error_code="NOT_FOUND",
                status_code=status.HTTP_404_NOT_FOUND
            )

    @action(detail=False, methods=['GET'], url_path='get/spend-limit',
        url_name='get-spend-limits', permission_classes=[IsAuthenticated])
    def get_pay_at_hotel_spend_limits(self, request):
        all_data = PayAtHotelSpendLimit.objects.all().order_by('start_limit')
        response_data = PayAtHotelSpendLimitSerializer(all_data, many=True).data

        return self.get_response(
            data=response_data,
            count=len(response_data),
            message="Spend limit list retrieved successfully",
            status_code=status.HTTP_200_OK
        )

    @action(detail=False, methods=['GET'], permission_classes=[IsAuthenticated],
            url_path='hotel-customer-eligibility', url_name='hotel-customer-eligibility')
    def get_customer_eligibility(self, request):

        queryset = MonthlyPayAtHotelEligibility.objects.all()
        
        is_eligible = request.query_params.get('is_eligible')
        is_blacklisted = request.query_params.get('is_blacklisted')
        month = request.query_params.get('month')
        user_id = request.query_params.get('user_id')
        
        if is_eligible is not None:
            is_eligible_bool = is_eligible.lower() == 'true'
            queryset = queryset.filter(is_eligible=is_eligible_bool)

        if is_blacklisted is not None:
            is_blacklisted_bool = is_blacklisted.lower() == 'true'
            queryset = queryset.filter(is_blacklisted=is_blacklisted_bool)
        
        if month:
            queryset = queryset.filter(month__iexact=month)
            
        if user_id:
            queryset = queryset.filter(user_id=user_id)
        
        count, queryset = paginate_queryset(request, queryset)
        
        serialized_data = MonthlyPayAtHotelEligibilitySerializer(queryset, many=True).data
        
        response_data = {
            "status": "success",
            "message": "Customer eligibility details retrieved successfully",
            "count": count,
            "data": serialized_data
        }
        
        return self.get_response(
            data=serialized_data,
            count=count,
            message="Customer eligibility details retrieved successfully",
            status_code=status.HTTP_200_OK
        )


class GalleryViewSet(viewsets.ModelViewSet, StandardResponseMixin, LoggingMixin):
    queryset = Gallery.objects.all()
    serializer_class = GallerySerializer
    # permission_classes = [AnonymousCanViewOnlyPermission,]
    http_method_names = ['get', 'post', 'put', 'patch']
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['added_by', 'property', 'room', 'active', 'created', 'updated']

    def create(self, request, *args, **kwargs):
        self.log_request(request)  # Log the incoming request

        # Create an instance of your serializer with the request data
        serializer = self.get_serializer(data=request.data)

        if serializer.is_valid():
            # If the serializer is valid, perform the default creation logic
            response = super().create(request, *args, **kwargs)

            # Create a custom response
            custom_response = self.get_response(
                data=response.data,  # Use the data from the default response
                message="Gallery Created",
                status_code=status.HTTP_201_CREATED,  # 201 for successful creation

            )
        else:
            # If the serializer is not valid, create a custom response with error details
            custom_response = self.get_response(
                data=serializer.errors,  # Use the serializer's error details
                message="Validation Error",
                status_code=status.HTTP_400_BAD_REQUEST,  # 400 for validation error
                is_error=True
            )

        self.log_response(custom_response)  # Log the custom response before returning
        return custom_response

    def update(self, request, *args, **kwargs):
        self.log_request(request)  # Log the incoming request

        # Get the object to be updated
        instance = self.get_object()

        # Create an instance of your serializer with the request data and the object to be updated
        serializer = self.get_serializer(instance, data=request.data)

        if serializer.is_valid():
            # If the serializer is valid, perform the default update logic
            response = super().update(request, *args, **kwargs)

            # Create a custom response
            custom_response = self.get_response(
                data=response.data,  # Use the data from the default response
                message="Gallery Updated",
                status_code=status.HTTP_200_OK,  # 200 for successful update

            )
        else:
            # If the serializer is not valid, create a custom response with error details
            custom_response = self.get_response(
                data=serializer.errors,  # Use the serializer's error details
                message="Validation Error",
                status_code=status.HTTP_400_BAD_REQUEST,  # 400 for validation error
                is_error=True
            )

        self.log_response(custom_response)  # Log the custom response before returning
        return custom_response

    def list(self, request, *args, **kwargs):
        self.log_request(request)  # Log the incoming request

        # Perform the default listing logic
        response = super().list(request, *args, **kwargs)

        if response.status_code == status.HTTP_200_OK:
            # If the response status code is OK (200), it's a successful listing
            custom_response = self.get_response(
                data=response.data,  # Use the data from the default response
                message="List Retrieved",
                status_code=status.HTTP_200_OK,  # 200 for successful listing

            )
        else:
            # If the response status code is not OK, it's an error
            custom_response = self.get_response(
                data=None,
                message="Error Occurred",
                status_code=response.status_code,  # Use the status code from the default response
                is_error=True
            )

        self.log_response(custom_response)  # Log the custom response before returning
        return custom_response

    def retrieve(self, request, *args, **kwargs):
        self.log_request(request)  # Log the incoming request

        # Perform the default retrieval logic
        response = super().retrieve(request, *args, **kwargs)

        if response.status_code == status.HTTP_200_OK:
            # If the response status code is OK (200), it's a successful retrieval
            custom_response = self.get_response(
                data=response.data,  # Use the data from the default response
                message="Item Retrieved",
                status_code=status.HTTP_200_OK,  # 200 for successful retrieval

            )
        else:
            # If the response status code is not OK, it's an error
            custom_response = self.get_response(
                data=None,
                message="Error Occurred",
                status_code=response.status_code,  # Use the status code from the default response
                is_error=True
            )

        self.log_response(custom_response)  # Log the custom response before returning
        return custom_response


class RoomViewSet(viewsets.ModelViewSet, StandardResponseMixin, LoggingMixin, ValidationMixin):
    queryset = Room.objects.all()
    serializer_class = RoomSerializer
    # permission_classes = [AnonymousCanViewOnlyPermission,]
##    filter_backends = [DjangoFilterBackend]
##    filterset_fields = ['room_type', "carpet_area", "bed_count", "person_capacity", "child_capacity", "price_per_night",
##                        "price_for_4_hours", "price_for_8_hours", "price_for_12_hours", "price_for_24_hours",
##                        "discount", "availability", "property", "amenities", "room_type", "room_view", "bed_type", ]
    http_method_names = ['get', 'post', 'put', 'patch', 'delete']
    # lookup_field = 'custom_id'

    permission_classes_by_action = {'create': [IsAuthenticated], 'update': [IsAuthenticated], 'partial_update':[IsAuthenticated],
                                    'destroy': [IsAuthenticated], 'list':[AllowAny], 'retrieve':[AllowAny]}

    def get_permissions(self):
        try: 
            return [permission() for permission in self.permission_classes_by_action[self.action]]
        except KeyError: 
            # action is not set return default permission_classes
            return [permission() for permission in self.permission_classes]



    def create(self, request, *args, **kwargs):
        self.log_request(request)  # Log the incoming request
        property_id = request.data.get('property', None)
        room_price = request.data.get('room_price', {})
        

        # Create an instance of your serializer with the request data
        # serializer = self.get_serializer(data=request.data)
        data = request.data.copy()
        is_valid, response = self.validate_room_fields(data)
        if not is_valid:
            custom_response = self.get_error_response(
                message=response.get("message", "Validation failed."),
                status="error",
                errors=[response],
                error_code=response.get("error_code", "VALIDATION_ERROR"),
                status_code=status.HTTP_400_BAD_REQUEST
            )
            return custom_response

        serializer = self.get_serializer(data=data)

        if serializer.is_valid():
            # If the serializer is valid, perform the default creation logic
            response = super().create(request, *args, **kwargs)

            # update the starting price of the property
            if room_price and property_id:
                starting_price_details = hotel_db_utils.get_slot_based_starting_room_price(property_id)
                # hotel_db_utils.update_property_with_starting_price(property_id, starting_price_details)
                is_slot_price_enabled = hotel_db_utils.check_slot_price_enabled(property_id)
                hotel_db_utils.room_based_property_update(property_id, starting_price_details, is_slot_price_enabled)
                

            # Create a custom response
            custom_response = self.get_response(
                data=response.data,  # Use the data from the default response
                message="Room Created",
                status_code=status.HTTP_201_CREATED,  # 201 for successful creation

            )
        else:
            # If the serializer is not valid, create a custom response with error details
            custom_response = self.get_response(
                data=serializer.errors,  # Use the serializer's error details
                message="Validation Error",
                status_code=status.HTTP_400_BAD_REQUEST,  # 400 for validation error
                is_error=True
            )

        self.log_response(custom_response)  # Log the custom response before returning
        return custom_response

    def update(self, request, *args, **kwargs):
        self.log_request(request)  # Log the incoming request

        # Get the object to be updated
        instance = self.get_object()
        data = request.data.copy()

        # Validate and convert data
        is_valid, response = self.validate_room_fields(data)
        if not is_valid:
            custom_response = self.get_error_response(
                message=response.get("message", "Validation failed."),
                status="error",
                errors=[response],
                error_code=response.get("error_code", "VALIDATION_ERROR"),
                status_code=status.HTTP_400_BAD_REQUEST
            )
            return custom_response

        serializer = self.get_serializer(instance, data=data)

        # Create an instance of your serializer with the request data and the object to be updated
        # serializer = self.get_serializer(instance, data=request.data)

        if serializer.is_valid():
            # If the serializer is valid, perform the default update logic
            response = super().update(request._request.__class__(data=data), *args, **kwargs)
            # response = super().update(request, *args, **kwargs)

            # Create a custom response
            custom_response = self.get_response(
                data=response.data,  # Use the data from the default response
                message="Room Updated",
                status_code=status.HTTP_200_OK,  # 200 for successful update

            )
        else:
            # If the serializer is not valid, create a custom response with error details
            custom_response = self.get_response(
                data=serializer.errors,  # Use the serializer's error details
                message="Validation Error",
                status_code=status.HTTP_400_BAD_REQUEST,  # 400 for validation error
                is_error=True
            )

        self.log_response(custom_response)  # Log the custom response before returning
        return custom_response

    def partial_update(self, request, *args, **kwargs):
        self.log_request(request)  # Log the incoming request

        room_price = request.data.get('room_price', {})
        slot_price_enabled = request.data.get('is_slot_price_enabled', None)

        # Get the object to be updated
        instance = self.get_object()
        data = request.data.copy()

        # Validate and convert partial data
        is_valid, response = self.validate_room_fields(data)
        if not is_valid:
            custom_response = self.get_error_response(
                message=response.get("message", "Validation failed."),
                status="error",
                errors=[response],
                error_code=response.get("error_code", "VALIDATION_ERROR"),
                status_code=status.HTTP_400_BAD_REQUEST
            )
            return custom_response

        # Create an instance of your serializer with the request data and the object to be updated
        serializer = self.get_serializer(instance, data=data, partial=True)
        # serializer = self.get_serializer(instance, data=request.data, partial=True)

        if serializer.is_valid():
            # If the serializer is valid, perform the default update logic
            # response = super().update(request, *args, **kwargs)
            response = self.perform_update(serializer)

            # update the starting price of the property
            property_id = instance.property_id
            if room_price or slot_price_enabled is not None:
                starting_price_details = hotel_db_utils.get_slot_based_starting_room_price(property_id)
                # hotel_db_utils.update_property_with_starting_price(property_id, starting_price_details)
                is_slot_price_enabled = hotel_db_utils.check_slot_price_enabled(property_id)
                hotel_db_utils.room_based_property_update(property_id, starting_price_details, is_slot_price_enabled)
                

            # Create a custom response
            custom_response = self.get_response(
                data=serializer.data,  # Use the data from the default response
                message="Room Updated",
                status_code=status.HTTP_200_OK,  # 200 for successful update

            )
        else:
            # If the serializer is not valid, create a custom response with error details
            custom_response = self.get_response(
                data=serializer.errors,  # Use the serializer's error details
                message="Validation Error",
                status_code=status.HTTP_400_BAD_REQUEST,  # 400 for validation error
                is_error=True
            )

        self.log_response(custom_response)  # Log the custom response before returning
        return custom_response

    def list(self, request, *args, **kwargs):
        self.log_request(request)  # Log the incoming request

        # Perform the default listing logic
        response = super().list(request, *args, **kwargs)

        if response.status_code == status.HTTP_200_OK:
            # If the response status code is OK (200), it's a successful listing
            custom_response = self.get_response(
                data=response.data,  # Use the data from the default response
                message="List Retrieved",
                status_code=status.HTTP_200_OK,  # 200 for successful listing

            )
        else:
            # If the response status code is not OK, it's an error
            custom_response = self.get_response(
                data=None,
                message="Error Occurred",
                status_code=response.status_code,  # Use the status code from the default response
                is_error=True
            )

        self.log_response(custom_response)  # Log the custom response before returning
        return custom_response

    def retrieve(self, request, *args, **kwargs):
        self.log_request(request)  # Log the incoming request

        # Perform the default retrieval logic
        response = super().retrieve(request, *args, **kwargs)

        if response.status_code == status.HTTP_200_OK:
            # If the response status code is OK (200), it's a successful retrieval
            custom_response = self.get_response(
                data=response.data,  # Use the data from the default response
                message="Item Retrieved",
                status_code=status.HTTP_200_OK,  # 200 for successful retrieval

            )
        else:
            # If the response status code is not OK, it's an error
            custom_response = self.get_response(
                data=None,
                message="Error Occurred",
                status_code=response.status_code,  # Use the status code from the default response
                is_error=True
            )

        self.log_response(custom_response)  # Log the custom response before returning
        return custom_response

    def destroy(self, request, *args, **kwargs):
        self.log_request(request)  # Log the incoming request

        room_id = kwargs.get("pk")
        instance = Room.objects.filter(id=room_id).first()

        if not instance:
            custom_response = self.get_response(
                data=None,
                message="No Room Details Found",
                status_code=status.HTTP_404_NOT_FOUND,
                is_error=True
            )
        else:
            self.perform_destroy(instance)
            custom_response = self.get_response(
                data=None,
                count=0,
                status="success",
                message="Room Deleted Successfully",
                status_code=status.HTTP_200_OK,
            )

        self.log_response(custom_response)
        return custom_response

    
    @action(detail=False, methods=['POST'], url_path='media',
            url_name='media', permission_classes=[IsAuthenticated])
    def upload_media(self, request):
        self.log_request(request)
        
        room_id = request.data.get('room', None)
        room_gallery_list = []
        media = request.FILES
        media_count = 0

        if not media:
            response = self.get_error_response(message="Media file missing",
                                               status="error",
                                               errors=[],error_code="MEDIA_FILE_MISSING",
                                               status_code=status.HTTP_400_BAD_REQUEST)
            self.log_response(response)
            return response

        room_details = hotel_db_utils.get_room_by_id(room_id)
        if not room_details:
            response = self.get_error_response(message="Room not found",
                                               status="error",
                                               errors=[],error_code="ROOM_NOT_FOUND",
                                               status_code=status.HTTP_400_BAD_REQUEST)
            self.log_response(response)
            return response

        # Bulk upload media
        try:
            for media_data in media.values():
                image_name = media_data.name
                room_gallery = RoomGallery(media=media_data, room_id=room_id)
                room_gallery_list.append(room_gallery)
        
            if room_gallery_list:
                bulk_create = RoomGallery.objects.bulk_create(room_gallery_list)
                media_count = len(bulk_create)
        except Exception as e:
            response = self.get_error_response(message=str(e), status="error",
                                               errors=[],error_code="INTERNAL_SERVER_ERROR",
                                               status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
            self.log_response(response)
            return response

            
        if media_count:
            gallery_objs = RoomGallery.objects.filter(room_id=room_id)
            count = gallery_objs.count()
            serializer = RoomGallerySerializer(gallery_objs, many=True)
            response = self.get_response(data=serializer.data, count = count,
                                         status="success", message="Media Upload Success",
                                         status_code=status.HTTP_200_OK)

        else:
            response = self.get_error_response(message="Media not uploaded",
                                               status="error",
                                               errors=[],error_code="MEDIA_UPLOAD_ERROR",
                                               status_code=status.HTTP_400_BAD_REQUEST)
            
        self.log_response(response)
        return response

    @action(detail=False, methods=['GET'], url_path='media/list',
            url_name='media-list', permission_classes=[AllowAny])
    def list_media(self, request):
        self.log_request(request)
        room_id = self.request.query_params.get('room', None)
        active = self.request.query_params.get('active', True)
        
        room_gallery = hotel_db_utils.get_room_gallery(room_id, active=active)
        count, room_gallery = paginate_queryset(self.request,  room_gallery)
        serializer = RoomGallerySerializer(room_gallery, many=True)
        
        response = self.get_response(data=serializer.data, count = count,
                                     status="success", message="List Room Gallery",
                                     status_code=status.HTTP_200_OK)
        return response

    @action(detail=True, methods=['PATCH'], url_path='inactive',
            url_name='inactive', permission_classes=[IsAuthenticated])
    def make_room_inactive(self, request, pk):
        active = request.data.get('active', False)
        # Get the object to be updated
        instance = self.get_object()
        instance.active = active
        instance.save()
        property_id = instance.property_id

        # update starting price
        if property_id:
            starting_price_details = hotel_db_utils.get_slot_based_starting_room_price(property_id)
            is_slot_price_enabled = hotel_db_utils.check_slot_price_enabled(property_id)
            hotel_db_utils.room_based_property_update(property_id, starting_price_details, is_slot_price_enabled)
        
        data = {"id": instance.id, "active":instance.active}

        custom_response = self.get_response(
            data=data,  # Use the data from the default response
            message="Success",
            status_code=status.HTTP_200_OK,  # 200 for successful update
        )
        return custom_response

    @action(detail=False, methods=['POST'], url_path='media/inactive',
            url_name='media-inactive', permission_classes=[IsAuthenticated])
    def make_media_inactive(self, request):

        image_ids = request.data.get('image_ids', [])
        active = request.data.get('active', False)
        
        if not image_ids and not isinstance(image_ids, list):
            custom_response = self.get_error_response(
                message="Invalid Ids", status="error", errors=[],
                error_code="INVALID_ID", status_code=status.HTTP_400_BAD_REQUEST)
            return custom_response

        # make media active or inactive
        update_status = RoomGallery.objects.filter(id__in=image_ids).update(active=active)
            
        custom_response = self.get_response(
            data={},  # Use the data from the default response
            status="success",
            message="Success",
            count=update_status,
            status_code=status.HTTP_200_OK,  # 200 for successful update
        )
        return custom_response

class BlockedPropertyViewSet(viewsets.ModelViewSet, StandardResponseMixin, LoggingMixin):
    queryset = BlockedProperty.objects.all()
    serializer_class = BlockedPropertySerializer
    http_method_name = ['get', 'post','put','patch']

    def validate_create_parameters(self):
        error_list = []
        blocked_property_dict = {}
        blocked_property = self.request.data.get('blocked_property', None)
        blocked_room = self.request.data.get('blocked_room', None)
        no_of_blocked_rooms = self.request.data.get('no_of_blocked_rooms', None)
        is_entire_property = self.request.data.get('is_entire_property', None)
        start_date = self.request.data.get('start_date', None)
        end_date = self.request.data.get('end_date', None)

        if not blocked_property:
            error_list.append({"field":"blocked_property", "message": "Missing property",
                               "error_code":"MISSING_PROPERTY"})

        if not blocked_room:
            error_list.append({"field":"blocked_room", "message": "Missing room",
                               "error_code":"MISSING_ROOM"})

        if not no_of_blocked_rooms:
            error_list.append({"field":"no_of_blocked_rooms", "message": "Missing room count",
                               "error_code":"MISSING_ROOM_COUNT"})
            
        is_start_date_valid = validate_date(start_date)
        if not is_start_date_valid:
            error_list.append({"field":"start_date", "message": "Wrong date format",
                               "error_code":"FORMAT_ERROR"})

        is_end_date_valid = validate_date(end_date)
        if not is_end_date_valid:
            error_list.append({"field":"end_date", "message": "Wrong date format",
                               "error_code":"FORMAT_ERROR"})
        

        if not error_list:
            block_overlap = hotel_db_utils.check_room_blocked(blocked_room, start_date, end_date)
            if block_overlap:
                error_list.append({"field":"unknown", "message": "Already blocked withing the date range.",
                                   "error_code":"DATE_OVERLAP"})

        if not error_list:
            room_dict = {blocked_room:no_of_blocked_rooms}

            room_rejected_list = hotel_utils.check_room_availability_for_blocking(
                start_date, end_date, blocked_property, room_dict)
            if room_rejected_list:
                error_list.append({"field":"unknown", "message": "Room not available for the date range",
                                   "error_code":"ROOM_UNAVAILABLE"})

        if not error_list:
            if not is_entire_property:
                is_entire_property = False
            blocked_property_dict = {"blocked_property_id": blocked_property, "blocked_room_id":blocked_room,
                                     "no_of_blocked_rooms":no_of_blocked_rooms, "is_entire_property":is_entire_property,
                                     "start_date":start_date, "end_date":end_date}


        return error_list, blocked_property_dict

    def validate_update_parameters(self, instance):
        error_list = []
        
        start_date = self.request.data.get('start_date', None)
        end_date = self.request.data.get('end_date', None)
        no_of_blocked_rooms = self.request.data.get('no_of_blocked_rooms', None)
        blocked_room = instance.blocked_room_id
        blocked_property = instance.blocked_property_id

        block_overlap = hotel_db_utils.check_room_blocked(blocked_room, start_date, end_date,
                                                          instance_id=instance.id)
        if block_overlap:
            error_list.append({"field":"unknown", "message": "Already blocked withing the date range.",
                               "error_code":"DATE_OVERLAP"})

        room_dict = {blocked_room:no_of_blocked_rooms}

        room_rejected_list = hotel_utils.check_room_availability_for_blocking(
            start_date, end_date, blocked_property, room_dict)
        if room_rejected_list:
            error_list.append({"field":"unknown", "message": "Room not available for the date range",
                               "error_code":"ROOM_UNAVAILABLE"})

        if not error_list:
            instance.no_of_blocked_rooms = no_of_blocked_rooms
            instance.start_date = start_date
            instance.end_date = end_date

        return error_list, instance

    def bocked_property_filter_ops(self):
        filter_dict = {}
        
        start_date = self.request.query_params.get('start_date', None)
        end_date = self.request.query_params.get('end_date', None)
        active = self.request.query_params.get('active', None)

        if active is not None and active in ("true", "false"):
            active = True if active == "true" else False
            filter_dict['active'] = active
            
        
        if start_date:
            start_date = start_date.replace(' ', '+')
            start_date = datetime.strptime(start_date, '%Y-%m-%dT%H:%M%z')
            filter_dict['start_date__gte'] = start_date

        if end_date:  
            end_date = end_date.replace(' ', '+')
            end_date = datetime.strptime(end_date, '%Y-%m-%dT%H:%M%z')
            filter_dict['end_date__lte'] = end_date
            
        if filter_dict:
            self.queryset = self.queryset.filter(**filter_dict)
            

    def create(self, request, *args, **kwargs):
        
        error_list, blocked_property_dict = self.validate_create_parameters()
        if error_list:
            response = self.get_error_response(
                message="Validation Error", status="error",
                errors=error_list, error_code="VALIDATION_ERROR",
                status_code=status.HTTP_400_BAD_REQUEST)
            return response

        
        blocked_property_obj = BlockedProperty.objects.create(**blocked_property_dict)
        serializer = BlockedPropertySerializer(blocked_property_obj)

        response = self.get_response(data=serializer.data, count=1,
                                     status="success", message="Property Blocked Successfully",
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
        
        serializer = BlockedPropertySerializer(instance)
        response = self.get_response(data=serializer.data, count=1,
                                     status="success", message="Updated Successfully",
                                     status_code=status.HTTP_200_OK)
        return response


    def list(self, request, *args, **kwargs):

        # filter
        self.bocked_property_filter_ops()

        # paginate the result
        count, self.queryset = paginate_queryset(self.request,  self.queryset)

        response = super().list(request, *args, **kwargs)
        
        response = self.get_response(
            count=count, status="success",
            data=response.data,  # Use the data from the default response
            message="List Retrieved",
            status_code=status.HTTP_200_OK,  # 200 for successful listing
            )

        return response

    def retrieve(self, request, *args, **kwargs):

        response = super().retrieve(request, *args, **kwargs)

        if response.status_code == status.HTTP_200_OK:
            # If the response status code is OK (200), it's a successful retrieval
            custom_response = self.get_response(
                data=response.data,  # Use the data from the default response,
                count=1,
                status="success",
                message="Blocked Property Retrieved",
                status_code=status.HTTP_200_OK,  # 200 for successful retrieval

            )
        else:
            # If the response status code is not OK, it's an error
            custom_response = self.get_error_response(message="Error Occured", status="error",
                                                      errors=[],error_code="ERROR",
                                                      status_code=response.status_code)

        self.log_response(custom_response)  # Log the custom response before returning
        return custom_response

    @action(detail=False, methods=['POST'], url_path='room-list',
            url_name='room-list', permission_classes=[])
    def retrieve_available_room(self, request):
        error_list = []
        
        blocked_property = self.request.data.get('blocked_property', None)
        print("blocked property", blocked_property)
        start_date = self.request.data.get('start_date', None)
        end_date = self.request.data.get('end_date', None)

        is_start_date_valid = validate_date(start_date)
        if not is_start_date_valid:
            error_list.append({"field":"start_date", "message": "Wrong date format",
                               "error_code":"FORMAT_ERROR"})

        is_end_date_valid = validate_date(end_date)
        if not is_end_date_valid:
            error_list.append({"field":"end_date", "message": "Wrong date format",
                               "error_code":"FORMAT_ERROR"})

##        blocked_room_list = hotel_db_utils.get_blocked_room_list(blocked_property, start_date, end_date)

##        rooms = hotel_db_utils.get_rooms_by_property(blocked_property)
##        serializer = RoomNameSerializer(rooms, many=True)

        room_list = []

        room_list = hotel_utils.get_available_room(start_date, end_date, blocked_property)

##        room_raw_obj = hotel_db_utils.get_room_availability(start_date, end_date)
##        for room_detail in room_raw_obj:
##            room_dict = {"id":room_detail.id, "no_available_rooms":room_detail.no_available_rooms,
##                         "no_booked_room":room_detail.no_booked_room, "no_of_blocked_rooms":room_detail.no_of_blocked_rooms,
##                         "current_available_room":room_detail.current_available_room}
##            room_list.append(room_dict)
##        print(room_list)
        custom_response = self.get_response(
            data=room_list,
            count=1, status="success",
            message="Propery room list success",
            status_code=status.HTTP_200_OK,
            )
        return custom_response
        

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
        instance.active = active
        #print("start date::", str(instance.start_date))  #.strftime('%Y-%m-%dT%H:%M%z'))
        instance.save()
        
        serializer = BlockedPropertySerializer(instance)
        response = self.get_response(data=serializer.data, count=1,
                                     status="success", message="Property Update Success",
                                     status_code=status.HTTP_200_OK)
        return response


class RuleViewSet(viewsets.ModelViewSet, StandardResponseMixin, LoggingMixin):
    queryset = Rule.objects.all()
    serializer_class = RuleSerializer
    # permission_classes = [AnonymousCanViewOnlyPermission,]
    http_method_names = ['get', 'post', 'put', 'patch']

    def create(self, request, *args, **kwargs):
        self.log_request(request)  # Log the incoming request

        # Create an instance of your serializer with the request data
        serializer = self.get_serializer(data=request.data)

        if serializer.is_valid():
            # If the serializer is valid, perform the default creation logic
            response = super().create(request, *args, **kwargs)

            # Create a custom response
            custom_response = self.get_response(
                data=response.data,  # Use the data from the default response
                message="Rule Created",
                status_code=status.HTTP_201_CREATED,  # 201 for successful creation

            )
        else:
            # If the serializer is not valid, create a custom response with error details
            custom_response = self.get_response(
                data=serializer.errors,  # Use the serializer's error details
                message="Validation Error",
                status_code=status.HTTP_400_BAD_REQUEST,  # 400 for validation error
                is_error=True
            )

        self.log_response(custom_response)  # Log the custom response before returning
        return custom_response

    def update(self, request, *args, **kwargs):
        self.log_request(request)  # Log the incoming request

        # Get the object to be updated
        instance = self.get_object()

        # Create an instance of your serializer with the request data and the object to be updated
        serializer = self.get_serializer(instance, data=request.data)

        if serializer.is_valid():
            # If the serializer is valid, perform the default update logic
            response = super().update(request, *args, **kwargs)

            # Create a custom response
            custom_response = self.get_response(
                data=response.data,  # Use the data from the default response
                message="Rule Updated",
                status_code=status.HTTP_200_OK,  # 200 for successful update

            )
        else:
            # If the serializer is not valid, create a custom response with error details
            custom_response = self.get_response(
                data=serializer.errors,  # Use the serializer's error details
                message="Validation Error",
                status_code=status.HTTP_400_BAD_REQUEST,  # 400 for validation error
                is_error=True
            )

        self.log_response(custom_response)  # Log the custom response before returning
        return custom_response

    def list(self, request, *args, **kwargs):
        self.log_request(request)  # Log the incoming request

        # Perform the default listing logic
        response = super().list(request, *args, **kwargs)

        if response.status_code == status.HTTP_200_OK:
            # If the response status code is OK (200), it's a successful listing
            custom_response = self.get_response(
                data=response.data,  # Use the data from the default response
                message="List Retrieved",
                status_code=status.HTTP_200_OK,  # 200 for successful listing

            )
        else:
            # If the response status code is not OK, it's an error
            custom_response = self.get_response(
                data=None,
                message="Error Occurred",
                status_code=response.status_code,  # Use the status code from the default response
                is_error=True
            )

        self.log_response(custom_response)  # Log the custom response before returning
        return custom_response

    def retrieve(self, request, *args, **kwargs):
        self.log_request(request)  # Log the incoming request

        # Perform the default retrieval logic
        response = super().retrieve(request, *args, **kwargs)

        if response.status_code == status.HTTP_200_OK:
            # If the response status code is OK (200), it's a successful retrieval
            custom_response = self.get_response(
                data=response.data,  # Use the data from the default response
                message="Item Retrieved",
                status_code=status.HTTP_200_OK,  # 200 for successful retrieval

            )
        else:
            # If the response status code is not OK, it's an error
            custom_response = self.get_response(
                data=None,
                message="Error Occurred",
                status_code=response.status_code,  # Use the status code from the default response
                is_error=True
            )

        self.log_response(custom_response)  # Log the custom response before returning
        return custom_response


class InclusionViewSet(viewsets.ModelViewSet, StandardResponseMixin, LoggingMixin):
    queryset = Inclusion.objects.all()
    serializer_class = InclusionSerializer
    # permission_classes = [AnonymousCanViewOnlyPermission,]
    http_method_names = ['get', 'post', 'put', 'patch']

    def create(self, request, *args, **kwargs):
        self.log_request(request)  # Log the incoming request

        # Create an instance of your serializer with the request data
        serializer = self.get_serializer(data=request.data)

        if serializer.is_valid():
            # If the serializer is valid, perform the default creation logic
            response = super().create(request, *args, **kwargs)

            # Create a custom response
            custom_response = self.get_response(
                data=response.data,  # Use the data from the default response
                message="Inclusion Created",
                status_code=status.HTTP_201_CREATED,  # 201 for successful creation

            )
        else:
            # If the serializer is not valid, create a custom response with error details
            custom_response = self.get_response(
                data=serializer.errors,  # Use the serializer's error details
                message="Validation Error",
                status_code=status.HTTP_400_BAD_REQUEST,  # 400 for validation error
                is_error=True
            )

        self.log_response(custom_response)  # Log the custom response before returning
        return custom_response

    def update(self, request, *args, **kwargs):
        self.log_request(request)  # Log the incoming request

        # Get the object to be updated
        instance = self.get_object()

        # Create an instance of your serializer with the request data and the object to be updated
        serializer = self.get_serializer(instance, data=request.data)

        if serializer.is_valid():
            # If the serializer is valid, perform the default update logic
            response = super().update(request, *args, **kwargs)

            # Create a custom response
            custom_response = self.get_response(
                data=response.data,  # Use the data from the default response
                message="Inclusion Updated",
                status_code=status.HTTP_200_OK,  # 200 for successful update

            )
        else:
            # If the serializer is not valid, create a custom response with error details
            custom_response = self.get_response(
                data=serializer.errors,  # Use the serializer's error details
                message="Validation Error",
                status_code=status.HTTP_400_BAD_REQUEST,  # 400 for validation error
                is_error=True
            )

        self.log_response(custom_response)  # Log the custom response before returning
        return custom_response

    def list(self, request, *args, **kwargs):
        self.log_request(request)  # Log the incoming request

        # Perform the default listing logic
        response = super().list(request, *args, **kwargs)

        if response.status_code == status.HTTP_200_OK:
            # If the response status code is OK (200), it's a successful listing
            custom_response = self.get_response(
                data=response.data,  # Use the data from the default response
                message="List Retrieved",
                status_code=status.HTTP_200_OK,  # 200 for successful listing

            )
        else:
            # If the response status code is not OK, it's an error
            custom_response = self.get_response(
                data=None,
                message="Error Occurred",
                status_code=response.status_code,  # Use the status code from the default response
                is_error=True
            )

        self.log_response(custom_response)  # Log the custom response before returning
        return custom_response

    def retrieve(self, request, *args, **kwargs):
        self.log_request(request)  # Log the incoming request

        # Perform the default retrieval logic
        response = super().retrieve(request, *args, **kwargs)

        if response.status_code == status.HTTP_200_OK:
            # If the response status code is OK (200), it's a successful retrieval
            custom_response = self.get_response(
                data=response.data,  # Use the data from the default response
                message="Item Retrieved",
                status_code=status.HTTP_200_OK,  # 200 for successful retrieval

            )
        else:
            # If the response status code is not OK, it's an error
            custom_response = self.get_response(
                data=None,
                message="Error Occurred",
                status_code=response.status_code,  # Use the status code from the default response
                is_error=True
            )

        self.log_response(custom_response)  # Log the custom response before returning
        return custom_response


class FinancialDetailViewSet(viewsets.ModelViewSet, StandardResponseMixin, LoggingMixin):
    queryset = FinancialDetail.objects.all()
    serializer_class = FinancialDetailSerializer
    # permission_classes = [AnonymousCanViewOnlyPermission,]
    http_method_names = ['get', 'post', 'put', 'patch']

    def create(self, request, *args, **kwargs):
        self.log_request(request)  # Log the incoming request

        # Create an instance of your serializer with the request data
        serializer = self.get_serializer(data=request.data)

        if serializer.is_valid():
            # If the serializer is valid, perform the default creation logic
            response = super().create(request, *args, **kwargs)

            # Create a custom response
            custom_response = self.get_response(
                data=response.data,  # Use the data from the default response
                message="Financial Detail Created",
                status_code=status.HTTP_201_CREATED,  # 201 for successful creation

            )
        else:
            # If the serializer is not valid, create a custom response with error details
            custom_response = self.get_response(
                data=serializer.errors,  # Use the serializer's error details
                message="Validation Error",
                status_code=status.HTTP_400_BAD_REQUEST,  # 400 for validation error
                is_error=True
            )

        self.log_response(custom_response)  # Log the custom response before returning
        return custom_response

    def update(self, request, *args, **kwargs):
        self.log_request(request)  # Log the incoming request

        # Get the object to be updated
        instance = self.get_object()

        # Create an instance of your serializer with the request data and the object to be updated
        serializer = self.get_serializer(instance, data=request.data)

        if serializer.is_valid():
            # If the serializer is valid, perform the default update logic
            response = super().update(request, *args, **kwargs)

            # Create a custom response
            custom_response = self.get_response(
                data=response.data,  # Use the data from the default response
                message="Financial Detail Updated",
                status_code=status.HTTP_200_OK,  # 200 for successful update

            )
        else:
            # If the serializer is not valid, create a custom response with error details
            custom_response = self.get_response(
                data=serializer.errors,  # Use the serializer's error details
                message="Validation Error",
                status_code=status.HTTP_400_BAD_REQUEST,  # 400 for validation error
                is_error=True
            )

        self.log_response(custom_response)  # Log the custom response before returning
        return custom_response

    def list(self, request, *args, **kwargs):
        self.log_request(request)  # Log the incoming request

        # Perform the default listing logic
        response = super().list(request, *args, **kwargs)

        if response.status_code == status.HTTP_200_OK:
            # If the response status code is OK (200), it's a successful listing
            custom_response = self.get_response(
                data=response.data,  # Use the data from the default response
                message="List Retrieved",
                status_code=status.HTTP_200_OK,  # 200 for successful listing

            )
        else:
            # If the response status code is not OK, it's an error
            custom_response = self.get_response(
                data=None,
                message="Error Occurred",
                status_code=response.status_code,  # Use the status code from the default response
                is_error=True
            )

        self.log_response(custom_response)  # Log the custom response before returning
        return custom_response

    def retrieve(self, request, *args, **kwargs):
        self.log_request(request)  # Log the incoming request

        # Perform the default retrieval logic
        response = super().retrieve(request, *args, **kwargs)

        if response.status_code == status.HTTP_200_OK:
            # If the response status code is OK (200), it's a successful retrieval
            custom_response = self.get_response(
                data=response.data,  # Use the data from the default response
                message="Item Retrieved",
                status_code=status.HTTP_200_OK,  # 200 for successful retrieval

            )
        else:
            # If the response status code is not OK, it's an error
            custom_response = self.get_response(
                data=None,
                message="Error Occurred",
                status_code=response.status_code,  # Use the status code from the default response
                is_error=True
            )

        self.log_response(custom_response)  # Log the custom response before returning
        return custom_response


##class ReviewViewSet(viewsets.ModelViewSet, StandardResponseMixin, LoggingMixin):
##    queryset = Review.objects.all()
##    serializer_class = ReviewSerializer
##    # permission_classes = [AnonymousCanViewOnlyPermission,]
##    http_method_names = ['get', 'post', 'put', 'patch']
##
##    def create(self, request, *args, **kwargs):
##        self.log_request(request)  # Log the incoming request
##
##        # Create an instance of your serializer with the request data
##        serializer = self.get_serializer(data=request.data)
##
##        if serializer.is_valid():
##            # If the serializer is valid, perform the default creation logic
##            response = super().create(request, *args, **kwargs)
##
##            # Create a custom response
##            custom_response = self.get_response(
##                data=response.data,  # Use the data from the default response
##                message="Review Created",
##                status_code=status.HTTP_201_CREATED,  # 201 for successful creation
##
##            )
##        else:
##            # If the serializer is not valid, create a custom response with error details
##            custom_response = self.get_response(
##                data=serializer.errors,  # Use the serializer's error details
##                message="Validation Error",
##                status_code=status.HTTP_400_BAD_REQUEST,  # 400 for validation error
##                is_error=True
##            )
##
##        self.log_response(custom_response)  # Log the custom response before returning
##        return custom_response
##
##    def update(self, request, *args, **kwargs):
##        self.log_request(request)  # Log the incoming request
##
##        # Get the object to be updated
##        instance = self.get_object()
##
##        # Create an instance of your serializer with the request data and the object to be updated
##        serializer = self.get_serializer(instance, data=request.data)
##
##        if serializer.is_valid():
##            # If the serializer is valid, perform the default update logic
##            response = super().update(request, *args, **kwargs)
##
##            # Create a custom response
##            custom_response = self.get_response(
##                data=response.data,  # Use the data from the default response
##                message="Review Updated",
##                status_code=status.HTTP_200_OK,  # 200 for successful update
##
##            )
##        else:
##            # If the serializer is not valid, create a custom response with error details
##            custom_response = self.get_response(
##                data=serializer.errors,  # Use the serializer's error details
##                message="Validation Error",
##                status_code=status.HTTP_400_BAD_REQUEST,  # 400 for validation error
##                is_error=True
##            )
##
##        self.log_response(custom_response)  # Log the custom response before returning
##        return custom_response
##
##    def list(self, request, *args, **kwargs):
##        self.log_request(request)  # Log the incoming request
##
##        # Perform the default listing logic
##        response = super().list(request, *args, **kwargs)
##
##        if response.status_code == status.HTTP_200_OK:
##            # If the response status code is OK (200), it's a successful listing
##            custom_response = self.get_response(
##                data=response.data,  # Use the data from the default response
##                message="List Retrieved",
##                status_code=status.HTTP_200_OK,  # 200 for successful listing
##
##            )
##        else:
##            # If the response status code is not OK, it's an error
##            custom_response = self.get_response(
##                data=None,
##                message="Error Occurred",
##                status_code=response.status_code,  # Use the status code from the default response
##                is_error=True
##            )
##
##        self.log_response(custom_response)  # Log the custom response before returning
##        return custom_response
##
##    def retrieve(self, request, *args, **kwargs):
##        self.log_request(request)  # Log the incoming request
##
##        # Perform the default retrieval logic
##        response = super().retrieve(request, *args, **kwargs)
##
##        if response.status_code == status.HTTP_200_OK:
##            # If the response status code is OK (200), it's a successful retrieval
##            custom_response = self.get_response(
##                data=response.data,  # Use the data from the default response
##                message="Item Retrieved",
##                status_code=status.HTTP_200_OK,  # 200 for successful retrieval
##
##            )
##        else:
##            # If the response status code is not OK, it's an error
##            custom_response = self.get_response(
##                data=None,
##                message="Error Occurred",
##                status_code=response.status_code,  # Use the status code from the default response
##                is_error=True
##            )
##
##        self.log_response(custom_response)  # Log the custom response before returning
##        return custom_response

class HotelAmenityCategoryViewSet(viewsets.ModelViewSet, StandardResponseMixin, LoggingMixin):
    queryset = HotelAmenityCategory.objects.all()
    serializer_class = HotelAmenityCategorySerializer
    # permission_classes = [AnonymousCanViewOnlyPermission,]
    http_method_names = ['get', 'post', 'put', 'patch']


    def list(self, request, *args, **kwargs):
        self.log_request(request)  # Log the incoming request

        # Perform the default listing logic
        response = super().list(request, *args, **kwargs)

        if response.status_code == status.HTTP_200_OK:
            # If the response status code is OK (200), it's a successful listing
            custom_response = self.get_response(
                data=response.data,  # Use the data from the default response
                message="List Retrieved",
                status_code=status.HTTP_200_OK,  # 200 for successful listing

            )
        else:
            # If the response status code is not OK, it's an error
            custom_response = self.get_response(
                data=None,
                message="Error Occurred",
                status_code=response.status_code,  # Use the status code from the default response
                is_error=True
            )

        self.log_response(custom_response)  # Log the custom response before returning
        return custom_response

class RoomAmenityCategoryViewSet(viewsets.ModelViewSet, StandardResponseMixin, LoggingMixin):
    queryset = RoomAmenityCategory.objects.all()
    serializer_class = RoomAmenityCategorySerializer
    http_method_names = ['get', 'post', 'put', 'patch']

    def list(self, request, *args, **kwargs):
        self.log_request(request)  # Log the incoming request

        # Perform the default listing logic
        response = super().list(request, *args, **kwargs)

        if response.status_code == status.HTTP_200_OK:
            # If the response status code is OK (200), it's a successful listing
            custom_response = self.get_response(
                data=response.data,  # Use the data from the default response
                message="List Retrieved",
                status_code=status.HTTP_200_OK,  # 200 for successful listing

            )
        else:
            # If the response status code is not OK, it's an error
            custom_response = self.get_response(
                data=None,
                message="Error Occurred",
                status_code=response.status_code,  # Use the status code from the default response
                is_error=True
            )

        self.log_response(custom_response)  # Log the custom response before returning
        return custom_response

class PropertyBankDetailViewSet(viewsets.ModelViewSet, StandardResponseMixin, LoggingMixin):
    queryset = PropertyBankDetails.objects.all()
    serializer_class = PropertyBankDetailsSerializer
    permission_classes = [IsAuthenticated,]
    http_method_names = ['get', 'post', 'put', 'patch']

    def create(self, request, *args, **kwargs):
        self.log_request(request)  # Log the incoming request

        # Create an instance of your serializer with the request data
        serializer = self.get_serializer(data=request.data)

        if serializer.is_valid():
            # If the serializer is valid, perform the default creation logic
            response = super().create(request, *args, **kwargs)

            # If the response status code is OK (200), it's a successful retrieval
            custom_response = self.get_response(
                data=response.data,  # Use the data from the default response,
                count=1,
                status="success",
                message="Bank Detail Created",
                status_code=status.HTTP_201_CREATED,  

            )
        else:
            # If the response status code is not OK, it's an error
            custom_response = self.get_error_response(message="Error Occured", status="error",
                                                      errors=[],error_code="ERROR",
                                                      status_code=status.HTTP_400_BAD_REQUEST)

        self.log_response(custom_response)  # Log the custom response before returning
        return custom_response

    def partial_update(self, request, *args, **kwargs):
        self.log_request(request)  # Log the incoming request

        # Get the object to be updated
        instance = self.get_object()

        # Create an instance of your serializer with the request data and the object to be updated
        serializer = self.get_serializer(instance, data=request.data, partial=True)

        if serializer.is_valid():
            # If the serializer is valid, perform the default update logic
            # response = super().update(request, *args, **kwargs)
            response = self.perform_update(serializer)

            # Create a custom response
            custom_response = self.get_response(
                data=serializer.data,  # Use the data from the default response,
                count=1,
                status="success",
                message="Bank Detail Updated",
                status_code=status.HTTP_200_OK,  # 200 for successful retrieval

            )
        else:
            # If the serializer is not valid, create a custom response with error details
            custom_response = self.get_error_response(message="Error Occured", status="error",
                                                      errors=[],error_code="ERROR",
                                                      status_code=status.HTTP_400_BAD_REQUEST)

        self.log_response(custom_response)  # Log the custom response before returning
        return custom_response

    def list(self, request, *args, **kwargs):
        self.log_request(request)  # Log the incoming request
        property_id = request.query_params.get('property', '')

        if not property_id:
            custom_response = self.get_error_response(message="Missing Property", status="error",
                                                      errors=[],error_code="MISSING_PROPERTY",
                                                      status_code=status.HTTP_400_BAD_REQUEST)
            return custom_response
            
        self.queryset = self.queryset.filter(property=property_id)
        # Perform the default listing logic
        response = super().list(request, *args, **kwargs)

        if response.status_code == status.HTTP_200_OK:
            # If the response status code is OK (200), it's a successful listing
            custom_response = self.get_response(
                data=response.data,  # Use the data from the default response
                message="List Retrieved",
                status="success",
                status_code=status.HTTP_200_OK,  # 200 for successful listing

            )
        else:
            # If the response status code is not OK, it's an error
            custom_response = self.get_error_response(message="Error", status="error",
                                                      errors=[],error_code="ERROR",
                                                      status_code=status.HTTP_400_BAD_REQUEST)

        self.log_response(custom_response)  # Log the custom response before returning
        return custom_response
