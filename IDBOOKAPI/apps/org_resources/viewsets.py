from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import viewsets
from rest_framework import views, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.generics import (
    CreateAPIView, ListAPIView, GenericAPIView, RetrieveAPIView, UpdateAPIView
)
from django_filters.rest_framework import DjangoFilterBackend

from IDBOOKAPI.mixins import StandardResponseMixin, LoggingMixin
from IDBOOKAPI.permissions import HasRoleModelPermission, AnonymousCanViewOnlyPermission
from .serializers import (
    AmenityCategorySerializer, AmenitySerializer, EnquirySerializer, RoomTypeSerializer, OccupancySerializer,
    AddressSerializer, AboutUsSerializer, PrivacyPolicySerializer, RefundAndCancellationPolicySerializer,
    TermsAndConditionsSerializer, LegalitySerializer, CareerSerializer, FAQsSerializer, CompanyDetailSerializer,
    UploadedMediaSerializer, CountryDetailsSerializer, UserNotificationSerializer, SubscriberSerializer,
    SubscriptionSerializer, UserSubscriptionSerializer, FeatureSubscriptionSerializer
)
from .models import (
    CompanyDetail, AmenityCategory, Amenity, Enquiry, RoomType, Occupancy, Address,
    AboutUs, PrivacyPolicy, RefundAndCancellationPolicy, TermsAndConditions, Legality,
    Career, FAQs, UploadedMedia, CountryDetails, UserNotification, Subscriber, Subscription,
    UserSubscription, FeatureSubscription
    )
from apps.log_management.models import UserSubscriptionLogs

from IDBOOKAPI.utils import (
    paginate_queryset, get_unique_id_from_time,
    get_date_from_string
    )

from IDBOOKAPI.basic_resources import DISTRICT_DATA
from apps.authentication.models import User
import requests, json
import traceback
import base64

#from rest_framework import decorators
from rest_framework.decorators import action
from django.db.models import Q
from django.conf import settings

from apps.authentication.utils import db_utils as auth_db_utils
from apps.authentication.utils.authentication_utils import get_group_based_on_name
from apps.customer.models import Customer
from apps.payment_gateways.mixins.phonepay_mixins import PhonePayMixin

from apps.org_resources.tasks import send_enquiry_email_task
from apps.org_resources.utils.db_utils import (
    is_corporate_email_exist, is_corporate_number_exist, get_subscription,
    update_subrecur_transaction)
from apps.org_resources.utils.subscription_utils import (
    subscription_phone_pe_process, subscription_payu_process,
    subscription_cancel_payu_process)
from IDBOOKAPI.utils import paginate_queryset

from datetime import datetime
import pytz
from dateutil.relativedelta import relativedelta

class CompanyDetailViewSet(viewsets.ModelViewSet, StandardResponseMixin, LoggingMixin):
    queryset = CompanyDetail.objects.all()
    serializer_class = CompanyDetailSerializer
    # permission_classes = [IsAuthenticated]
    permission_classes = []
    http_method_names = ['get', 'post', 'put', 'patch', 'delete']
    # filter_backends = [DjangoFilterBackend]
    # filterset_fields = ['service_category', 'area_name', 'city_name', 'starting_price', 'rating',]

    permission_classes_by_action = {'create': [AllowAny], 'update': [IsAuthenticated],
                                    'destroy': [IsAuthenticated]}

    def get_permissions(self):
        try: 
            return [permission() for permission in self.permission_classes_by_action[self.action]]
        except KeyError: 
            # action is not set return default permission_classes
            return [permission() for permission in self.permission_classes]

    def contact_verification(self):
        error_list = []
        
        company_email = self.request.data.get('company_email', '')
        company_phone = self.request.data.get('company_phone', '')
        contact_number = self.request.data.get('contact_number', '')
        contact_email_address = self.request.data.get('contact_email_address', '')

        # otp for company email
        otp_cmp_email = self.request.data.get('otp_cmp_email', None)
        # otp for contact mobile
        otp_cnt_mob = self.request.data.get('otp_cnt_mob', None)
        otp_cnt_email = self.request.data.get('otp_cnt_email', None)
        
        if otp_cmp_email and otp_cnt_mob and otp_cnt_email:
            # company email verify
            cmpobj_emailotp = auth_db_utils.check_email_otp(
                company_email, otp_cmp_email, 'VERIFY')
            if not cmpobj_emailotp:
                error_list.append({"field":"company_email",
                               "error_code":"INVALID_OTP",
                               "message": "Invalid Email OTP"})

            # contact number verify    
            cntobj_mobotp = auth_db_utils.check_mobile_otp(
                contact_number, otp_cnt_mob, 'SIGNUP')
            if not cntobj_mobotp:
                error_list.append({"field":"contact_number",
                               "error_code":"INVALID_OTP",
                               "message": "Invalid Mobile OTP"})

            # contact email verify
            cntobj_emailotp = auth_db_utils.check_email_otp(
                contact_email_address, otp_cnt_email, 'SIGNUP')
            if not cntobj_emailotp:
                error_list.append({"field":"contact_email_address",
                               "error_code":"INVALID_OTP",
                               "message": "Invalid Email OTP"})

        if error_list:
            return error_list

        group_name = "CORPORATE-GRP"
        self.grp, self.role = get_group_based_on_name(group_name)
        if not self.grp or not self.role:
            error_list.append({"field":"",
                           "error_code":"INVALID_GRP",
                           "message": "Invalid Group"})
            return error_list

        # check corporate email exist
        is_exist = is_corporate_email_exist(company_email)
        if is_exist:
            error_list.append({"field":"company_email",
                           "error_code":"CMP_EMAIL_EXIST",
                           "message": "Company email already exist"})

        # check corporate number exist
        is_number_exist = is_corporate_number_exist(company_phone)
        if is_number_exist:
            error_list.append({"field":"company_phone",
                           "error_code":"CMP_NUMBER_EXIST",
                           "message": "Company number already exist"})

        # check contact email exist
        cntemail_grp_users = auth_db_utils.get_userid_list(
            contact_email_address, group=self.grp)
        if cntemail_grp_users:
            error_list.append({"field":"contact_email_address",
                           "error_code":"CNT_EMAIL_EXIST",
                           "message": "Contact email already exist"})
            
        # check contact number exist
        mobile_grp_users = auth_db_utils.get_userid_list(
            contact_number, group=self.grp)
        if mobile_grp_users:
            error_list.append({"field":"contact_number",
                           "error_code":"CNT_MOB_EXIST",
                           "message": "Contact number already exist"})

        return error_list

    def update_corporate_verification(self, instance):
        error_list = []
        # daneshvar.khot@sandnetwork.in
        company_email = self.request.data.get('company_email', '')
        company_phone = self.request.data.get('company_phone', '')
        contact_number = self.request.data.get('contact_number', '')
        contact_email_address = self.request.data.get('contact_email_address', '')

        if company_email and instance.company_email != company_email:
            error_list.append({"field":"company_email",
                               "error_code":"UPDATE_NOT_PERMITTED",
                               "message": "company email update not allowed"})

        if company_phone and instance.company_phone != company_phone:
            error_list.append({"field":"company_phone",
                               "error_code":"UPDATE_NOT_PERMITTED",
                               "message": "company_phone update not allowed"})
            

        if contact_number and instance.contact_number != contact_number:
            error_list.append({"field":"contact_number",
                               "error_code":"UPDATE_NOT_PERMITTED",
                               "message": "contact_number update not allowed"})

        if contact_email_address and instance.contact_email_address != contact_email_address:
            error_list.append({"field":"contact_email_address",
                               "error_code":"UPDATE_NOT_PERMITTED",
                               "message": "contact_email_address update not allowed"})

        return error_list
                 
        

    def update_contact_verification(self, instance):
        error_list = []
        
        company_email = self.request.data.get('company_email', '')
        company_phone = self.request.data.get('company_phone', '')
        contact_number = self.request.data.get('contact_number', '')
        contact_email_address = self.request.data.get('contact_email_address', '')

        # otp for company email
        otp_cmp_email = self.request.data.get('otp_cmp_email', None)
        # otp for contact mobile
        otp_cnt_mob = self.request.data.get('otp_cnt_mob', None)
        otp_cnt_email = self.request.data.get('otp_cnt_email', None)

        
        # company email verify
        if company_email and instance.company_email != company_email:
            cmpobj_emailotp = auth_db_utils.check_email_otp(
                company_email, otp_cmp_email, 'VERIFY')
            if not cmpobj_emailotp:
                error_list.append({"field":"company_email",
                               "error_code":"INVALID_OTP",
                               "message": "Invalid Email OTP"})

            # check corporate email exist
            is_exist = is_corporate_email_exist(company_email)
            if is_exist:
                error_list.append({"field":"company_email",
                               "error_code":"CMP_EMAIL_EXIST",
                               "message": "Company email already exist"})

        # check corporate number exist
        if company_phone and instance.company_phone != company_phone:
            is_number_exist = is_corporate_number_exist(company_phone)
            if is_number_exist:
                error_list.append({"field":"company_phone",
                               "error_code":"CMP_NUMBER_EXIST",
                               "message": "Company number already exist"})

        # contact number verify
        if contact_number and instance.contact_number != contact_number:
            cntobj_mobotp = auth_db_utils.check_mobile_otp(
                contact_number, otp_cnt_mob, 'SIGNUP')
            if not cntobj_mobotp:
                error_list.append({"field":"contact_number",
                               "error_code":"INVALID_OTP",
                               "message": "Invalid Mobile OTP"})

        # contact email verify
        if contact_email_address and instance.contact_email_address != contact_email_address:
            cntobj_emailotp = auth_db_utils.check_email_otp(
                contact_email_address, otp_cnt_email, 'SIGNUP')
            if not cntobj_emailotp:
                error_list.append({"field":"contact_email_address",
                               "error_code":"INVALID_OTP",
                               "message": "Invalid Email OTP"})

        if error_list:
            return error_list

        group_name = "CORPORATE-GRP"
        self.grp, self.role = get_group_based_on_name(group_name)
        if not self.grp or not self.role:
            error_list.append({"field":"",
                           "error_code":"INVALID_GRP",
                           "message": "Invalid Group"})
            return error_list

        # check corporate email exist
        if company_email and instance.company_email != company_email:
            is_exist = is_corporate_email_exist(company_email)
            if is_exist:
                error_list.append({"field":"company_email",
                               "error_code":"CMP_EMAIL_EXIST",
                               "message": "Company email already exist"})

        # check contact email exist
        if contact_email_address and instance.contact_email_address != contact_email_address:
            cntemail_grp_users = auth_db_utils.get_userid_list(
                contact_email_address, group=self.grp)
            if cntemail_grp_users:
                error_list.append({"field":"contact_email_address",
                               "error_code":"CNT_EMAIL_EXIST",
                               "message": "Contact email already exist"})
            
        # check contact number exist
        if contact_number and instance.contact_number != contact_number:
            mobile_grp_users = auth_db_utils.get_userid_list(
                contact_number, group=self.grp)
            if mobile_grp_users:
                error_list.append({"field":"contact_number",
                               "error_code":"CNT_MOB_EXIST",
                               "message": "Contact number already exist"})
                
        return error_list
        


    def create(self, request, *args, **kwargs):
        self.log_request(request)  # Log the incoming request
        error_list = self.contact_verification()
        if error_list:
            response = self.get_error_response(
                message="Validation Error", status="error",
                errors=error_list, error_code="VALIDATION_ERROR",
                status_code=status.HTTP_400_BAD_REQUEST)
            return response

        # Create an instance of your serializer with the request data
        serializer = self.get_serializer(data=request.data)

        if serializer.is_valid():
            # If the serializer is valid, perform the default creation logic
            company_detail = serializer.save()
            
            #response = super().create(request, *args, **kwargs)

##            grp = auth_db_utils.get_group_by_name('CORPORATE-GRP')
##            role = auth_db_utils.get_role_by_name('CORP-ADMIN')

            # create or update user based on company email
            user = User.objects.filter(email=company_detail.contact_email_address).first()
            if not user:
                user = User.objects.create(name=company_detail.contact_person_name,
                                           email=company_detail.contact_email_address,
                                           mobile_number=company_detail.contact_number,
                                           company_id=company_detail.id,
                                           default_group='CORPORATE-GRP')
                Customer.objects.create(user_id=user.id, active=True)
            else:
                #user.category='CL-ADMIN'
                user.default_group='CORPORATE-GRP'
                user.company_id=company_detail.id
                user.save()
                customer = Customer.objects.filter(user_id=user.id).first()
                if not customer:
                    Customer.objects.create(user_id=user.id, active=True)
                    
            if user:
                # add group and roles
                if self.grp:
                    user.groups.add(self.grp)
                if self.role:
                    user.roles.add(self.role)
                    
                refresh = RefreshToken.for_user(user)

                user_roles = [uroles for uroles in user.roles.values('id','name')]
                user_groups = [ugroups for ugroups in user.groups.values('id','name')]

                data = {'refreshToken': str(refresh),
                        'groups': user_groups,
                        'roles': user_roles,
                        'accessToken': str(refresh.access_token),
                        'expiresIn': 0,
                        'company': serializer.data,
                        }
            else:
                data = {'refreshToken': "",
                        'accessToken': "",
                        'expiresIn': 0,
                        'company': serializer.data,
                        }

            # Create a custom response
            custom_response = self.get_response(
                status='success',
                data=data,  # Use the data from the default response
                message="CompanyDetail Created",
                status_code=status.HTTP_201_CREATED,  # 201 for successful creation

            )
        else:
##            # If the serializer is not valid, create a custom response with error details
##            custom_response = self.get_response(
##                data=serializer.errors,  # Use the serializer's error details
##                message="Validation Error",
##                status_code=status.HTTP_400_BAD_REQUEST,  # 400 for validation error
##                is_error=True
##            )
            
            error_list = self.custom_serializer_error(serializer.errors)
            custom_response = self.get_error_response(message="Validation Error", status="error",
                                                    errors=error_list,error_code="VALIDATION_ERROR",
                                                    status_code=status.HTTP_400_BAD_REQUEST)

        self.log_response(custom_response)  # Log the custom response before returning
        return custom_response
    
    def update(self, request, *args, **kwargs):
        self.log_request(request)  # Log the incoming request

        # Get the object to be updated
        instance = self.get_object()

        error_list = self.update_corporate_verification(instance)
        if error_list:
            response = self.get_error_response(
                message="Validation Error", status="error",
                errors=error_list, error_code="VALIDATION_ERROR",
                status_code=status.HTTP_400_BAD_REQUEST)
            return response
        

        # Create an instance of your serializer with the request data and the object to be updated
        serializer = self.get_serializer(instance, data=request.data)

        if serializer.is_valid():
            # If the serializer is valid, perform the default update logic
            response = super().update(request, *args, **kwargs)

            # Create a custom response
            custom_response = self.get_response(
                data=response.data,  # Use the data from the default response
                message="CompanyDetail Updated",
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

    def list(self, request, *args, **kwargs):
        self.log_request(request)  # Log the incoming request

##        offset = int(self.request.query_params.get('offset', 0))
##        limit = int(self.request.query_params.get('limit', 10))
        search = request.query_params.get('search', '')
        approved = request.query_params.get('approved', None)

        if search:
            search_q_filter = Q(company_name__icontains=search) | Q(brand_name__icontains=search)
            self.queryset = self.queryset.filter(search_q_filter)

        if approved is not None:
            if approved.lower() == 'true':
                self.queryset = self.queryset.filter(approved=True)
            elif approved.lower() == 'false':
                self.queryset = self.queryset.filter(approved=False)


##        count = self.queryset.count()
##        self.queryset = self.queryset[offset:offset+limit]

        count, self.queryset = paginate_queryset(self.request,  self.queryset)
        

        # Perform the default listing logic
        response = super().list(request, *args, **kwargs)

        if response.status_code == status.HTTP_200_OK:
            # If the response status code is OK (200), it's a successful listing
            custom_response = self.get_response(
                data=response.data,  # Use the data from the default response
                status='success',
                message="List Retrieved",
                count=count,
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

    #@decorators.action(permission_classes=[IsAuthenticated])
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

    @action(detail=False, methods=['POST'], url_path='create',
            url_name='create-company', permission_classes=[IsAuthenticated])
    def create_company_by_badmin(self, request):
        buser_id = request.user.id

        error_list = self.contact_verification()
        if error_list:
            response = self.get_error_response(
                message="Validation Error", status="error",
                errors=error_list, error_code="VALIDATION_ERROR",
                status_code=status.HTTP_400_BAD_REQUEST)
            return response
        
        # Create an instance of your serializer with the request data
        serializer = self.get_serializer(data=request.data)

        if serializer.is_valid():
            # If the serializer is valid, perform the default creation logic
            company_detail = serializer.save()
            #response = super().create(request, *args, **kwargs)
            grp = auth_db_utils.get_group_by_name('CORPORATE-GRP')
            role = auth_db_utils.get_role_by_name('CORP-ADMIN')

            # create or update user based on company email
            user = User.objects.filter(email=company_detail.contact_email_address).first()
            if not user:
                user = User.objects.create(name=company_detail.contact_person_name,
                                           email=company_detail.contact_email_address,
                                           mobile_number=company_detail.contact_number,
                                           company_id=company_detail.id,
                                           default_group='CORPORATE-GRP')
                Customer.objects.create(user_id=user.id, active=True)
            else:
                user.company_id=company_detail.id
                user.default_group='CORPORATE-GRP'
                user.save()

                customer = Customer.objects.filter(user_id=user.id).first()
                if not customer:
                    Customer.objects.create(user_id=user.id, active=True)

            if grp:
                user.groups.add(grp)
            if role:
                user.roles.add(role)

            # Create a custom response
            custom_response = self.get_response(
                status='success',
                data=serializer.data,  # Use the data from the default response
                message="CompanyDetail Created",
                status_code=status.HTTP_201_CREATED,  # 201 for successful creation

            )
        else:
            error_list = self.custom_serializer_error(serializer.errors)
            custom_response = self.get_error_response(message="Validation Error", status="error",
                                                    errors=error_list,error_code="VALIDATION_ERROR",
                                                    status_code=status.HTTP_400_BAD_REQUEST)

        self.log_response(custom_response)  # Log the custom response before returning
        return custom_response

    @action(detail=True, methods=['PATCH'], url_path='update/contact',
            url_name='update-contact', permission_classes=[IsAuthenticated])
    def update_contact(self, request, pk):

        company_email = self.request.data.get('company_email', '')
        company_phone = self.request.data.get('company_phone', '')
        contact_number = self.request.data.get('contact_number', '')
        contact_email_address = self.request.data.get('contact_email_address', '')
        contact_person_name = self.request.data.get('contact_person_name','')

        contact_user_update = False
        
        instance = self.get_object()
        
        error_list = self.update_contact_verification(instance)
        if error_list:
            response = self.get_error_response(
                message="Validation Error", status="error",
                errors=error_list, error_code="VALIDATION_ERROR",
                status_code=status.HTTP_400_BAD_REQUEST)
            return response

        if company_email and instance.company_email != company_email:
            instance.company_email = company_email
        if company_phone and instance.company_phone != company_phone:
            instance.company_phone = company_phone
        if contact_number and instance.contact_number != contact_number:
            instance.contact_number = contact_number
        if contact_email_address and instance.contact_email_address != contact_email_address:
            instance.contact_email_address = contact_email_address
            contact_user_update = True
        if contact_person_name and instance.contact_person_name != contact_person_name:
            instance.contact_person_name = contact_person_name

        instance.save()
        if contact_user_update:
            user = User.objects.filter(email=instance.contact_email_address).first()
            if not user:
                user = User.objects.create(name=instance.contact_person_name,
                                           email=instance.contact_email_address,
                                           mobile_number=instance.contact_number,
                                           company_id=instance.id,
                                           default_group='CORPORATE-GRP')
                Customer.objects.create(user_id=user.id, active=True)
            else:
                user.company_id=instance.id
                user.default_group='CORPORATE-GRP'
                user.save()

                customer = Customer.objects.filter(user_id=user.id).first()
                if not customer:
                    Customer.objects.create(user_id=user.id, active=True)

            if self.grp and not user.groups.filter(name='CORPORATE-GRP'):
                user.groups.add(self.grp)
            if self.role and not user.roles.filter(name='CORP-ADMIN'):
                user.roles.add(self.role)

        serializer = CompanyDetailSerializer(instance)

        custom_response = self.get_response(
            status='success',
            data=serializer.data,  # Use the data from the default response
            message="Company contact details updated",
            status_code=status.HTTP_200_OK,  # 201 for successful creation
        )
        return custom_response
        
        

    def destroy(self, request, pk=None):

        instance = self.get_object()
        instance.is_active=False
        instance.save()

        custom_response = self.get_response(
            status='success', data=None,
            message="Company set to inactive status",
            status_code=status.HTTP_200_OK,
            )
        return custom_response

        


class UploadedMediaViewSet(viewsets.ModelViewSet, StandardResponseMixin, LoggingMixin):
    queryset = UploadedMedia.objects.all()
    serializer_class = UploadedMediaSerializer
    # permission_classes = [AnonymousCanViewOnlyPermission,]
    http_method_names = ['get', 'post', 'put', 'patch']
    # filter_backends = [DjangoFilterBackend]
    # filterset_fields = ['service_category', 'area_name', 'city_name', 'starting_price', 'rating',]

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
                message="Media Created",
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

        # Get the object to be updated
        instance = self.get_object()

        # Create an instance of your serializer with the request data and the object to be updated
        serializer = self.get_serializer(instance, data=request.data)

        if serializer.is_valid():
            # If the serializer is valid, perform the default update logic
            response = super().update(request, *args, **kwargs)

            # Create a custom response
            custom_response = self.get_response(
                data=response.data,  # Use the data from the default response
                message="Media Updated",
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

    def list(self, request, *args, **kwargs):
        self.log_request(request)  # Log the incoming request

        # Perform the default listing logic
        response = super().list(request, *args, **kwargs)

        if response.status_code == status.HTTP_200_OK:
            # If the response status code is OK (200), it's a successful listing
            custom_response = self.get_response(
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


class AmenityCategoryViewSet(viewsets.ModelViewSet, StandardResponseMixin, LoggingMixin):
    queryset = AmenityCategory.objects.all()
    serializer_class = AmenityCategorySerializer
    permission_classes = [AnonymousCanViewOnlyPermission,]
    http_method_names = ['get', 'post', 'put', 'patch']

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
                message="AmenityCategory Created",
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

        # Get the object to be updated
        instance = self.get_object()

        # Create an instance of your serializer with the request data and the object to be updated
        serializer = self.get_serializer(instance, data=request.data)

        if serializer.is_valid():
            # If the serializer is valid, perform the default update logic
            response = super().update(request, *args, **kwargs)

            # Create a custom response
            custom_response = self.get_response(
                data=response.data,  # Use the data from the default response
                message="AmenityCategory Updated",
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

    def list(self, request, *args, **kwargs):
        self.log_request(request)  # Log the incoming request

        # Perform the default listing logic
        response = super().list(request, *args, **kwargs)

        if response.status_code == status.HTTP_200_OK:
            # If the response status code is OK (200), it's a successful listing
            custom_response = self.get_response(
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


class AmenityViewSet(viewsets.ModelViewSet, StandardResponseMixin, LoggingMixin):
    queryset = Amenity.objects.all()
    serializer_class = AmenitySerializer
    permission_classes = [AnonymousCanViewOnlyPermission,]
    http_method_names = ['get', 'post', 'put', 'patch']
    filter_backends = [DjangoFilterBackend]
    filterset_fields = [
        'amenity_category__id', 'amenity_category__title', 'amenity_category__active', 'title', 'active'
    ]

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
                message="Amenity Created",
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

        # Get the object to be updated
        instance = self.get_object()

        # Create an instance of your serializer with the request data and the object to be updated
        serializer = self.get_serializer(instance, data=request.data)

        if serializer.is_valid():
            # If the serializer is valid, perform the default update logic
            response = super().update(request, *args, **kwargs)

            # Create a custom response
            custom_response = self.get_response(
                data=response.data,  # Use the data from the default response
                message="Amenity Updated",
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

    def list(self, request, *args, **kwargs):
        self.log_request(request)  # Log the incoming request

        # Perform the default listing logic
        response = super().list(request, *args, **kwargs)

        if response.status_code == status.HTTP_200_OK:
            # If the response status code is OK (200), it's a successful listing
            custom_response = self.get_response(
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


class EnquiryViewSet(viewsets.ModelViewSet, StandardResponseMixin, LoggingMixin):
    queryset = Enquiry.objects.all()
    serializer_class = EnquirySerializer
    permission_classes = []
    http_method_names = ['get', 'post', 'put', 'patch']

    def get_queryset(self):
        queryset = Enquiry.objects.all()

        phone_no = self.request.query_params.get('phone_no')
        email = self.request.query_params.get('email')
        name = self.request.query_params.get('name')

        if phone_no:
            queryset = queryset.filter(phone_no__icontains=phone_no)
        if email:
            queryset = queryset.filter(email__icontains=email)
        if name:
            queryset = queryset.filter(name__icontains=name)

        queryset = queryset.order_by('-created')

        offset = self.request.query_params.get('offset')
        limit = self.request.query_params.get('limit')

        if offset is not None and limit is not None:
            offset = int(offset)
            limit = int(limit)
            queryset = queryset[offset:offset + limit]

        return queryset

    def create(self, request, *args, **kwargs):
        self.log_request(request)  # Log the incoming request

        # Create an instance of your serializer with the request data
        serializer = self.get_serializer(data=request.data)

        if serializer.is_valid():
            # If the serializer is valid, perform the default creation logic
            response = super().create(request, *args, **kwargs)
            enquiry_id = response.data.get('id')
            print("enquiry id", enquiry_id)
            send_enquiry_email_task.apply_async(args=[enquiry_id])
            # Create a custom response
            custom_response = self.get_response(
                data=response.data,  # Use the data from the default response
                message="Enquiry Created",
                status_code=status.HTTP_201_CREATED,  # 201 for successful creation

            )
        else:
            serializer_errors = self.custom_serializer_error(serializer.errors)
            custom_response = self.get_error_response(message="Validation Error", status="error",
                                                      errors=serializer_errors,error_code="VALIDATION_ERROR",
                                                      status_code=status.HTTP_400_BAD_REQUEST)

        self.log_response(custom_response)  # Log the custom response before returning
        return custom_response

    def update(self, request, *args, **kwargs):
        self.log_request(request)  # Log the incoming request

        # Get the object to be updated
        instance = self.get_object()

        # Create an instance of your serializer with the request data and the object to be updated
        serializer = self.get_serializer(instance, data=request.data)

        if serializer.is_valid():
            # If the serializer is valid, perform the default update logic
            response = super().update(request, *args, **kwargs)

            # Create a custom response
            custom_response = self.get_response(
                data=response.data,  # Use the data from the default response
                message="Enquiry Updated",
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

    def list(self, request, *args, **kwargs):
        self.log_request(request)  # Log the incoming request
        # self.queryset = self.get_queryset()
        # offset = request.query_params.get('offset')
        # limit = request.query_params.get('limit')
        
        # if offset is not None and limit is not None:
        #     count, self.queryset = paginate_queryset(request, self.queryset)
        # else:
        #     count = self.queryset.count()

        count = self.get_queryset().count()

        # Perform the default listing logic
        response = super().list(request, *args, **kwargs)

        if response.status_code == status.HTTP_200_OK:
            # If the response status code is OK (200), it's a successful listing
            custom_response = self.get_response(
                data=response.data,  # Use the data from the default response
                count=count,
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

class SubscriberViewset(viewsets.ModelViewSet, StandardResponseMixin, LoggingMixin):
    queryset = Subscriber.objects.all()
    serializer_class = SubscriberSerializer
    permission_classes = []
    http_method_names = ['get', 'post', 'put', 'patch']

    

    def create(self, request, *args, **kwargs):

        email = self.request.data.get('email', None)
        if not email:
            custom_response = self.get_error_response(message="Missing email", status="error",
                                                      errors=[],error_code="VALIDATION_ERROR",
                                                      status_code=status.HTTP_400_BAD_REQUEST)
            return custom_response

        subscriber_obj = Subscriber.objects.filter(email=email)
        if subscriber_obj.exists():
            custom_response = self.get_error_response(message="Email already subscribed", status="error",
                                                      errors=[],error_code="VALIDATION_ERROR",
                                                      status_code=status.HTTP_400_BAD_REQUEST)
            return custom_response

        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            # If the serializer is valid, perform the default creation logic
            response = super().create(request, *args, **kwargs)
            # Create a custom response
            custom_response = self.get_response(
                data=response.data,  # Use the data from the default response
                count=1,
                status="success",
                message="Subscribed Successfully",
                status_code=status.HTTP_201_CREATED,  # 201 for successful creation
            )
            return custom_response
        else:
            error_list = self.custom_serializer_error(serializer.errors)
            custom_response = self.get_error_response(
                message="Validation Error", status="error",
                errors=error_list,error_code="VALIDATION_ERROR", status_code=status.HTTP_400_BAD_REQUEST)
            return custom_response
        
class SubscriptionViewset(viewsets.ModelViewSet, StandardResponseMixin, LoggingMixin):
    queryset = Subscription.objects.all()
    serializer_class = SubscriptionSerializer
    # permission_classes = [IsAuthenticated]
    http_method_names = ['get', 'post', 'put', 'patch', 'delete']

    permission_classes_by_action = {'create': [IsAuthenticated], 'update': [IsAuthenticated],
                                    'list':[AllowAny], 'destroy': [IsAuthenticated]}

    def get_permissions(self):
        try: 
            return [permission() for permission in self.permission_classes_by_action[self.action]]
        except KeyError: 
            # action is not set return default permission_classes
            return [permission() for permission in self.permission_classes]

    def subscription_filter_ops(self):
        filter_dict = {}
        param_dict= self.request.query_params
        
        for key in param_dict:
            param_value = param_dict[key]
            if key in ('active', 'subscription_type'):
                filter_dict[key] = param_value

        if filter_dict:
            self.queryset = self.queryset.filter(**filter_dict)
            
        
        

    def create(self, request, *args, **kwargs):
        self.log_request(request)  # Log the incoming request

        name = self.request.data.get('name', '')
        subscription_type = self.request.data.get('subscription_type', '')

        is_name_exist = self.queryset.filter(
            name__iexact=name, subscription_type=subscription_type,
            active=True)
        
        if is_name_exist:
            custom_response = self.get_error_response(message="Name exist", status="error",
                                                      errors=[],error_code="DUPLICATE_NAME",
                                                      status_code=status.HTTP_400_BAD_REQUEST)
            return custom_response
            

        # Create an instance of your serializer with the request data
        serializer = self.get_serializer(data=request.data)

        if serializer.is_valid():
            # If the serializer is valid, perform the default creation logic
            response = super().create(request, *args, **kwargs)

            # Create a custom response
            custom_response = self.get_response(
                data=response.data,  # Use the data from the default response
                status='success',
                message="Subscription Created",
                status_code=status.HTTP_201_CREATED,  # 201 for successful creation

            )
        else:
            error_list = self.custom_serializer_error(serializer.errors)
            custom_response = self.get_error_response(
                message="Validation Error", status="error",
                errors=error_list,error_code="VALIDATION_ERROR", status_code=status.HTTP_400_BAD_REQUEST)
            return custom_response

        self.log_response(custom_response)  # Log the custom response before returning
        return custom_response

    def partial_update(self, request, *args, **kwargs):

        name = self.request.data.get('name', '')
        subscription_type = self.request.data.get('subscription_type', '')
        active = self.request.data.get('active', None)
        
        # Get the object to be updated
        instance = self.get_object()
        if not subscription_type:
            subscription_type = instance.subscription_type

        if not name:
            name = instance.name

        is_name_exist = self.queryset.filter(
            name__iexact=name, subscription_type=subscription_type, active=True).exclude(
                id=instance.id)
            
        if is_name_exist:
            custom_response = self.get_error_response(message="Name exist", status="error",
                                                      errors=[],error_code="DUPLICATE_NAME",
                                                      status_code=status.HTTP_400_BAD_REQUEST)
            return custom_response
                
        
        # Create an instance of your serializer with the request data and the object to be updated
        serializer = self.get_serializer(instance, data=request.data, partial=True)

        if serializer.is_valid():
            response = super().partial_update(request, *args, **kwargs)
            
            custom_response = self.get_response(
                data=response.data,  # Use the data from the default response
                status='success',
                message="Update success",
                status_code=status.HTTP_200_OK,  # 200 for successful listing
            )
            return custom_response
        else:
            error_list = self.custom_serializer_error(serializer.errors)
            custom_response = self.get_error_response(
                message="Validation Error", status="error",
                errors=error_list,error_code="VALIDATION_ERROR", status_code=status.HTTP_400_BAD_REQUEST)
            return custom_response

    
        

    def list(self, request, *args, **kwargs):
        self.log_request(request)  # Log the incoming request

        self.subscription_filter_ops()
        
        # paginate the result
        count, self.queryset = paginate_queryset(self.request,  self.queryset)
        
        # Perform the default listing logic
        response = super().list(request, *args, **kwargs)

        # If the response status code is OK (200), it's a successful listing
        custom_response = self.get_response(
            status='success',
            count=count,
            data=response.data,  # Use the data from the default response
            message="List Retrieved",
            status_code=status.HTTP_200_OK,  # 200 for successful listing
        )
        
        return custom_response

    def destroy(self, request, pk=None):

        instance = self.get_object()
        instance.delete()

        custom_response = self.get_response(
            status='success', data=None, count=1,
            message="Subscription deleted",
            status_code=status.HTTP_200_OK,
            )
        return custom_response


class UserSubscriptionViewset(viewsets.ModelViewSet, StandardResponseMixin, LoggingMixin):
    queryset = UserSubscription.objects.all()
    serializer_class = UserSubscriptionSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ['get', 'post', 'patch', 'delete']

##    permission_classes_by_action = {'create': [IsAuthenticated], 'update': [IsAuthenticated],
##                                    'list':[AllowAny], 'destroy': [IsAuthenticated]}
##
##    def get_permissions(self):
##        try: 
##            return [permission() for permission in self.permission_classes_by_action[self.action]]
##        except KeyError: 
##            # action is not set return default permission_classes
##            return [permission() for permission in self.permission_classes]

    def user_subscription_param_ops(self):
        
        filter_dict = {}
        # fetch filter parameters
        param_dict= self.request.query_params
        for key in param_dict:
            if key in ('user', 'idb_sub',
                       'paid', 'active', 'is_cancelled',
                       'is_cancel_initiated'):
                filter_dict[key] = param_dict[key]

        if filter_dict:
            self.queryset = self.queryset.filter(**filter_dict)

        # search 
        search = self.request.query_params.get('search', '')
        if search:
            search_q_filter = Q(pg_subid__icontains=search) | Q(mandate_tnx_id__icontains=search) | Q(cancel_tnx_id__icontains=search)
            self.queryset = self.queryset.filter(search_q_filter)

    def property_order_ops(self):
        ordering_params = self.request.query_params.get('ordering', None)
        if ordering_params:
            ordering_list = ordering_params.split(',')
            self.queryset = self.queryset.order_by(*ordering_list)


    def create(self, request, *args, **kwargs):
        self.log_request(request)  # Log the incoming request
        user_id = self.request.user.id
        idb_sub_id = request.data.get('idb_sub')
        upi = request.data.get('upi', '')
        payment_medium = request.data.get('payment_medium')
        daily = request.data.get('daily', 0)
        
        name = request.data.get('name')
        email = request.data.get('email')
        mobile_number = request.data.get('mobile_number')

        start_date = request.data.get('start_date')
        end_date = request.data.get('end_date')

        start_date = get_date_from_string(start_date)
        end_date = get_date_from_string(end_date)
        
        usersub_obj = None
        data = {}

        # generate merchant user id
        merchant_userid = "%s%d" % ("MU", user_id)
        # merchant_userid = get_unique_id_from_time(merchant_userid)

        # generate merchant subscription id
        merchant_subid = "%s%d%d" %("MSUB", user_id, idb_sub_id)
        merchant_subid = get_unique_id_from_time(merchant_subid)
        
        user_subscription_dict = {"user_id":user_id,
                                  "idb_sub_id":idb_sub_id}
        
        subscription = get_subscription(idb_sub_id)
        if not subscription:
            custom_response = self.get_error_response(
                message="Subscription not exist", status="error",
                errors=[],error_code="SUBSCRIPTION_NOT_EXIST",
                status_code=status.HTTP_400_BAD_REQUEST)
            return custom_response

        auth_request_id = "%s%d" % ("TX", user_id)
        auth_request_id = get_unique_id_from_time(auth_request_id)

        if payment_medium == 'PayU':
            user_subscription_dict['payment_type'] = 'PAYMENT GATEWAY'
            user_subscription_dict['payment_medium'] = payment_medium
            params = {'merchant_userid':merchant_userid,'merchant_subid':merchant_subid,
                      "txnid":auth_request_id, "amount":subscription.price,
                      "subscription_name":subscription.name,
                      "subscription_type":subscription.subscription_type,
                      "firstname":name,
                      "email":email, "phone":mobile_number,
                      "start_date":start_date,"end_date":end_date,
                      "daily":daily}
         
            response, usersub_obj = subscription_payu_process(user_subscription_dict, params)
            
            data = {"url":response.url, "text":response.text, "status_code":response.status_code}
            

        elif payment_medium == 'PhonePe':
            error_response_dict, usersub_obj = subscription_phone_pe_process(
                user_subscription_dict, merchant_subid, merchant_userid,
                subscription, mobile_number, upi, auth_request_id, user_id)

            if error_response_dict:
                custom_response = self.get_error_response(
                        message=error_response_dict.get('message', ''), status="error",
                        errors=[],error_code=error_response_dict.get('error_code', ''),
                        status_code=status.HTTP_400_BAD_REQUEST)
                return custom_response
            
            seriaizer = UserSubscriptionSerializer(usersub_obj)
            data = serializer.data
            
        custom_response = self.get_response(
            data=data,  # Use the data from the default response
            status='success',
            message="User Subscription Initiated",
            status_code=status.HTTP_201_CREATED,  # 201 for successful creation
        )

        self.log_response(custom_response)  # Log the custom response before returning
        return custom_response

    def list(self, request, *args, **kwargs):
        self.log_request(request)  # Log the incoming request

        self.user_subscription_param_ops()
        self.property_order_ops()
        # paginate the result
        count, self.queryset = paginate_queryset(self.request,  self.queryset)

        # Perform the default listing logic
        response = super().list(request, *args, **kwargs)

        if response.status_code == status.HTTP_200_OK:
            # If the response status code is OK (200), it's a successful listing
            custom_response = self.get_response(
                status="success",
                count=count,
                data=response.data,  # Use the data from the default response
                message="User Subscription List",
                status_code=status.HTTP_200_OK,  # 200 for successful listing

            )
        else:
            custom_response = self.get_error_response(message="Validation Error", status="error",
                                                      errors=[],error_code="VALIDATION_ERROR",
                                                      status_code=status.HTTP_400_BAD_REQUEST)

        self.log_response(custom_response)  # Log the custom response before returning
        return custom_response

    @action(detail=False, methods=['POST'], url_path='cancel',
            url_name='cancel', permission_classes=[IsAuthenticated])
    def cancel_subscription(self, request):
        
        user_id = self.request.user.id
        user_sub_id = request.data.get('user_sub')
        payment_medium = request.data.get('payment_medium')
        data = {}
        user_sub_logs = {"api_code":"SUB-CANC", "user_id":user_id} # log
        
        user_sub = UserSubscription.objects.filter(id=user_sub_id).first()
        if not user_sub:
            custom_response = self.get_error_response(
                message="Subscription not found", status="error",
                errors=[],error_code="SUBSCRIPTION_MISSING",
                status_code=status.HTTP_400_BAD_REQUEST)
            return custom_response
        
        user_sub_logs['user_sub_id'] = user_sub.id # log
        user_sub_logs['pg_subid'] = user_sub.pg_subid # log
        
        pg_subid = user_sub.pg_subid

        tnx_id = "%s%d" % ("CANC", user_id)
        tnx_id = get_unique_id_from_time(tnx_id)
        user_sub_logs['tnx_id'] = tnx_id # log

        user_sub.is_cancel_initiated = True
        user_sub.cancel_tnx_id = tnx_id

##        amount = user_sub.total_amount
##        subscription_name = user_sub.idb_sub.name
##        name = self.request.user.name
##        email = self.request.user.email
##        phone = self.request.user.mobile_number
##        
##        params = {"key":settings.PAYU_KEY, "txnid":tnx_id, "amount":amount,
##                  "udf1":"", "udf2":"", "udf3":"", "udf4":"", "udf5":"",
##                  "subscription_name":subscription_name, "firstname": name,
##                  "email":email, "phone":phone
##                  }

        if payment_medium == 'PayU':
            response = subscription_cancel_payu_process(pg_subid, tnx_id)
            data = response.json()

        user_sub.save() # save sunscription with cancellation details

        user_sub_logs['status_response'] = data # log      
        # log entry
        UserSubscriptionLogs.objects.create(**user_sub_logs)
        
        custom_response = self.get_response(
            data=data,  # Use the data from the default response
            status='success',
            message="User Subscription Initiated",
            status_code=status.HTTP_201_CREATED,  # 201 for successful creation
        )

        return custom_response

    @action(detail=False, methods=['POST'], url_path='payu-sucess',
            url_name='payu-sucess', permission_classes=[])
    def subscription_payu_success(self, request):
        user_sub_logs = {"api_code":"MNDT-CLBAK"} # log
        try:
            post_data = request.data
            subscription_data_json = json.dumps(post_data)
            print(subscription_data_json)
            user_sub_logs['status_response'] = subscription_data_json # log

            transaction_id = post_data.get('txnid')
            pg_subid = post_data.get('mihpayid')
            user_sub_logs['pg_subid'] = pg_subid # log
            user_sub_logs['tnx_id'] = transaction_id
            tranx_mode = post_data.get('mode')
            
            mnd_status = post_data.get('status')
            # log
            if mnd_status == "success":
                user_sub_logs['status_code'] = 200
            else:
                user_sub_logs['status_code'] = 400
                
            net_amount_debit = int(post_data.get('net_amount_debit'))
            if tranx_mode=="CC":
                # credit card
                pass

            timezone = pytz.timezone(settings.TIME_ZONE)
            current_date = datetime.now(timezone)
            
            user_sub_obj = UserSubscription.objects.filter(mandate_tnx_id=transaction_id).first()
            if user_sub_obj:
                # for logs
                user_id = user_sub_obj.user.id
                user_subid = user_sub_obj.id
                user_sub_logs['user_id'] = user_id
                user_sub_logs['user_sub_id'] = user_subid
                
                user_sub_obj.last_paid_date = current_date
                subscription_type = user_sub_obj.idb_sub.subscription_type
                if subscription_type == "Monthly":
                    user_sub_obj.next_payment_date = current_date + relativedelta(months=1)
                elif subscription_type == "Yearly":
                    user_sub_obj.next_payment_date = current_date + relativedelta(years=1)
                
                user_sub_obj.pg_subid = pg_subid
                user_sub_obj.transaction_amount = net_amount_debit
                if mnd_status == 'success':
                    user_sub_obj.paid = True
                    user_sub_obj.active = True
                user_sub_obj.save()
                
            custom_response = self.get_response(
                data=subscription_data_json,  # Use the data from the default response
                status='success',
                message="User Subscription Created",
                status_code=status.HTTP_201_CREATED,  # 201 for successful creation
            )
        except Exception as e:
            user_sub_logs['error_message'] = str(e)
            custom_response = self.get_error_response(
                message=str(e), status="error",
                errors=[],error_code="CALLBACK_ERRROR",
                status_code=status.HTTP_400_BAD_REQUEST)

        # create log
        UserSubscriptionLogs.objects.create(**user_sub_logs)   
        return custom_response

    @action(detail=False, methods=['POST'], url_path='payu-payment-response',
            url_name='payu-payment-response', permission_classes=[])
    def payment_payu_response(self, request):
        user_sub_logs = {"api_code":"CMN-CALBAK"}

        try:
            post_data = request.data
            payment_data_json = json.dumps(post_data)
            
            transaction_id = post_data.get('txnid')
            pg_subid = post_data.get('mihpayid')
            user_sub_logs['pg_subid'] = pg_subid # log
            user_sub_logs['tnx_id'] = transaction_id
            user_sub_logs['status_response'] = payment_data_json

            response_status = post_data.get('status')
            # log
            if response_status == "success":
                user_sub_logs['status_code'] = 200
            else:
                user_sub_logs['status_code'] = 400

            user_sub_obj = UserSubscription.objects.filter(
                Q(mandate_tnx_id=transaction_id) | Q(pg_subid=pg_subid)).first()
            print("user sub obj::", user_sub_obj)
            if user_sub_obj:
                user_id = user_sub_obj.user.id
                user_subid = user_sub_obj.id

                user_sub_logs['user_id'] = user_id
                user_sub_logs['user_sub_id'] = user_subid

            custom_response = self.get_response(
                data=payment_data_json,  # Use the data from the default response
                status='success',
                message="Payu Subscription Response",
                status_code=status.HTTP_201_CREATED,  # 201 for successful creation
            )
        except Exception as e:
            user_sub_logs['error_message'] = str(e)
            custom_response = self.get_error_response(
                message=str(e), status="error",
                errors=[],error_code="CALLBACK_ERRROR",
                status_code=status.HTTP_400_BAD_REQUEST)
            
        UserSubscriptionLogs.objects.create(**user_sub_logs)
        
        return custom_response


    @action(detail=False, methods=['POST'], url_path='submit-auth-init/pe-callbackurl',
            url_name='submit-auth-init-pe-callbackurl', permission_classes=[])
    def submit_auth_init_pe_callbackurl(self, request):
        user_sub_logs = {}
        
        try:
            self.log_request(request)
            
            response = request.data.get('response', None)
            if not response:
                custom_response = self.get_error_response(
                    message="Error in Response", status="error",
                    errors=[], error_code="VALIDATION_ERROR",
                    status_code=status.HTTP_400_BAD_REQUEST)
                return custom_response

            data = base64.b64decode(response)
            decoded_data = data.decode('utf-8')
            json_data = json.loads(decoded_data)
            # add log for response json
            user_sub_logs['api_code'] = "MNDT-CLBAK"
            user_sub_logs['status_response'] = json_data if json_data else {}
            if json_data:
                code = json_data.get('code')
                user_sub_logs['status_code'] = 200 if code == "SUCCESS" else 400

                auth_data = json_data.get('data', {})
                pg_subscription_id = auth_data.get('subscriptionDetails', {}).get("subscriptionId", "")
                #pg_subscription_id = "OM2504191131437470597164"
                subscription_state = auth_data.get('subscriptionDetails', {}).get("state", "")
                
                if pg_subscription_id:
                    user_sub_logs["pg_subid"] = pg_subscription_id
                    user_sub = UserSubscription.objects.filter(pg_subid=pg_subscription_id).first()
                    if user_sub:
                        user_sub_logs['user_sub_id'] = user_sub.id
                        user_sub_logs['user_id'] = user_sub.user_id
                        sub_workflow = user_sub.sub_workflow
                        subscription_type = user_sub.idb_sub.subscription_type
                        if sub_workflow == "TRANSACTION":
                            transaction_details = auth_data.get('transactionDetails', {})
                            transaction_amount = transaction_details.get('amount', 0)
                            transaction_state = transaction_details.get('state', None)
                            current_date = datetime.now()
                            if transaction_state == "COMPLETED":
                                user_sub.paid = True
                                user_sub.transaction_amount = transaction_amount
                                user_sub.last_paid_date = current_date
                                if subscription_type == "Monthly":
                                    user_sub.next_payment_date = current_date + relativedelta(months=1)
                                elif subscription_type == "Yearly":
                                    user_sub.next_payment_date = current_date + relativedelta(years=1)
                                user_sub.next_notify_date = user_sub.next_payment_date - relativedelta(days=1)
                                user_sub.sub_start_date = current_date
                                # user_sub.sub_end_date = sub_end_date
                            else:
                                user_sub.paid = False
                                user_sub.transaction_amount = transaction_amount
                                
                        if subscription_state == "ACTIVE":
                            user_sub.active = True
                        else:
                            user_sub.active = False
                        # save the details
                        user_sub.save()
            
        except Exception as e:
            print(e)

        # log entry
        UserSubscriptionLogs.objects.create(**user_sub_logs)

        custom_response = self.get_response(
            data={},  # Use the data from the default response
            status='success',
            message="Mandate response received",
            status_code=status.HTTP_200_OK,
        )
        return custom_response
    

    @action(detail=False, methods=['POST'], url_path='recur-init/pe-callbackurl',
            url_name='recur-init-pe-callbackurl', permission_classes=[])
    def recur_init_pe_callbackurl(self, request):
        recur_init_logs = {}
        trans_dict = {}
        try:
            self.log_request(request)
            
            response = request.data.get('response', None)
            if not response:
                custom_response = self.get_error_response(
                    message="Error in Response", status="error",
                    errors=[], error_code="VALIDATION_ERROR",
                    status_code=status.HTTP_400_BAD_REQUEST)
                return custom_response

            data = base64.b64decode(response)
            decoded_data = data.decode('utf-8')
            json_data = json.loads(decoded_data)

            # log entry
            recur_init_logs['api_code'] = "RECRINIT-CALBAK"
            recur_init_logs['status_response'] = json_data if json_data else {}

            if json_data:
                code = json_data.get('code')
                # log entry
                recur_init_logs['status_code'] = 200 if code == "SUCCESS" else 400

                recur_data = json_data.get('data', {})
                transaction_id = recur_data.get('transactionId')
                notification_state = recur_data.get('notificationDetails', {}).get("state")
                transaction_amount = recur_data.get('notificationDetails', {}).get("amount")
                pg_subscription_id = recur_data.get('subscriptionDetails', {}).get("subscriptionId")
                # log entry
                recur_init_logs['pg_subid'] = pg_subscription_id

                trans_dict['transaction_amount'] = transaction_amount
                trans_dict['callbak_state'] = notification_state

                if pg_subscription_id:
                    user_sub = UserSubscription.objects.filter(pg_subid=pg_subscription_id).first()
                    subscription_type = user_sub.idb_sub.subscription_type
                    user_sub.transaction_amount = transaction_amount
                    # log entry
                    recur_init_logs['user_id'] = user_sub.user.id
                    recur_init_logs['user_sub_id'] = user_sub.id
                    if notification_state == "NOTIFIED":
                        user_sub.paid = True
                        trans_dict['paid'] = True
                        current_date = datetime.now()
                        user_sub.last_paid_date = current_date
                        
                        if subscription_type == "Monthly":
                            user_sub.next_payment_date = current_date + relativedelta(months=1)
                        elif subscription_type == "Yearly":
                            user_sub.next_payment_date = current_date + relativedelta(years=1)    
                        user_sub.next_notify_date = user_sub.next_payment_date - relativedelta(days=1)
                    else:
                        user_sub.paid = False
                        user_sub.active = False
                        
                    user_sub.save()
                    
                # update recurring transaction details    
                update_subrecur_transaction(transaction_id, trans_dict)
                    
        except Exception as e:
            print(e)

        UserSubscriptionLogs.objects.create(**recur_init_logs)

        custom_response = self.get_response(
            data={},  # Use the data from the default response
            status='success',
            message="Recur Init Callback Success",
            status_code=status.HTTP_200_OK,
        )
        return custom_response

    

class RoomTypeViewSet(viewsets.ModelViewSet, StandardResponseMixin, LoggingMixin):
    queryset = RoomType.objects.all()
    serializer_class = RoomTypeSerializer
    permission_classes = [AnonymousCanViewOnlyPermission,]
    http_method_names = ['get', 'post', 'put', 'patch']

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
                message="RoomType Created",
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

        # Get the object to be updated
        instance = self.get_object()

        # Create an instance of your serializer with the request data and the object to be updated
        serializer = self.get_serializer(instance, data=request.data)

        if serializer.is_valid():
            # If the serializer is valid, perform the default update logic
            response = super().update(request, *args, **kwargs)

            # Create a custom response
            custom_response = self.get_response(
                data=response.data,  # Use the data from the default response
                message="RoomType Updated",
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

    def list(self, request, *args, **kwargs):
        self.log_request(request)  # Log the incoming request

        # Perform the default listing logic
        response = super().list(request, *args, **kwargs)

        if response.status_code == status.HTTP_200_OK:
            # If the response status code is OK (200), it's a successful listing
            custom_response = self.get_response(
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


class OccupancyViewSet(viewsets.ModelViewSet, StandardResponseMixin, LoggingMixin):
    queryset = Occupancy.objects.all()
    serializer_class = OccupancySerializer
    permission_classes = [AnonymousCanViewOnlyPermission,]
    http_method_names = ['get', 'post', 'put', 'patch']

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
                message="Occupancy Created",
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

        # Get the object to be updated
        instance = self.get_object()

        # Create an instance of your serializer with the request data and the object to be updated
        serializer = self.get_serializer(instance, data=request.data)

        if serializer.is_valid():
            # If the serializer is valid, perform the default update logic
            response = super().update(request, *args, **kwargs)

            # Create a custom response
            custom_response = self.get_response(
                data=response.data,  # Use the data from the default response
                message="Occupancy Updated",
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

    def list(self, request, *args, **kwargs):
        self.log_request(request)  # Log the incoming request

        # Perform the default listing logic
        response = super().list(request, *args, **kwargs)

        if response.status_code == status.HTTP_200_OK:
            # If the response status code is OK (200), it's a successful listing
            custom_response = self.get_response(
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


class AddressViewSet(viewsets.ModelViewSet, StandardResponseMixin, LoggingMixin):
    queryset = Address.objects.all()
    serializer_class = AddressSerializer
    # permission_classes = [AnonymousCanViewOnlyPermission,]
    http_method_names = ['get', 'post', 'put', 'patch']

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
                message="Occupancy Created",
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

        # Get the object to be updated
        instance = self.get_object()

        # Create an instance of your serializer with the request data and the object to be updated
        serializer = self.get_serializer(instance, data=request.data)

        if serializer.is_valid():
            # If the serializer is valid, perform the default update logic
            response = super().update(request, *args, **kwargs)

            # Create a custom response
            custom_response = self.get_response(
                data=response.data,  # Use the data from the default response
                message="Occupancy Updated",
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

    def list(self, request, *args, **kwargs):
        self.log_request(request)  # Log the incoming request

        # Perform the default listing logic
        response = super().list(request, *args, **kwargs)

        if response.status_code == status.HTTP_200_OK:
            # If the response status code is OK (200), it's a successful listing
            custom_response = self.get_response(
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


class AboutUsViewSet(viewsets.ModelViewSet, StandardResponseMixin, LoggingMixin):
    queryset = AboutUs.objects.all()
    serializer_class = AboutUsSerializer
    permission_classes = [AnonymousCanViewOnlyPermission,]
    http_method_names = ['get', 'post', 'put', 'patch']

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
                message="AboutUs Created",
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

        # Get the object to be updated
        instance = self.get_object()

        # Create an instance of your serializer with the request data and the object to be updated
        serializer = self.get_serializer(instance, data=request.data)

        if serializer.is_valid():
            # If the serializer is valid, perform the default update logic
            response = super().update(request, *args, **kwargs)

            # Create a custom response
            custom_response = self.get_response(
                data=response.data,  # Use the data from the default response
                message="AboutUs Updated",
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

    def list(self, request, *args, **kwargs):
        self.log_request(request)  # Log the incoming request

        # Perform the default listing logic
        response = super().list(request, *args, **kwargs)

        if response.status_code == status.HTTP_200_OK:
            # If the response status code is OK (200), it's a successful listing
            custom_response = self.get_response(
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


class PrivacyPolicyViewSet(viewsets.ModelViewSet, StandardResponseMixin, LoggingMixin):
    queryset = PrivacyPolicy.objects.all()
    serializer_class = PrivacyPolicySerializer
    permission_classes = [AnonymousCanViewOnlyPermission,]
    http_method_names = ['get', 'post', 'put', 'patch']

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
                message="PrivacyPolicy Created",
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

        # Get the object to be updated
        instance = self.get_object()

        # Create an instance of your serializer with the request data and the object to be updated
        serializer = self.get_serializer(instance, data=request.data)

        if serializer.is_valid():
            # If the serializer is valid, perform the default update logic
            response = super().update(request, *args, **kwargs)

            # Create a custom response
            custom_response = self.get_response(
                data=response.data,  # Use the data from the default response
                message="PrivacyPolicy Updated",
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

    def list(self, request, *args, **kwargs):
        self.log_request(request)  # Log the incoming request

        # Perform the default listing logic
        response = super().list(request, *args, **kwargs)

        if response.status_code == status.HTTP_200_OK:
            # If the response status code is OK (200), it's a successful listing
            custom_response = self.get_response(
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


class RefundAndCancellationPolicyViewSet(viewsets.ModelViewSet, StandardResponseMixin, LoggingMixin):
    queryset = RefundAndCancellationPolicy.objects.all()
    serializer_class = RefundAndCancellationPolicySerializer
    permission_classes = [AnonymousCanViewOnlyPermission,]
    http_method_names = ['get', 'post', 'put', 'patch']

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
                message="Refund And Cancellation Policy Created",
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

        # Get the object to be updated
        instance = self.get_object()

        # Create an instance of your serializer with the request data and the object to be updated
        serializer = self.get_serializer(instance, data=request.data)

        if serializer.is_valid():
            # If the serializer is valid, perform the default update logic
            response = super().update(request, *args, **kwargs)

            # Create a custom response
            custom_response = self.get_response(
                data=response.data,  # Use the data from the default response
                message="Refund And Cancellation Policy Updated",
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

    def list(self, request, *args, **kwargs):
        self.log_request(request)  # Log the incoming request

        # Perform the default listing logic
        response = super().list(request, *args, **kwargs)

        if response.status_code == status.HTTP_200_OK:
            # If the response status code is OK (200), it's a successful listing
            custom_response = self.get_response(
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


class TermsAndConditionsViewSet(viewsets.ModelViewSet, StandardResponseMixin, LoggingMixin):
    queryset = TermsAndConditions.objects.all()
    serializer_class = TermsAndConditionsSerializer
    permission_classes = [AnonymousCanViewOnlyPermission,]
    http_method_names = ['get', 'post', 'put', 'patch']

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
                message="Terms And Conditions Created",
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

        # Get the object to be updated
        instance = self.get_object()

        # Create an instance of your serializer with the request data and the object to be updated
        serializer = self.get_serializer(instance, data=request.data)

        if serializer.is_valid():
            # If the serializer is valid, perform the default update logic
            response = super().update(request, *args, **kwargs)

            # Create a custom response
            custom_response = self.get_response(
                data=response.data,  # Use the data from the default response
                message="Terms And Conditions Updated",
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

    def list(self, request, *args, **kwargs):
        self.log_request(request)  # Log the incoming request

        # Perform the default listing logic
        response = super().list(request, *args, **kwargs)

        if response.status_code == status.HTTP_200_OK:
            # If the response status code is OK (200), it's a successful listing
            custom_response = self.get_response(
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


class LegalityViewSet(viewsets.ModelViewSet, StandardResponseMixin, LoggingMixin):
    queryset = Legality.objects.all()
    serializer_class = LegalitySerializer
    permission_classes = [AnonymousCanViewOnlyPermission,]
    http_method_names = ['get', 'post', 'put', 'patch']

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
                message="Legality Created",
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

        # Get the object to be updated
        instance = self.get_object()

        # Create an instance of your serializer with the request data and the object to be updated
        serializer = self.get_serializer(instance, data=request.data)

        if serializer.is_valid():
            # If the serializer is valid, perform the default update logic
            response = super().update(request, *args, **kwargs)

            # Create a custom response
            custom_response = self.get_response(
                data=response.data,  # Use the data from the default response
                message="Legality Updated",
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

    def list(self, request, *args, **kwargs):
        self.log_request(request)  # Log the incoming request

        # Perform the default listing logic
        response = super().list(request, *args, **kwargs)

        if response.status_code == status.HTTP_200_OK:
            # If the response status code is OK (200), it's a successful listing
            custom_response = self.get_response(
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


class CareerViewSet(viewsets.ModelViewSet, StandardResponseMixin, LoggingMixin):
    queryset = Career.objects.all()
    serializer_class = CareerSerializer
    permission_classes = [AnonymousCanViewOnlyPermission,]
    http_method_names = ['get', 'post', 'put', 'patch']

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
                message="Career Created",
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

        # Get the object to be updated
        instance = self.get_object()

        # Create an instance of your serializer with the request data and the object to be updated
        serializer = self.get_serializer(instance, data=request.data)

        if serializer.is_valid():
            # If the serializer is valid, perform the default update logic
            response = super().update(request, *args, **kwargs)

            # Create a custom response
            custom_response = self.get_response(
                data=response.data,  # Use the data from the default response
                message="Career Updated",
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

    def list(self, request, *args, **kwargs):
        self.log_request(request)  # Log the incoming request

        # Perform the default listing logic
        response = super().list(request, *args, **kwargs)

        if response.status_code == status.HTTP_200_OK:
            # If the response status code is OK (200), it's a successful listing
            custom_response = self.get_response(
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


class FAQsViewSet(viewsets.ModelViewSet, StandardResponseMixin, LoggingMixin):
    queryset = FAQs.objects.all()
    serializer_class = FAQsSerializer
    permission_classes = [AnonymousCanViewOnlyPermission,]
    http_method_names = ['get', 'post', 'put', 'patch']

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
                message="FAQs Created",
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

        # Get the object to be updated
        instance = self.get_object()

        # Create an instance of your serializer with the request data and the object to be updated
        serializer = self.get_serializer(instance, data=request.data)

        if serializer.is_valid():
            # If the serializer is valid, perform the default update logic
            response = super().update(request, *args, **kwargs)

            # Create a custom response
            custom_response = self.get_response(
                data=response.data,  # Use the data from the default response
                message="FAQs Updated",
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

    def list(self, request, *args, **kwargs):
        self.log_request(request)  # Log the incoming request

        # Perform the default listing logic
        response = super().list(request, *args, **kwargs)

        if response.status_code == status.HTTP_200_OK:
            # If the response status code is OK (200), it's a successful listing
            custom_response = self.get_response(
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

class CountryDetailsViewSet(viewsets.ModelViewSet, StandardResponseMixin, LoggingMixin):
    queryset = CountryDetails.objects.all()
    serializer_class = CountryDetailsSerializer
    # permission_classes = [IsAuthenticated]
    permission_classes = []
    http_method_names = ['get', 'post', 'put', 'patch', 'delete']

    def list(self, request, *args, **kwargs):
        self.log_request(request)  # Log the incoming request

        # Perform the default listing logic
        response = super().list(request, *args, **kwargs)

        if response.status_code == status.HTTP_200_OK:
            # If the response status code is OK (200), it's a successful listing
            custom_response = self.get_response(
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


    @action(detail=False, methods=['POST'], url_path='populate-data',
            url_name='populate-data')
    def populate_data(self, request):

        print("inside populate data")
        state_list = []
        state_dict = {}
        COUNTRY_API_KEY = settings.COUNTRY_API_KEY

        url = "https://api.data.gov.in/resource/37231365-78ba-44d5-ac22-3deec40b9197?\
api-key={key}&format=json&limit=800".format(key=COUNTRY_API_KEY)

        payload = {}
        headers = {}

        response = requests.request("GET", url, headers=headers, data=payload)

        data = response.json()
        records = data['records']
        for state in records:
            state_code = state['state_code']
            state_name = state['state_name_english']
            district_name = state['district_name_english']
##            print(district_name)
            if state_dict.get(state_name, ''):
                dict_list = state_dict[state_name].get('district_list', [])
                dict_list.append(district_name)
                state_dict[state_name]['district_list'] = dict_list
            else:
                state_dict[state_name] = {'state_code':state_code, 'district_list':[district_name]}
                
        CountryDetails.objects.filter(country_name="India").update(country_details=state_dict)
            
        custom_response = self.get_response(
            data=state_dict,  # Use the data from the default response
            message="Success",
            status_code=status.HTTP_200_OK,  # 200 for successful retrieval
            )
        return custom_response

class UserNotificationViewSet(viewsets.ModelViewSet, StandardResponseMixin, LoggingMixin):
    queryset = UserNotification.objects.all()
    serializer_class = UserNotificationSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ['get', 'post', 'put', 'patch', 'delete']

    def notification_filter_ops(self):
        
        filter_dict = {}
        user_id = None
        
        user_id = self.request.user.id
        filter_dict['user__id'] = user_id
        
        
        # filter 
        is_read = self.request.query_params.get('is_read', None)
        if is_read:
            filter_dict['is_read'] = is_read

        group_name = self.request.query_params.get('group_name', '')
        if group_name:
            filter_dict['group_name'] = group_name

        self.queryset = self.queryset.filter(**filter_dict)



    def partial_update(self, request, *args, **kwargs):
        #self.log_request(request)  # Log the incoming request

        # Get the object to be updated
        instance = self.get_object()

        print("Inside partial update")

        # Create an instance of your serializer with the request data and the object to be updated
        serializer = self.get_serializer(instance, data=request.data, partial=True)

        if serializer.is_valid():
            # If the serializer is valid, perform the default update logic
            response = super().partial_update(request, *args, **kwargs)

            # Create a custom response
            custom_response = self.get_response(
                data=response.data,  # Use the data from the default response
                message="FAQs Updated",
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

        #self.log_response(custom_response)  # Log the custom response before returning
        return custom_response

    @action(detail=False, methods=['GET'], url_path='user-based/retrieve',
            url_name='user-based-retrieve', permission_classes=[IsAuthenticated])
    def get_user_based_notification(self, request, *args, **kwargs):
        #user = request.user
        #self.queryset = self.queryset.filter(user=user)
        #count = self.queryset.count()

        # filter
        self.notification_filter_ops()
        count, self.queryset = paginate_queryset(self.request, self.queryset)

        # Perform the default listing logic
        response = super().list(request, *args, **kwargs)

        if response.status_code == status.HTTP_200_OK:
            # If the response status code is OK (200), it's a successful listing
            custom_response = self.get_response(
                data=response.data,  # Use the data from the default response
                status='success',
                message="List Retrieved",
                count=count,
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

        #self.log_response(custom_response)  # Log the custom response before returning
        return custom_response



class GetDistrictStateView(APIView):
    def get(self, request, query):
        query = query.title()
        for data in DISTRICT_DATA:
            if query == data["state"]:
                return Response({"state": query, "districts": data["districts"]})
            elif query in data["districts"]:
                return Response({"district": query, "state": data["state"]})
        return Response({"error": f"Query '{query}' not found."}, status=404)

class FeatureSubscriptionViewSet(viewsets.ModelViewSet, StandardResponseMixin, LoggingMixin):
    queryset = FeatureSubscription.objects.all()
    serializer_class = FeatureSubscriptionSerializer
    http_method_names = ['get', 'post', 'patch', 'delete']  # Excluding 'put' as requested
    permission_classes_by_action = {
        'create': [IsAuthenticated], 
        'update': [IsAuthenticated],
        'partial_update': [IsAuthenticated],
        'list': [AllowAny], 
        'retrieve': [AllowAny],
        'destroy': [IsAuthenticated]
    }
    
    def get_permissions(self):
        try: 
            return [permission() for permission in self.permission_classes_by_action[self.action]]
        except KeyError: 
            # action is not set return default permission_classes
            return [permission() for permission in self.permission_classes]
    
    def feature_subscription_filter_ops(self):
        filter_dict = {}
        param_dict = self.request.query_params
        
        for key in param_dict:
            param_value = param_dict[key]
            if key in ('is_active', 'type', 'level', 'subscription'):
                filter_dict[key] = param_value
        
        if filter_dict:
            self.queryset = self.queryset.filter(**filter_dict)
    
    def list(self, request, *args, **kwargs):
        self.log_request(request)  # Log the incoming request
        self.feature_subscription_filter_ops()  # Apply filters
        
        response = super().list(request, *args, **kwargs)
        custom_response = self.get_response(
            data=response.data,
            status='success',
            message="Feature Subscriptions Retrieved",
            status_code=status.HTTP_200_OK,
        )
        
        self.log_response(custom_response)
        return custom_response
    
    def retrieve(self, request, *args, **kwargs):
        self.log_request(request)
        
        response = super().retrieve(request, *args, **kwargs)
        custom_response = self.get_response(
            data=response.data,
            status='success',
            message="Feature Subscription Retrieved",
            status_code=status.HTTP_200_OK,
        )
        
        self.log_response(custom_response)
        return custom_response
    
    def create(self, request, *args, **kwargs):
        self.log_request(request)  # Log the incoming request
        title = self.request.data.get('title', '')
        feature_key = self.request.data.get('feature_key', '')
        type_val = self.request.data.get('type', '')
        level = self.request.data.get('level', None)
        
        # Check if a feature with the same title or key already exists for this level and type
        is_feature_exist = self.queryset.filter(
            feature_key__iexact=feature_key, 
            type=type_val,
            level=level,
            is_active=True
        )
        
        if is_feature_exist:
            custom_response = self.get_error_response(
                message="Feature already exists", 
                status="error",
                errors=[],
                error_code="DUPLICATE_FEATURE",
                status_code=status.HTTP_400_BAD_REQUEST
            )
            return custom_response
            
        # Create an instance of the serializer with the request data
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            # If the serializer is valid, perform the default creation logic
            response = super().create(request, *args, **kwargs)
            # Create a custom response
            custom_response = self.get_response(
                data=response.data,  # Use the data from the default response
                status='success',
                message="Feature Subscription Created",
                status_code=status.HTTP_201_CREATED,  # 201 for successful creation
            )
        else:
            error_list = self.custom_serializer_error(serializer.errors)
            custom_response = self.get_error_response(
                message="Validation Error", 
                status="error",
                errors=error_list,
                error_code="VALIDATION_ERROR", 
                status_code=status.HTTP_400_BAD_REQUEST
            )
            return custom_response
            
        self.log_response(custom_response)  # Log the custom response before returning
        return custom_response
    
    def partial_update(self, request, *args, **kwargs):
        self.log_request(request)
        
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        
        if serializer.is_valid():
            serializer.save()
            custom_response = self.get_response(
                data=serializer.data,
                status='success',
                message="Feature Subscription Updated",
                status_code=status.HTTP_200_OK,
            )
        else:
            error_list = self.custom_serializer_error(serializer.errors)
            custom_response = self.get_error_response(
                message="Validation Error", 
                status="error",
                errors=error_list, 
                error_code="VALIDATION_ERROR",
                status_code=status.HTTP_400_BAD_REQUEST
            )
            
        self.log_response(custom_response)
        return custom_response
    
    def destroy(self, request, *args, **kwargs):
        self.log_request(request)
        
        instance = self.get_object()
        instance.delete()
        
        custom_response = self.get_response(
            data={},
            status='success',
            message="Feature Subscription Deleted",
            status_code=status.HTTP_204_NO_CONTENT,
        )
        
        self.log_response(custom_response)
        return custom_response