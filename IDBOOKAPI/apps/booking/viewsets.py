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
from IDBOOKAPI.utils import paginate_queryset, calculate_tax, get_days_from_string
from .serializers import (BookingSerializer, AppliedCouponSerializer, PreConfirmHotelBookingSerializer)
from .serializers import QueryFilterBookingSerializer, QueryFilterUserBookingSerializer
from .models import (Booking, HotelBooking, AppliedCoupon)

from apps.booking.tasks import send_booking_email_task, create_invoice_task
from apps.booking.utils.db_utils import get_user_based_booking, get_booking_based_tax_rule
from apps.booking.utils.booking_utils import (
    calculate_room_booking_amount, get_tax_rate,
    check_wallet_balance_for_booking, deduct_booking_amount,
    generate_booking_confirmation_code)
from apps.hotels.utils.db_utils import get_property_room_for_booking

from rest_framework.decorators import action
from django.db.models import Q, Sum
from IDBOOKAPI.basic_resources import BOOKING_TYPE

from django.db import transaction

from datetime import datetime

from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

##test_param = openapi.Parameter(
##    'test', openapi.IN_QUERY, description="test manual param",
##    type=openapi.TYPE_BOOLEAN)


class BookingViewSet(viewsets.ModelViewSet, StandardResponseMixin, LoggingMixin):
    queryset = Booking.objects.all()
    serializer_class = BookingSerializer
    permission_classes = [IsAuthenticated,]
##    filter_backends = [DjangoFilterBackend]
##    filterset_fields = ['property', 'room', 'user', 'coupon', 'booking_type', 'room_type', 'checkin_time',
##                        'checkout_time', 'bed_count', 'person_capacity', 'child_capacity', 'deal_price', 'discount',
##                        'final_amount', 'status', 'active', 'created', 'updated']
##    http_method_names = ['get', 'post', 'put', 'patch']
    # lookup_field = 'custom_id'

##    permission_classes_by_action = {'create': [IsAuthenticated], 'update': [IsAuthenticated]}
##
##    def get_permissions(self):
##        try: 
##            return [permission() for permission in self.permission_classes_by_action[self.action]]
##        except KeyError: 
##            # action is not set return default permission_classes
##            return [permission() for permission in self.permission_classes]


    def booking_filter_ops(self):
        
        filter_dict = {}
        exclude_dict = {}
        company_id, user_id = None, None
        
        user = self.request.user
        default_group = user.default_group

        # fetch filter parameters
        param_dict= self.request.query_params
        for key in param_dict:
            param_value = param_dict[key]

            if key in ('status', 'booking_type'):
                filter_dict[key] = param_value
            elif key == 'invoice_generated':
                if param_value in ('True', 'False', True, False):
                    if param_value == 'True':
                        param_value = True
                    elif param_value == 'False':
                        param_value = False  
                    exclude_dict['invoice_id__isnull'] = param_value
                
            
            if key == 'company_id':
                company_id =  param_value
            elif key == 'user_id':
                user_id = param_value
            
        
        print(user.category)
##        user.category = 'CL-CUST'
##        if user.category == 'B-ADMIN':
##             company_id = self.request.query_params.get('company_id', None)
        if user.category == 'CL-ADMIN':
            company_id = user.company_id if user.company_id else -1
            # user_id = self.request.query_params.get('user_id', None)
        elif user.category == 'CL-CUST':
            user_id = user.id
            company_id = user.company_id if user.company_id else -1
        
        if default_group == 'B2C-GRP':
           user_id = user.id
           company_id = None
           filter_dict['company_id__isnull'] = True
            
        # filter 
##        booking_status = self.request.query_params.get('status', '')
##        if booking_status:
##            filter_dict['status'] = booking_status
##        booking_type = self.request.query_params.get('booking_type', '')
##        if booking_type:
##            filter_dict['booking_type'] = booking_type
            
        if company_id:
            filter_dict['user__company_id'] = company_id
        if user_id:
            filter_dict['user__id'] = user_id

        # filter and exclude
        if exclude_dict:
            print("exclude dict::", exclude_dict)
            self.queryset = self.queryset.filter(**filter_dict).exclude(
                **exclude_dict)
        else:
            self.queryset = self.queryset.filter(**filter_dict)
        

        # search 
        search = self.request.query_params.get('search', '')
        if search:
            search_q_filter = Q(confirmation_code__icontains=search)
            self.queryset = self.queryset.filter(search_q_filter)


    def booking_pagination_ops(self):
        # offset and pagination
        offset = int(self.request.query_params.get('offset', 0))
        limit = int(self.request.query_params.get('limit', 10))

        count = self.queryset.count()
        self.queryset = self.queryset[offset:offset+limit]

        return count
    
##    @swagger_auto_schema(
##        manual_parameters=[test_param], operation_description="Create Booking",
##        request_body=openapi.Schema(
##            type=openapi.TYPE_OBJECT,
##            required=["data"],
##            properties={
##                "code": openapi.Schema(type=openapi.TYPE_STRING),
##            },
##         ),
##        responses={201: AppliedCouponSerializer(many=True)})

    #@swagger_auto_schema(query_serializer=BookingSerializer, request_body= BookingSerializer, manual_parameters=[test_param])
    def create(self, request, *args, **kwargs):
        self.log_request(request)  # Log the incoming request

        # Create an instance of your serializer with the request data
        serializer = self.get_serializer(data=request.data)

        if serializer.is_valid():
            # If the serializer is valid, perform the default creation logic
            response = super().create(request, *args, **kwargs)
            if response.data:
                booking_id = response.data.get('id')
                print("Booking Id", booking_id)
                booking_type = 'search-booking'
                send_booking_email_task.apply_async(args=[booking_id, booking_type])

            # Create a custom response
            custom_response = self.get_response(
                status="success",
                data=response.data,  # Use the data from the default response
                message="Booking Created",
                status_code=status.HTTP_201_CREATED,  # 201 for successful creation

            )
        else:
            # If the serializer is not valid, create a custom response with error details
            error_list = self.custom_serializer_error(serializer.errors)
            custom_response = self.get_error_response(
                message="Validation Error", status="error",
                errors=error_list,error_code="VALIDATION_ERROR", status_code=status.HTTP_400_BAD_REQUEST)

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
                status="success",
                data=response.data,  # Use the data from the default response
                message="Booking Updated",
                status_code=status.HTTP_200_OK,  # 200 for successful update

            )
        else:
            error_list = self.custom_serializer_error(serializer.errors)
            custom_response = self.get_error_response(
                message="Validation Error", status="error",
                errors=error_list,error_code="VALIDATION_ERROR", status_code=status.HTTP_400_BAD_REQUEST)
            
        self.log_response(custom_response)  # Log the custom response before returning
        return custom_response

    
    @swagger_auto_schema(
        query_serializer=QueryFilterBookingSerializer, operation_description="List Booking Based on User Roles",
        responses={200: BookingSerializer(many=True)})
    def list(self, request, *args, **kwargs):
        self.log_request(request)  # Log the incoming request

        # filter and pagination
        self.booking_filter_ops()
        count, self.queryset = paginate_queryset(self.request, self.queryset) #self.booking_pagination_ops()

        # Perform the default listing logic
        response = super().list(request, *args, **kwargs)

        if response.status_code == status.HTTP_200_OK:
            # If the response status code is OK (200), it's a successful listing
            custom_response = self.get_response(
                status="success",
                data=response.data,  # Use the data from the default response
                message="List Retrieved",
                count=count,
                status_code=status.HTTP_200_OK,  # 200 for successful listing

            )
        else:
            # If the response status code is not OK, it's an error
            custom_response = self.get_error_response(
                message="Error Occurred", data=None, status="error",
                errors=[],error_code="VALIDATION_ERROR", status_code=response.status_code)

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

    @swagger_auto_schema(
        query_serializer=QueryFilterUserBookingSerializer, operation_description="User Based Booking Retrieve",
        responses={200: BookingSerializer(many=True)})
    @action(detail=False, methods=['GET'], permission_classes=[IsAuthenticated],
            url_path='user/retrieve', url_name='user-retrieve')
    def user_based_retrieve(self, request):
  
##        self.queryset = self.queryset.filter(user=request.user)
##        
##        offset = int(self.request.query_params.get('offset', 0))
##        limit = int(self.request.query_params.get('limit', 10))
##        booking_status = self.request.query_params.get('status', '')
##
##        if booking_status:
##            self.queryset = self.queryset.filter(status=booking_status)
##        
##
##        count = self.queryset.count()
##        self.queryset = self.queryset[offset:offset+limit]

        # filter and pagination
        self.booking_filter_ops()
        # count = self.booking_pagination_ops()
        count, self.queryset = paginate_queryset(self.request, self.queryset)
        booking_serializer = BookingSerializer(self.queryset, many=True)
        
        response = self.get_response(
            data=booking_serializer.data, status="success", message="Retrieve Booking Success",
            count=count,
            status_code=status.HTTP_200_OK,
            )
        return response

    @action(detail=False, methods=['GET'], permission_classes=[IsAuthenticated],
            url_path='summary', url_name='booking-summary')
    def booking_summary(self, request):
        print("Inside booking summary")
        booking_summary = {}
        booking_type = self.request.query_params.get('booking_type', '')
        self.booking_filter_ops()
        if not booking_type:
            booking_type_list = BOOKING_TYPE #self.queryset.order_by().values_list('booking_type').distinct()
            
            for btype in booking_type_list:
                total_count  = self.queryset.filter(booking_type=btype[1]).count()
                total_booking_amount = self.queryset.filter(
                    booking_type=btype[0]).aggregate(Sum('final_amount'))
                total_amount = total_booking_amount.get('final_amount__sum')
                booking_summary[btype[1]] = {'total_booking_amount': total_amount,
                                             'total_count':total_count}
        else:
            total_count  = self.queryset.filter(booking_type=booking_type).count()
            total_booking_amount = self.queryset.filter(
                booking_type=booking_type).aggregate(Sum('final_amount'))
            total_amount = total_booking_amount.get('final_amount__sum')
            booking_summary[booking_type] = {'total_booking_amount': total_amount,
                                             'total_count':total_count}
                
            
        # total_booking_amount = self.queryset.aggregate(Sum('final_amount'))
        response = self.get_response(
            data=booking_summary, status="success", message="Booking Summary Success",
            status_code=status.HTTP_200_OK,
            )
        return response

    @action(detail=True, methods=['PATCH'], url_path='cancel',
            url_name='cancel', permission_classes=[IsAuthenticated])
    def cancel_booking(self, request, pk=None):
        """customer can cancel their booking"""
        user = request.user
        print("Booking Id::", pk)
        instance = get_user_based_booking(user.id, pk)
        if instance:
            instance.status = 'canceled'
            instance.save()
            custom_response = self.get_response(
                status='success', data=None,
                message="Booking Cancelled Successfully",
                status_code=status.HTTP_200_OK,
                )
        else:
                custom_response = self.get_error_response(
                    message="Booking Not Found for the User", status="error",
                    errors=[],error_code="BOOKING_ID_MISSING",
                    status_code=status.HTTP_404_NOT_FOUND)
        return custom_response

    @action(detail=False, methods=['POST'], url_path='hotel/pre-confirm',
            url_name='hotel-pre-confirm', permission_classes=[IsAuthenticated])
    def hotel_pre_confirm_booking(self, request):
        self.log_request(request)

        user = self.request.user
        property_id = request.data.get('property', None)
        company_id = request.data.get('company', None)
        room_list = request.data.get('room_list', [])
        
        coupon_code = request.data.get('coupon_code', None)
        
        confirmed_room_details = []
        
        final_amount, final_tax_amount = 0, 0

        
        confirmed_checkin_time = request.data.get('confirmed_checkin_time', None)
        confirmed_checkout_time = request.data.get('confirmed_checkout_time', None)

        if not confirmed_checkin_time or not confirmed_checkout_time:
            custom_response = self.get_error_response(
                message="check in and check out missing", status="error",
                errors=[],error_code="DATE_MISSING",
                status_code=status.HTTP_400_BAD_REQUEST)

            return custom_response
        

        if not property_id:
            custom_response = self.get_error_response(
                message="Property missing", status="error",
                errors=[],error_code="PROPERTY_MISSING",
                status_code=status.HTTP_400_BAD_REQUEST)

            return custom_response

        if not room_list or not isinstance(room_list, list):
            custom_response = self.get_error_response(
                message="Missing Room list or invalid list format", status="error",
                errors=[],error_code="ROOM_MISSING",
                status_code=status.HTTP_400_BAD_REQUEST)

            return custom_response

        # get no of  days from  checkin and checkout
        no_of_days = get_days_from_string(
            confirmed_checkin_time, confirmed_checkout_time,
            string_format="%Y-%m-%dT%H:%M%z")

        if no_of_days is None:
            custom_response = self.get_error_response(
                message="Error in date conversion", status="error",
                errors=[],error_code="DATE_ERROR",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
            return custom_response

        if no_of_days == 0:
            custom_response = self.get_error_response(
                message="Less than 24 hours slot booking is not allowed", status="error",
                errors=[],error_code="BOOKING_SLOT_ERROR",
                status_code=status.HTTP_400_BAD_REQUEST)
            return custom_response

        tax_rules_dict = get_booking_based_tax_rule('HOTEL')
        if not tax_rules_dict:
            custom_response = self.get_error_response(
                message="Tax Rule Missing", status="error",
                errors=[],error_code="TAX_RULE_MISSING",
                status_code=status.HTTP_400_BAD_REQUEST)
            return custom_response
            


        try:
            
            for room in room_list:
                room_id = room.get('room_id', None)
                no_of_rooms = room.get('no_of_rooms', None)
                base_price = 0

                # get room details
                room_detail = get_property_room_for_booking(property_id, room_id)
                if not room_detail:
                    custom_response = self.get_error_response(
                        message=f"The room: {room_id} is missing for the property", status="error",
                        errors=[],error_code="ROOM_MISSING",
                        status_code=status.HTTP_400_BAD_REQUEST)
                    return custom_response

                # get room details
                room_type = room_detail.get('room_type')
                room_price = room_detail.get('room_price')
                if not room_price:
                    custom_response = self.get_error_response(
                        message=f"The room price details for {room_id} is missing", status="error",
                        errors=[],error_code="ROOM_PRICE_MISSING",
                        status_code=status.HTTP_400_BAD_REQUEST)
                    return custom_response

                # get 24 hours price
                base_price = room_price.get('base_rate', None)
                if not base_price:
                    custom_response = self.get_error_response(
                        message=f"The room price details for room id {room_id} is missing", status="error",
                        errors=[],error_code="ROOM_PRICE_MISSING",
                        status_code=status.HTTP_400_BAD_REQUEST)
                    return custom_response
                    
                # get tax percent based on amount
                tax_in_percent = get_tax_rate(base_price, tax_rules_dict)
                if not tax_in_percent:
                    custom_response = self.get_error_response(
                        message=f"The room price details for room id {room_id} is missing", status="error",
                        errors=[],error_code="ROOM_PRICE_MISSING",
                        status_code=status.HTTP_400_BAD_REQUEST)
                    return custom_response

                tax_in_percent = float(tax_in_percent)
                tax_amount = calculate_tax(tax_in_percent, base_price)

                # calculate total tax amount
                total_tax_amount =   calculate_room_booking_amount(
                    tax_amount, no_of_days, no_of_rooms) #(tax_amount * no_of_days) * no_of_rooms
                # calculate total room amount
                total_room_amount = calculate_room_booking_amount(
                    base_price, no_of_days, no_of_rooms) #(base_price * no_of_days) * no_of_rooms
                
                final_room_total = total_room_amount + total_tax_amount

                
                confirmed_room = {"room_id": room_id, "room_type":room_type, "price": base_price,
                                  "no_of_rooms": no_of_rooms,
                                  "tax_in_percent": tax_in_percent, "tax_amount": tax_amount,
                                  "total_tax_amount": total_tax_amount,
                                  "no_of_days": no_of_days, "total_room_amount":total_room_amount,
                                  "final_room_total": final_room_total, "booking_slot":24}
                
                confirmed_room_details.append(confirmed_room)
                # final amount
                final_amount = final_amount + final_room_total
                final_tax_amount = final_tax_amount + total_tax_amount
        

            with transaction.atomic():
                    
                hotel_booking = HotelBooking(
                    confirmed_property_id=property_id, confirmed_room_details=confirmed_room_details,
                    confirmed_checkin_time=confirmed_checkin_time,
                    confirmed_checkout_time=confirmed_checkout_time)
                hotel_booking.save()
                
                booking = Booking(user_id=user.id, hotel_booking=hotel_booking, booking_type='HOTEL',
                                  final_amount=final_amount, gst_amount=final_tax_amount)
                if company_id:
                    booking.company_id = company_id
                    
                booking.save()

                # wallet balance check and send notification for low balance
                check_wallet_balance_for_booking(booking, user, company_id=company_id)
   
                serializer = PreConfirmHotelBookingSerializer(booking)
                
                custom_response = self.get_response(
                    status='success', data=serializer.data,
                    message="Booking Details", status_code=status.HTTP_200_OK,)

                self.log_response(custom_response)

                return custom_response
                
        except Exception as e:
            custom_response = self.get_error_response(
                message=str(e), status="error",
                errors=[],error_code="INERNAL_ERROR",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

            self.log_response(custom_response)

            return custom_response

    @action(detail=True, methods=['PATCH'], url_path='confirm',
            url_name='confirm', permission_classes=[IsAuthenticated])
    def confirm_booking(self, request, pk):
        
        instance = self.get_object()
      
        deduct_status = deduct_booking_amount(instance, instance.company_id)
        if not deduct_status:
            custom_response = self.get_error_response(
                message="Error in wallet deduction", status="error",
                errors=[], error_code="WALLET_ERROR",
                status_code=status.HTTP_400_BAD_REQUEST)
            return custom_response

        booking_id = instance.id
        booking_type = instance.booking_type
        
        confirmation_code = generate_booking_confirmation_code(booking_id, booking_type)
        print("Confirmation Code::", confirmation_code)
        instance.confirmation_code = confirmation_code
        instance.total_payment_made = instance.final_amount
        instance.status = 'confirmed'
        instance.save()
        
        create_invoice_task.apply_async(args=[booking_id])
            
        custom_response = self.get_response(
            status='success', data=None,
            message="Booking Confirmed", status_code=status.HTTP_200_OK,)

        return custom_response


class AppliedCouponViewSet(viewsets.ModelViewSet, StandardResponseMixin, LoggingMixin):
    queryset = AppliedCoupon.objects.all()
    serializer_class = AppliedCouponSerializer
    permission_classes = [AnonymousCanViewOnlyPermission,]
    # filter_backends = [DjangoFilterBackend]
    # filterset_fields = ['service_category', 'district', 'area_name', 'city_name', 'starting_price', 'rating',]
    http_method_names = ['get', 'post', 'put', 'patch']
    # lookup_field = 'custom_id'

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
                message="Applied Coupon Created",
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
                message="Applied Coupon Updated",
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
