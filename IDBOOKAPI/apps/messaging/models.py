from django.conf import settings
from django.db import models

from apps.authentication.constants import ALL_GROUP_CHOICES
from apps.authentication.models import User


class Contact(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="messaging_contacts",
    )
    name = models.CharField(max_length=255, blank=True)
    phone = models.CharField(max_length=32, blank=True, db_index=True)
    email = models.EmailField(blank=True, db_index=True)
    city = models.CharField(max_length=128, blank=True)
    country = models.CharField(max_length=128, blank=True)
    group_type = models.CharField(
        max_length=32, choices=ALL_GROUP_CHOICES, db_index=True
    )
    # free-form segmentation tags for flexible targeting
    segment_tags = models.JSONField(default=list, blank=True)
    # internal notes (e.g. VIP, preferred channel, past issues)
    remarks = models.TextField(blank=True)
    # department/team for corporate/B2B targeting (e.g. Sales, HR, Front desk)
    department = models.CharField(max_length=128, blank=True, db_index=True)

    opt_out_sms = models.BooleanField(default=False)
    opt_out_email = models.BooleanField(default=False)
    opt_out_whatsapp = models.BooleanField(default=False)
    is_blacklisted = models.BooleanField(default=False)

    source = models.CharField(max_length=64, blank=True, help_text="e.g. excel_upload")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["group_type", "city"]),
            models.Index(fields=["group_type", "country"]),
        ]

    def __str__(self) -> str:
        return self.name or self.phone or self.email or f"Contact {self.pk}"


class ContactUploadSession(models.Model):
    class Status(models.TextChoices):
        PROCESSING = "processing", "Processing"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"

    uploaded_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="contact_upload_sessions",
    )
    file_name = models.CharField(max_length=255)
    status = models.CharField(
        max_length=32, choices=Status.choices, default=Status.PROCESSING
    )
    total_rows = models.PositiveIntegerField(default=0)
    success_count = models.PositiveIntegerField(default=0)
    failure_count = models.PositiveIntegerField(default=0)
    created_count = models.PositiveIntegerField(
        default=0, help_text="Number of contacts newly created"
    )
    updated_count = models.PositiveIntegerField(
        default=0, help_text="Number of rows that matched existing contacts (updated)"
    )
    duplicate_in_file_count = models.PositiveIntegerField(
        default=0,
        help_text="Number of rows in the CSV that were duplicates (same group_type+phone/email seen earlier in file)",
    )
    error_report_path = models.TextField(
        blank=True,
        help_text="JSON array of row errors, or path to stored error report file",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    def __str__(self) -> str:
        return f"Upload {self.pk} - {self.file_name}"


class MessagingProviderConfig(models.Model):
    class Channel(models.TextChoices):
        SMS = "sms", "SMS"
        EMAIL = "email", "Email"

    channel = models.CharField(max_length=16, choices=Channel.choices)
    name = models.CharField(max_length=64)
    is_default = models.BooleanField(
        default=False,
        help_text="If true, this config will be used when no explicit provider is selected.",
    )
    settings = models.JSONField(
        default=dict,
        blank=True,
        help_text="Provider specific settings (API key overrides, sender IDs, etc.)",
    )
    rate_limit_per_minute = models.PositiveIntegerField(
        default=0,
        help_text="Soft rate limit hint for this provider (0 = use system default).",
    )
    active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("channel", "name")

    def __str__(self) -> str:
        return f"{self.channel} - {self.name}"


class EmailTemplate(models.Model):
    name = models.CharField(max_length=128)
    slug = models.SlugField(max_length=128, unique=True)
    subject = models.CharField(max_length=255)
    body_html = models.TextField()
    body_text = models.TextField(blank=True)
    variables_schema = models.JSONField(
        default=list,
        blank=True,
        help_text="List of supported variables, e.g. ['name', 'city', 'booking_link']",
    )
    is_marketing = models.BooleanField(default=True)
    provider = models.ForeignKey(
        MessagingProviderConfig,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        limit_choices_to={"channel": MessagingProviderConfig.Channel.EMAIL},
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_email_templates",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return self.name


class Campaign(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SCHEDULED = "scheduled", "Scheduled"
        RUNNING = "running", "Running"
        PAUSED = "paused", "Paused"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    target_group_type = models.CharField(
        max_length=32,
        choices=ALL_GROUP_CHOICES,
        blank=True,
        help_text="If empty, applies to all groups (filtered via target_filters).",
    )
    target_filters = models.JSONField(
        default=dict,
        blank=True,
        help_text="Flexible filters: {\"city\": \"Kochi\", \"country\": \"INDIA\"}",
    )
    status = models.CharField(
        max_length=32, choices=Status.choices, default=Status.DRAFT
    )
    schedule_time = models.DateTimeField(
        null=True,
        blank=True,
        help_text="If set, initial campaign dispatch will be scheduled for this time.",
    )
    repeat_every_days = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text=(
            "If set (>0), auto-create the next campaign run after completion "
            "with schedule_time + repeat_every_days."
        ),
    )
    repeat_from_campaign = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="generated_repeats",
        help_text="Internal link to the previous run when this campaign was auto-generated.",
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_campaigns",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return self.name


class CampaignStep(models.Model):
    class Channel(models.TextChoices):
        SMS = "sms", "SMS"
        EMAIL = "email", "Email"

    class DelayUnit(models.TextChoices):
        HOURS = "hours", "Hours"
        DAYS = "days", "Days"
        WEEKS = "weeks", "Weeks"

    campaign = models.ForeignKey(
        Campaign, on_delete=models.CASCADE, related_name="steps"
    )
    order_index = models.PositiveIntegerField(
        help_text="Ordering of steps within a campaign (1,2,3...)."
    )
    channel = models.CharField(max_length=16, choices=Channel.choices)
    template_code = models.CharField(
        max_length=255,
        blank=True,
        help_text="For SMS: MessageTemplate.template_code; for Email: EmailTemplate.slug.",
    )
    delay_amount = models.PositiveIntegerField(
        default=0,
        help_text="Delay after previous step (or campaign start) before sending.",
    )
    delay_unit = models.CharField(
        max_length=16, choices=DelayUnit.choices, default=DelayUnit.HOURS
    )
    active = models.BooleanField(default=True)
    messaging_provider = models.ForeignKey(
        MessagingProviderConfig,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="campaign_steps",
        help_text=(
            "Optional: send this step via this provider (must match channel). "
            "If empty, uses the email template's provider (email only), then the default provider for the channel, "
            "then server environment settings."
        ),
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["campaign", "order_index"]
        unique_together = ("campaign", "order_index")

    def __str__(self) -> str:
        return f"{self.campaign.name} - step {self.order_index}"


class CampaignContact(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        QUEUED = "queued", "Queued"
        SENT = "sent", "Sent"
        FAILED = "failed", "Failed"
        SKIPPED_OPT_OUT = "skipped_opt_out", "Skipped (opt-out)"
        BLACKLISTED = "blacklisted", "Skipped (blacklisted)"

    campaign = models.ForeignKey(
        Campaign, on_delete=models.CASCADE, related_name="campaign_contacts"
    )
    step = models.ForeignKey(
        CampaignStep,
        on_delete=models.CASCADE,
        related_name="campaign_contacts",
    )
    contact = models.ForeignKey(
        Contact, on_delete=models.CASCADE, related_name="campaign_contacts"
    )
    status = models.CharField(
        max_length=32, choices=Status.choices, default=Status.PENDING
    )
    scheduled_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When this specific message is scheduled to be sent.",
    )
    sent_at = models.DateTimeField(null=True, blank=True)
    provider_message_id = models.CharField(max_length=128, blank=True)
    error_code = models.CharField(max_length=64, blank=True)
    error_message = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("campaign", "step", "contact")


class MessageLog(models.Model):
    class Channel(models.TextChoices):
        SMS = "sms", "SMS"
        EMAIL = "email", "Email"

    class Status(models.TextChoices):
        QUEUED = "queued", "Queued"
        ACCEPTED = "accepted", "Accepted by provider"
        SENT = "sent", "Sent"
        DELIVERED = "delivered", "Delivered"
        BOUNCED = "bounced", "Bounced"
        DEFERRED = "deferred", "Deferred"
        FAILED = "failed", "Failed"

    contact = models.ForeignKey(
        Contact, on_delete=models.SET_NULL, null=True, related_name="message_logs"
    )
    campaign = models.ForeignKey(
        Campaign,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="message_logs",
    )
    step = models.ForeignKey(
        CampaignStep,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="message_logs",
    )
    channel = models.CharField(max_length=16, choices=Channel.choices)
    status = models.CharField(max_length=16, choices=Status.choices)
    provider = models.CharField(max_length=64, blank=True)
    provider_response = models.JSONField(default=dict, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"{self.channel} to {self.contact_id} ({self.status})"

