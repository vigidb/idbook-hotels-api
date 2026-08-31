from django.http import HttpResponse
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import Permission, Group
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes
from django.core.mail import send_mail
from django.db.models import Q
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import viewsets
from rest_framework import views, status
from rest_framework.permissions import AllowAny, IsAuthenticated, IsAdminUser
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.generics import (
    CreateAPIView,
    ListAPIView,
    GenericAPIView,
    RetrieveAPIView,
    UpdateAPIView,
)
from IDBOOKAPI.mixins import StandardResponseMixin, LoggingMixin
from IDBOOKAPI.utils import paginate_queryset, order_ops
from IDBOOKAPI.csv_export import csv_http_response_from_records, MAX_EXPORT_ROWS

from .models import BusinessDetail
from apps.authentication.models import User
from rest_framework.decorators import action

##from booking.models import *
##from carts.models import *
##from coupons.models import *
##from customer.models import *
##from holiday_package.models import *
##from hotel_managements.models import *
##from hotels.models import *
##from org_managements.models import *
##from org_resources.models import *
##from payment_gateways.models import *

from .serializers import (
    ORGMUserSerializer,
    BusinessDetailSerializer,
    BusinessDetailAdminSerializer,
)


class ORGMUserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = ORGMUserSerializer
    permission_classes = [
        IsAuthenticated,
        IsAdminUser,
    ]
    http_method_names = [
        "get",
    ]


class BusinessDetailViewSet(viewsets.ModelViewSet, StandardResponseMixin, LoggingMixin):
    queryset = BusinessDetail.objects.all()
    serializer_class = BusinessDetailSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "post", "put", "patch", "delete", "list"]

    def get_serializer_class(self):
        # Allow staff/superuser to create/edit BusinessDetail for any user.
        request = getattr(self, "request", None)
        if request and request.user and (request.user.is_staff or request.user.is_superuser):
            return BusinessDetailAdminSerializer
        return BusinessDetailSerializer

    def _sync_user_business_id(self, business_detail: BusinessDetail):
        """
        Keep User.business_id in sync with BusinessDetail.id for convenience,
        since parts of the system use User.business_id to resolve billed-by context.
        """
        try:
            user = business_detail.user
            if getattr(user, "business_id", None) != business_detail.id:
                user.business_id = business_detail.id
                user.save(update_fields=["business_id"])
        except Exception:
            # Avoid breaking CRUD on sync failures; model integrity remains.
            pass

    def _enforce_single_default(self, business_detail: BusinessDetail):
        # Ensure only one default business exists at a time.
        # If this instance is marked default, unset all others.
        if getattr(business_detail, "is_default", False):
            BusinessDetail.objects.exclude(id=business_detail.id).filter(is_default=True).update(
                is_default=False
            )

    def perform_create(self, serializer):
        instance = serializer.save()
        self._sync_user_business_id(instance)
        self._enforce_single_default(instance)

    def perform_update(self, serializer):
        instance = serializer.save()
        self._sync_user_business_id(instance)
        self._enforce_single_default(instance)

    def business_filter_ops(self):
        """Apply filtering operations for business details"""
        # Filter by default flag
        is_default = self.request.query_params.get("is_default", None)
        if is_default is not None:
            if is_default.lower() == "true":
                self.queryset = self.queryset.filter(is_default=True)
            elif is_default.lower() == "false":
                self.queryset = self.queryset.filter(is_default=False)

        # Filter by active status
        active = self.request.query_params.get("active", None)
        if active is not None:
            if active.lower() == "true":
                self.queryset = self.queryset.filter(active=True)
            elif active.lower() == "false":
                self.queryset = self.queryset.filter(active=False)

        # Filter by country
        country = self.request.query_params.get("country", None)
        if country:
            self.queryset = self.queryset.filter(country__icontains=country)

        # Filter by state
        state = self.request.query_params.get("state", None)
        if state:
            self.queryset = self.queryset.filter(state__icontains=state)

        # Filter by domain name
        domain = self.request.query_params.get("domain", None)
        if domain:
            self.queryset = self.queryset.filter(domain_name__icontains=domain)

        # Search functionality
        search = self.request.query_params.get("search", "")
        if search:
            search_q_filter = (
                Q(business_name__icontains=search)
                | Q(business_email__icontains=search)
                | Q(business_phone__icontains=search)
                | Q(domain_name__icontains=search)
                | Q(gstin_no__icontains=search)
                | Q(pan_no__icontains=search)
                | Q(hsn_sac_no__icontains=search)
                | Q(full_address__icontains=search)
            )
            self.queryset = self.queryset.filter(search_q_filter)

    def delete(self, request, *args, **kwargs):
        self.log_request(request)  # log the incoming request
        # Get the object to be deleted
        instance = self.get_object()
        instance.active = False
        instance.save()
        return self.get_response(
            status="success",
            data={},
            message="Business Details Deleted",
            status_code=status.HTTP_200_OK,
        )

    def list(self, request, *args, **kwargs):
        self.log_request(request)  # log the incoming request

        # Apply filtering operations
        self.business_filter_ops()

        # Apply ordering
        self.queryset = order_ops(request, self.queryset)

        # Apply pagination
        count, self.queryset = paginate_queryset(request, self.queryset)

        # Perform the default listing logic
        response = super().list(request, *args, **kwargs)

        if response.status_code == status.HTTP_200_OK:
            # If the response status code is OK (200), it's a successful listing
            custom_response = self.get_response(
                status="success",
                data=response.data,  # Use the data from the default response
                message="Business Details List Retrieved",
                count=count,
                status_code=status.HTTP_200_OK,  # 200 for successful listing
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
        methods=["get"],
        url_path="export-csv",
        permission_classes=[IsAuthenticated],
    )
    def export_csv(self, request):
        self.log_request(request)
        if not request.user.is_superuser:
            return Response(
                {"detail": "Only superusers can export data."},
                status=status.HTTP_403_FORBIDDEN,
            )
        self.queryset = BusinessDetail.objects.all()
        self.business_filter_ops()
        self.queryset = order_ops(request, self.queryset)
        queryset = self.queryset[:MAX_EXPORT_ROWS]
        serializer = self.get_serializer(queryset, many=True)
        return csv_http_response_from_records(
            serializer.data, "business-details-export.csv"
        )

    def create(self, request, *args, **kwargs):
        user_id = request.user.id
        self.log_request(request)  # log the incoming request
        # Create an instance of your serializer with the request data
        # serializer = self.get_serializer(data=request.data, context={'user_id': user_id})

        # TODO: Check user permission for business detail create
        # existing_detail = BusinessDetail.objects.filter(user=request.user)
        # if existing_detail:
        #     custom_response = self.get_error_response(message="Business deatil is already available", status="error",
        #                                        errors=[],error_code="VALIDATION_ERROR",
        #                                        status_code=status.HTTP_406_NOT_ACCEPTABLE)
        #     return custom_response

        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            self.perform_create(serializer)
            custom_response = self.get_response(
                status="success",
                data=serializer.data,
                message="Business Details Created",
                status_code=status.HTTP_201_CREATED,
            )
        else:
            custom_response = self.get_error_response(
                message="Validation error",
                status="error",
                errors=serializer.errors,
                error_code="VALIDATION_ERROR",
                status_code=status.HTTP_406_NOT_ACCEPTABLE,
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
            self.perform_update(serializer)
            custom_response = self.get_response(
                status="success",
                data=serializer.data,
                message="Business Details Updated",
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

    @action(
        detail=False,
        methods=["GET"],
        url_path="user/retrieve",
        url_name="user-retrieve",
    )
    def user_based_retrieve(self, request):
        try:
            business_detail = BusinessDetail.objects.get(user=request.user)
            serializer = BusinessDetailSerializer(business_detail)
            custom_response = self.get_response(
                status="success", data=serializer.data, status_code=status.HTTP_200_OK
            )
        except Exception as e:
            print(e)
            # self.log_response(e)
            custom_response = self.get_response(
                data={},
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        return custom_response

    @action(detail=False, methods=["GET"], url_path="active", url_name="active")
    def active_business(self, request):
        try:
            business_detail = BusinessDetail.objects.filter(active=True)
            serializer = BusinessDetailSerializer(business_detail, many=True)
            custom_response = self.get_response(
                status="success", data=serializer.data, status_code=status.HTTP_200_OK
            )
        except Exception as e:
            print(e)
            # self.log_response(e)
            custom_response = self.get_response(
                data={},
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        return custom_response
