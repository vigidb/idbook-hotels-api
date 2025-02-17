from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin, Permission
from django.db import models
from rest_framework.authtoken.models import Token
from django.db.models import Q
from django.db.models.signals import pre_save, post_save
from django.db.models.signals import post_save
from django.dispatch import receiver

from django.core.validators import (EmailValidator, RegexValidator)
from IDBOOKAPI.utils import (unique_key_generator, unique_referral_id_generator)

from IDBOOKAPI.basic_resources import OTP_TYPE_CHOICES, OTP_FOR_CHOICES


class UserOtp(models.Model):
    otp = models.PositiveIntegerField(help_text="otp")
    otp_type = models.CharField(max_length=25, choices=OTP_TYPE_CHOICES,
                                default='EMAIL', help_text="otp generated medium")
    user_account =  models.CharField(max_length=100, help_text="Email or Mobile Number")
    otp_for = models.CharField(max_length=25, choices=OTP_FOR_CHOICES,
                                default='OTHER')
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)


class Role(models.Model):
    name = models.CharField(max_length=50, unique=True, help_text="Name of the role.")
    short_code = models.CharField(max_length=3, default='', unique=True, db_index=True, help_text="Short code representing the role.")
    permissions = models.ManyToManyField(Permission, help_text="Select permissions associated with this role.")

    def __str__(self):
        return f'{self.name}_{self.short_code}'


class UserManager(BaseUserManager):
    def create_user(self, email, mobile_number, password=None, **extra_fields):
        if not email:
            raise ValueError("Users must have an email address")
        if not mobile_number:
            raise ValueError("Users must have a Mobile Number")
        if not password:
            raise ValueError("Users must have a password")
        email = self.normalize_email(email)
        user = self.model(email=email, mobile_number=mobile_number, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, mobile_number, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        return self.create_user(email, mobile_number, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    roles = models.ManyToManyField('Role', related_name='user_role', blank=True,
                                   help_text="Select roles associated with this user.")
    email = models.EmailField(db_index=True, validators=[EmailValidator],
                              null=True, blank=True, help_text="Email address of the user.")
    mobile_number = models.CharField(max_length=10, db_index=True, blank=True, null=True,
                                     validators=[RegexValidator(regex=r'^\+?1?\d{9,15}$',
                                                                message='Enter a valid phone number')],
                                     help_text="Mobile number of the user (10 digits only).")
    name = models.CharField(max_length=30, null=True, blank=True, help_text="Name of the user.")
    first_name = models.CharField(max_length=30, null=True, blank=True, help_text="First name of the user.")
    last_name = models.CharField(max_length=30, null=True, blank=True, help_text="Last name of the user.")

    referral = models.CharField(max_length=120, blank=True, help_text="Referral code associated with the user.")
    referred_code = models.CharField(max_length=120, blank=True, help_text="Referred by user code.")
    custom_id = models.CharField(max_length=15, blank=True, db_index=True, help_text="Custom ID for the user.")
    category = models.CharField(max_length=20, blank=True, help_text="Category of the user.")
    business_id = models.BigIntegerField(null=True, blank=True, help_text="Business detail id")
    company_id = models.BigIntegerField(null=True, blank=True, help_text="company detail id")
    first_booking = models.BooleanField(default=False, help_text="Status for first confirmed booking")

    email_verified = models.BooleanField(default=False, help_text="Whether the user's email address is verified.")
    mobile_verified = models.BooleanField(default=False, help_text="Whether the user's mobile number is verified.")

    is_active = models.BooleanField(default=True, help_text="Whether the user account is active.")
    is_staff = models.BooleanField(default=False, help_text="Whether the user has staff privileges.")
    default_group = models.CharField(max_length=30, null=True, help_text="Switched group")

    created = models.DateTimeField(auto_now_add=True, help_text="Date and time when the user account was created.")
    updated = models.DateTimeField(auto_now=True, help_text="Date and time when the user account was last updated.")

    # USERNAME_FIELD = 'mobile_number'
    USERNAME_FIELD = 'id'
    # REQUIRED_FIELDS = ['email',]

    objects = UserManager()

    def __str__(self):
        if self.email:
            return str(self.email)
        elif self.mobile_number:
            return str(self.mobile_number)
        else:
            return str(self.id)
    
    def get_short_name(self):
        return self.first_name

    def get_full_name(self):
        name = self.name if self.name else ''
        return name

    def has_perm(self, perm, obj=None):
        return True

    def has_module_perms(self, app_label):
        return True

    @property
    def is_admin(self):
        return self.is_superuser

    @property
    def is_customer(self):
        return False


##def post_save_user_create_receiver(sender, instance, created, *args, **kwargs):
##
##    if not instance.referral:
##        instance.referral = unique_referral_id_generator(instance)
##
##    if created:
##        Token.objects.get_or_create(user=instance)
##
##
##post_save.connect(post_save_user_create_receiver, sender=User)


# if role created then group with same name will be created
# @receiver(post_save, sender=Role)
# def create_group_for_role(sender, instance, created, **kwargs):
#     if created:
#         # Create a group with the same name as the Role object
#         Group.objects.get_or_create(name=instance.name.title())
#
#
# post_save.connect(create_group_for_role, sender=Role)


# @receiver(post_save, sender=Role)
# def create_group_for_role(sender, instance, created, **kwargs):
#     if created:
#         # Create a group with a unique name based on the Role object's name and short_code
#         group_name = f"{instance.name.title()}_{instance.short_code}"
#         Group.objects.get_or_create(name=group_name)
#
# post_save.connect(create_group_for_role, sender=Role)


# @receiver(post_save, sender=User)
# def assign_user_to_group(sender, instance, created, **kwargs):
#     if created:
#         # Automatically assign the user to the groups corresponding to their roles
#         for role in instance.roles.all():
#             group_name = f"{role.name.title()}_{role.short_code}"
#             try:
#                 group = Group.objects.get(name=group_name)
#                 instance.groups.add(group)
#             except Group.DoesNotExist:
#                 pass
#
#
# post_save.connect(assign_user_to_group, sender=User)
