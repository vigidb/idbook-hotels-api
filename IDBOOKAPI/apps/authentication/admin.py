from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.admin import GroupAdmin as BaseGroupAdmin
from django.utils.translation import gettext_lazy as _
from django.db.models import Q

from .models import Role, UserOtp, UserRole

User = get_user_model()


# Custom Filter for Scope
class ScopeFilter(admin.SimpleListFilter):
    """Filter UserRole by scope restrictions"""
    title = _('Scope Restrictions')
    parameter_name = 'scope'

    def lookups(self, request, model_admin):
        return (
            ('has_restrictions', _('Has Scope Restrictions')),
            ('no_restrictions', _('No Restrictions (Full Access)')),
            ('region_only', _('Region Only')),
            ('association_only', _('Association Only')),
            ('both', _('Region + Association')),
        )

    def queryset(self, request, queryset):
        if self.value() == 'has_restrictions':
            return queryset.filter(
                Q(region__isnull=False) | Q(association_id__isnull=False)
            )
        elif self.value() == 'no_restrictions':
            return queryset.filter(region__isnull=True, association_id__isnull=True)
        elif self.value() == 'region_only':
            return queryset.filter(region__isnull=False, association_id__isnull=True)
        elif self.value() == 'association_only':
            return queryset.filter(region__isnull=True, association_id__isnull=False)
        elif self.value() == 'both':
            return queryset.filter(region__isnull=False, association_id__isnull=False)
        return queryset


# Inline Admin for UserRole
class UserRoleInline(admin.TabularInline):
    """Inline admin for UserRole assignments within User admin"""
    model = UserRole
    extra = 0
    fields = ("role", "business", "scope_summary_inline", "is_active", "assigned_at")
    readonly_fields = ("assigned_at", "scope_summary_inline")
    autocomplete_fields = ("role", "business")
    verbose_name = "Role Assignment"
    verbose_name_plural = "Role Assignments"
    
    def get_queryset(self, request):
        """Optimize queryset"""
        return super().get_queryset(request).select_related("role", "business", "role__group")
    
    def scope_summary_inline(self, obj):
        """Display scope summary in inline"""
        if obj.pk:
            parts = []
            if obj.region:
                parts.append(f"📍{obj.region}")
            if obj.association_id:
                if obj.role and obj.role.group:
                    group_name = obj.role.group.name
                    if "CORPORATE" in group_name:
                        parts.append(f"🏢{obj.association_id}")
                    elif "AGENT" in group_name:
                        parts.append(f"👤{obj.association_id}")
                    elif "HOTELIER" in group_name:
                        parts.append(f"🏨{obj.association_id}")
                    else:
                        parts.append(f"🔗{obj.association_id}")
                else:
                    parts.append(f"🔗{obj.association_id}")
            
            if parts:
                return " | ".join(parts)
            return "🌐 Unrestricted"
        return "-"
    scope_summary_inline.short_description = "Scope"


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
        return qs.select_related().prefetch_related("roles", "groups", "user_roles")
    
    # Add inline for UserRole assignments
    def get_inline_instances(self, request, obj=None):
        """Add UserRole inline when editing existing user"""
        if obj and obj.pk:
            return [UserRoleInline(self.model, self.admin_site)]
        return []


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
    Admin interface for Role management with enhanced display
    """
    list_display = (
        "id",
        "name",
        "short_code",
        "business",
        "group",
        "is_system_role",
        "permission_count",
        "created",
    )
    list_display_links = ("id", "name")
    list_editable = ("is_system_role",)
    search_fields = ("name", "short_code", "description", "business__business_name")
    list_filter = (
        "is_system_role",
        "group",
        "business",
        "created",
    )
    filter_horizontal = ("permissions",)
    readonly_fields = ("created", "updated", "permission_count_display")
    fieldsets = (
        ("Basic Information", {
            "fields": ("name", "short_code", "description")
        }),
        ("Organization", {
            "fields": ("business", "group", "is_system_role")
        }),
        ("Permissions", {
            "fields": ("permissions", "permission_count_display"),
            "description": "Select permissions for this role. Use Ctrl/Cmd+Click to select multiple."
        }),
        ("Timestamps", {
            "fields": ("created", "updated"),
            "classes": ("collapse",)
        }),
    )
    ordering = ("-is_system_role", "name")
    list_per_page = 50
    date_hierarchy = "created"
    
    def permission_count(self, obj):
        """Display count of permissions"""
        return obj.permissions.count()
    permission_count.short_description = "Permissions"
    
    def permission_count_display(self, obj):
        """Display permission count in detail view"""
        if obj.pk:
            count = obj.permissions.count()
            return f"{count} permission(s) assigned"
        return "Save role first to assign permissions"
    permission_count_display.short_description = "Permission Count"
    
    def get_queryset(self, request):
        """Optimize queryset"""
        return super().get_queryset(request).select_related(
            "business", "group"
        ).prefetch_related("permissions")


@admin.register(UserRole)
class UserRoleAdmin(admin.ModelAdmin):
    """
    Admin interface for User Role assignments with scope management
    """
    list_display = (
        "id",
        "user",
        "role",
        "business",
        "scope_summary",
        "is_active",
        "assigned_by",
        "assigned_at",
    )
    list_display_links = ("id", "user")
    list_editable = ("is_active",)
    search_fields = (
        "user__email",
        "user__mobile_number",
        "user__name",
        "role__name",
        "business__business_name",
        "region",
        "association_id",
    )
    list_filter = (
        "is_active",
        "role",
        "business",
        "region",
        "role__group",
        ScopeFilter,
        "assigned_at",
    )
    readonly_fields = (
        "created",
        "updated",
        "assigned_at",
        "scope_description_display",
        "scope_type_display",
    )
    fieldsets = (
        ("Assignment", {
            "fields": ("user", "role", "business", "assigned_by")
        }),
        ("Access Scope", {
            "fields": (
                "region",
                "association_id",
                "scope_type_display",
                "scope_description_display",
            ),
            "description": "Set region and/or association restrictions for this role assignment. Leave blank for unrestricted access."
        }),
        ("Status", {
            "fields": ("is_active",)
        }),
        ("Timestamps", {
            "fields": ("assigned_at", "created", "updated"),
            "classes": ("collapse",)
        }),
    )
    ordering = ("-assigned_at",)
    list_per_page = 50
    date_hierarchy = "assigned_at"
    
    def scope_summary(self, obj):
        """Display concise scope summary in list view"""
        parts = []
        if obj.region:
            parts.append(f"📍 {obj.region}")
        if obj.association_id:
            if obj.role and obj.role.group:
                group_name = obj.role.group.name
                if "CORPORATE" in group_name:
                    parts.append(f"🏢 Co:{obj.association_id}")
                elif "AGENT" in group_name:
                    parts.append(f"👤 Ag:{obj.association_id}")
                elif "HOTELIER" in group_name:
                    parts.append(f"🏨 Ho:{obj.association_id}")
                else:
                    parts.append(f"🔗 {obj.association_id}")
            else:
                parts.append(f"🔗 {obj.association_id}")
        
        if parts:
            return " | ".join(parts)
        return "🌐 Unrestricted"
    scope_summary.short_description = "Scope"
    
    def scope_type_display(self, obj):
        """Display scope type classification"""
        has_region = bool(obj.region)
        has_association = bool(obj.association_id)
        
        if has_region and has_association:
            return "📍 Region + Association (Most Restricted)"
        elif has_region:
            return "📍 Region Only"
        elif has_association:
            return "🔗 Association Only"
        else:
            return "🌐 No Restrictions (Full Access)"
    scope_type_display.short_description = "Scope Type"
    
    def scope_description_display(self, obj):
        """Display detailed human-readable scope description"""
        scope_parts = []
        if obj.region:
            scope_parts.append(f"📍 Region: {obj.region}")
        if obj.association_id:
            if obj.role and obj.role.group:
                group_name = obj.role.group.name
                if "CORPORATE" in group_name:
                    scope_parts.append(f"🏢 Company ID: {obj.association_id}")
                elif "AGENT" in group_name:
                    scope_parts.append(f"👤 Agent ID: {obj.association_id}")
                elif "HOTELIER" in group_name:
                    scope_parts.append(f"🏨 Hotel ID: {obj.association_id}")
                else:
                    scope_parts.append(f"🔗 Association ID: {obj.association_id}")
            else:
                scope_parts.append(f"🔗 Association ID: {obj.association_id}")
        
        if scope_parts:
            return " | ".join(scope_parts)
        return "🌐 No scope restrictions (all regions/associations)"
    scope_description_display.short_description = "Scope Details"
    
    
    def get_queryset(self, request):
        """Optimize queryset"""
        return super().get_queryset(request).select_related(
            "user", "role", "business", "assigned_by", "role__group"
        )


# Enhanced Group Admin - Unregister default and register custom
admin.site.unregister(Group)

@admin.register(Group)
class GroupAdmin(BaseGroupAdmin):
    """
    Enhanced Group Admin with better organization
    """
    list_display = ("id", "name", "user_count")
    search_fields = ("name",)
    list_filter = ("name",)
    ordering = ("name",)
    
    def user_count(self, obj):
        """Display count of users in group"""
        return obj.user_set.count()
    user_count.short_description = "Users"


# Enhanced Permission Admin - Unregister default if exists and register custom
try:
    admin.site.unregister(Permission)
except admin.sites.NotRegistered:
    pass  # Permission might not be registered yet

@admin.register(Permission)
class PermissionAdmin(admin.ModelAdmin):
    """
    Enhanced Permission Admin with better organization
    """
    list_display = (
        "id",
        "name",
        "codename",
        "content_type",
        "permission_code_display",
        "module_display",
    )
    list_filter = ("content_type",)
    search_fields = ("name", "codename", "content_type__app_label", "content_type__model")
    ordering = ("content_type__app_label", "codename")
    list_per_page = 100
    
    def permission_code_display(self, obj):
        """Display custom permission code"""
        from apps.authentication.utils.permission_utils import get_permission_code
        return get_permission_code(obj)
    permission_code_display.short_description = "Permission Code"
    
    def module_display(self, obj):
        """Display module name"""
        codename = obj.codename
        if '_' in codename:
            parts = codename.split('_', 1)
            if len(parts) > 1:
                return parts[1]
        return obj.content_type.app_label
    module_display.short_description = "Module"


# Customize admin site headers
admin.site.site_title = "IDBookHotels Admin Panel"
admin.site.site_header = "IDBookHotels Administration"
admin.site.index_title = "Welcome to IDBookHotels Administration"

# Customize app verbose names for better organization
# Note: Django's built-in auth app will still show as "Authentication and Authorization"
# This is controlled by Django's internal configuration
