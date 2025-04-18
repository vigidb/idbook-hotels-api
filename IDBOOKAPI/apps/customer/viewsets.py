from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import viewsets
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import views, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.generics import (
    CreateAPIView, ListAPIView, GenericAPIView, RetrieveAPIView, UpdateAPIView
)
from rest_framework.decorators import action
from IDBOOKAPI.mixins import StandardResponseMixin, LoggingMixin
from IDBOOKAPI.permissions import HasRoleModelPermission, AnonymousCanViewOnlyPermission
from IDBOOKAPI.utils import paginate_queryset, get_unique_id_from_time

from apps.payment_gateways.mixins.phonepay_mixins import PhonePayMixin
from apps.customer.utils.db_utils import (
    update_wallet_transaction, update_wallet_recharge_details,
    update_wallet_transaction_detail)
from apps.log_management.utils.db_utils import create_wallet_payment_log

from .serializers import (
    CustomerSerializer, WalletSerializer,
    WalletTransactionSerializer)
# filter serializer for swagger
from .serializers import QueryFilterCustomerSerializer, QueryFilterWalletTransactionSerializer
from .models import (Customer, Wallet, WalletTransaction)
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
    #permission_classes = [AnonymousCanViewOnlyPermission,]
    permission_classes = [IsAuthenticated]
    # filter_backends = [DjangoFilterBackend]
    # filterset_fields = ['service_category', 'district', 'area_name', 'city_name', 'starting_price', 'rating',]
    http_method_names = ['get', 'post', 'put', 'patch','delete']
    # lookup_field = 'custom_id'

    def customer_filter_ops(self):
        filter_dict = {}
        company_id, user_id = None, None
        user = self.request.user
        print("user category:: ", user.category)
        # user.category = 'B-ADMIN'

        # fetch filter parameters
        param_dict= self.request.query_params
        for key in param_dict:
            param_value = param_dict[key]

            if key in ('group_name', 'department', 'privileged', 'active'):
                filter_dict[key] = param_value
            if key == 'company_id':
                company_id =  param_value
            elif key == 'user_id':
                user_id = param_value
        
##        if user.category == 'B-ADMIN':
##             company_id = self.request.query_params.get('company_id', None)
##             user_id = self.request.query_params.get('user_id', None)
##        if user.category == 'CL-ADMIN':
##            company_id = user.company_id if user.company_id else -1
##            # user_id = self.request.query_params.get('user_id', None)
##        elif user.category == 'CL-CUST':
##            user_id = user.id
        
        #company_id = 25    
        if company_id:
            filter_dict['user__company_id'] = company_id
        if user_id:
            filter_dict['user__id'] = user_id

        # filter 
        self.queryset = self.queryset.filter(**filter_dict)

        # search 
        search = self.request.query_params.get('search', '')
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
                is_error=True
            )

        self.log_response(custom_response)  # Log the custom response before returning
        return custom_response

    def update(self, request, *args, **kwargs):
        self.log_request(request)  # Log the incoming request
        compony_id = None
        name = request.data.get('name', None)
        
        user = request.user
        if user.category == 'CL-ADMIN':
            company_id = user.company_id
            if not company_id:
                custom_response = self.get_error_response(
                    message="No privilege to update. Missing authenticated user's company details",
                    status="error", errors=[],error_code="AUTHORIZATION_ERROR",
                    status_code=status.HTTP_403_FORBIDDEN)
                return custom_response
        else:
            custom_response = self.get_error_response(
                message="No privilege to update. The authenticated user is not a company admin",
                status="error", errors=[],error_code="AUTHORIZATION_ERROR",
                status_code=status.HTTP_403_FORBIDDEN)
            return custom_response
            

        # Get the object to be updated
        instance = self.get_object()

        if instance:
            customer_company_id = instance.user.company_id
            if not company_id == customer_company_id:
                custom_response = self.get_error_response(
                    message="No privilege to update. The customer belongs to different company",
                    status="error", errors=[],error_code="AUTHORIZATION_ERROR",
                    status_code=status.HTTP_403_FORBIDDEN)
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
            custom_response = self.get_error_response(message="Validation Error", status="error",
                                                    errors=error_list,error_code="VALIDATION_ERROR",
                                                    status_code=status.HTTP_400_BAD_REQUEST)

        self.log_response(custom_response)  # Log the custom response before returning
        return custom_response

    def partial_update(self, request, *args, **kwargs):
        self.log_request(request)  # Log the incoming request
        compony_id = None
        name = request.data.get('name', None)
        user = request.user
        if user.category == 'CL-ADMIN':
            company_id = user.company_id
            if not company_id:
                custom_response = self.get_error_response(
                    message="No privilege to update. Missing authenticated user's company details",
                    status="error", errors=[],error_code="AUTHORIZATION_ERROR",
                    status_code=status.HTTP_403_FORBIDDEN)
                return custom_response
        else:
            custom_response = self.get_error_response(
                message="No privilege to update. The authenticated user is not a company admin",
                status="error", errors=[],error_code="AUTHORIZATION_ERROR",
                status_code=status.HTTP_403_FORBIDDEN)
            return custom_response
            

        # Get the object to be updated
        instance = self.get_object()

        if instance:
            customer_company_id = instance.user.company_id
            if not company_id == customer_company_id:
                custom_response = self.get_error_response(
                    message="No privilege to update. The customer belongs to different company",
                    status="error", errors=[],error_code="AUTHORIZATION_ERROR",
                    status_code=status.HTTP_403_FORBIDDEN)
                return custom_response

        # Create an instance of your serializer with the request data and the object to be updated
        serializer = self.get_serializer(instance, data=request.data, partial=True)

        if serializer.is_valid():
            print("inside validation error", request.data)
            # If the serializer is valid, perform the default update logic
            #response = super().partial_update(request, *args, **kwargs)
            response = self.perform_update(serializer)
            if name:
                instance.user.name = name
                instance.user.save()
            # Create a custom response
            custom_response = self.get_response(
                status='success',
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
                is_error=True
            )

        self.log_response(custom_response)  # Log the custom response before returning
        return custom_response
        

    @swagger_auto_schema(
        query_serializer=QueryFilterCustomerSerializer, operation_description="List Customer Based on User Roles",
        responses={200: CustomerSerializer(many=True)})
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
                count = count,
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
                is_error=True
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
                is_error=True
            )

        self.log_response(custom_response)  # Log the custom response before returning
        return custom_response

    @action(detail=False, methods=['POST'], parser_classes = [MultiPartParser],
            url_path='user-based/update', url_name='user-based-update')
    def user_based_update(self, request):
        user_id = request.user.id
        name = request.data.get('name', None)
        instance = self.queryset.filter(user_id=user_id).first()
        if not instance:
            custom_response = self.get_error_response(
                message="No customer associated with the user", status="error",
                errors=[],error_code="CUSTOMER_ERROR", status_code=status.HTTP_400_BAD_REQUEST)
            return custom_response
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        if serializer.is_valid():
            response = self.perform_update(serializer)
            if name:
                instance.user.name = name
                instance.user.save()
            custom_response = self.get_response(
                status='success',
                data=serializer.data,  # Use the data from the default response
                message="Customer Updated",
                status_code=status.HTTP_200_OK,  # 200 for successful retrieval

            )
        else:
            error_list = self.custom_serializer_error(serializer.errors)
            custom_response = self.get_error_response(
                message="Validation Error", status="error",
                errors=error_list,error_code="VALIDATION_ERROR", status_code=status.HTTP_400_BAD_REQUEST)
            
##            custom_response = self.get_response(
##                status='error',
##                data=serializer.errors,  # Use the data from the default response
##                message="Customer Updation Failed",
##                status_code=status.HTTP_400_BAD_REQUEST
##
##            )
        
        return custom_response

    @action(detail=False, methods=['GET'], url_path='user-based/retrieve',
            url_name='user-based-retrieve')
    def user_based_retrieve(self, request):
        user_id = request.user.id
        instance = self.queryset.filter(user_id=user_id).first()
        serializer = CustomerSerializer(instance)
        custom_response = self.get_response(
            status='success',
            data=serializer.data,  # Use the data from the default response
            message="Customer Details",
            status_code=status.HTTP_200_OK,  # 200 for successful retrieval
            )
        return custom_response

    @action(detail=True, methods=['DELETE'], url_path='inactive',
            url_name='inactive-customer', permission_classes=[IsAuthenticated])
    def make_customer_inactive(self, request, pk=None):
        print("customer id", pk)
        instance = self.get_object()
        print(instance)
        if instance:
            instance.active = False
            instance.save()
            custom_response = self.get_response(
                status='success', data=None,
                message="Customer set to inactive status",
                status_code=status.HTTP_200_OK,
                )
        else:
                custom_response = self.get_error_response(
                    message="Customer Not Found", status="error",
                    errors=[],error_code="CUSTOMER_MISSING",
                    status_code=status.HTTP_404_NOT_FOUND)
        return custom_response
        

class WalletViewSet(viewsets.ModelViewSet, PhonePayMixin, StandardResponseMixin, LoggingMixin):
    queryset = Wallet.objects.all()
    serializer_class = WalletSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ['get', 'post', 'put', 'patch']

    @action(detail=False, methods=['GET'], url_path='balance',
            url_name='retrieve-wallet-balance')
    def user_based_wallet_retrieve(self, request):
        balance = 0
        user_id = request.user.id
        instance = None
        
        company_id = self.request.query_params.get('company_id', '')
        if company_id:
            instance = self.queryset.filter(company_id=company_id).first()
        else:    
            instance = self.queryset.filter(user_id=user_id, company_id__isnull=True).first()
            
        if instance:
            balance = instance.balance
        data = {'balance': balance}
        custom_response = self.get_response(
            status='success',
            data=data,  # Use the data from the default response
            message="Customer Wallet Balance",
            status_code=status.HTTP_200_OK,  # 200 for successful retrieval
            )
        return custom_response

    @action(detail=False, methods=['POST'], url_path='recharge',
            url_name='recharge')
    def wallet_recharge(self, request):
        user = request.user
        payment_channel = request.data.get('payment_channel')
        redirect_url = request.data.get('redirect_url', '')
        amount = request.data.get('amount', None)
        company_id = request.data.get('company', None)

        payment_log = {}

        if not amount:
            custom_response = self.get_error_response(message="Amount mising", status="error",
                                                      errors=[],error_code="AMOUNT_MISSING",
                                                          status_code=status.HTTP_400_BAD_REQUEST)
            return custom_response

        try:
            append_id = "%s%s" % ('WLT', user.id)
            merchant_transaction_id = get_unique_id_from_time(append_id)

##            wtransact = {"user_id":user.id, "amount":amount,
##                         "transaction_type":"Credit",
##                         "transaction_id":merchant_transaction_id,
##                         "payment_type":"PAYMENT GATEWAY",
##                         "payment_medium":"PHONE PAY"}

            wtransact = {"user_id":user.id,
                         "transaction_id":merchant_transaction_id,
                         "transaction_type":"Credit",
                         "payment_type":"PAYMENT GATEWAY",
                         "payment_medium":"PHONE PAY"
                         }

            payment_log['user_id'] = user.id
            payment_log['merchant_transaction_id'] = merchant_transaction_id
            if company_id:
                wtransact['company_id'] = company_id
                payment_log['company_id'] = company_id

            # wallet transaction entry
            update_wallet_transaction(wtransact)

            if payment_channel == 'PHONE PAY':
                
                merchant_id = settings.MERCHANT_ID
                callback_url = settings.CALLBACK_URL + "/api/v1/customer/wallet/phone-pay/callbackurl/"

                    
                payload = {
                    "merchantId": merchant_id,
                    "merchantTransactionId": merchant_transaction_id,
                    "merchantUserId": user.id,
                    "amount": int(amount) * 100,
                    "redirectUrl": redirect_url, # "https://webhook.site/redirect-url",
                    "redirectMode": "REDIRECT",
                    "callbackUrl": callback_url, #https://webhook-test.com/6d8aac024b00f1e22e38f927a29a6522
                    "paymentInstrument":{ "type": "PAY_PAGE"}
                    }

                req, auth_header = self.get_encrypted_header_and_payload(payload)
                response = self.post_pay_page(req, auth_header)

                if response.status_code == 200:
                    data_json = response.json()
                    payment_log['response'] = data_json
                    instrument_response = data_json.get('data').get('instrumentResponse',{})
                    data_json.pop('data')
                    data_json['instrumentResponse'] = instrument_response
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
                    payment_log['response'] = {'message': response.text}
                    custom_response = self.get_error_response(message=response.text, status="error",
                                                              errors=[],error_code="PAYMENT_ERROR",
                                                          status_code=status.HTTP_400_BAD_REQUEST)
                    # logs
                    create_wallet_payment_log(payment_log)
                    send_booking_sms_task.apply_async(
                        kwargs={
                            'notification_type': 'PAYMENT_FAILED_INFO',
                            'params': {
                                'user_id': user.id,
                                'failed_amount': float(amount),
                                'payment_purpose': 'Wallet Recharge'  # Different purpose
                            }
                        }
                    )
                    return custom_response

            else:
                custom_response = self.get_error_response(
                    message="Invalid option", status="error",
                    errors=[],error_code="VALIDATION_ERROR",
                    status_code=status.HTTP_400_BAD_REQUEST)
                return custom_response
        except Exception as e:
            print(traceback.format_exc())
            payment_log['response'] = {'message': str(e)}
            custom_response = self.get_error_response(message=str(e), status="error",
                                                      errors=[],error_code="INTERNAL_SERVER_ERROR",
                                                      status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
            create_wallet_payment_log(payment_log)

            return custom_response

    @action(detail=False, methods=['POST'], url_path='phone-pay/callbackurl',
            url_name='phone-pay-callbackurl', permission_classes=[])
    def phone_pay_callbackurl(self, request):
        try:
            payment_log = {}
            x_verify = request.META.get('HTTP_X_VERIFY', None)
            if x_verify:
                payment_log['x_verify'] = x_verify
            response = request.data.get('response', None)

            if not response:
                custom_response = self.get_error_response(
                    message="Error in Response", status="error",
                    errors=[],error_code="VALIDATION_ERROR",
                    status_code=status.HTTP_400_BAD_REQUEST)
                payment_log['request'] = {"message":"empty request"}
                # log
                create_wallet_payment_log(payment_log)
                return custom_response

            payment_log['request'] = {"response": response}
            data = base64.b64decode(response)
            decoded_data =  data.decode('utf-8')
            json_data = json.loads(decoded_data)
            payment_log['request'] = json_data
            
            code = json_data.get('code', '')
            message = json_data.get('message', '')

            sub_json_data = json_data.get('data', {})
            amount = int(sub_json_data.get('amount', 0))/100
            merchant_transaction_id = sub_json_data.get('merchantTransactionId', '')
            payment_log['merchant_transaction_id'] = merchant_transaction_id
            transaction_id = sub_json_data.get('transactionId', '')        
            print(json_data)

            payment_details = {
                "transaction_id": merchant_transaction_id, "code": code,
                "transaction_details":message, "payment_type": "PAYMENT GATEWAY",
                "payment_medium": "PHONE PAY", "amount": amount}

            if code == "PAYMENT_SUCCESS":
                payment_details["is_transaction_success"] = True

                # update wallet transaction and wallet
                user_id, company_id = update_wallet_transaction_detail(
                    merchant_transaction_id, payment_details)
                update_wallet_recharge_details(user_id, company_id, amount)

                if user_id:
                    wallet_balance = 0
                    wallet = Wallet.objects.filter(user__id=user_id, company_id__isnull=True).first()
                    if wallet:
                        wallet_balance = wallet.balance
                        print('wallet_balance', wallet_balance)

                        user = User.objects.get(id=user_id)
                        if user and user.mobile_number:
                            print("recharge_amount, mobile_number,user_id ", amount, user.mobile_number, user_id)
                            send_booking_sms_task.apply_async(
                                kwargs={
                                    'notification_type': 'WALLET_RECHARGE_CONFIRMATION',
                                    'params': {
                                        'user_id': user_id,
                                        'recharge_amount': amount,
                                        'wallet_balance': wallet_balance
                                    }
                                }
                            )
                if user_id:
                    payment_log['user_id'] = user_id
                if company_id:
                    payment_log['company_id'] = company_id
            else:
                payment_details["is_transaction_success"] = False
                user_id, company_id = update_wallet_transaction_detail(
                    merchant_transaction_id, payment_details)
                if user_id:
                    payment_log['user_id'] = user_id
                if company_id:
                    payment_log['company_id'] = company_id
                if code == "PAYMENT_ERROR" and user_id:
                    send_booking_sms_task.apply_async(
                        kwargs={
                            'notification_type': 'PAYMENT_FAILED_INFO',
                            'params': {
                                'user_id': user_id,
                                'failed_amount': float(amount),
                                'payment_purpose': 'Wallet Recharge'
                            }
                        }
                    )
                
                

            payment_details['phone_pe_transaction_id'] = transaction_id

            custom_response = self.get_response(
                status="success",
                data=payment_details,  # Use the data from the default response
                message="Wallet Recharge",
                status_code=status.HTTP_200_OK,  # 200 for successful retrieval
                )
            payment_log['response'] = payment_details
            create_wallet_payment_log(payment_log)
            return custom_response   
            
        except Exception as e:
            custom_response = self.get_error_response(message=str(e), status="error",
                                                      errors=[],error_code="INTERNAL_SERVER_ERROR",
                                                      status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
            payment_log['response'] = {'message': str(e)}
            create_wallet_payment_log(payment_log)
            return custom_response
            
        
    

class WalletTransactionViewSet(viewsets.ModelViewSet, StandardResponseMixin, LoggingMixin):
    queryset = WalletTransaction.objects.all()
    serializer_class = WalletTransactionSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ['get', 'post', 'put', 'patch']

    def wtransaction_filter_ops(self):
        filter_dict = {}
        
        # filter 
        transaction_type = self.request.query_params.get('transaction_type', '')
        if transaction_type:
            filter_dict['transaction_type'] = transaction_type

        is_transaction_success = self.request.query_params.get('is_transaction_success', '')
        if is_transaction_success:
            filter_dict['is_transaction_success'] = is_transaction_success
            

        company_id = self.request.query_params.get('company_id', '') 
        if company_id:
            filter_dict['company_id'] = company_id
        else:
            user_id = self.request.user.id
            filter_dict['user_id'] = user_id
        

        self.queryset = self.queryset.filter(**filter_dict)

    def wtransaction_order_ops(self):
        ordering_params = self.request.query_params.get('ordering', None)
        if ordering_params:
            ordering_list = ordering_params.split(',')
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
        responses={200: WalletTransactionSerializer(many=True)})
    @action(detail=False, methods=['GET'], url_path='user',
            url_name='retrieve-wallet-balance')
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
            status='success',
            count=count,
            data=serializer.data,  # Use the data from the default response
            message="Wallet Transaction Details",
            status_code=status.HTTP_200_OK,  # 200 for successful retrieval
            )
        return custom_response

