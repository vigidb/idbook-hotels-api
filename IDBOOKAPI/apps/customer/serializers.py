from rest_framework import serializers, status
# from django.contrib.auth.models import Permission, Group
from django.core.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.permissions import BasePermission
from apps.org_resources.models import CompanyDetail

# from apps.authentication.models import *
from .models import *
# from booking.models import *
# from carts.models import *
# from coupons.models import *
# from customer.models import *
# from holiday_package.models import *
# from hotel_managements.models import *
# from hotels.models import *
# from org_managements.models import *
from apps.org_resources.models import *
# from payment_gateways.models import *
from IDBOOKAPI.utils import format_custom_id
from django.conf import settings

class CustomerProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = '__all__'

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        if instance.profile_picture:
            representation['profile_picture'] = f"{settings.CDN}{settings.PUBLIC_MEDIA_LOCATION}/{str(instance.profile_picture)}"

        # settings.MEDIA_URL + str(gallery.get('media', ''))
        return representation
        
        

class CustomerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = '__all__'

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        if instance:
            business_id, company_id = '',''
            if instance.user:
                name = instance.user.get_full_name()
                email = instance.user.email if instance.user.email else ''
                mobile_number = instance.user.mobile_number if instance.user.mobile_number else ''
                company_id = instance.user.company_id
                business_id = instance.user.business_id
                user_details = {"name":name, "email":email, "mobile_number":mobile_number}
                representation['user'] = user_details
            if company_id:
                company_object = CompanyDetail.objects.filter(id=company_id).first() #instance.company_user.company_detail.first()
                company_details = {}
                if company_object:
                    company_name = company_object.company_name if company_object.company_name else ''
                    company_phone = company_object.company_phone if company_object.company_phone else ''
                    company_email = company_object.company_email if company_object.company_email else ''
                    company_details = {'company_name':company_name,
                                        'company_phone':company_phone,
                                        'company_email':company_email}
                    
                if not company_object:
                    business_object = instance.user.business_detail.first()
                    if business_object:
                        company_name = business_object.business_name if business_object.business_name else ''
                        company_phone = business_object.business_phone if business_object.business_phone else ''
                        company_email = business_object.business_email if business_object.business_email else ''
                        company_details = {'company_name':company_name,
                                           'company_phone':company_phone,
                                           'company_email':company_email}
                        
                representation['company_user'] = company_details

        return representation

class QueryFilterCustomerSerializer(serializers.ModelSerializer):
    company_id = serializers.IntegerField(required=False)
    user_id = serializers.IntegerField(required=False)
    offset = serializers.IntegerField(required=False)
    limit = serializers.IntegerField(required=False)
    search = serializers.CharField(required=False, help_text='Available columns: employee_id')
    
    class Meta:
        model = Customer
        fields = ('company_id', 'user_id', 'group_name',
                  'department', 'privileged', 'active',
                  'offset', 'limit', 'search')

class WalletSerializer(serializers.ModelSerializer):
    class Meta:
        model = Wallet
        fields = '__all__'

class WalletTransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = WalletTransaction
        fields = '__all__'

class QueryFilterWalletTransactionSerializer(serializers.ModelSerializer):
    offset = serializers.IntegerField(required=False)
    limit = serializers.IntegerField(required=False)
    #search = serializers.CharField(required=False, help_text='Available columns: employee_id')
    
    class Meta:
        model = WalletTransaction
        fields = ('transaction_type', 'offset', 'limit')

        
