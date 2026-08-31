from django.contrib import admin

from apps.messaging.models import (
    Campaign,
    CampaignContact,
    CampaignStep,
    Contact,
    ContactUploadSession,
    EmailTemplate,
    MessageLog,
    MessagingProviderConfig,
)


@admin.register(Contact)
class ContactAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "name",
        "email",
        "phone",
        "group_type",
        "city",
        "country",
        "is_blacklisted",
        "opt_out_email",
        "opt_out_sms",
        "updated_at",
    )
    list_filter = (
        "group_type",
        "country",
        "city",
        "is_blacklisted",
        "opt_out_email",
        "opt_out_sms",
        "opt_out_whatsapp",
    )
    search_fields = ("name", "email", "phone", "department", "remarks")
    readonly_fields = ("created_at", "updated_at")
    autocomplete_fields = ("user",)


@admin.register(ContactUploadSession)
class ContactUploadSessionAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "file_name",
        "status",
        "total_rows",
        "success_count",
        "failure_count",
        "created_count",
        "updated_count",
        "duplicate_in_file_count",
        "created_at",
        "finished_at",
    )
    list_filter = ("status", "created_at", "finished_at")
    search_fields = ("file_name",)
    readonly_fields = ("created_at", "finished_at")
    autocomplete_fields = ("uploaded_by",)


@admin.register(MessagingProviderConfig)
class MessagingProviderConfigAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "channel",
        "name",
        "is_default",
        "active",
        "rate_limit_per_minute",
        "updated_at",
    )
    list_filter = ("channel", "is_default", "active")
    search_fields = ("name",)
    readonly_fields = ("created_at", "updated_at")


@admin.register(EmailTemplate)
class EmailTemplateAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "name",
        "slug",
        "is_marketing",
        "is_active",
        "provider",
        "updated_at",
    )
    list_filter = ("is_marketing", "is_active")
    search_fields = ("name", "slug", "subject")
    readonly_fields = ("created_at", "updated_at")
    autocomplete_fields = ("provider", "created_by")


class CampaignStepInline(admin.TabularInline):
    model = CampaignStep
    extra = 0
    fields = (
        "order_index",
        "channel",
        "template_code",
        "delay_amount",
        "delay_unit",
        "active",
        "messaging_provider",
    )


@admin.register(Campaign)
class CampaignAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "name",
        "status",
        "target_group_type",
        "schedule_time",
        "repeat_every_days",
        "created_by",
        "updated_at",
    )
    list_filter = ("status", "target_group_type", "schedule_time")
    search_fields = ("name", "description")
    readonly_fields = ("created_at", "updated_at")
    autocomplete_fields = ("created_by", "repeat_from_campaign")
    inlines = (CampaignStepInline,)


@admin.register(CampaignStep)
class CampaignStepAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "campaign",
        "order_index",
        "channel",
        "template_code",
        "delay_amount",
        "delay_unit",
        "active",
        "messaging_provider",
    )
    list_filter = ("channel", "delay_unit", "active")
    search_fields = ("campaign__name", "template_code")
    autocomplete_fields = ("campaign", "messaging_provider")
    readonly_fields = ("created_at", "updated_at")


@admin.register(CampaignContact)
class CampaignContactAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "campaign",
        "step",
        "contact",
        "status",
        "scheduled_at",
        "sent_at",
        "updated_at",
    )
    list_filter = ("status", "step__channel", "scheduled_at", "sent_at")
    search_fields = (
        "campaign__name",
        "contact__name",
        "contact__email",
        "contact__phone",
        "provider_message_id",
        "error_code",
        "error_message",
    )
    autocomplete_fields = ("campaign", "step", "contact")
    readonly_fields = ("created_at", "updated_at")


@admin.register(MessageLog)
class MessageLogAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "campaign",
        "step",
        "contact",
        "channel",
        "status",
        "provider",
        "sent_at",
        "created_at",
    )
    list_filter = ("channel", "status", "provider", "sent_at", "created_at")
    search_fields = (
        "campaign__name",
        "contact__name",
        "contact__email",
        "contact__phone",
        "provider",
    )
    autocomplete_fields = ("campaign", "step", "contact")
    readonly_fields = ("created_at",)
