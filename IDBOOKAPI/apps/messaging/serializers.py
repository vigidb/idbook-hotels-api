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


class CampaignStepSerializer(serializers.ModelSerializer):
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

