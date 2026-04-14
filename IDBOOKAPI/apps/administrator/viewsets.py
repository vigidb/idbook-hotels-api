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
    CreateAPIView,
    ListAPIView,
    GenericAPIView,
    RetrieveAPIView,
    UpdateAPIView,
)
from IDBOOKAPI.mixins import StandardResponseMixin, LoggingMixin
from IDBOOKAPI.permissions import HasRoleModelPermission, IsSuperUserOrHasRolePermission
from apps.authentication.models import (
    User,
    Role,
    UserRole,
)
from apps.org_managements.models import BusinessDetail

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
from IDBOOKAPI.utils import paginate_queryset, order_ops
from IDBOOKAPI.csv_export import csv_http_response_from_records, MAX_EXPORT_ROWS
from django.db.models import Q
from django.contrib.auth.models import Group, Permission

from .models import available_permission_queryset
from .serializers import (
    UserSerializer,
    RoleSerializer,
    PermissionSerializer,
    UserAdminListSerializer,
    UserRoleSerializer,
    GroupSerializer,
)
from apps.org_resources.serializers import CompanyDetailSerializer
from apps.org_resources.serializers import AgentDetailSerializer
from apps.org_resources.models import CompanyDetail, AgentDetail
from apps.hotels.models import Property
from rest_framework.decorators import action


class UserViewSet(viewsets.ModelViewSet, StandardResponseMixin, LoggingMixin):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    # permission_classes = [HasRoleModelPermission]
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "post", "put", "patch"]
    # lookup_field = 'mobile_number'

    action_serializers = {
        "retrieve": UserAdminListSerializer,
        "list": UserAdminListSerializer,
        "create": UserSerializer,
        "update": UserSerializer,
    }

    def get_serializer_class(self):
        if hasattr(self, "action_serializers"):
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
            response = self.get_response(
                message="You do not have permission to create an admin user.",
                status_code=status.HTTP_403_FORBIDDEN,
                is_error=True,
            )
            self.log_response(response)  # Log the response before returning
            return response

        serializer = self.get_serializer(data=request.data)

        if serializer.is_valid():
            user = serializer.save()
            refresh = RefreshToken.for_user(user)
            token = {"refresh": str(refresh), "access": str(refresh.access_token)}

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
                "password": (
                    errors.get("password", [])[0] if "password" in errors else ""
                ),
                "mobile_number": (
                    errors.get("mobile_number", [])[0]
                    if "mobile_number" in errors
                    else ""
                ),
                "roles": errors.get("roles", []) if "roles" in errors else "",
            }
            response = self.get_response(
                data=[serializer.data],
                message=data,
                status_code=status.HTTP_401_UNAUTHORIZED,
                is_error=True,
            )
            self.log_response(response)  # Log the response before returning
            return response

    def update(self, request, *args, **kwargs):
        self.log_request(request)  # Log the incoming request
        partial = kwargs.pop("partial", False)
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
                is_error=True,
            )
            self.log_response(response)  # Log the response before returning
            return response

    def _filter_users_for_list(self, request, queryset):
        """Apply the same query-param filters as list (excluding pagination)."""
        # ========== SEARCH FUNCTIONALITY (SOLID Search) ==========
        # Single search parameter that searches across multiple fields
        search = request.query_params.get("search", "").strip()
        if search:
            # Try to parse as integer for ID search
            try:
                search_id = int(search)
                queryset = queryset.filter(
                    Q(id=search_id) |
                    Q(email__icontains=search) |
                    Q(name__icontains=search) |
                    Q(mobile_number__icontains=search) |
                    Q(custom_id__icontains=search) |
                    Q(first_name__icontains=search) |
                    Q(last_name__icontains=search) |
                    Q(referral__icontains=search) |
                    Q(referred_code__icontains=search)
                )
            except ValueError:
                # If not a number, search in text fields only
                queryset = queryset.filter(
                    Q(email__icontains=search) |
                    Q(name__icontains=search) |
                    Q(mobile_number__icontains=search) |
                    Q(custom_id__icontains=search) |
                    Q(first_name__icontains=search) |
                    Q(last_name__icontains=search) |
                    Q(referral__icontains=search) |
                    Q(referred_code__icontains=search)
                )
        
        # ========== INDIVIDUAL FIELD FILTERS (for backward compatibility) ==========
        name = request.query_params.get("name", "").strip()
        if name:
            queryset = queryset.filter(name__icontains=name)
        
        email = request.query_params.get("email", "").strip()
        if email:
            queryset = queryset.filter(email__icontains=email)
        
        mobile_number = request.query_params.get("mobile_number", "").strip()
        if mobile_number:
            queryset = queryset.filter(mobile_number__icontains=mobile_number)
        
        user_id = request.query_params.get("id", None)
        if user_id:
            try:
                user_id = int(user_id)
                queryset = queryset.filter(id=user_id)
            except (ValueError, TypeError):
                pass
        
        custom_id = request.query_params.get("custom_id", "").strip()
        if custom_id:
            queryset = queryset.filter(custom_id__icontains=custom_id)
        
        # ========== FILTER OPTIONS ==========
        # Role filter
        role_name = request.query_params.get("role", "").strip()
        if role_name:
            role = db_utils.get_role_by_name(role_name)
            if role:
                queryset = queryset.filter(roles__in=[role])
        
        # Group filter
        group_name = request.query_params.get("group", "").strip()
        if group_name:
            group = db_utils.get_group_by_name(group_name)
            if group:
                queryset = queryset.filter(groups__in=[group])
        
        # Company filter
        company_id = request.query_params.get("company_id", None)
        if company_id:
            try:
                company_id = int(company_id)
                queryset = queryset.filter(company_id=company_id)
            except (ValueError, TypeError):
                pass
        
        # Business filter
        business_id = request.query_params.get("business_id", None)
        if business_id:
            try:
                business_id = int(business_id)
                queryset = queryset.filter(business_id=business_id)
            except (ValueError, TypeError):
                pass
        
        # Category filter
        category = request.query_params.get("category", "").strip()
        if category:
            queryset = queryset.filter(category__icontains=category)
        
        # Default group filter
        default_group = request.query_params.get("default_group", "").strip()
        if default_group:
            queryset = queryset.filter(default_group=default_group)
        
        # Boolean filters
        is_active = request.query_params.get("is_active", None)
        if is_active is not None:
            is_active = is_active.lower() in ("true", "1", "yes")
            queryset = queryset.filter(is_active=is_active)
        
        is_staff = request.query_params.get("is_staff", None)
        if is_staff is not None:
            is_staff = is_staff.lower() in ("true", "1", "yes")
            queryset = queryset.filter(is_staff=is_staff)
        
        email_verified = request.query_params.get("email_verified", None)
        if email_verified is not None:
            email_verified = email_verified.lower() in ("true", "1", "yes")
            queryset = queryset.filter(email_verified=email_verified)
        
        mobile_verified = request.query_params.get("mobile_verified", None)
        if mobile_verified is not None:
            mobile_verified = mobile_verified.lower() in ("true", "1", "yes")
            queryset = queryset.filter(mobile_verified=mobile_verified)
        
        first_booking = request.query_params.get("first_booking", None)
        if first_booking is not None:
            first_booking = first_booking.lower() in ("true", "1", "yes")
            queryset = queryset.filter(first_booking=first_booking)
        
        # Date range filters
        created_from = request.query_params.get("created_from", None)
        if created_from:
            try:
                from datetime import datetime
                created_from = datetime.strptime(created_from, "%Y-%m-%d")
                queryset = queryset.filter(created__gte=created_from)
            except (ValueError, TypeError):
                pass
        
        created_to = request.query_params.get("created_to", None)
        if created_to:
            try:
                from datetime import datetime
                created_to = datetime.strptime(created_to, "%Y-%m-%d")
                queryset = queryset.filter(created__lte=created_to)
            except (ValueError, TypeError):
                pass
        
        # ========== SORT/ORDERING ==========
        ordering = request.query_params.get("ordering", None)
        if ordering:
            # Use the order_ops utility function
            queryset = order_ops(request, queryset)
        else:
            # Default ordering by created date (newest first)
            queryset = queryset.order_by("-created")
        
        # Remove duplicates that may occur from ManyToMany relationships
        return queryset.distinct()

    def list(self, request, *args, **kwargs):
        self.log_request(request)  # Log the incoming request
        queryset = self._filter_users_for_list(request, self.get_queryset())

        # ========== PAGINATION ==========
        count, queryset = paginate_queryset(self.request, queryset)

        # Set queryset for serializer
        self.queryset = queryset

        # Perform the default listing logic
        response = super().list(request, *args, **kwargs)

        if response.status_code == status.HTTP_200_OK:
            # If the response status code is OK (200), it's a successful listing
            custom_response = self.get_response(
                count=count,
                status="success",
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
        queryset = self._filter_users_for_list(request, self.get_queryset())[
            :MAX_EXPORT_ROWS
        ]
        serializer = UserAdminListSerializer(queryset, many=True)
        return csv_http_response_from_records(serializer.data, "users-export.csv")

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

    @action(detail=True, methods=["post", "put", "patch"], url_path="groups")
    def manage_groups(self, request, pk=None):
        """Assign or remove groups from a user"""
        self.log_request(request)
        
        user = self.get_object()
        group_ids = request.data.get("groups", [])
        action = request.data.get("action", "set")  # "set", "add", or "remove"
        
        if not isinstance(group_ids, list):
            response = self.get_response(
                data=None,
                message="Groups must be a list of group IDs",
                status_code=status.HTTP_400_BAD_REQUEST,
                is_error=True,
            )
            self.log_response(response)
            return response
        
        # Validate group IDs exist
        groups = Group.objects.filter(id__in=group_ids)
        if groups.count() != len(group_ids):
            invalid_ids = set(group_ids) - set(groups.values_list("id", flat=True))
            response = self.get_response(
                data={"invalid_group_ids": list(invalid_ids)},
                message=f"Invalid group IDs: {list(invalid_ids)}",
                status_code=status.HTTP_400_BAD_REQUEST,
                is_error=True,
            )
            self.log_response(response)
            return response
        
        # Perform the action
        if action == "set":
            # Replace all groups
            user.groups.set(groups)
            message = "User groups updated successfully"
        elif action == "add":
            # Add groups (keep existing)
            user.groups.add(*groups)
            message = "Groups added to user successfully"
        elif action == "remove":
            # Remove groups
            user.groups.remove(*groups)
            message = "Groups removed from user successfully"
        else:
            response = self.get_response(
                data=None,
                message="Invalid action. Use 'set', 'add', or 'remove'",
                status_code=status.HTTP_400_BAD_REQUEST,
                is_error=True,
            )
            self.log_response(response)
            return response
        
        # Get updated user data
        serializer = UserAdminListSerializer(user)
        response = self.get_response(
            data=serializer.data,
            message=message,
            status_code=status.HTTP_200_OK,
        )
        self.log_response(response)
        return response

    @action(
        detail=False,
        methods=["get"],
        url_path="users-company-details",
        url_name="users-company-details",
        permission_classes=[IsAuthenticated],
    )
    def users_company_details(self, request):
        self.log_request(request)

        # Get the authenticated user
        user = request.user

        client_type = request.query_params.get("client_type", "all").strip().lower()
        search = request.query_params.get("search", "").strip()

        # User filters
        role_name = request.query_params.get("role", "")
        name = request.query_params.get("name", "").strip()
        email = request.query_params.get("email", "").strip()
        company_id = request.query_params.get("company_id", None)
        # Filter user queryset based on name, email, and role
        user_queryset = self.filter_queryset(self.get_queryset().order_by("-created"))

        if search:
            user_queryset = user_queryset.filter(
                Q(name__icontains=search)
                | Q(email__icontains=search)
                | Q(mobile_number__icontains=search)
            )
        elif name:
            user_queryset = user_queryset.filter(name__icontains=name)

        if email:
            user_queryset = user_queryset.filter(email__icontains=email)

        if role_name:
            role = db_utils.get_role_by_name(role_name)
            user_queryset = user_queryset.filter(roles__in=[role])

        if company_id:
            user_queryset = user_queryset.filter(company_id=company_id)

        # IMPORTANT: For invoice client search UI:
        # - corporate => ONLY company entities (no corporate users)
        # - agent => ONLY agent entities (no agent users)
        # - b2c => ONLY b2c users
        if client_type in ("corporate", "agent"):
            user_count, user_serializer = 0, UserAdminListSerializer([], many=True)
        else:
            if client_type == "b2c":
                group = db_utils.get_group_by_name("B2C-GRP")
                if group:
                    user_queryset = user_queryset.filter(groups__in=[group])

            # Apply pagination to user queryset
            user_count, user_queryset = paginate_queryset(request, user_queryset)
            user_serializer = UserAdminListSerializer(user_queryset, many=True)

        # Company filters
        company_queryset = CompanyDetail.objects.all().order_by("-id")
        agent_queryset = AgentDetail.objects.all().order_by("-id")
        property_queryset = Property.objects.all().order_by("-id")

        company_is_active = request.query_params.get("company_is_active", None)
        company_phone = request.query_params.get("company_phone", "").strip()
        company_email = request.query_params.get("company_email", "").strip()

        # Apply company/agent/property filters (shared search)
        if search:
            company_queryset = company_queryset.filter(
                Q(company_name__icontains=search)
                | Q(company_email__icontains=search)
                | Q(company_phone__icontains=search)
            )
            agent_queryset = agent_queryset.filter(
                Q(agent_name__icontains=search)
                | Q(agent_email__icontains=search)
                | Q(contact_email_address__icontains=search)
                | Q(agent_phone__icontains=search)
                | Q(contact_number__icontains=search)
            )
            property_queryset = property_queryset.filter(
                Q(name__icontains=search)
                | Q(email__icontains=search)
                | Q(phone_no__icontains=search)
                | Q(customer_care_no__icontains=search)
            )
        elif name:
            company_queryset = company_queryset.filter(company_name__icontains=name)
            agent_queryset = agent_queryset.filter(agent_name__icontains=name)
            property_queryset = property_queryset.filter(name__icontains=name)

        if company_phone:
            company_queryset = company_queryset.filter(
                company_phone__icontains=company_phone
            )

        if company_email:
            company_queryset = company_queryset.filter(
                company_email__icontains=company_email
            )

        if company_is_active is not None:
            company_is_active = company_is_active.lower() == "true"
            company_queryset = company_queryset.filter(is_active=company_is_active)

        if company_id:
            company_queryset = company_queryset.filter(id=company_id)

        # Apply client_type scoping for entity lists
        include_companies = client_type in ("all", "corporate")
        include_agents = client_type in ("all", "agent")
        include_properties = False

        company_count, company_serializer = 0, []
        agent_count, agent_serializer = 0, []
        property_count, property_serializer = 0, []

        if include_companies:
            company_count, company_queryset = paginate_queryset(request, company_queryset)
            company_serializer = CompanyDetailSerializer(company_queryset, many=True).data

        if include_agents:
            agent_count, agent_queryset = paginate_queryset(request, agent_queryset)
            agent_serializer = AgentDetailSerializer(agent_queryset, many=True).data

        # Hotels are not invoice clients anymore

        data = {
            "users_details": user_serializer.data,
            "company_details": company_serializer,
            "agent_details": agent_serializer,
            "property_details": [],
        }

        # Return the response with user and company details
        return self.get_response(
            count=user_count + company_count + agent_count,
            status="success",
            data=data,
            message="Users and Company Details Retrieved",
            status_code=status.HTTP_200_OK,
        )


class RoleViewSet(viewsets.ModelViewSet, StandardResponseMixin, LoggingMixin):
    queryset = Role.objects.all()
    serializer_class = RoleSerializer
    permission_classes = [HasRoleModelPermission]
    http_method_names = ["get", "post", "put", "patch", "delete"]

    def get_object(self):
        """Override to prevent non-superusers from accessing system roles"""
        instance = super().get_object()
        
        # Non-superusers cannot access system roles (except for read-only GET)
        if instance.is_system_role and not self.request.user.is_superuser:
            # Allow GET requests (read-only access)
            if self.request.method == "GET":
                return instance
            # Block all other operations
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Only superusers can modify system roles.")
        
        return instance

    def get_queryset(self):
        """Filter roles by business_id if provided"""
        queryset = super().get_queryset()
        business_id = self.request.query_params.get("business_id")
        
        if business_id:
            try:
                business = BusinessDetail.objects.get(id=business_id)
                queryset = queryset.filter(business=business)
            except (BusinessDetail.DoesNotExist, ValueError):
                pass
        
        # Non-superusers can only see non-system roles
        if not self.request.user.is_superuser:
            queryset = queryset.filter(is_system_role=False)
        else:
            # Superusers can filter system roles if requested
            is_system = self.request.query_params.get("is_system_role")
            if is_system is not None:
                is_system_bool = is_system.lower() == "true"
                queryset = queryset.filter(is_system_role=is_system_bool)
        
        return queryset.select_related("business", "group").prefetch_related("permissions")

    def create(self, request, *args, **kwargs):
        self.log_request(request)  # Log the incoming request

        # Check if user is trying to create a system role
        is_system_role = request.data.get("is_system_role", False)
        if is_system_role and not request.user.is_superuser:
            response = self.get_response(
                data=None,
                message="Only superusers can create system roles. Please set is_system_role to false or contact a superuser.",
                status_code=status.HTTP_403_FORBIDDEN,
                is_error=True,
            )
            self.log_response(response)
            return response

        # Check for duplicate roles (especially for system roles)
        name = request.data.get("name")
        business_id = request.data.get("business")
        
        # For system roles, check if a role with the same name and is_system_role=True already exists
        if is_system_role:
            existing_role = Role.objects.filter(
                name=name,
                is_system_role=True,
                business__isnull=True
            ).first()
            if existing_role:
                response = self.get_response(
                    data={"existing_role_id": existing_role.id},
                    message=f"System role '{name}' already exists (ID: {existing_role.id}). Please use the existing role or update it.",
                    status_code=status.HTTP_400_BAD_REQUEST,
                    is_error=True,
                )
                self.log_response(response)
                return response
        else:
            # For non-system roles, check if role with same name and business exists
            if business_id:
                existing_role = Role.objects.filter(
                    name=name,
                    business_id=business_id,
                    is_system_role=False
                ).first()
                if existing_role:
                    response = self.get_response(
                        data={"existing_role_id": existing_role.id},
                        message=f"Role '{name}' already exists for this business (ID: {existing_role.id}). Please use the existing role or update it.",
                        status_code=status.HTTP_400_BAD_REQUEST,
                        is_error=True,
                    )
                    self.log_response(response)
                    return response

        # Extract permissions from request data
        permission_ids = request.data.get("permissions", [])
        if not isinstance(permission_ids, list):
            permission_ids = []

        # Create an instance of your serializer with the request data
        serializer = self.get_serializer(data=request.data)

        if serializer.is_valid():
            # Ensure non-superusers cannot create system roles even if they try to bypass
            if not request.user.is_superuser:
                serializer.validated_data['is_system_role'] = False
            
            # If the serializer is valid, perform the default creation logic
            role = serializer.save()

            # Handle permissions if provided
            if permission_ids:
                from django.contrib.auth.models import Permission
                
                # Convert permission IDs to integers
                permission_ids_int = []
                for pid in permission_ids:
                    try:
                        permission_ids_int.append(int(pid))
                    except (ValueError, TypeError):
                        continue
                
                # Check if permissions exist in the database
                existing_permissions = Permission.objects.filter(id__in=permission_ids_int)
                existing_permission_ids = list(existing_permissions.values_list("id", flat=True))
                
                # Set permissions if we have valid ones
                if existing_permission_ids:
                    role.permissions.set(existing_permission_ids)
                    # Refresh the role to get updated permissions
                    role.refresh_from_db()

            # Create a custom response
            custom_response = self.get_response(
                data=self.get_serializer(role).data,  # Use the serializer to get updated data
                message="Role Created",
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

        # Check if non-superuser is trying to modify a system role
        if instance.is_system_role and not request.user.is_superuser:
            response = self.get_response(
                data=None,
                message="Only superusers can modify system roles. This role is protected.",
                status_code=status.HTTP_403_FORBIDDEN,
                is_error=True,
            )
            self.log_response(response)
            return response

        # Check if user is trying to change a non-system role to system role
        is_system_role = request.data.get("is_system_role")
        if is_system_role and not request.user.is_superuser:
            response = self.get_response(
                data=None,
                message="Only superusers can create or modify system roles. Please set is_system_role to false or contact a superuser.",
                status_code=status.HTTP_403_FORBIDDEN,
                is_error=True,
            )
            self.log_response(response)
            return response

        # Extract permissions from request data
        permission_ids = request.data.get("permissions", None)
        if permission_ids is not None and not isinstance(permission_ids, list):
            permission_ids = None

        # Create an instance of your serializer with the request data and the object to be updated
        serializer = self.get_serializer(instance, data=request.data, partial=kwargs.get('partial', False))

        if serializer.is_valid():
            # Ensure non-superusers cannot set is_system_role to True
            if not request.user.is_superuser:
                serializer.validated_data['is_system_role'] = False
            
            # If the serializer is valid, save the role
            role = serializer.save()

            # Handle permissions if provided
            if permission_ids is not None:
                from django.contrib.auth.models import Permission
                
                # Convert permission IDs to integers
                permission_ids_int = []
                for pid in permission_ids:
                    try:
                        permission_ids_int.append(int(pid))
                    except (ValueError, TypeError):
                        continue
                
                # Check if permissions exist in the database
                existing_permissions = Permission.objects.filter(id__in=permission_ids_int)
                existing_permission_ids = list(existing_permissions.values_list("id", flat=True))
                
                # Set permissions if we have valid ones
                if existing_permission_ids:
                    role.permissions.set(existing_permission_ids)
                    # Refresh the role to get updated permissions
                    role.refresh_from_db()

            # Create a custom response
            custom_response = self.get_response(
                data=self.get_serializer(role).data,  # Use the serializer to get updated data
                message="Role Updated",
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
                is_error=True,
            )

        self.log_response(custom_response)  # Log the custom response before returning
        return custom_response

    def retrieve(self, request, *args, **kwargs):
        self.log_request(request)  # Log the incoming request

        # Get the object first to check if it's a system role
        instance = self.get_object()
        
        # Non-superusers cannot view system roles
        if instance.is_system_role and not request.user.is_superuser:
            response = self.get_response(
                data=None,
                message="Only superusers can view system roles. This role is protected.",
                status_code=status.HTTP_403_FORBIDDEN,
                is_error=True,
            )
            self.log_response(response)
            return response

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

    def destroy(self, request, *args, **kwargs):
        """Delete a role"""
        self.log_request(request)
        
        instance = self.get_object()
        
        # Check if role is a system role - only superusers can delete system roles
        if instance.is_system_role:
            if not request.user.is_superuser:
                response = self.get_response(
                    data=None,
                    message="Only superusers can delete system roles. This role is protected.",
                    status_code=status.HTTP_403_FORBIDDEN,
                    is_error=True,
                )
                self.log_response(response)
                return response
            # Superusers can delete system roles (with warning)
            # You might want to add additional confirmation for system role deletion
        
        # Check if role has any user assignments
        user_assignments_count = instance.user_roles.count()
        if user_assignments_count > 0:
            response = self.get_response(
                data={"user_assignments_count": user_assignments_count},
                message=f"Cannot delete role. It has {user_assignments_count} user assignment(s). Please remove all assignments first.",
                status_code=status.HTTP_400_BAD_REQUEST,
                is_error=True,
            )
            self.log_response(response)
            return response
        
        # Delete the role
        role_id = instance.id
        role_name = instance.name
        instance.delete()
        
        response = self.get_response(
            data={"id": role_id, "name": role_name},
            message="Role deleted successfully",
            status_code=status.HTTP_200_OK,
        )
        self.log_response(response)
        return response

    @action(detail=True, methods=["post"], url_path="clone", url_name="role-clone")
    def clone(self, request, pk=None):
        """Clone a role to another business"""
        self.log_request(request)
        role = self.get_object()
        
        # Non-superusers cannot clone system roles
        if role.is_system_role and not request.user.is_superuser:
            response = self.get_response(
                data=None,
                message="Only superusers can clone system roles.",
                status_code=status.HTTP_403_FORBIDDEN,
                is_error=True,
            )
            self.log_response(response)
            return response
        
        target_business_id = request.data.get("business_id")
        if not target_business_id:
            response = self.get_response(
                data=None,
                message="business_id is required",
                status_code=status.HTTP_400_BAD_REQUEST,
                is_error=True,
            )
            self.log_response(response)
            return response
        
        try:
            target_business = BusinessDetail.objects.get(id=target_business_id)
        except BusinessDetail.DoesNotExist:
            response = self.get_response(
                data=None,
                message="Business not found",
                status_code=status.HTTP_404_NOT_FOUND,
                is_error=True,
            )
            self.log_response(response)
            return response
        
        # Get permissions from request or use original role's permissions
        permission_ids = request.data.get("permissions", None)
        
        # Create cloned role
        cloned_role = Role.objects.create(
            name=role.name,
            short_code=role.short_code,
            business=target_business,
            group=role.group,
            is_system_role=False,
            description=role.description,
        )
        
        # Set permissions - use provided permissions or copy from original role
        if permission_ids and isinstance(permission_ids, list):
            # Filter to only available permissions
            from django.contrib.auth.models import Permission
            from .models import available_permission_queryset
            
            # Convert permission IDs to integers
            permission_ids_int = [int(pid) for pid in permission_ids if str(pid).isdigit()]
            
            # Get available permission IDs as a list
            available_ids = list(available_permission_queryset.values_list("id", flat=True))
            
            # Filter to only valid permissions that exist and are available
            valid_permission_ids = [
                pid for pid in permission_ids_int 
                if pid in available_ids
            ]
            
            if valid_permission_ids:
                cloned_role.permissions.set(valid_permission_ids)
        else:
            # Copy permissions from original role
            cloned_role.permissions.set(role.permissions.all())
        
        serializer = self.get_serializer(cloned_role)
        response = self.get_response(
            data=serializer.data,
            message="Role cloned successfully",
            status_code=status.HTTP_201_CREATED,
        )
        self.log_response(response)
        return response

    @action(detail=True, methods=["get", "put"], url_path="permissions", url_name="role-permissions")
    def permissions(self, request, pk=None):
        """Get or update role permissions"""
        self.log_request(request)
        role = self.get_object()
        
        # Non-superusers cannot modify system role permissions
        if request.method == "PUT" and role.is_system_role and not request.user.is_superuser:
            response = self.get_response(
                data=None,
                message="Only superusers can modify system role permissions.",
                status_code=status.HTTP_403_FORBIDDEN,
                is_error=True,
            )
            self.log_response(response)
            return response
        
        if request.method == "GET":
            from apps.authentication.utils.permission_utils import get_permission_code
            
            permissions = role.permissions.all()
            permission_data = [
                {
                    "id": perm.id,
                    "name": perm.name,
                    "codename": perm.codename,
                    "permission_code": get_permission_code(perm),
                    "content_type": perm.content_type.app_label + "." + perm.content_type.model,
                    "description": perm.name or f"Permission to {perm.codename.replace('_', ' ')}",
                    "module": perm.codename.split('_', 1)[1] if '_' in perm.codename else perm.content_type.app_label,
                }
                for perm in permissions
            ]
            response = self.get_response(
                data={
                    "role_id": role.id,
                    "role_name": role.name,
                    "role_description": role.description,
                    "permissions": permission_data,
                },
                message="Role permissions retrieved",
                status_code=status.HTTP_200_OK,
            )
            self.log_response(response)
            return response
        
        elif request.method == "PUT":
            permission_ids = request.data.get("permission_ids", [])
            if not isinstance(permission_ids, list):
                response = self.get_response(
                    data=None,
                    message="permission_ids must be a list",
                    status_code=status.HTTP_400_BAD_REQUEST,
                    is_error=True,
                )
                self.log_response(response)
                return response
            
            # Filter to only available permissions
            from django.contrib.auth.models import Permission
            from .models import available_permission_queryset
            
            # Convert permission IDs to integers
            permission_ids_int = [int(pid) for pid in permission_ids if str(pid).isdigit()]
            
            # Get available permission IDs as a list
            available_ids = list(available_permission_queryset.values_list("id", flat=True))
            
            # Filter to only valid permissions that exist and are available
            valid_permission_ids = [
                pid for pid in permission_ids_int 
                if pid in available_ids
            ]
            
            if valid_permission_ids:
                role.permissions.set(valid_permission_ids)
            role.save()
            
            serializer = self.get_serializer(role)
            response = self.get_response(
                data=serializer.data,
                message="Role permissions updated",
                status_code=status.HTTP_200_OK,
            )
            self.log_response(response)
            return response


class GroupViewSet(viewsets.ModelViewSet, StandardResponseMixin, LoggingMixin):
    """ViewSet for managing Django Groups"""
    queryset = Group.objects.all()
    serializer_class = GroupSerializer
    permission_classes = [IsSuperUserOrHasRolePermission]
    http_method_names = ["get", "post", "put", "patch", "delete"]
    
    def get_queryset(self):
        """Filter groups by name if provided"""
        queryset = super().get_queryset()
        name = self.request.query_params.get("name")
        
        if name:
            queryset = queryset.filter(name__icontains=name)
        
        return queryset.prefetch_related("permissions", "user_set", "roles")
    
    def create(self, request, *args, **kwargs):
        """Create a new group"""
        self.log_request(request)
        
        serializer = self.get_serializer(data=request.data)
        
        if serializer.is_valid():
            group = serializer.save()
            
            # Handle permissions if provided
            permission_ids = request.data.get("permissions", [])
            if permission_ids:
                permissions = Permission.objects.filter(id__in=permission_ids)
                group.permissions.set(permissions)
            
            response = self.get_response(
                data=self.get_serializer(group).data,
                message="Group created successfully",
                status_code=status.HTTP_201_CREATED,
            )
        else:
            response = self.get_response(
                data=serializer.errors,
                message="Validation Error",
                status_code=status.HTTP_400_BAD_REQUEST,
                is_error=True,
            )
        
        self.log_response(response)
        return response
    
    def update(self, request, *args, **kwargs):
        """Update a group"""
        self.log_request(request)
        
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=kwargs.get('partial', False))
        
        if serializer.is_valid():
            group = serializer.save()
            
            # Handle permissions if provided
            if "permissions" in request.data:
                permission_ids = request.data.get("permissions", [])
                permissions = Permission.objects.filter(id__in=permission_ids)
                group.permissions.set(permissions)
            
            response = self.get_response(
                data=self.get_serializer(group).data,
                message="Group updated successfully",
                status_code=status.HTTP_200_OK,
            )
        else:
            response = self.get_response(
                data=serializer.errors,
                message="Validation Error",
                status_code=status.HTTP_400_BAD_REQUEST,
                is_error=True,
            )
        
        self.log_response(response)
        return response
    
    def destroy(self, request, *args, **kwargs):
        """Delete a group"""
        self.log_request(request)
        
        instance = self.get_object()
        
        # Check if group has users
        user_count = instance.user_set.count()
        if user_count > 0:
            response = self.get_response(
                data={"user_count": user_count},
                message=f"Cannot delete group. It has {user_count} user(s) assigned. Please remove all users first.",
                status_code=status.HTTP_400_BAD_REQUEST,
                is_error=True,
            )
            self.log_response(response)
            return response
        
        # Check if group has roles
        role_count = 0
        if hasattr(instance, 'roles'):
            role_count = instance.roles.count()
            if role_count > 0:
                response = self.get_response(
                    data={"role_count": role_count},
                    message=f"Cannot delete group. It has {role_count} role(s) associated. Please remove all roles first.",
                    status_code=status.HTTP_400_BAD_REQUEST,
                    is_error=True,
                )
                self.log_response(response)
                return response
        
        # Delete the group
        group_id = instance.id
        group_name = instance.name
        instance.delete()
        
        response = self.get_response(
            data={"id": group_id, "name": group_name},
            message="Group deleted successfully",
            status_code=status.HTTP_200_OK,
        )
        self.log_response(response)
        return response
    
    def list(self, request, *args, **kwargs):
        """List all groups"""
        self.log_request(request)
        response = super().list(request, *args, **kwargs)
        
        if response.status_code == status.HTTP_200_OK:
            custom_response = self.get_response(
                data=response.data,
                message="Groups retrieved successfully",
                status_code=status.HTTP_200_OK,
            )
        else:
            custom_response = self.get_response(
                data=None,
                message="Error Occurred",
                status_code=response.status_code,
                is_error=True,
            )
        
        self.log_response(custom_response)
        return custom_response
    
    def retrieve(self, request, *args, **kwargs):
        """Retrieve a single group"""
        self.log_request(request)
        response = super().retrieve(request, *args, **kwargs)
        
        if response.status_code == status.HTTP_200_OK:
            custom_response = self.get_response(
                data=response.data,
                message="Group retrieved successfully",
                status_code=status.HTTP_200_OK,
            )
        else:
            custom_response = self.get_response(
                data=None,
                message="Error Occurred",
                status_code=response.status_code,
                is_error=True,
            )
        
        self.log_response(custom_response)
        return custom_response


class PermissionViewSet(viewsets.ModelViewSet, StandardResponseMixin, LoggingMixin):
    queryset = available_permission_queryset

    serializer_class = PermissionSerializer
    permission_classes = [HasRoleModelPermission]
    http_method_names = [
        "get",
    ]

    def list(self, request, *args, **kwargs):
        self.log_request(request)  # Log the incoming request
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)
        ids_list = [item["id"] for item in serializer.data]
        
        # Group permissions by module for better organization
        permissions_by_module = {}
        for perm_data in serializer.data:
            module = perm_data.get("module", "other")
            if module not in permissions_by_module:
                permissions_by_module[module] = []
            permissions_by_module[module].append(perm_data)

        response = self.get_response(
            data={
                "permissions_ids": sorted(ids_list),
                "permissions": serializer.data,
                "permissions_by_module": permissions_by_module,
            },
            message="permissions",
            status_code=status.HTTP_200_OK,
        )
        self.log_response(response)  # Log the response before returning
        return response

    def create(self, request, *args, **kwargs):
        self.log_request(request)  # Log the incoming request

        # Check if trying to create a system role
        is_system_role = request.data.get("is_system_role", False)
        if is_system_role and not request.user.is_superuser:
            response = self.get_response(
                data=None,
                message="Only superusers can create system roles.",
                status_code=status.HTTP_403_FORBIDDEN,
                is_error=True,
            )
            self.log_response(response)
            return response

        # Create an instance of your serializer with the request data
        serializer = self.get_serializer(data=request.data)

        if serializer.is_valid():
            # If the serializer is valid, perform the default creation logic
            response = super().create(request, *args, **kwargs)

            # Create a custom response
            custom_response = self.get_response(
                data=response.data,  # Use the data from the default response
                message="Role created successfully",
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

        # Check if non-superuser is trying to modify a system role
        if instance.is_system_role and not request.user.is_superuser:
            response = self.get_response(
                data=None,
                message="Only superusers can modify system roles. This role is protected.",
                status_code=status.HTTP_403_FORBIDDEN,
                is_error=True,
            )
            self.log_response(response)
            return response

        # Check if user is trying to change a non-system role to system role
        is_system_role = request.data.get("is_system_role")
        if is_system_role and not request.user.is_superuser:
            response = self.get_response(
                data=None,
                message="Only superusers can create or modify system roles. Please set is_system_role to false or contact a superuser.",
                status_code=status.HTTP_403_FORBIDDEN,
                is_error=True,
            )
            self.log_response(response)
            return response

        # Create an instance of your serializer with the request data and the object to be updated
        serializer = self.get_serializer(instance, data=request.data, partial=kwargs.get('partial', False))

        if serializer.is_valid():
            # Ensure non-superusers cannot set is_system_role to True
            if not request.user.is_superuser:
                serializer.validated_data['is_system_role'] = False
            
            # If the serializer is valid, perform the default update logic
            response = super().update(request, *args, **kwargs)

            # Create a custom response
            custom_response = self.get_response(
                data=response.data,  # Use the data from the default response
                message="Role Updated",
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
                is_error=True,
            )
            self.log_response(response)  # Log the response before returning
            return response

        roles = user.roles.all()

        group_data = []
        for role in roles:
            permissions = role.permissions.all()
            permission_names = [permission.name for permission in permissions]
            group_data.append(
                {
                    "user": {
                        "custom_id": user.custom_id,
                        "mobile_number": user.mobile_number,
                        "category": user.category,
                        "is_active": user.is_active,
                    },
                    "roles_and_permissions": {
                        "id": role.id,
                        "name": role.name,
                        "short_code": role.short_code,
                        "permissions": permission_names,
                    },
                }
            )
        response = self.get_response(
            data=group_data,
            message="roles and permissions",
            status_code=status.HTTP_200_OK,
        )
        self.log_response(response)  # Log the response before returning
        return response


# GroupMetadataViewSet and PermissionMetadataViewSet removed
# Use Django's Group and Permission models directly via existing viewsets

class UserRoleViewSet(viewsets.ModelViewSet, StandardResponseMixin, LoggingMixin):
    """ViewSet for managing UserRole assignments (Super Admin)"""
    queryset = UserRole.objects.all()
    serializer_class = UserRoleSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "post", "put", "patch", "delete"]

    def get_queryset(self):
        """Filter by user_id and business_id if provided"""
        queryset = super().get_queryset()
        user_id = self.request.query_params.get("user_id")
        business_id = self.request.query_params.get("business_id")
        
        if user_id:
            queryset = queryset.filter(user_id=user_id)
        if business_id:
            queryset = queryset.filter(business_id=business_id)
        
        # Only filter by is_active for list views, not for detail/update/delete operations
        # This allows accessing inactive roles by ID for editing
        if self.action == 'list':
            show_inactive = self.request.query_params.get("show_inactive", "false").lower() == "true"
            if not show_inactive:
                queryset = queryset.filter(is_active=True)
        
        return queryset.select_related("user", "role", "business", "assigned_by")

    def create(self, request, *args, **kwargs):
        self.log_request(request)
        serializer = self.get_serializer(data=request.data)
        
        if serializer.is_valid():
            # Ensure association_id is None if not provided or empty string
            if 'association_id' not in serializer.validated_data or serializer.validated_data.get('association_id') == '':
                serializer.validated_data['association_id'] = None
            
            # Set assigned_by to current user
            user_role = serializer.save(assigned_by=request.user)
            response = self.get_response(
                data=self.get_serializer(user_role).data,
                message="User role assigned successfully",
                status_code=status.HTTP_201_CREATED,
            )
        else:
            response = self.get_response(
                data=serializer.errors,
                message="Validation error",
                status_code=status.HTTP_400_BAD_REQUEST,
                is_error=True,
            )
        
        self.log_response(response)
        return response
    
    def update(self, request, *args, **kwargs):
        """Update user role assignment"""
        self.log_request(request)
        instance = self.get_object()
        partial = kwargs.pop('partial', False)
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        
        if serializer.is_valid():
            # Ensure association_id is None if explicitly set to null or empty
            if 'association_id' in serializer.validated_data:
                if serializer.validated_data['association_id'] == '':
                    serializer.validated_data['association_id'] = None
            
            user_role = serializer.save()
            response = self.get_response(
                data=self.get_serializer(user_role).data,
                message="User role updated successfully",
                status_code=status.HTTP_200_OK,
            )
        else:
            response = self.get_response(
                data=serializer.errors,
                message="Validation error",
                status_code=status.HTTP_400_BAD_REQUEST,
                is_error=True,
            )
        
        self.log_response(response)
        return response
    
    def partial_update(self, request, *args, **kwargs):
        """Partial update user role assignment"""
        kwargs['partial'] = True
        return self.update(request, *args, **kwargs)

    @action(detail=False, methods=["post"], url_path="bulk-assign")
    def bulk_assign(self, request):
        """Bulk assign roles to users"""
        self.log_request(request)
        assignments = request.data.get("assignments", [])
        
        if not isinstance(assignments, list):
            response = self.get_response(
                data=None,
                message="assignments must be a list",
                status_code=status.HTTP_400_BAD_REQUEST,
                is_error=True,
            )
            self.log_response(response)
            return response
        
        created = []
        errors = []
        
        for assignment in assignments:
            # Ensure association_id is None if not provided or empty string
            if 'association_id' not in assignment or assignment.get('association_id') == '':
                assignment['association_id'] = None
            
            serializer = self.get_serializer(data=assignment)
            if serializer.is_valid():
                user_role = serializer.save(assigned_by=request.user)
                created.append(self.get_serializer(user_role).data)
            else:
                errors.append({"assignment": assignment, "errors": serializer.errors})
        
        response = self.get_response(
            data={"created": created, "errors": errors},
            message=f"Bulk assignment completed: {len(created)} created, {len(errors)} errors",
            status_code=status.HTTP_200_OK,
        )
        self.log_response(response)
        return response
