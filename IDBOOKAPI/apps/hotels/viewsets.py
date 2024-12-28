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
from IDBOOKAPI.utils import paginate_queryset
from .serializers import (
    PropertySerializer, GallerySerializer, RoomSerializer, RuleSerializer, InclusionSerializer,
    FinancialDetailSerializer, HotelAmenityCategorySerializer,
    RoomAmenityCategorySerializer, PropertyGallerySerializer, RoomGallerySerializer,
    PropertyListSerializer, PropertyRetrieveSerializer, PropertyBankDetailsSerializer)
from .models import (Property, Gallery, Room, Rule, Inclusion,
                     FinancialDetail, HotelAmenityCategory,
                     RoomAmenityCategory, FavoriteList, PropertyBankDetails)

from .models import RoomGallery, PropertyGallery

from apps.hotels.utils import db_utils as hotel_db_utils
from apps.hotels.utils import hotel_policies_utils
from apps.hotels.utils import hotel_utils
from apps.booking.utils.db_utils import change_onhold_status

from rest_framework.decorators import action

from django.db.models import Q

from datetime import datetime

from functools import reduce


class PropertyViewSet(viewsets.ModelViewSet, StandardResponseMixin, LoggingMixin):
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
                                | Q(country=loc.strip())  for loc in loc_list),)

##                query = reduce(lambda a, b: a | b,
##                               (Q(city_name=loc) for loc in loc_list),)
##                print("query::", query)
                self.queryset = self.queryset.filter(query)
                
##                self.queryset = self.queryset.filter(
##                    Q(country__icontains=param_value) | Q(state__icontains=param_value)
##                    | Q(city_name__icontains=param_value) | Q(area_name__icontains=param_value))
                print("queryset::", self.queryset.query)
            if key == 'user':
                filter_dict['added_by'] = param_value

            if key == 'rating':
                rating_list = param_value.split(',')
                filter_dict['rating__in'] = rating_list
                

            if key in ('country', 'state', 'city_name', 'area_name', 'status'):
                filter_dict[key] = param_value

        # filter based on price range
        start_price = self.request.query_params.get('start_price', None)
        end_price = self.request.query_params.get('end_price', None)
        if start_price is not None and end_price is not None:
            property_list = hotel_db_utils.get_property_from_price_range(int(start_price), int(end_price))
            print("property list", property_list)
            self.queryset = self.queryset.filter(id__in=property_list)

        # filter based on slot based property
        is_slot_price_enabled = self.request.query_params.get('is_slot_price_enabled', 'false')
        is_slot_price_enabled = True if is_slot_price_enabled == "true" else False
        
        if is_slot_price_enabled:
            property_slot_list = hotel_db_utils.get_slot_price_enabled_property()
            self.queryset = self.queryset.filter(id__in=property_slot_list)

        if filter_dict:
            self.queryset = self.queryset.filter(**filter_dict)

        

    def checkin_checkout_based_filter(self):
        checkin_date = self.request.query_params.get('checkin', '')
        checkout_date = self.request.query_params.get('checkout', '')
##        is_slot_price_enabled = self.request.query_params.get('is_slot_price_enabled', 'false')
##        is_slot_price_enabled = True if is_slot_price_enabled == "true" else False
        
        print("checkin_date::", checkin_date)
        
        available_property_dict = {} 

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
            
            booked_hotel_dict = hotel_utils.get_booked_property(checkin_date, checkout_date, True)
            # print("booked hotel dict::", booked_hotel_dict)
            # property details from booking 
            nonavailable_property_list, available_property_dict = \
                                        hotel_utils.get_available_property(booked_hotel_dict)
##            print("Non available property list::", nonavailable_property_list)
##            print("available property list::", available_property_dict)

            
            # exclude non available property list
            if nonavailable_property_list:
                self.queryset = self.queryset.exclude(id__in=nonavailable_property_list)

        return available_property_dict      
            

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

        # Create an instance of your serializer with the request data and the object to be updated
        serializer = self.get_serializer(instance, data=request.data, partial=True)

        if serializer.is_valid():
            # If the serializer is valid, perform the default update logic
            #response = super().partial_update(request, *args, **kwargs)
            response = self.perform_update(serializer)
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
        favorite_list = []

        # update the on hold status to pending 
        change_onhold_status()
        
        # apply property filter
        self.property_filter_ops()
        # filter for checkin checkout
        available_property_dict = self.checkin_checkout_based_filter()

        if request.user:
            favorite_list = hotel_db_utils.get_favorite_property(request.user.id)

        
        # paginate the result
        count, self.queryset = paginate_queryset(self.request,  self.queryset)
        self.queryset = self.queryset.values('id','name', 'title', 'property_type',
                                             'rental_form', 'review_star', 'review_count',
                                             'additional_fields', 'area_name',
                                             'city_name', 'state', 'country',
                                             'rating', 'status', 'current_page', 'address')
        # Perform the default listing logic
        response = PropertyListSerializer(
            self.queryset, many=True,
            context={'available_property_dict': available_property_dict,
                     'favorite_list':favorite_list})
        # response = super().list(request, *args, **kwargs)

        custom_response = self.get_response(
            count=count, status="success",
            data=response.data,  # Use the data from the default response
            message="List Retrieved",
            status_code=status.HTTP_200_OK,  # 200 for successful listing
            )

        self.log_response(custom_response)  # Log the custom response before returning
        return custom_response

    def retrieve(self, request, *args, **kwargs):
        self.log_request(request)  # Log the incoming request

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

        # Perform the default retrieval logic
        response = super().retrieve(request, *args, **kwargs)

        if response.status_code == status.HTTP_200_OK:
            # If the response status code is OK (200), it's a successful retrieval
            custom_response = self.get_response(
                data=response.data,  # Use the data from the default response,
                count=1,
                status="success",
                message="Item Retrieved",
                status_code=status.HTTP_200_OK,  # 200 for successful retrieval

            )
        else:
            # If the response status code is not OK, it's an error
            custom_response = self.get_error_response(message="Error Occured", status="error",
                                                      errors=[],error_code="ERROR",
                                                      status_code=response.status_code)

        self.log_response(custom_response)  # Log the custom response before returning
        return custom_response

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
            response = self.get_response(data={}, count = media_count,
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

    @action(detail=False, methods=['GET'], url_path='favorite/list',
            url_name='favorite', permission_classes=[IsAuthenticated])
    def get_favorite_property(self, request):
        user = self.request.user
        
        queryset = FavoriteList.objects.filter(user_id=user.id, property__isnull=False)
        count, queryset = paginate_queryset(self.request, queryset)

        favorite_list = list(queryset.values_list('property_id', flat=True))
        print("favorite list::", favorite_list)
        
        self.queryset = self.queryset.filter(id__in = favorite_list).values(
            'id','name', 'display_name', 'area_name', 'city_name',
            'state', 'country','rating', 'status')

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
            min_price, max_price = hotel_db_utils.get_price_range()
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
        autosuggest_list = []
        autosuggest_dict = {}



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


                
##                autosuggest_data = f"{obj_dict.get('city_name', '')}, {obj_dict.get('state', '')}, {obj_dict.get('country', '')}"
##                autosuggest_list.append(autosuggest_data)
            
            response = self.get_response(
                data=autosuggest_dict, count=1, status="success",
                message="Location Autosuggest", status_code=status.HTTP_200_OK)
            return response
        
##        area_queryset = self.queryset.filter(area_name__icontains=location).exclude(city_name='',state='', country='')
##        if area_queryset.count():
##            obj_list = area_queryset.values('area_name', 'city_name', 'state', 'country').distinct(
##                'area_name', 'city_name', 'state', 'country').order_by('area_name', 'city_name')
##            
##            for obj_dict in obj_list:
##                autosuggest_data = f"{obj_dict.get('area_name', '')}, {obj_dict.get('city_name', '')}, \
##{obj_dict.get('state', '')}, {obj_dict.get('country', '')}"
##                autosuggest_list.append(autosuggest_data)
##            
##            response = self.get_response(
##                data=autosuggest_list, count=len(autosuggest_list), status="success",
##                message="Location Autosuggest", status_code=status.HTTP_200_OK)
##            return response
##
##        # city highlighted queryset
##        city_queryset = self.queryset.filter(city_name__icontains=location).exclude(state='', country='')
##        if city_queryset.count():
##            obj_list = city_queryset.values('city_name', 'state', 'country').distinct(
##                'city_name', 'state', 'country').order_by('city_name')
##            
##            for obj_dict in obj_list:
##                    
##                country = obj_dict.get('country', '')
##                state = obj_dict.get('state', '')
##                city_name = obj_dict.get('city_name', '')
##                
##                if autosuggest_dict.get(country, {}):
##                    country_dict = autosuggest_dict.get(country, {})
##                    if country_dict.get(state, {}):
##                        country_dict[state].append(city_name)
##                    else:
##                        country_dict[state] = [city_name]
##                else:
##                    autosuggest_dict = {country: {state:[city_name]}}
##
##
##                
##                autosuggest_data = f"{obj_dict.get('city_name', '')}, {obj_dict.get('state', '')}, {obj_dict.get('country', '')}"
##                autosuggest_list.append(autosuggest_data)
##            
##            response = self.get_response(
##                data=autosuggest_dict, count=len(autosuggest_list), status="success",
##                message="Location Autosuggest", status_code=status.HTTP_200_OK)
##            return response
##
##        state_queryset = self.queryset.filter(state__icontains=location).exclude(country='')
##        if state_queryset.count():
##            obj_list = state_queryset.values('state', 'country').distinct(
##                'state', 'country').order_by('state')
##
##            for obj_dict in obj_list:
##                autosuggest_data = f"{obj_dict.get('state', '')}, {obj_dict.get('country', '')}"
##                autosuggest_list.append(autosuggest_data)
##
##            response = self.get_response(
##                data=autosuggest_list, count=len(autosuggest_list), status="success",
##                message="Location Autosuggest", status_code=status.HTTP_200_OK)
##            return response      
##            
##
##        country_queryset = self.queryset.filter(country__icontains=location)
##        if country_queryset.count():
##            obj_list = country_queryset.values('country').distinct('country').order_by('country')
##
##            for obj_dict in obj_list:
##                autosuggest_data = f"{obj_dict.get('country', '')}"
##                autosuggest_list.append(autosuggest_data)
##
##            response = self.get_response(
##                data=autosuggest_list, count=len(autosuggest_list), status="success",
##                message="Location Autosuggest", status_code=status.HTTP_200_OK)
##            return response
##            
##        
        response = self.get_response(data=[], count=0, status="success", message="Location Autosuggest",
                                     status_code=status.HTTP_200_OK)
        return response
        


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


class RoomViewSet(viewsets.ModelViewSet, StandardResponseMixin, LoggingMixin):
    queryset = Room.objects.all()
    serializer_class = RoomSerializer
    # permission_classes = [AnonymousCanViewOnlyPermission,]
##    filter_backends = [DjangoFilterBackend]
##    filterset_fields = ['room_type', "carpet_area", "bed_count", "person_capacity", "child_capacity", "price_per_night",
##                        "price_for_4_hours", "price_for_8_hours", "price_for_12_hours", "price_for_24_hours",
##                        "discount", "availability", "property", "amenities", "room_type", "room_view", "bed_type", ]
    http_method_names = ['get', 'post', 'put', 'patch']
    # lookup_field = 'custom_id'

    permission_classes_by_action = {'create': [IsAuthenticated], 'update': [IsAuthenticated],
                                    'destroy': [IsAuthenticated], 'list':[AllowAny], 'retrieve':[AllowAny]}

    def get_permissions(self):
        try: 
            return [permission() for permission in self.permission_classes_by_action[self.action]]
        except KeyError: 
            # action is not set return default permission_classes
            return [permission() for permission in self.permission_classes]



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

        # Create an instance of your serializer with the request data and the object to be updated
        serializer = self.get_serializer(instance, data=request.data)

        if serializer.is_valid():
            # If the serializer is valid, perform the default update logic
            response = super().update(request, *args, **kwargs)

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
            response = self.get_response(data={}, count = media_count,
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
        
        room_gallery = hotel_db_utils.get_room_gallery(room_id)
        count, room_gallery = paginate_queryset(self.request,  room_gallery)
        serializer = RoomGallerySerializer(room_gallery, many=True)
        
        response = self.get_response(data=serializer.data, count = count,
                                     status="success", message="List Room Gallery",
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
