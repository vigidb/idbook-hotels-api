from django.contrib import admin
from .models import BusinessDetail


@admin.register(BusinessDetail)
class BusinessDetailAdmin(admin.ModelAdmin):
    """
    Admin interface for Business Detail management
    """
    list_display = (
        "id",
        "business_name",
        "user",
        "gstin_no",
        "state",
        "country",
        "active",
        "created",
    )
    list_display_links = ("id", "business_name")
    list_editable = ("active",)
    search_fields = (
        "business_name",
        "gstin_no",
        "pan_no",
        "business_email",
        "business_phone",
        "user__email",
        "user__mobile_number",
    )
    list_filter = (
        "active",
        "state",
        "country",
        "created",
    )
    readonly_fields = (
        "created",
        "updated",
        "role_count_display",
    )
    fieldsets = (
        ("Business Information", {
            "fields": (
                "user",
                "business_name",
                "business_logo",
                "business_email",
                "business_phone",
                "website_url",
            )
        }),
        ("Address & Location", {
            "fields": (
                "full_address",
                "state",
                "country",
            )
        }),
        ("Tax & Legal", {
            "fields": (
                "gstin_no",
                "pan_no",
                "hsn_sac_no",
            )
        }),
        ("Domain", {
            "fields": ("domain_name",)
        }),
        ("Status", {
            "fields": ("active", "role_count_display")
        }),
        ("Timestamps", {
            "fields": ("created", "updated"),
            "classes": ("collapse",)
        }),
    )
    ordering = ("-created",)
    list_per_page = 50
    date_hierarchy = "created"
    autocomplete_fields = ("user",)
    
    def role_count_display(self, obj):
        """Display count of roles for this business"""
        if obj.pk:
            count = obj.roles.count()
            return f"{count} role(s) defined"
        return "Save business first to assign roles"
    role_count_display.short_description = "Roles"
    
    def get_queryset(self, request):
        """Optimize queryset"""
        return super().get_queryset(request).select_related("user").prefetch_related("roles")
