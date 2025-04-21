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
from apps.authentication.utils.authentication_utils import get_group_based_on_name
from apps.authentication.utils.db_utils import get_group_based_user_details

##from IDBOOKAPI.email_utils import email_validation
##from IDBOOKAPI.utils import validate_mobile_number




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
        fields = ('id', 'password', 'email', 'name','mobile_number','roles', 'referred_code')
        extra_kwargs = {'password': {'write_only': True}}

    def validate_roles(self, value):
        if len(value) != 1:
            raise serializers.ValidationError({'message': 'User role with multiple choice not allowed.'})
        return value

    def validate_email(self, value):
        if value:
            value = value.lower()
            if User.objects.filter(email=value).exists():
                raise serializers.ValidationError("Email already exists.")
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
            

##    def validate_email(self, value):
##        if value and User.objects.filter(email=value).exists():
##            raise serializers.ValidationError('Email already exists.')
##        return value

    def create(self, validated_data):
        mobile_number = validated_data.get('mobile_number')
        email = validated_data.get('email')
        # roles = validated_data.pop('roles')

        user = User(**validated_data)
        user.set_password(validated_data['password'])
        # user.is_active = True

        # user.custom_id = format_custom_id(roles[0].short_code, mobile_number)
        # user.category = roles[0].name.title()
        user.save()
        #user.roles.set(roles)

        return user

    def update(self, instance, validated_data):
        mobile_number = validated_data.get('mobile_number')
        name = validated_data.get('name')
        password = validated_data.get('password')
        
        instance.set_password(password)
        instance.mobile_number = mobile_number
        instance.name = name
        instance.save()
        
        return instance
        

    


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField(required=False, allow_null=True)
    mobile_number = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    username = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    group_name = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    password = serializers.CharField(write_only=True)

    def validate(self, validated_data):
        email = validated_data.get('email')
        username = validated_data.get('username')
        mobile_number = validated_data.get('mobile_number')
        password = validated_data.get('password')
        group_name = validated_data.get('group_name', 'B2C-GRP')

        if username:
            grp, role = get_group_based_on_name(group_name)
            if not grp or not role:
                raise serializers.ValidationError('GROUP_ROLE_NOT_EXIST')

            user = get_group_based_user_details(grp, username)
            if user:
                if not user.check_password(password):
                    raise serializers.ValidationError('credentials_error')
                
                user.default_group = group_name
                user.save()
                
            
##            is_mb_valid = validate_mobile_number(username)
##            if is_mb_valid:
##               # get the group name and make validation
##               
##                   
##            else:
##                is_email_valid = email_validation(username)

        else:
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

class UserRefferalSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('id', 'name', 'email','first_booking')

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        credited_user_dict = self.context.get("credited_user_dict", {})
        print(credited_user_dict)
        if instance:
            credited_user = credited_user_dict.get(instance.id, None)
            if credited_user:
                representation['is_credited'] = True
                representation['amount'] = credited_user.get('amount', None)
            else:
                representation['is_credited'] = False
                representation['amount'] = None

        return representation
