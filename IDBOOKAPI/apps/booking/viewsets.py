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
from IDBOOKAPI.utils import paginate_queryset, calculate_tax, order_ops
from .serializers import (BookingSerializer, AppliedCouponSerializer,
                          PreConfirmHotelBookingSerializer, ReviewSerializer,
                          BookingPaymentDetailSerializer)
from .serializers import QueryFilterBookingSerializer, QueryFilterUserBookingSerializer, BookingCheckInOutSerializer
from .models import (Booking, HotelBooking, AppliedCoupon, Review, BookingPaymentDetail, BookingMetaInfo)

from apps.booking.tasks import send_booking_email_task, create_invoice_task, send_cancelled_booking_task, send_completed_booking_task, send_booking_sms_task
from apps.booking.utils.db_utils import (
    get_user_based_booking, create_booking_payment_details,
    update_booking_payment_details, check_booking_and_transaction,
    get_booking_from_payment, check_room_booked_details, get_booking,
    create_booking_refund_details, get_refund_log_by_merchant_id,
    refund_create_booking_payment_details, check_booking_confirmation_code,
    add_or_update_booking_commission)
from apps.booking.utils.booking_utils import (
    calculate_room_booking_amount, get_tax_rate, calculate_xbed_amount,
    check_wallet_balance_for_booking, deduct_booking_amount,
    generate_booking_confirmation_code, calculate_refund_amount, refund_wallet_payment, update_no_show_status)

from apps.booking.mixins.booking_mixins import BookingMixins
from apps.booking.mixins.validation_mixins import ValidationMixins

from apps.hotels.utils.db_utils import (
    get_property_room_for_booking, # need to remove
    get_property_by_id)
from apps.hotels.utils.hotel_utils import (
    check_room_count, total_room_count,
    process_property_confirmed_booking_total,
    get_available_room)
from apps.hotels.models import Property
from apps.coupons.utils.db_utils import get_coupon_from_code
from apps.coupons.utils.coupon_utils import apply_coupon_based_discount
from apps.payment_gateways.mixins.phonepay_mixins import PhonePayMixin
from apps.log_management.utils.db_utils import create_booking_payment_log, create_booking_refund_log

from apps.authentication.models import UserOtp
from apps.authentication.utils.db_utils import get_user_from_email, create_user
from apps.authentication.utils.authentication_utils import (
    add_group_based_on_signup, add_group_for_guest_user)

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
from apps.hotels.tasks import send_hotel_sms_task
from datetime import datetime, timedelta
from pytz import timezone
from decimal import Decimal
import pytz
from apps.customer.models import Wallet
##test_param = openapi.Parameter(
##    'test', openapi.IN_QUERY, description="test manual param",
##    type=openapi.TYPE_BOOLEAN)


class BookingViewSet(viewsets.ModelViewSet, BookingMixins, ValidationMixins,
                     StandardResponseMixin, LoggingMixin, PhonePayMixin):
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
            elif key == 'confirmed_property':
                filter_dict['hotel_booking__confirmed_property'] = param_value
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
##        if user.category == 'CL-ADMIN':
##            company_id = user.company_id if user.company_id else -1
##            # user_id = self.request.query_params.get('user_id', None)
##        elif user.category == 'CL-CUST':
##            user_id = user.id
##            company_id = user.company_id if user.company_id else -1
        
        if default_group == 'B2C-GRP':
           user_id = user.id
           company_id = None
           filter_dict['company_id__isnull'] = True
        elif default_group in ('HTLR-ADMIN', 'FRANCH-ADMIN'):
            pass
        elif default_group == 'CORP-ADMIN':
            company_id = user.company_id if user.company_id else -1
        elif default_group == 'CORP-EMP':
            user_id = user.id
            company_id = user.company_id if user.company_id else -1
            
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

        # filter to get booked property based on date
        property_booked_date =  self.request.query_params.get('property_booked_date', None)
        if property_booked_date:
            property_booked_date = datetime.strptime(
                property_booked_date, '%Y-%m-%d').replace(tzinfo=timezone('UTC')).date()

            booked_date_query = Q(hotel_booking__confirmed_checkin_time__date=property_booked_date)
            booked_date_query |= Q(hotel_booking__confirmed_checkout_time__date=property_booked_date)
            self.queryset = self.queryset.filter(booked_date_query)
   
        # filter to get booked property based on date range
        start_booked_date = self.request.query_params.get('start_booked_date', None)
        end_booked_date = self.request.query_params.get('end_booked_date', None)
        if start_booked_date and end_booked_date:
            start_booked_date = datetime.strptime(
                start_booked_date, '%Y-%m-%d').replace(tzinfo=timezone('UTC')).date()
            end_booked_date = datetime.strptime(
                end_booked_date, '%Y-%m-%d').replace(tzinfo=timezone('UTC')).date()

            booked_drange_query = Q(hotel_booking__confirmed_checkin_time__date__lte=end_booked_date,
                                  hotel_booking__confirmed_checkin_time__date__gte=start_booked_date)

            booked_drange_query |= Q(hotel_booking__confirmed_checkout_time__date__lte=end_booked_date,
                                  hotel_booking__confirmed_checkout_time__date__gte=start_booked_date)
            self.queryset = self.queryset.filter(booked_drange_query) 

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

        # filter, order and pagination
        update_no_show_status(request.user.id)
        self.booking_filter_ops()
        self.queryset = order_ops(self.request, self.queryset)
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

        # filter, order and pagination
        self.booking_filter_ops()
        self.queryset = order_ops(self.request, self.queryset)
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

    # @action(detail=True, methods=['PATCH'], url_path='cancel',
    #         url_name='cancel', permission_classes=[IsAuthenticated])
    # def cancel_booking(self, request, pk=None):
    #     """customer can cancel their booking"""
    #     user = request.user
    #     print("Booking Id::", pk)
    #     instance = get_user_based_booking(user.id, pk)
    #     if instance:
    #         instance.status = 'canceled'
    #         instance.save()
    #         custom_response = self.get_response(
    #             status='success', data=None,
    #             message="Booking Cancelled Successfully",
    #             status_code=status.HTTP_200_OK,
    #             )
    #     else:
    #             custom_response = self.get_error_response(
    #                 message="Booking Not Found for the User", status="error",
    #                 errors=[],error_code="BOOKING_ID_MISSING",
    #                 status_code=status.HTTP_404_NOT_FOUND)
    #     return custom_response

    # Inside send_cancel_task method
    def send_cancel_task(self, instance, refund_amount=0):
        print("email and SMS notifications called")
        send_cancelled_booking_task.apply_async(args=[instance.id])
        send_booking_sms_task.apply_async(
            kwargs={
                'notification_type': 'HOTEL_BOOKING_CANCEL',
                'params': {
                    'booking_id': instance.id,
                    'refund_amount': float(refund_amount) if refund_amount > 0 else 0
                }
            }
        )

    # For refund notification
    def send_refund_task(self, instance, refund_amount=0):
        print("refund SMS notification called")
        send_booking_sms_task.apply_async(
            kwargs={
                'notification_type': 'HOTEL_PAYMENT_REFUND',
                'params': {
                    'booking_id': instance.id,
                    'refund_amount': float(refund_amount)
                }
            }
        )

    @action(detail=True, methods=['PATCH'], url_path='cancel',
            url_name='cancel', permission_classes=[IsAuthenticated])
    def cancel_booking(self, request, pk=None):
        user = request.user
        instance = get_user_based_booking(user.id, pk)
        refund_log = {}
        
        if not instance:
            return self.get_error_response(
                message="Booking Not Found for the User", 
                status="error",
                errors=[],
                error_code="BOOKING_ID_MISSING",
                status_code=status.HTTP_404_NOT_FOUND
            )
        
        refund_log['booking_id'] = instance.id
        print("booking id", instance.id)
        payment_details = BookingPaymentDetail.objects.filter(
                booking=instance, 
                is_transaction_success=True
            ).first()
        print("\n\n\npayment_details",payment_details)
        
        confirmed_checkin_time = instance.hotel_booking.confirmed_checkin_time
        india_tz = pytz.timezone('Asia/Kolkata')
        curr_time = datetime.now()
        print("curr_time", curr_time)

        current_time = curr_time.astimezone(india_tz)

        print("\n\n\ncurrent_time",current_time)
        hours_before_checkin = (confirmed_checkin_time - current_time).total_seconds() / 3600

        # Check if payment details exist and check-in time has passed
        if payment_details and hours_before_checkin < 0:
            return self.get_error_response(
                message="Cancellation not allowed after check-in time has passed", 
                status="error",
                errors=[],
                error_code="CANCELLATION_NOT_ALLOWED",
                status_code=status.HTTP_400_BAD_REQUEST
            )
        cancellation_policy = instance.hotel_booking.cancel_policy or {}
        print("cancellation_policy",cancellation_policy)
        hour_based_deduction = cancellation_policy.get('hour_based_deduction', [])
        print("hour_based_deduction",hour_based_deduction)
        policies = []
        for policy in hour_based_deduction:
            policies.append({
                'hours_before_checkin': policy.get('hours_before_checkin', 0),
                'refund_percentage': policy.get('refund_percentage', 0),
                'cancellation_fee': policy.get('cancellation_fee', 0)
            })

        policies.append({
            'hours_before_checkin': 0,
            'refund_percentage': 0,
            'cancellation_fee': 0
        })
        sorted_policies = sorted(policies, key=lambda x: x['hours_before_checkin'], reverse=True)

        applicable_policy = None
        for policy in sorted_policies:
            if hours_before_checkin >= policy['hours_before_checkin']:
                applicable_policy = policy
                break
        if applicable_policy is None:
            applicable_policy = {
                'hours_before_checkin': 0,
                'refund_percentage': 0,
                'cancellation_fee': 0
            }
        print("applicable_policy----",applicable_policy)
        

        total_payment_made = payment_details.amount if payment_details else 0
        
        refund_amount, cancellation_details = calculate_refund_amount(
            total_payment_made, 
            applicable_policy
        )

        refund_status = 'refund_intiated'
        if not payment_details or refund_amount <= 0:
            refund_status = 'non_refundable'

        if hours_before_checkin < 24:
            cancellation_details['canceled_time_hours_before_checkin'] = "before_24_hours"
        elif hours_before_checkin < 48:
            cancellation_details['canceled_time_hours_before_checkin'] = "more_than_24_hours"
        elif hours_before_checkin < 72:
            cancellation_details['canceled_time_hours_before_checkin'] = "more_than_48_hours"
        else:
            cancellation_details['canceled_time_hours_before_checkin'] = "more_than_72_hours"

        local_checkin = current_time.astimezone(india_tz)
        cancellation_details['cancellation_time'] = current_time.isoformat()

        if instance.hotel_booking.confirmed_checkin_time:
            local_checkin = instance.hotel_booking.confirmed_checkin_time.astimezone(india_tz)
            cancellation_details['checkin_time'] = local_checkin.isoformat()
        else:
            cancellation_details['checkin_time'] = None

        if instance.hotel_booking.confirmed_checkout_time:
            local_checkout = instance.hotel_booking.confirmed_checkout_time.astimezone(india_tz)
            cancellation_details['checkout_time'] = local_checkout.isoformat()
        else:
            cancellation_details['checkout_time'] = None

        cancellation_details['refund_status'] = refund_status
        cancellation_details['applied_policy'] = applicable_policy
        instance.hotel_booking.cancellation_details = cancellation_details
        instance.hotel_booking.save()
        instance.status = 'canceled'
        instance.save()
        instance.meta_info.booking_cancelled_date = datetime.now()
        instance.meta_info.save()
        print ("\n\n\ncancellation_details", cancellation_details)

        if payment_details and payment_details.payment_type == 'WALLET' and payment_details.payment_medium == 'Idbook':
            print("payment_details")
            send_hotel_sms_task.apply_async(
                kwargs={
                    'notification_type': 'HOTELER_BOOKING_CANCEL_NOTIFICATION',
                    'params': {
                        'booking_id': instance.id
                    }
                }
            ) 
        
        if not payment_details or refund_amount <= 0:
            self.send_cancel_task(instance, refund_amount)
            return self.get_response(
                status='success',
                message="Booking Cancelled Successfully (No Refund Possible)",
                data={
                    'cancellation_details': cancellation_details
                },
                status_code=status.HTTP_200_OK,
            )

        if payment_details and payment_details.payment_type == 'WALLET' and payment_details.payment_medium == 'Idbook':

            success, refund_status, refund_data = refund_wallet_payment(
                instance, 
                refund_amount, 
                cancellation_details
            )
            
            if success:
                self.send_cancel_task(instance, refund_amount)
                self.send_refund_task(instance, refund_amount)
                return self.get_response(
                    status='success',
                    message=f"Booking Cancelled Successfully, {refund_status}",
                    data={
                        'refund_merchant_transaction_id': refund_data['merchant_refund_id'],
                        'cancellation_details': cancellation_details
                    },
                    status_code=status.HTTP_200_OK,
                )
            else:
                return self.get_error_response(
                    message="Booking Cancelled, but Refund Failed", 
                    status="error",
                    errors=[{"detail": refund_data.get('error_message', 'Unknown error')}],
                    error_code="REFUND_FAILED",
                    status_code=status.HTTP_206_PARTIAL_CONTENT
                )
        else:
            merchant_id = settings.MERCHANT_ID
            callback_url = settings.CALLBACK_URL + "/api/v1/booking/bookings/phone-pay/refundcallbackurl/"
            print("\n\n\ncallback_url",callback_url)
            

            append_id = "RF{}".format(instance.user.id)

            refund_log_obj = create_booking_refund_details(
                instance.id, 
                payment_details.merchant_transaction_id, 
                append_id
            )
            merchant_refund_id = refund_log_obj.merchant_refund_id
            
            refund_log['merchant_refund_id'] = merchant_refund_id
            refund_log['original_transaction_id'] = payment_details.merchant_transaction_id
            refund_log['refund_amount'] = refund_amount
            payload = {
                "merchantId": merchant_id,
                "merchantUserId": str(instance.user.id),
                "originalTransactionId": payment_details.merchant_transaction_id,
                "merchantTransactionId": merchant_refund_id,
                "amount": int(refund_amount * Decimal(100)),
                # "callbackUrl": "https://webhook-test.com/3755aad896192a6b2e0675e81761806d"
                "callbackUrl": callback_url
            }

            
            refund_log['request'] = payload
            
            # req, auth_header = self.get_encrypted_header_and_payload_refund(payload)
            req, auth_header = self.get_encrypted_header_and_payload(payload, req_trigger=True)
            response = self.post_refund_request(req, auth_header)
            if response.status_code == 200:
                response_data = response.json()
                refund_log['response'] = response_data
                
                # Extract data from response
                if 'data' in response_data:
                    data = response_data.get('data', {})
                    refund_log['transaction_id'] = data.get('transactionId', '')
                    refund_log['response_code'] = data.get('responseCode', '')
                    refund_log['transaction_details'] = data
                
                refund_log['response_message'] = response_data.get('message', '')
                refund_status = ''
                if response_data.get('code') == "PAYMENT_PENDING":
                    refund_log['status'] = 'pending'
                    refund_status = 'refund_in_progress'
                    self.send_refund_task(instance, refund_amount)
                elif response_data.get('code') == "PAYMENT_SUCCESS":
                    refund_log['status'] = 'completed'
                    refund_status = 'refund_completed'
                    self.send_refund_task(instance, refund_amount)
                else:
                    refund_log['status'] = 'failed'
                    refund_status = 'refund_failed'
                    refund_log['error_message'] = response_data.get('message', '')

                cancellation_details['refund_status'] = refund_status
                instance.hotel_booking.cancellation_details = cancellation_details
                instance.hotel_booking.save()
                
                # Create the refund log entry
                create_booking_refund_log(refund_log)
                self.send_cancel_task(instance, refund_amount)
                send_hotel_sms_task.apply_async(
                    kwargs={
                        'notification_type': 'HOTELER_BOOKING_CANCEL_NOTIFICATION',
                        'params': {
                            'booking_id': instance.id
                        }
                    }
                )
                
                custom_response = self.get_response(
                    status='success',
                    message=f"Booking Cancelled Successfully, {refund_status}",
                    data={
                        'refund_merchant_transaction_id': merchant_refund_id,
                        'booking_merchant_transaction_id': payment_details.merchant_transaction_id,
                        'booking_transaction_id_from_phonepay': payment_details.transaction_id,
                        'cancellation_details': cancellation_details
                    },
                    # data={'cancellation_details': cancellation_details},
                    status_code=status.HTTP_200_OK,
                )
            else:
                refund_log['status'] = 'failed'
                refund_log['error_message'] = response.text
                refund_log['response'] = {'error': response.text}
                
                create_booking_refund_log(refund_log)
                
                custom_response = self.get_error_response(
                    message="Booking Cancelled, but Refund Failed", 
                    status="error",
                    errors=[{"detail": response.text}],
                    error_code="REFUND_FAILED",
                    status_code=status.HTTP_206_PARTIAL_CONTENT
                )
            print("\n\n\n\n custom response final", custom_response)
            return custom_response

    @action(detail=False, methods=['POST'], url_path='phone-pay/refundcallbackurl',
            url_name='phone-pay-refund-callbackurl', permission_classes=[])
    def phone_pay_refund_callbackurl(self, request):
        try:
            self.log_request(request)
            refund_log = {}
            x_verify = request.META.get('HTTP_X_VERIFY', None)
            refund_log['x_verify'] = x_verify
            response = request.data.get('response', None)
            if not response:
                custom_response = self.get_error_response(
                    message="Error in Response", status="error",
                    errors=[], error_code="VALIDATION_ERROR",
                    status_code=status.HTTP_400_BAD_REQUEST)
                refund_log['request'] = {"message": "empty request"}
                create_booking_refund_log(refund_log)
                return custom_response

            refund_log['request'] = {"response": response}
            data = base64.b64decode(response)
            decoded_data = data.decode('utf-8')
            json_data = json.loads(decoded_data)
            refund_log['request'] = json_data

            code = json_data.get('code', '')
            message = json_data.get('message', '')

            sub_json_data = json_data.get('data', {})
            amount = sub_json_data.get('amount', 0) / 100
            merchant_transaction_id = sub_json_data.get('merchantTransactionId', '')
            refund_log['merchant_refund_id'] = merchant_transaction_id
            transaction_id = sub_json_data.get('transactionId', '')
            state = sub_json_data.get('state', '')
            response_code = sub_json_data.get('responseCode', '')


            refund_log_obj = get_refund_log_by_merchant_id(merchant_transaction_id)
            
            if refund_log_obj:
                refund_log['booking_id'] = refund_log_obj.booking_id if refund_log_obj.booking else None
                
                # Update the refund log with callback data
                refund_log_obj.transaction_id = transaction_id
                refund_log_obj.response_code = response_code
                refund_log_obj.response_message = message
                refund_log_obj.transaction_details = sub_json_data
                refund_log_obj.response = json_data
                
                # Update status based on code and state
                if code == "PAYMENT_SUCCESS" and state == "COMPLETED":
                    refund_log_obj.status = 'completed'
                elif code == "PAYMENT_PENDING":
                    refund_log_obj.status = 'pending'
                else:
                    refund_log_obj.status = 'failed'
                    refund_log_obj.error_message = message
                refund_log_obj.save()

            hotel_booking = refund_log_obj.booking.hotel_booking if refund_log_obj and refund_log_obj.booking else None
            cancellation_details = hotel_booking.cancellation_details if hotel_booking else {}

            # Construct booking_payment_details dictionary
            booking_payment_details = {
                "transaction_id": transaction_id,
                "code": code,
                "message": message,
                "payment_type": "PAYMENT GATEWAY",
                "payment_medium": "PHONE PAY",
                "transaction_for": "booking_refund",
                "amount": amount,
                "transaction_details": sub_json_data,
                "is_transaction_success": code == "PAYMENT_SUCCESS" and state == "COMPLETED"
            }
            # Update the BookingPaymentDetail instance
            refund_create_booking_payment_details(merchant_transaction_id, booking_payment_details)

            # Log the refund details
            refund_log['status'] = 'completed' if booking_payment_details["is_transaction_success"] else 'failed'
            refund_log['response'] = json_data
            refund_log['transaction_id'] = transaction_id
            create_booking_refund_log(refund_log)

            custom_response = self.get_response(
                status="success",
                data={
                    "booking_payment_details": booking_payment_details,
                    "cancellation_details": cancellation_details
                },
                message="Refund processed successfully",
                status_code=status.HTTP_200_OK,
            )

            return custom_response

        except Exception as e:
            refund_log['error_message'] = str(e)
            refund_log['status'] = 'failed'
            refund_log['response'] = {'error': str(e)}
            create_booking_refund_log(refund_log)

            custom_response = self.get_error_response(
                message=str(e), status="error",
                errors=[], error_code="INTERNAL_SERVER_ERROR",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
            return custom_response

    @swagger_auto_schema(
        request_body=BookingCheckInOutSerializer,
        operation_description="Update check-in/check-out status of a booking",
        responses={200: BookingSerializer}
    )
    @action(detail=True, methods=['PATCH'], permission_classes=[IsAuthenticated],
            url_path='update-checkinout', url_name='update-checkinout')
    def update_checkin_checkout(self, request, pk=None):
        self.log_request(request)  # Log the incoming request
        
        try:
            booking = self.get_object()
            print("booking_id", booking.id)
            
            serializer = BookingCheckInOutSerializer(booking, data=request.data, partial=True)
            if not serializer.is_valid():
                error_list = self.custom_serializer_error(serializer.errors)
                custom_response = self.get_error_response(
                    message="Validation Error", status="error",
                    errors=error_list, error_code="VALIDATION_ERROR", 
                    status_code=status.HTTP_400_BAD_REQUEST
                )
                self.log_response(custom_response)
                return custom_response
            
            serializer.save()
            
            booking.refresh_from_db()
            
            if booking.is_checkin and booking.is_checkout:
                booking.status = 'completed'
                booking.meta_info.booking_completed_date = datetime.now()
                booking.meta_info.save()
                booking.save()
                
                print("Triggering send_completed_booking_task for booking_id:", booking.id)
                send_completed_booking_task.apply_async(args=[booking.id])
                print(f"Completed booking task queued")
            
            updated_booking = BookingSerializer(booking).data
            custom_response = self.get_response(
                status="success",
                data=updated_booking,
                message="Check-in/Check-out status updated successfully",
                status_code=status.HTTP_200_OK
            )
            
            self.log_response(custom_response)
            return custom_response
            
        except Exception as e:
            custom_response = self.get_error_response(
                message=f"Error updating check-in/check-out status: {str(e)}", 
                status="error",
                errors=[str(e)],
                error_code="UPDATE_ERROR", 
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
            self.log_response(custom_response)
            return custom_response

##    def validate_pre_confirm_booking(self):
##
##        child_count = self.request.data.get('child_count', 0)
##        child_age_list = self.request.data.get('child_age_list', [])
##
##        if not isinstance(child_age_list, list):
##            error_info = {"message": "invalid child age list format",
##                          "error_code":"CHILD_AGE_ERROR"}
##            return False, error_info
##
##
##        if child_count != len(child_age_list):
##            error_info = {"message": "Mismatch between child count and age list",
##                          "error_code":"MISMATCH_CHILD_COUNT_AGE"}
##            return False, error_info
##
##        confirmed_checkin_time = self.request.data.get('confirmed_checkin_time', None)
##        confirmed_checkout_time = self.request.data.get('confirmed_checkout_time', None)
##
##        if not confirmed_checkin_time or not confirmed_checkout_time:
##            error_info = {"message": "check in and check out missing",
##                          "error_code":"DATE_MISSING"}
##            return False, error_info
##
##        property_id = self.request.data.get('property', None)
##        if not property_id:
##            error_info = {"message": "Property missing",
##                          "error_code":"PROPERTY_MISSING"}
##            return False, error_info
##
##        room_list = self.request.data.get('room_list', [])
##        if not room_list or not isinstance(room_list, list):
##            error_info = {"message": "Missing Room list or invalid list format",
##                          "error_code":"ROOM_MISSING"}
##            return False, error_info
##
##        self.no_of_days = get_days_from_string(
##            confirmed_checkin_time, confirmed_checkout_time,
##            string_format="%Y-%m-%dT%H:%M%z")
##
##        if self.no_of_days is None:
##            error_info = {"message": "Error in date conversion",
##                          "error_code":"DATE_ERROR"}
##            return False, error_info
##
##        self.tax_rules_dict = get_booking_based_tax_rule('HOTEL')
##        if not self.tax_rules_dict:
##            error_info = {"message": "Tax Rule Missing",
##                          "error_code":"TAX_RULE_MISSING"}
##            return False, error_info
##
##        success_info = {"message":"Success"}
##        return True, success_info
##            
        


    @action(detail=False, methods=['POST'], url_path='hotel/booking-caclulation',
            url_name='hotel-booking-calculation', permission_classes=[])
    def hotel_booking_calculation(self, request):

        # validation
        is_valid, info = self.validate_pre_confirm_booking()
        if not is_valid:
            message = info.get("message","")
            error_code = info.get("error_code", "")
            
            custom_response = self.get_error_response(
                message=message, status="error",
                errors=[],error_code=error_code,
                status_code=status.HTTP_400_BAD_REQUEST)

            return custom_response

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
        booking_id = request.data.get('booking_id', 0)
        additional_notes = request.data.get('additional_notes', '')
        booking_status = request.data.get('status', '')
        
        
        coupon_code = request.data.get('coupon_code', None)
        coupon = None

        confirmed_checkin_time = request.data.get('confirmed_checkin_time', None)
        confirmed_checkout_time = request.data.get('confirmed_checkout_time', None)

        property_obj = get_property_by_id(property_id)
        if not property_obj:
            custom_response = self.get_error_response(
                message="Invalid property", status="error",
                errors=[],error_code="PROPERTY_MISSING",
                status_code=status.HTTP_400_BAD_REQUEST)
            return custom_response

##        min_nights = property_obj.minimum_no_of_nights
##        max_nights = property_obj.maximum_no_of_nights
##
##        if min_nights > no_days or no_days > max_nights:
##            custom_response = self.get_error_response(
##                message="Minimum or Maximum night constraint failed", status="error",
##                errors=[],error_code="MIN_MAX_NIGHT_ERROR",
##                status_code=status.HTTP_400_BAD_REQUEST)
##            return custom_response
            
            
        # no_of_days = self.no_of_days
        if self.no_of_days == 0:
            self.no_of_days = 1

        try:
            if coupon_code:
                coupon = get_coupon_from_code(coupon_code)
                if not coupon:
                    custom_response = self.get_error_response(
                        message="Invalid coupon", status="error",
                        errors=[],error_code="COUPON_ERROR",
                        status_code=status.HTTP_400_BAD_REQUEST)
                    return custom_response

            self.adult_count = adult_count
            self.child_count = child_count
            self.child_age_list = child_age_list

            self.room_list = room_list
            self.property_id = property_id
            self.booking_slot = booking_slot

            # get dynamic pricing if applicable
            self.room_dprice_dict, self.date_list, self.dprice_roomids = self.get_dynamic_pricing_applicable_room(
                self.checkin_datetime.date(), self.checkout_datetime.date())

            is_status, custom_response = self.room_allocation()
            if not is_status:
                return custom_response

            self.confirmed_room_details = []
            self.final_amount, self.final_tax_amount, self.subtotal = 0, 0, 0

            is_cal_status, custom_response = self.amount_calculation()
            if not is_cal_status:
                return custom_response

            if coupon:
                coupon_discount_type = coupon.discount_type
                coupon_discount = coupon.discount
                discount, subtotal_after_discount = apply_coupon_based_discount(
                    coupon_discount, coupon_discount_type, self.subtotal)

                self.final_amount = float(subtotal_after_discount) + self.final_tax_amount
            else:
                discount = 0
                self.final_amount = self.subtotal + self.final_tax_amount

            hotel_booking_dict = {
                "confirmed_property_id":property_id, "confirmed_room_details":self.confirmed_room_details,
                "confirmed_checkin_time":confirmed_checkin_time,
                "confirmed_checkout_time":confirmed_checkout_time,
                "booking_slot":booking_slot, "requested_room_no":requested_room_no
            }

##            com_amnt, com_tax_amount, com_tax_in_percent = self.commission_calculation()
##            com_amnt_withtax = com_amnt + com_tax_amount
##            commission_details = {"com_amount":com_amnt, "tax_amount":com_tax_amount,
##                                  "tax_percent":com_tax_in_percent,
##                                  "total_com_amnt":com_amnt_withtax}
##            self.final_amount = self.final_amount + float(com_amnt_withtax)

            commission_details = self.commission_calculation()
            if commission_details:
                self.final_amount = self.final_amount + float(
                    commission_details.get('com_amnt_withtax', 0))
                hotelier_amount = self.final_amount - float(commission_details.get('com_amnt_withtax', 0))
                commission_details['hotelier_amount'] = hotelier_amount

            booking_dict = {"user_id":user.id, "hotel_booking":hotel_booking_dict, "booking_type":'HOTEL',
                            "subtotal":str(self.subtotal), "discount":str(discount),
                            "final_amount":str(self.final_amount),
                            "gst_amount": str(self.final_tax_amount), "adult_count":adult_count,
                            "child_count":child_count, "infant_count":infant_count,
                            "child_age_list":child_age_list, "additional_notes":additional_notes,
                            "commission_info":commission_details}
            
            if coupon:

                booking_dict['coupon_code'] = coupon_code
            else:
                booking_dict['coupon_code'] = ''
                

            # provide the available room list for the property
            room_availability_list = get_available_room(
                confirmed_checkin_time, confirmed_checkout_time, property_id)

            booking_dict['room_availability_details']=room_availability_list
            
            custom_response = self.get_response(
                status='success', count=1, data=booking_dict,
                message="Booking Calculation Details", status_code=status.HTTP_200_OK,)

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

        
        
        
    @action(detail=False, methods=['POST'], url_path='hotel/pre-confirm',
            url_name='hotel-pre-confirm', permission_classes=[])
    def hotel_pre_confirm_booking(self, request):
        self.log_request(request)

        # validation
        is_valid, info = self.validate_pre_confirm_booking()
        if not is_valid:
            message = info.get("message","")
            error_code = info.get("error_code", "")
            
            custom_response = self.get_error_response(
                message=message, status="error",
                errors=[],error_code=error_code,
                status_code=status.HTTP_400_BAD_REQUEST)

            return custom_response
            

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
        booking_id = request.data.get('booking_id', 0)
        additional_notes = request.data.get('additional_notes', '')
        booking_status = request.data.get('status', '')
        
        
        coupon_code = request.data.get('coupon_code', None)
        coupon = None
        
##        confirmed_room_details = []
##        
##        final_amount, final_tax_amount, subtotal = 0, 0, 0

        
        confirmed_checkin_time = request.data.get('confirmed_checkin_time', None)
        confirmed_checkout_time = request.data.get('confirmed_checkout_time', None)

        property_obj = get_property_by_id(property_id)
        if not property_obj:
            custom_response = self.get_error_response(
                message="Invalid property", status="error",
                errors=[],error_code="PROPERTY_MISSING",
                status_code=status.HTTP_400_BAD_REQUEST)
            return custom_response

##        min_nights = property_obj.minimum_no_of_nights
##        max_nights = property_obj.maximum_no_of_nights
##
##        if min_nights > no_days or no_days > max_nights:
##            custom_response = self.get_error_response(
##                message="Minimum or Maximum night constraint failed", status="error",
##                errors=[],error_code="MIN_MAX_NIGHT_ERROR",
##                status_code=status.HTTP_400_BAD_REQUEST)
##            return custom_response

        # no_of_days = self.no_of_days
        if self.no_of_days == 0:
            self.no_of_days = 1

        # tax_rules_dict = self.tax_rules_dict 

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

            self.adult_count = adult_count
            self.child_count = child_count
            self.child_age_list = child_age_list

            self.room_list = room_list
            self.property_id = property_id
            self.booking_slot = booking_slot

            # get dynamic pricing if applicable
            self.room_dprice_dict, self.date_list, self.dprice_roomids = self.get_dynamic_pricing_applicable_room(
                self.checkin_datetime.date(), self.checkout_datetime.date())

            # print("room dynamic price dict::", room_dprice_dict)


##            custom_response = self.get_error_response(
##                message="", status="error",
##                errors=[],error_code="TYU_RT",
##                status_code=status.HTTP_400_BAD_REQUEST)
##
##            return custom_response
##            
            is_status, custom_response = self.room_allocation()
            if not is_status:
                return custom_response

            self.confirmed_room_details = []
            self.final_amount, self.final_tax_amount, self.subtotal = 0, 0, 0

            is_cal_status, custom_response = self.amount_calculation()
            if not is_cal_status:
                return custom_response


##            room_detail_dict = {}
##            room_occupancy_dict = {}
##            allotted_person = 0
##            need_to_allot = adult_count
##            child_need_to_allot = child_count
##            child_age_need_to_allot = child_age_list
            

##            for room in room_list:
##                child_allotted_list = []
##                room_id = room.get('room_id', None)
##                no_of_rooms = room.get('no_of_rooms', None)
##                # room_id_list.append(room_id)
##
##                room_detail = get_property_room_for_booking(property_id, room_id)
##                if not room_detail:
##                    custom_response = self.get_error_response(
##                        message=f"The room: {room_id} is missing for the property", status="error",
##                        errors=[],error_code="ROOM_MISSING",
##                        status_code=status.HTTP_400_BAD_REQUEST)
##                    return custom_response
##
##                room_detail_dict[room_id] = room_detail
##
##                child_bed_price = room_detail.get('room_price', {}).get('child_bed_price', {})
##
##                
##                room_occupancy = room_detail.get('room_occupancy', {})
##                base_adults = room_occupancy.get('base_adults', None)
##                max_occupancy = room_occupancy.get('max_occupancy', None)
##
##                is_extra_bed_available = room_detail.get('is_extra_bed_available', False)
##
##                if not no_of_rooms:
##                    custom_response = self.get_error_response(
##                        message=f"The no of rooms for {room_id} is missing", status="error",
##                        errors=[],error_code="NO_ROOM_MISSING",
##                        status_code=status.HTTP_400_BAD_REQUEST)
##                    return custom_response
##
##                
##                total_base_adults =  base_adults * no_of_rooms
##                total_max_occupancy = max_occupancy * no_of_rooms
##
##                if need_to_allot <= total_base_adults:
##                    allotted_person = need_to_allot
##                    need_to_allot = 0
##                elif need_to_allot > total_base_adults:
##                    allotted_person = total_base_adults
##                    need_to_allot = need_to_allot - allotted_person 
##                    
##                extra_persons_allowed = total_max_occupancy - allotted_person
##                len_child_to_allot = len(child_age_need_to_allot)
##                print("child age need to allot::", child_age_need_to_allot)
##                print("extra_persons_allowed::", extra_persons_allowed)
##                
##
##                if  len_child_to_allot and extra_persons_allowed:
##                    remove_alloted_list = []
##                    for age in child_age_need_to_allot:
##                        print("age::", age, "extra_persons_allowed::", extra_persons_allowed)
##                        if not extra_persons_allowed:
##                            break
##                        else:
##                            allotted_status = False
##                            for price_details in child_bed_price:
##                                age_list = price_details.get('age_limit', [])
##                                
##                                if age_list[0] <= age <= age_list[1]:
##                                    print("age:", age, "age0:", age_list[0], "age1:", age_list[1])
##                                    if booking_slot == '12 Hrs':
##                                        age_price = price_details.get('child_bed_price_12hrs', 0)
##                                    elif booking_slot == '8 Hrs':
##                                        age_price = price_details.get('child_bed_price_8hrs', 0)
##                                    elif booking_slot == '4 Hrs':
##                                        age_price = price_details.get('child_bed_price_4hrs', 0)
##                                    else:
##                                        age_price = price_details.get('child_bed_price', 0)
##
##                                    child_allotted = {'age': age, 'price':age_price}
##                                    child_allotted_list.append(child_allotted)
##                                    extra_persons_allowed = extra_persons_allowed - 1
##                                    remove_alloted_list.append(age)
##                                    allotted_status = True
##                                    break
##
##                            # if age not withing the price range then provide adult extra bed price
##                            if not allotted_status:
##                                if booking_slot == '12 Hrs':
##                                    age_price =  room_detail.get('room_price', {}).get('extra_bed_price_12hrs', 0)
##                                elif booking_slot == '8 Hrs':
##                                    age_price =  room_detail.get('room_price', {}).get('extra_bed_price_8hrs', 0)
##                                elif booking_slot == '4 Hrs':
##                                    age_price =  room_detail.get('room_price', {}).get('extra_bed_price_4hrs', 0)
##                                else:
##                                    age_price = room_detail.get('room_price', {}).get('extra_bed_price', 0)
##                                    
##                                child_allotted = {'age': age, 'price':age_price}
##                                child_allotted_list.append(child_allotted)
##                                extra_persons_allowed = extra_persons_allowed - 1
##                                remove_alloted_list.append(age)
##                                    
##                    # remove alloted list
##                    print("child age need to allot", child_age_need_to_allot)
##                    print("remove_alloted_list", remove_alloted_list)
##                    #child_age_need_to_allot = [x for x in child_age_need_to_allot if x not in remove_alloted_list]
##                    for pop_age in remove_alloted_list:
##                        child_age_need_to_allot.remove(pop_age)
##    
##                room_occupancy_dict[room_id] = {'total_base_adults':total_base_adults,
##                                                'total_max_occupancy': total_max_occupancy,
##                                                'allotted_person': allotted_person,
##                                                'is_extra_bed_available':is_extra_bed_available,
##                                                'extra_persons_allowed':extra_persons_allowed,
##                                                'extra_adults_allotted':0,
##                                                'child_allotted': child_allotted_list
##                                                }  
##                
##            if need_to_allot:
##                for room_occupancy_key in room_occupancy_dict:
##                    room_occupancy_details = room_occupancy_dict.get(room_occupancy_key)
##                    extra_persons_allowed = room_occupancy_details.get('extra_persons_allowed', 0)
##
##                    if need_to_allot <= extra_persons_allowed:
##                        room_occupancy_details['extra_adults_allotted'] = need_to_allot
##                        need_to_allot = 0
##                    elif need_to_allot > extra_persons_allowed:
##                        need_to_allot = need_to_allot - extra_persons_allowed
##                        room_occupancy_details['extra_adults_allotted'] = extra_persons_allowed
##
##            print(room_occupancy_dict)
##
##            if need_to_allot or child_age_need_to_allot:
##                custom_response = self.get_error_response(
##                    message=f"The no of guests is more for selected room(s)", status="error",
##                    errors=[],error_code="INADEQUATE_ROOM",
##                    status_code=status.HTTP_400_BAD_REQUEST)
##                return custom_response
                
            
##            for room in room_list:
##                room_id = room.get('room_id', None)
##                no_of_rooms = room.get('no_of_rooms', None)
##                base_price = 0
##
##                room_detail = room_detail_dict.get(room_id)
##
##                # get room details
##                room_type = room_detail.get('room_type')
##                room_price = room_detail.get('room_price')
##                if not room_price:
##                    custom_response = self.get_error_response(
##                        message=f"The room price details for {room_id} is missing", status="error",
##                        errors=[],error_code="ROOM_PRICE_MISSING",
##                        status_code=status.HTTP_400_BAD_REQUEST)
##                    return custom_response
##
##                # get 24 hours price
##                base_price = room_price.get('base_rate', None)
##                if not base_price:
##                    custom_response = self.get_error_response(
##                        message=f"The room price details for room id {room_id} is missing", status="error",
##                        errors=[],error_code="ROOM_PRICE_MISSING",
##                        status_code=status.HTTP_400_BAD_REQUEST)
##                    return custom_response
##
##                if booking_slot == '12 Hrs':
##                    slot_price = room_price.get('price_12hrs', None)
##                    extra_bed_price = room_price.get('extra_bed_price_12hrs', 0)
##                    booking_room_price = slot_price
##                elif booking_slot == '8 Hrs':
##                    slot_price = room_price.get('price_8hrs', None)
##                    extra_bed_price = room_price.get('extra_bed_price_8hrs', 0)
##                    booking_room_price = slot_price
##                elif booking_slot == '4 Hrs':
##                    slot_price = room_price.get('price_4hrs', None)
##                    extra_bed_price = room_price.get('extra_bed_price_4hrs', 0)
##                    booking_room_price = slot_price
##                else:
##                    slot_price = None
##                    extra_bed_price = room_price.get('extra_bed_price', 0)
##                    booking_room_price = base_price
##                    
##                if not slot_price and not booking_slot == '24 Hrs':
##                    custom_response = self.get_error_response(
##                        message=f"The {booking_slot} hrs room price for room id {room_id} is missing", status="error",
##                        errors=[],error_code="ROOM_PRICE_MISSING",
##                        status_code=status.HTTP_400_BAD_REQUEST)
##                    return custom_response
##                        
##                print("extra bed price::", extra_bed_price)    
##                # get tax percent based on amount
##                tax_in_percent = get_tax_rate(base_price, tax_rules_dict)
##                if not tax_in_percent:
##                    custom_response = self.get_error_response(
##                        message=f"The room price details for room id {room_id} is missing", status="error",
##                        errors=[],error_code="ROOM_PRICE_MISSING",
##                        status_code=status.HTTP_400_BAD_REQUEST)
##                    return custom_response
##
##                # tax percentage based on base price
##                tax_in_percent = float(tax_in_percent)
##
##                # for extra bed calculation
##                occup_details = room_occupancy_dict.get(room_id)
##                extra_adults_allotted = occup_details.get('extra_adults_allotted', 0)
##                child_allotted = occup_details.get('child_allotted', [])
##
##                if extra_adults_allotted:
##                    total_extra_bed_price = extra_bed_price * extra_adults_allotted
##
##                
##                # tax calculation based on booked 
##                if booking_slot == '24 Hrs':
##                    tax_amount = calculate_tax(tax_in_percent, base_price)
##                    
##                else:
##                    tax_amount = calculate_tax(tax_in_percent, slot_price)
##
##                # calculate total tax amount
##                total_tax_amount =   calculate_room_booking_amount(
##                    tax_amount, no_of_days, no_of_rooms)
##
##                # calculate tax amount for extra person
##                if extra_adults_allotted:
##                    tax_amount_xbed = calculate_tax(tax_in_percent, total_extra_bed_price)
##                    total_tax_amount_xbed = calculate_xbed_amount(tax_amount_xbed, no_of_days)
##
##                    # total tax amount including extra bed
##                    total_tax_amount = total_tax_amount + total_tax_amount_xbed
##
##                total_child_price = 0
##                if child_allotted:
##                    for child_price in child_allotted:
##                        total_child_price = total_child_price + child_price.get('price', 0)
##                # calculate tax amount for children
##                if total_child_price:
##                    tax_amount_child = calculate_tax(tax_in_percent, total_child_price)
##                    total_tax_amount_child = calculate_xbed_amount(tax_amount_child, no_of_days)
##
##                    # total tax amount including extra bed
##                    total_tax_amount = total_tax_amount + total_tax_amount_child
##                    
##                    
##                
##                # calculate total room amount
##                if booking_slot == '24 Hrs':
##                    total_room_amount = calculate_room_booking_amount(
##                        base_price, no_of_days, no_of_rooms)
##                else:
##                    total_room_amount = calculate_room_booking_amount(
##                        slot_price, no_of_days, no_of_rooms)
##
##                # calculate extra bed amount
##                if extra_adults_allotted:
##                    total_room_amount_xbed = calculate_xbed_amount(total_extra_bed_price, no_of_days)
##                    total_room_amount = total_room_amount + total_room_amount_xbed
##
##                # calculate children price
##                if total_child_price:
##                    total_child_amount = calculate_xbed_amount(total_child_price, no_of_days)
##                    total_room_amount = total_room_amount + total_child_amount
##                
##                
##                final_room_total = total_room_amount + total_tax_amount
##
##                
##                confirmed_room = {"room_id": room_id, "room_type":room_type, "base_price":base_price,
##                                  "price": booking_room_price,
##                                  "no_of_rooms": no_of_rooms,
##                                  "tax_in_percent": tax_in_percent, "tax_amount": tax_amount,
##                                  "total_tax_amount": total_tax_amount,
##                                  "no_of_days": no_of_days, "total_room_amount":total_room_amount,
##                                  "final_room_total": final_room_total, "booking_slot":booking_slot,
##                                  "extra_adults_allotted":extra_adults_allotted, "extra_bed_price":extra_bed_price,
##                                  "child_allotted":child_allotted
##                                  }
##                
##                confirmed_room_details.append(confirmed_room)
##                # final amount
##                # final_amount = final_amount + final_room_total
##                final_tax_amount = final_tax_amount + total_tax_amount
##                subtotal = subtotal + total_room_amount # total room amount without tax and services
        

            with transaction.atomic():

                # apply coupon discount
                if coupon:
                    coupon_discount_type = coupon.discount_type
                    coupon_discount = coupon.discount
                    discount, subtotal_after_discount = apply_coupon_based_discount(
                        coupon_discount, coupon_discount_type, self.subtotal)

                    self.final_amount = float(subtotal_after_discount) + self.final_tax_amount
                else:
                    discount = 0
                    self.final_amount = self.subtotal + self.final_tax_amount

##                tm ='Asia/Kolkata'
##                local_dt = timezone.localtime(item.created_at, pytz.timezone(tm))

    
##                hotel_booking = HotelBooking(
##                    confirmed_property_id=property_id, confirmed_room_details=confirmed_room_details,
##                    confirmed_checkin_time=confirmed_checkin_time,
##                    confirmed_checkout_time=confirmed_checkout_time,
##                    booking_slot=booking_slot, requested_room_no=requested_room_no)
##                hotel_booking.save()

##                booking = Booking(user_id=user.id, hotel_booking=hotel_booking, booking_type='HOTEL',
##                                  subtotal=subtotal, discount=discount, final_amount=final_amount,
##                                  gst_amount=final_tax_amount, adult_count=adult_count,
##                                  child_count=child_count, infant_count=infant_count,
##                                  child_age_list=child_age_list)

                if booking_id:
                    booking_objs = Booking.objects.filter(id=booking_id)
                    hotel_booking_id = booking_objs.first().hotel_booking_id
                    hotel_booking_objs = HotelBooking.objects.filter(id=hotel_booking_id)

                property_obj = Property.objects.get(id=property_id)  
                property_policies = None  

                if property_obj.policies and isinstance(property_obj.policies, dict):  
                    property_policies = property_obj.policies.get("cancellation_policy", None)

                hotel_booking_dict = {
                    "confirmed_property_id":property_id, "confirmed_room_details":self.confirmed_room_details,
                    "confirmed_checkin_time":confirmed_checkin_time,
                    "confirmed_checkout_time":confirmed_checkout_time,
                    "booking_slot":booking_slot, "requested_room_no":requested_room_no, "cancel_policy": property_policies
                }
                
                # save hotel booking details
                if booking_id:
                    hotel_booking_objs.update(**hotel_booking_dict)
                else:
                    hotel_booking = HotelBooking(**hotel_booking_dict)
                    hotel_booking.save()
                    hotel_booking_id = hotel_booking.id

                commission_details = self.commission_calculation()
                if commission_details:
                    self.final_amount = self.final_amount + float(commission_details.get('com_amnt_withtax', 0))
                    hotelier_amount = self.final_amount - float(commission_details.get('com_amnt_withtax', 0))
                    commission_details['hotelier_amount'] = hotelier_amount

                booking_dict = {"user_id":user.id, "hotel_booking_id":hotel_booking_id, "booking_type":'HOTEL',
                                "subtotal":self.subtotal, "discount":discount, "final_amount":self.final_amount,
                                "gst_amount": self.final_tax_amount, "adult_count":adult_count,
                                "child_count":child_count, "infant_count":infant_count,
                                "child_age_list":child_age_list, "additional_notes":additional_notes}
                if coupon:
                    booking_dict['coupon_code'] = coupon_code
                    #booking.coupon_code = coupon_code
                    
                if company_id:
                    booking_dict['company_id'] = company_id
                    # booking.company_id = company_id

                if not booking_id:
                    booking = Booking(**booking_dict)
                    booking.save()
                else:
                    booking_objs.update(**booking_dict)
                    booking = booking_objs.first()

                if commission_details:
                    add_or_update_booking_commission(booking.id, commission_details)

                if not booking_id:
                    BookingMetaInfo.objects.create(booking=booking, booking_created_date=datetime.now())
                booking_status_message = ""
                if booking_id and booking_status == "on_hold":
                    # check the room availability before locking
                    room_confirmed_dict = total_room_count(self.confirmed_room_details)
                    booked_rooms = check_room_booked_details(
                        confirmed_checkin_time, confirmed_checkout_time,
                        property_id, is_slot_price_enabled=True, booking_id=booking.id)
                    room_rejected_list = check_room_count(booked_rooms, room_confirmed_dict)

                    if not room_rejected_list:
                        on_hold_end_time = datetime.now(timezone('UTC')) + timedelta(minutes=5)
                        booking.status = 'on_hold'
                        booking.on_hold_end_time = on_hold_end_time
                        booking.save()
                        booking_status_message = "Status Changed to on_hold"
                    else:
                        booking_status_message = "Failed to change status to on_hold"

                # create and save merchant transaction id for payment reference
##                append_id = "%s" % (user.id)
##                booking_payment_detail = create_booking_payment_details(booking.id, append_id)
##                merchant_transaction_id = booking_payment_detail.merchant_transaction_id

                # wallet balance check and send notification for low balance
                if user.id:
                    check_wallet_balance_for_booking(booking, user, company_id=company_id)
   
                serializer = PreConfirmHotelBookingSerializer(booking)

                # provide the available room list for the property
                room_availability_list = get_available_room(
                    confirmed_checkin_time, confirmed_checkout_time, property_id)
                
                booking_dict = {'merchant_transaction_id': '',
                                'room_availability_details':room_availability_list,
                                'booking_status_message': booking_status_message}
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

        self.final_amount = subtotal_after_discount + tax_amount

        # save the deduction details based on discount
        instance.final_amount = self.final_amount
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
        if deduct_status:
            wallet_balance = 0
            wallet = Wallet.objects.filter(user__id=instance.user.id, company_id__isnull=True).first()
            if wallet:
                wallet_balance = wallet.balance
            try:
                send_booking_sms_task.apply_async(
                    kwargs={
                        'notification_type': 'WALLET_DEDUCTION_CONFIRMATION',
                        'params': {
                            'user_id': instance.user.id,
                            'deduct_amount': float(instance.final_amount),
                            'wallet_balance': float(wallet_balance)
                        }
                    }
                )
                send_hotel_sms_task.apply_async(
                    kwargs={
                        'notification_type': 'HOTELER_PAYMENT_NOTIFICATION',
                        'params': {
                            'booking_id': instance.id
                        }
                    }
                )
                print(f"Wallet deduction SMS scheduled for user {instance.user.id}")
            except Exception as sms_error:
                print(f"Error scheduling wallet deduction SMS: {sms_error}")
        if not deduct_status:
            booking_payment_detail.code = "PAYMENT_ERROR"
            booking_payment_detail.message = "Insufficient fund in wallet balance"
            booking_payment_detail.payment_type = "WALLET"
            booking_payment_detail.payment_medium = "Idbook"
            booking_payment_detail.is_transaction_success = False
            booking_payment_detail.transaction_for = "booking_confirmed"
            booking_payment_detail.save()
            send_booking_sms_task.apply_async(
                    kwargs={
                        'notification_type': 'PAYMENT_FAILED_INFO',
                        'params': {
                            'booking_id': instance.id,
                            'failed_amount': float(instance.final_amount),
                            'payment_purpose': 'Hotel Booking'
                        }
                    }
                )
            
            custom_response = self.get_error_response(
                message="Error in wallet deduction; Please make sure wallet has sufficient fund",
                status="error", errors=[], error_code="WALLET_ERROR",
                status_code=status.HTTP_400_BAD_REQUEST)
            return custom_response

        booking_id = instance.id
        booking_type = instance.booking_type

        while True:
            confirmation_code = generate_booking_confirmation_code(
                booking_id, booking_type) # need to remove the params
            is_exist = check_booking_confirmation_code(confirmation_code)
            if not is_exist:
                break
        
        print("Confirmation Code::", confirmation_code)
        instance.confirmation_code = confirmation_code
        instance.total_payment_made = instance.final_amount
        instance.status = 'confirmed'      
        instance.save()
        instance.meta_info.booking_confirmed_date = datetime.now()
        instance.meta_info.save()

        booking_payment_detail.code = "PAYMENT_SUCCESS"
        booking_payment_detail.message = "Your payment is successful."
        booking_payment_detail.payment_type = "WALLET"
        booking_payment_detail.payment_medium = "Idbook"
        booking_payment_detail.amount = instance.final_amount
        booking_payment_detail.is_transaction_success = True
        booking_payment_detail.transaction_for = "booking_confirmed"
        booking_payment_detail.save()

        # update total no of confirmed booking for a property
        process_property_confirmed_booking_total(property_id)
        
        create_invoice_task.apply_async(args=[booking_id])
        send_booking_sms_task.apply_async(
            kwargs={
                'notification_type': 'HOTEL_BOOKING_CONFIRMATION',
                'params': {
                    'booking_id': booking_id
                }
            }
        )
        send_hotel_sms_task.apply_async(
            kwargs={
                'notification_type': 'HOTELIER_BOOKING_NOTIFICATION',
                'params': {
                    'booking_id': booking_id
                }
            }
        )
        print(f"Booking confirmation SMS scheduled for booking {booking_id}")
            
        custom_response = self.get_response(
            status='success', data=None,
            message="Booking Confirmed", status_code=status.HTTP_200_OK,)

        return custom_response

    @action(detail=True, methods=['PATCH'], url_path='hold',
            url_name='hold', permission_classes=[IsAuthenticated])
    def hold_booking(self, request, pk):
        
        instance = self.get_object()
        confirmed_room_details = instance.hotel_booking.confirmed_room_details
        property_id = instance.hotel_booking.confirmed_property_id
        confirmed_checkin_time = instance.hotel_booking.confirmed_checkin_time
        confirmed_checkout_time = instance.hotel_booking.confirmed_checkout_time
        
        # check the room availability before locking
        room_confirmed_dict = total_room_count(confirmed_room_details)
        booked_rooms = check_room_booked_details(
            confirmed_checkin_time, confirmed_checkout_time,
            property_id, is_slot_price_enabled=True, booking_id=pk)
        room_rejected_list = check_room_count(booked_rooms, room_confirmed_dict)

        if not room_rejected_list:
            on_hold_end_time = datetime.now(timezone('UTC')) + timedelta(minutes=5)
            instance.status = 'on_hold'
            instance.on_hold_end_time = on_hold_end_time
            instance.save()

            custom_response = self.get_response(
                status='success', count=1, data={"id":pk, "status":instance.status},
                message="On Hold state activated", status_code=status.HTTP_200_OK,)
            return custom_response
        else:
            print("room rejected list::", room_rejected_list)
            custom_response = self.get_error_response(
                message=f"Few of the selected rooms are not available.", status="error",
                errors=[],error_code="ROOM_UNAVAILABLE",
                status_code=status.HTTP_400_BAD_REQUEST)
            return custom_response
            
        

##class ReviewViewSet(viewsets.ModelViewSet, StandardResponseMixin, LoggingMixin):
##    queryset = Review.objects.all()
##    serializer_class = ReviewSerializer
##    # permission_classes = [IsAuthenticated,]
##    # permission_classes = [AnonymousCanViewOnlyPermission,]
##    http_method_names = ['get', 'post', 'put', 'patch']
##
##    permission_classes_by_action = {'create': [IsAuthenticated], 'update': [IsAuthenticated],
##                                    'partial_update': [IsAuthenticated],
##                                    'destroy': [IsAuthenticated], 'list':[AllowAny], 'retrieve':[AllowAny]}
##
##    def get_permissions(self):
##        try:
##            return [permission() for permission in self.permission_classes_by_action[self.action]]
##        except KeyError: 
##            # action is not set return default permission_classes
##            return [permission() for permission in self.permission_classes]
##
##    def review_filter_ops(self):
##        
##        filter_dict = {}
##        # fetch filter parameters
##        param_dict= self.request.query_params
##        for key in param_dict:
##            if key in ('booking', 'property', 'user'):
##                filter_dict[key] = param_dict[key]
##
##        if filter_dict:
##            self.queryset = self.queryset.filter(**filter_dict)
##
##        
##
##    def create(self, request, *args, **kwargs):
##        self.log_request(request)  # Log the incoming request
##
##        booking_id = request.data.get('booking', None)
##        review_exist = check_review_exist_for_booking(booking_id)
##        if review_exist:
##            custom_response = self.get_error_response(message="Review already done for the booking", status="error",
##                                                      errors=[],error_code="DUPLICATE_REVIEW",
##                                                      status_code=status.HTTP_400_BAD_REQUEST)
##            return custom_response
##            
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
##                status="success",
##                data=response.data,  # Use the data from the default response
##                message="Review Created",
##                status_code=status.HTTP_201_CREATED,  # 201 for successful creation
##
##            )
##        else:
##            custom_response = self.get_error_response(message="Validation Error", status="error",
##                                                      errors=[],error_code="VALIDATION_ERROR",
##                                                      status_code=status.HTTP_400_BAD_REQUEST)
##
##        self.log_response(custom_response)  # Log the custom response before returning
##        return custom_response
##
##    def list(self, request, *args, **kwargs):
##        self.log_request(request)  # Log the incoming request
##
##        self.review_filter_ops()
##        # paginate the result
##        count, self.queryset = paginate_queryset(self.request,  self.queryset)
##
##        # Perform the default listing logic
##        response = super().list(request, *args, **kwargs)
##
##        if response.status_code == status.HTTP_200_OK:
##            # If the response status code is OK (200), it's a successful listing
##            custom_response = self.get_response(
##                status="success",
##                count=count,
##                data=response.data,  # Use the data from the default response
##                message="List Retrieved",
##                status_code=status.HTTP_200_OK,  # 200 for successful listing
##
##            )
##        else:
##            custom_response = self.get_error_response(message="Validation Error", status="error",
##                                                      errors=[],error_code="VALIDATION_ERROR",
##                                                      status_code=status.HTTP_400_BAD_REQUEST)
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
##                status="success",
##                data=response.data,  # Use the data from the default response
##                message="Item Retrieved",
##                status_code=status.HTTP_200_OK,  # 200 for successful retrieval
##
##            )
##        else:
##            custom_response = self.get_error_response(message="Validation Error", status="error",
##                                                      errors=[],error_code="VALIDATION_ERROR",
##                                                      status_code=status.HTTP_400_BAD_REQUEST)
##
##        self.log_response(custom_response)  # Log the custom response before returning
##        return custom_response


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

##        if room_rejected_list:
##            custom_response = self.get_error_response(
##                message="Some of the selected rooms are allready booked, please refresh your list",
##                status="error", errors=room_rejected_list, error_code="BOOKING_ERROR",
##                status_code=status.HTTP_400_BAD_REQUEST)
##            return custom_response


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
                otp = user_details.get('otp', None)

                address = user_details.get('address', '')
                gender = user_details.get('gender', '')
                state = user_details.get('state', '')
                country = user_details.get('country', '')
                pan_card_number = user_details.get('pan_card_number', '')
                
                if not email:
                    custom_response = self.get_error_response(
                        message="Missing user email",
                        status="error", errors=[], error_code="VALIDATION_ERROR",
                        status_code=status.HTTP_400_BAD_REQUEST)
                    return custom_response

                # verify email using otp
                user_otp = None
                if otp:
                    user_otp = UserOtp.objects.filter(user_account=email, otp=otp, otp_for='VERIFY-GUEST').first()
                    if not user_otp:
                        response = self.get_error_response(
                            message="Invalid OTP", status="error",
                            errors=[], error_code="INVALID_OTP",
                            status_code=status.HTTP_406_NOT_ACCEPTABLE)
                        return response
                   

                user = get_user_from_email(email)
                if not user:
                    udetails = {"name":name, "mobile_number":mobile_number,
                                "email":email}
                    cdetails = {"address":address, "gender":gender,
                                "state":state, "country":country,
                                "pan_card_number":pan_card_number}
                    
                    user = create_user(udetails, cdetails)
                    user = add_group_for_guest_user(user)
                    # add_group_based_on_signup(user, '')
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
                    "amount": int(amount) * 100,
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
                    send_booking_sms_task.apply_async(
                        kwargs={
                            'notification_type': 'PAYMENT_FAILED_INFO',
                            'params': {
                                'booking_id': booking_id,
                                'failed_amount': float(amount),
                                'payment_purpose': 'Hotel Booking'  # Dynamic based on context
                            }
                        }
                    )
                    print(f"Payment failed SMS scheduled for booking {booking_id}")
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
        
##            confirmation_code = generate_booking_confirmation_code(booking_id, booking_type)
            while True:
                confirmation_code = generate_booking_confirmation_code(
                    booking_id, booking_type) # need to remove the params
                is_exist = check_booking_confirmation_code(confirmation_code)
                if not is_exist:
                    break
            print("Confirmation Code::", confirmation_code)
            booking.confirmation_code = confirmation_code
            booking.total_payment_made = amount
            booking.status = 'confirmed'
            booking.save()
            booking.meta_info.booking_confirmed_date = datetime.now()
            booking.meta_info.save()

            # update property confirmed booking count
            property_id = booking.hotel_booking.confirmed_property_id
            process_property_confirmed_booking_total(property_id)
        
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
            amount = int(sub_json_data.get('amount', 0))/100
            merchant_transaction_id = sub_json_data.get('merchantTransactionId', '')
            booking_payment_log['merchant_transaction_id'] = merchant_transaction_id
            transaction_id = sub_json_data.get('transactionId', '')        
            print(json_data)

            booking_payment_details = {
                "transaction_id": transaction_id, "code": code,
                "message":message, "payment_type": "PAYMENT GATEWAY",
                "payment_medium": "PHONE PAY", "amount": amount, "transaction_details": sub_json_data, "transaction_for": "booking_confirmed"}

            if code == "PAYMENT_SUCCESS":
                booking_payment_details["is_transaction_success"] = True

            update_booking_payment_details(merchant_transaction_id, booking_payment_details)
            booking_id = get_booking_from_payment(merchant_transaction_id)
            booking_payment_log['booking_id'] = booking_id

            if code == "PAYMENT_ERROR":
                send_booking_sms_task.apply_async(
                    kwargs={
                        'notification_type': 'PAYMENT_FAILED_INFO',
                        'params': {
                            'booking_id': booking_id,
                            'failed_amount': amount,
                            'payment_purpose': 'Hotel Booking'
                        }
                    }
                )

            if code == "PAYMENT_SUCCESS":
                self.set_booking_as_confirmed(booking_id, amount)
                send_booking_sms_task.apply_async(
                    kwargs={
                        'notification_type': 'HOTEL_BOOKING_CONFIRMATION',
                        'params': {
                            'booking_id': booking_id
                        }
                    }
                )
                send_hotel_sms_task.apply_async(
                    kwargs={
                        'notification_type': 'HOTELIER_BOOKING_NOTIFICATION',
                        'params': {
                            'booking_id': booking_id
                        }
                    }
                )
                print(f"Booking confirmation SMS scheduled for booking {booking_id}")
                send_booking_sms_task.apply_async(
                    kwargs={
                        'notification_type': 'PAYMENT_PROCEED_INFO',
                        'params': {
                            'booking_id': booking_id,
                            'amount': float(amount),
                            'payment_purpose': 'Hotel Booking',
                            'transaction_id': transaction_id
                        }
                    }
                )
                print(f"Payment processed SMS scheduled for booking {booking_id}")
                send_hotel_sms_task.apply_async(
                    kwargs={
                        'notification_type': 'HOTELER_PAYMENT_NOTIFICATION',
                        'params': {
                            'booking_id': booking_id
                        }
                    }
                )


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
            print(traceback.format_exc())
            create_booking_payment_log(booking_payment_log)
            return custom_response
            
            

    
    
