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
from apps.authentication.models import User

from IDBOOKAPI.utils import (unique_key_generator, unique_referral_id_generator, )
from IDBOOKAPI.validators import get_filename, validate_file_extension, calculate_age, MinAgeValidator
from IDBOOKAPI.basic_resources import (ENQUIRY_CHOICES, STATE_CHOICES, IMAGE_TYPE_CHOICES, COUNTRY_CHOICES)

from django.core.validators import (EmailValidator, RegexValidator)


class AmenityCategory(models.Model):
    title = models.CharField(max_length=200, unique=True)

    active = models.BooleanField(default=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title

    class Meta:
        verbose_name_plural = 'Amenity_Categories'


class Amenity(models.Model):
    amenity_category = models.ForeignKey(AmenityCategory, on_delete=models.DO_NOTHING, related_name='amenity_category')
    title = models.CharField(max_length=200, unique=True)

    active = models.BooleanField(default=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title

    class Meta:
        verbose_name_plural = 'Amenities'


class RoomType(models.Model):
    title = models.CharField(max_length=30, unique=True)

    active = models.BooleanField(default=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title


class Occupancy(models.Model):
    title = models.CharField(max_length=30, unique=True)

    active = models.BooleanField(default=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title


class Address(models.Model):
    full_address = models.CharField(max_length=100, help_text="Full address")
    district = models.CharField(max_length=50, help_text="District")
    state = models.CharField(max_length=50, choices=STATE_CHOICES, default='', help_text="State")
    country = models.CharField(max_length=50, choices=COUNTRY_CHOICES, default='INDIA',
                               help_text="Country")
    pin_code = models.PositiveIntegerField(default=000000, help_text="PIN code")

# class FCMToken(models.Model):
#     user = models.ForeignKey(User, on_delete=models.DO_NOTHING, null=True, related_name='fcm_user')
#     fcm_token = models.CharField(max_length=200, unique=True)
#     token_type = models.CharField(max_length=10, choices=FCM_TOKEN_CHOICE, default='android')
#     user_type = models.CharField(max_length=25, choices=USER_TYPE_CHOICE, default='customer')
#
#     active = models.BooleanField(default=True)
#     created = models.DateTimeField(auto_now_add=True)
#     updated = models.DateTimeField(auto_now=True)
#
#     def __str__(self):
#         return f'{self.fcm_token}'
#
#
# class KYCDocument(models.Model):
#     user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='kyc_document')
#     document_type = models.CharField(max_length=15, choices=KYC_DOCUMENT_CHOICES, default='Others')
#     upload_document = models.CharField(max_length=255, blank=True, null=True)
#     full_name = models.CharField(max_length=100, blank=True, null=True)
#     pan_number = models.CharField(max_length=10, blank=True, null=True)
#     date_of_birth = models.DateField(blank=True, null=True)
#     upload_pan_card = models.CharField(max_length=255, blank=True, null=True)
#     status = models.CharField(max_length=10, choices=KYC_STATUS_CHOICES, default='Others')
#
#     active = models.BooleanField(default=False)
#     created = models.DateTimeField(auto_now_add=True)
#     updated = models.DateTimeField(auto_now=True)
#
#     def __str__(self):
#         return str(self.user.email)
#

class BankDetail(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='bank_detail')
    bank_name = models.CharField(max_length=100, blank=True, null=True)
    account_holder_name = models.CharField(max_length=100, blank=True, null=True)
    account_number = models.CharField(max_length=15, blank=True, null=True)
    repeat_account_number = models.CharField(max_length=15, blank=True, null=True)
    ifsc = models.CharField(max_length=15, blank=True, null=True)
    # paytm_number = models.CharField(max_length=10, blank=True, null=True)
    # google_pay_number = models.CharField(max_length=10, blank=True, null=True)
    # phonepe_number = models.CharField(max_length=10, blank=True, null=True)
    upi = models.CharField(max_length=50, blank=True, null=True)
    qrcode = models.ImageField()
    payment_url = models.URLField()

    razorpay_vpa_fund_account_id = models.CharField(max_length=100, blank=True, null=True)
    razorpay_bank_fund_account_id = models.CharField(max_length=100, blank=True, null=True)

    active = models.BooleanField(default=False)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return str(self.user.email)


class CompanyDetail(models.Model):
    #user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='company_detail')
    added_user = models.ForeignKey(User, on_delete=models.CASCADE,
                                   related_name='company_list', null=True, blank=True)

    company_name = models.CharField(max_length=50)
    brand_name = models.CharField(max_length=100, null=True, blank=True)
    company_logo = models.FileField(upload_to='company/logo/', blank=True, null=True)
    company_phone = models.CharField(max_length=50, null=True, blank=True,
                                     validators=[RegexValidator(regex=r'^\+?1?\d{9,15}$',
                                                                message='Enter a valid phone number')])
    company_email = models.EmailField(validators=[EmailValidator],
                              null=True, blank=True, help_text="Email address of the company.")
    domain_name = models.CharField(max_length=50, blank=True, null=True)
    company_website = models.URLField(null=True, blank=True)
    gstin_no = models.CharField(max_length=100, null=True)
    pan_no = models.CharField(max_length=100, blank=True)
    registered_address = models.TextField(blank=True, null=True)

    contact_person_name = models.CharField(max_length=50, null=True, blank=True)
    contact_number = models.CharField(max_length=10, null=True, blank=True,
                                      validators=[RegexValidator(regex=r'^\+?1?\d{9,15}$',
                                                                message='Enter a valid phone number')])
    designation = models.CharField(max_length=50, null=True, blank=True)
    contact_email_address = models.EmailField(validators=[EmailValidator],
                                              null=True, blank=True, help_text="Email address of the contact person.")
    
    district = models.CharField(max_length=20, null=True, blank=True)
    state = models.CharField(max_length=30, choices=STATE_CHOICES, default='')
    country = models.CharField(max_length=25, default='INDIA')
    pin_code = models.PositiveIntegerField(null=True, blank=True)

    location = models.CharField(max_length=255, null=True, blank=True,
                                help_text="Google map URL")
    latitude = models.FloatField(default=0, help_text="Latitude")
    longitude = models.FloatField(default=0, help_text="Longitude")
    approved = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True, help_text="Whether the company is active.")


class UploadedMedia(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='uploaded_by', blank=True, null=True)
    title = models.CharField(max_length=200, blank=True, null=True)
    file_name = models.CharField(max_length=200, blank=True, null=True)
    file_id = models.CharField(max_length=200, blank=True, null=True)
    caption = models.CharField(max_length=200, blank=True, null=True)
    url = models.URLField(blank=True, null=True)
    tags = models.TextField(blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    size = models.PositiveIntegerField(default=0)
    height = models.PositiveIntegerField(default=0)
    width = models.PositiveIntegerField(default=0)
    type = models.CharField(max_length=20, blank=True, null=True)
    version_name = models.CharField(max_length=200, blank=True, null=True)
    version_id = models.CharField(max_length=200, blank=True, null=True)
    thumbnail_url = models.URLField(blank=True, null=True)

    active = models.BooleanField(default=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)



# class PayoutCalculation(models.Model):
#     user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='payout_calculation_user')
#     # txn = models.ForeignKey('Transaction', blank=True, null=True, on_delete=models.CASCADE, related_name='txns')
#     total_referral = models.PositiveSmallIntegerField(default=0, blank=True, null=True)
#     referral = models.CharField(max_length=250, blank=True, null=True)
#     total_earning = models.TextField(blank=True, null=True)
#     note = models.CharField(max_length=250, blank=True, null=True)
#
#     active = models.BooleanField(default=False)
#     created = models.DateTimeField(auto_now_add=True)
#     updated = models.DateTimeField(auto_now=True)
#
#     def __str__(self):
#         return str(self.user.email)
#
#
# class Banners(models.Model):
#     user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='banners_user')
#     upload_banner = models.FileField(upload_to='banners', blank=True,
#                                      validators=[FileExtensionValidator(allowed_extensions=['png', 'jpeg', 'jpg'])],
#                                      help_text='Max size 2MB, and only pdf are allowed')
#
#     active = models.BooleanField(default=False)
#     created = models.DateTimeField(auto_now_add=True)
#     updated = models.DateTimeField(auto_now=True)
#
#     def __str__(self):
#         return str(self.user.email)
#
#     def get_absolute_url(self):
#         return reverse('banners_detail', kwargs={"id": self.id})
#
#     class Meta:
#         verbose_name_plural = 'Banners'
#
#
# class Deposit(models.Model):
#     user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='deposit_user')
#     balance = models.FloatField(default=0, blank=True, null=True)
#     info = models.CharField(max_length=15, blank=True, null=True)
#     status = models.CharField(max_length=15, choices=DEPOSIT_STATUS, default="Completed")
#
#     active = models.BooleanField(default=False)
#     created = models.DateTimeField(auto_now_add=True)
#     updated = models.DateTimeField(auto_now=True)
#
#     def __str__(self):
#         return str(self.user.email)
#
#
# class Wallet(models.Model):
#     user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='wallet_user')
#     balance = models.FloatField(default=0, blank=True, null=True)
#
#     active = models.BooleanField(default=True)
#     created = models.DateTimeField(auto_now_add=True)
#     updated = models.DateTimeField(auto_now=True)
#
#     def __str__(self):
#         return str(self.user.email)
#
#
# class AdminWallet(models.Model):
#     balance = models.FloatField(default=0, blank=True, null=True)
#     admin_charges = models.FloatField(default=0, blank=True, null=True)
#     admin_charges_collected = models.FloatField(default=0, blank=True, null=True)
#     total_withdrawn = models.FloatField(default=0, blank=True, null=True)
#
#     active = models.BooleanField(default=True)
#     created = models.DateTimeField(auto_now_add=True)
#     updated = models.DateTimeField(auto_now=True)
#
#     def __str__(self):
#         return str(self.balance)
#
#
# class Withdrawal(models.Model):
#     user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='withdrawal')
#     balance = models.PositiveIntegerField(default=0)
#     txn_type = models.CharField(max_length=20, choices=TXN_TYPE_CHOICES, default='Others')
#     info = models.CharField(max_length=15, blank=True, null=True)
#     method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES, default='Others')
#     status = models.CharField(max_length=10, choices=PAYMENT_STATUS_CHOICES, default='Others')
#
#     active = models.BooleanField(default=True)
#     created = models.DateTimeField(auto_now_add=True)
#     updated = models.DateTimeField(auto_now=True)
#
#     def __str__(self):
#         return str(self.user.email)
#
#
# class Transaction(models.Model):
#     user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='transaction')
#     balance = models.FloatField(default=0)
#     txn_type = models.CharField(max_length=20, choices=TXN_TYPE_CHOICES, default='Others')
#     info = models.CharField(max_length=250, blank=True, null=True)
#     method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES, default='Others')
#     status = models.CharField(max_length=10, choices=PAYMENT_STATUS_CHOICES, default='Others')
#
#     active = models.BooleanField(default=True)
#     created = models.DateTimeField(auto_now_add=True)
#     updated = models.DateTimeField(auto_now=True)
#
#     def __str__(self):
#         return str(self.user.email)
#
#
# class Notification(models.Model):
#     user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notification_user')
#     contest_name = models.CharField(max_length=150, blank=True, null=True)
#     contest_description = models.TextField(blank=True, null=True)
#     match = models.CharField(max_length=250, blank=True, null=True)
#
#     active = models.BooleanField(default=False)
#     created = models.DateTimeField(auto_now_add=True)
#     updated = models.DateTimeField(auto_now=True)
#
#     def __str__(self):
#         return str(self.user.email)


class Enquiry(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='user_enquiry')
    replied_by = models.ForeignKey(User, on_delete=models.CASCADE, blank=True, null=True, related_name='user_reply')
    subject = models.CharField(max_length=150, choices=ENQUIRY_CHOICES, default='Other')
    enquiry_msg = models.TextField(blank=True, null=True)
    enquiry_reply = models.TextField(blank=True, null=True)
    read = models.BooleanField(default=False)

    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ('created',)

    def __str__(self):
        return 'Reply by {} on {}'.format(self.replied_by, self.user)


class AboutUs(models.Model):
    title = models.CharField(max_length=150, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    image = models.ImageField(upload_to='about/', blank=True, null=True)

    active = models.BooleanField(default=False)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title


class PrivacyPolicy(models.Model):
    title = models.CharField(max_length=150, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    image = models.ImageField(upload_to='privacy-policy/', blank=True, null=True)

    active = models.BooleanField(default=False)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title


class RefundAndCancellationPolicy(models.Model):
    title = models.CharField(max_length=150, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    image = models.ImageField(upload_to='refund-and-cancellation-policy/', blank=True, null=True)

    active = models.BooleanField(default=False)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title


class TermsAndConditions(models.Model):
    title = models.CharField(max_length=150, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    image = models.ImageField(upload_to='terms-and-conditions/', blank=True, null=True)

    active = models.BooleanField(default=False)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title


class Legality(models.Model):
    title = models.CharField(max_length=150, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    image = models.ImageField(upload_to='legality/', blank=True,null=True)

    active = models.BooleanField(default=False)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title


class Career(models.Model):
    title = models.CharField(max_length=150, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    image = models.ImageField(upload_to='career/', blank=True,null=True)

    active = models.BooleanField(default=False)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title


class FAQs(models.Model):
    title = models.CharField(max_length=150, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    image = models.ImageField(upload_to='faqs/', blank=True,null=True)

    active = models.BooleanField(default=False)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title

class CountryDetails(models.Model):
    country_name = models.CharField(max_length=150, blank=True, null=True)
    country_short_name = models.CharField(max_length=20, blank=True, null=True)
    country_phone_code = models.CharField(max_length=10, blank=True, null=True)
    country_details = models.JSONField(blank=True, null=True)

    def __str__(self):
        return self.country_name


class UserNotification(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='user_notifications')
    title = models.CharField(max_length=150, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    is_read = models.BooleanField(default=False)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.user.email
    
