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
from .serializers import (CouponSerializer)
from .models import (Coupon)
from rest_framework.decorators import action


from apps.booking.utils.db_utils import (
    get_user_based_applied_coupon, check_user_used_coupon)

from datetime import datetime
from django.db.models import Q

from IDBOOKAPI.utils import paginate_queryset


class CouponViewSet(viewsets.ModelViewSet, StandardResponseMixin, LoggingMixin):
    queryset = Coupon.objects.all()
    serializer_class = CouponSerializer
    permission_classes = [IsAuthenticated]
    # filter_backends = [DjangoFilterBackend]
    # filterset_fields = ['service_category', 'district', 'area_name', 'city_name', 'starting_price', 'rating',]
    http_method_names = ['get', 'post', 'put', 'patch']
    # lookup_field = 'custom_id'

    def coupon_filter_ops(self):
        filter_dict = {}
        
        user_id = self.request.query_params.get('user', '')
        checkin_date = self.request.query_params.get('checkin_date', '')
        booking_date = self.request.query_params.get('booking_date', '')
        property_id = self.request.query_params.get('property', '')
        active = self.request.query_params.get('active', None)
        
        if user_id:
            used_coupons = get_user_based_applied_coupon(user_id)
            print("used coupons", used_coupons)
            if used_coupons:
                self.queryset = self.queryset.exclude(code__in=used_coupons)

        # filter based on check in and booking date
        if checkin_date and booking_date:
            checkin_date = datetime.strptime(checkin_date, '%Y-%m-%d').date()
            booking_date = datetime.strptime(booking_date, '%Y-%m-%d').date()
            
            self.queryset = self.queryset.filter(
                Q(stay_start_date__lte=checkin_date, stay_end_date__gte=checkin_date)
                | Q(booking_start_date__lte=booking_date, booking_end_date__gte=booking_date))
        elif checkin_date:
            checkin_date = datetime.strptime(checkin_date, '%Y-%m-%d').date()
            self.queryset = self.queryset.filter(
                stay_start_date__lte=checkin_date, stay_end_date__gte=checkin_date)
        elif booking_date:
            booking_date = datetime.strptime(booking_date, '%Y-%m-%d').date()
            self.queryset = self.queryset.filter(
                booking_start_date__lte=booking_date, booking_end_date__gte=booking_date)

        if property_id:
            self.queryset = self.queryset.filter(Q(property=property_id) | Q(property__isnull=True))
        else:
            self.queryset = self.queryset.filter(property__isnull=True)

        if active is not None:
            active = True if active == 'true' else False
            self.queryset = self.queryset.filter(active=active)

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

    def partial_update(self, request, *args, **kwargs):
        self.log_request(request)  # Log the incoming request
        # Get the object to be updated
        instance = self.get_object()

        # Create an instance of your serializer with the request data and the object to be updated
        serializer = self.get_serializer(instance, data=request.data, partial=True)

        if serializer.is_valid():
            # If the serializer is valid, perform the default update logic
            #response = super().partial_update(request, *args, **kwargs)
            response = self.perform_update(serializer)
            custom_response = self.get_response(
                status="success",
                count=1,
                data=serializer.data,  # Use the data from the default response
                message="Update success",
                status_code=status.HTTP_200_OK,  # 200 for successful listing
            )
            return custom_response
        else:
            # If the serializer is not valid, create a custom response with error details
            serializer_errors = self.custom_serializer_error(serializer.errors)
            custom_response = self.get_error_response(message="Validation Error", status="error",
                                                      errors=serializer_errors,error_code="VALIDATION_ERROR",
                                                      status_code=status.HTTP_400_BAD_REQUEST)
            return custom_response

    def list(self, request, *args, **kwargs):
        self.log_request(request)  # Log the incoming request
        # coupon filter
        self.coupon_filter_ops()

        count, self.queryset = paginate_queryset(self.request,  self.queryset)
        # Perform the default listing logic
        response = super().list(request, *args, **kwargs)

      
        custom_response = self.get_response(count=count, status="success",
                                            data=response.data, message="List Retrieved",
                                            status_code=status.HTTP_200_OK)


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

    @action(detail=False, methods=['POST'], permission_classes=[],
            url_path='validity', url_name='validity')
    def check_coupon_validity(self, request):
        code = request.data.get('code', '')
        checkin_date = request.data.get('checkin_date', '')
        booking_date = request.data.get('booking_date', '')
        user_id = request.data.get('user', None)

        if checkin_date:
            checkin_date = datetime.strptime(checkin_date, '%Y-%m-%d').date()

        if booking_date:
            booking_date = datetime.strptime(booking_date, '%Y-%m-%d').date()
        
        if not code:
            custom_response = self.get_error_response(
                message="Missing coupon code", status="error",
                errors=[],error_code="CODE_MISSING",
                status_code=status.HTTP_400_BAD_REQUEST)

            return custom_response

        
        coupon = Coupon.objects.filter(code=code, active=True).first()
        if not coupon:
            custom_response = self.get_error_response(
                message="Invalid coupon code", status="error",
                errors=[],error_code="CODE_INVALID",
                status_code=status.HTTP_400_BAD_REQUEST)

            return custom_response

        if user_id:
            coupon_used = check_user_used_coupon(code, user_id)
            if coupon_used:
                custom_response = self.get_error_response(
                    message="Coupon already applied", status="error",
                    errors=[],error_code="CODE_INVALID",
                    status_code=status.HTTP_400_BAD_REQUEST)

                return custom_response
            
        
        if coupon.is_stay_date:
            stay_start_date = coupon.stay_start_date
            stay_end_date = coupon.stay_end_date

            if not checkin_date:
                custom_response = self.get_error_response(
                    message="The coupon is based on checkin date, so please provide a checkin date",
                    status="error", errors=[],error_code="COUPON_DATE_ERROR",
                    status_code=status.HTTP_400_BAD_REQUEST)
                return custom_response
                

            if stay_start_date > checkin_date:
                custom_response = self.get_error_response(
                    message="Check in date is less than the coupon start date",
                    status="error", errors=[],error_code="COUPON_DATE_ERROR",
                    status_code=status.HTTP_400_BAD_REQUEST)
                return custom_response

            if stay_end_date and stay_end_date < checkin_date:
                custom_response = self.get_error_response(
                    message="Check in date is greater than the coupon end date",
                    status="error", errors=[],error_code="COUPON_DATE_ERROR",
                    status_code=status.HTTP_400_BAD_REQUEST)
                return custom_response


        elif coupon.is_booking_date:
            booking_start_date = coupon.booking_start_date
            booking_end_date = coupon.booking_end_date

            if not booking_date:
                custom_response = self.get_error_response(
                    message="The coupon is based on booking date, so please provide a booking date",
                    status="error", errors=[],error_code="COUPON_DATE_ERROR",
                    status_code=status.HTTP_400_BAD_REQUEST)
                return custom_response

            if booking_start_date > booking_date:
                custom_response = self.get_error_response(
                    message="Booking date is less than the coupon start date",
                    status="error", errors=[],error_code="COUPON_DATE_ERROR",
                    status_code=status.HTTP_400_BAD_REQUEST)
                return custom_response

            if booking_end_date and booking_end_date < booking_date:
                custom_response = self.get_error_response(
                    message="Booking date is greater than the coupon end date",
                    status="error", errors=[],error_code="COUPON_DATE_ERROR",
                    status_code=status.HTTP_400_BAD_REQUEST)
                return custom_response
                

        serializer = CouponSerializer(coupon)
        custom_response = self.get_response(
            status="success", data=serializer.data,
            message="Coupon Details",
            status_code=status.HTTP_200_OK,  # 200 for successful retrieval
        )
        return custom_response
        
            
            

        
        
