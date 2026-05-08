from rest_framework.views import APIView
from decimal import Decimal
from rest_framework.response import Response
from rest_framework import viewsets
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import views, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.generics import (
    CreateAPIView,
    ListAPIView,
    GenericAPIView,
    RetrieveAPIView,
    UpdateAPIView,
)
from rest_framework.decorators import action
from IDBOOKAPI.mixins import StandardResponseMixin, LoggingMixin
from IDBOOKAPI.permissions import HasRoleModelPermission, AnonymousCanViewOnlyPermission
from IDBOOKAPI.utils import paginate_queryset, get_unique_id_from_time

from apps.payment_gateways.mixins.phonepay_mixins import PhonePayMixin
from apps.payment_gateways.mixins.razorpay_mixins import RazorpayMixin
from apps.customer.utils.db_utils import (
    update_wallet_transaction,
    update_wallet_recharge_details,
    update_wallet_transaction_detail,
    process_wallet_recharge_transaction_once,
    add_company_wallet_amount,
    add_user_wallet_amount,
    add_agent_wallet_amount,
    attach_razorpay_fee_metadata,
)
from apps.log_management.utils.db_utils import create_wallet_payment_log
from django.conf import settings

from .serializers import (
    AdminWalletListQuerySerializer,
    AdminWalletScopedTransactionQuerySerializer,
    AdminWalletTransactionListQuerySerializer,
    AdminWalletTransactionWriteSerializer,
    ApproveRechargeSerializer,
    CustomerSerializer,
    FeePreviewQuerySerializer,
    PendingRechargeSerializer,
    QueryFilterCustomerSerializer,
    QueryFilterPendingRechargeSerializer,
    QueryFilterWalletTransactionSerializer,
    WalletAdminListSerializer,
    WalletRechargeSerializer,
    WalletSerializer,
    WalletTransactionAdminSerializer,
    WalletTransactionSerializer,
)
from apps.customer.wallet_admin_views import (
    compute_wallet_ledger_balance,
    finance_ops_admin_allowed,
    transaction_matches_wallet,
    wallet_transactions_scope_q,
)
from apps.customer.wallet_owner_utils import (
    wallet_owner_kwargs_from_wallet,
    validate_exclusive_wallet_owner,
)
from .models import Customer, Wallet, WalletTransaction
from django.db.models import (
    Q,
    Sum,
    Count,
    Case,
    When,
    F,
    Value,
    DecimalField,
    Window,
    CharField,
)
from django.db.models.functions import Coalesce, Cast, Concat
from django.core.exceptions import ValidationError as DjangoValidationError
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
import traceback
from rest_framework.parsers import MultiPartParser
from apps.booking.tasks import send_booking_sms_task
from apps.authentication.models import User
from django.conf import settings

import base64, json


def _is_counted_wallet_txn(status_value, success_value):
    return str(status_value).strip().lower() == "completed" and bool(success_value) is True


def _wallet_txn_effect(amount, transaction_type, status_value, success_value):
    amt = Decimal(str(amount or 0))
    if not _is_counted_wallet_txn(status_value, success_value):
        return Decimal("0")
    txn_type = str(transaction_type or "").strip().lower()
    if txn_type == "credit":
        return amt
    if txn_type == "debit":
        return -amt
    return Decimal("0")


class CustomerViewSet(viewsets.ModelViewSet, StandardResponseMixin, LoggingMixin):
    queryset = Customer.objects.all()
    serializer_class = CustomerSerializer
    # permission_classes = [AnonymousCanViewOnlyPermission,]
    permission_classes = [IsAuthenticated]
    # filter_backends = [DjangoFilterBackend]
    # filterset_fields = ['service_category', 'district', 'area_name', 'city_name', 'starting_price', 'rating',]
    http_method_names = ["get", "post", "put", "patch", "delete"]
    # lookup_field = 'custom_id'

    def customer_filter_ops(self):
        filter_dict = {}
        user = self.request.user

        # Get active group strictly from token (no fallback to user.default_group)
        from apps.authentication.utils.token_utils import get_active_group_from_request
        from apps.authentication.constants import (
            UserGroups,
            CORPORATE_GROUPS,
            B2C_GROUPS,
        )

        active_group = get_active_group_from_request(self.request)

        # fetch filter parameters
        param_dict = self.request.query_params
        for key in param_dict:
            param_value = param_dict[key]

            if key in ("group_name", "department", "privileged", "active"):
                filter_dict[key] = param_value

        # Apply permission-based filtering based on user's active group
        # Normal users (B2C-GRP, B2C-GUEST): can only see their own customer record
        if active_group in B2C_GROUPS:
            filter_dict["user"] = user.id

        # Corporate users (CORP-ADMIN, CORP-EMP, CORPORATE-GRP): can see customers from their company
        elif active_group in CORPORATE_GROUPS:
            # All corporate users can see all customers for their company
            if user.company_id:
                filter_dict["user__company_id"] = user.company_id
            else:
                # If user has no company_id, they shouldn't see any customers
                filter_dict["user__company_id"] = -1  # This will return empty queryset

        # Business users (BUSINESS-GRP, BUS-ADMIN): can see all customers (no filter)
        elif active_group in (UserGroups.BUSINESS_GRP, UserGroups.BUS_ADMIN):
            # No filtering - business users can see all customers
            # Allow query params to filter if provided
            if "company_id" in param_dict:
                filter_dict["user__company_id"] = param_dict["company_id"]
            if "user_id" in param_dict:
                filter_dict["user"] = param_dict["user_id"]

        # Hotelier/Franchise admins: no filtering (existing behavior)
        elif active_group in (UserGroups.HTLR_ADMIN, UserGroups.FRANCH_ADMIN):
            # Allow query params to filter if provided
            if "company_id" in param_dict:
                filter_dict["user__company_id"] = param_dict["company_id"]
            if "user_id" in param_dict:
                filter_dict["user"] = param_dict["user_id"]

        # filter
        self.queryset = self.queryset.filter(**filter_dict)

        # search
        search = self.request.query_params.get("search", "")
        if search:
            search_q_filter = Q(employee_id__icontains=search)
            self.queryset = self.queryset.filter(search_q_filter)

    def create(self, request, *args, **kwargs):
        self.log_request(request)  # Log the incoming request

        # Create an instance of your serializer with the request data
        serializer = self.get_serializer(data=request.data)

        if serializer.is_valid():
            # If the serializer is valid, perform the default creation logic
            response = super().create(request, *args, **kwargs)

            # Create a custom response
            custom_response = self.get_response(
                data=response.data,  # Use the data from the default response
                message="Customer Created",
                status_code=status.HTTP_201_CREATED,  # 201 for successful creation
            )
        else:
            # If the serializer is not valid, create a custom response with error details
            custom_response = self.get_response(
                data=serializer.errors,  # Use the serializer's error details
                message="Validation Error",
                status_code=status.HTTP_400_BAD_REQUEST,  # 400 for validation error
                is_error=True,
            )

        self.log_response(custom_response)  # Log the custom response before returning
        return custom_response

    def update(self, request, *args, **kwargs):
        self.log_request(request)  # Log the incoming request
        compony_id = None
        name = request.data.get("name", None)

        user = request.user
        if user.category == "CL-ADMIN":
            company_id = user.company_id
            if not company_id:
                custom_response = self.get_error_response(
                    message="No privilege to update. Missing authenticated user's company details",
                    status="error",
                    errors=[],
                    error_code="AUTHORIZATION_ERROR",
                    status_code=status.HTTP_403_FORBIDDEN,
                )
                return custom_response
        else:
            custom_response = self.get_error_response(
                message="No privilege to update. The authenticated user is not a company admin",
                status="error",
                errors=[],
                error_code="AUTHORIZATION_ERROR",
                status_code=status.HTTP_403_FORBIDDEN,
            )
            return custom_response

        # Get the object to be updated
        instance = self.get_object()

        if instance:
            customer_company_id = instance.user.company_id
            if not company_id == customer_company_id:
                custom_response = self.get_error_response(
                    message="No privilege to update. The customer belongs to different company",
                    status="error",
                    errors=[],
                    error_code="AUTHORIZATION_ERROR",
                    status_code=status.HTTP_403_FORBIDDEN,
                )
                return custom_response

        # Create an instance of your serializer with the request data and the object to be updated
        serializer = self.get_serializer(instance, data=request.data)

        if serializer.is_valid():
            # If the serializer is valid, perform the default update logic
            response = super().update(request, *args, **kwargs)

            # Create a custom response
            custom_response = self.get_response(
                data=response.data,  # Use the data from the default response
                message="Customer Updated",
                status_code=status.HTTP_200_OK,  # 200 for successful update
            )
        else:
            # If the serializer is not valid, create a custom response with error details
            error_list = self.custom_serializer_error(serializer.errors)
            custom_response = self.get_error_response(
                message="Validation Error",
                status="error",
                errors=error_list,
                error_code="VALIDATION_ERROR",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        self.log_response(custom_response)  # Log the custom response before returning
        return custom_response

    def partial_update(self, request, *args, **kwargs):
        self.log_request(request)  # Log the incoming request
        compony_id = None
        name = request.data.get("name", None)
        user = request.user
        if user.category == "CL-ADMIN":
            company_id = user.company_id
            if not company_id:
                custom_response = self.get_error_response(
                    message="No privilege to update. Missing authenticated user's company details",
                    status="error",
                    errors=[],
                    error_code="AUTHORIZATION_ERROR",
                    status_code=status.HTTP_403_FORBIDDEN,
                )
                return custom_response
        else:
            custom_response = self.get_error_response(
                message="No privilege to update. The authenticated user is not a company admin",
                status="error",
                errors=[],
                error_code="AUTHORIZATION_ERROR",
                status_code=status.HTTP_403_FORBIDDEN,
            )
            return custom_response

        # Get the object to be updated
        instance = self.get_object()

        if instance:
            customer_company_id = instance.user.company_id
            if not company_id == customer_company_id:
                custom_response = self.get_error_response(
                    message="No privilege to update. The customer belongs to different company",
                    status="error",
                    errors=[],
                    error_code="AUTHORIZATION_ERROR",
                    status_code=status.HTTP_403_FORBIDDEN,
                )
                return custom_response

        # Create an instance of your serializer with the request data and the object to be updated
        serializer = self.get_serializer(instance, data=request.data, partial=True)

        if serializer.is_valid():
            print("inside validation error", request.data)
            # If the serializer is valid, perform the default update logic
            # response = super().partial_update(request, *args, **kwargs)
            response = self.perform_update(serializer)
            if name:
                instance.user.name = name
                instance.user.save()
            # Create a custom response
            custom_response = self.get_response(
                status="success",
                data=serializer.data,  # Use the data from the default response
                message="Customer Updated",
                status_code=status.HTTP_200_OK,  # 200 for successful update
            )
        else:
            # If the serializer is not valid, create a custom response with error details
            custom_response = self.get_response(
                data=serializer.errors,  # Use the serializer's error details
                message="Validation Error",
                status_code=status.HTTP_400_BAD_REQUEST,  # 400 for validation error
                is_error=True,
            )

        self.log_response(custom_response)  # Log the custom response before returning
        return custom_response

    @swagger_auto_schema(
        query_serializer=QueryFilterCustomerSerializer,
        operation_description="List Customer Based on User Roles",
        responses={200: CustomerSerializer(many=True)},
    )
    def list(self, request, *args, **kwargs):
        self.log_request(request)  # Log the incoming request
        print("Inside customer")
        self.customer_filter_ops()
        # count = self.customer_pagination_ops()
        count, self.queryset = paginate_queryset(self.request, self.queryset)

        # Perform the default listing logic
        response = super().list(request, *args, **kwargs)

        if response.status_code == status.HTTP_200_OK:
            # If the response status code is OK (200), it's a successful listing
            custom_response = self.get_response(
                count=count,
                data=response.data,  # Use the data from the default response
                message="List Retrieved",
                status_code=status.HTTP_200_OK,  # 200 for successful listing
            )
        else:
            # If the response status code is not OK, it's an error
            custom_response = self.get_response(
                data=None,
                message="Error Occurred",
                status_code=response.status_code,  # Use the status code from the default response
                is_error=True,
            )

        self.log_response(custom_response)  # Log the custom response before returning
        return custom_response

    def retrieve(self, request, *args, **kwargs):
        self.log_request(request)  # Log the incoming request

        # Perform the default retrieval logic
        response = super().retrieve(request, *args, **kwargs)

        if response.status_code == status.HTTP_200_OK:
            # If the response status code is OK (200), it's a successful retrieval
            custom_response = self.get_response(
                data=response.data,  # Use the data from the default response
                message="Item Retrieved",
                status_code=status.HTTP_200_OK,  # 200 for successful retrieval
            )
        else:
            # If the response status code is not OK, it's an error
            custom_response = self.get_response(
                data=None,
                message="Error Occurred",
                status_code=response.status_code,  # Use the status code from the default response
                is_error=True,
            )

        self.log_response(custom_response)  # Log the custom response before returning
        return custom_response

    @action(
        detail=False,
        methods=["POST"],
        parser_classes=[MultiPartParser],
        url_path="user-based/update",
        url_name="user-based-update",
    )
    def user_based_update(self, request):
        user_id = request.user.id
        name = request.data.get("name", None)
        instance = self.queryset.filter(user_id=user_id).first()
        if not instance:
            custom_response = self.get_error_response(
                message="No customer associated with the user",
                status="error",
                errors=[],
                error_code="CUSTOMER_ERROR",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
            return custom_response
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        if serializer.is_valid():
            response = self.perform_update(serializer)
            if name:
                max_len = instance.user._meta.get_field("name").max_length
                if max_len and len(name) > max_len:
                    custom_response = self.get_error_response(
                        message="Validation Error",
                        status="error",
                        errors=[
                            {
                                "field": "name",
                                "message": f"Ensure this field has no more than {max_len} characters.",
                            }
                        ],
                        error_code="VALIDATION_ERROR",
                        status_code=status.HTTP_400_BAD_REQUEST,
                    )
                    return custom_response
                instance.user.name = name
                instance.user.save()
            custom_response = self.get_response(
                status="success",
                data=serializer.data,  # Use the data from the default response
                message="Customer Updated",
                status_code=status.HTTP_200_OK,  # 200 for successful retrieval
            )
        else:
            error_list = self.custom_serializer_error(serializer.errors)
            custom_response = self.get_error_response(
                message="Validation Error",
                status="error",
                errors=error_list,
                error_code="VALIDATION_ERROR",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        ##            custom_response = self.get_response(
        ##                status='error',
        ##                data=serializer.errors,  # Use the data from the default response
        ##                message="Customer Updation Failed",
        ##                status_code=status.HTTP_400_BAD_REQUEST
        ##
        ##            )

        return custom_response

    @action(
        detail=False,
        methods=["GET"],
        url_path="user-based/retrieve",
        url_name="user-based-retrieve",
    )
    def user_based_retrieve(self, request):
        user_id = request.user.id
        instance = self.queryset.filter(user_id=user_id).first()
        serializer = CustomerSerializer(instance)
        custom_response = self.get_response(
            status="success",
            data=serializer.data,  # Use the data from the default response
            message="Customer Details",
            status_code=status.HTTP_200_OK,  # 200 for successful retrieval
        )
        return custom_response

    @action(
        detail=True,
        methods=["DELETE"],
        url_path="inactive",
        url_name="inactive-customer",
        permission_classes=[IsAuthenticated],
    )
    def make_customer_inactive(self, request, pk=None):
        print("customer id", pk)
        instance = self.get_object()
        print(instance)
        if instance:
            instance.active = False
            instance.save()
            custom_response = self.get_response(
                status="success",
                data=None,
                message="Customer set to inactive status",
                status_code=status.HTTP_200_OK,
            )
        else:
            custom_response = self.get_error_response(
                message="Customer Not Found",
                status="error",
                errors=[],
                error_code="CUSTOMER_MISSING",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        return custom_response


class WalletViewSet(
    viewsets.ModelViewSet, PhonePayMixin, RazorpayMixin, StandardResponseMixin, LoggingMixin
):
    queryset = Wallet.objects.all()
    serializer_class = WalletSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "post", "put", "patch", "delete"]

    def _with_admin_running_balances_annotation(self, qs):
        effect_expr = Case(
            When(
                status__iexact="Completed",
                is_transaction_success=True,
                transaction_type__iexact="Credit",
                then=F("amount"),
            ),
            When(
                status__iexact="Completed",
                is_transaction_success=True,
                transaction_type__iexact="Debit",
                then=-F("amount"),
            ),
            default=Value(Decimal("0")),
            output_field=DecimalField(max_digits=24, decimal_places=6),
        )

        scope_partition = Case(
            When(
                company_id__isnull=False,
                then=Concat(
                    Value("company:"),
                    Cast("company_id", output_field=CharField()),
                ),
            ),
            When(
                agent_id__isnull=False,
                then=Concat(
                    Value("agent:"),
                    Cast("agent_id", output_field=CharField()),
                ),
            ),
            default=Concat(
                Value("user:"),
                Cast("user_id", output_field=CharField()),
            ),
            output_field=CharField(),
        )

        wallet_running_expr = Coalesce(
            Window(
                expression=Sum(effect_expr),
                partition_by=[scope_partition],
                order_by=[F("created").asc(), F("id").asc()],
            ),
            Value(Decimal("0")),
        )
        platform_running_expr = Coalesce(
            Window(
                expression=Sum(effect_expr),
                order_by=[F("created").asc(), F("id").asc()],
            ),
            Value(Decimal("0")),
        )

        return qs.annotate(
            wallet_running_balance=wallet_running_expr,
            platform_running_balance=platform_running_expr,
            running_balance=wallet_running_expr,
        )

    @action(
        detail=False,
        methods=["GET"],
        url_path="balance",
        url_name="retrieve-wallet-balance",
    )
    def user_based_wallet_retrieve(self, request):
        balance = 0
        user_id = request.user.id
        instance = None

        # Resolve wallet by active_group from current access token.
        # This endpoint should not switch context based on query params.
        from apps.booking.utils.agent_linking_utils import get_agent_for_user
        from apps.authentication.constants import UserGroups, CORPORATE_GROUPS

        active_group = None
        token = getattr(request, "auth", None)
        if token is not None:
            try:
                active_group = token.get("active_group")
            except Exception:
                active_group = None

        if not active_group:
            active_group = getattr(request.user, "default_group", None)

        if active_group in (UserGroups.AGENT_GRP, UserGroups.AGENT_ADMIN):
            user_agent = get_agent_for_user(request.user)
            if user_agent:
                instance = self.queryset.filter(agent_id=user_agent.id, active=True).first()
        elif active_group in CORPORATE_GROUPS:
            company_id = getattr(request.user, "company_id", None)
            if company_id:
                instance = self.queryset.filter(company_id=company_id, active=True).first()
        else:
            instance = self.queryset.filter(
                user_id=user_id, company_id__isnull=True, agent_id__isnull=True
            ).first()

        if instance:
            balance = instance.balance
        data = {"balance": balance}
        custom_response = self.get_response(
            status="success",
            data=data,  # Use the data from the default response
            message="Wallet Balance",
            status_code=status.HTTP_200_OK,  # 200 for successful retrieval
        )
        return custom_response

    @action(detail=False, methods=["POST"], url_path="recharge", url_name="recharge")
    def wallet_recharge(self, request):
        user = request.user
        payment_channel = request.data.get("payment_channel")
        redirect_url = request.data.get("redirect_url", "")
        amount = request.data.get("amount", None)
        # Check for both 'company' and 'company_id' for consistency
        company_id = request.data.get("company") or request.data.get("company_id")
        # Check for agent_id
        agent_id = request.data.get("agent") or request.data.get("agent_id")

        payment_log = {}

        if not amount:
            custom_response = self.get_error_response(
                message="Amount mising",
                status="error",
                errors=[],
                error_code="AMOUNT_MISSING",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
            return custom_response

        try:
            append_id = "%s%s" % ("WLT", user.id)
            merchant_transaction_id = get_unique_id_from_time(append_id)

            ##            wtransact = {"user_id":user.id, "amount":amount,
            ##                         "transaction_type":"Credit",
            ##                         "transaction_id":merchant_transaction_id,
            ##                         "payment_type":"PAYMENT GATEWAY",
            ##                         "payment_medium":"PHONE PAY"}

            # Auto-detect agent if user is an agent and no agent_id/company_id specified
            from apps.booking.utils.agent_linking_utils import get_agent_for_user
            user_agent = get_agent_for_user(user)
            
            # Convert company_id to int if it's provided as string
            if company_id:
                try:
                    company_id = int(company_id)
                except (ValueError, TypeError):
                    company_id = None
            
            # Convert agent_id to int if it's provided as string
            if agent_id:
                try:
                    agent_id = int(agent_id)
                except (ValueError, TypeError):
                    agent_id = None
            elif user_agent and not company_id:
                # Auto-detect agent wallet if user is an agent
                agent_id = user_agent.id
            
            # Validate agent access
            if agent_id:
                if not (user.is_superuser or (user_agent and user_agent.id == agent_id)):
                    return self.get_error_response(
                        message="You don't have permission to recharge this agent wallet",
                        status="error",
                        errors=[],
                        error_code="PERMISSION_DENIED",
                        status_code=status.HTTP_403_FORBIDDEN,
                    )

            # Set payment_medium based on payment_channel
            payment_medium = "PHONE PAY" if payment_channel == "PHONE PAY" else "RAZORPAY" if payment_channel == "RAZORPAY" else "PAYMENT GATEWAY"
            
            wtransact = {
                "transaction_id": merchant_transaction_id,
                "amount": amount,
                "transaction_type": "Credit",
                "transaction_for": "wallet_recharge",
                "transaction_details": f"Wallet recharge of {float(amount)} via {payment_channel}",
                "payment_type": "PAYMENT GATEWAY",
                "payment_medium": payment_medium,
                "status": "Pending",
            }

            payment_log["user_id"] = user.id
            payment_log["merchant_transaction_id"] = merchant_transaction_id
            if company_id:
                wtransact["company_id"] = company_id
                payment_log["company_id"] = company_id
            elif agent_id:
                wtransact["agent_id"] = agent_id
                payment_log["agent_id"] = agent_id
            else:
                wtransact["user_id"] = user.id

            # wallet transaction entry
            update_wallet_transaction(wtransact)

            if payment_channel == "PHONE PAY":

                merchant_id = settings.MERCHANT_ID
                callback_url = (
                    settings.CALLBACK_URL
                    + "/api/v1/customer/wallet/phone-pay/callbackurl/"
                )

                payload = {
                    "merchantId": merchant_id,
                    "merchantTransactionId": merchant_transaction_id,
                    "merchantUserId": user.id,
                    "amount": int(amount) * 100,
                    "redirectUrl": redirect_url,  # "https://webhook.site/redirect-url",
                    "redirectMode": "REDIRECT",
                    "callbackUrl": callback_url,  # https://webhook-test.com/6d8aac024b00f1e22e38f927a29a6522
                    "paymentInstrument": {"type": "PAY_PAGE"},
                }

                req, auth_header = self.get_encrypted_header_and_payload(payload)
                response = self.post_pay_page(req, auth_header)

                if response.status_code == 200:
                    data_json = response.json()
                    payment_log["response"] = data_json
                    instrument_response = data_json.get("data").get(
                        "instrumentResponse", {}
                    )
                    data_json.pop("data")
                    data_json["instrumentResponse"] = instrument_response
                    custom_response = self.get_response(
                        status="success",
                        count=1,
                        data=data_json,  # Use the data from the default response
                        message="Payment Initiate Url",
                        status_code=status.HTTP_200_OK,  # 200 for successful retrieval
                    )
                    # log
                    create_wallet_payment_log(payment_log)
                    return custom_response

                else:
                    payment_log["response"] = {"message": response.text}
                    custom_response = self.get_error_response(
                        message=response.text,
                        status="error",
                        errors=[],
                        error_code="PAYMENT_ERROR",
                        status_code=status.HTTP_400_BAD_REQUEST,
                    )
                    # logs
                    create_wallet_payment_log(payment_log)
                    send_booking_sms_task.apply_async(
                        kwargs={
                            "notification_type": "PAYMENT_FAILED_INFO",
                            "params": {
                                "user_id": user.id,
                                "failed_amount": float(amount),
                                "payment_purpose": "Wallet Recharge",  # Different purpose
                            },
                        }
                    )
                    return custom_response

            elif payment_channel == "RAZORPAY":
                # Razorpay payment flow
                try:
                    razorpay_mixin = RazorpayMixin()
                    
                    # Prepare notes for Razorpay order
                    notes = {
                        "user_id": str(user.id),
                        "merchant_transaction_id": merchant_transaction_id,
                        "transaction_type": "wallet_recharge",
                    }
                    if company_id:
                        notes["company_id"] = str(company_id)
                    if agent_id:
                        notes["agent_id"] = str(agent_id)
                    
                    # Create Razorpay order
                    order_result = razorpay_mixin.create_razorpay_order(
                        amount=float(amount),
                        currency="INR",
                        receipt=merchant_transaction_id,
                        notes=notes,
                    )
                    
                    if not order_result.get("success"):
                        payment_log["response"] = {
                            "error": order_result.get("error", "Failed to create Razorpay order")
                        }
                        custom_response = self.get_error_response(
                            message=order_result.get("error", "Failed to create Razorpay order"),
                            status="error",
                            errors=[],
                            error_code="RAZORPAY_ORDER_ERROR",
                            status_code=status.HTTP_400_BAD_REQUEST,
                        )
                        create_wallet_payment_log(payment_log)
                        return custom_response
                    
                    # Store Razorpay order details in wallet transaction
                    razorpay_order_id = order_result.get("order_id")
                    
                    # Update wallet transaction with Razorpay order ID
                    from apps.customer.models import WalletTransaction
                    wallet_txn = WalletTransaction.objects.filter(
                        transaction_id=merchant_transaction_id
                    ).first()
                    if wallet_txn:
                        wallet_txn.transaction_details = f"Wallet recharge of {float(amount)} via RAZORPAY. Order ID: {razorpay_order_id}"
                        wallet_txn.payment_medium = "RAZORPAY"
                        wallet_txn.save()
                    
                    response_data = {
                        "order_id": razorpay_order_id,
                        "razorpay_key": settings.RAZORPAY_KEY_ID,
                        "amount": order_result.get("amount"),  # Amount in paise
                        "currency": order_result.get("currency"),
                        "merchant_transaction_id": merchant_transaction_id,
                        "name": getattr(user, "name", None) or user.email,
                        "email": user.email,
                        "contact": getattr(user, "mobile_number", "") or "",
                        "redirect_url": redirect_url,
                    }
                    
                    payment_log["response"] = response_data
                    custom_response = self.get_response(
                        status="success",
                        count=1,
                        data=response_data,
                        message="Razorpay payment order created successfully",
                        status_code=status.HTTP_200_OK,
                    )
                    create_wallet_payment_log(payment_log)
                    return custom_response
                    
                except Exception as e:
                    print(traceback.format_exc())
                    payment_log["response"] = {"message": str(e)}
                    custom_response = self.get_error_response(
                        message=f"Razorpay payment initiation failed: {str(e)}",
                        status="error",
                        errors=[],
                        error_code="RAZORPAY_INITIATION_ERROR",
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    )
                    create_wallet_payment_log(payment_log)
                    return custom_response

            else:
                custom_response = self.get_error_response(
                    message="Invalid payment channel. Use PHONE PAY or RAZORPAY",
                    status="error",
                    errors=[],
                    error_code="VALIDATION_ERROR",
                    status_code=status.HTTP_400_BAD_REQUEST,
                )
                return custom_response
        except Exception as e:
            print(traceback.format_exc())
            payment_log["response"] = {"message": str(e)}
            custom_response = self.get_error_response(
                message=str(e),
                status="error",
                errors=[],
                error_code="INTERNAL_SERVER_ERROR",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
            create_wallet_payment_log(payment_log)

            return custom_response

    @action(
        detail=False,
        methods=["POST"],
        url_path="razorpay/verify",
        url_name="razorpay-wallet-verify",
        permission_classes=[AllowAny],
    )
    def razorpay_wallet_verify(self, request):
        """Verify Razorpay payment for wallet recharge"""
        try:
            self.log_info("=== RAZORPAY WALLET VERIFY ENDPOINT CALLED ===")
            self.log_info(f"Request data: {request.data}")
            
            payment_log = {}
            
            razorpay_order_id = request.data.get("razorpay_order_id")
            razorpay_payment_id = request.data.get("razorpay_payment_id")
            razorpay_signature = request.data.get("razorpay_signature")
            
            self.log_info(f"Received - order_id: {razorpay_order_id}, payment_id: {razorpay_payment_id}, signature: {razorpay_signature[:20] if razorpay_signature else None}...")
            
            if not all([razorpay_order_id, razorpay_payment_id, razorpay_signature]):
                self.log_error("Missing required fields in Razorpay verify request")
                return self.get_error_response(
                    message="Missing required fields: razorpay_order_id, razorpay_payment_id, razorpay_signature",
                    status="error",
                    errors=[],
                    error_code="VALIDATION_ERROR",
                    status_code=status.HTTP_400_BAD_REQUEST,
                )
            
            payment_log["razorpay_order_id"] = razorpay_order_id
            payment_log["razorpay_payment_id"] = razorpay_payment_id
            
            razorpay_mixin = RazorpayMixin()
            
            # Verify signature
            self.log_info(f"Verifying payment signature for order_id: {razorpay_order_id}, payment_id: {razorpay_payment_id}")
            is_valid = razorpay_mixin.verify_payment_signature(
                razorpay_order_id, razorpay_payment_id, razorpay_signature
            )
            
            if not is_valid:
                self.log_error(f"Invalid signature for order_id: {razorpay_order_id}, payment_id: {razorpay_payment_id}")
                payment_log["response"] = {"error": "Invalid signature"}
                create_wallet_payment_log(payment_log)
                return self.get_error_response(
                    message="Payment signature verification failed",
                    status="error",
                    errors=[],
                    error_code="SIGNATURE_INVALID",
                    status_code=status.HTTP_400_BAD_REQUEST,
                )
            
            self.log_info(f"Signature verified successfully for payment_id: {razorpay_payment_id}")
            
            # Get payment details from Razorpay
            self.log_info(f"Fetching payment details from Razorpay for payment_id: {razorpay_payment_id}")
            payment_result = razorpay_mixin.get_payment_details(razorpay_payment_id)
            if not payment_result.get("success"):
                self.log_error(f"Failed to fetch payment details: {payment_result.get('error')}")
                payment_log["response"] = {"error": payment_result.get("error")}
                create_wallet_payment_log(payment_log)
                return self.get_error_response(
                    message=f"Failed to fetch payment details: {payment_result.get('error')}",
                    status="error",
                    errors=[],
                    error_code="PAYMENT_FETCH_ERROR",
                    status_code=status.HTTP_400_BAD_REQUEST,
                )
            
            payment_data = payment_result.get("payment", {})
            payment_status = payment_data.get("status")
            amount = float(payment_data.get("amount", 0)) / 100  # Convert from paise
            
            self.log_info(f"Payment status from Razorpay: {payment_status}, Amount: {amount}")
            
            # Get merchant_transaction_id from order notes
            self.log_info(f"Fetching order details from Razorpay for order_id: {razorpay_order_id}")
            order_result = razorpay_mixin.get_order_details(razorpay_order_id)
            if not order_result.get("success"):
                self.log_error(f"Order not found in Razorpay: {razorpay_order_id}")
                payment_log["response"] = {"error": "Order not found"}
                create_wallet_payment_log(payment_log)
                return self.get_error_response(
                    message="Razorpay order not found",
                    status="error",
                    errors=[],
                    error_code="ORDER_NOT_FOUND",
                    status_code=status.HTTP_404_NOT_FOUND,
                )
            
            order_data = order_result.get("order", {})
            notes = order_data.get("notes", {})
            merchant_transaction_id = notes.get("merchant_transaction_id")
            user_id = notes.get("user_id")
            company_id = notes.get("company_id")
            agent_id = notes.get("agent_id")
            
            self.log_info(f"Order notes - merchant_transaction_id: {merchant_transaction_id}, user_id: {user_id}, company_id: {company_id}, agent_id: {agent_id}")
            
            if company_id:
                try:
                    company_id = int(company_id)
                except (ValueError, TypeError):
                    company_id = None
            
            if user_id:
                try:
                    user_id = int(user_id)
                except (ValueError, TypeError):
                    user_id = None
            
            if agent_id:
                try:
                    agent_id = int(agent_id)
                except (ValueError, TypeError):
                    agent_id = None
            
            payment_log["merchant_transaction_id"] = merchant_transaction_id
            
            if payment_status == "captured":
                self.log_info(f"Payment is CAPTURED. Processing wallet update for transaction_id: {merchant_transaction_id}")
                
                # Payment successful - update wallet
                payment_details = {
                    "transaction_id": razorpay_payment_id,
                    "code": "PAYMENT_SUCCESS",
                    "transaction_details": f"Razorpay payment successful. Payment ID: {razorpay_payment_id}",
                    "payment_type": "PAYMENT GATEWAY",
                    "payment_medium": "RAZORPAY",
                    "amount": amount,
                    "is_transaction_success": True,
                    "status": "Completed",
                }
                
                self.log_info(f"Updating wallet transaction with details: {payment_details}")
                txn_result = process_wallet_recharge_transaction_once(
                    merchant_transaction_id, payment_details
                )
                user_id = txn_result.get("user_id")
                company_id = txn_result.get("company_id")
                agent_id = txn_result.get("agent_id")
                self.log_info(
                    f"Wallet transaction update result - user_id: {user_id}, company_id: {company_id}, agent_id: {agent_id}, already_processed: {txn_result.get('already_processed')}"
                )
                
                # Verify the transaction was updated
                from apps.customer.models import WalletTransaction
                wallet_txn_check = WalletTransaction.objects.filter(
                    transaction_id=merchant_transaction_id
                ).first()
                if wallet_txn_check:
                    self.log_info(f"Transaction after update - status: {wallet_txn_check.status}, is_success: {wallet_txn_check.is_transaction_success}, code: {wallet_txn_check.code}")
                else:
                    self.log_warning(f"Transaction not found after update attempt: {merchant_transaction_id}")
                
                # Get user_id, company_id, and agent_id - try from notes first, then from WalletTransaction
                if not user_id and not company_id and not agent_id:
                    from apps.customer.models import WalletTransaction
                    wallet_txn = WalletTransaction.objects.filter(
                        transaction_id=merchant_transaction_id
                    ).first()
                    if wallet_txn:
                        if wallet_txn.user:
                            user_id = wallet_txn.user.id
                        company_id = wallet_txn.company_id if wallet_txn.company_id else None
                        agent_id = wallet_txn.agent.id if wallet_txn.agent else None
                        self.log_info(f"Retrieved from WalletTransaction - user_id: {user_id}, company_id: {company_id}, agent_id: {agent_id}")
                
                self.log_info(f"Final user_id: {user_id}, company_id: {company_id}, agent_id: {agent_id}, amount: {amount}")
                
                # Recharge the wallet
                if txn_result.get("already_processed"):
                    self.log_info(
                        f"Skipping duplicate wallet credit for transaction {merchant_transaction_id}; already processed"
                    )
                elif user_id or company_id or agent_id:
                    self.log_info(f"Calling update_wallet_recharge_details with user_id={user_id}, company_id={company_id}, agent_id={agent_id}, amount={amount}")
                    wallet_update_result = update_wallet_recharge_details(user_id, company_id, amount, agent_id)
                    self.log_info(f"Wallet recharge update result: {wallet_update_result}")
                    
                    # Verify wallet balance was updated
                    from apps.customer.models import Wallet
                    if agent_id:
                        wallet = Wallet.objects.filter(agent_id=agent_id, active=True).first()
                        if wallet:
                            self.log_info(f"Agent wallet balance after recharge: {wallet.balance}")
                    elif user_id and not company_id:
                        wallet = Wallet.objects.filter(user__id=user_id, company_id__isnull=True, agent_id__isnull=True).first()
                        if wallet:
                            self.log_info(f"User wallet balance after recharge: {wallet.balance}")
                    elif company_id:
                        wallet = Wallet.objects.filter(company_id=company_id).first()
                        if wallet:
                            self.log_info(f"Company wallet balance after recharge: {wallet.balance}")
                    
                    payment_log["response"] = {"success": True, "amount": amount}
                    if user_id:
                        payment_log["user_id"] = user_id
                    if company_id:
                        payment_log["company_id"] = company_id
                    if agent_id:
                        payment_log["agent_id"] = agent_id
                    create_wallet_payment_log(payment_log)
                    
                    # Send SMS notification (same as PhonePe)
                    from apps.booking.tasks import send_booking_sms_task
                    from apps.customer.models import Wallet
                    from apps.authentication.models import User
                    from apps.org_resources.models import AgentDetail
                    
                    if agent_id:
                        wallet_balance = 0
                        wallet = Wallet.objects.filter(agent_id=agent_id, active=True).first()
                        if wallet:
                            wallet_balance = wallet.balance
                            self.log_info(f"Razorpay verify - agent wallet_balance: {wallet_balance}")
                        
                        agent = AgentDetail.objects.filter(id=agent_id).first()
                        if agent and agent.contact_mobile_number:
                            # Get the user associated with the agent for SMS
                            agent_user = agent.added_user
                            if agent_user and agent_user.mobile_number:
                                self.log_info(f"Razorpay verify - agent recharge_amount: {amount}, mobile_number: {agent_user.mobile_number}, agent_id: {agent_id}")
                                send_booking_sms_task.apply_async(
                                    kwargs={
                                        "notification_type": "WALLET_RECHARGE_CONFIRMATION",
                                        "params": {
                                            "user_id": agent_user.id,
                                            "recharge_amount": float(amount),
                                            "wallet_balance": wallet_balance,
                                        },
                                    }
                                )
                    elif user_id and not company_id:
                        wallet_balance = 0
                        wallet = Wallet.objects.filter(
                            user__id=user_id, company_id__isnull=True, agent_id__isnull=True
                        ).first()
                        if wallet:
                            wallet_balance = wallet.balance
                            print("Razorpay verify - wallet_balance", wallet_balance)
                        
                        user = User.objects.get(id=user_id)
                        if user and user.mobile_number:
                            print(
                                "Razorpay verify - recharge_amount, mobile_number, user_id ",
                                amount,
                                user.mobile_number,
                                user_id,
                            )
                            send_booking_sms_task.apply_async(
                                kwargs={
                                    "notification_type": "WALLET_RECHARGE_CONFIRMATION",
                                    "params": {
                                        "user_id": user_id,
                                        "recharge_amount": float(amount),
                                        "wallet_balance": wallet_balance,
                                    },
                                }
                            )
                    elif company_id and user_id:
                        wallet_balance = 0
                        wallet = Wallet.objects.filter(company_id=company_id).first()
                        if wallet:
                            wallet_balance = wallet.balance
                            print("Razorpay verify - company_wallet_balance", wallet_balance)
                        
                        user = User.objects.get(id=user_id)
                        if user and user.mobile_number:
                            print(
                                "Razorpay verify - company recharge_amount, mobile_number, user_id, company_id ",
                                amount,
                                user.mobile_number,
                                user_id,
                                company_id,
                            )
                            send_booking_sms_task.apply_async(
                                kwargs={
                                    "notification_type": "WALLET_RECHARGE_CONFIRMATION",
                                    "params": {
                                        "user_id": user_id,
                                        "recharge_amount": float(amount),
                                        "wallet_balance": wallet_balance,
                                        "company_id": company_id,
                                    },
                                }
                            )
                else:
                    self.log_error(f"WARNING: No user_id, company_id, or agent_id found for transaction {merchant_transaction_id}")
                    payment_log["response"] = {"error": "No user_id, company_id, or agent_id found"}
                    create_wallet_payment_log(payment_log)
                    return self.get_error_response(
                        message="Unable to identify user, company, or agent for wallet recharge",
                        status="error",
                        errors=[],
                        error_code="USER_NOT_FOUND",
                        status_code=status.HTTP_400_BAD_REQUEST,
                    )
                
                self.log_info(f"=== RAZORPAY WALLET VERIFY SUCCESS - Payment ID: {razorpay_payment_id}, Order ID: {razorpay_order_id} ===")
                fee_breakdown = {}
                try:
                    from apps.payment_gateways.utils.razorpay_fees import (
                        actual_fee_from_payment_entity,
                    )

                    attach_razorpay_fee_metadata(razorpay_payment_id, payment_data)
                    fee_breakdown = actual_fee_from_payment_entity(payment_data)
                except Exception:
                    self.log_error(
                        "Failed to persist Razorpay fee metadata on wallet transaction",
                        exc_info=True,
                    )
                return self.get_response(
                    status="success",
                    data={
                        "payment_id": razorpay_payment_id,
                        "order_id": razorpay_order_id,
                        "amount": amount,
                        "status": "completed",
                        "razorpay_fee": fee_breakdown,
                    },
                    message="Wallet recharged successfully",
                    status_code=status.HTTP_200_OK,
                )
            else:
                # Payment failed
                self.log_warning(f"Payment status is NOT captured: {payment_status}. Marking transaction as failed.")
                payment_details = {
                    "transaction_id": razorpay_payment_id,
                    "code": "PAYMENT_FAILED",
                    "transaction_details": f"Razorpay payment failed. Status: {payment_status}",
                    "payment_type": "PAYMENT GATEWAY",
                    "payment_medium": "RAZORPAY",
                    "amount": amount,
                    "is_transaction_success": False,
                    "status": "Failed",
                }
                
                self.log_info(f"Updating wallet transaction as failed: {payment_details}")
                user_id, company_id, agent_id = update_wallet_transaction_detail(merchant_transaction_id, payment_details)
                if user_id:
                    payment_log["user_id"] = user_id
                if company_id:
                    payment_log["company_id"] = company_id
                if agent_id:
                    payment_log["agent_id"] = agent_id
                
                payment_log["response"] = {"success": False, "status": payment_status}
                create_wallet_payment_log(payment_log)
                
                return self.get_error_response(
                    message=f"Payment failed with status: {payment_status}",
                    status="error",
                    errors=[],
                    error_code="PAYMENT_FAILED",
                    status_code=status.HTTP_400_BAD_REQUEST,
                )
                
        except Exception as e:
            self.log_error(f"Exception in Razorpay wallet verify: {str(e)}")
            self.log_error(traceback.format_exc())
            payment_log["response"] = {"error": str(e)}
            create_wallet_payment_log(payment_log)
            return self.get_error_response(
                message=f"Payment verification failed: {str(e)}",
                status="error",
                errors=[],
                error_code="VERIFICATION_ERROR",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(
        detail=False,
        methods=["POST"],
        url_path="razorpay/webhook",
        url_name="razorpay-wallet-webhook",
        permission_classes=[],
    )
    def razorpay_wallet_webhook(self, request):
        """Handle Razorpay webhook for wallet recharge"""
        try:
            self.log_info("=== RAZORPAY WALLET WEBHOOK ENDPOINT CALLED ===")
            self.log_info(f"Request headers: {dict(request.META)}")
            self.log_info(f"Request body: {request.body}")
            
            payment_log = {}
            
            # Get raw body for signature verification
            raw_body = request.body
            signature = request.META.get("HTTP_X_RAZORPAY_SIGNATURE", "")
            
            self.log_info(f"Webhook signature received: {signature[:20] if signature else 'None'}...")
            
            razorpay_mixin = RazorpayMixin()
            
            # Verify webhook signature
            if signature and not razorpay_mixin.verify_webhook_signature(raw_body, signature):
                self.log_error("Invalid webhook signature")
                payment_log["response"] = {"error": "Invalid webhook signature"}
                create_wallet_payment_log(payment_log)
                return self.get_error_response(
                    message="Invalid webhook signature",
                    status="error",
                    errors=[],
                    error_code="INVALID_SIGNATURE",
                    status_code=status.HTTP_400_BAD_REQUEST,
                )
            
            self.log_info("Webhook signature verified successfully")
            
            payload = request.data
            event = payload.get("event")
            
            self.log_info(f"Webhook event: {event}")
            payment_log["event"] = event
            
            if event == "payment.captured":
                self.log_info("Processing payment.captured event")
                payment_entity = payload.get("payload", {}).get("payment", {}).get("entity", {})
                razorpay_payment_id = payment_entity.get("id")
                razorpay_order_id = payment_entity.get("order_id")
                amount = float(payment_entity.get("amount", 0)) / 100
                
                self.log_info(f"Webhook payment details - payment_id: {razorpay_payment_id}, order_id: {razorpay_order_id}, amount: {amount}")
                
                payment_log["razorpay_payment_id"] = razorpay_payment_id
                payment_log["razorpay_order_id"] = razorpay_order_id
                
                # Get order details
                self.log_info(f"Fetching order details for order_id: {razorpay_order_id}")
                order_result = razorpay_mixin.get_order_details(razorpay_order_id)
                if order_result.get("success"):
                    order_data = order_result.get("order", {})
                    notes = order_data.get("notes", {})
                    
                    self.log_info(f"Order notes: {notes}")
                    
                    # Only process if it's a wallet recharge transaction
                    transaction_type = notes.get("transaction_type")
                    self.log_info(f"Transaction type from notes: {transaction_type}")
                    
                    if transaction_type == "wallet_recharge":
                        self.log_info("Transaction type is wallet_recharge, processing...")
                        merchant_transaction_id = notes.get("merchant_transaction_id")
                        user_id = notes.get("user_id")
                        company_id = notes.get("company_id")
                        agent_id = notes.get("agent_id")
                        
                        self.log_info(f"Webhook - merchant_transaction_id: {merchant_transaction_id}, user_id: {user_id}, company_id: {company_id}, agent_id: {agent_id}")
                        
                        if company_id:
                            try:
                                company_id = int(company_id)
                            except (ValueError, TypeError):
                                company_id = None
                        
                        if user_id:
                            try:
                                user_id = int(user_id)
                            except (ValueError, TypeError):
                                user_id = None
                        
                        if agent_id:
                            try:
                                agent_id = int(agent_id)
                            except (ValueError, TypeError):
                                agent_id = None
                        
                        # Update wallet transaction
                        payment_details = {
                            "transaction_id": razorpay_payment_id,
                            "code": "PAYMENT_SUCCESS",
                            "transaction_details": f"Razorpay webhook payment successful. Payment ID: {razorpay_payment_id}",
                            "payment_type": "PAYMENT GATEWAY",
                            "payment_medium": "RAZORPAY",
                            "amount": amount,
                            "is_transaction_success": True,
                            "status": "Completed",
                        }
                        
                        self.log_info(f"Webhook - Updating wallet transaction with details: {payment_details}")
                        # Store agent_id from notes before transaction processing
                        agent_id_from_notes = agent_id
                        txn_result = process_wallet_recharge_transaction_once(
                            merchant_transaction_id, payment_details
                        )
                        user_id = txn_result.get("user_id")
                        company_id = txn_result.get("company_id")
                        agent_id_from_db = txn_result.get("agent_id")
                        self.log_info(f"Webhook - Wallet transaction update result - user_id: {user_id}, company_id: {company_id}, agent_id: {agent_id_from_db}")
                        
                        # Prioritize agent_id: first from notes, then from database transaction, then from WalletTransaction object
                        if agent_id_from_notes:
                            agent_id = agent_id_from_notes
                            self.log_info(f"Webhook - Using agent_id from notes: {agent_id}")
                        elif agent_id_from_db:
                            agent_id = agent_id_from_db
                            self.log_info(f"Webhook - Using agent_id from transaction: {agent_id}")
                        else:
                            # If agent_id is not in notes and not in transaction, try to get from WalletTransaction
                            from apps.customer.models import WalletTransaction
                            wallet_txn = WalletTransaction.objects.filter(
                                transaction_id=merchant_transaction_id
                            ).first()
                            if wallet_txn and wallet_txn.agent:
                                agent_id = wallet_txn.agent.id
                                self.log_info(f"Webhook - Retrieved agent_id from WalletTransaction: {agent_id}")
                            else:
                                agent_id = None
                        
                        # Verify the transaction was updated
                        from apps.customer.models import WalletTransaction
                        wallet_txn_check = WalletTransaction.objects.filter(
                            transaction_id=merchant_transaction_id
                        ).first()
                        if wallet_txn_check:
                            self.log_info(f"Webhook - Transaction after update - status: {wallet_txn_check.status}, is_success: {wallet_txn_check.is_transaction_success}, code: {wallet_txn_check.code}")
                        else:
                            self.log_warning(f"Webhook - Transaction not found after update attempt: {merchant_transaction_id}")
                        
                        # Get user_id and company_id if not already set - try from WalletTransaction
                        if not user_id or not company_id:
                            from apps.customer.models import WalletTransaction
                            wallet_txn = WalletTransaction.objects.filter(
                                transaction_id=merchant_transaction_id
                            ).first()
                            if wallet_txn:
                                if not user_id and wallet_txn.user:
                                    user_id = wallet_txn.user.id
                                if not company_id:
                                    company_id = wallet_txn.company_id if wallet_txn.company_id else None
                                self.log_info(f"Webhook - Retrieved from WalletTransaction - user_id: {user_id}, company_id: {company_id}")
                        
                        self.log_info(f"Webhook - Final user_id: {user_id}, company_id: {company_id}, agent_id: {agent_id}, amount: {amount}")
                        
                        # Recharge the wallet
                        if txn_result.get("already_processed"):
                            self.log_info(
                                f"Webhook - Skipping duplicate wallet credit for transaction {merchant_transaction_id}; already processed"
                            )
                        elif user_id or company_id or agent_id:
                            self.log_info(f"Webhook - Calling update_wallet_recharge_details with user_id={user_id}, company_id={company_id}, agent_id={agent_id}, amount={amount}")
                            wallet_update_result = update_wallet_recharge_details(user_id, company_id, amount, agent_id)
                            self.log_info(f"Webhook - Wallet recharge update result: {wallet_update_result}")
                            try:
                                attach_razorpay_fee_metadata(
                                    razorpay_payment_id, payment_entity
                                )
                            except Exception:
                                self.log_error(
                                    "Webhook: failed to attach Razorpay fee metadata",
                                    exc_info=True,
                                )

                            # Verify wallet balance was updated
                            from apps.customer.models import Wallet
                            if agent_id:
                                wallet = Wallet.objects.filter(agent_id=agent_id, active=True).first()
                                if wallet:
                                    self.log_info(f"Webhook - Agent wallet balance after recharge: {wallet.balance}")
                            elif user_id and not company_id:
                                wallet = Wallet.objects.filter(user__id=user_id, company_id__isnull=True, agent_id__isnull=True).first()
                                if wallet:
                                    self.log_info(f"Webhook - User wallet balance after recharge: {wallet.balance}")
                            elif company_id:
                                wallet = Wallet.objects.filter(company_id=company_id).first()
                                if wallet:
                                    self.log_info(f"Webhook - Company wallet balance after recharge: {wallet.balance}")
                            
                            # Send SMS notification (same as PhonePe)
                            from apps.booking.tasks import send_booking_sms_task
                            from apps.customer.models import Wallet
                            from apps.authentication.models import User
                            from apps.org_resources.models import AgentDetail
                            
                            if agent_id:
                                wallet_balance = 0
                                wallet = Wallet.objects.filter(agent_id=agent_id, active=True).first()
                                if wallet:
                                    wallet_balance = wallet.balance
                                
                                agent = AgentDetail.objects.filter(id=agent_id).first()
                                if agent and agent.contact_mobile_number:
                                    # Get the user associated with the agent for SMS
                                    agent_user = agent.added_user
                                    if agent_user and agent_user.mobile_number:
                                        send_booking_sms_task.apply_async(
                                            kwargs={
                                                "notification_type": "WALLET_RECHARGE_CONFIRMATION",
                                                "params": {
                                                    "user_id": agent_user.id,
                                                    "recharge_amount": float(amount),
                                                    "wallet_balance": wallet_balance,
                                                },
                                            }
                                        )
                            elif user_id and not company_id:
                                wallet_balance = 0
                                wallet = Wallet.objects.filter(
                                    user__id=user_id, company_id__isnull=True, agent_id__isnull=True
                                ).first()
                                if wallet:
                                    wallet_balance = wallet.balance
                                
                                user = User.objects.get(id=user_id)
                                if user and user.mobile_number:
                                    send_booking_sms_task.apply_async(
                                        kwargs={
                                            "notification_type": "WALLET_RECHARGE_CONFIRMATION",
                                            "params": {
                                                "user_id": user_id,
                                                "recharge_amount": float(amount),
                                                "wallet_balance": wallet_balance,
                                            },
                                        }
                                    )
                            elif company_id and user_id:
                                wallet_balance = 0
                                wallet = Wallet.objects.filter(company_id=company_id).first()
                                if wallet:
                                    wallet_balance = wallet.balance
                                
                                user = User.objects.get(id=user_id)
                                if user and user.mobile_number:
                                    send_booking_sms_task.apply_async(
                                        kwargs={
                                            "notification_type": "WALLET_RECHARGE_CONFIRMATION",
                                            "params": {
                                                "user_id": user_id,
                                                "recharge_amount": float(amount),
                                                "wallet_balance": wallet_balance,
                                                "company_id": company_id,
                                            },
                                        }
                                    )
                        else:
                            self.log_warning(f"Webhook - No user_id or company_id found for transaction {merchant_transaction_id}")
                        
                        payment_log["response"] = {"success": True}
                        create_wallet_payment_log(payment_log)
                        self.log_info(f"=== RAZORPAY WEBHOOK SUCCESS - Payment ID: {razorpay_payment_id}, Order ID: {razorpay_order_id} ===")
                    else:
                        self.log_info(f"Webhook - Skipping transaction (not wallet_recharge). Transaction type: {transaction_type}")
                else:
                    self.log_error(f"Webhook - Failed to fetch order details for order_id: {razorpay_order_id}")
            
            elif event == "payment.failed":
                self.log_warning("Processing payment.failed event")
                payment_entity = payload.get("payload", {}).get("payment", {}).get("entity", {})
                razorpay_payment_id = payment_entity.get("id")
                razorpay_order_id = payment_entity.get("order_id")
                
                self.log_info(f"Webhook - Failed payment - payment_id: {razorpay_payment_id}, order_id: {razorpay_order_id}")
                
                # Get order details and update transaction as failed
                order_result = razorpay_mixin.get_order_details(razorpay_order_id)
                if order_result.get("success"):
                    order_data = order_result.get("order", {})
                    notes = order_data.get("notes", {})
                    
                    if notes.get("transaction_type") == "wallet_recharge":
                        merchant_transaction_id = notes.get("merchant_transaction_id")
                        
                        self.log_info(f"Webhook - Updating transaction as failed: {merchant_transaction_id}")
                        payment_details = {
                            "transaction_id": razorpay_payment_id,
                            "code": "PAYMENT_FAILED",
                            "transaction_details": "Razorpay webhook payment failed",
                            "is_transaction_success": False,
                            "status": "Failed",
                        }
                        
                        user_id, company_id, agent_id = update_wallet_transaction_detail(merchant_transaction_id, payment_details)
                        if user_id:
                            payment_log["user_id"] = user_id
                        if company_id:
                            payment_log["company_id"] = company_id
                        if agent_id:
                            payment_log["agent_id"] = agent_id
                
                payment_log["response"] = {"success": False, "event": event}
                create_wallet_payment_log(payment_log)
            else:
                self.log_info(f"Webhook - Unhandled event type: {event}")
            
            return self.get_response(
                status="success",
                data={"received": True},
                message="Webhook processed",
                status_code=status.HTTP_200_OK,
            )
            
        except Exception as e:
            self.log_error(f"Exception in Razorpay webhook: {str(e)}")
            self.log_error(traceback.format_exc())
            return self.get_error_response(
                message=f"Webhook processing failed: {str(e)}",
                status="error",
                errors=[],
                error_code="WEBHOOK_ERROR",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(
        detail=False,
        methods=["POST"],
        url_path="phone-pay/callbackurl",
        url_name="phone-pay-callbackurl",
        permission_classes=[],
    )
    def phone_pay_callbackurl(self, request):
        try:
            payment_log = {}
            x_verify = request.META.get("HTTP_X_VERIFY", None)
            if x_verify:
                payment_log["x_verify"] = x_verify
            response = request.data.get("response", None)

            if not response:
                custom_response = self.get_error_response(
                    message="Error in Response",
                    status="error",
                    errors=[],
                    error_code="VALIDATION_ERROR",
                    status_code=status.HTTP_400_BAD_REQUEST,
                )
                payment_log["request"] = {"message": "empty request"}
                # log
                create_wallet_payment_log(payment_log)
                return custom_response

            payment_log["request"] = {"response": response}
            data = base64.b64decode(response)
            decoded_data = data.decode("utf-8")
            json_data = json.loads(decoded_data)
            payment_log["request"] = json_data

            code = json_data.get("code", "")
            message = json_data.get("message", "")

            sub_json_data = json_data.get("data", {})
            amount = int(sub_json_data.get("amount", 0)) / 100
            merchant_transaction_id = sub_json_data.get("merchantTransactionId", "")
            payment_log["merchant_transaction_id"] = merchant_transaction_id
            transaction_id = sub_json_data.get("transactionId", "")
            state = sub_json_data.get("state", "")
            print(json_data)

            payment_details = {
                "transaction_id": merchant_transaction_id,
                "code": code,
                "transaction_details": message,
                "payment_type": "PAYMENT GATEWAY",
                "payment_medium": "PHONE PAY",
                "amount": amount,
            }

            # Check both code and state for payment success (same as flight payment callbacks)
            is_success = code == "PAYMENT_SUCCESS" and state == "COMPLETED"
            
            if is_success:
                payment_details["is_transaction_success"] = True
                payment_details["status"] = "Completed"

                # update wallet transaction and wallet
                user_id, company_id, agent_id = update_wallet_transaction_detail(
                    merchant_transaction_id, payment_details
                )
                
                print(f"PhonePe callback - user_id: {user_id}, company_id: {company_id}, agent_id: {agent_id}, amount: {amount}")

                # Recharge the wallet (company, agent, or user)
                if user_id or company_id or agent_id:
                    update_wallet_recharge_details(user_id, company_id, amount, agent_id)
                else:
                    print(f"WARNING: PhonePe callback - No user_id, company_id, or agent_id found for transaction {merchant_transaction_id}")
                    # Try to get from WalletTransaction directly
                    from apps.customer.models import WalletTransaction
                    wallet_txn = WalletTransaction.objects.filter(
                        transaction_id=merchant_transaction_id
                    ).first()
                    if wallet_txn:
                        if wallet_txn.user:
                            user_id = wallet_txn.user.id
                        company_id = wallet_txn.company_id if wallet_txn.company_id else None
                        agent_id = wallet_txn.agent.id if wallet_txn.agent else None
                        print(f"Retrieved from WalletTransaction - user_id: {user_id}, company_id: {company_id}, agent_id: {agent_id}")
                        if user_id or company_id or agent_id:
                            update_wallet_recharge_details(user_id, company_id, amount, agent_id)

                # Send SMS notification for user wallet recharge
                if user_id and not company_id:
                    wallet_balance = 0
                    wallet = Wallet.objects.filter(
                        user__id=user_id, company_id__isnull=True
                    ).first()
                    if wallet:
                        wallet_balance = wallet.balance
                        print("wallet_balance", wallet_balance)

                        user = User.objects.get(id=user_id)
                        if user and user.mobile_number:
                            print(
                                "recharge_amount, mobile_number,user_id ",
                                amount,
                                user.mobile_number,
                                user_id,
                            )
                            send_booking_sms_task.apply_async(
                                kwargs={
                                    "notification_type": "WALLET_RECHARGE_CONFIRMATION",
                                    "params": {
                                        "user_id": user_id,
                                        "recharge_amount": amount,
                                        "wallet_balance": wallet_balance,
                                    },
                                }
                            )
                # Send SMS notification for company wallet recharge
                elif company_id and user_id:
                    wallet_balance = 0
                    wallet = Wallet.objects.filter(company_id=company_id).first()
                    if wallet:
                        wallet_balance = wallet.balance
                        print("company_wallet_balance", wallet_balance)

                        user = User.objects.get(id=user_id)
                        if user and user.mobile_number:
                            print(
                                "company recharge_amount, mobile_number,user_id,company_id ",
                                amount,
                                user.mobile_number,
                                user_id,
                                company_id,
                            )
                            send_booking_sms_task.apply_async(
                                kwargs={
                                    "notification_type": "WALLET_RECHARGE_CONFIRMATION",
                                    "params": {
                                        "user_id": user_id,
                                        "recharge_amount": amount,
                                        "wallet_balance": wallet_balance,
                                        "company_id": company_id,
                                    },
                                }
                            )

                if user_id:
                    payment_log["user_id"] = user_id
                if company_id:
                    payment_log["company_id"] = company_id
            else:
                payment_details["is_transaction_success"] = False
                payment_details["status"] = "Failed"
                user_id, company_id, agent_id = update_wallet_transaction_detail(
                    merchant_transaction_id, payment_details
                )
                if user_id:
                    payment_log["user_id"] = user_id
                if company_id:
                    payment_log["company_id"] = company_id
                if agent_id:
                    payment_log["agent_id"] = agent_id
                if code == "PAYMENT_ERROR" and user_id:
                    send_booking_sms_task.apply_async(
                        kwargs={
                            "notification_type": "PAYMENT_FAILED_INFO",
                            "params": {
                                "user_id": user_id,
                                "failed_amount": float(amount),
                                "payment_purpose": "Wallet Recharge",
                            },
                        }
                    )

            payment_details["phone_pe_transaction_id"] = transaction_id

            custom_response = self.get_response(
                status="success",
                data=payment_details,  # Use the data from the default response
                message="Wallet Recharge",
                status_code=status.HTTP_200_OK,  # 200 for successful retrieval
            )
            payment_log["response"] = payment_details
            create_wallet_payment_log(payment_log)
            return custom_response

        except Exception as e:
            custom_response = self.get_error_response(
                message=str(e),
                status="error",
                errors=[],
                error_code="INTERNAL_SERVER_ERROR",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
            payment_log["response"] = {"message": str(e)}
            create_wallet_payment_log(payment_log)
            return custom_response

    @action(
        detail=False,
        methods=["POST"],
        url_path="wallet-recharge",
        url_name="wallet_recharge",
    )
    def wallet_bank_recharge(self, request):
        """
        API for wallet recharge through bank transfer
        User uploads payment proof image along with transaction details
        Supports user, company, and agent wallets
        """
        user = request.user
        serializer = WalletRechargeSerializer(data=request.data)

        if not serializer.is_valid():
            return self.get_error_response(
                message="Validation failed",
                status="error",
                errors=serializer.errors,
                error_code="VALIDATION_ERROR",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        try:
            validated_data = serializer.validated_data
            amount = validated_data["amount"]
            company_id = validated_data.get("company_id")
            agent_id = validated_data.get("agent_id")
            payment_type = validated_data["payment_type"]
            payment_medium = validated_data["payment_medium"]
            media = validated_data["media"]
            transaction_id = validated_data["transaction_id"]

            # Auto-detect agent if user is an agent and no agent_id/company_id specified
            from apps.booking.utils.agent_linking_utils import get_agent_for_user
            user_agent = get_agent_for_user(user)
            
            # Convert agent_id to int if it's provided as string
            if agent_id:
                try:
                    agent_id = int(agent_id)
                except (ValueError, TypeError):
                    agent_id = None
            elif user_agent and not company_id:
                # Auto-detect agent wallet if user is an agent
                agent_id = user_agent.id
            
            # Validate agent access
            if agent_id:
                if not (user.is_superuser or (user_agent and user_agent.id == agent_id)):
                    return self.get_error_response(
                        message="You don't have permission to recharge this agent wallet",
                        status="error",
                        errors=[],
                        error_code="PERMISSION_DENIED",
                        status_code=status.HTTP_403_FORBIDDEN,
                    )

            # Create wallet transaction entry
            wtransact_data = {
                "amount": amount,
                "transaction_type": "Credit",
                "transaction_for": "wallet_recharge",
                "transaction_id": transaction_id,
                "transaction_details": f"Wallet recharge of {float(amount)} with transaction id {transaction_id}",
                "payment_type": payment_type,
                "payment_medium": payment_medium,
                "is_transaction_success": False,
                "code": "PAYMENT_PENDING",
                "status": "Pending",
                "media": media,
            }

            if company_id:
                wtransact_data["company_id"] = company_id
            elif agent_id:
                wtransact_data["agent_id"] = agent_id
            else:
                wtransact_data["user_id"] = user.id

            # Create wallet transaction
            wallet_transaction = WalletTransaction.objects.create(**wtransact_data)

            response_data = {
                "transaction_id": transaction_id,
                "amount": str(float(amount)),
                "user_id": user.id,
                "company_id": company_id,
                "agent_id": agent_id,
                "transaction_type": "Credit",
                "transaction_for": "wallet_recharge",
                "transaction_details": f"Wallet recharge of {float(amount)} with transaction id {transaction_id}",
                "payment_type": payment_type,
                "payment_medium": payment_medium,
                "is_transaction_success": False,
                "code": "PAYMENT_PENDING",
                "status": "Pending",
                "media_url": (
                    wallet_transaction.media.url if wallet_transaction.media else None
                ),
                "created_at": wallet_transaction.created.isoformat(),
            }

            return self.get_response(
                status="success",
                count=1,
                data=response_data,
                message="Bank recharge request submitted successfully, waiting for admin approval.",
                status_code=status.HTTP_201_CREATED,
            )

        except Exception as e:
            print(traceback.format_exc())

            # Update transaction status to failed if transaction was created
            try:
                failed_transaction = WalletTransaction.objects.get(
                    transaction_id=transaction_id, status="Pending"
                )
                failed_transaction.status = "Failed"
                failed_transaction.is_transaction_success = False
                failed_transaction.code = "PAYMENT_ERROR"
                failed_transaction.save()
            except WalletTransaction.DoesNotExist:
                pass  # Transaction might not have been created yet

            return self.get_error_response(
                message=str(e),
                status="error",
                errors=[],
                error_code="INTERNAL_SERVER_ERROR",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(
        detail=False,
        methods=["POST"],
        url_path="approve-recharge",
        url_name="approve_recharge",
    )
    def approve_wallet_recharge(self, request):
        """
        API for admin to approve wallet recharge requests
        Admin verifies the amount and approves the transaction
        """
        # Add admin permission check here if needed
        # if not request.user.is_staff:
        #     return self.get_error_response(...)

        serializer = ApproveRechargeSerializer(data=request.data)

        if not serializer.is_valid():
            return self.get_error_response(
                message="Validation failed",
                status="error",
                errors=serializer.errors,
                error_code="VALIDATION_ERROR",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        if not finance_ops_admin_allowed(request):
            return self.get_error_response(
                message="You don't have permission to approve wallet recharges",
                status="error",
                errors=[],
                error_code="PERMISSION_DENIED",
                status_code=status.HTTP_403_FORBIDDEN,
            )

        try:
            validated_data = serializer.validated_data
            transaction_id = validated_data["transaction_id"]
            approve_amount = validated_data["amount"]

            # Get the wallet transaction
            try:
                wallet_transaction = WalletTransaction.objects.get(
                    transaction_id=transaction_id, status__in=["Pending", "Failed"]
                )
            except WalletTransaction.DoesNotExist:
                return self.get_error_response(
                    message="Transaction not found",
                    status="error",
                    errors=[],
                    error_code="TRANSACTION_NOT_FOUND",
                    status_code=status.HTTP_404_NOT_FOUND,
                )
            # Verify amount matches
            if wallet_transaction.amount != approve_amount:
                # Update transaction status to failed
                wallet_transaction.status = "Failed"
                wallet_transaction.is_transaction_success = False
                wallet_transaction.code = "PAYMENT_ERROR"
                wallet_transaction.save()

                return self.get_error_response(
                    message=f"Amount mismatch. Transaction amount: {float(wallet_transaction.amount)}, Approval amount: {float(approve_amount)}",
                    status="error",
                    errors=[
                        {
                            "transaction_amount": str(float(wallet_transaction.amount)),
                            "approval_amount": str(float(approve_amount)),
                        }
                    ],
                    error_code="AMOUNT_MISMATCH",
                    status_code=status.HTTP_400_BAD_REQUEST,
                )

            # Credit the wallet amount - prioritize in order: company > agent > user wallet
            success = False
            if wallet_transaction.company_id:
                success = add_company_wallet_amount(
                    wallet_transaction.company_id, approve_amount
                )
            elif wallet_transaction.agent_id:
                success = add_agent_wallet_amount(
                    wallet_transaction.agent_id, approve_amount
                )
            elif wallet_transaction.user_id:
                success = add_user_wallet_amount(
                    wallet_transaction.user_id, approve_amount
                )

            if not success:
                # Update transaction status to failed
                wallet_transaction.status = "Failed"
                wallet_transaction.is_transaction_success = False
                wallet_transaction.code = "PAYMENT_ERROR"
                wallet_transaction.save()

                return self.get_error_response(
                    message="Failed to credit wallet amount",
                    status="error",
                    errors=[],
                    error_code="WALLET_CREDIT_FAILED",
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

            # Update transaction status
            # For company/agent wallet scopes, keep user null to avoid
            # mixing personal and non-personal wallet transaction filters.
            if wallet_transaction.company_id or wallet_transaction.agent_id:
                wallet_transaction.user = None
            wallet_transaction.code = "PAYMENT_SUCCESS"
            wallet_transaction.is_transaction_success = True
            wallet_transaction.status = "Completed"
            wallet_transaction.save()

            # Create response data with complete transaction details
            response_data = {
                "transaction_id": transaction_id,
                "amount": str(float(approve_amount)),
                "user_id": wallet_transaction.user_id,
                "company_id": wallet_transaction.company_id,
                "agent_id": wallet_transaction.agent_id if wallet_transaction.agent else None,
                "transaction_type": wallet_transaction.transaction_type,
                "transaction_for": wallet_transaction.transaction_for,
                "transaction_details": wallet_transaction.transaction_details,
                "payment_type": wallet_transaction.payment_type,
                "payment_medium": wallet_transaction.payment_medium,
                "is_transaction_success": True,
                "code": "PAYMENT_SUCCESS",
                "status": "Completed",
                "media_url": (
                    wallet_transaction.media.url if wallet_transaction.media else None
                ),
                "approved_at": wallet_transaction.updated.isoformat(),
                "created_at": wallet_transaction.created.isoformat(),
                "message": "Wallet recharge approved and amount credited successfully",
            }

            return self.get_response(
                status="success",
                count=1,
                data=response_data,
                message="Wallet recharge approved and amount credited successfully",
                status_code=status.HTTP_200_OK,
            )
        except Exception as e:
            print(traceback.format_exc())

            # Update transaction status to failed if it exists and is pending
            try:
                validated_data = (
                    serializer.validated_data if serializer.is_valid() else {}
                )
                transaction_id = validated_data.get("transaction_id")
                if transaction_id:
                    failed_transaction = WalletTransaction.objects.get(
                        transaction_id=transaction_id, status="Pending"
                    )
                    failed_transaction.status = "Failed"
                    failed_transaction.is_transaction_success = False
                    failed_transaction.code = "PAYMENT_ERROR"
                    failed_transaction.save()
            except (WalletTransaction.DoesNotExist, KeyError):
                pass  # Transaction might not exist or serializer data unavailable

            return self.get_error_response(
                message=str(e),
                status="error",
                errors=[],
                error_code="INTERNAL_SERVER_ERROR",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @swagger_auto_schema(
        query_serializer=QueryFilterPendingRechargeSerializer,
        operation_description=(
            "List wallet recharge requests (bank transfer flow). "
            "Use query param `status` (Pending | Completed | Failed); "
            "omit it to default to Pending. Filter by `wallet_owner` "
            "(b2c | company | agent), ids, dates, etc."
        ),
        responses={200: PendingRechargeSerializer(many=True)},
    )
    @action(
        detail=False,
        methods=["GET"],
        url_path="pending-recharges",
        url_name="list_pending_recharges",
    )
    def list_pending_recharges(self, request):
        try:
            if not finance_ops_admin_allowed(request):
                return self.get_error_response(
                    message="You don't have permission to list pending wallet recharges",
                    status="error",
                    errors=[],
                    error_code="PERMISSION_DENIED",
                    status_code=status.HTTP_403_FORBIDDEN,
                )

            # Validate query parameters
            query_serializer = QueryFilterPendingRechargeSerializer(
                data=request.query_params
            )
            if not query_serializer.is_valid():
                return self.get_error_response(
                    message="Invalid query parameters",
                    status="error",
                    errors=query_serializer.errors,
                    error_code="VALIDATION_ERROR",
                    status_code=status.HTTP_400_BAD_REQUEST,
                )

            validated_data = query_serializer.validated_data

            # Bank / manual wallet recharge rows (status filtered below)
            queryset = (
                WalletTransaction.objects.filter(transaction_for="wallet_recharge")
                .select_related("user", "company", "agent")
                .prefetch_related("user__customer_profile")
            )

            status_raw = (validated_data.get("status") or "").strip()
            if status_raw:
                queryset = queryset.filter(status__iexact=status_raw)
            else:
                queryset = queryset.filter(status__iexact="Pending")

            wo = (validated_data.get("wallet_owner") or "").strip().lower()
            if wo == "b2c":
                queryset = queryset.filter(
                    user_id__isnull=False,
                    company_id__isnull=True,
                    agent_id__isnull=True,
                )
            elif wo == "company":
                queryset = queryset.filter(company_id__isnull=False)
            elif wo == "agent":
                queryset = queryset.filter(agent_id__isnull=False)

            # Apply filters
            user_id = validated_data.get("user_id")
            if user_id:
                queryset = queryset.filter(user_id=user_id)

            company_id = validated_data.get("company_id")
            if company_id:
                queryset = queryset.filter(company_id=company_id)

            agent_id = validated_data.get("agent_id")
            if agent_id:
                queryset = queryset.filter(agent_id=agent_id)

            transaction_id = validated_data.get("transaction_id")
            if transaction_id:
                queryset = queryset.filter(transaction_id__icontains=transaction_id)

            payment_type = validated_data.get("payment_type")
            if payment_type:
                queryset = queryset.filter(payment_type__iexact=payment_type)

            payment_medium = validated_data.get("payment_medium")
            if payment_medium:
                queryset = queryset.filter(payment_medium__iexact=payment_medium)

            # Date range filter
            start_date = validated_data.get("start_date")
            end_date = validated_data.get("end_date")
            if start_date:
                # If it's a date, convert to datetime for comparison
                from django.utils import timezone
                from datetime import datetime
                if hasattr(start_date, 'date') and not isinstance(start_date, datetime):
                    start_datetime = timezone.make_aware(
                        datetime.combine(start_date, datetime.min.time())
                    )
                else:
                    start_datetime = start_date
                queryset = queryset.filter(created__date__gte=start_date)
            if end_date:
                # If it's a date, convert to datetime for comparison (end of day)
                from django.utils import timezone
                from datetime import datetime
                if hasattr(end_date, 'date') and not isinstance(end_date, datetime):
                    end_datetime = timezone.make_aware(
                        datetime.combine(end_date, datetime.max.time())
                    )
                else:
                    end_datetime = end_date
                queryset = queryset.filter(created__date__lte=end_date)

            # Search filter - search by user name, email, mobile, or transaction_id
            search = validated_data.get("search")
            if search:
                search_query = Q(
                    Q(transaction_id__icontains=search) |
                    Q(user__name__icontains=search) |
                    Q(user__email__icontains=search) |
                    Q(user__mobile_number__icontains=search) |
                    Q(user__first_name__icontains=search) |
                    Q(user__last_name__icontains=search)
                )
                # Also search by agent name if agent exists
                if search:
                    search_query |= Q(agent__agent_name__icontains=search)
                queryset = queryset.filter(search_query)

            # Apply ordering
            ordering = validated_data.get("ordering")
            if ordering:
                # Validate ordering fields to prevent SQL injection
                allowed_fields = [
                    "created", "-created", "updated", "-updated",
                    "amount", "-amount", "transaction_id", "-transaction_id",
                    "payment_type", "-payment_type", "payment_medium", "-payment_medium"
                ]
                ordering_list = [o.strip() for o in ordering.split(",") if o.strip() in allowed_fields]
                if ordering_list:
                    queryset = queryset.order_by(*ordering_list)
                else:
                    # Default ordering if invalid
                    queryset = queryset.order_by("-created")
            else:
                # Default ordering
                queryset = queryset.order_by("-created")

            # Get total count before pagination
            total_count = queryset.count()

            # Apply pagination using your existing paginate_queryset function
            count, paginated_queryset = paginate_queryset(request, queryset)

            # Serialize the data
            serializer = PendingRechargeSerializer(paginated_queryset, many=True)

            return self.get_response(
                status="success",
                message="Wallet recharge requests retrieved successfully",
                count=count,
                data=serializer.data,
                status_code=status.HTTP_200_OK,
            )

        except Exception as e:
            print(traceback.format_exc())
            return self.get_error_response(
                message=str(e),
                status="error",
                errors=[],
                error_code="INTERNAL_SERVER_ERROR",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def wallet_recharge_fee_preview(self, request):
        """Estimate Razorpay processing fee; bank-transfer path has zero fee."""
        from decimal import Decimal

        from apps.payment_gateways.utils import razorpay_fees as rzfee

        ser = FeePreviewQuerySerializer(data=request.query_params)
        if not ser.is_valid():
            return self.get_error_response(
                message="Invalid query parameters",
                status="error",
                errors=ser.errors,
                error_code="VALIDATION_ERROR",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        amount_rupees = Decimal(str(ser.validated_data["amount"]))
        raw_bucket = (ser.validated_data.get("bucket") or "worst_case").strip().lower()
        disclaimer = (
            "Estimates only; actual Razorpay fee and GST depend on the payment method "
            "chosen at checkout. Wallet is credited the paid amount; platform costs are "
            "tracked separately. Bank transfer with receipt and admin approval has no "
            "processing fee."
        )
        bucket_map = {
            "domestic_standard": rzfee.BUCKET_DOMESTIC_STANDARD,
            "premium": rzfee.BUCKET_PREMIUM,
            "international_bank": rzfee.BUCKET_INTL_BANK,
            "rupay_credit_upi": rzfee.BUCKET_RUPAY_UPI,
        }
        if raw_bucket in ("worst_case", "conservative", ""):
            default_est = rzfee.worst_case_estimate(amount_rupees)
        elif raw_bucket in bucket_map:
            default_est = rzfee.build_fee_estimate_response(
                amount_rupees, bucket_map[raw_bucket]
            )
        else:
            default_est = rzfee.worst_case_estimate(amount_rupees)

        idbook_manual = {
            "channel": "bank_transfer_receipt",
            "processing_fee_rupees": "0",
            "gst_on_fee_rupees": "0",
            "total_fee_rupees": "0",
            "wallet_credit_rupees": str(amount_rupees),
        }

        return self.get_response(
            status="success",
            count=1,
            data={
                "amount_rupees": str(amount_rupees),
                "razorpay_estimate": dict(default_est),
                "idbook_manual": idbook_manual,
                "disclaimer": disclaimer,
            },
            message="Wallet recharge fee preview",
            status_code=status.HTTP_200_OK,
        )

    def admin_wallet_list(self, request):
        if not finance_ops_admin_allowed(request):
            return self.get_error_response(
                message="You don't have permission to list wallets",
                status="error",
                errors=[],
                error_code="PERMISSION_DENIED",
                status_code=status.HTTP_403_FORBIDDEN,
            )
        ser = AdminWalletListQuerySerializer(data=request.query_params)
        if not ser.is_valid():
            return self.get_error_response(
                message="Invalid query parameters",
                status="error",
                errors=ser.errors,
                error_code="VALIDATION_ERROR",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        v = ser.validated_data
        qs = Wallet.objects.filter(active=True).select_related("user", "company", "agent")

        wo = (v.get("wallet_owner") or "").strip().lower()
        if wo == "b2c":
            qs = qs.filter(
                user_id__isnull=False,
                company_id__isnull=True,
                agent_id__isnull=True,
            )
        elif wo == "company":
            qs = qs.filter(company_id__isnull=False)
        elif wo == "agent":
            qs = qs.filter(agent_id__isnull=False)

        uid = v.get("user_id")
        if uid is not None:
            qs = qs.filter(user_id=uid)
        cid = v.get("company_id")
        if cid is not None:
            qs = qs.filter(company_id=cid)
        aid = v.get("agent_id")
        if aid is not None:
            qs = qs.filter(agent_id=aid)

        search = (v.get("search") or "").strip()
        if search:
            qs = qs.filter(
                Q(user__email__icontains=search)
                | Q(user__first_name__icontains=search)
                | Q(user__last_name__icontains=search)
                | Q(user__mobile_number__icontains=search)
                | Q(company__company_name__icontains=search)
                | Q(agent__agent_name__icontains=search)
            )
        ordering = (v.get("ordering") or "-updated").strip()
        allowed = {
            "updated",
            "-updated",
            "created",
            "-created",
            "balance",
            "-balance",
            "id",
            "-id",
        }
        if ordering not in allowed:
            ordering = "-updated"
        qs = qs.order_by(ordering)
        count, page = paginate_queryset(request, qs)
        out = WalletAdminListSerializer(page, many=True)
        return self.get_response(
            status="success",
            message="Wallets retrieved successfully",
            count=count,
            data=out.data,
            status_code=status.HTTP_200_OK,
        )

    def admin_wallet_dashboard_summary(self, request):
        if not finance_ops_admin_allowed(request):
            return self.get_error_response(
                message="You don't have permission to view wallet dashboard summary",
                status="error",
                errors=[],
                error_code="PERMISSION_DENIED",
                status_code=status.HTTP_403_FORBIDDEN,
            )

        wallets_qs = Wallet.objects.filter(active=True)
        tx_qs = WalletTransaction.objects.filter(
            status__iexact="Completed",
            is_transaction_success=True,
        )

        wallet_agg = wallets_qs.aggregate(
            total_wallet_balance=Coalesce(
                Sum("balance"), Value(0), output_field=DecimalField(max_digits=24, decimal_places=6)
            ),
            wallets_count=Count("id"),
        )
        tx_agg = tx_qs.aggregate(
            total_credit=Coalesce(
                Sum("amount", filter=Q(transaction_type="Credit")),
                Value(0),
                output_field=DecimalField(max_digits=24, decimal_places=6),
            ),
            total_debit=Coalesce(
                Sum("amount", filter=Q(transaction_type="Debit")),
                Value(0),
                output_field=DecimalField(max_digits=24, decimal_places=6),
            ),
            successful_transactions=Count("id"),
        )

        total_credit = tx_agg["total_credit"] or 0
        total_debit = tx_agg["total_debit"] or 0
        data = {
            "wallets_count": wallet_agg["wallets_count"] or 0,
            "total_wallet_balance": str(wallet_agg["total_wallet_balance"] or 0),
            "total_money_in": str(total_credit),
            "total_money_out": str(total_debit),
            "net_flow": str(total_credit - total_debit),
            "successful_transactions": tx_agg["successful_transactions"] or 0,
        }
        return self.get_response(
            status="success",
            count=1,
            data=data,
            message="Wallet dashboard summary",
            status_code=status.HTTP_200_OK,
        )

    def admin_wallet_funds_summary(self, request):
        if not finance_ops_admin_allowed(request):
            return self.get_error_response(
                message="You don't have permission to view wallet funds summary",
                status="error",
                errors=[],
                error_code="PERMISSION_DENIED",
                status_code=status.HTTP_403_FORBIDDEN,
            )

        ser_q = AdminWalletTransactionListQuerySerializer(data=request.query_params)
        if not ser_q.is_valid():
            return self.get_error_response(
                message="Invalid query params",
                status="error",
                errors=ser_q.errors,
                error_code="VALIDATION_ERROR",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        validated = ser_q.validated_data
        tx_qs = WalletTransaction.objects.filter(
            status__iexact="Completed",
            is_transaction_success=True,
        )
        tx_qs = WalletTransactionViewSet()._apply_admin_transaction_filters(
            tx_qs, validated
        )

        promo_credit_for = [
            "signup_reward",
            "booking_cashback",
            "referral_booking",
            "pro_member_bonus",
        ]

        agg = tx_qs.aggregate(
            total_credit=Coalesce(
                Sum("amount", filter=Q(transaction_type="Credit")),
                Value(0),
                output_field=DecimalField(max_digits=24, decimal_places=6),
            ),
            total_debit=Coalesce(
                Sum("amount", filter=Q(transaction_type="Debit")),
                Value(0),
                output_field=DecimalField(max_digits=24, decimal_places=6),
            ),
            real_money_in=Coalesce(
                Sum(
                    "amount",
                    filter=Q(transaction_type="Credit", transaction_for__iexact="wallet_recharge"),
                ),
                Value(0),
                output_field=DecimalField(max_digits=24, decimal_places=6),
            ),
            promo_credit_credited=Coalesce(
                Sum(
                    "amount",
                    filter=Q(transaction_type="Credit", transaction_for__in=promo_credit_for),
                ),
                Value(0),
                output_field=DecimalField(max_digits=24, decimal_places=6),
            ),
            promo_credit_used=Coalesce(
                Sum(
                    "used_amount",
                    filter=Q(transaction_type="Credit", transaction_for__in=promo_credit_for),
                ),
                Value(0),
                output_field=DecimalField(max_digits=24, decimal_places=6),
            ),
            promo_credit_expired=Coalesce(
                Sum(
                    "amount",
                    filter=Q(
                        transaction_type="Debit",
                        transaction_for__iexact="pro_member_bonus_expiry",
                    ),
                ),
                Value(0),
                output_field=DecimalField(max_digits=24, decimal_places=6),
            ),
            successful_transactions=Count("id"),
        )

        total_credit = agg["total_credit"] or 0
        total_debit = agg["total_debit"] or 0
        real_money_in = agg["real_money_in"] or 0
        promo_credit_credited = agg["promo_credit_credited"] or 0
        promo_credit_used = agg["promo_credit_used"] or 0
        promo_credit_expired = agg["promo_credit_expired"] or 0

        data = {
            "total_credit": str(total_credit),
            "total_debit": str(total_debit),
            "net_flow": str(total_credit - total_debit),
            "real_money_in": str(real_money_in),
            "promo_credit_credited": str(promo_credit_credited),
            "promo_credit_used": str(promo_credit_used),
            "promo_credit_expired": str(promo_credit_expired),
            "unclassified_credit": str(total_credit - real_money_in - promo_credit_credited),
            "unclassified_debit": str(total_debit - promo_credit_expired),
            "successful_transactions": agg["successful_transactions"] or 0,
            "start_date": str(validated.get("start_date") or ""),
            "end_date": str(validated.get("end_date") or ""),
        }
        return self.get_response(
            status="success",
            count=1,
            data=data,
            message="Wallet funds summary",
            status_code=status.HTTP_200_OK,
        )

    def admin_wallet_summary(self, request, pk=None):
        if not finance_ops_admin_allowed(request):
            return self.get_error_response(
                message="You don't have permission to view this wallet",
                status="error",
                errors=[],
                error_code="PERMISSION_DENIED",
                status_code=status.HTTP_403_FORBIDDEN,
            )
        wallet = (
            Wallet.objects.filter(pk=pk)
            .select_related("user", "company", "agent")
            .first()
        )
        if not wallet:
            return self.get_error_response(
                message="Wallet not found",
                status="error",
                errors=[],
                error_code="NOT_FOUND",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        out = WalletAdminListSerializer(wallet)
        return self.get_response(
            status="success",
            count=1,
            data=out.data,
            message="Wallet summary",
            status_code=status.HTTP_200_OK,
        )

    @action(
        detail=True,
        methods=["patch", "delete"],
        url_path="admin",
        url_name="wallet-admin-manage",
    )
    def admin_wallet_manage(self, request, pk=None):
        from django.db import transaction as db_transaction

        if not finance_ops_admin_allowed(request):
            return self.get_error_response(
                message="You don't have permission to manage wallets",
                status="error",
                errors=[],
                error_code="PERMISSION_DENIED",
                status_code=status.HTTP_403_FORBIDDEN,
            )

        with db_transaction.atomic():
            wallet = Wallet.objects.select_for_update().filter(pk=pk).first()
            if not wallet:
                return self.get_error_response(
                    message="Wallet not found",
                    status="error",
                    errors=[],
                    error_code="NOT_FOUND",
                    status_code=status.HTTP_404_NOT_FOUND,
                )

            if request.method == "DELETE":
                has_ledger_rows = WalletTransaction.objects.filter(
                    wallet_transactions_scope_q(wallet)
                ).exists()
                if has_ledger_rows:
                    if not wallet.active:
                        return self.get_response(
                            status="success",
                            count=1,
                            data={"id": wallet.id, "deleted": False, "active": False},
                            message="Wallet already inactive (ledger exists, hard delete blocked)",
                            status_code=status.HTTP_200_OK,
                        )
                    wallet.active = False
                    wallet.save(update_fields=["active", "updated"])
                    return self.get_response(
                        status="success",
                        count=1,
                        data={"id": wallet.id, "deleted": False, "active": wallet.active},
                        message="Wallet has ledger rows; deactivated instead of hard delete",
                        status_code=status.HTTP_200_OK,
                    )
                wallet_id = wallet.id
                wallet.delete()
                return self.get_response(
                    status="success",
                    count=1,
                    data={"id": wallet_id, "deleted": True},
                    message="Wallet deleted successfully",
                    status_code=status.HTTP_200_OK,
                )

            def _to_nullable_int(value):
                if value in (None, "", "null"):
                    return None
                try:
                    iv = int(value)
                except (TypeError, ValueError):
                    raise ValueError("Owner ids must be integers or null")
                if iv < 1:
                    raise ValueError("Owner ids must be >= 1")
                return iv

            owner_keys = {"user_id", "company_id", "agent_id", "user", "company", "agent"}
            owner_payload_present = any(k in request.data for k in owner_keys)
            next_user_id = wallet.user_id
            next_company_id = wallet.company_id
            next_agent_id = wallet.agent_id

            if owner_payload_present:
                try:
                    if "user_id" in request.data or "user" in request.data:
                        next_user_id = _to_nullable_int(
                            request.data.get("user_id", request.data.get("user"))
                        )
                    if "company_id" in request.data or "company" in request.data:
                        next_company_id = _to_nullable_int(
                            request.data.get("company_id", request.data.get("company"))
                        )
                    if "agent_id" in request.data or "agent" in request.data:
                        next_agent_id = _to_nullable_int(
                            request.data.get("agent_id", request.data.get("agent"))
                        )
                except ValueError as exc:
                    return self.get_error_response(
                        message="Validation failed",
                        status="error",
                        errors={"owner": [str(exc)]},
                        error_code="VALIDATION_ERROR",
                        status_code=status.HTTP_400_BAD_REQUEST,
                    )

            try:
                validate_exclusive_wallet_owner(
                    user_id=next_user_id,
                    company_id=next_company_id,
                    agent_id=next_agent_id,
                )
            except (DjangoValidationError, ValueError) as exc:
                return self.get_error_response(
                    message="Validation failed",
                    status="error",
                    errors={"owner": [str(exc)]},
                    error_code="VALIDATION_ERROR",
                    status_code=status.HTTP_400_BAD_REQUEST,
                )

            owner_changed = (
                (next_user_id != wallet.user_id)
                or (next_company_id != wallet.company_id)
                or (next_agent_id != wallet.agent_id)
            )
            if owner_changed:
                has_ledger_rows = WalletTransaction.objects.filter(
                    wallet_transactions_scope_q(wallet)
                ).exists()
                if has_ledger_rows:
                    return self.get_error_response(
                        message="Validation failed",
                        status="error",
                        errors={
                            "owner": [
                                "Cannot change wallet owner while ledger rows exist for current scope."
                            ]
                        },
                        error_code="VALIDATION_ERROR",
                        status_code=status.HTTP_400_BAD_REQUEST,
                    )

            active = wallet.active
            if "active" in request.data:
                raw_active = request.data.get("active")
                if isinstance(raw_active, bool):
                    active = raw_active
                else:
                    active = str(raw_active).strip().lower() in {"1", "true", "yes", "on"}

            wallet.user_id = next_user_id
            wallet.company_id = next_company_id
            wallet.agent_id = next_agent_id
            wallet.active = active
            try:
                wallet.full_clean()
                wallet.save()
            except DjangoValidationError as exc:
                if hasattr(exc, "message_dict"):
                    errors = exc.message_dict
                else:
                    errors = {"non_field_errors": list(exc.messages)}
                return self.get_error_response(
                    message="Validation failed",
                    status="error",
                    errors=errors,
                    error_code="VALIDATION_ERROR",
                    status_code=status.HTTP_400_BAD_REQUEST,
                )

        out = WalletAdminListSerializer(wallet)
        return self.get_response(
            status="success",
            count=1,
            data=out.data,
            message="Wallet updated successfully",
            status_code=status.HTTP_200_OK,
        )

    @action(
        detail=True,
        methods=["GET", "POST"],
        url_path="admin-transactions",
        url_name="wallet-admin-transactions",
    )
    def admin_wallet_transactions(self, request, pk=None):
        """Finance admin: list or create transactions scoped to this wallet."""
        if not finance_ops_admin_allowed(request):
            return self.get_error_response(
                message="You don't have permission to manage wallet transactions",
                status="error",
                errors=[],
                error_code="PERMISSION_DENIED",
                status_code=status.HTTP_403_FORBIDDEN,
            )

        wallet = (
            Wallet.objects.filter(pk=pk)
            .select_related("user", "company", "agent")
            .first()
        )
        if not wallet:
            return self.get_error_response(
                message="Wallet not found",
                status="error",
                errors=[],
                error_code="NOT_FOUND",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        if request.method == "GET":
            ser_q = AdminWalletScopedTransactionQuerySerializer(
                data=request.query_params
            )
            if not ser_q.is_valid():
                return self.get_error_response(
                    message="Invalid query parameters",
                    status="error",
                    errors=ser_q.errors,
                    error_code="VALIDATION_ERROR",
                    status_code=status.HTTP_400_BAD_REQUEST,
                )
            v = ser_q.validated_data
            qs = WalletTransaction.objects.filter(
                wallet_transactions_scope_q(wallet)
            ).select_related("user", "company", "agent")
            search = (v.get("search") or "").strip()
            if search:
                qs = qs.filter(
                    Q(transaction_id__icontains=search)
                    | Q(transaction_details__icontains=search)
                    | Q(code__icontains=search)
                )
            ordering = (v.get("ordering") or "-created").strip()
            allowed_ordering = {
                "created",
                "-created",
                "updated",
                "-updated",
                "amount",
                "-amount",
                "status",
                "-status",
                "id",
                "-id",
                "transaction_type",
                "-transaction_type",
            }
            if ordering not in allowed_ordering:
                ordering = "-created"
            qs = self._with_admin_running_balances_annotation(qs).order_by(ordering)
            offset = v["offset"]
            limit = v["limit"]
            count = qs.count()
            page = qs[offset : offset + limit]
            out = WalletTransactionAdminSerializer(page, many=True)
            return self.get_response(
                status="success",
                message="Wallet transactions",
                count=count,
                data=out.data,
                status_code=status.HTTP_200_OK,
            )

        from django.db import transaction as db_transaction

        with db_transaction.atomic():
            locked_wallet = (
                Wallet.objects.select_for_update().filter(pk=wallet.pk).first()
            )
            if not locked_wallet:
                return self.get_error_response(
                    message="Wallet not found",
                    status="error",
                    errors=[],
                    error_code="NOT_FOUND",
                    status_code=status.HTTP_404_NOT_FOUND,
                )

            ser = AdminWalletTransactionWriteSerializer(
                data=request.data, context={"wallet": locked_wallet}
            )
            if not ser.is_valid():
                return self.get_error_response(
                    message="Validation failed",
                    status="error",
                    errors=ser.errors,
                    error_code="VALIDATION_ERROR",
                    status_code=status.HTTP_400_BAD_REQUEST,
                )

            validated = dict(ser.validated_data)
            if not str(validated.get("code") or "").strip():
                validated["code"] = f"WLTX-{get_unique_id_from_time(locked_wallet.pk)}"

            try:
                txn = WalletTransaction.objects.create(
                    **wallet_owner_kwargs_from_wallet(locked_wallet),
                    **validated,
                )
            except DjangoValidationError as exc:
                return self.get_error_response(
                    message="Validation failed",
                    status="error",
                    errors=getattr(
                        exc, "message_dict", {"non_field_errors": exc.messages}
                    ),
                    error_code="VALIDATION_ERROR",
                    status_code=status.HTTP_400_BAD_REQUEST,
                )

            delta = _wallet_txn_effect(
                amount=txn.amount,
                transaction_type=txn.transaction_type,
                status_value=txn.status,
                success_value=txn.is_transaction_success,
            )
            locked_wallet.balance = (locked_wallet.balance or Decimal("0")) + delta
            locked_wallet.save(update_fields=["balance", "updated"])

        out = WalletTransactionAdminSerializer(txn)
        return self.get_response(
            status="success",
            message="Wallet transaction created",
            count=1,
            data=out.data,
            status_code=status.HTTP_201_CREATED,
        )

    @action(
        detail=True,
        methods=["POST"],
        url_path="reconcile-balance",
        url_name="wallet-reconcile-balance",
    )
    def admin_reconcile_wallet_balance(self, request, pk=None):
        """Set wallet.balance from sum(Credit) - sum(Debit) over Completed successful ledger rows."""
        from django.db import transaction as db_transaction

        if not finance_ops_admin_allowed(request):
            return self.get_error_response(
                message="You don't have permission to reconcile wallet balance",
                status="error",
                errors=[],
                error_code="PERMISSION_DENIED",
                status_code=status.HTTP_403_FORBIDDEN,
            )

        if not Wallet.objects.filter(pk=pk).exists():
            return self.get_error_response(
                message="Wallet not found",
                status="error",
                errors=[],
                error_code="NOT_FOUND",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        with db_transaction.atomic():
            wallet = Wallet.objects.select_for_update().get(pk=pk)
            new_bal, cnt = compute_wallet_ledger_balance(wallet)
            old_bal = wallet.balance
            wallet.balance = new_bal
            wallet.save(update_fields=["balance", "updated"])

        return self.get_response(
            status="success",
            message="Wallet balance reconciled from ledger",
            count=1,
            data={
                "previous_balance": str(old_bal),
                "new_balance": str(new_bal),
                "ledger_transactions_count": cnt,
                "ledger_rule": "status=Completed and is_transaction_success=true",
            },
            status_code=status.HTTP_200_OK,
        )


class WalletTransactionViewSet(
    viewsets.ModelViewSet, StandardResponseMixin, LoggingMixin
):
    queryset = WalletTransaction.objects.all()
    serializer_class = WalletTransactionSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "post", "put", "patch", "delete"]
    allowed_ordering_fields = {
        "created",
        "updated",
        "amount",
        "status",
        "transaction_type",
        "transaction_id",
        "payment_medium",
        "payment_type",
    }
    no_filter_values = {"", "all", "any", "*"}

    def _apply_admin_transaction_filters(self, qs, validated_data):
        st = (validated_data.get("status") or "").strip()
        if st:
            qs = qs.filter(status__iexact=st)

        tf = (validated_data.get("transaction_for") or "").strip()
        if tf:
            qs = qs.filter(transaction_for__iexact=tf)

        tt = (validated_data.get("transaction_type") or "").strip()
        if tt:
            qs = qs.filter(transaction_type__iexact=tt)

        pt = (validated_data.get("payment_type") or "").strip()
        if pt:
            qs = qs.filter(payment_type__iexact=pt)

        pm = (validated_data.get("payment_medium") or "").strip()
        if pm:
            qs = qs.filter(payment_medium__iexact=pm)

        wo = (validated_data.get("wallet_owner") or "").strip().lower()
        if wo == "b2c":
            qs = qs.filter(
                user_id__isnull=False,
                company_id__isnull=True,
                agent_id__isnull=True,
            )
        elif wo == "company":
            qs = qs.filter(company_id__isnull=False)
        elif wo == "agent":
            qs = qs.filter(agent_id__isnull=False)

        uid = validated_data.get("user_id")
        if uid is not None:
            qs = qs.filter(user_id=uid)
        cid = validated_data.get("company_id")
        if cid is not None:
            qs = qs.filter(company_id=cid)
        aid = validated_data.get("agent_id")
        if aid is not None:
            qs = qs.filter(agent_id=aid)

        start_date = validated_data.get("start_date")
        end_date = validated_data.get("end_date")
        if start_date:
            qs = qs.filter(created__date__gte=start_date)
        if end_date:
            qs = qs.filter(created__date__lte=end_date)

        search = (validated_data.get("search") or "").strip()
        if search:
            qs = qs.filter(
                Q(transaction_id__icontains=search)
                | Q(transaction_details__icontains=search)
                | Q(code__icontains=search)
                | Q(user__email__icontains=search)
                | Q(user__first_name__icontains=search)
                | Q(user__last_name__icontains=search)
                | Q(user__mobile_number__icontains=search)
                | Q(company__company_name__icontains=search)
                | Q(agent__agent_name__icontains=search)
            )
        return qs

    def destroy(self, request, *args, **kwargs):
        """Block generic DELETE; finance admins use .../admin/?wallet_id= instead."""
        return self.get_error_response(
            message=(
                "Deleting wallet transactions via this URL is not supported. "
                "Use DELETE /wallet-transaction/<id>/admin/?wallet_id=<wallet_pk>."
            ),
            status="error",
            errors=[],
            error_code="METHOD_NOT_ALLOWED",
            status_code=status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    def _set_scope_filter(self, filter_dict, scope, value):
        """
        Apply only one scope filter at a time.
        Allowed scopes: user_id, company_id, agent_id.
        """
        filter_dict.pop("user_id", None)
        filter_dict.pop("company_id", None)
        filter_dict.pop("agent_id", None)
        filter_dict.pop("company_id__isnull", None)
        filter_dict.pop("agent_id__isnull", None)

        if scope == "user_id":
            filter_dict["user_id"] = value
            # Keep user scope broad: include user-initiated personal/company/agent transactions.
        elif scope == "company_id":
            filter_dict["company_id"] = value
        elif scope == "agent_id":
            filter_dict["agent_id"] = value

    def wtransaction_filter_ops(self):
        filter_dict = {}
        user = self.request.user
        params = self._validated_query_params
        self._scope_denied_error = None
        self._applied_filter_dict = {}
        token_user_id = None
        auth_header = self.request.META.get("HTTP_AUTHORIZATION", "")
        if auth_header.startswith("Bearer "):
            try:
                from rest_framework_simplejwt.tokens import UntypedToken

                token_payload = UntypedToken(auth_header.split(" ", 1)[1])
                token_user_id = token_payload.get("user_id")
            except Exception:
                token_user_id = None
        effective_user_id = token_user_id or user.id

        # Match wallet balance scope resolution to avoid divergence.
        # Prefer token active_group, then fallback to user's default_group.
        from apps.authentication.constants import (
            UserGroups,
            CORPORATE_GROUPS,
            B2C_GROUPS,
        )

        active_group = None
        token = getattr(self.request, "auth", None)
        if token is not None:
            try:
                active_group = token.get("active_group")
            except Exception:
                active_group = None
        if not active_group:
            active_group = getattr(user, "default_group", None)
        # filter by transaction type
        transaction_type = str(params.get("transaction_type", "")).strip()
        if transaction_type and transaction_type.lower() not in self.no_filter_values:  
            filter_dict["transaction_type"] = transaction_type

        # Filter by transaction success only when query param is explicitly provided.
        # This avoids accidental pending-only filtering from blank/implicit values.
        raw_success_param = self.request.query_params.get("is_transaction_success", None)
        if raw_success_param is not None and str(raw_success_param).strip() != "":
            is_transaction_success = params.get("is_transaction_success", None)
            if is_transaction_success is not None:
                filter_dict["is_transaction_success"] = is_transaction_success

        # status filter
        status_param = str(params.get("status", "")).strip()
        if status_param and status_param.lower() not in self.no_filter_values:
            status_normalized = status_param.lower()
            success_aliases = {"success", "succes", "successful", "succeeded"}
            failed_aliases = {"failed", "failure", "error", "unsuccessful"}

            if status_normalized in success_aliases:
                # Wallet transactions use "Completed" for successful rows.
                filter_dict["status__in"] = ["Completed", "Success", "SUCCESS"]
            elif status_normalized in failed_aliases:
                filter_dict["status__in"] = ["Failed", "FAILED", "Error"]
            else:
                filter_dict["status__iexact"] = status_param

        transaction_for = str(params.get("transaction_for", "")).strip()
        if transaction_for and transaction_for.lower() not in self.no_filter_values:
            filter_dict["transaction_for__iexact"] = transaction_for

        payment_type = str(params.get("payment_type", "")).strip()
        if payment_type and payment_type.lower() not in self.no_filter_values:
            filter_dict["payment_type__iexact"] = payment_type

        payment_medium = str(params.get("payment_medium", "")).strip()
        if payment_medium and payment_medium.lower() not in self.no_filter_values:
            filter_dict["payment_medium__iexact"] = payment_medium

        start_date = params.get("start_date")
        if start_date:
            filter_dict["created__date__gte"] = start_date

        end_date = params.get("end_date")
        if end_date:
            filter_dict["created__date__lte"] = end_date

        # fetch validated filter parameters
        param_dict = params
        requested_agent_id = param_dict.get("agent_id")
        requested_company_id = param_dict.get("company_id")
        requested_user_id = param_dict.get("user_id")

        # Explicit company scope takes priority (when provided).
        if requested_company_id is not None:
            has_permission = False
            if user.is_superuser:
                has_permission = True
            elif active_group in CORPORATE_GROUPS:
                has_permission = user.company_id == requested_company_id
            elif active_group in (
                UserGroups.BUSINESS_GRP,
                UserGroups.BUS_ADMIN,
                UserGroups.HTLR_ADMIN,
                UserGroups.FRANCH_ADMIN,
            ):
                has_permission = True

            if not has_permission:
                self._scope_denied_error = {
                    "message": "You don't have permission to access this company transactions",
                    "error_code": "PERMISSION_DENIED",
                }
                return

            self._set_scope_filter(filter_dict, "company_id", requested_company_id)
            self._applied_filter_dict = dict(filter_dict)
            self.queryset = self.queryset.filter(**filter_dict)
            search_param = params.get("search", "").strip()
            if search_param:
                self.queryset = self.queryset.filter(
                    Q(transaction_id__icontains=search_param)
                    | Q(transaction_details__icontains=search_param)
                    | Q(code__icontains=search_param)
                    | Q(payment_type__icontains=search_param)
                    | Q(payment_medium__icontains=search_param)
                )
            return

        # Deterministic default scope: when client does not explicitly request
        # company/agent/user scope, return current user's transactions.
        if (
            requested_agent_id is None
            and requested_company_id is None
            and requested_user_id is None
        ):
            self._set_scope_filter(filter_dict, "user_id", effective_user_id)
            self._applied_filter_dict = dict(filter_dict)
            self.queryset = self.queryset.filter(**filter_dict)
            search_param = params.get("search", "").strip()
            if search_param:
                self.queryset = self.queryset.filter(
                    Q(transaction_id__icontains=search_param)
                    | Q(transaction_details__icontains=search_param)
                    | Q(code__icontains=search_param)
                    | Q(payment_type__icontains=search_param)
                    | Q(payment_medium__icontains=search_param)
                )
            return

        # Explicit agent scope takes priority over group branching.
        # This keeps behavior predictable for /wallet-transaction/user/?agent_id=<id>
        if requested_agent_id is not None:
            from apps.booking.utils.agent_linking_utils import get_agent_for_user

            user_agent = get_agent_for_user(user)
            has_permission = user.is_superuser or (
                user_agent and user_agent.id == requested_agent_id
            )
            if not has_permission:
                self._scope_denied_error = {
                    "message": "You don't have permission to access this agent transactions",
                    "error_code": "PERMISSION_DENIED",
                }
                return

            # Permission granted: apply strict agent-only filtering.
            self._set_scope_filter(filter_dict, "agent_id", requested_agent_id)
            self._applied_filter_dict = dict(filter_dict)
            self.queryset = self.queryset.filter(**filter_dict)
            search_param = params.get("search", "").strip()
            if search_param:
                self.queryset = self.queryset.filter(
                    Q(transaction_id__icontains=search_param)
                    | Q(transaction_details__icontains=search_param)
                    | Q(code__icontains=search_param)
                    | Q(payment_type__icontains=search_param)
                    | Q(payment_medium__icontains=search_param)
                )
            return

        # Apply permission-based filtering based on user's active group
        # B2C users (B2C-GRP, B2C-GUEST): can only see their own user wallet transactions
        if active_group in B2C_GROUPS:
            self._set_scope_filter(filter_dict, "user_id", effective_user_id)

        # Agent users (AGENT-ADMIN): can see their own agent wallet transactions
        elif active_group in (UserGroups.AGENT_ADMIN, UserGroups.AGENT_GRP):
            from apps.booking.utils.agent_linking_utils import get_agent_for_user
            agent = get_agent_for_user(user)
            if agent:
                # If agent_id is provided in query params, verify it matches the user's agent
                agent_id_param = param_dict.get("agent_id", "")
                if agent_id_param:
                    if agent_id_param == agent.id:
                        self._set_scope_filter(filter_dict, "agent_id", agent.id)
                    else:
                        self._scope_denied_error = {
                            "message": "You don't have permission to access this agent transactions",
                            "error_code": "PERMISSION_DENIED",
                        }
                        return
                else:
                    # Auto-filter to agent's transactions
                    self._set_scope_filter(filter_dict, "agent_id", agent.id)
            else:
                # Fallback to user's own transactions if agent mapping is missing
                self._set_scope_filter(filter_dict, "user_id", user.id)

        # Corporate users (CORP-ADMIN, CORP-EMP, CORPORATE-GRP): can see company wallet transactions
        elif active_group in CORPORATE_GROUPS:
            # All corporate users can see company wallet transactions for their company
            if user.company_id:
                self._set_scope_filter(filter_dict, "company_id", user.company_id)
            else:
                # Fallback to user's own transactions when company mapping is missing
                self._set_scope_filter(filter_dict, "user_id", user.id)

        # Business users (BUSINESS-GRP, BUS-ADMIN): can see all transactions
        elif active_group in (UserGroups.BUSINESS_GRP, UserGroups.BUS_ADMIN):
            # Apply only one requested scope filter at a time.
            if "company_id" in param_dict:
                self._set_scope_filter(filter_dict, "company_id", param_dict["company_id"])
            elif "agent_id" in param_dict:
                self._set_scope_filter(filter_dict, "agent_id", param_dict["agent_id"])
            elif "user_id" in param_dict:
                self._set_scope_filter(filter_dict, "user_id", param_dict["user_id"])

        # Hotelier/Franchise admins: can see all transactions
        elif active_group in (UserGroups.HTLR_ADMIN, UserGroups.FRANCH_ADMIN):
            # Apply only one requested scope filter at a time.
            if "company_id" in param_dict:
                self._set_scope_filter(filter_dict, "company_id", param_dict["company_id"])
            elif "agent_id" in param_dict:
                self._set_scope_filter(filter_dict, "agent_id", param_dict["agent_id"])
            elif "user_id" in param_dict:
                self._set_scope_filter(filter_dict, "user_id", param_dict["user_id"])

        # For other groups or if no group matches, default to user's own transactions
        else:
            # If company_id is explicitly provided in query params, use it
            company_id = param_dict.get("company_id", "")
            agent_id = param_dict.get("agent_id", "")
            if company_id:
                self._set_scope_filter(filter_dict, "company_id", company_id)
            elif agent_id:
                # Check if user has permission to view this agent's transactions
                from apps.booking.utils.agent_linking_utils import get_agent_for_user
                user_agent = get_agent_for_user(user)
                if user_agent and user_agent.id == agent_id:
                    self._set_scope_filter(filter_dict, "agent_id", agent_id)
                elif user.is_superuser:
                    self._set_scope_filter(filter_dict, "agent_id", agent_id)
                else:
                    self._scope_denied_error = {
                        "message": "You don't have permission to access this agent transactions",
                        "error_code": "PERMISSION_DENIED",
                    }
                    return
            else:
                # Default to user's own transactions
                self._set_scope_filter(filter_dict, "user_id", user.id)

        self._applied_filter_dict = dict(filter_dict)
        self.queryset = self.queryset.filter(**filter_dict)

        search_param = params.get("search", "").strip()
        if search_param:
            self.queryset = self.queryset.filter(
                Q(transaction_id__icontains=search_param)
                | Q(transaction_details__icontains=search_param)
                | Q(code__icontains=search_param)
                | Q(payment_type__icontains=search_param)
                | Q(payment_medium__icontains=search_param)
            )

    def wtransaction_order_ops(self):
        ordering_params = self._validated_query_params.get("ordering", "")
        if not ordering_params:
            self.queryset = self.queryset.order_by("-created")
            return

        ordering_list = []
        for ordering in ordering_params.split(","):
            ordering = ordering.strip()
            if not ordering:
                continue
            ordering_key = ordering.lstrip("-")
            if ordering_key in self.allowed_ordering_fields:
                ordering_list.append(ordering)
        if ordering_list:
            self.queryset = self.queryset.order_by(*ordering_list)
        else:
            self.queryset = self.queryset.order_by("-created")

    def _running_balance_scope_queryset(self, request):
        params = self._validated_query_params
        requested_agent_id = params.get("agent_id")
        requested_company_id = params.get("company_id")
        requested_user_id = params.get("user_id")

        if requested_company_id is not None:
            return WalletTransaction.objects.filter(company_id=requested_company_id)
        if requested_agent_id is not None:
            return WalletTransaction.objects.filter(agent_id=requested_agent_id)
        if requested_user_id is not None:
            return WalletTransaction.objects.filter(user_id=requested_user_id)

        token_user_id = None
        auth_header = request.META.get("HTTP_AUTHORIZATION", "")
        if auth_header.startswith("Bearer "):
            try:
                from rest_framework_simplejwt.tokens import UntypedToken

                token_payload = UntypedToken(auth_header.split(" ", 1)[1])
                token_user_id = token_payload.get("user_id")
            except Exception:
                token_user_id = None

        effective_user_id = token_user_id or request.user.id
        return WalletTransaction.objects.filter(user_id=effective_user_id)

    def _attach_running_balance(self, rows, request):
        if not rows:
            return rows

        target_ids = {row.id for row in rows}
        running_map = {}
        running_total = Decimal("0")

        scope_qs = self._running_balance_scope_queryset(request).order_by("created", "id")
        for row in scope_qs.only(
            "id", "amount", "transaction_type", "status", "is_transaction_success"
        ):
            running_total += _wallet_txn_effect(
                row.amount,
                row.transaction_type,
                row.status,
                row.is_transaction_success,
            )
            if row.id in target_ids:
                running_map[row.id] = running_total

        for row in rows:
            setattr(row, "running_balance", running_map.get(row.id, Decimal("0")))
        return rows

    def _attach_running_balance_single_scope(self, rows, scope_qs):
        if not rows:
            return rows
        target_ids = {row.id for row in rows}
        running_map = {}
        running_total = Decimal("0")
        for row in scope_qs.order_by("created", "id").only(
            "id", "amount", "transaction_type", "status", "is_transaction_success"
        ):
            running_total += _wallet_txn_effect(
                row.amount,
                row.transaction_type,
                row.status,
                row.is_transaction_success,
            )
            if row.id in target_ids:
                running_map[row.id] = running_total
        for row in rows:
            setattr(row, "running_balance", running_map.get(row.id, Decimal("0")))
        return rows

    def _attach_running_balance_multi_scope(self, rows, base_qs):
        if not rows:
            return rows
        target_ids = {row.id for row in rows}
        running_map = {}
        running_totals = {}
        for row in base_qs.order_by("created", "id").only(
            "id",
            "user_id",
            "company_id",
            "agent_id",
            "amount",
            "transaction_type",
            "status",
            "is_transaction_success",
        ):
            if row.company_id:
                scope_key = ("company", row.company_id)
            elif row.agent_id:
                scope_key = ("agent", row.agent_id)
            else:
                scope_key = ("user", row.user_id)
            running_totals[scope_key] = running_totals.get(
                scope_key, Decimal("0")
            ) + _wallet_txn_effect(
                row.amount,
                row.transaction_type,
                row.status,
                row.is_transaction_success,
            )
            if row.id in target_ids:
                running_map[row.id] = running_totals[scope_key]
        for row in rows:
            setattr(row, "running_balance", running_map.get(row.id, Decimal("0")))
        return rows

    def _with_admin_running_balances_annotation(self, qs):
        effect_expr = Case(
            When(
                status__iexact="Completed",
                is_transaction_success=True,
                transaction_type__iexact="Credit",
                then=F("amount"),
            ),
            When(
                status__iexact="Completed",
                is_transaction_success=True,
                transaction_type__iexact="Debit",
                then=-F("amount"),
            ),
            default=Value(Decimal("0")),
            output_field=DecimalField(max_digits=24, decimal_places=6),
        )

        scope_partition = Case(
            When(
                company_id__isnull=False,
                then=Concat(
                    Value("company:"),
                    Cast("company_id", output_field=CharField()),
                ),
            ),
            When(
                agent_id__isnull=False,
                then=Concat(
                    Value("agent:"),
                    Cast("agent_id", output_field=CharField()),
                ),
            ),
            default=Concat(
                Value("user:"),
                Cast("user_id", output_field=CharField()),
            ),
            output_field=CharField(),
        )

        wallet_running_expr = Coalesce(
            Window(
                expression=Sum(effect_expr),
                partition_by=[scope_partition],
                order_by=[F("created").asc(), F("id").asc()],
            ),
            Value(Decimal("0")),
        )
        platform_running_expr = Coalesce(
            Window(
                expression=Sum(effect_expr),
                order_by=[F("created").asc(), F("id").asc()],
            ),
            Value(Decimal("0")),
        )

        return qs.annotate(
            wallet_running_balance=wallet_running_expr,
            platform_running_balance=platform_running_expr,
            running_balance=wallet_running_expr,
        )

    ##    def wtransaction_pagination_ops(self):
    ##        # offset and pagination
    ##        offset = int(self.request.query_params.get('offset', 0))
    ##        limit = int(self.request.query_params.get('limit', 10))
    ##
    ##        count = self.queryset.count()
    ##        self.queryset = self.queryset[offset:offset+limit]
    ##
    ##        return count

    @swagger_auto_schema(
        query_serializer=QueryFilterWalletTransactionSerializer,
        operation_description="List Wallet Transaction Based on User",
        responses={200: WalletTransactionSerializer(many=True)},
    )
    @action(
        detail=False,
        methods=["GET"],
        url_path="user",
        url_name="retrieve-wallet-balance",
    )
    def user_based_wallet_transaction(self, request):
        query_serializer = QueryFilterWalletTransactionSerializer(data=request.query_params)
        if not query_serializer.is_valid():
            return self.get_error_response(
                message="Invalid query parameters",
                status="error",
                errors=self.custom_serializer_error(query_serializer.errors),
                error_code="VALIDATION_ERROR",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        self._validated_query_params = query_serializer.validated_data
        # Always use a fresh base queryset per request.
        self.queryset = WalletTransaction.objects.all()

        requested_agent_id = self._validated_query_params.get("agent_id")
        requested_company_id = self._validated_query_params.get("company_id")
        requested_user_id = self._validated_query_params.get("user_id")

        # Hard default: if no explicit scope params are provided, always list
        # current token user's transactions.
        if (
            requested_agent_id is None
            and requested_company_id is None
            and requested_user_id is None
        ):
            token_user_id = None
            auth_header = request.META.get("HTTP_AUTHORIZATION", "")
            if auth_header.startswith("Bearer "):
                try:
                    from rest_framework_simplejwt.tokens import UntypedToken

                    token_payload = UntypedToken(auth_header.split(" ", 1)[1])
                    token_user_id = token_payload.get("user_id")
                except Exception:
                    token_user_id = None

            effective_user_id = token_user_id or request.user.id
            self.queryset = self.queryset.filter(user_id=effective_user_id)
            self.wtransaction_order_ops()

            offset = self._validated_query_params.get("offset", 0)
            limit = self._validated_query_params.get("limit", 10)
            count = self.queryset.count()
            self.queryset = self.queryset[offset : offset + limit]
            instance = list(self.queryset)
            instance = self._attach_running_balance(instance, request)
            serializer = WalletTransactionSerializer(instance, many=True)
            return self.get_response(
                status="success",
                count=count,
                data=serializer.data,
                message="Wallet Transaction Details",
                status_code=status.HTTP_200_OK,
            )

        # filter and pagination
        self.wtransaction_filter_ops()
        if self._scope_denied_error:
            return self.get_error_response(
                message=self._scope_denied_error["message"],
                status="error",
                errors=[],
                error_code=self._scope_denied_error["error_code"],
                status_code=status.HTTP_403_FORBIDDEN,
            )
        self.wtransaction_order_ops()

        offset = self._validated_query_params.get("offset", 0)
        limit = self._validated_query_params.get("limit", 10)
        count = self.queryset.count()
        self.queryset = self.queryset[offset : offset + limit]
        instance = list(self.queryset)
        instance = self._attach_running_balance(instance, request)
        serializer = WalletTransactionSerializer(instance, many=True)
        custom_response = self.get_response(
            status="success",
            count=count,
            data=serializer.data,  # Use the data from the default response
            message="Wallet Transaction Details",
            status_code=status.HTTP_200_OK,  # 200 for successful retrieval
        )
        return custom_response

    def admin_all_transactions(self, request):
        """List all wallet transactions (finance admin only)."""
        if not finance_ops_admin_allowed(request):
            return self.get_error_response(
                message="You don't have permission to list wallet transactions",
                status="error",
                errors=[],
                error_code="PERMISSION_DENIED",
                status_code=status.HTTP_403_FORBIDDEN,
            )

        ser = AdminWalletTransactionListQuerySerializer(data=request.query_params)
        if not ser.is_valid():
            return self.get_error_response(
                message="Invalid query parameters",
                status="error",
                errors=ser.errors,
                error_code="VALIDATION_ERROR",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        v = ser.validated_data

        qs = WalletTransaction.objects.all().select_related(
            "user", "company", "agent"
        )

        qs = self._apply_admin_transaction_filters(qs, v)

        ordering = (v.get("ordering") or "-created").strip()
        allowed_ordering = {
            "created",
            "-created",
            "updated",
            "-updated",
            "amount",
            "-amount",
            "status",
            "-status",
            "id",
            "-id",
            "transaction_type",
            "-transaction_type",
        }
        if ordering not in allowed_ordering:
            ordering = "-created"
        qs = self._with_admin_running_balances_annotation(qs).order_by(ordering)

        count, page = paginate_queryset(request, qs)
        out = WalletTransactionAdminSerializer(page, many=True)
        return self.get_response(
            status="success",
            message="Wallet transactions retrieved successfully",
            count=count,
            data=out.data,
            status_code=status.HTTP_200_OK,
        )

    @action(
        detail=False,
        methods=["GET"],
        url_path="admin/stats",
        url_name="wallet-transaction-admin-stats",
    )
    def admin_transactions_stats(self, request):
        if not finance_ops_admin_allowed(request):
            return self.get_error_response(
                message="You don't have permission to view wallet transaction stats",
                status="error",
                errors=[],
                error_code="PERMISSION_DENIED",
                status_code=status.HTTP_403_FORBIDDEN,
            )

        ser = AdminWalletTransactionListQuerySerializer(data=request.query_params)
        if not ser.is_valid():
            return self.get_error_response(
                message="Invalid query parameters",
                status="error",
                errors=ser.errors,
                error_code="VALIDATION_ERROR",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        v = ser.validated_data
        qs = WalletTransaction.objects.all()
        qs = self._apply_admin_transaction_filters(qs, v)

        agg = qs.aggregate(
            transactions_count=Count("id"),
            total_credit=Coalesce(
                Sum("amount", filter=Q(transaction_type="Credit")),
                Value(0),
                output_field=DecimalField(max_digits=24, decimal_places=6),
            ),
            total_debit=Coalesce(
                Sum("amount", filter=Q(transaction_type="Debit")),
                Value(0),
                output_field=DecimalField(max_digits=24, decimal_places=6),
            ),
            completed_count=Count("id", filter=Q(status__iexact="Completed")),
            pending_count=Count("id", filter=Q(status__iexact="Pending")),
            failed_count=Count("id", filter=Q(status__iexact="Failed")),
            successful_count=Count("id", filter=Q(is_transaction_success=True)),
        )
        total_credit = agg["total_credit"] or 0
        total_debit = agg["total_debit"] or 0
        data = {
            "transactions_count": agg["transactions_count"] or 0,
            "total_credit": str(total_credit),
            "total_debit": str(total_debit),
            "net_flow": str(total_credit - total_debit),
            "completed_count": agg["completed_count"] or 0,
            "pending_count": agg["pending_count"] or 0,
            "failed_count": agg["failed_count"] or 0,
            "successful_count": agg["successful_count"] or 0,
            "start_date": str(v.get("start_date") or ""),
            "end_date": str(v.get("end_date") or ""),
        }
        return self.get_response(
            status="success",
            message="Wallet transaction stats retrieved successfully",
            count=1,
            data=data,
            status_code=status.HTTP_200_OK,
        )

    @action(
        detail=True,
        methods=["PATCH", "DELETE"],
        url_path="admin",
        url_name="wallet-transaction-admin-update",
    )
    def admin_wallet_transaction_patch(self, request, pk=None):
        """Finance admin: PATCH partial update or DELETE; wallet_id query verifies ledger scope."""
        if not finance_ops_admin_allowed(request):
            return self.get_error_response(
                message="You don't have permission to change wallet transactions",
                status="error",
                errors=[],
                error_code="PERMISSION_DENIED",
                status_code=status.HTTP_403_FORBIDDEN,
            )

        raw_wid = request.query_params.get("wallet_id")
        try:
            wallet_id = int(raw_wid) if raw_wid is not None else None
        except (TypeError, ValueError):
            wallet_id = None
        if not wallet_id:
            return self.get_error_response(
                message="wallet_id query parameter is required",
                status="error",
                errors=[],
                error_code="VALIDATION_ERROR",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        from django.db import transaction as db_transaction

        with db_transaction.atomic():
            locked_wallet = (
                Wallet.objects.select_for_update().filter(pk=wallet_id).first()
            )
            if not locked_wallet:
                return self.get_error_response(
                    message="Wallet not found",
                    status="error",
                    errors=[],
                    error_code="NOT_FOUND",
                    status_code=status.HTTP_404_NOT_FOUND,
                )

            txn = WalletTransaction.objects.select_for_update().filter(pk=pk).first()
            if not txn:
                return self.get_error_response(
                    message="Wallet transaction not found",
                    status="error",
                    errors=[],
                    error_code="NOT_FOUND",
                    status_code=status.HTTP_404_NOT_FOUND,
                )

            if not transaction_matches_wallet(txn, locked_wallet):
                return self.get_error_response(
                    message="Transaction does not belong to this wallet",
                    status="error",
                    errors=[],
                    error_code="WALLET_SCOPE_MISMATCH",
                    status_code=status.HTTP_400_BAD_REQUEST,
                )

            if request.method == "DELETE":
                old_effect = _wallet_txn_effect(
                    amount=txn.amount,
                    transaction_type=txn.transaction_type,
                    status_value=txn.status,
                    success_value=txn.is_transaction_success,
                )
                txn.delete()
                locked_wallet.balance = (locked_wallet.balance or Decimal("0")) - old_effect
                locked_wallet.save(update_fields=["balance", "updated"])
                return self.get_response(
                    status="success",
                    message="Wallet transaction deleted",
                    count=0,
                    data={},
                    status_code=status.HTTP_200_OK,
                )

            ser = AdminWalletTransactionWriteSerializer(
                txn,
                data=request.data,
                partial=True,
                context={"wallet": locked_wallet},
            )
            if not ser.is_valid():
                return self.get_error_response(
                    message="Validation failed",
                    status="error",
                    errors=ser.errors,
                    error_code="VALIDATION_ERROR",
                    status_code=status.HTTP_400_BAD_REQUEST,
                )
            old_effect = _wallet_txn_effect(
                amount=txn.amount,
                transaction_type=txn.transaction_type,
                status_value=txn.status,
                success_value=txn.is_transaction_success,
            )

            next_amount = ser.validated_data.get("amount", txn.amount)
            next_type = ser.validated_data.get("transaction_type", txn.transaction_type)
            next_status = ser.validated_data.get("status", txn.status)
            next_success = ser.validated_data.get(
                "is_transaction_success", txn.is_transaction_success
            )
            new_effect = _wallet_txn_effect(
                amount=next_amount,
                transaction_type=next_type,
                status_value=next_status,
                success_value=next_success,
            )

            updated_txn = ser.save()
            locked_wallet.balance = (locked_wallet.balance or Decimal("0")) + (
                new_effect - old_effect
            )
            locked_wallet.save(update_fields=["balance", "updated"])

            out = WalletTransactionAdminSerializer(updated_txn)
            return self.get_response(
                status="success",
                message="Wallet transaction updated",
                count=1,
                data=out.data,
                status_code=status.HTTP_200_OK,
            )

    @action(
        detail=False,
        methods=["GET"],
        url_path="agent/search",
        url_name="search-customers-for-agent",
        permission_classes=[IsAuthenticated],
    )
    def search_customers_for_agent(self, request):
        """Search existing customers to link to agent"""
        self.log_request(request)
        
        from apps.booking.utils.agent_linking_utils import get_agent_for_user
        from apps.org_resources.models import AgentDetail
        
        agent = get_agent_for_user(request.user)
        if not agent:
            return self.get_error_response(
                message="User is not associated with an agent",
                status="error",
                errors=[],
                error_code="NOT_AN_AGENT",
                status_code=status.HTTP_403_FORBIDDEN,
            )
        
        # Search parameters
        email = request.query_params.get("email")
        phone = request.query_params.get("phone")
        name = request.query_params.get("name")
        
        if not (email or phone or name):
            return self.get_error_response(
                message="At least one search parameter (email, phone, or name) is required",
                status="error",
                errors=[],
                error_code="MISSING_SEARCH_PARAM",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        
        # Build search query
        from django.db.models import Q
        search_query = Q()
        
        if email:
            search_query |= Q(user__email__icontains=email)
        if phone:
            search_query |= Q(user__mobile_number__icontains=phone)
        if name:
            search_query |= Q(user__name__icontains=name) | Q(user__first_name__icontains=name)
        
        # Get customers not yet linked to this agent
        customers = Customer.objects.filter(search_query).exclude(agents=agent)
        
        # Limit results
        limit = int(request.query_params.get("limit", 20))
        customers = customers[:limit]
        
        # Serialize results
        serializer = CustomerSerializer(customers, many=True)
        
        response = self.get_response(
            data=serializer.data,
            message="Customers found",
            count=len(serializer.data),
            status_code=status.HTTP_200_OK,
        )
        self.log_response(response)
        return response
    
    @action(
        detail=True,
        methods=["POST"],
        url_path="link-agent",
        url_name="link-agent",
        permission_classes=[IsAuthenticated],
    )
    def link_agent(self, request, pk=None):
        """Explicitly link customer to agent"""
        self.log_request(request)
        
        from apps.booking.utils.agent_linking_utils import get_agent_for_user
        from apps.org_resources.models import AgentDetail
        
        customer = self.get_object()
        agent = get_agent_for_user(request.user)
        
        if not agent:
            return self.get_error_response(
                message="User is not associated with an agent",
                status="error",
                errors=[],
                error_code="NOT_AN_AGENT",
                status_code=status.HTTP_403_FORBIDDEN,
            )
        
        # Check if agent_id is provided in request (for admin linking)
        agent_id = request.data.get("agent_id")
        if agent_id and request.user.is_superuser:
            try:
                agent = AgentDetail.objects.get(id=agent_id)
            except AgentDetail.DoesNotExist:
                return self.get_error_response(
                    message="Agent not found",
                    status="error",
                    errors=[],
                    error_code="AGENT_NOT_FOUND",
                    status_code=status.HTTP_404_NOT_FOUND,
                )
        
        # Add agent to customer's agents (ManyToMany)
        customer.agents.add(agent)
        
        # Optionally set as primary agent
        set_primary = request.data.get("set_as_primary", False)
        if set_primary or not customer.primary_agent:
            customer.primary_agent = agent
            customer.save()
        else:
            customer.save()
        
        serializer = CustomerSerializer(customer)
        
        response = self.get_response(
            data=serializer.data,
            message="Customer linked to agent successfully",
            status_code=status.HTTP_200_OK,
        )
        self.log_response(response)
        return response
    
    @action(
        detail=True,
        methods=["POST"],
        url_path="unlink-agent",
        url_name="unlink-agent",
        permission_classes=[IsAuthenticated],
    )
    def unlink_agent(self, request, pk=None):
        """Remove agent from customer"""
        self.log_request(request)
        
        from apps.booking.utils.agent_linking_utils import get_agent_for_user
        from apps.org_resources.models import AgentDetail
        
        customer = self.get_object()
        agent = get_agent_for_user(request.user)
        
        if not agent:
            return self.get_error_response(
                message="User is not associated with an agent",
                status="error",
                errors=[],
                error_code="NOT_AN_AGENT",
                status_code=status.HTTP_403_FORBIDDEN,
            )
        
        # Check if agent_id is provided in request (for admin unlinking)
        agent_id = request.data.get("agent_id")
        if agent_id and request.user.is_superuser:
            try:
                agent = AgentDetail.objects.get(id=agent_id)
            except AgentDetail.DoesNotExist:
                return self.get_error_response(
                    message="Agent not found",
                    status="error",
                    errors=[],
                    error_code="AGENT_NOT_FOUND",
                    status_code=status.HTTP_404_NOT_FOUND,
                )
        
        # Check if customer is linked to this agent
        if agent not in customer.agents.all():
            return self.get_error_response(
                message="Customer is not linked to this agent",
                status="error",
                errors=[],
                error_code="NOT_LINKED",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        
        # Remove from ManyToMany
        customer.agents.remove(agent)
        
        # If was primary_agent, set to another agent or null
        if customer.primary_agent == agent:
            other_agents = customer.agents.all()
            if other_agents.exists():
                customer.primary_agent = other_agents.first()
            else:
                customer.primary_agent = None
            customer.save()
        else:
            customer.save()
        
        serializer = CustomerSerializer(customer)
        
        response = self.get_response(
            data=serializer.data,
            message="Customer unlinked from agent successfully",
            status_code=status.HTTP_200_OK,
        )
        self.log_response(response)
        return response
    
    @action(
        detail=False,
        methods=["GET"],
        url_path="agent/(?P<agent_id>[^/.]+)/customers",
        url_name="agent-customers",
        permission_classes=[IsAuthenticated],
    )
    def agent_customers(self, request, agent_id=None):
        """List all customers linked to an agent"""
        self.log_request(request)
        
        from apps.org_resources.models import AgentDetail
        from apps.booking.utils.agent_linking_utils import get_agent_for_user
        
        # Verify user is the agent or admin
        user_agent = get_agent_for_user(request.user)
        
        try:
            agent = AgentDetail.objects.get(id=agent_id)
        except AgentDetail.DoesNotExist:
            return self.get_error_response(
                message="Agent not found",
                status="error",
                errors=[],
                error_code="AGENT_NOT_FOUND",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        
        # Check permission
        if not (request.user.is_superuser or (user_agent and user_agent.id == agent.id)):
            return self.get_error_response(
                message="You don't have permission to view this agent's customers",
                status="error",
                errors=[],
                error_code="PERMISSION_DENIED",
                status_code=status.HTTP_403_FORBIDDEN,
            )
        
        # Get customers linked to agent
        customers = Customer.objects.filter(agents=agent).select_related('user')
        
        # Pagination
        offset = int(request.query_params.get("offset", 0))
        limit = int(request.query_params.get("limit", 20))
        count = customers.count()
        customers = customers[offset:offset + limit]
        
        serializer = CustomerSerializer(customers, many=True)
        
        response = self.get_response(
            data=serializer.data,
            message="Customers retrieved successfully",
            count=count,
            status_code=status.HTTP_200_OK,
        )
        self.log_response(response)
        return response