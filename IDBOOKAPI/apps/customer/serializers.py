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


class WalletRechargeSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=20, decimal_places=6, required=True)
    company_id = serializers.IntegerField(required=False, allow_null=True)
    payment_type = serializers.CharField(max_length=50, required=True)
    payment_medium = serializers.CharField(max_length=50, required=True)
    media = serializers.FileField(required=True)
    transaction_id = serializers.CharField(max_length=350, required=True)

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("Amount must be greater than 0")
        return value

    def validate_transaction_id(self, value):
        if WalletTransaction.objects.filter(transaction_id=value).exists():
            raise serializers.ValidationError("Transaction ID already exists")
        return value

class ApproveRechargeSerializer(serializers.Serializer):
    transaction_id = serializers.CharField(max_length=350)
    amount = serializers.DecimalField(max_digits=20, decimal_places=6)

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("Amount must be greater than 0")
        return value

class QueryFilterPendingRechargeSerializer(serializers.Serializer):
    user_id = serializers.IntegerField(required=False, allow_null=True)
    company_id = serializers.IntegerField(required=False, allow_null=True)
    offset = serializers.IntegerField(required=False, default=0, min_value=0)
    limit = serializers.IntegerField(required=False, default=10, min_value=1, max_value=100)
    transaction_id = serializers.CharField(required=False, allow_blank=True)
    payment_type = serializers.CharField(required=False, allow_blank=True)
    payment_medium = serializers.CharField(required=False, allow_blank=True)
    start_date = serializers.DateTimeField(required=False, allow_null=True)
    end_date = serializers.DateTimeField(required=False, allow_null=True)

class PendingRechargeSerializer(serializers.ModelSerializer):
    user_name = serializers.SerializerMethodField()
    company_name = serializers.SerializerMethodField()
    
    class Meta:
        model = WalletTransaction
        fields = [
            'id', 'user', 'company', 'user_name', 'company_name',
            'code', 'amount', 'transaction_type', 'transaction_for',
            'transaction_id', 'transaction_details', 'payment_type',
            'payment_medium', 'status', 'media',
            'created', 'updated'
        ]
    
    def get_user_name(self, obj):
        if obj.user:
            return f"{obj.user.name}".strip() or obj.user.name
        return None
    
    def get_company_name(self, obj):
        if obj.company:
            return obj.company.company_name if hasattr(obj.company, 'company_name') else str(obj.company)
        return None
