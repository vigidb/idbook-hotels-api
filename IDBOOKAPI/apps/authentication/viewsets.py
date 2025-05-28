import traceback

# django import
from django.http import HttpResponse
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.conf import settings
# rest framework import
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated, IsAdminUser
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.generics import (
    CreateAPIView, ListAPIView, GenericAPIView, RetrieveAPIView, UpdateAPIView
)
from IDBOOKAPI.mixins import StandardResponseMixin, LoggingMixin
from IDBOOKAPI.email_utils import (send_otp_email, send_password_forget_email,
                                   email_validation, get_domain)
from IDBOOKAPI.otp_utils import generate_otp
from IDBOOKAPI.utils import get_timediff_in_minutes, validate_mobile_number

from .models import User, UserOtp, Role
from apps.customer.models import Customer
from .serializers import (UserSignupSerializer, LoginSerializer,
                          UserListSerializer, UserRefferalSerializer,
                          BilledUserSerializer)
# from .emails import send_welcome_email

from rest_framework.decorators import action
from rest_framework import viewsets
from django.utils import timezone

from apps.org_managements.utils import get_domain_business_details
from apps.customer.utils import db_utils as customer_db_utils

from apps.authentication.tasks import (
    send_email_task, customer_signup_link_task, send_signup_email_task)

from apps.authentication.utils import (db_utils, authentication_utils)

from IDBOOKAPI.permissions import HasRoleModelPermission
from IDBOOKAPI.utils import paginate_queryset
from django.db import transaction
from apps.booking.models import Booking
from apps.customer.models import Wallet, WalletTransaction
from apps.log_management.models import WalletTransactionLog, BookingPaymentLog, BookingInvoiceLog
from django.db.models import Q

User = get_user_model()


def homepage(request):
    from IDBOOKAPI.settings import BASE_URL as HOST
    return HttpResponse(f"Welcome to APIs server please visit <a href='/api/v1/docs'>{HOST}/api/v1/docs</a> or <a href='/api/v1/docs2'>{HOST}/api/v1/docs2</a> ")


class UserCreateAPIView(viewsets.ModelViewSet, StandardResponseMixin, LoggingMixin):
    queryset = User.objects.all()
    serializer_class = UserSignupSerializer
    http_method_names = ['get', 'post', 'put', 'patch']

    def get_user_with_tokens(self, user):
            
        refresh = RefreshToken.for_user(user)
        data = authentication_utils.user_representation(user, refresh_token = refresh)

        return data


    def create(self, request, *args, **kwargs):
        self.log_request(request)  # Log the incoming request

        email = request.data.get('email', None)
        if email:
            email = email.lower().strip()
        mobile_number = request.data.get('mobile_number', None)
        group_name = request.data.get('group_name', 'B2C-GRP')
        otp = request.data.get('otp', None)
        otp_mobile = request.data.get('otp_mobile', None)
        user = None

        # Check mandatory OTP fields
        errors = []
        if not otp:
            errors.append({"field": "otp", "message": "Email OTP is required"})
        if not otp_mobile:
            errors.append({"field": "otp_mobile", "message": "Mobile OTP is required"})

        if errors:
            return self.get_error_response(
                message="Email or Mobile OTP is missing", status="error",
                errors=errors, error_code="OTP_FIELDS_REQUIRED",
                status_code=status.HTTP_400_BAD_REQUEST)
        accept_term = request.data.get('acceptTerm', None)
        if not accept_term:
            response = self.get_error_response(
                message="Please accept the terms and conditions",
                status="error",
                errors=[{"field": "acceptTerm", "message": "Please accept the terms and conditions"}],
                error_code="TERMS_NOT_ACCEPTED",
                status_code=status.HTTP_400_BAD_REQUEST
            )
            return response

        user_otp = None
        if otp:
            # VERIFY
            user_otp = UserOtp.objects.filter(user_account=email, otp=otp, otp_for='SIGNUP').first()
            if not user_otp:
                response = self.get_error_response(
                    message="Invalid Email OTP", status="error",
                    errors=[], error_code="INVALID_OTP",
                    status_code=status.HTTP_406_NOT_ACCEPTABLE)
                return response

        if otp_mobile:
            mob_otp = UserOtp.objects.filter(
                user_account=mobile_number, otp=otp_mobile, otp_for='SIGNUP').first()
            if not mob_otp:
                response = self.get_error_response(
                    message="Invalid Mobile OTP", status="error",
                    errors=[], error_code="INVALID_OTP",
                    status_code=status.HTTP_406_NOT_ACCEPTABLE)
                return response

        
        
        if email:
            email = email.lower().strip()
            user = User.objects.filter(email=email).first()

        grp, role = authentication_utils.get_group_based_on_name(group_name)
        if not grp or not role:
            response = self.get_error_response(
                message="Group or role doesn't exist", status="error", errors=[],
                error_code="GROUP_ROLE_NOT_EXIST", status_code=status.HTTP_406_NOT_ACCEPTABLE)
            return response

        # check whether existing group and email exist for the sign up type
        if user and group_name:
##            grp_user = authentication_utils.check_email_exist_for_group(email, group_name)
            email_grp_users= db_utils.get_userid_list(email, group=grp)
            if email_grp_users:
                is_role_exist = False
                if group_name == 'B2C-GRP':
                    # check if B2C-CUST role exist for guest user
                    #is_role_exist = usr.roles.filter(id=role.id).exists()
                    is_role_exist = db_utils.is_role_exist(email_grp_users, role)
                else:
                    is_role_exist = True

                if is_role_exist:
                    error_list = [{"field":"email", "message": "Email already exists"}]
                    response = self.get_error_response(message="Signup Failed", status="error",
                                                        errors=error_list,error_code="VALIDATION_ERROR",
                                                        status_code=status.HTTP_401_UNAUTHORIZED)
                    self.log_response(response)  # Log the response before returning
                    return response

        # check email exist for missing group name
        if user and not group_name:
            error_list = [{"field":"email", "message": "Email already exists."}]
            response = self.get_error_response(message="Signup Failed", status="error",
                                                errors=error_list,error_code="VALIDATION_ERROR",
                                                status_code=status.HTTP_401_UNAUTHORIZED)
            self.log_response(response)  # Log the response before returning
            return response

##        grp, role = authentication_utils.get_group_based_on_name(group_name)

##        if not grp or not role:
##            response = self.get_error_response(
##                message="Group or role doesn't exist", status="error", errors=[],
##                error_code="GROUP_ROLE_NOT_EXIST", status_code=status.HTTP_406_NOT_ACCEPTABLE)
##            return response

        if mobile_number:
##            check_mobile_existing_user = authentication_utils.check_mobile_exist_for_group(mobile_number, grp)
            mobile_grp_users = db_utils.get_userid_list(mobile_number, group=grp)
            if mobile_grp_users:
                is_role_exist = False
                if group_name == 'B2C-GRP':
                    # check if B2C-CUST role exist for guest user
                    is_role_exist = db_utils.is_role_exist(mobile_grp_users, role)
                else:
                    is_role_exist = True

                if is_role_exist:
                    response = self.get_error_response(
                        message="Mobile already exist", status="error", errors=[],
                        error_code="MOBILE_EXIST", status_code=status.HTTP_406_NOT_ACCEPTABLE)
                    return response
            
                
            
        if user:
            serializer = self.get_serializer(user, data=request.data, partial=True)
        else:
            serializer = self.get_serializer(data=request.data)
            
        #serializer = self.get_serializer(data=request.data)

        if serializer.is_valid():
            if not user:
                user = serializer.save()
                customer_id = user.id
                # save customer profile with user id
                Customer.objects.create(user_id=customer_id, active=True)
            else:
                user = serializer.save()
                
            
##            # set groups and roles
##            grp = db_utils.get_group_by_name('B2C-GRP')
##            role = db_utils.get_role_by_name('B2C-CUST')
##
            if grp:
                user.groups.add(grp)
            if role:
                user.roles.add(role)
            user.default_group = group_name
            user.email_verified = True
            user.mobile_verified = True
            user.save()
            authentication_utils.add_signup_bonus(user, group_name, role)


##            user = authentication_utils.add_group_based_on_signup(user, group_name)
            # userlist_serializer = UserListSerializer(user)
            
            # send welcome email
            send_signup_email_task.apply_async(args=[user.get_full_name(), [user.email]])
            # generate token
            refresh = RefreshToken.for_user(user)
            # user representation
            data = authentication_utils.user_representation(user, refresh_token = refresh)

            if user.email:
                db_utils.reset_otp_counter(user.email)
            if user.mobile_number:
                db_utils.reset_otp_counter(user.mobile_number)

            response = self.get_response(
                data=data,
                status="success",
                message="Signup successful",
                status_code=status.HTTP_200_OK,
                )
            self.log_response(response)  # Log the response before returning
            return response
        else:
            error_list = []
            errors = serializer.errors
            for field_name, field_errors in serializer.errors.items():
                for ferror in field_errors:
                    error_list.append({"field":field_name, "message": ferror})

            response = self.get_error_response(message="Signup Failed", status="error",
                                                    errors=error_list,error_code="VALIDATION_ERROR",
                                                    status_code=status.HTTP_401_UNAUTHORIZED)
            self.log_response(response)  # Log the response before returning
            return response

        
    @action(detail=False, methods=['POST'], url_path='customer/signup-link', url_name='customer-signup-link',
            permission_classes=[IsAuthenticated])
    def customer_signup_link(self, request):
        company_user = request.user
        email = request.data.get('email', '')
        gender = request.data.get('gender', '')
        mobile_number = request.data.get('mobile_number', '')
        name = request.data.get('name', '')
        employee_id = request.data.get('employee_id', '')
        group_name = request.data.get('group_name', 'DEFAULT')
        department = request.data.get('department', '')
        
        company_id = company_user.company_id

        if not company_id:
            response = self.get_error_response(message="The user is not associated with any company.", status="error",
                                               errors=[], error_code="COMPANY_MISSING",
                                               status_code=status.HTTP_401_UNAUTHORIZED)
            return response
            
        
        user = User.objects.filter(email=email).first()
        if not user:
            user = User.objects.create(email=email, company_id=company_id, mobile_number=mobile_number, name=name)
            customer = customer_db_utils.create_customer_signup_entry(user, added_user=company_user, gender=gender,
                                                             employee_id=employee_id, group_name=group_name,
                                                             department=department)
        else:
            customer = customer_db_utils.check_customer_exist(user.id)
            if not customer:
                customer = customer_db_utils.create_customer_signup_entry(user, added_user=company_user, gender=gender,
                                                                 employee_id=employee_id, group_name=group_name,
                                                                 department=department)
            #user.category = 'CL-CUST'
            user.company_id = company_id
            user.save()

        refresh = RefreshToken.for_user(user)
        customer_signup_token = str(refresh.access_token)

        customer_signup_link = f"{settings.FRONTEND_URL}/signup-link/?token={customer_signup_token}&email={email}"
        print(customer_signup_link)
        customer_signup_link_task.apply_async(args=[customer_signup_link, name, [email]])

        response = self.get_response(
            status="success",
            message="If the provided email exists, a sign up link has been sent to your employee email address.",
            status_code=status.HTTP_200_OK,
        )
        return response

    @action(detail=False, methods=['POST'], url_path='customer/signup-link/process', url_name='customer-signup-link-process',
            permission_classes=[IsAuthenticated])
    def customer_signup_link_process(self, request):
        user = request.user
        name = request.data.get('name')
        email = request.data.get('email')
        password = request.data.get('password', '')
        mobile_number = request.data.get('mobile_number', '')

        token_email = user.email
        if not token_email == email:
            response = self.get_error_response(message="Email Mismatch", status="error",
                                               errors=[], error_code="EMAIL_MISMATCH",
                                               status_code=status.HTTP_401_UNAUTHORIZED)
            return response

        user.name = name
        if password:
            user.set_password(password)
        user.category = 'CL-CUST'
        user.mobile_number = mobile_number
        user.default_group = 'CORPORATE-GRP'
        user.save()

        grp = db_utils.get_group_by_name('CORPORATE-GRP')
        role = db_utils.get_role_by_name('CORP-EMP')

        if grp:
            user.groups.add(grp)
        if role:
            user.roles.add(role)

##        profile_picture = ''
##        customer_profile = user.customer_profile
##        if user.customer_profile:
##            profile_picture = customer_profile.profile_picture
##            employee_id = customer_profile.employee_id
##
##
##        user_data = {'id': user.id,
##                     'mobile_number': user.mobile_number if user.mobile_number else '',
##                     'email': user.email if user.email else '',
##                     'name': user.get_full_name(),
##                     'category': user.category,
##                     'roles': [],
##                     'permissions': []}
            
        refresh = RefreshToken.for_user(user)
        data = authentication_utils.user_representation(user, refresh_token = refresh)

##        data = {'refreshToken': str(refresh),
##                'accessToken': str(refresh.access_token),
##                'expiresIn': 0,
##                'user': user_data,
##                }

        response = self.get_response(
            data = data,
            status="success",
            message="Signup Process Success.",
            status_code=status.HTTP_201_CREATED)
        return response
        

    @action(detail=False, methods=['POST'], url_path='customer', url_name='customer-signup',
            permission_classes=[IsAuthenticated])
    def company_based_customer_signup(self, request):
        user = request.user
        user_id = user.id
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid() and user_id:
            user_serializer = serializer.save()
            user_serializer.company_id = user.company_id
            user_serializer.category = 'CL-CUST'
            user_serializer.save()
            
            customer_id = user_serializer.id
            Customer.objects.create(user_id=customer_id, added_user=user)
    

            data = {'user': serializer.data}
            response = self.get_response(
                data=data,
                status="success",
                message="Signup successful",
                status_code=status.HTTP_200_OK
                )
            return response
        else:
            error_list = []
            errors = serializer.errors
            for field_name, field_errors in serializer.errors.items():
                for ferror in field_errors:
                    error_list.append({"field":field_name, "message": ferror})

            response = self.get_error_response(message="Signup Failed", status="error",
                                               errors=error_list,error_code="VALIDATION_ERROR",
                                               status_code=status.HTTP_401_UNAUTHORIZED)
            return response

    @action(detail=False, methods=['POST'], url_path='email/generate-otp',
            url_name='generate-email-otp')
    def generate_email_otp(self, request):
        """Need to delete the code"""
        try:
            to_email = request.data.get('email', '')
            valid = email_validation(to_email)
            if not valid:
                response = self.get_error_response(message="Invalid Email", status="error",
                                                   errors=[], error_code="INVALID_EMAIL",
                                                   status_code=status.HTTP_406_NOT_ACCEPTABLE)
                return response

            # Check if user has exceeded OTP generation limit
            can_generate, error_message = authentication_utils.check_otp_generation_limit(to_email)
            if not can_generate:
                response = self.get_error_response(
                    message=error_message,
                    status="error", errors=[], error_code="OTP_LIMIT_EXCEEDED",
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS)
                return response
            
            # generate otp
            otp = generate_otp(no_digits=4)
            # delete any previous otp for the user account
            # UserOtp.objects.filter(user_account=to_email).delete()
            # save otp
            # Use the same process as in the working example
            authentication_utils.email_generate_otp_process(otp, to_email, 'PASSWORD_RESET')
            # send email
            # send_otp_email(otp, [to_email])
            # send_email_task.apply_async(args=[otp, [to_email]])
            
            response = self.get_response(data={}, status="success",
                                         message="OTP Success",
                                         status_code=status.HTTP_200_OK)
        except Exception as e:
            print(e)
            response = self.get_error_response(message="Internal server error. Please try again later.",
                                               status="error",
                                               errors=[],error_code="INTERNAL_SERVER_ERROR",
                                               status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        return response

    
    

    @action(detail=False, methods=['POST'], url_path='buser/email-otp',
            url_name='buser-email-otp-signup')
    def email_otp_based_buser_signup(self, request):
        try:
            email = request.data.get('email', '')
            mobile_number = request.data.get('mobile_number', '')
            name = request.data.get('name', '')
            otp = request.data.get('otp', None)
            business_id, category = "", ""
            referred_code = request.data.get('referred_code', '')

            valid = email_validation(email)
            if not valid:
                response = self.get_error_response(message="Invalid Email", status="error",
                                                   errors=[], error_code="INVALID_EMAIL",
                                                   status_code=status.HTTP_406_NOT_ACCEPTABLE)
                return response
            if not otp:
                response = self.get_error_response(message="OTP Missing", status="error",
                                                   errors=[], error_code="OTP_MISSING",
                                                   status_code=status.HTTP_406_NOT_ACCEPTABLE)
                return response

            
            
            user_otp = UserOtp.objects.filter(user_account=email, otp=otp).first()
            if user_otp:
                current_time = timezone.now()
                timediff = current_time - user_otp.created
                timediff_in_minutes = timediff.total_seconds()/60

                if timediff_in_minutes >= settings.OTP_EXPIRY_MIN:
                    response = self.get_error_response(message="OTP Expired", status="error",
                                                   errors=[], error_code="OTP_EXPIRED",
                                                   status_code=status.HTTP_406_NOT_ACCEPTABLE)
                else:
                    check_existing_user = User.objects.filter(email=email).first()
                    if check_existing_user:
                        data = self.get_user_with_tokens(check_existing_user)
                        response = self.get_response(data=data, status="success",
                                                     message="Login successful",
                                                     status_code=status.HTTP_200_OK)
                    else:
                        domain_name = get_domain(email)
                        if domain_name == 'idbookhotels.com':
                            bdetails = get_domain_business_details(domain_name)
                            if bdetails:
                                business_id = bdetails.id
                        if business_id:
                            category = "B-CUST"
                            new_user = User.objects.create(name=name, email=email, mobile_number=mobile_number,
                                                           business_id=business_id, category=category,
                                                           referred_code=referred_code, default_group='B2C-GRP')
                        else:
                            category = "B-CUST"
                            new_user = User.objects.create(name=name, email=email,
                                                           mobile_number=mobile_number,
                                                           category=category, referred_code=referred_code,
                                                           default_group='B2C-GRP')
                        # set groups and roles
                        grp = db_utils.get_group_by_name('B2C-GRP')
                        role = db_utils.get_role_by_name('B2C-CUST')

                        if grp:
                            new_user.groups.add(grp)
                        if role:
                            new_user.roles.add(role)
                            
                        data = self.get_user_with_tokens(new_user)
                        response = self.get_response(data=data, status="success",
                                                     message="Signup successful",
                                                     status_code=status.HTTP_200_OK)
            else:
                response = self.get_error_response(message="Invalid Credentials", status="error",
                                                   errors=[], error_code="INVALID_CREDENTIALS",
                                                   status_code=status.HTTP_406_NOT_ACCEPTABLE)
        except Exception as e:
            print(e)
            response = self.get_error_response(message="Internal server error. Please try again later.",
                                               status="error",
                                               errors=[],error_code="INTERNAL_SERVER_ERROR",
                                               status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
        return response
        


class LoginAPIView(GenericAPIView, StandardResponseMixin, LoggingMixin):
    serializer_class = LoginSerializer

    def post(self, request):
        self.log_request(request)  # Log the incoming request

        username = request.data.get('username', '')
        # If it's an email, normalize it to lowercase
        if "@" in username:
            request.data['username'] = username.lower()
        serializer = self.get_serializer(data=request.data)
        # serializer.is_valid(raise_exception=True)
        if serializer.is_valid():
            user = serializer.validated_data['user']
            refresh = RefreshToken.for_user(user)
##            data = [serializer.data,
##                    {
##                        'refresh': str(refresh),
##                        'access': str(refresh.access_token)
##                     }
##                    ]
##            data = {'refreshToken': str(refresh),
##                    'accessToken': str(refresh.access_token),
##                    'expiresIn': 0,
##                    'user': serializer.data,
##                    }

            data = authentication_utils.user_representation(user, refresh_token=refresh)
            # Reset OTP counter after successful login
            if user.email:
                db_utils.reset_otp_counter(user.email)
            if user.mobile_number:
                db_utils.reset_otp_counter(user.mobile_number)
            
            response = self.get_response(
                data=data,
                status="success",
                message="Login successful",
                status_code=status.HTTP_200_OK,
                )
            self.log_response(response)  # Log the response before returning
            return response
        else:
            error_list = []
            message, error_code = "", ""
            errors = serializer.errors
            for field_name, field_errors in serializer.errors.items():
                for ferror in field_errors:
                    if ferror == 'account_inactive':
                        message = "Your account is locked or inactive. Please contact support."
                        ferror = message
                        error_code = "ACCOUNT_INACTIVE"
                    elif ferror == 'credentials_error':
                        message = "Invalid email or password"
                        ferror = message
                        error_code = "INVALID_CREDENTIALS"
                    else:
                        message = ferror
                        error_code = "INVALID_CREDENTIALS"
                    error_list.append({"field":field_name, "message": ferror})

            response = self.get_error_response(message=message, status="error",
                                                    errors=error_list,error_code=error_code,
                                                    status_code=status.HTTP_401_UNAUTHORIZED)
##            response = self.get_response(
##                data=[serializer.data],
##                message=errors['non_field_errors'][0],
##                status_code=status.HTTP_401_UNAUTHORIZED,
##                is_error=True)
            self.log_response(response)  # Log the response before returning
            return response


class LogoutAPIView(GenericAPIView, StandardResponseMixin, LoggingMixin):
    permission_classes = (IsAuthenticated,)

    def post(self, request):
        self.log_request(request)  # Log the incoming request
        refresh_token = request.data.get('refresh_token')

        if refresh_token:
            try:
                token = RefreshToken(refresh_token)
                token.blacklist()
            except Exception:
                response = self.get_response(
                    message="Something went wrong",
                    status_code=status.HTTP_400_BAD_REQUEST,
                    is_error=True)
                self.log_response(response)  # Log the response before returning
                return response
        response = self.get_response(
            message="Successfully logged out",
            status_code=status.HTTP_200_OK,
            )
        self.log_response(response)  # Log the response before returning
        return response

class OtpBasedUserEntryAPIView(viewsets.ModelViewSet, StandardResponseMixin, LoggingMixin):
    queryset = User.objects.all()
    serializer_class = UserSignupSerializer
    http_method_names = ['get', 'post', 'put', 'patch']
    
    @action(detail=False, methods=['POST'], url_path='signup',
            url_name='otp-signup')
    def otp_based_user_signup(self, request):
        
        email = request.data.get('email', '')
        mobile_number = request.data.get('mobile_number', '')
        name = request.data.get('name', '')
        otp = request.data.get('otp', None)
        referred_code = request.data.get('referred_code', '')
        group_name = request.data.get("group_name", 'B2C-GRP')

        valid = email_validation(email)
        if not valid:
            response = self.get_error_response(message="Invalid Email", status="error",
                                               errors=[], error_code="INVALID_EMAIL",
                                               status_code=status.HTTP_406_NOT_ACCEPTABLE)
            return response
        if not otp:
            response = self.get_error_response(message="OTP Missing", status="error",
                                               errors=[], error_code="OTP_MISSING",
                                               status_code=status.HTTP_406_NOT_ACCEPTABLE)
            return response
        is_mb_valid = validate_mobile_number(mobile_number)
        if not is_mb_valid:
            response = self.get_error_response(message="Invalid Mobile Number", status="error",
                                               errors=[], error_code="INVALID_NUMBER",
                                               status_code=status.HTTP_406_NOT_ACCEPTABLE)
            return response

        user_otp = db_utils.get_user_otp_details(email, mobile_number, otp)
        # user_otp = UserOtp.objects.filter(user_account=email, otp=otp).first()
        if not user_otp:
            response = self.get_error_response(
                message="Invalid Credentials", status="error",
                errors=[], error_code="INVALID_CREDENTIALS",
                status_code=status.HTTP_406_NOT_ACCEPTABLE)
            return response

        # check whether otp expired or not
        current_time = timezone.now()
        timediff = current_time - user_otp.created
        timediff_in_minutes = timediff.total_seconds()/60

        if timediff_in_minutes >= settings.OTP_EXPIRY_MIN:
            response = self.get_error_response(message="OTP Expired", status="error",
                                           errors=[], error_code="OTP_EXPIRED",
                                           status_code=status.HTTP_406_NOT_ACCEPTABLE)
            return response

        # check whether email already exist or not
        check_existing_user = User.objects.filter(email=email).first()
        if check_existing_user:
            response = self.get_error_response(
                message="Email already exist", status="error", errors=[],
                error_code="EMAIL_EXIST", status_code=status.HTTP_406_NOT_ACCEPTABLE)
            return response

        # group and roles
        grp, role = authentication_utils.get_group_based_on_name(group_name)
        if not grp or not role:
            response = self.get_error_response(
                message="Group or role doesn't exist", status="error", errors=[],
                error_code="GROUP_ROLE_NOT_EXIST", status_code=status.HTTP_406_NOT_ACCEPTABLE)
            return response

        #check whether mobile already exist or not
        check_mobile_existing_user = User.objects.filter(mobile_number=mobile_number, groups=grp).first()
        if check_mobile_existing_user:
            response = self.get_error_response(
                message="Mobile already exist", status="error", errors=[],
                error_code="MOBILE_EXIST", status_code=status.HTTP_406_NOT_ACCEPTABLE)
            return response
            

        # create user
        new_user = User.objects.create(
            name=name, email=email, mobile_number=mobile_number,
            referred_code=referred_code, default_group=group_name,
            email_verified=True)
        Customer.objects.create(user_id=new_user.id, active=True)
        
##        # set groups and roles
##        grp = db_utils.get_group_by_name('B2C-GRP')
##        role = db_utils.get_role_by_name('B2C-CUST')

        if grp:
            new_user.groups.add(grp)
        if role:
            new_user.roles.add(role)
            
        # data = self.get_user_with_tokens(new_user)
        
        data = authentication_utils.generate_refresh_token(new_user)
        response = self.get_response(data=data, status="success",
                                     message="Signup successful",
                                     status_code=status.HTTP_200_OK)
        return response
    

    @action(detail=False, methods=['POST'], url_path='login',
            url_name='otp-login')
    def otp_based_user_login(self, request):

        username = request.data.get('username', '')
        if "@" in username:
            username = username.lower()
        user_id = request.data.get('user_id', None)
        otp = request.data.get('otp', None)
        group_name = request.data.get("group_name", 'B2C-GRP')

        if not username:
            response = self.get_error_response(
                message="Missing username", status="error",
                errors=[], error_code="INVALID_PARAM",
                status_code=status.HTTP_406_NOT_ACCEPTABLE)
            return response

        # Check if user has exceeded login attempt limit
        can_attempt, error_message = authentication_utils.check_login_attempt_limit(username)
        if not can_attempt:
            response = self.get_error_response(
                message=error_message,
                status="error", errors=[], error_code="LOGIN_LIMIT_EXCEEDED",
                status_code=status.HTTP_429_TOO_MANY_REQUESTS)
            return response
        
        # Increment login attempts before processing
        db_utils.increment_login_attempts(username)

        # get the otp details
        user_otp = UserOtp.objects.filter(user_account=username, otp=otp, otp_for='LOGIN').first()
        if not user_otp:
            response = self.get_error_response(
                message="Invalid Credentials", status="error",
                errors=[], error_code="INVALID_CREDENTIALS",
                status_code=status.HTTP_406_NOT_ACCEPTABLE)
            return response
            
        # get the time difference
        current_time = timezone.now()
        timediff_in_minutes = get_timediff_in_minutes(
            user_otp.created, current_time)

        if timediff_in_minutes >= settings.OTP_EXPIRY_MIN:
            response = self.get_error_response(message="OTP Expired", status="error",
                                               errors=[], error_code="OTP_EXPIRED",
                                               status_code=status.HTTP_406_NOT_ACCEPTABLE)
            return response

        grp, role = authentication_utils.get_group_based_on_name(group_name)
        if not grp:
            response = self.get_error_response(
                message="Group doesn't exist", status="error", errors=[],
                error_code="GROUP_NOT_EXIST", status_code=status.HTTP_406_NOT_ACCEPTABLE)
            return response

##        user_detail = db_utils.get_user_details(user_id, username)
        user_detail = db_utils.get_group_based_user_details(grp, username)
        if not user_detail:
            response = self.get_error_response(
                message="Invalid user details", status="error",
                errors=[], error_code="INVALID_CREDENTIALS",
                status_code=status.HTTP_406_NOT_ACCEPTABLE)
            return response
        user_detail.default_group = group_name
        user_detail.save()
        db_utils.reset_otp_counter(username)
        data = authentication_utils.generate_refresh_token(user_detail)
        response = self.get_response(data=data, status="success",
                                     message="Login successful",
                                     status_code=status.HTTP_200_OK)
        return response

    @action(detail=False, methods=['POST'], url_path='generate-otp',
            url_name='generate-otp')
    def generate_otp(self, request):
        try:
            username = request.data.get('username', None)
            otp_for = request.data.get('otp_for', None)
            group_name = request.data.get('group_name', '')
            if username and '@' in username:
                username = username.lower()
            
            if not username:
                response = self.get_error_response(message="Missing username", status="error",
                                                   errors=[], error_code="INVALID_PARAM",
                                                   status_code=status.HTTP_406_NOT_ACCEPTABLE)
                return response

            if not otp_for:
                response = self.get_error_response(message="Missing otp_for", status="error",
                                                   errors=[], error_code="INVALID_PARAM",
                                                   status_code=status.HTTP_406_NOT_ACCEPTABLE)
                return response

            
            # check whether user name is based on email
            # or mobile number
            is_mb_valid = validate_mobile_number(username)
            if is_mb_valid:
                medium_type = 'mobile'
            else:
                is_email_valid = email_validation(username)
                if is_email_valid:
                    medium_type = 'email'
                else:
                    response = self.get_error_response(message="Invalid Username", status="error",
                                                   errors=[], error_code="INVALID_USERNAME",
                                                   status_code=status.HTTP_406_NOT_ACCEPTABLE)
                    return response
            grp = None
            if group_name:
                # group and roles
                grp, role = authentication_utils.get_group_based_on_name(group_name)
                if not grp or not role:
                    response = self.get_error_response(
                        message="Group or role doesn't exist", status="error", errors=[],
                        error_code="GROUP_ROLE_NOT_EXIST", status_code=status.HTTP_406_NOT_ACCEPTABLE)
                    return response

            user_objs = db_utils.get_userid_list(username, group=grp)
            
            # allow B2C-GRP sign up for guest user
            is_role_exist = False
            if group_name == 'B2C-GRP':
                # check if B2C-CUST role exist for guest user
                is_role_exist = db_utils.is_role_exist(user_objs, role)
            else:
                if user_objs:
                    is_role_exist = True
                
                
            if otp_for == 'LOGIN':
                if not user_objs:
                    response = self.get_error_response(
                        message="Invalid User Credentials!",
                        status="error", errors=[], error_code="MISSING_USERNAME",
                        status_code=status.HTTP_406_NOT_ACCEPTABLE)
                    return response
            elif otp_for == 'SIGNUP':
                if is_role_exist:
                    response = self.get_error_response(
                        message=f"User {medium_type} is already associated with the account!",
                        status="error", errors=[], error_code="USERNAME_DUPLICATE",
                        status_code=status.HTTP_406_NOT_ACCEPTABLE)
                    return response
            
            # Check if user has exceeded OTP generation limit
            can_generate, error_message = authentication_utils.check_otp_generation_limit(username)
            if not can_generate:
                response = self.get_error_response(
                    message=error_message,
                    status="error", errors=[], error_code="OTP_LIMIT_EXCEEDED",
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS)
                return response

            # generate otp
            otp = generate_otp(no_digits=4)

            if medium_type == 'email':
                authentication_utils.email_generate_otp_process(otp, username, otp_for)
            elif medium_type == 'mobile':
                authentication_utils.mobile_generate_otp_process(otp, username, otp_for)
            
            data = {'user_list': user_objs}
            response = self.get_response(data=data, status="success",
                                         message="OTP Success",
                                         status_code=status.HTTP_200_OK)
        except Exception as e:
            print(traceback.format_exc())
            print(e)
            response = self.get_error_response(message="Internal server error. Please try again later.",
                                               status="error",
                                               errors=[],error_code="INTERNAL_SERVER_ERROR",
                                               status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        return response


    @action(detail=False, methods=['POST'], url_path='verify-otp',
            url_name='verify-otp')
    def verify_otp(self, request):

        username = request.data.get('username', '')
        otp = request.data.get('otp', None)
        otp_for = request.data.get('otp_for', None)

        if not username:
            response = self.get_error_response(message="Missing username", status="error",
                                               errors=[], error_code="INVALID_PARAM",
                                               status_code=status.HTTP_406_NOT_ACCEPTABLE)
            return response

        if not otp_for:
            response = self.get_error_response(message="Missing otp_for", status="error",
                                               errors=[], error_code="INVALID_PARAM",
                                               status_code=status.HTTP_406_NOT_ACCEPTABLE)
            return response

        can_attempt, error_message = authentication_utils.check_verify_attempt_limit(username)
        if not can_attempt:
            response = self.get_error_response(
                message=error_message,
                status="error", errors=[], error_code="VERIFY_LIMIT_EXCEEDED",
                status_code=status.HTTP_429_TOO_MANY_REQUESTS)
            return response
        
        # Increment verification attempts before processing
        db_utils.increment_verify_attempts(username)
        
        # get the otp details
        user_otp = UserOtp.objects.filter(user_account=username, otp=otp, otp_for=otp_for).first()
        if not user_otp:
            response = self.get_error_response(
                message="Invalid Credentials", status="error",
                errors=[], error_code="INVALID_CREDENTIALS",
                status_code=status.HTTP_406_NOT_ACCEPTABLE)
            return response
            
        # get the time difference
        current_time = timezone.now()
        timediff_in_minutes = get_timediff_in_minutes(
            user_otp.created, current_time)

        if timediff_in_minutes >= settings.OTP_EXPIRY_MIN:
            response = self.get_error_response(message="OTP Expired", status="error",
                                               errors=[], error_code="OTP_EXPIRED",
                                               status_code=status.HTTP_406_NOT_ACCEPTABLE)
            return response

        data = {}
        if otp_for == 'VERIFY-GUEST':
            grp, role = authentication_utils.get_group_based_on_name("B2C-GRP")
            if not grp:
                response = self.get_error_response(
                    message="Group doesn't exist", status="error", errors=[],
                    error_code="GROUP_NOT_EXIST", status_code=status.HTTP_406_NOT_ACCEPTABLE)
                return response

            user_detail = db_utils.get_group_based_user_details(grp, username)
            if user_detail:
                data = authentication_utils.generate_refresh_token(user_detail)

        
        db_utils.reset_otp_counter(username)
        response = self.get_response(data=data, status="success",
                                     message="Otp Verification Success",
                                     status_code=status.HTTP_200_OK)
        return response

        

    


class PasswordProcessViewSet(viewsets.ModelViewSet, StandardResponseMixin, LoggingMixin):
    queryset = User.objects.all()
    serializer_class = UserSignupSerializer

    @action(detail=False, methods=['POST'], url_path='otp-reset', url_name='password-otp-reset',
            permission_classes=[])
    def otp_based_password_reset(self, request):
        email = request.data.get('email', '')
        password = request.data.get('password', None)
        otp = request.data.get('otp', None)
        
        valid = email_validation(email)
        if not valid:
            response = self.get_error_response(message="Invalid Email", status="error",
                                               errors=[], error_code="INVALID_EMAIL",
                                               status_code=status.HTTP_406_NOT_ACCEPTABLE)
            return response
        
        if not otp:
            response = self.get_error_response(message="OTP Missing", status="error",
                                               errors=[], error_code="OTP_MISSING",
                                               status_code=status.HTTP_406_NOT_ACCEPTABLE)
            return response

        if not password:
            response = self.get_error_response(message="Password Missing", status="error",
                                               errors=[], error_code="PASSWORD_MISSING",
                                               status_code=status.HTTP_406_NOT_ACCEPTABLE)
            return response

            
        # Check if user has exceeded password reset attempt limit
        can_attempt, error_message = authentication_utils.check_pwd_reset_attempt_limit(email)
        if not can_attempt:
            response = self.get_error_response(
                message=error_message,
                status="error", errors=[], error_code="PWD_RESET_LIMIT_EXCEEDED",
                status_code=status.HTTP_429_TOO_MANY_REQUESTS)
            return response
        
        # Increment password reset attempts before processing
        db_utils.increment_pwd_reset_attempts(email)

        user_otp = UserOtp.objects.filter(user_account=email, otp=otp).first()
        print(user_otp)

        if not user_otp:
            response = self.get_error_response(message="Invalid Credentials", status="error",
                                               errors=[], error_code="INVALID_CREDENTIALS",
                                               status_code=status.HTTP_406_NOT_ACCEPTABLE)
            return response
        
        current_time = timezone.now()
        timediff = current_time - user_otp.created
        timediff_in_minutes = timediff.total_seconds()/60

        if timediff_in_minutes >= settings.OTP_EXPIRY_MIN:
            response = self.get_error_response(message="OTP Expired", status="error",
                                           errors=[], error_code="OTP_EXPIRED",
                                           status_code=status.HTTP_406_NOT_ACCEPTABLE)
            return response

        user = User.objects.filter(email=email).first()
        if not user:
            response = self.get_error_response(message="User Not Found", status="error",
                                               errors=[], error_code="USER_MISSING",
                                               status_code=status.HTTP_406_NOT_ACCEPTABLE)
            return response
            
        
        user.set_password(password)
        user.save()
        db_utils.reset_otp_counter(email)
        response = self.get_response(
            data={}, status="success", message="Password has been successfully reset. Please login",
            status_code=status.HTTP_201_CREATED,
            )
        return response

    @action(detail=False, methods=['POST'], url_path='profile-reset', url_name='password-otp-reset',
            permission_classes=[IsAuthenticated])
    def profile_password_reset(self, request):
        user = request.user
        password = request.data.get('password', '')
        old_password = request.data.get('old_password', '')
        token = request.auth

        if '' in (user, password, old_password):
            response = self.get_error_response(
                message="Missing Fields", status="error", errors=[],
                        error_code="INVALID_FIELDS", status_code=status.HTTP_406_NOT_ACCEPTABLE)
            return response

        
        try:
            user = User.objects.get(id=user.id)
            
            if not user.check_password(old_password):
                response = self.get_error_response(
                    message="Invalid Password", status="error", errors=[],
                    error_code="INVALID_PASSWORD", status_code=status.HTTP_401_UNAUTHORIZED)
                
                return response
                
            user.set_password(password)
            user.save()

            response = self.get_response(
                data={}, status="success",
                message="Password has been successfully reset.",
                status_code=status.HTTP_201_CREATED,
                )
            self.log_response(response)  # Log the response before returning
            return response
        except Exception as e:
            print(e)
            response = self.get_response(
                message="Something went wrong",
                status_code=status.HTTP_401_UNAUTHORIZED,
                is_error=True)
            self.log_response(response)  # Log the response before returning
            return response
    

class ForgotPasswordAPIView(GenericAPIView, StandardResponseMixin, LoggingMixin):
    def post(self, request):
        self.log_request(request)  # Log the incoming request
        email = request.data.get('email')

        if email:
            try:
                user = User.objects.get(email=email)
                refresh = RefreshToken.for_user(user)

                reset_password_token = str(refresh.access_token)
                reset_password_link = f"{settings.FRONTEND_URL}/reset-password/?token={reset_password_token}"
                print("reset password link", reset_password_link)
                # email reset password link
                send_password_forget_email(reset_password_link, [email])

                # Send reset password email
##                send_mail(
##                    'Reset Password',
##                    f'Click the following link to reset your password: {reset_password_link}',
##                    settings.DEFAULT_FROM_EMAIL,
##                    [email],
##                    fail_silently=False,
##                )

            except User.DoesNotExist:
                response = self.get_response(
                    message="User not found",
                    status_code=status.HTTP_400_BAD_REQUEST,
                    is_error=True)
                self.log_response(response)  # Log the response before returning
                return response

        # Regardless of whether the user exists or not, show a success message
        response = self.get_response(
            message="If the provided email exists, a password reset link has been sent to your email address.",
            status_code=status.HTTP_200_OK,
            )
        self.log_response(response)  # Log the response before returning
        return response


class ResetPasswordAPIView(APIView, StandardResponseMixin, LoggingMixin):
    permission_classes = (IsAuthenticated,)
    
    def post(self, request):
        self.log_request(request)  # Log the incoming request
        user = request.user
        #token = request.data.get('token')
        password = request.data.get('password', '')
        old_password = request.data.get('old_password', '')
        token = request.auth

        
        if user and password:
            try:
##                token_obj = RefreshToken(token)
##                user_id = token_obj.get('user_id')
                user = User.objects.get(id=user.id)
                
                if not user.check_password(old_password):
                    response = self.get_error_response(
                        message="Invalid Password", status="error", errors=[],
                        error_code="INVALID_PASSWORD", status_code=status.HTTP_401_UNAUTHORIZED)
                    
                    return response
                    
                user.set_password(password)
                user.save()

                # Blacklist the token used for password reset
                # token.blacklist()
                response = self.get_response(
                    data={}, status="success",
                    message="Password has been successfully reset.",
                    status_code=status.HTTP_200_OK,
                    )
                self.log_response(response)  # Log the response before returning
                return response
            except Exception:
                response = self.get_response(
                    message="Something went wrong",
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    is_error=True)
                self.log_response(response)  # Log the response before returning
                return response

        response = self.get_error_response(
            message="Invalid token or missing password", status="error", errors=[],
            error_code="INVALID_CREDENTIALS", status_code=status.HTTP_401_UNAUTHORIZED)
        self.log_response(response)  # Log the response before returning
        return response

class ResetPasswordTokenAPIView(APIView, StandardResponseMixin, LoggingMixin):
    permission_classes = (IsAuthenticated,)
    
    def post(self, request):
        self.log_request(request)  # Log the incoming request
        user = request.user
        #token = request.data.get('token')
        password = request.data.get('password')
        token = request.auth
        
        if user and password:
            try:
##                token_obj = RefreshToken(token)
##                user_id = token_obj.get('user_id')
                user = User.objects.get(id=user.id)
                user.set_password(password)
                user.save()

                # Blacklist the token used for password reset
                # token.blacklist()
                response = self.get_response(data={}, status="success",
                                         message="Password has been successfully reset.",
                                         status_code=status.HTTP_200_OK)
                
                self.log_response(response)  # Log the response before returning
                return response
            except Exception:
                response = self.get_response(
                    message="Something went wrong",
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    is_error=True)
                self.log_response(response)  # Log the response before returning
                return response

        response = self.get_response(
            message="Invalid token or missing password",
            status_code=status.HTTP_401_UNAUTHORIZED,
            is_error=True)
        self.log_response(response)  # Log the response before returning
        return response



class UserProfileViewset(viewsets.ModelViewSet, StandardResponseMixin, LoggingMixin):
    queryset = User.objects.all()
    serializer_class = UserListSerializer
    http_method_names = ['get', 'post', 'put', 'patch', 'delete']

    @action(detail=True, methods=['delete'], url_path='delete_user',
            permission_classes=[IsAuthenticated], url_name='delete-user')
    def delete_user(self, request, pk=None):
        try:
            user = self.get_object()

            with transaction.atomic():
                
                BookingInvoiceLog.objects.filter(booking__user=user).delete()
                BookingPaymentLog.objects.filter(booking__user=user).delete()
                Booking.objects.filter(user=user).delete()

                # Delete Wallet-related data
                Wallet.objects.filter(user=user).delete()
                WalletTransaction.objects.filter(user=user).delete()
                WalletTransactionLog.objects.filter(user=user).delete()

                # Finally, delete the user
                user_email = user.email
                user_phone_number = user.mobile_number
                user.delete()
                print(f"Deleted user with ID: {user.id}, Email: {user_email}, Phone: {user_phone_number}")

            return Response(
                {
                    'detail': 'User and related data deleted successfully.',
                    'email': user_email,
                    'phone_number': user_phone_number
                },
                status=status.HTTP_204_NO_CONTENT
            )
        
        except Exception as e:
            return Response({'detail': f'Error deleting user: {str(e)}'}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['GET'], url_path='detail',
            permission_classes=[IsAuthenticated],
            url_name='user-profile-detail')
    def get_user_profile_detail(self, request):

        user = request.user
        #print("customer profile", user.customer_profile.all())
        userlist_serializer = UserListSerializer(user)
        response = self.get_response(data=userlist_serializer.data, status="success",
                                     message="Profile Retrieved",
                                     status_code=status.HTTP_200_OK)
        return response

    @action(detail=False, methods=['GET'], url_path='referral',
            permission_classes=[IsAuthenticated],
            url_name='referral-link')
    def get_referral_link(self, request):
        user = request.user
        referral_code = user.referral

        if user.default_group == 'B2C-GRP':
            signup_link = f"{settings.FRONTEND_URL}/signup/?referral_code={referral_code}"
        elif user.default_group == 'BUSINESS-GRP':
            signup_link = f"{settings.FRONTEND_URL}/signup/?referral_code={referral_code}"
        elif user.default_group == 'CORPORATE-GRP':
            signup_link = f"{settings.FRONTEND_URL}/corporate-register/?referral_code={referral_code}"
        else:
            signup_link = f"{settings.FRONTEND_URL}/signup/?referral_code={referral_code}"

        data = {"signup_link": signup_link}

        response = self.get_response(data=data, status="success",
                                     message="Referral Link",
                                     status_code=status.HTTP_200_OK)
        return response

    @action(detail=False, methods=['GET'], url_path='referral/summary',
            permission_classes=[IsAuthenticated],
            url_name='referral-summary')
    def get_referral_summary(self, request):
        user_id = request.query_params.get('user', None)
        if not user_id:
            user = request.user
            user_id = user.id
        else:  
            user = User.objects.filter(id=user_id).first()

        if not user or not user_id:
            response = self.get_error_response(
                message="Invalid User", status="error",
                errors=[],error_code="INVALID_USER",
                status_code=status.HTTP_400_BAD_REQUEST)
            return response
            
        referral = user.referral

        if not referral:
            response = self.get_error_response(
                message="Missing referral code", status="error",
                errors=[],error_code="MISSING_REFERRAL_CODE",
                status_code=status.HTTP_400_BAD_REQUEST)
            return response
            
        referred_users = list(User.objects.filter(
            referred_code=referral).values_list('id', flat=True))

        no_of_referred_users = len(referred_users)
        referred_users.append(-1)

        total_amount, credited_user_list = customer_db_utils.get_referral_bonus(referred_users, user_id)
        if total_amount is None:
            total_amount = 0
        else:
            total_amount = str(total_amount)

        no_of_credited_users = len(credited_user_list)

        data = {"no_of_referred_users":no_of_referred_users,
                "no_of_credited_user":no_of_credited_users,
                "total_credited_amount": total_amount}

        response = self.get_response(data=data, count=1, status="success",
                                     message="Referral Summary",
                                     status_code=status.HTTP_200_OK)
        return response

    @action(detail=False, methods=['GET'], url_path='referral/users',
            permission_classes=[IsAuthenticated],
            url_name='referral-users')
    def get_referral_user(self, request):
        user_id = request.query_params.get('user', None)
        if not user_id:
            user = request.user
            user_id = user.id
        else:  
            user = User.objects.filter(id=user_id).first()

        if not user or not user_id:
            response = self.get_error_response(
                message="Invalid User", status="error",
                errors=[],error_code="INVALID_USER",
                status_code=status.HTTP_400_BAD_REQUEST)
            return response
            
        referral = user.referral

        if not referral:
            response = self.get_error_response(
                message="Missing referral code", status="error",
                errors=[],error_code="MISSING_REFERRAL_CODE",
                status_code=status.HTTP_400_BAD_REQUEST)
            return response

        referred_users = User.objects.filter(referred_code=referral)

        count, referred_users = paginate_queryset(self.request, referred_users)

        credited_user_dict = customer_db_utils.get_credited_referred_user(user_id)
        context={'credited_user_dict': credited_user_dict}

        serializer = UserRefferalSerializer(referred_users, many=True, context=context)

##        referred_users = referred_users.values(
##            'id','name', 'email','first_booking')
##
##        data = {"referred_list":}

        response = self.get_response(data=serializer.data, count=count, status="success",
                                     message="Referral User List",
                                     status_code=status.HTTP_200_OK)
        return response
    
    
    @action(detail=False, methods=['POST'], url_path='default/group',
            permission_classes=[IsAuthenticated],
            url_name='default-group')
    def update_default_group(self, request):
        instance = self.request.user
        user_groups = []
        
        try:
            user_groups = [ugroups.get('name', '') for ugroups in instance.groups.values('name')]
        except Exception as e:
            print(e)   
        
        default_group = request.data.get('default_group', None)
            
        if instance:
            if not default_group:
                custom_response = self.get_error_response(
                    message="Missing default group", status="error",
                    errors=[],error_code="GROUP_MISSING",
                    status_code=status.HTTP_404_NOT_FOUND)
                return custom_response

            if not default_group in user_groups:
                custom_response = self.get_error_response(
                    message="Group Not Mapped", status="error",
                    errors=[],error_code="GROUP_MISSING",
                    status_code=status.HTTP_404_NOT_FOUND)
                return custom_response
            
            instance.default_group = default_group
            instance.save()
            custom_response = self.get_response(
                status='success',
                data=[],  # Use the data from the default response
                message="Default Group Updated",
                status_code=status.HTTP_200_OK,  # 200 for successful retrieval
                )
        else:
            custom_response = self.get_error_response(
                message="User Not Found", status="error",
                errors=[],error_code="USER_MISSING",
                status_code=status.HTTP_404_NOT_FOUND)
        return custom_response
        
    @action(detail=False, methods=['POST'], url_path='update-groups-roles',
            permission_classes=[IsAuthenticated],
            url_name='update-groups-roles')
    def update_user_groups_roles(self, request):
        self.log_request(request)
        
        user_id = request.data.get('user_id', None)
        
        if user_id:
            # if not request.user.is_staff and not request.user.is_superuser:
            #     response = self.get_error_response(
            #         message="Permission denied to modify other users",
            #         status="error",
            #         errors=[],
            #         error_code="PERMISSION_DENIED",
            #         status_code=status.HTTP_403_FORBIDDEN
            #     )
            #     self.log_response(response)
            #     return response
                
            try:
                user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                response = self.get_error_response(
                    message="User not found",
                    status="error",
                    errors=[],
                    error_code="USER_NOT_FOUND",
                    status_code=status.HTTP_404_NOT_FOUND
                )
                self.log_response(response)
                return response
        else:
            response = self.get_error_response(
                message="User ID is required",
                status="error",
                errors=[],
                error_code="USER_ID_REQUIRED",
                status_code=status.HTTP_400_BAD_REQUEST
            )
            self.log_response(response)
            return response
                
        users_groups = request.data.get('users_groups', [])
        users_roles = request.data.get('users_roles', [])
        removal_groups = request.data.get('removal_groups', [])
        removal_roles = request.data.get('removal_roles', [])
        
        current_groups = list(user.groups.values_list('name', flat=True))
        current_roles = list(user.roles.values_list('name', flat=True))
        
        if (all(group in current_groups for group in users_groups) and 
            all(role in current_roles for role in users_roles) and
            not removal_groups and not removal_roles):
            response = self.get_response(
                data=[],
                status="success",
                message="Already existed.",
                status_code=status.HTTP_200_OK
            )
            self.log_response(response)
            return response
        
        if removal_groups:
            remaining_groups = [group for group in current_groups if group not in removal_groups]
            if not remaining_groups and not users_groups:
                response = self.get_error_response(
                    message="At least one group and role required",
                    status="error",
                    errors=[],
                    error_code="VALIDATION_ERROR",
                    status_code=status.HTTP_400_BAD_REQUEST
                )
                self.log_response(response)
                return response
                
            for group_name in removal_groups:
                group = db_utils.get_group_by_name(group_name)
                if group and group in user.groups.all():
                    user.groups.remove(group)
                    
        if removal_roles:
            remaining_roles = [role for role in current_roles if role not in removal_roles]
            if not remaining_roles and not users_roles:
                response = self.get_error_response(
                    message="At least one group and role required",
                    status="error",
                    errors=[],
                    error_code="VALIDATION_ERROR",
                    status_code=status.HTTP_400_BAD_REQUEST
                )
                self.log_response(response)
                return response
                
            for role_name in removal_roles:
                role = db_utils.get_role_by_name(role_name)
                if role and role in user.roles.all():
                    user.roles.remove(role)
        
        # Add new groups
        for group_name in users_groups:
            if group_name not in current_groups:
                group = db_utils.get_group_by_name(group_name)
                if group:
                    user.groups.add(group)
        
        # Add new roles
        for role_name in users_roles:
            if role_name not in current_roles:
                role = db_utils.get_role_by_name(role_name)
                if role:
                    user.roles.add(role)
        
        user.refresh_from_db()
        updated_groups = list(user.groups.values_list('name', flat=True))
        updated_roles = list(user.roles.values_list('name', flat=True))
        
        response_data = {
            "user_id": user.id,
            "email": user.email,
            "groups": updated_groups,
            "roles": updated_roles
        }
        
        response = self.get_response(
            data=response_data,
            status="success",
            message="User groups and roles updated successfully",
            status_code=status.HTTP_200_OK
        )
        self.log_response(response)
        return response

    @action(detail=False, methods=['post'], url_path='billed-to-user',
        permission_classes=[IsAuthenticated], url_name='billed-to-user')
    def billed_to_user(self, request):
        """
        Create a new user with group and role assignment for billing purposes
        """
        try:
            # Validate request data
            serializer = BilledUserSerializer(data=request.data)
            if not serializer.is_valid():
                return self.get_error_response(
                    message="Invalid request data", 
                    status="error", 
                    errors=serializer.errors,
                    error_code="INVALID_DATA", 
                    status_code=status.HTTP_400_BAD_REQUEST
                )

            validated_data = serializer.validated_data
            mobile_number = validated_data['mobile_number']
            email = validated_data['email']
            name = validated_data['name']
            user_group = validated_data['user_group']

            # Check if user already exists with same email or mobile
            existing_user = User.objects.filter(
                Q(email=email) | Q(mobile_number=mobile_number)
            ).first()
            
            if existing_user:
                return self.get_error_response(
                    message="User already exists with this email or mobile number",
                    status="error",
                    errors=[],
                    error_code="USER_ALREADY_EXISTS",
                    status_code=status.HTTP_409_CONFLICT
                )

            # Get group and role based on user_group
            grp, role = authentication_utils.get_group_based_on_name(user_group)
            if not grp or not role:
                return self.get_error_response(
                    message="Group or role doesn't exist",
                    status="error",
                    errors=[],
                    error_code="GROUP_ROLE_NOT_EXIST",
                    status_code=status.HTTP_406_NOT_ACCEPTABLE
                )

            # Create user within transaction
            with transaction.atomic():
                # Create the user
                user = User.objects.create(
                    email=email,
                    mobile_number=mobile_number,
                    name=name,
                    first_name=name.split(' ')[0] if name else '',
                    last_name=' '.join(name.split(' ')[1:]) if len(name.split(' ')) > 1 else '',
                    default_group=user_group,
                    is_active=True
                )

                # Create customer profile
                Customer.objects.create(user_id=user.id, active=True)

                # Assign group and role
                if grp:
                    user.groups.add(grp)
                if role:
                    user.roles.add(role)

                # Prepare response data
                user_data = {
                    'id': user.id,
                    'email': user.email,
                    'mobile_number': user.mobile_number,
                    'name': user.name,
                    'user_group': user_group,
                    'groups': [{'id': grp.id, 'name': grp.name}] if grp else [],
                    'roles': [{'id': role.id, 'name': role.name}] if role else [],
                    'default_group': user.default_group,
                    'created': user.created,
                    'is_active': user.is_active
                }

                return Response(
                    {
                        'status': 'success',
                        'message': 'User created successfully for billing',
                        'data': user_data
                    },
                    status=status.HTTP_201_CREATED
                )

        except Exception as e:
            return Response(
                {
                    'status': 'error',
                    'message': f'Error creating billed user: {str(e)}',
                    'data': {}
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class SocialAuthentication(viewsets.ModelViewSet, StandardResponseMixin, LoggingMixin):
    queryset = User.objects.all()
    serializer_class = UserListSerializer
    http_method_names = ['get', 'post', 'put', 'patch']

    @action(detail=False, methods=['POST'], url_path='google',
            permission_classes=[],
            url_name='google')
    def google_based_authentication(self, request):
        gtoken = request.data.get('id_token', None)
        referred_code = request.data.get('referred_code', '')

        if not gtoken:
            custom_response = self.get_error_response(
                message="Missing token", status="error",
                errors=[],error_code="TOKEN_MISSING",
                status_code=status.HTTP_400_BAD_REQUEST)
            return custom_response
        
        token_status, name, email = authentication_utils.validate_google_token(gtoken)
        if not token_status:
            custom_response = self.get_error_response(
                message="Invalid token", status="error",
                errors=[],error_code="INVALID_TOKEN",
                status_code=status.HTTP_400_BAD_REQUEST)
            return custom_response

        if not email:
            custom_response = self.get_error_response(
                message="Missing Email", status="error",
                errors=[],error_code="MISSING_EMAIL",
                status_code=status.HTTP_400_BAD_REQUEST)
            return custom_response
            
        email = email.lower()
        check_existing_user = User.objects.filter(email=email).first()
        if check_existing_user:
            data = authentication_utils.generate_refresh_token(check_existing_user)
            response = self.get_response(data=data, status="success",
                                         message="Login successful",
                                         status_code=status.HTTP_200_OK)
            return response


        # for new user 
        new_user = User.objects.create(
            name=name, email=email, mobile_number="",
            referred_code=referred_code, default_group='B2C-GRP')
        Customer.objects.create(user_id=new_user.id, active=True)
        
        # set groups and roles
        grp = db_utils.get_group_by_name('B2C-GRP')
        role = db_utils.get_role_by_name('B2C-CUST')

        if grp:
            new_user.groups.add(grp)
        if role:
            new_user.roles.add(role)

        authentication_utils.add_signup_bonus(new_user, 'B2C-GRP', role)

        
        data = authentication_utils.generate_refresh_token(new_user)
        
        response = self.get_response(data=data, status="success",
                                     message="Signup successful",
                                     status_code=status.HTTP_200_OK)
        return response


# class ForgotPasswordView(APIView):
#     permission_classes = [AllowAny]
#
#     def post(self, request):
#         email = request.data.get('email')
#         if not email:
#             # return Response({'message': 'Email is required.', 'status': status.HTTP_400_BAD_REQUEST})
#             return Response({
#                     RETURN_RESPONSE['STATUS']: FAILED,
#                     RETURN_RESPONSE['STATUS_CODE']: status.HTTP_400_BAD_REQUEST,
#                     RETURN_RESPONSE['MESSAGE']: 'Email is required.',
#                     RETURN_RESPONSE['RESULT']:  {}
#                 })
#
#         try:
#             user = User.objects.get(email=email)
#         except User.DoesNotExist:
#             return Response({
#                     RETURN_RESPONSE['STATUS']: SUCCESS,
#                     RETURN_RESPONSE['STATUS_CODE']: status.HTTP_404_NOT_FOUND,
#                     RETURN_RESPONSE['MESSAGE']: 'No user found with the provided email.',
#                     RETURN_RESPONSE['RESULT']:  {"email": email}
#                 })
#
#         # Generate password reset token
#         token = default_token_generator.make_token(user)
#         uid = urlsafe_base64_encode(force_bytes(user.pk))
#
#         # Send password reset email
#         reset_link = f'http://your-domain.com/reset-password/{uid}/{token}/'  # Update with your actual reset URL
#         message = f'Click the link below to reset your password:\n{reset_link}'
#         send_mail('Password Reset', message, 'from@example.com', [email])
#
#         return Response({
#                     RETURN_RESPONSE['STATUS']: SUCCESS,
#                     RETURN_RESPONSE['STATUS_CODE']: status.HTTP_200_OK,
#                     RETURN_RESPONSE['MESSAGE']: 'Password reset email sent.',
#                     RETURN_RESPONSE['RESULT']:  {"email": email}
#                 })

