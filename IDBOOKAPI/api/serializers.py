from rest_framework import serializers
from rest_framework import exceptions
from django.contrib.auth import authenticate
from api.models import (User, KYCDocument, BankDetail, PayoutCalculation, Banners, Deposit,
                            Withdrawal, Transaction, Notification, Enquiry, Wallet, ShopDetail,
                            Gallery, Stylist, Service, Appointment, Review, WorkingDay,
                            AdminWallet, AboutUs, PrivacyPolicy, RefundAndCancellationPolicy,
                            TermsAndConditions, Legality, Career, FAQs, PaymentGateway, FCMToken)


class LoginSerializer(serializers.Serializer):
    email = serializers.CharField()
    password = serializers.CharField()

    def validate(self, data):
        email = data.get('email', '')
        password = data.get('password', '')

        if email and password:
            user = authenticate(username=email, password=password)
            if user:
                if user.mobile_verified:
                    data['user'] = user
                else:
                    msg = "User is not active"
                    raise exceptions.ValidationError(msg)
            else:
                msg = "Unable to login with given credentials"
                raise exceptions.ValidationError(msg)
        else:
            msg = "Must provide username and password both"
            raise exceptions.ValidationError(msg)
        return data


class UserSerializer(serializers.ModelSerializer):

    class Meta:
        model = User
        fields = ["id",
        "password",
        "email",
        "mobile",
        "first_name",
        "last_name",
        "gender",
        "profile_picture",
        # "razorpay_customer_id",
        # "razorpay_contact_id",
        # "razorpay_order_id",
        # "razorpay_payment_id",
        # "referral",
        # "level",
        # "joining",
        # "no_of_referral",
        # "total_earning",
        # "total_withdrawn",
        # "daily_earning",
        # "fcm_token",
        "email_verified",
        "mobile_verified",
        "customer",
        "shop_owner",
        # "payment_received",
        # "eligible",
        "blocked",
        "is_active",]
        # "reference"]
        # fields = '__all__'


class FCMTokenSerializer(serializers.ModelSerializer):

    class Meta:
        model = FCMToken
        fields = '__all__'


class ReferenceSerializer(serializers.ModelSerializer):
    referral = serializers.CharField()

    class Meta:
        model = User
        fields = ["referral"]


class ReferredListSerializer(serializers.ModelSerializer):
    referral = serializers.CharField()

    class Meta:
        model = User
        fields = ["id", "first_name", "last_name", "profile_picture", "paid", "referral"]


# class ProfileDetailSerializer(serializers.ModelSerializer):
#     class Meta:
#         model = ProfileDetail
#         fields = '__all__'

#
# class ServiceCategorySerializer(serializers.ModelSerializer):
#     class Meta:
#         model = ServiceCategory
#         fields = '__all__'


class WorkingDaySerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkingDay
        fields = '__all__'


class ShopDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShopDetail
        fields = '__all__'


class GallerySerializer(serializers.ModelSerializer):
    class Meta:
        model = Gallery
        fields = '__all__'


class StylistSerializer(serializers.ModelSerializer):
    class Meta:
        model = Stylist
        fields = '__all__'


class ServiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Service
        fields = '__all__'


class AppointmentSerializer(serializers.ModelSerializer):
    # service_charge = serializers.SerializerMethodField(read_only=True)
    # discount = serializers.SerializerMethodField(read_only=True)
    # total = serializers.SerializerMethodField(read_only=True)
    # booked_slot = serializers.SerializerMethodField(read_only=True)
    # exit_time = serializers.SerializerMethodField(read_only=True)
    # active = serializers.SerializerMethodField(read_only=True)

    # time_required = serializers.SerializerMethodField(read_only = True)

    class Meta:
        model = Appointment
        fields = '__all__'

    # def get_service_charge(self, obj):
    #     return 0
    #
    # def get_discount(self, obj):
    #     return 0
    #
    # def get_total(self, obj):
    #     return 0

    # def get_exit_time(self, obj):
    #     exit_time = obj.booked_slot
    #     for service in obj.service_taken.all():
    #         exit_time = exit_time + service.required_time
    #     print(exit_time, 'exit time')
    #     return exit_time

    # def get_time_required(self, obj):
    #     return (obj.exit_time - obj.booked_slot)

    # def get_active(self, obj):
    #     return True

    # def validate(self, data):
    #     date = data['booked_slot'].date()
    #     exit_time = data['booked_slot']
    #     for service in data['service_taken']:
    #         exit_time = exit_time + service.required_time
    #     obj_set = Appointment.objects.filter(booked_slot__date=date)
    #     print(exit_time)
    #
    #     if not obj_set:
    #         return data
    #     for appointment in obj_set:
    #         if ((data['booked_slot'] >= appointment.booked_slot) and (data['booked_slot'] <= appointment.exit_time)):
    #             raise serializers.ValidationError("Time Slot already taken")
    #         elif ((exit_time >= appointment.booked_slot) and (exit_time <= appointment.exit_time)):
    #             raise serializers.ValidationError("Time Slot already taken")
    #         elif ((data['booked_slot'] <= appointment.booked_slot) and (exit_time >= appointment.exit_time)):
    #             raise serializers.ValidationError("Time Slot already taken")
    #     return data


class ReviewSerializer(serializers.ModelSerializer):
    class Meta:
        model = Review
        fields = '__all__'


class KYCDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = KYCDocument
        fields = '__all__'


class BankDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = BankDetail
        fields = '__all__'
        # fields = ['id', 'bank_name', 'account_holder_name', 'account_number', 'ifsc', 'upi',
        #           'razorpay_vpa_fund_account_id', 'razorpay_bank_fund_account_id', 'active', 'created', 'updated',
        #           'user']


class PayoutCalculationSerializer(serializers.ModelSerializer):
    class Meta:
        model = PayoutCalculation
        fields = '__all__'


class BannersSerializer(serializers.ModelSerializer):
    class Meta:
        model = Banners
        fields = '__all__'


class DepositSerializer(serializers.ModelSerializer):
    class Meta:
        model = Deposit
        fields = '__all__'

#
# class ActiveSerializer(serializers.ModelSerializer):
#     class Meta:
#         model = Active
#         fields = '__all__'


class WithdrawalSerializer(serializers.ModelSerializer):
    class Meta:
        model = Withdrawal
        fields = '__all__'


class TransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Transaction
        fields = '__all__'


class AdminWalletSerializer(serializers.ModelSerializer):
    class Meta:
        model = AdminWallet
        fields = ["admin_charges"]


class WalletSerializer(serializers.ModelSerializer):
    class Meta:
        model = Wallet
        fields = '__all__'


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = '__all__'


class EnquirySerializer(serializers.ModelSerializer):
    class Meta:
        model = Enquiry
        fields = '__all__'


class AboutUsSerializer(serializers.ModelSerializer):
    class Meta:
        model = AboutUs
        fields = '__all__'


class PrivacyPolicySerializer(serializers.ModelSerializer):
    class Meta:
        model = PrivacyPolicy
        fields = '__all__'


class RefundAndCancellationPolicySerializer(serializers.ModelSerializer):
    class Meta:
        model = RefundAndCancellationPolicy
        fields = '__all__'


class TermsAndConditionsSerializer(serializers.ModelSerializer):
    class Meta:
        model = TermsAndConditions
        fields = '__all__'


class LegalitySerializer(serializers.ModelSerializer):
    class Meta:
        model = Legality
        fields = '__all__'


class CareerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Career
        fields = '__all__'


class FAQsSerializer(serializers.ModelSerializer):
    class Meta:
        model = FAQs
        fields = '__all__'


class PaymentGatewaySerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentGateway
        fields = ('provider', 'enabled')
        # extra_kwargs = {'password': {'read_only': True}}
