from rest_framework import serializers, status
from django.contrib.auth.models import Permission, Group
from django.core.exceptions import PermissionDenied
from django.core.validators import (RegexValidator)
from rest_framework.permissions import IsAuthenticated
from rest_framework.permissions import BasePermission

from apps.authentication.models import User, Role
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
                regex=r'^(?=.*[a-zA-Z])(?=.*\d)(?=.*[@#$!%^&*()\-_+=])[A-Za-z\d@#$!%^&*()\-_+=]{8,}$',
                message="""Password must be at least 8 characters long and contain at least one letter, 
                    one number, and one special character."""
            )
        ]
    )

    class Meta:
        model = User
        fields = ('id', 'custom_id', 'email', 'password', 'mobile_number', 'first_name', 'last_name', 'last_login',
                  'category', 'is_staff', 'is_active', 'roles')
        extra_kwargs = {'password': {'write_only': True}}

    def validate_roles(self, value):
        if len(value) != 1:
            raise serializers.ValidationError({'message': 'User role with multiple choice not allowed.'})
        return value

    def create(self, validated_data):
        mobile_number = validated_data.get('mobile_number')
        roles = validated_data.pop('roles')

        if User.objects.filter(mobile_number=mobile_number).exists():
            raise serializers.ValidationError({'message': 'User with this mobile number already exists.'})

        user = User(**validated_data)
        user.set_password(validated_data['password'])
        user.custom_id = format_custom_id(roles[0].short_code, mobile_number)
        user.category = roles[0].name.title()
        if user.category == "Admin":
            user.is_staff = True
        user.save()
        user.roles.set(roles)

        return user

    def update(self, instance, validated_data):
        mobile_number = validated_data.get('mobile_number', instance.mobile_number)
        first_name = validated_data.get('first_name', instance.first_name)
        last_name = validated_data.get('last_name', instance.last_name)
        email = validated_data.get('email', instance.email)
        is_active = validated_data.get('is_active', instance.is_active)
        roles = validated_data.pop('roles', instance.roles.all())

        if mobile_number != instance.mobile_number and User.objects.filter(mobile_number=mobile_number).exists():
            raise serializers.ValidationError({'message': 'User with this mobile number already exists.'})

        if email != instance.email and User.objects.filter(email=email).exists():
            raise serializers.ValidationError({'message': 'User with this email already exists.'})

        instance.mobile_number = mobile_number
        instance.first_name = first_name
        instance.last_name = last_name
        instance.email = email
        instance.is_active = is_active

        instance.roles.set(roles)

        if 'password' in validated_data:
            instance.set_password(validated_data['password'])

        instance.save()
        if roles[0].name.title() == "Admin":
            instance.category = roles[0].name.title()
            instance.is_staff = True
        else:
            instance.category = roles[0].name.title()
            instance.is_staff = False
        instance.save()
        return instance

class UserListSerializer(serializers.ModelSerializer):
    
    class Meta:
        model = User
        fields = ('id', 'email', 'mobile_number', 'name', 'company_id',
                  'category', 'is_active', 'groups', 'roles')

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        user = instance
        customer_data = {}
        if instance:
            customer = user.customer_profile.all().first()
            if customer:
                customer_serializer = CustomerProfileSerializer(customer)
                customer_data = customer_serializer.data
                
        representation['customer_details'] = customer_data

        user_roles = [uroles for uroles in user.roles.values('id','name')]
        representation['roles'] = user_roles
        user_groups = [ugroups for ugroups in user.groups.values('id','name')]
        representation['groups'] = user_groups
        # representation['company_user'] = company_details
        return representation


class RoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Role
        fields = '__all__'

    def create(self, validated_data):
        get_permissions = validated_data.pop('permissions')
        role = super().create(validated_data)
        get_permission_ids = [permission.id for permission in get_permissions]
        final_permissions = [element for element in get_permission_ids if element in available_permission_ids]
        role.save()
        role.permissions.set(final_permissions)
        return role

    def update(self, instance, validated_data):
        get_permissions = validated_data.pop('permissions')
        role = super().update(instance, validated_data)
        get_permission_ids = [permission.id for permission in get_permissions]
        final_permissions = [element for element in get_permission_ids if element in available_permission_ids]
        role.save()
        role.permissions.set(final_permissions)
        return role


class PermissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Permission
        fields = '__all__'
