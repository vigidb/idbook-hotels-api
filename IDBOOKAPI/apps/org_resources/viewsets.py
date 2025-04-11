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
    SubscriptionSerializer
)
from .models import (
    CompanyDetail, AmenityCategory, Amenity, Enquiry, RoomType, Occupancy, Address,
    AboutUs, PrivacyPolicy, RefundAndCancellationPolicy, TermsAndConditions, Legality,
    Career, FAQs, UploadedMedia, CountryDetails, UserNotification, Subscriber, Subscription)

from IDBOOKAPI.utils import paginate_queryset
from IDBOOKAPI.basic_resources import DISTRICT_DATA
from apps.authentication.models import User
import requests, json

#from rest_framework import decorators
from rest_framework.decorators import action
from django.db.models import Q
from django.conf import settings

from apps.authentication.utils import db_utils as auth_db_utils
from apps.authentication.utils.authentication_utils import get_group_based_on_name
from apps.customer.models import Customer

from apps.org_resources.tasks import send_enquiry_email_task
from apps.org_resources.utils.db_utils import (
    is_corporate_email_exist, is_corporate_number_exist)
from IDBOOKAPI.utils import paginate_queryset

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
