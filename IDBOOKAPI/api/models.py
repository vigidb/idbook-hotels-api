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

# send_mail(subject, message, from_email, recipient_list, html_message)
DEFAULT_ACTIVATION_DAYS = getattr(settings, 'DEFAULT_ACTIVATION_DAYS', 7)


class UserManager(BaseUserManager):
    def create_user(self, email, mobile_number, password=None, is_active=False, is_staff=False, is_admin=False,
                    is_customer=True,
                    is_hotel_owner=True, is_hotel_staff=False,
                    is_agent=True, is_manager=False, is_managers=False):
        if not email:
            raise ValueError("Users must have an email address")
        if not mobile_number:
            raise ValueError("Users must have a mobile_number Number")
        if not password:
            raise ValueError("Users must have a password")
        user = self.model(
            email = self.normalize_email(email),
        )
        user.set_password(password)
        user.is_active = is_active
        user.staff = is_staff
        user.admin = is_admin
        user.customer = is_customer
        user.shop_owner = is_shop_owner
        user.stylist = is_stylist
        user.agent = is_agent
        user.manager = is_manager
        user.save(using=self._db)
        return user

    def create_customer(self, email, mobile_number, password=None):
        user = self.create_user(
                email, mobile_number,
                password=password,
                is_customer=True
        )
        return user

    def create_shop_owner(self, email, mobile_number, password=None):
        user = self.create_user(
                email, mobile_number,
                password=password,
                is_shop_owner=True
        )
        return user

    def create_stylist(self, email, mobile_number, password=None):
        user = self.create_user(
                email, mobile_number,
                password=password,
                is_stylist=True
        )
        return user

    def create_agent(self, email, mobile_number, password=None):
        user = self.create_user(
                email, mobile_number,
                password=password,
                is_agent=True
        )
        return user

    def create_manager(self, email, mobile_number, password=None):
        user = self.create_user(
                email, mobile_number,
                password=password,
                is_manager=True
        )
        return user

    def create_staffuser(self, email, mobile_number, password=None):
        user = self.create_user(
                email, mobile_number,
                password=password,
                is_staff=True,
                is_active=True,
                is_customer=True,
                is_shop_owner=True,
                is_stylist=True,
                is_agent=True,
                is_manager=True
        )
        return user

    def create_superuser(self, email, mobile_number, password=None):
        user = self.create_user(
                email, mobile_number,
                password=password,
                is_staff=True,
                is_admin=True,
                is_active=True,
                is_customer=True,
                is_shop_owner=True,
                is_stylist=True,
                is_agent=True,
                is_manager=True
        )
        return user


class User(AbstractBaseUser):
    email = models.EmailField(db_index=True, validators=[EmailValidator], unique=True)
    mobile_number = models.CharField(max_length=10, db_index=True, unique=True,
                              validators=[RegexValidator(regex=r'^\+?1?\d{9,15}$',
                                                         message='Enter a valid phone number')],
                              )
    first_name = models.CharField(max_length=30)
    last_name = models.CharField(max_length=30, null=True, blank=True, )
    gender = models.CharField(max_length=20, choices=GENDER_CHOICES, default='Other')
    date_of_birth = models.DateField(auto_now=False, auto_now_add=False, validators=[MinAgeValidator(18)], blank=True,
                                     null=True)
    profile_picture = models.CharField(max_length=255, blank=True, null=True)
    education = models.CharField(max_length=25, choices=EDUCATION_CHOICES, default='Others')

    reference = models.ForeignKey('self', null=True, blank=True, on_delete=models.SET_NULL)
    referral = models.CharField(max_length=120, blank=True)
    level = models.PositiveIntegerField(default=0)  # for organizational use only

    # razorpay payment gateway
    razorpay_customer_id = models.CharField(max_length=50, blank=True)
    razorpay_order_id = models.CharField(max_length=50, blank=True)
    razorpay_payment_id = models.CharField(max_length=50, blank=True)
    razorpay_contact_id = models.CharField(max_length=50, blank=True)

    # firebase
    # fcm_token = models.CharField(max_length=250, blank=True)

    email_verified = models.BooleanField(default=False)
    mobile_number_verified = models.BooleanField(default=False)

    customer = models.BooleanField(default=False)
    shop_owner = models.BooleanField(default=False)  # if paid verified manually by admin
    subscription = models.BooleanField(default=False)
    stylist = models.BooleanField(default=False)
    agent = models.BooleanField(default=False)
    manager = models.BooleanField(default=False)

    paid = models.BooleanField(default=False)  # paid for mega membership
    eligible = models.BooleanField(default=False)  # referred at least one user
    blocked = models.BooleanField(default=False)
    payment_received = models.BooleanField(default=False)

    is_active = models.BooleanField(default=False)
    staff = models.BooleanField(default=False)

    admin = models.BooleanField(default=False)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['mobile_number',]

    objects = UserManager()

    def __str__(self):
        return self.email

    def get_short_name(self):
        return self.first_name

    def get_full_name(self):
        return "{} {}".format(self.first_name, self.last_name)

    def has_perm(self, perm, obj=None):
        return True

    def has_module_perms(self, app_label):
        return True

    @property
    def is_staff(self):
        if self.is_admin:
            return True
        return self.staff

    @property
    def is_admin(self):
        return self.admin

    @property
    def is_customer(self):
        return self.customer

    @property
    def is_shop_owner(self):
        return self.shop_owner

    @property
    def is_stylist(self):
        return self.stylist

    @property
    def is_agent(self):
        return self.agent

    @property
    def is_manager(self):
        return self.manager


def post_save_user_create_receiver(sender, instance, created, *args, **kwargs):

    if not instance.referral:
        instance.referral = unique_referral_id_generator(instance)

    if created:
        # ProfileDetail.objects.create(user=instance)
        BankDetail.objects.create(user=instance)
        KYCDocument.objects.create(user=instance)
        Wallet.objects.create(user=instance)
        Token.objects.get_or_create(user=instance)


post_save.connect(post_save_user_create_receiver, sender=User)


class FCMToken(models.Model):
    user = models.ForeignKey(User, on_delete=models.DO_NOTHING, null=True, related_name='fcm_user')
    fcm_token = models.CharField(max_length=200, unique=True)
    token_type = models.CharField(max_length=10, choices=FCM_TOKEN_CHOICE, default='android')
    user_type = models.CharField(max_length=25, choices=USER_TYPE_CHOICE, default='customer')

    active = models.BooleanField(default=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'{self.fcm_token}'


class ShopDetail(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='shop_owner_user')
    services = models.ManyToManyField('Service', related_name='services', blank=True)
    stylists = models.ManyToManyField('Stylist', related_name='stylists', blank=True)
    service_category = models.CharField(max_length=255, choices=SERVICE_CATEGORY_TYPE_CHOICES, default='')

    full_image = models.CharField(max_length=255, blank=True, null=True)
    cropped_image = models.CharField(max_length=255, blank=True, null=True)

    name = models.CharField(max_length=255, blank=True, null=True)
    description = models.CharField(max_length=255, blank=True, null=True)
    other_info = models.CharField(max_length=255, blank=True, null=True)
    about = models.TextField(blank=True, null=True)

    review = models.FloatField(default=0)

    full_address = models.CharField(max_length=100, blank=True, null=True)
    district = models.CharField(max_length=20, blank=True, null=True)
    state = models.CharField(max_length=30, choices=STATE_CHOICES, default='')
    country = models.CharField(max_length=15, default='INDIA')
    pin_code = models.PositiveIntegerField(blank=True, null=True)

    location = models.CharField(max_length=255, blank=True, null=True, help_text="Google map url")
    area_name = models.CharField(max_length=60, null=True, blank=True, help_text="Area Name")
    city_name = models.CharField(max_length=35, null=True, blank=True, help_text="City Name")
    latitude = models.FloatField(default=0, help_text="latitude")
    longitude = models.FloatField(default=0, help_text="longitude")

    google_map_located = models.BooleanField(default=False)
    blocked = models.BooleanField(default=False)
    featured = models.BooleanField(default=False)

    active = models.BooleanField(default=False)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    # def get_absolute_url(self):
    #     return reverse("profile_detail", kwargs={"pk": self.pk})

    def __str__(self):
        return str(self.name)


def post_save_shop_detail_create_receiver(sender, instance, created, *args, **kwargs):

    if created:
        WorkingDay.objects.create(shop=instance, day_name="Sunday", opening_time="09:00:00", closing_time="23:00:00")
        WorkingDay.objects.create(shop=instance, day_name="Monday", opening_time="09:00:00", closing_time="23:00:00")
        WorkingDay.objects.create(shop=instance, day_name="Tuesday", opening_time="09:00:00", closing_time="23:00:00")
        WorkingDay.objects.create(shop=instance, day_name="Wednesday", opening_time="09:00:00", closing_time="23:00:00")
        WorkingDay.objects.create(shop=instance, day_name="Thursday", opening_time="09:00:00", closing_time="23:00:00")
        WorkingDay.objects.create(shop=instance, day_name="Friday", opening_time="09:00:00", closing_time="23:00:00")
        WorkingDay.objects.create(shop=instance, day_name="Saturday", opening_time="09:00:00", closing_time="23:00:00")


post_save.connect(post_save_shop_detail_create_receiver, sender=ShopDetail)


class Gallery(models.Model):
    shop = models.ForeignKey(ShopDetail, on_delete=models.CASCADE, related_name='gallery')
    # upload_image = models.FileField(upload_to='gallery', blank=True,
    #                                  validators=[FileExtensionValidator(allowed_extensions=['png', 'jpeg', 'jpg'])],
    #                                  help_text='Max size 2MB, and only pdf are allowed')
    upload_image = models.CharField(max_length=255, blank=True, null=True)

    active = models.BooleanField(default=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return str(self.shop.name)

    class Meta:
        verbose_name_plural = 'Gallery'


class WorkingDay(models.Model):
    shop = models.ForeignKey(ShopDetail, null=True, blank=True, on_delete=models.CASCADE, related_name='shop_working_day')
    day_name = models.CharField(max_length=20, choices=WORKING_DAYS, default='Sunday')
    is_working = models.BooleanField(default=True)
    opening_time = models.TimeField(auto_now=False, auto_now_add=False, blank=True, null=True,
                                    help_text='Time should be in 18:12:00 this format')
    closing_time = models.TimeField(auto_now=False, auto_now_add=False, blank=True, null=True,
                                    help_text='Time should be in 18:12:00 this format')

    active = models.BooleanField(default=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return "{} is {} for {}".format(self.day_name, 'working' if self.is_working else 'not working', self.shop)

    class Meta:
        unique_together = ('shop', 'day_name',)


class Stylist(models.Model):
    shop = models.ForeignKey(ShopDetail, on_delete=models.CASCADE, related_name='stylist')
    mobile_number = models.CharField(max_length=10, db_index=True, unique=True,
                              validators=[RegexValidator(regex=r'^\+?1?\d{9,15}$',
                                                         message='Enter a valid phone number')],
                              default='9999999999'
                              )
    first_name = models.CharField(max_length=30, null=True, blank=True)
    last_name = models.CharField(max_length=30, null=True, blank=True)
    gender = models.CharField(max_length=20, choices=GENDER_CHOICES, default='Other')
    date_of_birth = models.DateField(auto_now=False, auto_now_add=False, validators=[MinAgeValidator(18)], blank=True,
                                     null=True)
    profile_picture = models.CharField(max_length=255, blank=True, null=True)
    education = models.CharField(max_length=25, choices=EDUCATION_CHOICES, default='Others')
    experience = models.CharField(max_length=25)
    review = models.FloatField(default=0)

    active = models.BooleanField(default=False)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return str(self.first_name)

    class Meta:
        verbose_name_plural = 'Stylists'


class Service(models.Model):
    shop = models.ForeignKey(ShopDetail, on_delete=models.CASCADE, related_name='shop_services')
    service_type = models.CharField(max_length=25, choices=SERVICE_TYPE_CHOICES, default='Others')
    icon = models.CharField(max_length=255, blank=True, null=True)
    service_charge = models.FloatField(default=0)
    required_time = models.DurationField(blank=True, null=True,
                                         help_text='It must be in [DD] [[HH:]MM:]ss[.uuuuuu] format.')

    active = models.BooleanField(default=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('shop', 'service_type')


class Appointment(models.Model):
    stylist = models.ForeignKey(Stylist, on_delete=models.CASCADE, related_name='stylist_appointment')
    user = models.ForeignKey(User, on_delete=models.DO_NOTHING, blank=True, null=True, related_name='user_appointment')
    service_taken = models.ManyToManyField(Service, related_name='service_taken')
    service_charge = models.FloatField(default=0)
    discount = models.FloatField(default=0)
    total = models.FloatField(default=0)
    booked_slot = models.DateTimeField(auto_now=False, auto_now_add=False)
    time_required = models.DurationField(blank=True, null=True,
                                         help_text='It must be in [DD] [[HH:]MM:]ss[.uuuuuu] format.')
    exit_time = models.DateTimeField(auto_now=False, auto_now_add=False, null=True)

    status = models.CharField(max_length=20, choices=APPOINTMENT_STATUS, default='Waiting')
    completed = models.BooleanField(default=False)

    active = models.BooleanField(default=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)


class Review(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='user_comment')
    shop = models.ForeignKey(ShopDetail, on_delete=models.CASCADE, null=True, blank=True, related_name='shop_review')
    # stylist = models.ForeignKey(Stylist, on_delete=models.CASCADE, null=True, blank=True, related_name='stylist_review')

    shop_cleanliness = models.PositiveSmallIntegerField(default=5)
    tools_cleanliness = models.PositiveSmallIntegerField(default=5)
    behaviour = models.PositiveSmallIntegerField(default=5)
    style = models.PositiveSmallIntegerField(default=5)
    value_for_money = models.PositiveSmallIntegerField(default=5)
    waiting_time = models.PositiveSmallIntegerField(default=5)
    review = models.PositiveSmallIntegerField(default=5)
    body = models.TextField()

    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    active = models.BooleanField(default=False)

    class Meta:
        ordering = ('created',)
        unique_together = ("user", "shop")

    def __str__(self):
        return 'Review by {} on {}'.format(self.user.email, self.shop)


class KYCDocument(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='kyc_document')
    document_type = models.CharField(max_length=15, choices=KYC_DOCUMENT_CHOICES, default='Others')
    upload_document = models.CharField(max_length=255, blank=True, null=True)
    full_name = models.CharField(max_length=100, blank=True, null=True)
    pan_number = models.CharField(max_length=10, blank=True, null=True)
    date_of_birth = models.DateField(blank=True, null=True)
    upload_pan_card = models.CharField(max_length=255, blank=True, null=True)
    status = models.CharField(max_length=10, choices=KYC_STATUS_CHOICES, default='Others')

    active = models.BooleanField(default=False)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return str(self.user.email)


class BankDetail(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='bank_detail')
    bank_name = models.CharField(max_length=100, blank=True, null=True)
    account_holder_name = models.CharField(max_length=100, blank=True, null=True)
    account_number = models.CharField(max_length=15, blank=True, null=True)
    repeat_account_number = models.CharField(max_length=15, blank=True, null=True)
    ifsc = models.CharField(max_length=15, blank=True, null=True)
    paytm_number = models.CharField(max_length=10, blank=True, null=True)
    google_pay_number = models.CharField(max_length=10, blank=True, null=True)
    phonepe_number = models.CharField(max_length=10, blank=True, null=True)
    upi = models.CharField(max_length=50, blank=True, null=True)

    razorpay_vpa_fund_account_id = models.CharField(max_length=100, blank=True, null=True)
    razorpay_bank_fund_account_id = models.CharField(max_length=100, blank=True, null=True)

    active = models.BooleanField(default=False)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return str(self.user.email)


class PayoutCalculation(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='payout_calculation_user')
    # txn = models.ForeignKey('Transaction', blank=True, null=True, on_delete=models.CASCADE, related_name='txns')
    total_referral = models.PositiveSmallIntegerField(default=0, blank=True, null=True)
    referral = models.CharField(max_length=250, blank=True, null=True)
    total_earning = models.TextField(blank=True, null=True)
    note = models.CharField(max_length=250, blank=True, null=True)

    active = models.BooleanField(default=False)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return str(self.user.email)


class Banners(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='banners_user')
    upload_banner = models.FileField(upload_to='banners', blank=True,
                                     validators=[FileExtensionValidator(allowed_extensions=['png', 'jpeg', 'jpg'])],
                                     help_text='Max size 2MB, and only pdf are allowed')

    active = models.BooleanField(default=False)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return str(self.user.email)

    def get_absolute_url(self):
        return reverse('banners_detail', kwargs={"id": self.id})

    class Meta:
        verbose_name_plural = 'Banners'


class Deposit(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='deposit_user')
    balance = models.FloatField(default=0, blank=True, null=True)
    info = models.CharField(max_length=15, blank=True, null=True)
    status = models.CharField(max_length=15, choices=DEPOSIT_STATUS, default="Completed")

    active = models.BooleanField(default=False)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return str(self.user.email)


class Wallet(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='wallet_user')
    balance = models.FloatField(default=0, blank=True, null=True)

    active = models.BooleanField(default=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return str(self.user.email)


class AdminWallet(models.Model):
    balance = models.FloatField(default=0, blank=True, null=True)
    admin_charges = models.FloatField(default=0, blank=True, null=True)
    admin_charges_collected = models.FloatField(default=0, blank=True, null=True)
    total_withdrawn = models.FloatField(default=0, blank=True, null=True)

    active = models.BooleanField(default=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return str(self.balance)


# class Active(models.Model):
#     user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='active_user')
#     balance = models.FloatField(default=0, blank=True, null=True)
#     info = models.CharField(max_length=15, blank=True, null=True)
#     status = models.CharField(max_length=15, choices=ACTIVE_STATUS, default="Completed")
#
#     active = models.BooleanField(default=True)
#     created = models.DateTimeField(auto_now_add=True)
#     updated = models.DateTimeField(auto_now=True)
#
#     def __str__(self):
#         return str(self.user.email)


class Withdrawal(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='withdrawal')
    balance = models.PositiveIntegerField(default=0)
    txn_type = models.CharField(max_length=20, choices=TXN_TYPE_CHOICES, default='Others')
    info = models.CharField(max_length=15, blank=True, null=True)
    method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES, default='Others')
    status = models.CharField(max_length=10, choices=PAYMENT_STATUS_CHOICES, default='Others')

    active = models.BooleanField(default=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return str(self.user.email)


class Transaction(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='transaction')
    balance = models.FloatField(default=0)
    txn_type = models.CharField(max_length=20, choices=TXN_TYPE_CHOICES, default='Others')
    info = models.CharField(max_length=250, blank=True, null=True)
    method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES, default='Others')
    status = models.CharField(max_length=10, choices=PAYMENT_STATUS_CHOICES, default='Others')

    active = models.BooleanField(default=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return str(self.user.email)


class Notification(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notification_user')
    contest_name = models.CharField(max_length=150, blank=True, null=True)
    contest_description = models.TextField(blank=True, null=True)
    match = models.CharField(max_length=250, blank=True, null=True)

    active = models.BooleanField(default=False)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return str(self.user.email)

#
# class Category(models.Model):
#     category = models.CharField(max_length=200, primary_key=True)
#
#     class Meta:
#         db_table = 'Category'
#
#     def __str__(self):
#         return self.category
#
#     def save(self, *args, **kwargs):
#         self.slug = slugify(self.category)
#         super(Category, self).save(*args, **kwargs)
#
#
# class Post(models.Model):
#     user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='post_user')
#     category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='post_category')
#     title = models.CharField(max_length=250)
#     slug = models.SlugField(max_length=250, unique_for_date='publish')
#     body = models.TextField()
#     picture_gallery = models.ImageField(upload_to='blog/images/', blank=True)
#     author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='blog_posts')
#     active = models.BooleanField(default=False)
#     featured = models.BooleanField(default=False)
#     publish = models.DateTimeField(default=timezone.now)
#     created = models.DateTimeField(auto_now_add=True)
#     updated = models.DateTimeField(auto_now=True)
#
#     class Meta:
#         ordering = ('publish',)
#
#     def save(self, *args, **kwargs):
#         self.slug = slugify(self.title)
#         super(Post, self).save(*args, **kwargs)
#
#     def __str__(self):
#         return self.title
#
#
# class Comment(models.Model):
#     user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='user_comment')
#     post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='comments')
#     name = models.CharField(max_length=80)
#     email = models.EmailField()
#     body = models.TextField()
#     created = models.DateTimeField(auto_now_add=True)
#     updated = models.DateTimeField(auto_now=True)
#     active = models.BooleanField(default=False)
#
#     class Meta:
#         ordering = ('created',)
#
#     def __str__(self):
#         return 'Comment by {} on {}'.format(self.name, self.post)


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



class HotelQuerySet(models.query.QuerySet):
    def active(self):
        return self.filter(active=True)

    def featured(self):
        return self.filter(featured=True, active=True)

    def search(self, query):
        lookups = (Q(title__icontains=query) |
                  Q(description__icontains=query) |
                  Q(price__icontains=query) |
                  Q(city__icontains=query)
                  )

        return self.filter(lookups).distinct()


class HotelManager(models.Manager):
    def get_queryset(self):
        return HotelQuerySet(self.model, using=self._db)

    def all(self):
        return self.get_queryset().active()

    def featured(self):
        return self.get_queryset().featured()

    def get_by_id(self, id, slug):
        qs = self.get_queryset().filter(id=id, slug=slug)
        if qs.count() == 1:
            return qs.first()
        return None

    def search(self, query):
        return self.get_queryset().active().search(query)


class Hotel(models.Model):
    # Hotel Detail
    title               = models.CharField(max_length=30, db_index=True)
    slug                = models.SlugField(max_length=200, db_index=True)

    # Hotel Address
    address             = models.CharField(max_length=250)
    city                = models.CharField(max_length=250)
    state               = models.CharField(max_length=250)
    postal_code         = models.CharField(max_length=100)

    # Hotel Contact
    email               = models.EmailField(null=True,blank=True)
    phone_no            = models.CharField(max_length=15)
    description         = models.TextField(blank=True)
    picture             = models.ImageField(upload_to='hotels/%Y/%m/%d', blank=True)

    starting_price      = models.DecimalField(max_digits=10, decimal_places=2)

    # Direction
    latitude            = models.CharField(null=True,blank=True,max_length=250)
    longitude           = models.CharField(null=True,blank=True,max_length=250)

    # Basic amenities
    elevator            = models.BooleanField(default=False)
    wifi                = models.BooleanField(default=False)
    fitness_center      = models.BooleanField(default=False)
    taxi                = models.BooleanField(default=False)
    breakfast           = models.BooleanField(default=False)
    parking             = models.BooleanField(default=False)
    air_condition       = models.BooleanField(default=False)
    smoking_zone        = models.BooleanField(default=False)
    wheelchair          = models.BooleanField(default=False)
    restaurant          = models.BooleanField(default=False)
    couple_friendly     = models.BooleanField(default=False)
    hourly_booking      = models.BooleanField(default=False)

    discount            = models.IntegerField(validators=[MinValueValidator(0),
                                                          MaxValueValidator(100)])

    person_name         = models.CharField(max_length=30, db_index=True)
    GENDER_CHOICES      = (
        ('M', 'Male'),
        ('F', 'Female'),
    )
    gender              = models.CharField(max_length=1, choices=GENDER_CHOICES)
    contact_no          = models.CharField(max_length=15)
    person_detail       = models.TextField(blank=True)
    person_age          = models.IntegerField(validators=[MinValueValidator(18),
                                                          MaxValueValidator(100)])
    person_photo        = models.ImageField(upload_to='hotels/person/', blank=True)

    manager_name        = models.CharField(max_length=30, null=True, blank=True, db_index=True)
    GENDER_CHOICES = (
        ('M', 'Male'),
        ('F', 'Female'),
    )
    manager_gender      = models.CharField(null=True,blank=True, max_length=1,
                                           choices=GENDER_CHOICES)
    manager_contact_no  = models.CharField(null=True,blank=True,max_length=15)
    manager_detail      = models.TextField(null=True,blank=True,)
    manager_age         = models.IntegerField(null=True,blank=True,
                                              validators=[MinValueValidator(18),
                                                          MaxValueValidator(100)])
    manager_photo       = models.ImageField(upload_to='hotels/person/', blank=True)

    room_picture_1      = models.ImageField(upload_to='hotels/rooms//%Y/%m/%d', blank=True)
    room_picture_2      = models.ImageField(upload_to='hotels/rooms//%Y/%m/%d', blank=True)
    room_picture_3      = models.ImageField(upload_to='hotels/rooms//%Y/%m/%d', blank=True)
    room_picture_4      = models.ImageField(upload_to='hotels/rooms//%Y/%m/%d', blank=True)
    room_picture_5      = models.ImageField(upload_to='hotels/rooms//%Y/%m/%d', blank=True)
    room_picture_6      = models.ImageField(upload_to='hotels/rooms//%Y/%m/%d', blank=True)
    room_picture_7      = models.ImageField(upload_to='hotels/rooms//%Y/%m/%d', blank=True)
    room_picture_8      = models.ImageField(upload_to='hotels/rooms//%Y/%m/%d', blank=True)
    room_picture_9      = models.ImageField(upload_to='hotels/rooms//%Y/%m/%d', blank=True)

    featured            = models.BooleanField(default=False)
    active              = models.BooleanField(default=False)
    author              = models.ForeignKey(settings.AUTH_USER_MODEL,
                                            on_delete=models.CASCADE, related_name='hotel')
    created             = models.DateTimeField(auto_now_add=True)
    updated             = models.DateTimeField(auto_now=True)

    objects             = models.Manager()  # The default manager.
    published           = HotelManager()  # Our custom manager.

    def save(self, *args, **kwargs):
        self.slug = slugify(self.city)
        self.slug = slugify(self.title)
        super(Hotel, self).save(*args, **kwargs)


    def __str__(self):
        return self.title

    class Meta:
        ordering = ('-created',)
        verbose_name = 'hotel'
        verbose_name_plural = 'hotels'
        index_together = (('id', 'slug'),)

    def get_absolute_url(self):
            return reverse('app:hotel-detail', args=[self.id, self.slug])


class Room(models.Model):
    hotel           = models.ForeignKey(Hotel, related_name='rooms', on_delete=models.CASCADE)

    ROOM_CHOICES    = (('DELUXE ROOM', 'DELUXE'), ('CLASSIC ROOM', 'CLASSIC'),
                       ('PREMIUM ROOM', 'PREMIUM'))
    room_type       = models.CharField(max_length=25, choices=ROOM_CHOICES,blank=True)

    TIME_SLOTS      = (('4 HOURS', 4), ('8 HOURS', 8),
                       ('12 HOURS',12), ('24 HOURS',24))
    time_duration   = models.CharField(max_length=25,choices=TIME_SLOTS,blank=True)

    CHOICES         = ((1, 1), (2, 2), (3, 3),(4, 4), (5, 5))
    person_capacity = models.PositiveSmallIntegerField(choices=CHOICES, default=0)
    child_capacity  = models.PositiveSmallIntegerField(choices=CHOICES, default=0)

    price           = models.DecimalField(max_digits=6, decimal_places=2,null=True,blank=True)

    availability    = models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        # self.slug = slugify(self.hotel)
        self.slug = slugify(self.room_type)
        super(Room, self).save(*args, **kwargs)


    def __str__(self):
        return str(self.room_type)

    class Meta:
        ordering = ('-price',)
        verbose_name = 'room'
        verbose_name_plural = 'rooms'
        index_together = (('id', 'room_type'),)

    # def get_absolute_url(self):
    #         return reverse('app:hotel-detail', args=[self.id, self.slug])


class Reviews(models.Model):
    hotel       = models.ForeignKey(Hotel, on_delete=models.CASCADE, related_name='reviews')
    name        = models.CharField(max_length=80)
    email       = models.EmailField(blank=True,null=True)
    body        = models.TextField(blank=True,null=True)

    cleanliness = models.DecimalField(max_digits=3, decimal_places=2)
    comfort     = models.DecimalField(max_digits=3, decimal_places=2)
    staff       = models.DecimalField(max_digits=3, decimal_places=2)
    facilities  = models.DecimalField(max_digits=3, decimal_places=2)
    over_all    = models.DecimalField(max_digits=3, decimal_places=2)

    created     = models.DateTimeField(auto_now_add=True)
    updated     = models.DateTimeField(auto_now=True)
    active      = models.BooleanField(default=True)

    class Meta:
        ordering = ('created',)

    def __str__(self):
        return 'Reviews by {} on {}'.format(self.name, self.hotel)
