from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import AbstractUser, Permission
from django.contrib.auth.admin import UserAdmin

# from django.contrib.auth.forms import UserChangeForm, UserCreationForm
from .models import Role, UserOtp

User = get_user_model()


# class CustomUserChangeForm(UserChangeForm):
#     class Meta(UserChangeForm.Meta):
#         model = User
#
#
# class CustomUserCreationForm(UserCreationForm):
#     class Meta(UserCreationForm.Meta):
#         model = User


# class CustomUserAdmin(UserAdmin):
#     form = CustomUserChangeForm
#     add_form = CustomUserCreationForm
#     fieldsets = UserAdmin.fieldsets + (
#         ('Roles', {'fields': ('roles',)}),
#     )
#
#
# admin.site.register(User, CustomUserAdmin)
# admin.site.unregister(Group)
# admin.site.register(Group, GroupAdmin)
# admin.site.register(Permission)


@admin.register(User)
class CustomUserAdmin(BaseUserAdmin):
    """
    Enhanced User Admin with comprehensive search, filters, and display options
    """
    # List display - columns shown in the list view
    list_display = (
        "id",
        "custom_id",
        "email",
        "mobile_number",
        "name",
        "email_verified",
        "mobile_verified",
        "is_active",
        "is_staff",
        "is_superuser",
        "first_booking",
        "created",
    )
    
    # Fields that can be clicked to edit
    list_display_links = ("id", "email", "custom_id")
    
    # Fields that can be edited directly from the list view
    list_editable = ("is_active", "is_staff", "email_verified", "mobile_verified")
    
    # Search fields - fields that can be searched
    search_fields = (
        "email",
        "mobile_number",
        "name",
        "first_name",
        "last_name",
        "custom_id",
        "referral",
        "referred_code",
    )
    
    # List filters - sidebar filters
    list_filter = (
        "is_active",
        "is_staff",
        "is_superuser",
        "email_verified",
        "mobile_verified",
        "first_booking",
        "created",
        "updated",
    )
    
    # Date hierarchy - allows filtering by date
    date_hierarchy = "created"
    
    # Ordering - default sorting
    ordering = ("-created",)
    
    # Fieldsets - organization of fields in the detail view
    fieldsets = (
        ("Authentication", {
            "fields": ("email", "password")
        }),
        ("Personal Information", {
            "fields": ("name", "first_name", "last_name", "mobile_number")
        }),
        ("Account Details", {
            "fields": (
                "custom_id",
                "referral",
                "referred_code",
            )
        }),
        ("Verification Status", {
            "fields": ("email_verified", "mobile_verified", "first_booking")
        }),
        ("Relationships", {
            "fields": ("business_id", "company_id", "roles", "groups")
        }),
        ("Permissions", {
            "fields": (
                "is_active",
                "is_staff",
                "is_superuser",
                "user_permissions",
            )
        }),
        ("Important Dates", {
            "fields": ("created", "updated", "last_login")
        }),
    )
    
    # Fieldsets for adding a new user
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("email", "password1", "password2", "mobile_number", "name")
        }),
    )
    
    # Filter horizontal for many-to-many fields
    filter_horizontal = ("roles", "groups", "user_permissions")
    
    # Readonly fields - fields that cannot be edited
    readonly_fields = ("created", "updated", "last_login", "id")
    
    # Number of items per page
    list_per_page = 50
    
    # Show full result count
    show_full_result_count = True
    
    # Preserve filters on save
    preserve_filters = True
    
    def get_queryset(self, request):
        """Optimize queryset with select_related and prefetch_related"""
        qs = super().get_queryset(request)
        return qs.select_related().prefetch_related("roles", "groups")
admin.site.register(Permission)
# Remove Group Model from admin. We're not using it.
# admin.site.unregister(Group)


@admin.register(UserOtp)
class UserOtpAdmin(admin.ModelAdmin):
    """
    Admin interface for User OTP management
    """
    list_display = (
        "id",
        "user_account",
        "otp",
        "otp_type",
        "otp_for",
        "otp_generate_tries",
        "verify_tries",
        "login_tries",
        "created",
        "last_attempt_time",
    )
    list_filter = (
        "otp_type",
        "otp_for",
        "created",
        "last_attempt_time",
    )
    search_fields = ("user_account", "otp", "otp_for")
    readonly_fields = (
        "created",
        "last_attempt_time",
        "last_login_attempt_time",
        "last_pwd_reset_attempt_time",
        "last_verify_attempt_time",
    )
    date_hierarchy = "created"
    ordering = ("-created",)
    list_per_page = 50


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    """
    Admin interface for Role management
    """
    list_display = ("id", "name", "short_code")
    search_fields = ("name", "short_code")
    list_filter = ("name",)
    ordering = ("name",)

admin.site.site_title = "IDBookHotels Admin Panel"
admin.site.site_header = "IDBookHotels"
admin.site.index_title = "Welcome to IDBookHotels"
