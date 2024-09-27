from rest_framework import serializers, status
from django.contrib.auth.models import Permission, Group
from rest_framework.permissions import IsAuthenticated

from .models import BusinessDetail
from apps.authentication.models import User

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


class ORGMUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('id', 'custom_id', 'email', 'password', 'mobile_number',
                  'first_name', 'last_name', 'last_login', 'roles')


class BusinessDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = BusinessDetail
        fields = ('business_name','business_logo','business_phone',
                  'business_email', 'country')

    def create(self, validated_data):
        request = self.context.get('request')
        if not request.user:
            raise serializers.ValidationError({'message': 'Provide user id'})
        
        existing_detail = BusinessDetail.objects.filter(user=request.user)
        if existing_detail:
            raise serializers.ValidationError({'message': 'Business deatil is already available'})
            
        business_detail = BusinessDetail(**validated_data)
        business_detail.user = request.user
        business_detail.save()

        return business_detail

    
        




        
