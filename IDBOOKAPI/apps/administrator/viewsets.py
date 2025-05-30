from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404, Http404
from django.http import JsonResponse
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import viewsets
from rest_framework import status
from rest_framework.decorators import permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated, IsAdminUser
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.generics import (
    CreateAPIView, ListAPIView, GenericAPIView, RetrieveAPIView, UpdateAPIView
)
from IDBOOKAPI.mixins import StandardResponseMixin, LoggingMixin
from IDBOOKAPI.permissions import HasRoleModelPermission
from apps.authentication.models import User, Role
# from booking.models import *
# from carts.models import *
# from coupons.models import *
# from customer.models import *
# from holiday_package.models import *
# from hotel_managements.models import *
# from hotels.models import *
# from org_managements.models import *
# from apps.org_resources.models import *
# from payment_gateways.models import *

from apps.authentication.utils import db_utils
from IDBOOKAPI.utils import paginate_queryset

from .models import available_permission_queryset
from .serializers import UserSerializer, RoleSerializer, PermissionSerializer, UserAdminListSerializer
from apps.org_resources.serializers import CompanyDetailSerializer
from apps.org_resources.models import CompanyDetail
from rest_framework.decorators import action

class UserViewSet(viewsets.ModelViewSet, StandardResponseMixin, LoggingMixin):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    # permission_classes = [HasRoleModelPermission]
    permission_classes = [IsAuthenticated]
    http_method_names = ['get', 'post', 'put', 'patch']
    # lookup_field = 'mobile_number'

    action_serializers = {
        'retrieve': UserAdminListSerializer,
        'list': UserAdminListSerializer,
        'create': UserSerializer,
        'update': UserSerializer
    }

    def get_serializer_class(self):
        if hasattr(self, 'action_serializers'):
            return self.action_serializers.get(self.action, self.serializer_class)

        return super(UserViewSet, self).get_serializer_class()

    def get_object(self):
        queryset = self.get_queryset()
        queryset = self.filter_queryset(queryset)
        mobile_number = self.kwargs.get(self.lookup_field)
        obj = get_object_or_404(queryset, **{self.lookup_field: mobile_number})
        self.check_object_permissions(self.request, obj)
        return obj

    def create(self, request, *args, **kwargs):
        self.log_request(request)  # Log the incoming request
        if not self.request.user.is_staff:
            response = self.get_response(message='You do not have permission to create an admin user.',
                                     status_code=status.HTTP_403_FORBIDDEN, is_error=True)
            self.log_response(response)  # Log the response before returning
            return response

        serializer = self.get_serializer(data=request.data)

        if serializer.is_valid():
            user = serializer.save()
            refresh = RefreshToken.for_user(user)
            token = {
                'refresh': str(refresh),
                'access': str(refresh.access_token)
            }

            response = self.get_response(
                data=[serializer.data, token],
                message="User Created",
                status_code=status.HTTP_200_OK,
                )
            self.log_response(response)  # Log the response before returning
            return response
        else:
            errors = serializer.errors
            data = {
                "password": errors.get('password', [])[0] if 'password' in errors else "",
                "mobile_number": errors.get('mobile_number', [])[0] if 'mobile_number' in errors else "",
                "roles": errors.get('roles', []) if 'roles' in errors else ""
            }
            response = self.get_response(
                data=[serializer.data],
                message=data,
                status_code=status.HTTP_401_UNAUTHORIZED,
                is_error=True)
            self.log_response(response)  # Log the response before returning
            return response

    def update(self, request, *args, **kwargs):
        self.log_request(request)  # Log the incoming request
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)

        if serializer.is_valid():
            self.perform_update(serializer)
            response = self.get_response(
                data=[serializer.data],
                message="User data update successfully",
                status_code=status.HTTP_200_OK,
                )
            self.log_response(response)  # Log the response before returning
            return response
        else:
            errors = serializer.errors
            response = self.get_response(
                data=[serializer.data],
                message=errors,
                status_code=status.HTTP_401_UNAUTHORIZED,
                is_error=True)
            self.log_response(response)  # Log the response before returning
            return response

    def list(self, request, *args, **kwargs):
        self.log_request(request)  # Log the incoming request
        user = request.user
        company_id = request.query_params.get('company_id', None)
##        company_id = user.company_id
##        category = request.GET.get('category', '')
##        if category:
##            if category == 'CL-CUST' and company_id:
##                self.queryset = self.queryset.filter(category=category, company_id=company_id)
##            else:
##                self.queryset = self.queryset.filter(category=category)

        role_name = request.query_params.get('role', '')
        name = request.query_params.get('name', '').strip()
        email = request.query_params.get('email', '').strip()

        if name:
            self.queryset = self.queryset.filter(name__icontains=name)

        if email:
            self.queryset = self.queryset.filter(email__icontains=email)

        if role_name:
            role = db_utils.get_role_by_name(role_name)
            self.queryset = self.queryset.filter(roles__in=[role])

        if company_id:
            self.queryset = self.queryset.filter(company_id=company_id)

        self.queryset = self.queryset.order_by('-created')
        count, self.queryset = paginate_queryset(self.request,  self.queryset)

        # Perform the default listing logic
        response = super().list(request, *args, **kwargs)

        if response.status_code == status.HTTP_200_OK:
            # If the response status code is OK (200), it's a successful listing
            custom_response = self.get_response(
                count=count, status="success",
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

    @action(detail=False, methods=['get'], url_path='users-company-details',
        url_name='users-company-details', permission_classes=[IsAuthenticated])
    def users_company_details(self, request):
        self.log_request(request)

        # Get the authenticated user
        user = request.user

        # User filters
        role_name = request.query_params.get('role', '')
        name = request.query_params.get('name', '').strip()
        email = request.query_params.get('email', '').strip()
        company_id = request.query_params.get('company_id', None)
        # Filter user queryset based on name, email, and role
        user_queryset = self.filter_queryset(self.get_queryset().order_by('-created'))

        if name:
            user_queryset = user_queryset.filter(name__icontains=name)

        if email:
            user_queryset = user_queryset.filter(email__icontains=email)

        if role_name:
            role = db_utils.get_role_by_name(role_name)
            user_queryset = user_queryset.filter(roles__in=[role])

        if company_id:
            user_queryset = user_queryset.filter(company_id=company_id)

        # Apply pagination to user queryset
        user_count, user_queryset = paginate_queryset(request, user_queryset)
        user_serializer = UserAdminListSerializer(user_queryset, many=True)

        # Company filters
        company_queryset = CompanyDetail.objects.all().order_by('-id')

        company_is_active = request.query_params.get('company_is_active', None)
        company_phone = request.query_params.get('company_phone', '').strip()
        company_email = request.query_params.get('company_email', '').strip()

        # Apply company filters
        if name:
            company_queryset = company_queryset.filter(company_name__icontains=name)
        
        if company_phone:
            company_queryset = company_queryset.filter(company_phone__icontains=company_phone)
        
        if company_email:
            company_queryset = company_queryset.filter(company_email__icontains=company_email)
        
        if company_is_active is not None:
            company_is_active = company_is_active.lower() == 'true'
            company_queryset = company_queryset.filter(is_active=company_is_active)

        if company_id:
            company_queryset = company_queryset.filter(id=company_id)

        # Apply pagination to company queryset
        company_count, company_queryset = paginate_queryset(request, company_queryset)
        company_serializer = CompanyDetailSerializer(company_queryset, many=True)

        data = {
            "users_details": user_serializer.data,
            "company_details": company_serializer.data
        }

        # Return the response with user and company details
        return self.get_response(
            count=user_count+company_count,
            status="success",
            data=data,
            message="Users and Company Details Retrieved",
            status_code=status.HTTP_200_OK
        )


class RoleViewSet(viewsets.ModelViewSet, StandardResponseMixin, LoggingMixin):
    queryset = Role.objects.all()
    serializer_class = RoleSerializer
    permission_classes = [HasRoleModelPermission]
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

class PermissionViewSet(viewsets.ModelViewSet, StandardResponseMixin, LoggingMixin):
    queryset = available_permission_queryset

    serializer_class = PermissionSerializer
    permission_classes = [HasRoleModelPermission]
    http_method_names = ['get', ]

    def list(self, request, *args, **kwargs):
        self.log_request(request)  # Log the incoming request
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)
        ids_list = [item['id'] for item in serializer.data]

        response = self.get_response(
            data={"permissions_ids": sorted(ids_list), "permissions": serializer.data},
            message="permissions",
            status_code=status.HTTP_200_OK,
            )
        self.log_response(response)  # Log the response before returning
        return response

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


#
# @permission_classes([IsAdminUser])
class UserRolesAndPermissionsAPIView(APIView, StandardResponseMixin, LoggingMixin):
    queryset = User.objects.all()  # for HasRoleModelPermission
    permission_classes = [HasRoleModelPermission]
    """
    get user roles and permissions
    """
    def get(self, request, mobile_number):
        self.log_request(request)  # Log the incoming request
        try:
            user = User.objects.get(mobile_number=mobile_number)
        except User.DoesNotExist:
            response = self.get_response(
                message="User not found.",
                status_code=status.HTTP_404_NOT_FOUND,
                is_error=True)
            self.log_response(response)  # Log the response before returning
            return response

        roles = user.roles.all()

        group_data = []
        for role in roles:
            permissions = role.permissions.all()
            permission_names = [permission.name for permission in permissions]
            group_data.append({
                "user": {
                    "custom_id": user.custom_id,
                    "mobile_number": user.mobile_number,
                    "category": user.category,
                    "is_active": user.is_active
                },
                "roles_and_permissions": {
                    "id": role.id,
                    "name": role.name,
                    "short_code": role.short_code,
                    "permissions": permission_names
                }

            })
        response = self.get_response(
            data=group_data,
            message="roles and permissions",
            status_code=status.HTTP_200_OK,
            )
        self.log_response(response)  # Log the response before returning
        return response

