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
from .serializers import (BookingSerializer, AppliedCouponSerializer,
                          PreConfirmHotelBookingSerializer, ReviewSerializer,
                          BookingPaymentDetailSerializer)
from .serializers import QueryFilterBookingSerializer, QueryFilterUserBookingSerializer
from .models import (Booking, HotelBooking, AppliedCoupon, Review, BookingPaymentDetail)

from apps.booking.tasks import send_booking_email_task, create_invoice_task
from apps.booking.utils.db_utils import (
    get_user_based_booking, get_booking_based_tax_rule,
    check_review_exist_for_booking, create_booking_payment_details,
    update_booking_payment_details, check_booking_and_transaction,
    get_booking_from_payment, check_room_booked_details, get_booking)
from apps.booking.utils.booking_utils import (
    calculate_room_booking_amount, get_tax_rate,
    check_wallet_balance_for_booking, deduct_booking_amount,
    generate_booking_confirmation_code)

from apps.hotels.utils.db_utils import get_property_room_for_booking
from apps.hotels.utils.hotel_utils import check_room_count, total_room_count

from apps.coupons.utils.db_utils import get_coupon_from_code
from apps.coupons.utils.coupon_utils import apply_coupon_based_discount
from apps.payment_gateways.mixins.phonepay_mixins import PhonePayMixin
from apps.log_management.utils.db_utils import create_booking_payment_log

from apps.authentication.utils.db_utils import get_user_from_email, create_user
from apps.authentication.utils.authentication_utils import add_group_based_on_signup

from rest_framework.decorators import action
from django.db.models import Q, Sum
from IDBOOKAPI.basic_resources import BOOKING_TYPE

from django.db import transaction

from datetime import datetime

from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

import traceback
import base64, json

from django.conf import settings

from datetime import datetime, timedelta
from pytz import timezone

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
            url_name='hotel-pre-confirm', permission_classes=[])
    def hotel_pre_confirm_booking(self, request):
        self.log_request(request)

        user = self.request.user
        
        property_id = request.data.get('property', None)
        company_id = request.data.get('company', None)
        room_list = request.data.get('room_list', [])
        requested_room_no = request.data.get('requested_room_no', 1)

        adult_count = request.data.get('adult_count', 1)
        child_count = request.data.get('child_count', 0)
        child_age_list = request.data.get('child_age_list', [])
        infant_count = request.data.get('infant_count', 0)
        booking_slot = request.data.get('booking_slot', '24 Hrs')
        
        
        coupon_code = request.data.get('coupon_code', None)
        coupon = None
        
        confirmed_room_details = []
        
        final_amount, final_tax_amount, subtotal = 0, 0, 0

        
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

        if not isinstance(child_age_list, list):
            custom_response = self.get_error_response(
                message="invalid child age list format", status="error",
                errors=[],error_code="CHILD_AGE_ERROR",
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
            no_of_days = 1
##            custom_response = self.get_error_response(
##                message="Less than 24 hours slot booking is not allowed", status="error",
##                errors=[],error_code="BOOKING_SLOT_ERROR",
##                status_code=status.HTTP_400_BAD_REQUEST)
##            return custom_response

        tax_rules_dict = get_booking_based_tax_rule('HOTEL')
        if not tax_rules_dict:
            custom_response = self.get_error_response(
                message="Tax Rule Missing", status="error",
                errors=[],error_code="TAX_RULE_MISSING",
                status_code=status.HTTP_400_BAD_REQUEST)
            return custom_response
            

        try:
            # get coupon details
            if coupon_code:
                coupon = get_coupon_from_code(coupon_code)
                if not coupon:
                    custom_response = self.get_error_response(
                        message="Invalid coupon", status="error",
                        errors=[],error_code="COUPON_ERROR",
                        status_code=status.HTTP_400_BAD_REQUEST)
                    return custom_response
            
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

                if booking_slot == '12 Hrs':
                    slot_price = room_price.get('price_12hrs', None)
                    booking_room_price = slot_price
                elif booking_slot == '8 Hrs':
                    slot_price = room_price.get('price_8hrs', None)
                    booking_room_price = slot_price
                elif booking_slot == '4 Hrs':
                    slot_price = room_price.get('price_4hrs', None)
                    booking_room_price = slot_price
                else:
                    slot_price = None
                    booking_room_price = base_price
                    
                if not slot_price and not booking_slot == '24 Hrs':
                    custom_response = self.get_error_response(
                        message=f"The {booking_slot} hrs room price for room id {room_id} is missing", status="error",
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

                # tax percentage based on base price
                tax_in_percent = float(tax_in_percent)
                # tax calculation based on booked 
                if booking_slot == '24 Hrs':
                    tax_amount = calculate_tax(tax_in_percent, base_price)
                else:
                    tax_amount = calculate_tax(tax_in_percent, slot_price)

                # calculate total tax amount
                total_tax_amount =   calculate_room_booking_amount(
                    tax_amount, no_of_days, no_of_rooms)
                
                # calculate total room amount
                if booking_slot == '24 Hrs':
                    total_room_amount = calculate_room_booking_amount(
                        base_price, no_of_days, no_of_rooms)
                else:
                    total_room_amount = calculate_room_booking_amount(
                        slot_price, no_of_days, no_of_rooms)
                
                final_room_total = total_room_amount + total_tax_amount

                
                confirmed_room = {"room_id": room_id, "room_type":room_type, "base_price":base_price,
                                  "price": booking_room_price,
                                  "no_of_rooms": no_of_rooms,
                                  "tax_in_percent": tax_in_percent, "tax_amount": tax_amount,
                                  "total_tax_amount": total_tax_amount,
                                  "no_of_days": no_of_days, "total_room_amount":total_room_amount,
                                  "final_room_total": final_room_total, "booking_slot":booking_slot}
                
                confirmed_room_details.append(confirmed_room)
                # final amount
                # final_amount = final_amount + final_room_total
                final_tax_amount = final_tax_amount + total_tax_amount
                subtotal = subtotal + total_room_amount # total room amount without tax and services
        

            with transaction.atomic():

                # apply coupon discount
                if coupon:
                    coupon_discount_type = coupon.discount_type
                    coupon_discount = coupon.discount
                    discount, subtotal_after_discount = apply_coupon_based_discount(
                        coupon_discount, coupon_discount_type, subtotal)

                    final_amount = float(subtotal_after_discount) + final_tax_amount
                else:
                    discount = 0
                    final_amount = subtotal + final_tax_amount

##                tm ='Asia/Kolkata'
##                local_dt = timezone.localtime(item.created_at, pytz.timezone(tm))


                # check the room availability before locking
                room_confirmed_dict = total_room_count(confirmed_room_details)
                booked_rooms = check_room_booked_details(
                    confirmed_checkin_time, confirmed_checkout_time,
                    property_id, is_slot_price_enabled=True, booking_id=None)
                room_rejected_list = check_room_count(booked_rooms, room_confirmed_dict)
                    
                hotel_booking = HotelBooking(
                    confirmed_property_id=property_id, confirmed_room_details=confirmed_room_details,
                    confirmed_checkin_time=confirmed_checkin_time,
                    confirmed_checkout_time=confirmed_checkout_time,
                    booking_slot=booking_slot, requested_room_no=requested_room_no)
                hotel_booking.save()
                
                booking = Booking(user_id=user.id, hotel_booking=hotel_booking, booking_type='HOTEL',
                                  subtotal=subtotal, discount=discount, final_amount=final_amount,
                                  gst_amount=final_tax_amount, adult_count=adult_count,
                                  child_count=child_count, infant_count=infant_count,
                                  child_age_list=child_age_list)

                if coupon:
                    booking.coupon_code = coupon_code
                    
                if company_id:
                    booking.company_id = company_id

                if not room_rejected_list:
                    on_hold_end_time = datetime.now(timezone('UTC')) + timedelta(minutes=5)
                    booking.status = 'on_hold'
                    booking.on_hold_end_time = on_hold_end_time
                    
                booking.save()

                # create and save merchant transaction id for payment reference
##                append_id = "%s" % (user.id)
##                booking_payment_detail = create_booking_payment_details(booking.id, append_id)
##                merchant_transaction_id = booking_payment_detail.merchant_transaction_id

                # wallet balance check and send notification for low balance
                if user.id:
                    check_wallet_balance_for_booking(booking, user, company_id=company_id)
   
                serializer = PreConfirmHotelBookingSerializer(booking)
                
                booking_dict = {'merchant_transaction_id': ''}
                booking_dict.update(serializer.data)
                
                custom_response = self.get_response(
                    status='success', count=1, data=booking_dict,
                    message="Booking Details", status_code=status.HTTP_200_OK,)

                self.log_response(custom_response)

                return custom_response
                
        except Exception as e:
            print(traceback.format_exc())
            custom_response = self.get_error_response(
                message=str(e), status="error",
                errors=[],error_code="INERNAL_ERROR",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

            self.log_response(custom_response)

            return custom_response


    @action(detail=True, methods=['PATCH'], url_path='apply-coupon',
            url_name='apply-coupon', permission_classes=[IsAuthenticated])
    def apply_coupon_pre_booking(self, request, pk):
        coupon_code = request.data.get('coupon_code', None)
        coupon = None
        
        instance = self.get_object()

        if not coupon_code:
            custom_response = self.get_error_response( message="Invalid coupon", status="error",
                                                       errors=[],error_code="COUPON_ERROR",
                                                       status_code=status.HTTP_400_BAD_REQUEST)
            return custom_response

            
        coupon = get_coupon_from_code(coupon_code)
        if not coupon:
            custom_response = self.get_error_response(
                message="Invalid coupon", status="error",
                errors=[],error_code="COUPON_ERROR",
                status_code=status.HTTP_400_BAD_REQUEST)
            return custom_response

        subtotal = instance.subtotal
        # final_amount = instance.final_amount
        tax_amount = instance.gst_amount
        
        coupon_discount_type = coupon.discount_type
        coupon_discount = coupon.discount
        discount, subtotal_after_discount = apply_coupon_based_discount(
            coupon_discount, coupon_discount_type, subtotal)

        final_amount = subtotal_after_discount + tax_amount

        # save the deduction details based on discount
        instance.final_amount = final_amount
        instance.discount = discount
        instance.coupon_code = coupon_code
        instance.save()

        serializer = PreConfirmHotelBookingSerializer(instance)
                
        custom_response = self.get_response(
            status='success', data=serializer.data,
            message="Booking Details", status_code=status.HTTP_200_OK,)

        self.log_response(custom_response)

        return custom_response
        
        
        

    @action(detail=True, methods=['PATCH'], url_path='confirm',
            url_name='confirm', permission_classes=[IsAuthenticated])
    def confirm_booking(self, request, pk):
        instance = self.get_object()
        user = self.request.user
        
        if not instance.hotel_booking:
            custom_response = self.get_error_response(
                message="Error in data; Please check the details",
                status="error", errors=[], error_code="VALIDATION_ERROR",
                status_code=status.HTTP_400_BAD_REQUEST)
            return custom_response

        if not instance.user:
            custom_response = self.get_error_response(
                message="The booking is not associated with any user",
                status="error", errors=[], error_code="VALIDATION_ERROR",
                status_code=status.HTTP_400_BAD_REQUEST)
            return custom_response

        property_id = instance.hotel_booking.confirmed_property_id
        room_details = instance.hotel_booking.confirmed_room_details
        checkin_time = instance.hotel_booking.confirmed_checkin_time
        checkout_time = instance.hotel_booking.confirmed_checkout_time
        booking_slot = instance.hotel_booking.booking_slot
        
##        if booking_slot == "24 Hrs":
##            is_slot_price_enabled = False
##            checkin_date = checkin_time.date()
##            checkout_date = checkout_time.date()
##        else:
##            is_slot_price_enabled = True
##            checkin_date = checkin_time
##            checkout_date = checkout_time

        is_slot_price_enabled = True
        checkin_date = checkin_time
        checkout_date = checkout_time

        room_confirmed_dict = total_room_count(room_details)
        print(room_confirmed_dict)

        booked_rooms = check_room_booked_details(checkin_date, checkout_date,
                                                 property_id, is_slot_price_enabled,
                                                 booking_id = instance.id)
        print("booked rooms::", booked_rooms)
        room_rejected_list = check_room_count(booked_rooms, room_confirmed_dict)

        if room_rejected_list:
            custom_response = self.get_error_response(
                message="Some of the selected rooms are allready booked, please refresh your list",
                status="error", errors=room_rejected_list, error_code="BOOKING_ERROR",
                status_code=status.HTTP_400_BAD_REQUEST)
            return custom_response

        # generate merchant transaction id
        append_id = "%s" % (user.id)
        booking_payment_detail = create_booking_payment_details(instance.id, append_id)
        # merchant_transaction_id = booking_payment_detail.merchant_transaction_id
      
        deduct_status = deduct_booking_amount(instance, instance.company_id)
        if not deduct_status:
            booking_payment_detail.code = "PAYMENT_ERROR"
            booking_payment_detail.message = "Insufficient fund in wallet balance"
            booking_payment_detail.payment_type = "WALLET"
            booking_payment_detail.payment_medium = "Idbook"
            booking_payment_detail.is_transaction_success = False
            booking_payment_detail.save()
            
            custom_response = self.get_error_response(
                message="Error in wallet deduction; Please make sure wallet has sufficient fund",
                status="error", errors=[], error_code="WALLET_ERROR",
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

        booking_payment_detail.code = "PAYMENT_SUCCESS"
        booking_payment_detail.message = "Your payment is successful."
        booking_payment_detail.payment_type = "WALLET"
        booking_payment_detail.payment_medium = "Idbook"
        booking_payment_detail.amount = instance.final_amount
        booking_payment_detail.is_transaction_success = True
        booking_payment_detail.save()
        
        create_invoice_task.apply_async(args=[booking_id])
            
        custom_response = self.get_response(
            status='success', data=None,
            message="Booking Confirmed", status_code=status.HTTP_200_OK,)

        return custom_response

class ReviewViewSet(viewsets.ModelViewSet, StandardResponseMixin, LoggingMixin):
    queryset = Review.objects.all()
    serializer_class = ReviewSerializer
    # permission_classes = [IsAuthenticated,]
    # permission_classes = [AnonymousCanViewOnlyPermission,]
    http_method_names = ['get', 'post', 'put', 'patch']

    permission_classes_by_action = {'create': [IsAuthenticated], 'update': [IsAuthenticated],
                                    'partial_update': [IsAuthenticated],
                                    'destroy': [IsAuthenticated], 'list':[AllowAny], 'retrieve':[AllowAny]}

    def get_permissions(self):
        try:
            return [permission() for permission in self.permission_classes_by_action[self.action]]
        except KeyError: 
            # action is not set return default permission_classes
            return [permission() for permission in self.permission_classes]

    def review_filter_ops(self):
        
        filter_dict = {}
        # fetch filter parameters
        param_dict= self.request.query_params
        for key in param_dict:
            if key in ('booking', 'property', 'user'):
                filter_dict[key] = param_dict[key]

        if filter_dict:
            self.queryset = self.queryset.filter(**filter_dict)

        

    def create(self, request, *args, **kwargs):
        self.log_request(request)  # Log the incoming request

        booking_id = request.data.get('booking', None)
        review_exist = check_review_exist_for_booking(booking_id)
        if review_exist:
            custom_response = self.get_error_response(message="Review already done for the booking", status="error",
                                                      errors=[],error_code="DUPLICATE_REVIEW",
                                                      status_code=status.HTTP_400_BAD_REQUEST)
            return custom_response
            

        # Create an instance of your serializer with the request data
        serializer = self.get_serializer(data=request.data)

        if serializer.is_valid():
            # If the serializer is valid, perform the default creation logic
            response = super().create(request, *args, **kwargs)

            # Create a custom response
            custom_response = self.get_response(
                status="success",
                data=response.data,  # Use the data from the default response
                message="Review Created",
                status_code=status.HTTP_201_CREATED,  # 201 for successful creation

            )
        else:
            custom_response = self.get_error_response(message="Validation Error", status="error",
                                                      errors=[],error_code="VALIDATION_ERROR",
                                                      status_code=status.HTTP_400_BAD_REQUEST)

        self.log_response(custom_response)  # Log the custom response before returning
        return custom_response

    def list(self, request, *args, **kwargs):
        self.log_request(request)  # Log the incoming request

        self.review_filter_ops()
        # paginate the result
        count, self.queryset = paginate_queryset(self.request,  self.queryset)

        # Perform the default listing logic
        response = super().list(request, *args, **kwargs)

        if response.status_code == status.HTTP_200_OK:
            # If the response status code is OK (200), it's a successful listing
            custom_response = self.get_response(
                status="success",
                count=count,
                data=response.data,  # Use the data from the default response
                message="List Retrieved",
                status_code=status.HTTP_200_OK,  # 200 for successful listing

            )
        else:
            custom_response = self.get_error_response(message="Validation Error", status="error",
                                                      errors=[],error_code="VALIDATION_ERROR",
                                                      status_code=status.HTTP_400_BAD_REQUEST)

        self.log_response(custom_response)  # Log the custom response before returning
        return custom_response

    def retrieve(self, request, *args, **kwargs):
        self.log_request(request)  # Log the incoming request

        # Perform the default retrieval logic
        response = super().retrieve(request, *args, **kwargs)

        if response.status_code == status.HTTP_200_OK:
            # If the response status code is OK (200), it's a successful retrieval
            custom_response = self.get_response(
                status="success",
                data=response.data,  # Use the data from the default response
                message="Item Retrieved",
                status_code=status.HTTP_200_OK,  # 200 for successful retrieval

            )
        else:
            custom_response = self.get_error_response(message="Validation Error", status="error",
                                                      errors=[],error_code="VALIDATION_ERROR",
                                                      status_code=status.HTTP_400_BAD_REQUEST)

        self.log_response(custom_response)  # Log the custom response before returning
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

class BookingPaymentDetailViewSet(viewsets.ModelViewSet, StandardResponseMixin, LoggingMixin, PhonePayMixin):
    queryset = BookingPaymentDetail.objects.all()
    serializer_class = BookingPaymentDetailSerializer
    permission_classes = []

    def cross_check_booking_availability(self, instance):
        property_id = instance.hotel_booking.confirmed_property_id
        room_details = instance.hotel_booking.confirmed_room_details
        checkin_time = instance.hotel_booking.confirmed_checkin_time
        checkout_time = instance.hotel_booking.confirmed_checkout_time
        booking_slot = instance.hotel_booking.booking_slot
        
##        import pytz
##        tm ='Asia/Kolkata'
##        local_dt = timezone.localtime(item.created_at, pytz.timezone(tm))
        
##        if booking_slot == "24 Hrs":
##            is_slot_price_enabled = False
##            checkin_date = checkin_time.date()
##            checkout_date = checkout_time.date()
##        else:
##            is_slot_price_enabled = True
##            checkin_date = checkin_time
##            checkout_date = checkout_time

        is_slot_price_enabled = True
        checkin_date = checkin_time
        checkout_date = checkout_time

        room_confirmed_dict = total_room_count(room_details)
        print(room_confirmed_dict)

        booked_rooms = check_room_booked_details(
            checkin_date, checkout_date, property_id,
            is_slot_price_enabled, booking_id=instance.id)
        room_rejected_list = check_room_count(booked_rooms, room_confirmed_dict)
        return room_rejected_list

        if room_rejected_list:
            custom_response = self.get_error_response(
                message="Some of the selected rooms are allready booked, please refresh your list",
                status="error", errors=room_rejected_list, error_code="BOOKING_ERROR",
                status_code=status.HTTP_400_BAD_REQUEST)
            return custom_response


    @action(detail=False, methods=['POST'], url_path='initiate',
            url_name='initiate', permission_classes=[])
    def phone_pay_call_initiate(self, request):

        try:
            user = request.user
            booking_payment_log = {}
            
            user_id = self.request.user.id
            
            booking_id = request.data.get('booking', None)
            booking_payment_log['booking_id'] = booking_id
##            merchant_transaction_id = request.data.get('merchant_transaction_id', None)
##            booking_payment_log['merchant_transaction_id'] = merchant_transaction_id
            
            redirect_url = request.data.get('redirect_url', '')
            payment_channel = request.data.get('payment_channel')

            booking = get_booking(booking_id)
            if not booking:
                custom_response = self.get_error_response(message="Booking not exist", status="error",
                                                          errors=[],error_code="VALIDATION_ERROR",
                                                          status_code=status.HTTP_400_BAD_REQUEST)
                return custom_response
                

##            is_exist = check_booking_and_transaction(booking_id, merchant_transaction_id)
##            if not is_exist:
##                message = "Booking or merchant transaction id not registered with booking payment system"
##                custom_response = self.get_error_response(message=message, status="error",
##                                                          errors=[],error_code="VALIDATION_ERROR",
##                                                          status_code=status.HTTP_400_BAD_REQUEST)
##                return custom_response
                
            amount = request.data.get('amount', None)
            if not amount:
                custom_response = self.get_error_response(message="Amount mismatch", status="error",
                                                          errors=[],error_code="VALIDATION_ERROR",
                                                          status_code=status.HTTP_400_BAD_REQUEST)
                return custom_response

            #https://mercury-uat.phonepe.com/transact/simulator?token=87tM6GJCcJ142nCtz6gGhFHm9DCL3H4LepDHs5

            room_rejected_list = self.cross_check_booking_availability(booking)
            if room_rejected_list:
                custom_response = self.get_error_response(
                    message="Some of the selected rooms are allready booked, please refresh your list",
                    status="error", errors=room_rejected_list, error_code="BOOKING_ERROR",
                    status_code=status.HTTP_400_BAD_REQUEST)
                return custom_response


            if not user.id:
                user_details =  self.request.data.get('user_details', {})
                name = user_details.get('name', '')
                email = user_details.get('email', '')
                mobile_number = user_details.get('mobile_number', '')
                
                if not email:
                    custom_response = self.get_error_response(
                        message="Missing user email",
                        status="error", errors=[], error_code="VALIDATION_ERROR",
                        status_code=status.HTTP_400_BAD_REQUEST)
                    return custom_response
                   

                user = get_user_from_email(email)
                if not user:
                    user = create_user(user_details)
                    add_group_based_on_signup(user, '')
                else:
                    user.name = name
                    user.mobile_number = mobile_number
                    user.save()

            # generate merchant transaction id
            append_id = "%s" % (user.id)
            booking_payment_detail = create_booking_payment_details(booking.id, append_id)
            merchant_transaction_id = booking_payment_detail.merchant_transaction_id

            if not booking.user:
                booking.user_id = user.id
                booking.save()
                
            # payment_channel = 'PHONE PAY'
            if payment_channel == 'PHONE PAY':
                merchant_id = settings.MERCHANT_ID
                callback_url = settings.CALLBACK_URL + "/api/v1/booking/payment/phone-pay/callbackurl/"
                
                payload = {
                    "merchantId": merchant_id,
                    "merchantTransactionId": merchant_transaction_id,
                    "merchantUserId": user_id,
                    "amount": amount * 100,
                    "redirectUrl": redirect_url, # "https://webhook.site/redirect-url",
                    "redirectMode": "REDIRECT",
                    "callbackUrl": callback_url, #https://webhook.site/592b9daf-b744-4fe8-97f1-652f1d4b65bd
                    "paymentInstrument":{ "type": "PAY_PAGE"}
                    }

                booking_payment_log['request'] = payload

                req, auth_header = self.get_encrypted_header_and_payload(payload)
                response = self.post_pay_page(req, auth_header)

                if response.status_code == 200:
                    data_json = response.json()
                    booking_payment_log['response'] = data_json
                    instrument_response = data_json.get('data').get('instrumentResponse',{})
                    data_json.pop('data')
                    data_json['instrumentResponse'] = instrument_response
                    custom_response = self.get_response(
                        status="success",
                        count=1,
                        data=data_json,  # Use the data from the default response
                        message="Payment Initiate Url",
                        status_code=status.HTTP_200_OK,  # 200 for successful retrieval
                        )
                    create_booking_payment_log(booking_payment_log)
                    return custom_response
                else:
                    
                    booking_payment_log['response'] = {'message': response.text}
                    custom_response = self.get_error_response(message=response.text, status="error",
                                                              errors=[],error_code="PAYMENT_ERROR",
                                                          status_code=status.HTTP_400_BAD_REQUEST)
                    create_booking_payment_log(booking_payment_log)
                    return custom_response


            custom_response = self.get_error_response(message="Invalid option", status="error",
                                                      errors=[],error_code="VALIDATION_ERROR",
                                                      status_code=status.HTTP_400_BAD_REQUEST)
            return custom_response
        except Exception as e:
            print(traceback.format_exc())
            booking_payment_log['response'] = {'message': str(e)}
            custom_response = self.get_error_response(message=str(e), status="error",
                                                      errors=[],error_code="INTERNAL_SERVER_ERROR",
                                                      status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
            create_booking_payment_log(booking_payment_log)
            return custom_response

    def set_booking_as_confirmed(self, booking_id, amount):
        booking = Booking.objects.get(id=booking_id)
        if booking:
            booking_id = booking.id
            booking_type = booking.booking_type
        
            confirmation_code = generate_booking_confirmation_code(booking_id, booking_type)
            print("Confirmation Code::", confirmation_code)
            booking.confirmation_code = confirmation_code
            booking.total_payment_made = amount
            booking.status = 'confirmed'
            booking.save()
        
            create_invoice_task.apply_async(args=[booking_id])
            
    
    @action(detail=False, methods=['POST'], url_path='phone-pay/callbackurl',
            url_name='phone-pay-callbackurl', permission_classes=[])
    def phone_pay_callbackurl(self, request):
        try:
            self.log_request(request)
            booking_payment_log = {}
            x_verify = request.META.get('HTTP_X_VERIFY', None)
            booking_payment_log['x_verify'] = x_verify
            response = request.data.get('response', None)

            if not response:
                custom_response = self.get_error_response(
                    message="Error in Response", status="error",
                    errors=[],error_code="VALIDATION_ERROR",
                    status_code=status.HTTP_400_BAD_REQUEST)
                booking_payment_log['request'] = {"message":"empty request"}
                create_booking_payment_log(booking_payment_log)
                return custom_response
            booking_payment_log['request'] = {"response": response}
            data = base64.b64decode(response)
            decoded_data =  data.decode('utf-8')
            json_data = json.loads(decoded_data)
            booking_payment_log['request'] = json_data
            
            code = json_data.get('code', '')
            message = json_data.get('message', '')

            
            
            sub_json_data = json_data.get('data', {})
            amount = sub_json_data.get('amount', 0)/100
            merchant_transaction_id = sub_json_data.get('merchantTransactionId', '')
            booking_payment_log['merchant_transaction_id'] = merchant_transaction_id
            transaction_id = sub_json_data.get('transactionId', '')        
            print(json_data)

            booking_payment_details = {
                "transaction_id": transaction_id, "code": code,
                "message":message, "payment_type": "PAYMENT GATEWAY",
                "payment_medium": "PHONE PAY", "amount": amount, "transaction_details": sub_json_data}

            if code == "PAYMENT_SUCCESS":
                booking_payment_details["is_transaction_success"] = True

            update_booking_payment_details(merchant_transaction_id, booking_payment_details)
            booking_id = get_booking_from_payment(merchant_transaction_id)
            booking_payment_log['booking_id'] = booking_id
            self.set_booking_as_confirmed(booking_id, amount)

            custom_response = self.get_response(
                status="success",
                data=booking_payment_details,  # Use the data from the default response
                message="Booking Confirmed",
                status_code=status.HTTP_200_OK,  # 200 for successful retrieval
                )
            booking_payment_log['response'] = booking_payment_details
            create_booking_payment_log(booking_payment_log)
            return custom_response
        except Exception as e:
            custom_response = self.get_error_response(message=str(e), status="error",
                                                      errors=[],error_code="INTERNAL_SERVER_ERROR",
                                                      status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
            booking_payment_log['response'] = {'message': str(e)}
            create_booking_payment_log(booking_payment_log)
            return custom_response
            
            

    
    
