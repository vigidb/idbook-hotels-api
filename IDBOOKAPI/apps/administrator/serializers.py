from rest_framework import serializers, status
from django.contrib.auth.models import Permission, Group
from django.core.exceptions import PermissionDenied
from django.core.validators import RegexValidator
from rest_framework.permissions import IsAuthenticated
from rest_framework.permissions import BasePermission

from apps.authentication.models import (
    User,
    Role,
    UserRole,
)
from apps.org_managements.models import BusinessDetail
from .models import available_permission_ids, available_permission_queryset

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
from IDBOOKAPI.utils import format_custom_id

from apps.customer.serializers import CustomerProfileSerializer


class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(
        write_only=True,
        validators=[
            RegexValidator(
                regex=r"^(?=.*[a-zA-Z])(?=.*\d)(?=.*[@#$!%^&*()\-_+=])[A-Za-z\d@#$!%^&*()\-_+=]{8,}$",
                message="""Password must be at least 8 characters long and contain at least one letter, 
                    one number, and one special character.""",
            )
        ],
    )

    class Meta:
        model = User
        fields = (
            "id",
            "custom_id",
            "email",
            "password",
            "mobile_number",
            "first_name",
            "last_name",
            "last_login",
            "category",
            "is_staff",
            "is_active",
            "roles",
        )
        extra_kwargs = {"password": {"write_only": True}}

    def validate_roles(self, value):
        if len(value) != 1:
            raise serializers.ValidationError(
                {"message": "User role with multiple choice not allowed."}
            )
        return value

    def create(self, validated_data):
        mobile_number = validated_data.get("mobile_number")
        roles = validated_data.pop("roles")

        if User.objects.filter(mobile_number=mobile_number).exists():
            raise serializers.ValidationError(
                {"message": "User with this mobile number already exists."}
            )

        user = User(**validated_data)
        user.set_password(validated_data["password"])
        user.custom_id = format_custom_id(roles[0].short_code, mobile_number)
        user.category = roles[0].name.title()
        if user.category == "Admin":
            user.is_staff = True
        user.save()
        user.roles.set(roles)

        return user

    def update(self, instance, validated_data):
        mobile_number = validated_data.get("mobile_number", instance.mobile_number)
        first_name = validated_data.get("first_name", instance.first_name)
        last_name = validated_data.get("last_name", instance.last_name)
        email = validated_data.get("email", instance.email)
        is_active = validated_data.get("is_active", instance.is_active)
        roles = validated_data.pop("roles", instance.roles.all())

        if (
            mobile_number != instance.mobile_number
            and User.objects.filter(mobile_number=mobile_number).exists()
        ):
            raise serializers.ValidationError(
                {"message": "User with this mobile number already exists."}
            )

        if email != instance.email and User.objects.filter(email=email).exists():
            raise serializers.ValidationError(
                {"message": "User with this email already exists."}
            )

        instance.mobile_number = mobile_number
        instance.first_name = first_name
        instance.last_name = last_name
        instance.email = email
        instance.is_active = is_active

        instance.roles.set(roles)

        if "password" in validated_data:
            instance.set_password(validated_data["password"])

        instance.save()
        if roles[0].name.title() == "Admin":
            instance.category = roles[0].name.title()
            instance.is_staff = True
        else:
            instance.category = roles[0].name.title()
            instance.is_staff = False
        instance.save()
        return instance


class UserAdminListSerializer(serializers.ModelSerializer):

    class Meta:
        model = User
        fields = (
            "id",
            "custom_id",
            "email",
            "mobile_number",
            "name",
            "first_name",
            "last_name",
            "company_id",
            "business_id",
            "category",
            "default_group",
            "is_active",
            "is_staff",
            "email_verified",
            "mobile_verified",
            "first_booking",
            "created",
            "updated",
            "groups",
            "roles",
        )

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        user = instance
        customer_data = {}
        if instance:
            customer = user.customer_profile.all().first()
            if customer:
                customer_serializer = CustomerProfileSerializer(customer)
                customer_data = customer_serializer.data

        representation["customer_details"] = customer_data

        # Use UserRole model instead of old ManyToMany roles field
        from apps.authentication.models import UserRole
        user_role_assignments = UserRole.objects.filter(user=user, is_active=True).select_related("role", "business")
        user_roles = [
            {
                "id": ur.role.id,
                "name": ur.role.name,
                "short_code": ur.role.short_code,
                "business_id": ur.business.id if ur.business else None,
                "business_name": ur.business.business_name if ur.business else None,
                "region": ur.region,
                "association_id": ur.association_id,
                "is_system_role": ur.role.is_system_role,
            }
            for ur in user_role_assignments
        ]
        representation["roles"] = user_roles
        
        # Keep groups from ManyToMany (this is still valid)
        user_groups = [ugroups for ugroups in user.groups.values("id", "name")]
        representation["groups"] = user_groups
        # representation['company_user'] = company_details
        return representation


class RoleSerializer(serializers.ModelSerializer):
    business_name = serializers.CharField(source="business.business_name", read_only=True, allow_null=True)
    group_name = serializers.CharField(source="group.name", read_only=True, allow_null=True)
    permissions_detail = serializers.SerializerMethodField()
    
    class Meta:
        model = Role
        fields = "__all__"
    
    def get_permissions_detail(self, obj):
        """Get detailed permission information"""
        permissions = obj.permissions.all()
        return [
            {
                "id": perm.id,
                "name": perm.name,
                "codename": perm.codename,
                "permission_code": self._get_permission_code(perm),
                "module": self._get_module(perm),
                "description": perm.name or self._get_description(perm),
            }
            for perm in permissions
        ]
    
    def _get_permission_code(self, perm):
        """Helper to get permission code"""
        from apps.authentication.utils.permission_utils import get_permission_code
        return get_permission_code(perm)
    
    def _get_module(self, perm):
        """Helper to get module"""
        codename = perm.codename
        if '_' in codename:
            parts = codename.split('_', 1)
            if len(parts) > 1:
                return parts[1]
        return perm.content_type.app_label
    
    def _get_description(self, perm):
        """Helper to get description"""
        codename = perm.codename
        action_map = {
            'view': 'View',
            'add': 'Create',
            'change': 'Update',
            'delete': 'Delete',
        }
        for action, action_desc in action_map.items():
            if codename.startswith(f"{action}_"):
                model_name = codename[len(action) + 1:].replace('_', ' ').title()
                return f"{action_desc} {model_name}"
        return perm.name

    def create(self, validated_data):
        # Permissions are handled in the viewset, not here
        # Remove permissions from validated_data if present (it will be handled separately)
        validated_data.pop("permissions", None)
        
        # Create the role
        role = super().create(validated_data)
        
        return role

    def update(self, instance, validated_data):
        # Permissions are handled in the viewset, not here
        # Remove permissions from validated_data if present (it will be handled separately)
        validated_data.pop("permissions", None)
        
        # Update the role
        role = super().update(instance, validated_data)
        
        return role


class PermissionSerializer(serializers.ModelSerializer):
    permission_code = serializers.SerializerMethodField()
    module = serializers.SerializerMethodField()
    description = serializers.SerializerMethodField()
    
    class Meta:
        model = Permission
        fields = "__all__"
    
    def get_permission_code(self, obj):
        """Convert Django permission to custom code format"""
        from apps.authentication.utils.permission_utils import get_permission_code
        return get_permission_code(obj)
    
    def get_module(self, obj):
        """Extract module name from permission"""
        # Extract module from codename (e.g., "view_booking" -> "booking")
        codename = obj.codename
        if '_' in codename:
            # Remove action prefix (view_, add_, change_, delete_)
            parts = codename.split('_', 1)
            if len(parts) > 1:
                return parts[1]  # Return model name (e.g., "booking")
        return obj.content_type.app_label
    
    def get_description(self, obj):
        """Generate human-readable description from permission"""
        codename = obj.codename
        content_type = obj.content_type.model
        
        # Map actions to descriptions
        action_map = {
            'view': 'View',
            'add': 'Create',
            'change': 'Update',
            'delete': 'Delete',
        }
        
        # Extract action and model
        for action, action_desc in action_map.items():
            if codename.startswith(f"{action}_"):
                model_name = codename[len(action) + 1:].replace('_', ' ').title()
                return f"{action_desc} {model_name}"
        
        # Fallback to name
        return obj.name


# GroupMetadata and PermissionMetadata serializers removed - using Django models directly

class UserRoleSerializer(serializers.ModelSerializer):
    user_email = serializers.CharField(source="user.email", read_only=True)
    user_mobile = serializers.CharField(source="user.mobile_number", read_only=True)
    user_name = serializers.CharField(source="user.get_full_name", read_only=True)
    role_name = serializers.CharField(source="role.name", read_only=True)
    role_description = serializers.CharField(source="role.description", read_only=True)
    role_short_code = serializers.CharField(source="role.short_code", read_only=True)
    business_name = serializers.CharField(source="business.business_name", read_only=True)
    assigned_by_email = serializers.CharField(
        source="assigned_by.email", read_only=True, allow_null=True
    )
    scope_description = serializers.SerializerMethodField()

    class Meta:
        model = UserRole
        fields = "__all__"
        read_only_fields = ("assigned_at", "created", "updated")
        extra_kwargs = {
            "association_id": {"required": False, "allow_null": True},
            "region": {"required": False, "allow_null": True},
        }
    
    def get_scope_description(self, obj):
        """Generate human-readable scope description"""
        scope_parts = []
        if obj.region:
            scope_parts.append(f"Region: {obj.region}")
        if obj.association_id:
            # Try to determine association type
            if obj.role and obj.role.group:
                group_name = obj.role.group.name
                if "CORPORATE" in group_name:
                    scope_parts.append(f"Company ID: {obj.association_id}")
                elif "AGENT" in group_name:
                    scope_parts.append(f"Agent ID: {obj.association_id}")
                elif "HOTELIER" in group_name:
                    scope_parts.append(f"Hotel ID: {obj.association_id}")
                else:
                    scope_parts.append(f"Association ID: {obj.association_id}")
            else:
                scope_parts.append(f"Association ID: {obj.association_id}")
        
        if scope_parts:
            return " | ".join(scope_parts)
        return "No scope restrictions (all regions/associations)"

class GroupSerializer(serializers.ModelSerializer):
    """Serializer for Django Group model"""
    user_count = serializers.SerializerMethodField()
    role_count = serializers.SerializerMethodField()
    permissions_detail = serializers.SerializerMethodField()
    
    class Meta:
        model = Group
        fields = "__all__"
        read_only_fields = ("id",)
    
    def get_user_count(self, obj):
        """Get count of users in this group"""
        return obj.user_set.count()
    
    def get_role_count(self, obj):
        """Get count of roles associated with this group"""
        if hasattr(obj, 'roles'):
            return obj.roles.count()
        return 0
    
    def get_permissions_detail(self, obj):
        """Get detailed permission information"""
        permissions = obj.permissions.all()
        return [
            {
                "id": perm.id,
                "name": perm.name,
                "codename": perm.codename,
                "permission_code": self._get_permission_code(perm),
                "module": self._get_module(perm),
                "description": perm.name or self._get_description(perm),
            }
            for perm in permissions
        ]
    
    def _get_permission_code(self, perm):
        """Helper to get permission code"""
        from apps.authentication.utils.permission_utils import get_permission_code
        return get_permission_code(perm)
    
    def _get_module(self, perm):
        """Helper to get module"""
        codename = perm.codename
        if '_' in codename:
            parts = codename.split('_', 1)
            if len(parts) > 1:
                return parts[1]
        return perm.content_type.app_label
    
    def _get_description(self, perm):
        """Helper to get description"""
        codename = perm.codename
        action_map = {
            'view': 'View',
            'add': 'Create',
            'change': 'Update',
            'delete': 'Delete',
        }
        for action, action_desc in action_map.items():
            if codename.startswith(f"{action}_"):
                model_name = codename[len(action) + 1:].replace('_', ' ').title()
                return f"{action_desc} {model_name}"
        return perm.name
