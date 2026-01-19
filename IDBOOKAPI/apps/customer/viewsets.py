from rest_framework.views import APIView
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
    add_company_wallet_amount,
    add_user_wallet_amount,
)
from apps.log_management.utils.db_utils import create_wallet_payment_log
from django.conf import settings

from .serializers import (
    CustomerSerializer,
    WalletSerializer,
    WalletTransactionSerializer,
    WalletRechargeSerializer,
    ApproveRechargeSerializer,
    PendingRechargeSerializer,
    QueryFilterPendingRechargeSerializer,
)

# filter serializer for swagger
from .serializers import (
    QueryFilterCustomerSerializer,
    QueryFilterWalletTransactionSerializer,
)
from .models import Customer, Wallet, WalletTransaction
from django.db.models import Q
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
import traceback
from rest_framework.parsers import MultiPartParser
from apps.booking.tasks import send_booking_sms_task
from apps.authentication.models import User
from django.conf import settings

import base64, json


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

        # Get active group from token, fall back to default_group
        from apps.authentication.utils.token_utils import get_user_active_group
        from apps.authentication.constants import (
            UserGroups,
            CORPORATE_GROUPS,
            B2C_GROUPS,
        )

        active_group = get_user_active_group(user, self.request)
        default_group = active_group or user.default_group

        # fetch filter parameters
        param_dict = self.request.query_params
        for key in param_dict:
            param_value = param_dict[key]

            if key in ("group_name", "department", "privileged", "active"):
                filter_dict[key] = param_value

        # Apply permission-based filtering based on user's active group
        # Normal users (B2C-GRP, B2C-GUEST): can only see their own customer record
        if default_group in B2C_GROUPS:
            filter_dict["user"] = user.id

        # Corporate users (CORP-ADMIN, CORP-EMP, CORPORATE-GRP): can see customers from their company
        elif default_group in CORPORATE_GROUPS:
            # All corporate users can see all customers for their company
            if user.company_id:
                filter_dict["user__company_id"] = user.company_id
            else:
                # If user has no company_id, they shouldn't see any customers
                filter_dict["user__company_id"] = -1  # This will return empty queryset

        # Business users (BUSINESS-GRP, BUS-ADMIN): can see all customers (no filter)
        elif default_group in (UserGroups.BUSINESS_GRP, UserGroups.BUS_ADMIN):
            # No filtering - business users can see all customers
            # Allow query params to filter if provided
            if "company_id" in param_dict:
                filter_dict["user__company_id"] = param_dict["company_id"]
            if "user_id" in param_dict:
                filter_dict["user"] = param_dict["user_id"]

        # Hotelier/Franchise admins: no filtering (existing behavior)
        elif default_group in (UserGroups.HTLR_ADMIN, UserGroups.FRANCH_ADMIN):
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
    http_method_names = ["get", "post", "put", "patch"]

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

        company_id = self.request.query_params.get("company_id", "")
        agent_id = self.request.query_params.get("agent_id", "")
        
        # Auto-detect agent if user is an agent and no agent_id specified
        from apps.booking.utils.agent_linking_utils import get_agent_for_user
        user_agent = get_agent_for_user(request.user)
        
        if agent_id:
            # Check if user is an agent and matches the requested agent_id
            if user_agent and user_agent.id == int(agent_id):
                instance = self.queryset.filter(agent_id=agent_id).first()
            elif request.user.is_superuser:
                # Admin can access any agent wallet
                instance = self.queryset.filter(agent_id=agent_id).first()
            else:
                return self.get_error_response(
                    message="You don't have permission to access this agent wallet",
                    status="error",
                    errors=[],
                    error_code="PERMISSION_DENIED",
                    status_code=status.HTTP_403_FORBIDDEN,
                )
        elif user_agent and not company_id:
            # User is an agent and no specific agent_id/company_id - use their agent wallet
            instance = self.queryset.filter(agent=user_agent, active=True).first()
        elif company_id:
            instance = self.queryset.filter(company_id=company_id).first()
        else:
            # Default to user's personal wallet
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
                "user_id": user.id,
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
            if agent_id:
                wtransact["agent_id"] = agent_id
                payment_log["agent_id"] = agent_id

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
            
            self.log_info(f"Order notes - merchant_transaction_id: {merchant_transaction_id}, user_id: {user_id}, company_id: {company_id}")
            
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
                # Update wallet transaction
                user_id, company_id, agent_id = update_wallet_transaction_detail(merchant_transaction_id, payment_details)
                self.log_info(f"Wallet transaction update result - user_id: {user_id}, company_id: {company_id}, agent_id: {agent_id}")
                
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
                if user_id or company_id or agent_id:
                    self.log_info(f"Calling update_wallet_recharge_details with user_id={user_id}, company_id={company_id}, agent_id={agent_id}, amount={amount}")
                    wallet_update_result = update_wallet_recharge_details(user_id, company_id, amount, agent_id)
                    self.log_info(f"Wallet recharge update result: {wallet_update_result}")
                    
                    # Verify wallet balance was updated
                    from apps.customer.models import Wallet
                    if user_id and not company_id:
                        wallet = Wallet.objects.filter(user__id=user_id, company_id__isnull=True).first()
                        if wallet:
                            self.log_info(f"Wallet balance after recharge: {wallet.balance}")
                    elif company_id:
                        wallet = Wallet.objects.filter(company_id=company_id).first()
                        if wallet:
                            self.log_info(f"Company wallet balance after recharge: {wallet.balance}")
                    
                    payment_log["response"] = {"success": True, "amount": amount}
                    if user_id:
                        payment_log["user_id"] = user_id
                    if company_id:
                        payment_log["company_id"] = company_id
                    create_wallet_payment_log(payment_log)
                    
                    # Send SMS notification (same as PhonePe)
                    from apps.booking.tasks import send_booking_sms_task
                    from apps.customer.models import Wallet
                    from apps.authentication.models import User
                    
                    if user_id and not company_id:
                        wallet_balance = 0
                        wallet = Wallet.objects.filter(
                            user__id=user_id, company_id__isnull=True
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
                    self.log_error(f"WARNING: No user_id or company_id found for transaction {merchant_transaction_id}")
                    payment_log["response"] = {"error": "No user_id or company_id found"}
                    create_wallet_payment_log(payment_log)
                    return self.get_error_response(
                        message="Unable to identify user or company for wallet recharge",
                        status="error",
                        errors=[],
                        error_code="USER_NOT_FOUND",
                        status_code=status.HTTP_400_BAD_REQUEST,
                    )
                
                self.log_info(f"=== RAZORPAY WALLET VERIFY SUCCESS - Payment ID: {razorpay_payment_id}, Order ID: {razorpay_order_id} ===")
                return self.get_response(
                    status="success",
                    data={
                        "payment_id": razorpay_payment_id,
                        "order_id": razorpay_order_id,
                        "amount": amount,
                        "status": "completed",
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
                        
                        self.log_info(f"Webhook - merchant_transaction_id: {merchant_transaction_id}, user_id: {user_id}, company_id: {company_id}")
                        
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
                        user_id, company_id, agent_id = update_wallet_transaction_detail(merchant_transaction_id, payment_details)
                        self.log_info(f"Webhook - Wallet transaction update result - user_id: {user_id}, company_id: {company_id}, agent_id: {agent_id}")
                        
                        # Verify the transaction was updated
                        from apps.customer.models import WalletTransaction
                        wallet_txn_check = WalletTransaction.objects.filter(
                            transaction_id=merchant_transaction_id
                        ).first()
                        if wallet_txn_check:
                            self.log_info(f"Webhook - Transaction after update - status: {wallet_txn_check.status}, is_success: {wallet_txn_check.is_transaction_success}, code: {wallet_txn_check.code}")
                        else:
                            self.log_warning(f"Webhook - Transaction not found after update attempt: {merchant_transaction_id}")
                        
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
                                self.log_info(f"Webhook - Retrieved from WalletTransaction - user_id: {user_id}, company_id: {company_id}, agent_id: {agent_id}")
                        
                        self.log_info(f"Webhook - Final user_id: {user_id}, company_id: {company_id}, agent_id: {agent_id}, amount: {amount}")
                        
                        # Recharge the wallet
                        if user_id or company_id or agent_id:
                            self.log_info(f"Webhook - Calling update_wallet_recharge_details with user_id={user_id}, company_id={company_id}, agent_id={agent_id}, amount={amount}")
                            wallet_update_result = update_wallet_recharge_details(user_id, company_id, amount, agent_id)
                            self.log_info(f"Webhook - Wallet recharge update result: {wallet_update_result}")
                            
                            # Verify wallet balance was updated
                            from apps.customer.models import Wallet
                            if user_id and not company_id:
                                wallet = Wallet.objects.filter(user__id=user_id, company_id__isnull=True).first()
                                if wallet:
                                    self.log_info(f"Webhook - Wallet balance after recharge: {wallet.balance}")
                            elif company_id:
                                wallet = Wallet.objects.filter(company_id=company_id).first()
                                if wallet:
                                    self.log_info(f"Webhook - Company wallet balance after recharge: {wallet.balance}")
                            
                            # Send SMS notification (same as PhonePe)
                            from apps.booking.tasks import send_booking_sms_task
                            from apps.customer.models import Wallet
                            from apps.authentication.models import User
                            
                            if user_id and not company_id:
                                wallet_balance = 0
                                wallet = Wallet.objects.filter(
                                    user__id=user_id, company_id__isnull=True
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
            payment_type = validated_data["payment_type"]
            payment_medium = validated_data["payment_medium"]
            media = validated_data["media"]
            transaction_id = validated_data["transaction_id"]

            # Create wallet transaction entry
            wtransact_data = {
                "user_id": user.id,
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

            # Create wallet transaction
            wallet_transaction = WalletTransaction.objects.create(**wtransact_data)

            response_data = {
                "transaction_id": transaction_id,
                "amount": str(float(amount)),
                "user_id": user.id,
                "company_id": company_id,
                "transaction_type": "Credit",
                "transaction_for": "Wallet_Recharge",
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

            # Credit the wallet amount
            success = False
            if wallet_transaction.company_id:
                success = add_company_wallet_amount(
                    wallet_transaction.company_id, approve_amount
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
        operation_description="List all pending wallet recharge requests with filtering options",
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

            # Base queryset for pending wallet recharges
            queryset = (
                WalletTransaction.objects.filter(
                    status="Pending", transaction_for="wallet_recharge"
                )
                .select_related("user", "company")
                .order_by("-created")
            )

            # Apply filters
            user_id = validated_data.get("user_id")
            if user_id:
                queryset = queryset.filter(user_id=user_id)

            company_id = validated_data.get("company_id")
            if company_id:
                queryset = queryset.filter(company_id=company_id)

            transaction_id = validated_data.get("transaction_id")
            if transaction_id:
                queryset = queryset.filter(transaction_id__icontains=transaction_id)

            # Get total count before pagination
            total_count = queryset.count()

            # Apply pagination using your existing paginate_queryset function
            count, paginated_queryset = paginate_queryset(request, queryset)

            # Serialize the data
            serializer = PendingRechargeSerializer(paginated_queryset, many=True)

            return self.get_response(
                status="success",
                message="Pending wallet recharge requests retrieved successfully",
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


class WalletTransactionViewSet(
    viewsets.ModelViewSet, StandardResponseMixin, LoggingMixin
):
    queryset = WalletTransaction.objects.all()
    serializer_class = WalletTransactionSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "post", "put", "patch"]

    def wtransaction_filter_ops(self):
        filter_dict = {}
        user = self.request.user

        # Get active group from token, fall back to default_group
        from apps.authentication.utils.token_utils import get_user_active_group
        from apps.authentication.constants import (
            UserGroups,
            CORPORATE_GROUPS,
            B2C_GROUPS,
        )

        active_group = get_user_active_group(user, self.request)
        default_group = active_group or user.default_group

        # filter by transaction type
        transaction_type = self.request.query_params.get("transaction_type", "")
        if transaction_type:
            filter_dict["transaction_type"] = transaction_type

        # filter by transaction success
        is_transaction_success = self.request.query_params.get(
            "is_transaction_success", ""
        )
        if is_transaction_success:
            filter_dict["is_transaction_success"] = is_transaction_success

        # status filter
        status_param = self.request.query_params.get("status", "")
        if status_param:
            filter_dict["status__iexact"] = status_param

        # fetch filter parameters
        param_dict = self.request.query_params

        # Apply permission-based filtering based on user's active group
        # B2C users (B2C-GRP, B2C-GUEST): can only see their own user wallet transactions
        if default_group in B2C_GROUPS:
            filter_dict["user_id"] = user.id
            filter_dict["company_id__isnull"] = (
                True  # Only user wallet, not company wallet
            )

        # Corporate users (CORP-ADMIN, CORP-EMP, CORPORATE-GRP): can see company wallet transactions
        elif default_group in CORPORATE_GROUPS:
            # All corporate users can see company wallet transactions for their company
            if user.company_id:
                filter_dict["company_id"] = user.company_id
            else:
                # If user has no company_id, they shouldn't see any transactions
                filter_dict["company_id"] = -1  # This will return empty queryset

        # Business users (BUSINESS-GRP, BUS-ADMIN): can see all transactions
        elif default_group in (UserGroups.BUSINESS_GRP, UserGroups.BUS_ADMIN):
            # No filtering - business users can see all transactions
            # Allow query params to filter if provided
            if "company_id" in param_dict:
                filter_dict["company_id"] = param_dict["company_id"]
            if "user_id" in param_dict:
                filter_dict["user_id"] = param_dict["user_id"]

        # Hotelier/Franchise admins: can see all transactions
        elif default_group in (UserGroups.HTLR_ADMIN, UserGroups.FRANCH_ADMIN):
            # Allow query params to filter if provided
            if "company_id" in param_dict:
                filter_dict["company_id"] = param_dict["company_id"]
            if "user_id" in param_dict:
                filter_dict["user_id"] = param_dict["user_id"]

        # For other groups or if no group matches, default to user's own transactions
        else:
            # If company_id is explicitly provided in query params, use it
            company_id = param_dict.get("company_id", "")
            if company_id:
                filter_dict["company_id"] = company_id
            else:
                # Default to user's own transactions
                filter_dict["user_id"] = user.id

        self.queryset = self.queryset.filter(**filter_dict)

    def wtransaction_order_ops(self):
        ordering_params = self.request.query_params.get("ordering", None)
        if ordering_params:
            ordering_list = ordering_params.split(",")
            self.queryset = self.queryset.order_by(*ordering_list)

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
        user_id = request.user.id
        # self.queryset = self.queryset.filter(user_id=user_id)
        # filter and pagination
        self.wtransaction_filter_ops()
        self.wtransaction_order_ops()
        # count = self.wtransaction_pagination_ops()
        count, self.queryset = paginate_queryset(self.request, self.queryset)
        instance = self.queryset
        serializer = WalletTransactionSerializer(instance, many=True)
        custom_response = self.get_response(
            status="success",
            count=count,
            data=serializer.data,  # Use the data from the default response
            message="Wallet Transaction Details",
            status_code=status.HTTP_200_OK,  # 200 for successful retrieval
        )
        return custom_response
    
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