from rest_framework import serializers, status
from django.core.validators import RegexValidator

from .models import User
from .mobile_authentication import PhonePasswordAuthBackend
from .email_authentication  import EmailPasswordAuthBackend
from django.contrib.auth import authenticate
from IDBOOKAPI.utils import format_custom_id

from apps.customer.serializers import CustomerProfileSerializer
from apps.org_resources.serializers import CompanyDetailSerializer
from apps.org_managements.serializers import BusinessDetailSerializer
from apps.org_managements.utils import get_business_details
from apps.org_resources.db_utils import get_company_details



class UserSignupSerializer(serializers.ModelSerializer):
    password = serializers.CharField(
        write_only=True,
        validators=[
            RegexValidator(
                regex=r'^(?=.*[a-zA-Z])(?=.*\d)(?=.*[@#$!%^&*()\-_+=])[A-Za-z\d@#$!%^&*()\-_+=]{8,}$',
                message="""Password must be at least 8 characters long and contain at least one letter, one number, and one special character."""
            )
        ]
    )

    class Meta:
        model = User
        fields = ('id', 'password', 'email', 'name','mobile_number','roles')
        extra_kwargs = {'password': {'write_only': True}}

    def validate_roles(self, value):
        if len(value) != 1:
            raise serializers.ValidationError({'message': 'User role with multiple choice not allowed.'})
        return value

    def validate(self, attrs):
        email = attrs.get("email", '')
        mobile_number = attrs.get("mobile_number", '')
        if not email and not mobile_number:
            raise serializers.ValidationError('Provide either mobile number or email')
        return attrs
            

##    def validate_mobile_number(self, value):
##        if value and User.objects.filter(mobile_number=value).exists():
##             raise serializers.ValidationError("Mobile number already exists.")
##        return value
            

    def validate_email(self, value):
        if value and User.objects.filter(email=value).exists():
            raise serializers.ValidationError('Email already exists.')
        return value

    def create(self, validated_data):
        mobile_number = validated_data.get('mobile_number')
        email = validated_data.get('email')
        # roles = validated_data.pop('roles')

        user = User(**validated_data)
        user.set_password(validated_data['password'])
        user.is_active = True
        user.category = 'B-CUST'
##        if roles[0].short_code != 'CUS':
##            user.is_active = False
##        if roles[0].short_code == 'HOT':
##            user.is_active = True
        # user.custom_id = format_custom_id(roles[0].short_code, mobile_number)
        # user.category = roles[0].name.title()
        user.save()
        #user.roles.set(roles)

        return user


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField(required=False, allow_null=True)
    mobile_number = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    password = serializers.CharField(write_only=True)

    def validate(self, validated_data):
        email = validated_data.get('email')
        mobile_number = validated_data.get('mobile_number')
        password = validated_data.get('password')
        user = ''

        if email:
            user = EmailPasswordAuthBackend().authenticate(email=email, password=password)
        elif mobile_number:
            user = PhonePasswordAuthBackend().authenticate(mobile_number=mobile_number, password=password)

        if user:
            if not user.is_active:
                raise serializers.ValidationError('account_inactive')
        else:
            raise serializers.ValidationError('credentials_error')

        validated_data['user'] = user
        return validated_data

##    def to_representation(self, instance):
##        ret = super().to_representation(instance)
##        profile_picture, employee_id = "", ""
##        user = instance['user']
##        user_roles = [uroles for uroles in user.roles.values('id','name')]
##
##        ret['id'] = user.id
##        ret['mobile_number'] = user.mobile_number if user.mobile_number else ''
##        ret['email'] = user.email if user.email else ''
##        ret['name'] =  user.get_full_name() #user.first_name if user.first_name else ''
##        ret['roles'] = user_roles
##        ret['permissions'] = []
##        ret['business_id'] = user.business_id if user.business_id else ''
##        ret['company_id'] = user.company_id if user.company_id else ''
##        ret['category'] = user.category
##        ret['is_active'] = user.is_active
##
##        customer_profile = user.customer_profile
##        if user.customer_profile:
##            profile_picture = customer_profile.profile_picture
##            employee_id = customer_profile.employee_id
##            
##        ret['profile_picture'] = profile_picture
##        # ret['employee_id'] = employee_id
##        
##        return ret


class UserListSerializer(serializers.Serializer):
    class Meta:
        model = User
        fields = '__all__'

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        user = instance
        user_category = user.category
        
        business_id, company_id  = user.business_id, user.company_id
        business_data, company_data = {}, {}
        customer_data = {}
        
        customer = user.customer_profile.all().first()
        if customer:
            customer_serializer = CustomerProfileSerializer(customer)
            customer_data = customer_serializer.data

        if business_id:
            business_details = get_business_details(business_id)
            business_serializer = BusinessDetailSerializer(business_details)
            business_data = business_serializer.data

##        if company_id:
##            company_details = get_company_details(company_id)
##            company_serializer = CompanyDetailSerializer(company_details)
##            company_data = company_serializer.data
            
        
        user_roles = [uroles for uroles in user.roles.values('id','name')]
        user_groups = [ugroups for ugroups in user.groups.values('id','name')]
        ret['id'] = user.id
        ret['mobile_number'] = user.mobile_number if user.mobile_number else ''
        ret['email'] = user.email if user.email else ''
        ret['name'] = user.get_full_name()
        ret['groups'] = user_groups
        ret['roles'] = user_roles
        ret['permissions'] = []
        ret['category'] = user_category
        ret['customer_details'] = customer_data
        ret['business_details'] = business_data
        # ret['company_details'] = company_data
        ret['company_id'] = company_id
        
        # ret['category'] = user.category
        # ret['is_active'] = user.is_active
        return ret
