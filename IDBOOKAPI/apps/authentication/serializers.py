from rest_framework import serializers, status
from django.core.validators import RegexValidator

from .models import User
from .mobile_authentication import PhonePasswordAuthBackend
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
        fields = ('custom_id', 'password', 'mobile_number', 'category', 'is_active', 'roles')
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
        if roles[0].short_code != 'CUS':
            user.is_active = False
        if roles[0].short_code == 'HOT':
            user.is_active = True
        user.custom_id = format_custom_id(roles[0].short_code, mobile_number)
        user.category = roles[0].name.title()
        user.save()
        user.roles.set(roles)

        return user


class LoginSerializer(serializers.Serializer):
    # email = serializers.EmailField()
    mobile_number = serializers.CharField()
    password = serializers.CharField(write_only=True)

    def validate(self, validated_data):
        # email = validated_data.get('email')
        mobile_number = validated_data.get('mobile_number')
        password = validated_data.get('password')

        # user = authenticate(username=email, password=password)
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
        ret['custom_id'] = user.custom_id
        ret['mobile_number'] = user.mobile_number
        ret['category'] = user.category
        ret['is_active'] = user.is_active
        return ret

