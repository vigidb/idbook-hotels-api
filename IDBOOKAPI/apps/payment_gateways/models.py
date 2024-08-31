from datetime import timedelta
from django.conf import settings
from django.urls import reverse, reverse_lazy
from django.db import models
from django.db.models import Q
from django.db.models.signals import pre_save, post_save
from django.contrib.auth.models import (AbstractBaseUser, BaseUserManager)
from django.core.mail import send_mail
from django.template.loader import get_template
from django.utils import timezone
from django.utils.text import slugify
from rest_framework.authtoken.models import Token
from django.core.validators import (BaseValidator, FileExtensionValidator, URLValidator, EmailValidator, validate_slug,
                                    RegexValidator, MinValueValidator, MaxValueValidator)


from .utils import (unique_key_generator, GENDER_CHOICES, PAYMENT_STATUS_CHOICES, KYC_STATUS_CHOICES,
                          EDUCATION_CHOICES, KYC_DOCUMENT_CHOICES, TXN_TYPE_CHOICES, PAYMENT_METHOD_CHOICES,
                          SERVICE_CATEGORY_TYPE_CHOICES, SERVICE_TYPE_CHOICES, DEPOSIT_STATUS, STATE_CHOICES,
                          ENQUIRY_CHOICES, PAYMENT_GATEWAY_STATUS_CHOICE, unique_referral_id_generator, WORKING_DAYS,
                          APPOINTMENT_STATUS, FCM_TOKEN_CHOICE, USER_TYPE_CHOICE)
from .validators import get_filename, validate_file_extension, calculate_age, MinAgeValidator


class RazorpayOrder(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='razorpay_user')
    rp_id = models.CharField(max_length=250)
    entity = models.CharField(max_length=50)
    amount = models.PositiveSmallIntegerField(default=0)
    amount_due = models.PositiveSmallIntegerField(default=0)
    currency = models.CharField(max_length=50)
    receipt = models.CharField(max_length=50)
    offer_id = models.CharField(max_length=50)
    status = models.CharField(max_length=50)
    attempts = models.PositiveSmallIntegerField(default=0)
    notes = models.TextField(blank=True, null=True)
    created_at = models.CharField(max_length=50)

    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return str(self.user.email)


class RazorpayPayout(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='razorpay_payout_user')
    razorpay_customer_id = models.CharField(max_length=50, blank=True)
    razorpay_order_id = models.CharField(max_length=50, blank=True)
    razorpay_payment_id = models.CharField(max_length=50, blank=True)
    razorpay_contact_id = models.CharField(max_length=50, blank=True)
    razorpay_vpa_fund_account_id = models.CharField(max_length=50, blank=True, null=True)
    razorpay_bank_fund_account_id = models.CharField(max_length=50, blank=True, null=True)
    razorpay_payout_id = models.CharField(max_length=50, blank=True)
    razorpay_transaction_id = models.CharField(max_length=50, blank=True)
    razorpay_utr_no = models.CharField(max_length=50, blank=True)
    entity = models.CharField(max_length=50, blank=True, null=True)
    mode = models.CharField(max_length=50, blank=True, null=True)
    amount = models.FloatField(default=0)
    currency = models.CharField(max_length=50)

    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return str(self.user.email)


class PaymentGateway(models.Model):
    provider = models.CharField(max_length=50, blank=True, null=True)
    enabled = models.BooleanField(default=False)

    active = models.BooleanField(default=False)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return str(self.provider)
