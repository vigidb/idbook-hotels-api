from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import viewsets
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import views, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.generics import (
    CreateAPIView,
    ListAPIView,
    GenericAPIView,
    RetrieveAPIView,
    UpdateAPIView,
)
from IDBOOKAPI.mixins import StandardResponseMixin, LoggingMixin
from IDBOOKAPI.permissions import HasRoleModelPermission, AnonymousCanViewOnlyPermission
from .serializers import (
    CouponSerializer,
    CouponPartnerSerializer,
    CouponCampaignSerializer,
    CouponAmountSlabSerializer,
    CouponRedemptionSerializer,
    CouponClaimSerializer,
)
from .models import (
    Coupon,
    CouponPartner,
    CouponCampaign,
    CouponAmountSlab,
    CouponRedemption,
)
from rest_framework.decorators import action
from rest_framework.throttling import ScopedRateThrottle


from apps.booking.utils.db_utils import (
    get_user_based_applied_coupon,
    check_user_used_coupon,
)
from apps.booking.models import AppliedCoupon

from datetime import datetime
from decimal import Decimal
from django.db.models import Q
from django.db.utils import ProgrammingError

from IDBOOKAPI.utils import paginate_queryset, order_ops

from apps.coupons.services.redemption import validate_coupon_for_context
from apps.authentication.constants import UserGroups
from apps.authentication.utils.token_utils import get_user_active_group
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi


class CouponPartnerViewSet(viewsets.ModelViewSet, StandardResponseMixin, LoggingMixin):
    queryset = CouponPartner.objects.all().order_by("name")
    serializer_class = CouponPartnerSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "post", "put", "patch"]

    def get_queryset(self):
        queryset = super().get_queryset()
        active = self.request.query_params.get("active")
        search = (self.request.query_params.get("search") or "").strip()
        partner_type = (self.request.query_params.get("partner_type") or "").strip()

        if active is not None:
            queryset = queryset.filter(active=str(active).lower() == "true")
        if partner_type:
            queryset = queryset.filter(partner_type__iexact=partner_type)
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search)
                | Q(display_name__icontains=search)
                | Q(partner_type__icontains=search)
            )
        queryset = queryset.order_by("name")
        return order_ops(self.request, queryset)

    def list(self, request, *args, **kwargs):
        self.log_request(request)
        queryset = self.filter_queryset(self.get_queryset())
        count, queryset = paginate_queryset(self.request, queryset)
        serializer = self.get_serializer(queryset, many=True)
        custom_response = self.get_response(
            count=count,
            status="success",
            data=serializer.data,
            message="List Retrieved",
            status_code=status.HTTP_200_OK,
        )
        self.log_response(custom_response)
        return custom_response

    def retrieve(self, request, *args, **kwargs):
        self.log_request(request)
        response = super().retrieve(request, *args, **kwargs)
        custom_response = (
            self.get_response(
                data=response.data,
                message="Item Retrieved",
                status_code=status.HTTP_200_OK,
            )
            if response.status_code == status.HTTP_200_OK
            else self.get_response(
                data=None,
                message="Error Occurred",
                status_code=response.status_code,
                is_error=True,
            )
        )
        self.log_response(custom_response)
        return custom_response

    def create(self, request, *args, **kwargs):
        self.log_request(request)
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            resp = super().create(request, *args, **kwargs)
            custom_response = self.get_response(
                data=resp.data,
                message="Item Created",
                status_code=status.HTTP_201_CREATED,
                status="success",
                count=1,
            )
            self.log_response(custom_response)
            return custom_response
        custom_response = self.get_error_response(
            message="Validation Error",
            status="error",
            errors=self.custom_serializer_error(serializer.errors),
            error_code="VALIDATION_ERROR",
            status_code=status.HTTP_400_BAD_REQUEST,
        )
        self.log_response(custom_response)
        return custom_response

    def update(self, request, *args, **kwargs):
        self.log_request(request)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data)
        if serializer.is_valid():
            resp = super().update(request, *args, **kwargs)
            custom_response = self.get_response(
                data=resp.data,
                message="Item Updated",
                status_code=status.HTTP_200_OK,
                status="success",
                count=1,
            )
            self.log_response(custom_response)
            return custom_response
        custom_response = self.get_error_response(
            message="Validation Error",
            status="error",
            errors=self.custom_serializer_error(serializer.errors),
            error_code="VALIDATION_ERROR",
            status_code=status.HTTP_400_BAD_REQUEST,
        )
        self.log_response(custom_response)
        return custom_response

    def partial_update(self, request, *args, **kwargs):
        self.log_request(request)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)

        if serializer.is_valid():
            self.perform_update(serializer)
            custom_response = self.get_response(
                status="success",
                count=1,
                data=serializer.data,
                message="Update success",
                status_code=status.HTTP_200_OK,
            )
            self.log_response(custom_response)
            return custom_response

        serializer_errors = self.custom_serializer_error(serializer.errors)
        custom_response = self.get_error_response(
            message="Validation Error",
            status="error",
            errors=serializer_errors,
            error_code="VALIDATION_ERROR",
            status_code=status.HTTP_400_BAD_REQUEST,
        )
        self.log_response(custom_response)
        return custom_response


class CouponCampaignViewSet(viewsets.ModelViewSet, StandardResponseMixin, LoggingMixin):
    queryset = CouponCampaign.objects.all().order_by("-created")
    serializer_class = CouponCampaignSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "post", "put", "patch"]

    def get_queryset(self):
        queryset = super().get_queryset()
        active = self.request.query_params.get("active")
        search = (self.request.query_params.get("search") or "").strip()
        partner = self.request.query_params.get("partner")
        booking_type = (self.request.query_params.get("booking_type") or "").strip().upper()

        if active is not None:
            queryset = queryset.filter(active=str(active).lower() == "true")
        if partner:
            queryset = queryset.filter(partner_id=partner)
        if booking_type:
            queryset = queryset.filter(
                Q(allowed_booking_types=[]) | Q(allowed_booking_types__contains=[booking_type])
            )
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search)
                | Q(internal_code__icontains=search)
                | Q(partner__name__icontains=search)
            )
        queryset = queryset.select_related("partner").order_by("-created")
        return order_ops(self.request, queryset)

    def list(self, request, *args, **kwargs):
        self.log_request(request)
        queryset = self.filter_queryset(self.get_queryset())
        count, queryset = paginate_queryset(self.request, queryset)
        serializer = self.get_serializer(queryset, many=True)
        custom_response = self.get_response(
            count=count,
            status="success",
            data=serializer.data,
            message="List Retrieved",
            status_code=status.HTTP_200_OK,
        )
        self.log_response(custom_response)
        return custom_response

    def retrieve(self, request, *args, **kwargs):
        self.log_request(request)
        response = super().retrieve(request, *args, **kwargs)
        custom_response = (
            self.get_response(
                data=response.data,
                message="Item Retrieved",
                status_code=status.HTTP_200_OK,
            )
            if response.status_code == status.HTTP_200_OK
            else self.get_response(
                data=None,
                message="Error Occurred",
                status_code=response.status_code,
                is_error=True,
            )
        )
        self.log_response(custom_response)
        return custom_response

    def create(self, request, *args, **kwargs):
        self.log_request(request)
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            resp = super().create(request, *args, **kwargs)
            custom_response = self.get_response(
                data=resp.data,
                message="Item Created",
                status_code=status.HTTP_201_CREATED,
                status="success",
                count=1,
            )
            self.log_response(custom_response)
            return custom_response
        custom_response = self.get_error_response(
            message="Validation Error",
            status="error",
            errors=self.custom_serializer_error(serializer.errors),
            error_code="VALIDATION_ERROR",
            status_code=status.HTTP_400_BAD_REQUEST,
        )
        self.log_response(custom_response)
        return custom_response

    def update(self, request, *args, **kwargs):
        self.log_request(request)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data)
        if serializer.is_valid():
            resp = super().update(request, *args, **kwargs)
            custom_response = self.get_response(
                data=resp.data,
                message="Item Updated",
                status_code=status.HTTP_200_OK,
                status="success",
                count=1,
            )
            self.log_response(custom_response)
            return custom_response
        custom_response = self.get_error_response(
            message="Validation Error",
            status="error",
            errors=self.custom_serializer_error(serializer.errors),
            error_code="VALIDATION_ERROR",
            status_code=status.HTTP_400_BAD_REQUEST,
        )
        self.log_response(custom_response)
        return custom_response

    def partial_update(self, request, *args, **kwargs):
        self.log_request(request)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)

        if serializer.is_valid():
            self.perform_update(serializer)
            custom_response = self.get_response(
                status="success",
                count=1,
                data=serializer.data,
                message="Update success",
                status_code=status.HTTP_200_OK,
            )
            self.log_response(custom_response)
            return custom_response

        serializer_errors = self.custom_serializer_error(serializer.errors)
        custom_response = self.get_error_response(
            message="Validation Error",
            status="error",
            errors=serializer_errors,
            error_code="VALIDATION_ERROR",
            status_code=status.HTTP_400_BAD_REQUEST,
        )
        self.log_response(custom_response)
        return custom_response


class CouponAmountSlabViewSet(viewsets.ModelViewSet, StandardResponseMixin, LoggingMixin):
    queryset = CouponAmountSlab.objects.all().order_by("campaign_id", "sort_order", "id")
    serializer_class = CouponAmountSlabSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "post", "put", "patch"]

    def get_queryset(self):
        queryset = super().get_queryset()
        campaign = self.request.query_params.get("campaign")
        active = self.request.query_params.get("active")
        search = (self.request.query_params.get("search") or "").strip()

        if campaign:
            queryset = queryset.filter(campaign_id=campaign)
        if active is not None:
            queryset = queryset.filter(campaign__active=str(active).lower() == "true")
        if search:
            queryset = queryset.filter(
                Q(campaign__name__icontains=search)
                | Q(campaign__internal_code__icontains=search)
            )
        queryset = queryset.select_related("campaign").order_by(
            "campaign_id", "sort_order", "id"
        )
        return order_ops(self.request, queryset)

    def list(self, request, *args, **kwargs):
        self.log_request(request)
        queryset = self.filter_queryset(self.get_queryset())
        count, queryset = paginate_queryset(self.request, queryset)
        serializer = self.get_serializer(queryset, many=True)
        custom_response = self.get_response(
            count=count,
            status="success",
            data=serializer.data,
            message="List Retrieved",
            status_code=status.HTTP_200_OK,
        )
        self.log_response(custom_response)
        return custom_response

    def retrieve(self, request, *args, **kwargs):
        self.log_request(request)
        response = super().retrieve(request, *args, **kwargs)
        custom_response = (
            self.get_response(
                data=response.data,
                message="Item Retrieved",
                status_code=status.HTTP_200_OK,
            )
            if response.status_code == status.HTTP_200_OK
            else self.get_response(
                data=None,
                message="Error Occurred",
                status_code=response.status_code,
                is_error=True,
            )
        )
        self.log_response(custom_response)
        return custom_response

    def create(self, request, *args, **kwargs):
        self.log_request(request)
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            resp = super().create(request, *args, **kwargs)
            custom_response = self.get_response(
                data=resp.data,
                message="Item Created",
                status_code=status.HTTP_201_CREATED,
                status="success",
                count=1,
            )
            self.log_response(custom_response)
            return custom_response
        custom_response = self.get_error_response(
            message="Validation Error",
            status="error",
            errors=self.custom_serializer_error(serializer.errors),
            error_code="VALIDATION_ERROR",
            status_code=status.HTTP_400_BAD_REQUEST,
        )
        self.log_response(custom_response)
        return custom_response

    def update(self, request, *args, **kwargs):
        self.log_request(request)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data)
        if serializer.is_valid():
            resp = super().update(request, *args, **kwargs)
            custom_response = self.get_response(
                data=resp.data,
                message="Item Updated",
                status_code=status.HTTP_200_OK,
                status="success",
                count=1,
            )
            self.log_response(custom_response)
            return custom_response
        custom_response = self.get_error_response(
            message="Validation Error",
            status="error",
            errors=self.custom_serializer_error(serializer.errors),
            error_code="VALIDATION_ERROR",
            status_code=status.HTTP_400_BAD_REQUEST,
        )
        self.log_response(custom_response)
        return custom_response

    def partial_update(self, request, *args, **kwargs):
        self.log_request(request)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)

        if serializer.is_valid():
            self.perform_update(serializer)
            custom_response = self.get_response(
                status="success",
                count=1,
                data=serializer.data,
                message="Update success",
                status_code=status.HTTP_200_OK,
            )
            self.log_response(custom_response)
            return custom_response

        serializer_errors = self.custom_serializer_error(serializer.errors)
        custom_response = self.get_error_response(
            message="Validation Error",
            status="error",
            errors=serializer_errors,
            error_code="VALIDATION_ERROR",
            status_code=status.HTTP_400_BAD_REQUEST,
        )
        self.log_response(custom_response)
        return custom_response


class CouponRedemptionViewSet(viewsets.ReadOnlyModelViewSet, StandardResponseMixin, LoggingMixin):
    queryset = CouponRedemption.objects.all().order_by("-created")
    serializer_class = CouponRedemptionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = super().get_queryset()
        campaign = self.request.query_params.get("campaign")
        partner = self.request.query_params.get("partner")
        user_id = self.request.query_params.get("user")
        booking = self.request.query_params.get("booking")
        booking_type = (self.request.query_params.get("booking_type") or "").strip().upper()
        status_value = (self.request.query_params.get("status") or "").strip().lower()
        search = (self.request.query_params.get("search") or "").strip()

        if campaign:
            queryset = queryset.filter(coupon__campaign_id=campaign)
        if partner:
            queryset = queryset.filter(coupon__partner_id=partner)
        if user_id:
            queryset = queryset.filter(user_id=user_id)
        if booking:
            queryset = queryset.filter(booking_id=booking)
        if booking_type:
            queryset = queryset.filter(booking_type=booking_type)
        if status_value:
            queryset = queryset.filter(status=status_value)
        if search:
            queryset = queryset.filter(
                Q(coupon__code__icontains=search)
                | Q(coupon__name__icontains=search)
                | Q(user__name__icontains=search)
                | Q(user__email__icontains=search)
            )
        queryset = queryset.select_related(
            "coupon", "coupon__campaign", "coupon__partner", "user"
        ).order_by("-created")
        return order_ops(self.request, queryset)

    def list(self, request, *args, **kwargs):
        self.log_request(request)
        queryset = self.filter_queryset(self.get_queryset())
        count, queryset = paginate_queryset(self.request, queryset)
        serializer = self.get_serializer(queryset, many=True)
        custom_response = self.get_response(
            count=count,
            status="success",
            data=serializer.data,
            message="List Retrieved",
            status_code=status.HTTP_200_OK,
        )
        self.log_response(custom_response)
        return custom_response

    def retrieve(self, request, *args, **kwargs):
        self.log_request(request)
        response = super().retrieve(request, *args, **kwargs)
        custom_response = (
            self.get_response(
                data=response.data,
                message="Item Retrieved",
                status_code=status.HTTP_200_OK,
            )
            if response.status_code == status.HTTP_200_OK
            else self.get_response(
                data=None,
                message="Error Occurred",
                status_code=response.status_code,
                is_error=True,
            )
        )
        self.log_response(custom_response)
        return custom_response


class CouponClaimViewSet(viewsets.ReadOnlyModelViewSet, StandardResponseMixin, LoggingMixin):
    queryset = AppliedCoupon.objects.all().order_by("-id")
    serializer_class = CouponClaimSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = (
            super()
            .get_queryset()
            .select_related(
                "coupon",
                "coupon__campaign",
                "coupon__partner",
                "booking",
                "booking__user",
            )
        )
        campaign = self.request.query_params.get("campaign")
        partner = self.request.query_params.get("partner")
        user_id = self.request.query_params.get("user")
        booking = self.request.query_params.get("booking")
        search = (self.request.query_params.get("search") or "").strip()

        if campaign:
            queryset = queryset.filter(coupon__campaign_id=campaign)
        if partner:
            queryset = queryset.filter(coupon__partner_id=partner)
        if user_id:
            queryset = queryset.filter(booking__user_id=user_id)
        if booking:
            queryset = queryset.filter(booking_id=booking)
        if search:
            queryset = queryset.filter(
                Q(coupon__code__icontains=search)
                | Q(coupon__name__icontains=search)
                | Q(booking__user__name__icontains=search)
                | Q(booking__user__email__icontains=search)
            )
        return order_ops(self.request, queryset)

    def list(self, request, *args, **kwargs):
        self.log_request(request)
        queryset = self.filter_queryset(self.get_queryset())
        count, queryset = paginate_queryset(self.request, queryset)
        serializer = self.get_serializer(queryset, many=True)
        custom_response = self.get_response(
            count=count,
            status="success",
            data=serializer.data,
            message="List Retrieved",
            status_code=status.HTTP_200_OK,
        )
        self.log_response(custom_response)
        return custom_response


class CouponViewSet(viewsets.ModelViewSet, StandardResponseMixin, LoggingMixin):
    queryset = Coupon.objects.all()
    serializer_class = CouponSerializer
    permission_classes = [IsAuthenticated]
    # filter_backends = [DjangoFilterBackend]
    # filterset_fields = ['service_category', 'district', 'area_name', 'city_name', 'starting_price', 'rating',]
    http_method_names = ["get", "post", "put", "patch"]
    # lookup_field = 'custom_id'

    def get_throttles(self):
        if getattr(self, "action", None) == "check_coupon_validity":
            self.throttle_scope = "coupon_validity"
            return [ScopedRateThrottle()]
        return super().get_throttles()

    def _is_admin_user(self):
        user = getattr(self.request, "user", None)
        if not user or not user.is_authenticated:
            return False
        active_group = get_user_active_group(user, self.request)
        default_group = active_group or getattr(user, "default_group", "")
        return default_group in [UserGroups.BUSINESS_GRP, UserGroups.BUS_ADMIN]

    def coupon_filter_ops(self):
        filter_dict = {}

        user_id = self.request.query_params.get("user", "")
        checkin_date = self.request.query_params.get("checkin_date", "")
        booking_date = self.request.query_params.get("booking_date", "")
        property_id = self.request.query_params.get("property", "")
        active = self.request.query_params.get("active", None)
        code = self.request.query_params.get("code", "")

        # Visibility policy:
        # - Admin users can see all coupons.
        # - Non-admin users should NOT see admin-managed/internal campaign coupons in coupon list.
        #   These are distributed via CSV/internal channels and are meant for manual entry/validation.
        if not self._is_admin_user():
            self.queryset = self.queryset.filter(campaign__isnull=True, partner__isnull=True)

        if user_id:
            used_coupons = get_user_based_applied_coupon(user_id)
            print("used coupons", used_coupons)
            if used_coupons:
                self.queryset = self.queryset.exclude(code__in=used_coupons)

        # filter based on check in and booking date
        if checkin_date and booking_date:
            checkin_date = datetime.strptime(checkin_date, "%Y-%m-%d").date()
            booking_date = datetime.strptime(booking_date, "%Y-%m-%d").date()

            self.queryset = self.queryset.filter(
                Q(is_stay_date=False, is_booking_date=False)
                | Q(
                    stay_start_date__isnull=True,
                    stay_end_date__isnull=True,
                    booking_start_date__isnull=True,
                    booking_end_date__isnull=True,
                )
                | Q(stay_start_date__lte=checkin_date, stay_end_date__gte=checkin_date)
                | Q(
                    booking_start_date__lte=booking_date,
                    booking_end_date__gte=booking_date,
                )
            )
        elif checkin_date:
            checkin_date = datetime.strptime(checkin_date, "%Y-%m-%d").date()
            self.queryset = self.queryset.filter(
                Q(is_stay_date=False, is_booking_date=False)
                | Q(
                    stay_start_date__isnull=True,
                    stay_end_date__isnull=True,
                    booking_start_date__isnull=True,
                    booking_end_date__isnull=True,
                )
                |
                Q(stay_start_date__lte=checkin_date, stay_end_date__gte=checkin_date)
            )
        elif booking_date:
            booking_date = datetime.strptime(booking_date, "%Y-%m-%d").date()
            self.queryset = self.queryset.filter(
                Q(is_stay_date=False, is_booking_date=False)
                | Q(
                    stay_start_date__isnull=True,
                    stay_end_date__isnull=True,
                    booking_start_date__isnull=True,
                    booking_end_date__isnull=True,
                )
                | Q(booking_start_date__lte=booking_date, booking_end_date__gte=booking_date)
            )

        if property_id:
            self.queryset = self.queryset.filter(
                Q(property=property_id) | Q(property__isnull=True)
            )
        else:
            self.queryset = self.queryset.filter(property__isnull=True)

        if active is not None:
            active = True if active == "true" else False
            self.queryset = self.queryset.filter(active=active)

        if code:
            self.queryset = self.queryset.filter(code__icontains=code)

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
                is_error=True,
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
                is_error=True,
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
            # response = super().partial_update(request, *args, **kwargs)
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
            custom_response = self.get_error_response(
                message="Validation Error",
                status="error",
                errors=serializer_errors,
                error_code="VALIDATION_ERROR",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
            return custom_response

    def list(self, request, *args, **kwargs):
        self.log_request(request)  # Log the incoming request
        # coupon filter
        self.coupon_filter_ops()

        # Apply ordering for server-side sorting when requested
        self.queryset = order_ops(self.request, self.queryset)

        count, self.queryset = paginate_queryset(self.request, self.queryset)
        # Perform the default listing logic
        response = super().list(request, *args, **kwargs)

        custom_response = self.get_response(
            count=count,
            status="success",
            data=response.data,
            message="List Retrieved",
            status_code=status.HTTP_200_OK,
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
                is_error=True,
            )

        self.log_response(custom_response)  # Log the custom response before returning
        return custom_response

    @action(
        detail=False,
        methods=["POST"],
        permission_classes=[],
        url_path="validity",
        url_name="validity",
    )
    @swagger_auto_schema(
        operation_summary="Validate coupon for amount/context",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=["code"],
            properties={
                "code": openapi.Schema(type=openapi.TYPE_STRING),
                "booking_type": openapi.Schema(type=openapi.TYPE_STRING, default="HOTEL"),
                "amount": openapi.Schema(type=openapi.TYPE_NUMBER),
                "user": openapi.Schema(type=openapi.TYPE_INTEGER),
                "checkin_date": openapi.Schema(type=openapi.TYPE_STRING, format="date"),
                "booking_date": openapi.Schema(type=openapi.TYPE_STRING, format="date"),
            },
        ),
        responses={200: "Coupon valid", 400: "Coupon invalid or bad payload"},
    )
    def check_coupon_validity(self, request):
        code = request.data.get("code", "")
        checkin_date = request.data.get("checkin_date", "")
        booking_date = request.data.get("booking_date", "")
        user_id = request.data.get("user", None)
        booking_type = request.data.get("booking_type", "HOTEL")
        raw_amount = request.data.get("amount", None)

        if checkin_date:
            checkin_date = datetime.strptime(str(checkin_date), "%Y-%m-%d").date()

        if booking_date:
            booking_date = datetime.strptime(str(booking_date), "%Y-%m-%d").date()

        if not code:
            return self.get_error_response(
                message="Missing coupon code",
                status="error",
                errors=[],
                error_code="CODE_MISSING",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        amount = None
        if raw_amount is not None and raw_amount != "":
            try:
                amount = Decimal(str(raw_amount))
            except Exception:
                return self.get_error_response(
                    message="Invalid amount",
                    status="error",
                    errors=[],
                    error_code="VALIDATION_ERROR",
                    status_code=status.HTTP_400_BAD_REQUEST,
                )

        uid = None
        if user_id is not None and user_id != "":
            try:
                uid = int(user_id)
            except (TypeError, ValueError):
                uid = None

        ctx = validate_coupon_for_context(
            code,
            booking_type=booking_type,
            amount=amount,
            user_id=uid,
            checkin_date=checkin_date or None,
            booking_date=booking_date or None,
        )

        if not ctx["valid"]:
            return self.get_error_response(
                message=ctx.get("user_message") or "Invalid coupon",
                status="error",
                errors=[],
                error_code=ctx.get("reason_code") or "CODE_INVALID",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        coupon = ctx["coupon"]
        serializer = CouponSerializer(coupon)
        data = dict(serializer.data)
        data["valid"] = True
        data["reason_code"] = ""
        data["user_message"] = ""
        if ctx.get("discount_applied") is not None:
            data["discount_applied"] = float(ctx["discount_applied"])
        if ctx.get("payable_after_discount") is not None:
            data["payable_after_discount"] = float(ctx["payable_after_discount"])
        data["campaign_name"] = ctx.get("campaign_name") or ""

        return self.get_response(
            status="success",
            data=data,
            message="Coupon Details",
            status_code=status.HTTP_200_OK,
        )

    @action(
        detail=False,
        methods=["POST"],
        url_path="bulk-generate",
        url_name="bulk-generate",
    )
    @swagger_auto_schema(
        operation_summary="Bulk generate partner coupon codes",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=["campaign_id", "count"],
            properties={
                "campaign_id": openapi.Schema(type=openapi.TYPE_INTEGER),
                "count": openapi.Schema(type=openapi.TYPE_INTEGER, minimum=1, maximum=5000),
                "code_prefix": openapi.Schema(type=openapi.TYPE_STRING, default="IDB-MAT-"),
                "max_redemptions_total": openapi.Schema(
                    type=openapi.TYPE_INTEGER,
                    minimum=0,
                    description="Optional per-coupon total redemption limit for each generated code.",
                ),
                "max_redemptions_per_user": openapi.Schema(
                    type=openapi.TYPE_INTEGER,
                    minimum=0,
                    description="Optional per-coupon per-user redemption limit for each generated code.",
                ),
                "max_total_discount_budget": openapi.Schema(
                    type=openapi.TYPE_NUMBER,
                    description="Optional per-coupon total discount budget cap for each generated code.",
                ),
            },
        ),
        responses={201: "Coupons generated", 400: "Validation error", 404: "Campaign not found"},
    )
    def bulk_generate(self, request):
        """Generate N coupon codes sharing the same campaign (prefix e.g. IDB-MAT-)."""
        self.log_request(request)
        campaign_id = request.data.get("campaign_id")
        try:
            count = int(request.data.get("count", 0) or 0)
        except (TypeError, ValueError):
            count = 0
        prefix = request.data.get("code_prefix", "IDB-MAT-")
        raw_coupon_total = request.data.get("max_redemptions_total", None)
        raw_coupon_per_user = request.data.get("max_redemptions_per_user", None)
        raw_coupon_budget = request.data.get("max_total_discount_budget", None)
        raw_use_override = request.data.get("use_coupon_value_override", False)
        raw_discount_type = (request.data.get("discount_type", "AMOUNT") or "AMOUNT").upper()
        raw_discount = request.data.get("discount", 0)

        def _to_optional_int(v):
            if v in (None, ""):
                return None
            try:
                iv = int(v)
            except (TypeError, ValueError):
                return None
            return iv if iv >= 0 else None

        def _to_optional_decimal(v):
            if v in (None, ""):
                return None
            try:
                dv = Decimal(str(v))
            except Exception:
                return None
            return dv if dv >= 0 else None

        def _to_bool(v):
            if isinstance(v, bool):
                return v
            if isinstance(v, str):
                return v.strip().lower() in ("true", "1", "yes")
            return bool(v)

        coupon_max_total = _to_optional_int(raw_coupon_total)
        coupon_max_per_user = _to_optional_int(raw_coupon_per_user)
        coupon_budget_cap = _to_optional_decimal(raw_coupon_budget)
        use_coupon_value_override = _to_bool(raw_use_override)
        discount_type = raw_discount_type if raw_discount_type in ("AMOUNT", "PERCENT") else None
        discount_value = _to_optional_decimal(raw_discount)
        if raw_coupon_total not in (None, "") and coupon_max_total is None:
            return self.get_error_response(
                message="max_redemptions_total must be a non-negative integer",
                status="error",
                errors=[],
                error_code="VALIDATION_ERROR",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        if raw_coupon_per_user not in (None, "") and coupon_max_per_user is None:
            return self.get_error_response(
                message="max_redemptions_per_user must be a non-negative integer",
                status="error",
                errors=[],
                error_code="VALIDATION_ERROR",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        if raw_coupon_budget not in (None, "") and coupon_budget_cap is None:
            return self.get_error_response(
                message="max_total_discount_budget must be a non-negative number",
                status="error",
                errors=[],
                error_code="VALIDATION_ERROR",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        if discount_type is None:
            return self.get_error_response(
                message="discount_type must be one of: AMOUNT, PERCENT",
                status="error",
                errors=[],
                error_code="VALIDATION_ERROR",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        if raw_discount not in (None, "") and discount_value is None:
            return self.get_error_response(
                message="discount must be a non-negative number",
                status="error",
                errors=[],
                error_code="VALIDATION_ERROR",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        if not campaign_id or count < 1 or count > 5000:
            return self.get_error_response(
                message="Provide campaign_id and count between 1 and 5000",
                status="error",
                errors=[],
                error_code="VALIDATION_ERROR",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        campaign = CouponCampaign.objects.filter(pk=campaign_id).first()
        if not campaign:
            return self.get_error_response(
                message="Campaign not found",
                status="error",
                errors=[],
                error_code="NOT_FOUND",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        created = []
        partner = campaign.partner
        prefix = (prefix or "").strip().upper()
        if prefix and not prefix.endswith("-"):
            prefix = prefix + "-"
        if len(f"{prefix}{'A' * 6}") > 64:
            return self.get_error_response(
                message="Prefix is too long for a 64-char coupon code",
                status="error",
                errors=[],
                error_code="VALIDATION_ERROR",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        try:
            for _ in range(count):
                c = Coupon(
                    campaign=campaign,
                    partner=partner,
                    discount_type=discount_type,
                    discount=discount_value or Decimal("0"),
                    use_coupon_value_override=use_coupon_value_override,
                    max_redemptions_total=coupon_max_total,
                    max_redemptions_per_user=coupon_max_per_user,
                    max_total_discount_budget=coupon_budget_cap,
                    active=True,
                )
                c.code = c.generate_unique_code(length=6, prefix=prefix)
                c.save()
                created.append(c.code)
        except ProgrammingError:
            return self.get_error_response(
                message=(
                    "Coupon schema is outdated. Please run database migrations "
                    "(python manage.py migrate) and retry."
                ),
                status="error",
                errors=[],
                error_code="SCHEMA_OUTDATED",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        return self.get_response(
            status="success",
            data={
                "codes": created,
                "count": len(created),
                "campaign_id": campaign.id,
                "campaign_name": campaign.name,
                "partner_id": partner.id if partner else None,
                "partner_name": partner.name if partner else "",
                "coupon_limits": {
                    "max_redemptions_total": coupon_max_total,
                    "max_redemptions_per_user": coupon_max_per_user,
                    "max_total_discount_budget": str(coupon_budget_cap)
                    if coupon_budget_cap is not None
                    else None,
                },
                "coupon_value": {
                    "use_coupon_value_override": use_coupon_value_override,
                    "discount_type": discount_type,
                    "discount": str(discount_value or Decimal("0")),
                },
            },
            message="Coupons generated",
            status_code=status.HTTP_201_CREATED,
        )
