from decimal import Decimal

from rest_framework import serializers, status

# from django.contrib.auth.models import Permission, Group
from django.core.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.permissions import BasePermission
from apps.org_resources.models import CompanyDetail

# from apps.authentication.models import *
from .models import *

# from booking.models import *
# from carts.models import *
# from coupons.models import *
# from customer.models import *
# from holiday_package.models import *
# from hotel_managements.models import *
# from hotels.models import *
# from org_managements.models import *
from apps.org_resources.models import *

# from payment_gateways.models import *
from IDBOOKAPI.utils import format_custom_id
from django.conf import settings
from django.db.models import Sum, Case, When, F, Value, DecimalField
from django.db.models.functions import Coalesce


class CustomerProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = "__all__"

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        # Backward-compatible keys used by invoice UI.
        representation["GSTIN"] = representation.get("gstin", "") or ""
        representation["PAN"] = representation.get("pan_card_number", "") or ""
        if instance.profile_picture:
            representation["profile_picture"] = (
                f"{settings.CDN}{settings.PUBLIC_MEDIA_LOCATION}/{str(instance.profile_picture)}"
            )

        # settings.MEDIA_URL + str(gallery.get('media', ''))
        return representation


class CustomerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = "__all__"

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        if instance:
            business_id, company_id = "", ""
            if instance.user:
                name = instance.user.get_full_name()
                email = instance.user.email if instance.user.email else ""
                mobile_number = (
                    instance.user.mobile_number if instance.user.mobile_number else ""
                )
                company_id = instance.user.company_id
                business_id = instance.user.business_id
                user_details = {
                    "name": name,
                    "email": email,
                    "mobile_number": mobile_number,
                }
                representation["user"] = user_details
            if company_id:
                company_object = CompanyDetail.objects.filter(
                    id=company_id
                ).first()  # instance.company_user.company_detail.first()
                company_details = {}
                if company_object:
                    company_name = (
                        company_object.company_name
                        if company_object.company_name
                        else ""
                    )
                    company_phone = (
                        company_object.company_phone
                        if company_object.company_phone
                        else ""
                    )
                    company_email = (
                        company_object.company_email
                        if company_object.company_email
                        else ""
                    )
                    company_details = {
                        "company_name": company_name,
                        "company_phone": company_phone,
                        "company_email": company_email,
                    }

                if not company_object:
                    business_object = instance.user.business_detail.first()
                    if business_object:
                        company_name = (
                            business_object.business_name
                            if business_object.business_name
                            else ""
                        )
                        company_phone = (
                            business_object.business_phone
                            if business_object.business_phone
                            else ""
                        )
                        company_email = (
                            business_object.business_email
                            if business_object.business_email
                            else ""
                        )
                        company_details = {
                            "company_name": company_name,
                            "company_phone": company_phone,
                            "company_email": company_email,
                        }

                representation["company_user"] = company_details

        return representation


class QueryFilterCustomerSerializer(serializers.ModelSerializer):
    company_id = serializers.IntegerField(required=False)
    user_id = serializers.IntegerField(required=False)
    offset = serializers.IntegerField(required=False)
    limit = serializers.IntegerField(required=False)
    search = serializers.CharField(
        required=False, help_text="Available columns: employee_id"
    )

    class Meta:
        model = Customer
        fields = (
            "company_id",
            "user_id",
            "group_name",
            "department",
            "privileged",
            "active",
            "offset",
            "limit",
            "search",
        )


class WalletSerializer(serializers.ModelSerializer):
    class Meta:
        model = Wallet
        fields = "__all__"


class WalletTransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = WalletTransaction
        fields = "__all__"


class WalletTransactionAdminSerializer(serializers.ModelSerializer):
    """Same as ledger row plus resolved wallet PK for admin UIs."""

    wallet_id = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = WalletTransaction
        fields = "__all__"

    def get_wallet_id(self, obj):
        qs = Wallet.objects.all()
        if obj.company_id:
            wid = (
                qs.filter(company_id=obj.company_id)
                .values_list("id", flat=True)
                .first()
            )
            return wid
        if obj.agent_id:
            wid = (
                qs.filter(agent_id=obj.agent_id)
                .values_list("id", flat=True)
                .first()
            )
            return wid
        if obj.user_id:
            return (
                qs.filter(
                    user_id=obj.user_id,
                    company_id__isnull=True,
                    agent_id__isnull=True,
                )
                .values_list("id", flat=True)
                .first()
            )
        return None


class QueryFilterWalletTransactionSerializer(serializers.Serializer):
    user_id = serializers.IntegerField(required=False, min_value=1)
    company_id = serializers.IntegerField(required=False, min_value=1)
    agent_id = serializers.IntegerField(required=False, min_value=1)
    transaction_type = serializers.ChoiceField(
        choices=["Credit", "Debit"], required=False
    )
    transaction_for = serializers.CharField(required=False, allow_blank=True)
    payment_type = serializers.CharField(required=False, allow_blank=True)
    payment_medium = serializers.CharField(required=False, allow_blank=True)
    status = serializers.CharField(required=False, allow_blank=True)
    is_transaction_success = serializers.BooleanField(required=False)
    search = serializers.CharField(required=False, allow_blank=True)
    start_date = serializers.DateField(required=False)
    end_date = serializers.DateField(required=False)
    ordering = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="Comma separated fields. Allowed: created, updated, amount, status, transaction_type, transaction_id, payment_medium, payment_type",
    )
    offset = serializers.IntegerField(required=False, default=0, min_value=0)
    limit = serializers.IntegerField(required=False, default=10, min_value=1, max_value=100)


class WalletRechargeSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=20, decimal_places=6, required=True)
    company_id = serializers.IntegerField(required=False, allow_null=True)
    agent_id = serializers.IntegerField(required=False, allow_null=True)
    payment_type = serializers.CharField(max_length=50, required=True)
    payment_medium = serializers.CharField(max_length=50, required=True)
    media = serializers.FileField(required=True)
    transaction_id = serializers.CharField(max_length=350, required=True)

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("Amount must be greater than 0")
        return value

    def validate_transaction_id(self, value):
        if WalletTransaction.objects.filter(transaction_id=value).exists():
            raise serializers.ValidationError("Transaction ID already exists")
        return value


class ApproveRechargeSerializer(serializers.Serializer):
    transaction_id = serializers.CharField(max_length=350)
    amount = serializers.DecimalField(max_digits=20, decimal_places=6)

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("Amount must be greater than 0")
        return value


class RejectPendingRechargeSerializer(serializers.Serializer):
    reason = serializers.CharField(min_length=3, max_length=2000)


class FeePreviewQuerySerializer(serializers.Serializer):
    amount = serializers.DecimalField(
        max_digits=20, decimal_places=2, min_value=Decimal("0.01")
    )
    bucket = serializers.CharField(required=False, allow_blank=True, default="worst_case")


class AdminWalletListQuerySerializer(serializers.Serializer):
    offset = serializers.IntegerField(required=False, default=0, min_value=0)
    limit = serializers.IntegerField(
        required=False, default=20, min_value=1, max_value=100
    )
    search = serializers.CharField(required=False, allow_blank=True)
    ordering = serializers.CharField(required=False, allow_blank=True)
    wallet_owner = serializers.CharField(required=False, allow_blank=True)
    user_id = serializers.IntegerField(required=False, allow_null=True)
    company_id = serializers.IntegerField(required=False, allow_null=True)
    agent_id = serializers.IntegerField(required=False, allow_null=True)

    def validate_wallet_owner(self, value):
        if not value or not str(value).strip():
            return ""
        v = str(value).strip().lower()
        if v not in ("b2c", "company", "agent"):
            raise serializers.ValidationError(
                "wallet_owner must be one of: b2c, company, agent"
            )
        return v


class AdminWalletScopedTransactionQuerySerializer(serializers.Serializer):
    """Finance admin: transactions for a single wallet (scope derived server-side)."""

    offset = serializers.IntegerField(required=False, default=0, min_value=0)
    limit = serializers.IntegerField(
        required=False, default=20, min_value=1, max_value=100
    )
    search = serializers.CharField(required=False, allow_blank=True)
    ordering = serializers.CharField(required=False, allow_blank=True)


class AdminWalletTransactionWriteSerializer(serializers.ModelSerializer):
    """Finance admin: create/update ledger fields (wallet scope set by server)."""

    class Meta:
        model = WalletTransaction
        fields = (
            "amount",
            "transaction_type",
            "transaction_for",
            "transaction_details",
            "payment_type",
            "payment_medium",
            "status",
            "is_transaction_success",
            "transaction_id",
            "code",
            "other_details",
        )
        extra_kwargs = {
            "transaction_for": {"required": False, "default": "others"},
            "payment_type": {"required": False, "default": "WALLET"},
            "payment_medium": {"required": False, "default": "Idbook"},
            "status": {"required": False, "default": "Completed"},
            "is_transaction_success": {"required": False, "default": True},
            "transaction_id": {"required": False, "allow_null": True},
            "code": {"required": False, "allow_blank": True},
            "other_details": {"required": False},
        }

    def validate_amount(self, value):
        if value is not None and value <= 0:
            raise serializers.ValidationError("Amount must be greater than 0")
        return value

    def validate_other_details(self, value):
        if value in ("", None):
            return {}
        if isinstance(value, dict):
            return value
        raise serializers.ValidationError("other_details must be a valid JSON object")

    def _wallet_scope_queryset(self, wallet):
        qs = WalletTransaction.objects.all()
        if wallet.company_id:
            return qs.filter(company_id=wallet.company_id)
        if wallet.agent_id:
            return qs.filter(agent_id=wallet.agent_id)
        return qs.filter(
            user_id=wallet.user_id,
            company_id__isnull=True,
            agent_id__isnull=True,
        )

    def _is_counted(self, status_value, success_value):
        return str(status_value or "").lower() == "completed" and bool(success_value)

    def validate(self, attrs):
        wallet = self.context.get("wallet")
        if not wallet:
            return attrs

        instance = getattr(self, "instance", None)
        amount = attrs.get("amount")
        if amount is None and instance is not None:
            amount = instance.amount
        amount = Decimal(amount or 0)

        txn_type = attrs.get("transaction_type")
        if not txn_type and instance is not None:
            txn_type = instance.transaction_type

        status_value = attrs.get("status")
        if status_value is None and instance is not None:
            status_value = instance.status
        if status_value is None:
            status_value = "Completed"

        success_value = attrs.get("is_transaction_success")
        if success_value is None and instance is not None:
            success_value = instance.is_transaction_success
        if success_value is None:
            success_value = True

        qs = self._wallet_scope_queryset(wallet).filter(
            status__iexact="Completed",
            is_transaction_success=True,
        )
        if instance is not None and instance.pk:
            qs = qs.exclude(pk=instance.pk)

        current_balance = qs.aggregate(
            total=Coalesce(
                Sum(
                    Case(
                        When(transaction_type="Credit", then=F("amount")),
                        When(transaction_type="Debit", then=-F("amount")),
                        default=Value(Decimal("0")),
                        output_field=DecimalField(max_digits=24, decimal_places=6),
                    )
                ),
                Value(Decimal("0")),
            )
        )["total"] or Decimal("0")

        if self._is_counted(status_value, success_value):
            if str(txn_type) == "Credit":
                projected_balance = current_balance + amount
            elif str(txn_type) == "Debit":
                projected_balance = current_balance - amount
            else:
                projected_balance = current_balance
        else:
            projected_balance = current_balance

        if projected_balance < 0:
            raise serializers.ValidationError(
                {"amount": "Insufficient wallet balance for this debit transaction."}
            )

        return attrs


class AdminWalletTransactionListQuerySerializer(serializers.Serializer):
    """Finance admin: paginated all wallet transactions."""

    offset = serializers.IntegerField(required=False, default=0, min_value=0)
    limit = serializers.IntegerField(
        required=False, default=20, min_value=1, max_value=100
    )
    search = serializers.CharField(required=False, allow_blank=True)
    ordering = serializers.CharField(required=False, allow_blank=True)
    status = serializers.CharField(required=False, allow_blank=True)
    transaction_for = serializers.CharField(required=False, allow_blank=True)
    transaction_type = serializers.CharField(required=False, allow_blank=True)
    payment_type = serializers.CharField(required=False, allow_blank=True)
    payment_medium = serializers.CharField(required=False, allow_blank=True)
    wallet_owner = serializers.CharField(required=False, allow_blank=True)
    user_id = serializers.IntegerField(required=False, allow_null=True)
    company_id = serializers.IntegerField(required=False, allow_null=True)
    agent_id = serializers.IntegerField(required=False, allow_null=True)
    start_date = serializers.DateField(required=False, allow_null=True)
    end_date = serializers.DateField(required=False, allow_null=True)

    def validate_wallet_owner(self, value):
        if not value or not str(value).strip():
            return ""
        v = str(value).strip().lower()
        if v not in ("b2c", "company", "agent"):
            raise serializers.ValidationError(
                "wallet_owner must be one of: b2c, company, agent"
            )
        return v

    def validate(self, attrs):
        start_date = attrs.get("start_date")
        end_date = attrs.get("end_date")
        if start_date and end_date and start_date > end_date:
            raise serializers.ValidationError(
                {"end_date": "end_date must be on or after start_date"}
            )
        return attrs


class WalletAdminListSerializer(serializers.ModelSerializer):
    """Wallet row for admin finance list (owner labels)."""

    owner_type = serializers.SerializerMethodField()
    owner_label = serializers.SerializerMethodField()
    user_email = serializers.SerializerMethodField()

    class Meta:
        model = Wallet
        fields = (
            "id",
            "user",
            "company",
            "agent",
            "balance",
            "active",
            "created",
            "updated",
            "owner_type",
            "owner_label",
            "user_email",
        )

    def get_owner_type(self, obj):
        if obj.company_id:
            return "company"
        if obj.agent_id:
            return "agent"
        if obj.user_id:
            return "user"
        return "unknown"

    def get_owner_label(self, obj):
        if obj.company:
            return getattr(obj.company, "company_name", None) or str(obj.company_id)
        if obj.agent:
            return obj.agent.agent_name or str(obj.agent_id)
        if obj.user:
            return obj.user.get_full_name() or obj.user.email or str(obj.user_id)
        return None

    def get_user_email(self, obj):
        if obj.user:
            return obj.user.email
        return None


class QueryFilterPendingRechargeSerializer(serializers.Serializer):
    user_id = serializers.IntegerField(required=False, allow_null=True)
    company_id = serializers.IntegerField(required=False, allow_null=True)
    agent_id = serializers.IntegerField(required=False, allow_null=True)
    offset = serializers.IntegerField(required=False, default=0, min_value=0)
    limit = serializers.IntegerField(
        required=False, default=10, min_value=1, max_value=100
    )
    transaction_id = serializers.CharField(required=False, allow_blank=True)
    payment_type = serializers.CharField(required=False, allow_blank=True)
    payment_medium = serializers.CharField(required=False, allow_blank=True)
    status = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="Pending | Completed | Failed (defaults to Pending when omitted)",
    )
    wallet_owner = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="b2c | company | agent — filter by wallet scope",
    )
    start_date = serializers.DateField(required=False, allow_null=True, help_text="Filter by start date (YYYY-MM-DD)")
    end_date = serializers.DateField(required=False, allow_null=True, help_text="Filter by end date (YYYY-MM-DD)")
    search = serializers.CharField(required=False, allow_blank=True, help_text="Search by user name, email, mobile, transaction_id")
    ordering = serializers.CharField(required=False, allow_blank=True, help_text="Order by field (e.g., '-created', 'amount', '-amount')")

    def validate_wallet_owner(self, value):
        if not value or not str(value).strip():
            return ""
        v = str(value).strip().lower()
        if v not in ("b2c", "company", "agent"):
            raise serializers.ValidationError(
                "wallet_owner must be one of: b2c, company, agent"
            )
        return v


class PendingRechargeSerializer(serializers.ModelSerializer):
    wallet_id = serializers.SerializerMethodField()
    user_name = serializers.SerializerMethodField()
    company_name = serializers.SerializerMethodField()
    agent_name = serializers.SerializerMethodField()
    user_email = serializers.SerializerMethodField()
    user_mobile = serializers.SerializerMethodField()

    class Meta:
        model = WalletTransaction
        fields = [
            "id",
            "wallet_id",
            "user",
            "company",
            "agent",
            "user_name",
            "company_name",
            "agent_name",
            "user_email",
            "user_mobile",
            "code",
            "amount",
            "transaction_type",
            "transaction_for",
            "transaction_id",
            "transaction_details",
            "payment_type",
            "payment_medium",
            "status",
            "media",
            "created",
            "updated",
            "other_details",
        ]

    def get_wallet_id(self, obj):
        qs = Wallet.objects.all()
        if obj.company_id:
            return (
                qs.filter(company_id=obj.company_id)
                .values_list("id", flat=True)
                .first()
            )
        if obj.agent_id:
            return (
                qs.filter(agent_id=obj.agent_id)
                .values_list("id", flat=True)
                .first()
            )
        if obj.user_id:
            return (
                qs.filter(
                    user_id=obj.user_id,
                    company_id__isnull=True,
                    agent_id__isnull=True,
                )
                .values_list("id", flat=True)
                .first()
            )
        return None

    def get_user_name(self, obj):
        if obj.user:
            return f"{obj.user.name}".strip() or obj.user.name
        return None

    def get_user_email(self, obj):
        if obj.user:
            return obj.user.email
        return None

    def get_user_mobile(self, obj):
        if obj.user:
            return obj.user.mobile_number
        return None

    def get_company_name(self, obj):
        if obj.company:
            return (
                obj.company.company_name
                if hasattr(obj.company, "company_name")
                else None
            )
        return None

    def get_agent_name(self, obj):
        if obj.agent:
            return obj.agent.agent_name
        return None
