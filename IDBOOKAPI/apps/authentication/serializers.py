from rest_framework import serializers, status
from django.core.validators import RegexValidator

from .models import User
from .mobile_authentication import PhonePasswordAuthBackend
from .email_authentication  import EmailPasswordAuthBackend
from django.contrib.auth import authenticate
from IDBOOKAPI.utils import format_custom_id


class UserSignupSerializer(serializers.ModelSerializer):
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
        fields = ('id', 'password', 'email', 'first_name','last_name','mobile_number','roles')
        extra_kwargs = {'password': {'write_only': True}}

    def validate_roles(self, value):
        if len(value) != 1:
            raise serializers.ValidationError({'message': 'User role with multiple choice not allowed.'})
        return value

    def create(self, validated_data):
        mobile_number = validated_data.get('mobile_number')
        email = validated_data.get('email')
        # roles = validated_data.pop('roles')

        if not mobile_number and not email:
            raise serializers.ValidationError({'message': 'Provide either mobile number or email'})

        if mobile_number and User.objects.filter(mobile_number=mobile_number).exists():
            raise serializers.ValidationError({'message': 'User with this mobile number already exists.'})

        if email and User.objects.filter(email=email).exists():
            raise serializers.ValidationError({'message': 'User with this email already exists.'})

        user = User(**validated_data)
        user.set_password(validated_data['password'])
        user.is_active = True
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
                raise serializers.ValidationError('User account is disabled.')
        else:
            raise serializers.ValidationError('User not found or password incorrect.')

        validated_data['user'] = user
        return validated_data

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        user = instance['user']
        user_roles = [uroles for uroles in user.roles.values('id','name')]
        ret['id'] = user.id
        ret['mobile_number'] = user.mobile_number if user.mobile_number else ''
        ret['email'] = user.email if user.email else ''
        ret['name'] =  user.get_full_name() #user.first_name if user.first_name else ''
        ret['roles'] = user_roles
        ret['permissions'] = []
        
        # ret['category'] = user.category
        # ret['is_active'] = user.is_active
        return ret

class UserListSerializer(serializers.Serializer):
    class Meta:
        model = User
        fields = '__all__'

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        user = instance['user']
        user_roles = [uroles for uroles in user.roles.values('id','name')]
        ret['id'] = user.id
        ret['mobile_number'] = user.mobile_number if user.mobile_number else ''
        ret['email'] = user.email if user.email else ''
        ret['name'] = user.get_full_name()#user.first_name if user.first_name else ''
        ret['roles'] = user_roles
        ret['permissions'] = []
        
        # ret['category'] = user.category
        # ret['is_active'] = user.is_active
        return ret
