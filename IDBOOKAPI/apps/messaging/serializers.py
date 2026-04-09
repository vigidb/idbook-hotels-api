import re
from rest_framework import serializers

from apps.authentication.constants import ALL_GROUP_CHOICES
from apps.authentication.models import User
from apps.messaging.models import (
    Contact,
    ContactUploadSession,
    Campaign,
    CampaignStep,
    CampaignContact,
    MessageLog,
    EmailTemplate,
    MessagingProviderConfig,
)
from apps.messaging.provider_runtime import (
    merge_settings_preserving_secrets,
    mask_settings_for_api,
)
from apps.messaging.services import normalize_phone


class ContactSerializer(serializers.ModelSerializer):
    def validate(self, attrs):
        phone = (attrs.get("phone") or "").strip()
        email = (attrs.get("email") or "").strip()
        group_type = (attrs.get("group_type") or "").strip()

        if not phone and not email:
            raise serializers.ValidationError(
                {"non_field_errors": ["Either phone or email is required"]}
            )

        if group_type and group_type not in dict(ALL_GROUP_CHOICES):
            raise serializers.ValidationError({"group_type": ["Invalid group_type"]})

        # Normalize and validate phone
        if phone:
            phone_digits = re.sub(r"\D", "", phone)
            if len(phone_digits) < 10 or len(phone_digits) > 15:
                raise serializers.ValidationError(
                    {"phone": ["Invalid phone: must be 10–15 digits"]}
                )
            attrs["phone"] = normalize_phone(phone)

        # Normalize email
        if email:
            attrs["email"] = email.lower()

        return attrs

    class Meta:
        model = Contact
        fields = "__all__"
        read_only_fields = ("id", "created_at", "updated_at")


class ContactUploadSessionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContactUploadSession
        fields = "__all__"
        read_only_fields = ("id", "status", "created_at", "finished_at")


class EmailTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmailTemplate
        fields = "__all__"
        read_only_fields = ("id", "created_at", "updated_at", "created_by")


class MessagingProviderConfigSerializer(serializers.ModelSerializer):
    """Secrets in `settings` are masked on read; partial updates preserve existing secrets."""

    class Meta:
        model = MessagingProviderConfig
        fields = "__all__"
        read_only_fields = ("id", "created_at", "updated_at")

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["settings"] = mask_settings_for_api(instance.settings)
        return data

    def validate(self, attrs):
        channel = attrs.get("channel") or getattr(self.instance, "channel", None)
        settings_payload = attrs.get("settings")
        if settings_payload is None or not channel:
            return attrs
        merged = merge_settings_preserving_secrets(
            getattr(self.instance, "settings", None), settings_payload
        )
        if channel == MessagingProviderConfig.Channel.EMAIL:
            for key in ("smtp_host", "smtp_username", "smtp_password", "from_email"):
                if not str(merged.get(key) or "").strip():
                    raise serializers.ValidationError(
                        {
                            "settings": [
                                f"Email provider requires settings.{key} (non-empty)."
                            ]
                        }
                    )
        elif channel == MessagingProviderConfig.Channel.SMS:
            for key in ("fast2sms_api_key", "dlt_sender_id"):
                if not str(merged.get(key) or "").strip():
                    raise serializers.ValidationError(
                        {
                            "settings": [
                                f"SMS provider requires settings.{key} (non-empty)."
                            ]
                        }
                    )
        return attrs

    def create(self, validated_data):
        ch = validated_data.get("channel")
        if validated_data.get("is_default") and ch:
            MessagingProviderConfig.objects.filter(channel=ch).update(is_default=False)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        if "settings" in validated_data:
            validated_data["settings"] = merge_settings_preserving_secrets(
                instance.settings, validated_data["settings"]
            )
        if validated_data.get("is_default") and instance.channel:
            MessagingProviderConfig.objects.filter(channel=instance.channel).exclude(
                pk=instance.pk
            ).update(is_default=False)
        return super().update(instance, validated_data)


class CampaignStepSerializer(serializers.ModelSerializer):
    def validate(self, attrs):
        channel = attrs.get("channel")
        if self.instance:
            channel = channel or self.instance.channel
        prov = attrs.get("messaging_provider")
        if self.instance and prov is None and "messaging_provider" not in attrs:
            prov = self.instance.messaging_provider
        if prov and channel:
            expected = (
                MessagingProviderConfig.Channel.EMAIL
                if channel == CampaignStep.Channel.EMAIL
                else MessagingProviderConfig.Channel.SMS
            )
            if prov.channel != expected:
                raise serializers.ValidationError(
                    {
                        "messaging_provider": [
                            f"Provider channel must be {expected} for this step"
                        ]
                    }
                )
        return attrs

    class Meta:
        model = CampaignStep
        fields = "__all__"
        read_only_fields = ("id", "created_at", "updated_at")


class CampaignSerializer(serializers.ModelSerializer):
    steps = CampaignStepSerializer(many=True, read_only=True)

    class Meta:
        model = Campaign
        fields = "__all__"
        read_only_fields = ("id", "created_at", "updated_at")


class CampaignCreateUpdateSerializer(serializers.ModelSerializer):
    """
    Separate serializer for create/update that does not require nested steps.
    Steps can be managed via dedicated endpoints.
    """

    class Meta:
        model = Campaign
        fields = "__all__"
        read_only_fields = ("id", "status", "created_at", "updated_at", "created_by")


class CampaignContactSerializer(serializers.ModelSerializer):
    contact = ContactSerializer(read_only=True)
    step = CampaignStepSerializer(read_only=True)

    class Meta:
        model = CampaignContact
        fields = "__all__"


class MessageLogSerializer(serializers.ModelSerializer):
    contact = ContactSerializer(read_only=True)

    class Meta:
        model = MessageLog
        fields = "__all__"


class TemplateVariable(serializers.Serializer):
    name = serializers.CharField()
    label = serializers.CharField()
    category = serializers.CharField()


class TemplateVariableGroup(serializers.Serializer):
    category = serializers.CharField()
    variables = TemplateVariable(many=True)

