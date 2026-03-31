from django.contrib.auth.models import (
    AbstractBaseUser,
    BaseUserManager,
    PermissionsMixin,
    Permission,
    Group,
)
from django.db import models
from rest_framework.authtoken.models import Token
from django.db.models import Q
from django.db.models.signals import pre_save, post_save
from django.db.models.signals import post_save
from django.dispatch import receiver

from django.core.validators import EmailValidator, RegexValidator
from IDBOOKAPI.utils import unique_key_generator, unique_referral_id_generator

from IDBOOKAPI.basic_resources import OTP_TYPE_CHOICES, OTP_FOR_CHOICES


class UserOtp(models.Model):
    otp = models.PositiveIntegerField(help_text="otp")
    otp_type = models.CharField(
        max_length=25,
        choices=OTP_TYPE_CHOICES,
        default="EMAIL",
        help_text="otp generated medium",
    )
    user_account = models.CharField(max_length=100, help_text="Email or Mobile Number")
    otp_for = models.CharField(max_length=25, choices=OTP_FOR_CHOICES, default="OTHER")
    otp_generate_tries = models.PositiveIntegerField(
        default=1, help_text="Number of OTP generation attempts"
    )
    login_tries = models.PositiveIntegerField(
        default=0, help_text="Number of OTP login attempts"
    )
    pwd_reset_tries = models.PositiveIntegerField(
        default=0, help_text="Number of password reset OTP attempts"
    )
    verify_tries = models.PositiveIntegerField(
        default=0, help_text="Number of signup OTP verification attempts"
    )
    last_attempt_time = models.DateTimeField(
        auto_now=True, help_text="Last OTP generation attempt time"
    )
    last_login_attempt_time = models.DateTimeField(
        null=True, blank=True, help_text="Last OTP login attempt time"
    )
    last_pwd_reset_attempt_time = models.DateTimeField(
        null=True, blank=True, help_text="Last password reset OTP attempt time"
    )
    last_verify_attempt_time = models.DateTimeField(
        null=True, blank=True, help_text="Last signup OTP verification attempt time"
    )
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)


# NOTE: GroupMetadata and PermissionMetadata removed - using Django's built-in fields directly
# Groups: Use group.name directly (already contains codes like "BUSINESS-GRP")
# Permissions: Use utility function get_permission_code() to convert Django format to custom format

class Role(models.Model):
    name = models.CharField(max_length=50, help_text="Name of the role.")
    short_code = models.CharField(
        max_length=3,
        default="",
        db_index=True,
        help_text="Short code representing the role.",
    )
    description = models.TextField(
        blank=True,
        null=True,
        help_text="Detailed description of what this role does and its responsibilities."
    )
    permissions = models.ManyToManyField(
        Permission, help_text="Select permissions associated with this role."
    )
    business = models.ForeignKey(
        "org_managements.BusinessDetail",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="roles",
        help_text="Business this role belongs to. Null for system roles."
    )
    group = models.ForeignKey(
        Group,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="roles",
        help_text="Django Group this role belongs to (e.g., BUSINESS-GRP, CORPORATE-GRP)."
    )
    is_system_role = models.BooleanField(
        default=False,
        help_text="Whether this is a system role (BUS-ADMIN, CORP-ADMIN, etc.)."
    )
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [["name", "business", "is_system_role"]]
        ordering = ("name",)
        indexes = [
            models.Index(fields=["business", "is_system_role"]),
            models.Index(fields=["group", "is_system_role"]),
            models.Index(fields=["name", "is_system_role"]),
        ]

    def __str__(self):
        if self.business:
            return f"{self.name}_{self.short_code} ({self.business.business_name})"
        return f"{self.name}_{self.short_code} (System)"


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
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        return self.create_user(email, mobile_number, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    roles = models.ManyToManyField(
        "Role",
        related_name="user_role",
        blank=True,
        help_text="Select roles associated with this user.",
    )
    email = models.EmailField(
        db_index=True,
        validators=[EmailValidator],
        null=True,
        blank=True,
        help_text="Email address of the user.",
    )
    mobile_number = models.CharField(
        max_length=10,
        db_index=True,
        blank=True,
        null=True,
        validators=[
            RegexValidator(
                regex=r"^\+?1?\d{9,15}$", message="Enter a valid phone number"
            )
        ],
        help_text="Mobile number of the user (10 digits only).",
    )
    name = models.CharField(
        max_length=255, null=True, blank=True, help_text="Name of the user."
    )
    first_name = models.CharField(
        max_length=150, null=True, blank=True, help_text="First name of the user."
    )
    last_name = models.CharField(
        max_length=150, null=True, blank=True, help_text="Last name of the user."
    )

    referral = models.CharField(
        max_length=120, blank=True, help_text="Referral code associated with the user."
    )
    referred_code = models.CharField(
        max_length=120, blank=True, help_text="Referred by user code."
    )
    custom_id = models.CharField(
        max_length=15, blank=True, db_index=True, help_text="Custom ID for the user."
    )
    category = models.CharField(
        max_length=20, blank=True, help_text="Category of the user."
    )
    business_id = models.BigIntegerField(
        null=True, blank=True, help_text="Business detail id"
    )
    company_id = models.BigIntegerField(
        null=True, blank=True, help_text="company detail id"
    )
    first_booking = models.BooleanField(
        default=False, help_text="Status for first confirmed booking"
    )

    email_verified = models.BooleanField(
        default=False, help_text="Whether the user's email address is verified."
    )
    mobile_verified = models.BooleanField(
        default=False, help_text="Whether the user's mobile number is verified."
    )

    is_active = models.BooleanField(
        default=True, help_text="Whether the user account is active."
    )
    is_staff = models.BooleanField(
        default=False, help_text="Whether the user has staff privileges."
    )
    default_group = models.CharField(
        max_length=30, null=True, help_text="Switched group"
    )

    created = models.DateTimeField(
        auto_now_add=True, help_text="Date and time when the user account was created."
    )
    updated = models.DateTimeField(
        auto_now=True, help_text="Date and time when the user account was last updated."
    )

    # USERNAME_FIELD = 'mobile_number'
    USERNAME_FIELD = "id"
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
        name = self.name if self.name else ""
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


class UserRole(models.Model):
    """User-Role-Business assignment with region/association scoping"""
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="user_roles",
        help_text="User this role is assigned to."
    )
    role = models.ForeignKey(
        Role,
        on_delete=models.CASCADE,
        related_name="user_roles",
        help_text="Role assigned to the user."
    )
    business = models.ForeignKey(
        "org_managements.BusinessDetail",
        on_delete=models.CASCADE,
        related_name="user_roles",
        help_text="Business this role assignment belongs to."
    )
    region = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        db_index=True,
        help_text="Region code for region-based access (e.g., TN, KA)."
    )
    association_id = models.BigIntegerField(
        null=True,
        blank=True,
        db_index=True,
        help_text="Association ID for association-based access (company_id, hotel_id, or agent_id)."
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this role assignment is active."
    )
    assigned_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_roles",
        help_text="User who assigned this role."
    )
    assigned_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When this role was assigned."
    )
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [["user", "role", "business", "association_id"]]
        ordering = ("-assigned_at",)
        indexes = [
            models.Index(fields=["user", "business", "is_active"]),
            models.Index(fields=["user", "association_id", "is_active"]),
            models.Index(fields=["business", "is_active"]),
        ]
        verbose_name = "User Role Assignment"
        verbose_name_plural = "User Role Assignments"

    def __str__(self):
        scope = ""
        if self.region:
            scope = f" [Region: {self.region}]"
        if self.association_id:
            scope += f" [Association: {self.association_id}]"
        return f"{self.user.email or self.user.mobile_number} - {self.role.name}{scope}"


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
