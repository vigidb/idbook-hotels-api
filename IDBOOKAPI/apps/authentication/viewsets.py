import traceback
import logging

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
    CreateAPIView,
    ListAPIView,
    GenericAPIView,
    RetrieveAPIView,
    UpdateAPIView,
)
from IDBOOKAPI.mixins import StandardResponseMixin, LoggingMixin
from IDBOOKAPI.email_utils import (
    send_otp_email,
    send_password_forget_email,
    email_validation,
    get_domain,
)
from IDBOOKAPI.otp_utils import generate_otp
from IDBOOKAPI.utils import get_timediff_in_minutes, validate_mobile_number

from .models import User, UserOtp, Role
from apps.customer.models import Customer
from .serializers import (
    UserSignupSerializer,
    LoginSerializer,
    UserListSerializer,
    UserRefferalSerializer,
    BilledUserSerializer,
)

# from .emails import send_welcome_email

from rest_framework.decorators import action
from apps.authentication.throttles import SwitchGroupThrottle
from rest_framework import viewsets
from django.utils import timezone

from apps.org_managements.utils import get_domain_business_details
from apps.customer.utils import db_utils as customer_db_utils

from apps.authentication.tasks import (
    send_email_task,
    customer_signup_link_task,
    send_signup_email_task,
)

from apps.authentication.utils import db_utils, authentication_utils

from IDBOOKAPI.permissions import HasRoleModelPermission
from IDBOOKAPI.utils import paginate_queryset
from django.db import transaction
from apps.booking.models import Booking
from apps.customer.models import Wallet, WalletTransaction
from apps.log_management.models import (
    WalletTransactionLog,
    BookingPaymentLog,
    BookingInvoiceLog,
    UserSubscriptionLogs,
    BookingRefundLog,
)
from django.db.models import Q

User = get_user_model()

logger = logging.getLogger(__name__)


def homepage(request):
    from IDBOOKAPI.settings import BASE_URL as HOST

    return HttpResponse(
        f"Welcome to APIs server please visit <a href='/api/v1/docs'>{HOST}/api/v1/docs</a> or <a href='/api/v1/docs2'>{HOST}/api/v1/docs2</a> "
    )


class UserCreateAPIView(viewsets.ModelViewSet, StandardResponseMixin, LoggingMixin):
    queryset = User.objects.all()
    serializer_class = UserSignupSerializer
    http_method_names = ["get", "post", "put", "patch"]

    def get_user_with_tokens(self, user):

        refresh = RefreshToken.for_user(user)
        data = authentication_utils.user_representation(user, refresh_token=refresh)

        return data

    def create(self, request, *args, **kwargs):
        self.log_request(request)  # Log the incoming request

        email = request.data.get("email", None)
        if email:
            email = email.lower().strip()
        mobile_number = request.data.get("mobile_number", None)
        name = request.data.get("name", None)
        group_name = request.data.get("group_name", "B2C-GRP")
        otp = request.data.get("otp", None)
        otp_mobile = request.data.get("otp_mobile", None)
        user = None

        # Check mandatory OTP fields
        errors = []
        if not otp:
            errors.append({"field": "otp", "message": "Email OTP is required"})
        if not otp_mobile:
            errors.append({"field": "otp_mobile", "message": "Mobile OTP is required"})

        if errors:
            return self.get_error_response(
                message="Email or Mobile OTP is missing",
                status="error",
                errors=errors,
                error_code="OTP_FIELDS_REQUIRED",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        accept_term = request.data.get("acceptTerms", None)
        if not accept_term:
            response = self.get_error_response(
                message="Please accept the terms and conditions",
                status="error",
                errors=[
                    {
                        "field": "acceptTerms",
                        "message": "Please accept the terms and conditions",
                    }
                ],
                error_code="TERMS_NOT_ACCEPTED",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
            return response

        user_otp = None
        if otp:
            # VERIFY
            user_otp = UserOtp.objects.filter(
                user_account=email, otp=otp, otp_for="SIGNUP"
            ).first()
            if not user_otp:
                response = self.get_error_response(
                    message="Invalid Email OTP",
                    status="error",
                    errors=[],
                    error_code="INVALID_OTP",
                    status_code=status.HTTP_406_NOT_ACCEPTABLE,
                )
                return response

        if otp_mobile:
            mob_otp = UserOtp.objects.filter(
                user_account=mobile_number, otp=otp_mobile, otp_for="SIGNUP"
            ).first()
            if not mob_otp:
                response = self.get_error_response(
                    message="Invalid Mobile OTP",
                    status="error",
                    errors=[],
                    error_code="INVALID_OTP",
                    status_code=status.HTTP_406_NOT_ACCEPTABLE,
                )
                return response

        if email:
            email = email.lower().strip()
            user = User.objects.filter(email=email).first()

        grp, role = authentication_utils.get_group_based_on_name(group_name)
        if not grp or not role:
            response = self.get_error_response(
                message="Group or role doesn't exist",
                status="error",
                errors=[],
                error_code="GROUP_ROLE_NOT_EXIST",
                status_code=status.HTTP_406_NOT_ACCEPTABLE,
            )
            return response

        # Check if user already exists and already has this group
        if user and group_name:
            if user.groups.filter(id=grp.id).exists():
                error_list = [{"field": "email", "message": "Email already exists for this group"}]
                response = self.get_error_response(
                    message="Signup Failed",
                    status="error",
                    errors=error_list,
                    error_code="EMAIL_ALREADY_EXISTS_FOR_GROUP",
                    status_code=status.HTTP_401_UNAUTHORIZED,
                )
                self.log_response(response)
                return response

        if mobile_number:
            ##            check_mobile_existing_user = authentication_utils.check_mobile_exist_for_group(mobile_number, grp)
            mobile_grp_users = db_utils.get_userid_list(mobile_number, group=grp)
            if mobile_grp_users:
                if any((not user) or u["id"] != user.id for u in mobile_grp_users):
                    response = self.get_error_response(
                        message="Mobile already exist",
                        status="error",
                        errors=[],
                        error_code="MOBILE_EXIST",
                        status_code=status.HTTP_406_NOT_ACCEPTABLE,
                    )
                    return response

        # If user exists, update it directly (don't use serializer to avoid validation issues)
        if user:
            # User exists - update fields and add group/role
            if name and not user.name:
                user.name = name
            if mobile_number and not user.mobile_number:
                user.mobile_number = mobile_number
            
            if grp and not user.groups.filter(id=grp.id).exists():
                user.groups.add(grp)
            if role and not user.roles.filter(id=role.id).exists():
                user.roles.add(role)
            user.default_group = group_name
            user.email_verified = True
            user.mobile_verified = True
            user.save()
            authentication_utils.add_signup_bonus(user, group_name, role)
        else:
            # User doesn't exist - create new user using serializer
            # Double-check email doesn't exist (race condition protection)
            if email:
                final_check = User.objects.filter(email=email).first()
                if final_check:
                    # User was created between checks - add group instead
                    if grp and not final_check.groups.filter(id=grp.id).exists():
                        final_check.groups.add(grp)
                    if role and not final_check.roles.filter(id=role.id).exists():
                        final_check.roles.add(role)
                    final_check.default_group = group_name
                    final_check.email_verified = True
                    final_check.mobile_verified = True
                    final_check.save()
                    authentication_utils.add_signup_bonus(final_check, group_name, role)
                    user = final_check
                else:
                    # Create new user
                    serializer = self.get_serializer(data=request.data)
                    if serializer.is_valid():
                        user = serializer.save()
                        customer_id = user.id
                        # save customer profile with user id
                        Customer.objects.create(user_id=customer_id, active=True)
                        
                        if grp and not user.groups.filter(id=grp.id).exists():
                            user.groups.add(grp)
                        if role and not user.roles.filter(id=role.id).exists():
                            user.roles.add(role)
                        user.default_group = group_name
                        user.email_verified = True
                        user.mobile_verified = True
                        user.save()
                        authentication_utils.add_signup_bonus(user, group_name, role)
                    else:
                        # Serializer validation failed
                        error_list = []
                        errors = serializer.errors
                        for field_name, field_errors in serializer.errors.items():
                            for ferror in field_errors:
                                error_list.append({"field": field_name, "message": ferror})

                        response = self.get_error_response(
                            message="Signup Failed",
                            status="error",
                            errors=error_list,
                            error_code="VALIDATION_ERROR",
                            status_code=status.HTTP_401_UNAUTHORIZED,
                        )
                        self.log_response(response)
                        return response

        if user:

            ##            user = authentication_utils.add_group_based_on_signup(user, group_name)
            # userlist_serializer = UserListSerializer(user)

            # send welcome email
            send_signup_email_task.apply_async(
                args=[user.get_full_name(), [user.email], group_name]
            )
            # send_signup_email_task.apply_async(args=[user.get_full_name(), [user.email]])
            # generate token
            refresh = RefreshToken.for_user(user)
            # user representation
            data = authentication_utils.user_representation(user, refresh_token=refresh)

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
                    error_list.append({"field": field_name, "message": ferror})

            response = self.get_error_response(
                message="Signup Failed",
                status="error",
                errors=error_list,
                error_code="VALIDATION_ERROR",
                status_code=status.HTTP_401_UNAUTHORIZED,
            )
            self.log_response(response)  # Log the response before returning
            return response

    @action(
        detail=False,
        methods=["POST"],
        url_path="customer/signup-link",
        url_name="customer-signup-link",
        permission_classes=[IsAuthenticated],
    )
    def customer_signup_link(self, request):
        company_user = request.user
        email = request.data.get("email", "")
        gender = request.data.get("gender", "")
        mobile_number = request.data.get("mobile_number", "")
        name = request.data.get("name", "")
        employee_id = request.data.get("employee_id", "")
        group_name = request.data.get("group_name", "DEFAULT")
        department = request.data.get("department", "")

        company_id = company_user.company_id

        if not company_id:
            response = self.get_error_response(
                message="The user is not associated with any company.",
                status="error",
                errors=[],
                error_code="COMPANY_MISSING",
                status_code=status.HTTP_401_UNAUTHORIZED,
            )
            return response

        user = User.objects.filter(email=email).first()
        if not user:
            user = User.objects.create(
                email=email,
                company_id=company_id,
                mobile_number=mobile_number,
                name=name,
            )
            customer = customer_db_utils.create_customer_signup_entry(
                user,
                added_user=company_user,
                gender=gender,
                employee_id=employee_id,
                group_name=group_name,
                department=department,
            )
        else:
            customer = customer_db_utils.check_customer_exist(user.id)
            if not customer:
                customer = customer_db_utils.create_customer_signup_entry(
                    user,
                    added_user=company_user,
                    gender=gender,
                    employee_id=employee_id,
                    group_name=group_name,
                    department=department,
                )
            # user.category = 'CL-CUST'
            user.company_id = company_id
            user.save()

        refresh = RefreshToken.for_user(user)
        customer_signup_token = str(refresh.access_token)

        customer_signup_link = f"{settings.FRONTEND_URL}/signup-link/?token={customer_signup_token}&email={email}"
        print(customer_signup_link)
        customer_signup_link_task.apply_async(
            args=[customer_signup_link, name, [email]]
        )

        response = self.get_response(
            status="success",
            message="If the provided email exists, a sign up link has been sent to your employee email address.",
            status_code=status.HTTP_200_OK,
        )
        return response

    @action(
        detail=False,
        methods=["POST"],
        url_path="customer/signup-link/process",
        url_name="customer-signup-link-process",
        permission_classes=[IsAuthenticated],
    )
    def customer_signup_link_process(self, request):
        user = request.user
        name = request.data.get("name")
        email = request.data.get("email")
        password = request.data.get("password", "")
        mobile_number = request.data.get("mobile_number", "")

        token_email = user.email
        if not token_email == email:
            response = self.get_error_response(
                message="Email Mismatch",
                status="error",
                errors=[],
                error_code="EMAIL_MISMATCH",
                status_code=status.HTTP_401_UNAUTHORIZED,
            )
            return response

        user.name = name
        if password:
            user.set_password(password)
        user.category = "CL-CUST"
        user.mobile_number = mobile_number
        user.default_group = "CORPORATE-GRP"
        user.save()

        grp = db_utils.get_group_by_name("CORPORATE-GRP")
        role = db_utils.get_role_by_name("CORP-EMP")

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
        data = authentication_utils.user_representation(user, refresh_token=refresh)

        ##        data = {'refreshToken': str(refresh),
        ##                'accessToken': str(refresh.access_token),
        ##                'expiresIn': 0,
        ##                'user': user_data,
        ##                }

        response = self.get_response(
            data=data,
            status="success",
            message="Signup Process Success.",
            status_code=status.HTTP_201_CREATED,
        )
        return response

    @action(
        detail=False,
        methods=["POST"],
        url_path="customer",
        url_name="customer-signup",
        permission_classes=[IsAuthenticated],
    )
    def company_based_customer_signup(self, request):
        user = request.user
        user_id = user.id
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid() and user_id:
            user_serializer = serializer.save()
            user_serializer.company_id = user.company_id
            user_serializer.category = "CL-CUST"
            user_serializer.save()

            customer_id = user_serializer.id
            Customer.objects.create(user_id=customer_id, added_user=user)

            data = {"user": serializer.data}
            response = self.get_response(
                data=data,
                status="success",
                message="Signup successful",
                status_code=status.HTTP_200_OK,
            )
            return response
        else:
            error_list = []
            errors = serializer.errors
            for field_name, field_errors in serializer.errors.items():
                for ferror in field_errors:
                    error_list.append({"field": field_name, "message": ferror})

            response = self.get_error_response(
                message="Signup Failed",
                status="error",
                errors=error_list,
                error_code="VALIDATION_ERROR",
                status_code=status.HTTP_401_UNAUTHORIZED,
            )
            return response

    @action(
        detail=False,
        methods=["POST"],
        url_path="email/generate-otp",
        url_name="generate-email-otp",
    )
    def generate_email_otp(self, request):
        """Need to delete the code"""
        try:
            to_email = request.data.get("email", "")
            valid = email_validation(to_email)
            if not valid:
                response = self.get_error_response(
                    message="Invalid Email",
                    status="error",
                    errors=[],
                    error_code="INVALID_EMAIL",
                    status_code=status.HTTP_406_NOT_ACCEPTABLE,
                )
                return response

            # Check if user has exceeded OTP generation limit
            can_generate, error_message = (
                authentication_utils.check_otp_generation_limit(to_email)
            )
            if not can_generate:
                response = self.get_error_response(
                    message=error_message,
                    status="error",
                    errors=[],
                    error_code="OTP_LIMIT_EXCEEDED",
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                )
                return response

            # generate otp
            otp = generate_otp(no_digits=4)
            # delete any previous otp for the user account
            # UserOtp.objects.filter(user_account=to_email).delete()
            # save otp
            # Use the same process as in the working example
            authentication_utils.email_generate_otp_process(
                otp, to_email, "PASSWORD_RESET"
            )
            # send email
            # send_otp_email(otp, [to_email])
            # send_email_task.apply_async(args=[otp, [to_email]])

            response = self.get_response(
                data={},
                status="success",
                message="OTP Success",
                status_code=status.HTTP_200_OK,
            )
        except Exception as e:
            print(e)
            response = self.get_error_response(
                message="Internal server error. Please try again later.",
                status="error",
                errors=[],
                error_code="INTERNAL_SERVER_ERROR",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return response

    @action(
        detail=False,
        methods=["POST"],
        url_path="buser/email-otp",
        url_name="buser-email-otp-signup",
    )
    def email_otp_based_buser_signup(self, request):
        try:
            email = request.data.get("email", "")
            mobile_number = request.data.get("mobile_number", "")
            name = request.data.get("name", "")
            otp = request.data.get("otp", None)
            business_id, category = "", ""
            referred_code = request.data.get("referred_code", "")

            valid = email_validation(email)
            if not valid:
                response = self.get_error_response(
                    message="Invalid Email",
                    status="error",
                    errors=[],
                    error_code="INVALID_EMAIL",
                    status_code=status.HTTP_406_NOT_ACCEPTABLE,
                )
                return response
            if not otp:
                response = self.get_error_response(
                    message="OTP Missing",
                    status="error",
                    errors=[],
                    error_code="OTP_MISSING",
                    status_code=status.HTTP_406_NOT_ACCEPTABLE,
                )
                return response

            user_otp = UserOtp.objects.filter(user_account=email, otp=otp).first()
            if user_otp:
                current_time = timezone.now()
                timediff = current_time - user_otp.created
                timediff_in_minutes = timediff.total_seconds() / 60

                if timediff_in_minutes >= settings.OTP_EXPIRY_MIN:
                    response = self.get_error_response(
                        message="OTP Expired",
                        status="error",
                        errors=[],
                        error_code="OTP_EXPIRED",
                        status_code=status.HTTP_406_NOT_ACCEPTABLE,
                    )
                else:
                    check_existing_user = User.objects.filter(email=email).first()
                    if check_existing_user:
                        data = self.get_user_with_tokens(check_existing_user)
                        response = self.get_response(
                            data=data,
                            status="success",
                            message="Login successful",
                            status_code=status.HTTP_200_OK,
                        )
                    else:
                        domain_name = get_domain(email)
                        if domain_name == "idbookhotels.com":
                            bdetails = get_domain_business_details(domain_name)
                            if bdetails:
                                business_id = bdetails.id
                        if business_id:
                            category = "B-CUST"
                            new_user = User.objects.create(
                                name=name,
                                email=email,
                                mobile_number=mobile_number,
                                business_id=business_id,
                                category=category,
                                referred_code=referred_code,
                                default_group="B2C-GRP",
                            )
                        else:
                            category = "B-CUST"
                            new_user = User.objects.create(
                                name=name,
                                email=email,
                                mobile_number=mobile_number,
                                category=category,
                                referred_code=referred_code,
                                default_group="B2C-GRP",
                            )
                        # set groups and roles
                        grp = db_utils.get_group_by_name("B2C-GRP")
                        role = db_utils.get_role_by_name("B2C-CUST")

                        if grp:
                            new_user.groups.add(grp)
                        if role:
                            new_user.roles.add(role)

                        data = self.get_user_with_tokens(new_user)
                        response = self.get_response(
                            data=data,
                            status="success",
                            message="Signup successful",
                            status_code=status.HTTP_200_OK,
                        )
            else:
                response = self.get_error_response(
                    message="Invalid Credentials",
                    status="error",
                    errors=[],
                    error_code="INVALID_CREDENTIALS",
                    status_code=status.HTTP_406_NOT_ACCEPTABLE,
                )
        except Exception as e:
            print(e)
            response = self.get_error_response(
                message="Internal server error. Please try again later.",
                status="error",
                errors=[],
                error_code="INTERNAL_SERVER_ERROR",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return response


class LoginAPIView(GenericAPIView, StandardResponseMixin, LoggingMixin):
    serializer_class = LoginSerializer

    def post(self, request):
        self.log_request(request)  # Log the incoming request

        username = request.data.get("username", "")
        # If it's an email, normalize it to lowercase
        if "@" in username:
            request.data["username"] = username.lower()
        serializer = self.get_serializer(data=request.data)
        # serializer.is_valid(raise_exception=True)
        if serializer.is_valid():
            user = serializer.validated_data["user"]
            # Enforce mobile verification before issuing tokens
            if not user.mobile_verified:
                mobile = (
                    user.mobile_number
                    or request.data.get("mobile_number")
                    or request.data.get("username")
                )

                if not mobile or not validate_mobile_number(mobile):
                    response = self.get_error_response(
                        message="Mobile verification required. Please add a valid mobile number.",
                        status="error",
                        errors=[],
                        error_code="MOBILE_VERIFICATION_REQUIRED",
                        status_code=status.HTTP_400_BAD_REQUEST,
                    )
                    self.log_response(response)
                    return response

                otp = generate_otp(no_digits=4)
                authentication_utils.mobile_generate_otp_process(
                    otp, mobile, "LOGIN"
                )

                response = self.get_response(
                    data={
                        "redirect": True,
                        "verification_required": "mobile",
                        "mobile_number": mobile,
                    },
                    status="error",
                    message="Mobile verification required. OTP sent.",
                    status_code=status.HTTP_307_TEMPORARY_REDIRECT,
                )
                self.log_response(response)
                return response
            # Use custom token with active_group support
            from apps.authentication.tokens import CustomRefreshToken

            # Get active_group from request if provided, otherwise use group_name, otherwise use default
            active_group = request.data.get("active_group", None)
            if not active_group:
                # If active_group not provided, use group_name if provided
                active_group = request.data.get("group_name", None)
            refresh = CustomRefreshToken.for_user(user, active_group=active_group)
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
            # Add active_group to response
            if refresh.get("active_group"):
                data["user"]["active_group"] = refresh["active_group"]
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
                    if ferror == "account_inactive":
                        message = "Your account is locked or inactive. Please contact support."
                        ferror = message
                        error_code = "ACCOUNT_INACTIVE"
                    elif ferror == "credentials_error":
                        message = "Invalid email or password"
                        ferror = message
                        error_code = "INVALID_CREDENTIALS"
                    else:
                        message = ferror
                        error_code = "INVALID_CREDENTIALS"
                    error_list.append({"field": field_name, "message": ferror})

            response = self.get_error_response(
                message=message,
                status="error",
                errors=error_list,
                error_code=error_code,
                status_code=status.HTTP_401_UNAUTHORIZED,
            )
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
        refresh_token = request.data.get("refresh_token")

        if refresh_token:
            try:
                token = RefreshToken(refresh_token)
                token.blacklist()
            except Exception:
                response = self.get_response(
                    message="Something went wrong",
                    status_code=status.HTTP_400_BAD_REQUEST,
                    is_error=True,
                )
                self.log_response(response)  # Log the response before returning
                return response
        response = self.get_response(
            message="Successfully logged out",
            status_code=status.HTTP_200_OK,
        )
        self.log_response(response)  # Log the response before returning
        return response


class OtpBasedUserEntryAPIView(
    viewsets.ModelViewSet, StandardResponseMixin, LoggingMixin
):
    queryset = User.objects.all()
    serializer_class = UserSignupSerializer
    http_method_names = ["get", "post", "put", "patch"]

    @action(detail=False, methods=["POST"], url_path="signup", url_name="otp-signup")
    def otp_based_user_signup(self, request):

        email = request.data.get("email", "")
        if email:
            email = email.lower().strip()
        mobile_number = request.data.get("mobile_number", "")
        name = request.data.get("name", "")
        otp = request.data.get("otp", None)
        referred_code = request.data.get("referred_code", "")
        group_name = request.data.get("group_name", "B2C-GRP")

        valid = email_validation(email)
        if not valid:
            response = self.get_error_response(
                message="Invalid Email",
                status="error",
                errors=[],
                error_code="INVALID_EMAIL",
                status_code=status.HTTP_406_NOT_ACCEPTABLE,
            )
            return response
        if not otp:
            response = self.get_error_response(
                message="OTP Missing",
                status="error",
                errors=[],
                error_code="OTP_MISSING",
                status_code=status.HTTP_406_NOT_ACCEPTABLE,
            )
            return response
        is_mb_valid = validate_mobile_number(mobile_number)
        if not is_mb_valid:
            response = self.get_error_response(
                message="Invalid Mobile Number",
                status="error",
                errors=[],
                error_code="INVALID_NUMBER",
                status_code=status.HTTP_406_NOT_ACCEPTABLE,
            )
            return response

        user_otp = db_utils.get_user_otp_details(email, mobile_number, otp)
        # user_otp = UserOtp.objects.filter(user_account=email, otp=otp).first()
        if not user_otp:
            response = self.get_error_response(
                message="Invalid Credentials",
                status="error",
                errors=[],
                error_code="INVALID_CREDENTIALS",
                status_code=status.HTTP_406_NOT_ACCEPTABLE,
            )
            return response

        # check whether otp expired or not
        current_time = timezone.now()
        timediff = current_time - user_otp.created
        timediff_in_minutes = timediff.total_seconds() / 60

        if timediff_in_minutes >= settings.OTP_EXPIRY_MIN:
            response = self.get_error_response(
                message="OTP Expired",
                status="error",
                errors=[],
                error_code="OTP_EXPIRED",
                status_code=status.HTTP_406_NOT_ACCEPTABLE,
            )
            return response

        # Normalize email and check whether email already exists (globally unique)
        if email:
            email = email.lower().strip()
        check_existing_user = User.objects.filter(email=email).first() if email else None

        # group and roles
        grp, role = authentication_utils.get_group_based_on_name(group_name)
        if not grp or not role:
            response = self.get_error_response(
                message="Group or role doesn't exist",
                status="error",
                errors=[],
                error_code="GROUP_ROLE_NOT_EXIST",
                status_code=status.HTTP_406_NOT_ACCEPTABLE,
            )
            return response

        # Check if user already exists and already has this group
        if check_existing_user:
            if check_existing_user.groups.filter(id=grp.id).exists():
                response = self.get_error_response(
                    message="Email already exists for this group",
                    status="error",
                    errors=[{"field": "email", "message": "Email already exists for this group"}],
                    error_code="EMAIL_ALREADY_EXISTS_FOR_GROUP",
                    status_code=status.HTTP_406_NOT_ACCEPTABLE,
                )
                return response

        # check whether mobile already exist or not (within the same group)
        # First check if mobile exists globally (to prevent duplicates)
        if mobile_number:
            mobile_user_global = User.objects.filter(mobile_number=mobile_number).first()
            if mobile_user_global:
                # If mobile exists but it's a different user than the email user, that's an error
                if check_existing_user and mobile_user_global.id != check_existing_user.id:
                    response = self.get_error_response(
                        message="Mobile number is already associated with a different account",
                        status="error",
                        errors=[{"field": "mobile_number", "message": "Mobile number already exists"}],
                        error_code="MOBILE_EXISTS_DIFFERENT_USER",
                        status_code=status.HTTP_406_NOT_ACCEPTABLE,
                    )
                    return response
                # If mobile exists and it's the same user, check group
                if mobile_user_global.groups.filter(id=grp.id).exists():
                    response = self.get_error_response(
                        message="Mobile already exists for this group",
                        status="error",
                        errors=[{"field": "mobile_number", "message": "Mobile already exists for this group"}],
                        error_code="MOBILE_EXIST",
                        status_code=status.HTTP_406_NOT_ACCEPTABLE,
                    )
                    return response

        # If user exists, add group/role and return (DO NOT CREATE DUPLICATE)
        if check_existing_user:
            # User exists but doesn't have this group - add it
            if grp and not check_existing_user.groups.filter(id=grp.id).exists():
                check_existing_user.groups.add(grp)
            if role and not check_existing_user.roles.filter(id=role.id).exists():
                check_existing_user.roles.add(role)
            
            # Update user details if needed
            if name and not check_existing_user.name:
                check_existing_user.name = name
            if mobile_number and not check_existing_user.mobile_number:
                check_existing_user.mobile_number = mobile_number
            
            check_existing_user.default_group = group_name
            check_existing_user.email_verified = True
            check_existing_user.mobile_verified = True
            check_existing_user.save()

            data = authentication_utils.generate_refresh_token(
                check_existing_user, active_group=group_name
            )
            response = self.get_response(
                data=data,
                status="success",
                message="Signup successful - Group added to existing account",
                status_code=status.HTTP_200_OK,
            )
            return response

        # Only create new user if email doesn't exist globally
        # Double-check to prevent race conditions
        if email:
            final_check = User.objects.filter(email=email).first()
            if final_check:
                # User was created between checks - add group instead
                if grp and not final_check.groups.filter(id=grp.id).exists():
                    final_check.groups.add(grp)
                if role and not final_check.roles.filter(id=role.id).exists():
                    final_check.roles.add(role)
                final_check.default_group = group_name
                final_check.email_verified = True
                final_check.mobile_verified = True
                final_check.save()
                
                data = authentication_utils.generate_refresh_token(
                    final_check, active_group=group_name
                )
                response = self.get_response(
                    data=data,
                    status="success",
                    message="Signup successful - Group added to existing account",
                    status_code=status.HTTP_200_OK,
                )
                return response

        # create new user only if email doesn't exist
        new_user = User.objects.create(
            name=name,
            email=email,
            mobile_number=mobile_number,
            referred_code=referred_code,
            default_group=group_name,
            email_verified=True,
            mobile_verified=True,
        )
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
        response = self.get_response(
            data=data,
            status="success",
            message="Signup successful",
            status_code=status.HTTP_200_OK,
        )
        return response

    @action(detail=False, methods=["POST"], url_path="login", url_name="otp-login")
    def otp_based_user_login(self, request):

        username = request.data.get("username", "")
        if "@" in username:
            username = username.lower()
        user_id = request.data.get("user_id", None)
        otp = request.data.get("otp", None)
        group_name = request.data.get("group_name", "B2C-GRP")
        active_group = request.data.get(
            "active_group", None
        )  # Get active_group from request

        if not username:
            response = self.get_error_response(
                message="Missing username",
                status="error",
                errors=[],
                error_code="INVALID_PARAM",
                status_code=status.HTTP_406_NOT_ACCEPTABLE,
            )
            return response

        # Check if user has exceeded login attempt limit
        can_attempt, error_message = authentication_utils.check_login_attempt_limit(
            username
        )
        if not can_attempt:
            response = self.get_error_response(
                message=error_message,
                status="error",
                errors=[],
                error_code="LOGIN_LIMIT_EXCEEDED",
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            )
            return response

        # Increment login attempts before processing
        db_utils.increment_login_attempts(username)

        # get the otp details
        user_otp = UserOtp.objects.filter(
            user_account=username, otp=otp, otp_for="LOGIN"
        ).first()
        if not user_otp:
            response = self.get_error_response(
                message="Invalid Credentials",
                status="error",
                errors=[],
                error_code="INVALID_CREDENTIALS",
                status_code=status.HTTP_406_NOT_ACCEPTABLE,
            )
            return response

        # get the time difference
        current_time = timezone.now()
        timediff_in_minutes = get_timediff_in_minutes(user_otp.created, current_time)

        if timediff_in_minutes >= settings.OTP_EXPIRY_MIN:
            response = self.get_error_response(
                message="OTP Expired",
                status="error",
                errors=[],
                error_code="OTP_EXPIRED",
                status_code=status.HTTP_406_NOT_ACCEPTABLE,
            )
            return response

        grp, role = authentication_utils.get_group_based_on_name(group_name)
        if not grp:
            response = self.get_error_response(
                message="Group doesn't exist",
                status="error",
                errors=[],
                error_code="GROUP_NOT_EXIST",
                status_code=status.HTTP_406_NOT_ACCEPTABLE,
            )
            return response

        ##        user_detail = db_utils.get_user_details(user_id, username)
        user_detail = db_utils.get_group_based_user_details(grp, username)
        if not user_detail:
            response = self.get_error_response(
                message="Invalid user details",
                status="error",
                errors=[],
                error_code="INVALID_CREDENTIALS",
                status_code=status.HTTP_406_NOT_ACCEPTABLE,
            )
            return response
        user_detail.default_group = group_name
        user_detail.save()
        db_utils.reset_otp_counter(username)
        # Use active_group from request if provided, otherwise use group_name
        active_group = active_group or group_name
        data = authentication_utils.generate_refresh_token(
            user_detail, active_group=active_group
        )
        response = self.get_response(
            data=data,
            status="success",
            message="Login successful",
            status_code=status.HTTP_200_OK,
        )
        return response

    @action(
        detail=False, methods=["POST"], url_path="generate-otp", url_name="generate-otp"
    )
    def generate_otp(self, request):
        try:
            username = request.data.get("username", None)
            otp_for = request.data.get("otp_for", None)
            group_name = request.data.get("group_name", "")
            user_id = request.data.get("user_id", None)  # For Google auth cases
            if username and "@" in username:
                username = username.lower()

            if not username:
                response = self.get_error_response(
                    message="Missing username",
                    status="error",
                    errors=[],
                    error_code="INVALID_PARAM",
                    status_code=status.HTTP_406_NOT_ACCEPTABLE,
                )
                return response

            if not otp_for:
                response = self.get_error_response(
                    message="Missing otp_for",
                    status="error",
                    errors=[],
                    error_code="INVALID_PARAM",
                    status_code=status.HTTP_406_NOT_ACCEPTABLE,
                )
                return response

            # check whether user name is based on email
            # or mobile number
            is_mb_valid = validate_mobile_number(username)
            if is_mb_valid:
                medium_type = "mobile"
            else:
                is_email_valid = email_validation(username)
                if is_email_valid:
                    medium_type = "email"
                else:
                    response = self.get_error_response(
                        message="Invalid Username",
                        status="error",
                        errors=[],
                        error_code="INVALID_USERNAME",
                        status_code=status.HTTP_406_NOT_ACCEPTABLE,
                    )
                    return response
            
            # Handle Google authentication cases - update user mobile if user_id provided
            if user_id and is_mb_valid and otp_for in ["GOOGLE-SIGNUP", "GOOGLE-LOGIN"]:
                try:
                    user = User.objects.get(id=user_id)
                    # Check if mobile is already taken by another user in the same group
                    if group_name:
                        grp, role = authentication_utils.get_group_based_on_name(group_name)
                        if grp:
                            mobile_user = User.objects.filter(
                                mobile_number=username, groups=grp
                            ).exclude(id=user_id).first()
                            if mobile_user:
                                response = self.get_error_response(
                                    message="Mobile number is already associated with another account",
                                    status="error",
                                    errors=[{"field": "mobile_number", "message": "Mobile number already exists"}],
                                    error_code="MOBILE_EXISTS",
                                    status_code=status.HTTP_406_NOT_ACCEPTABLE,
                                )
                                return response
                    # Update user's mobile number
                    user.mobile_number = username
                    user.save()
                except User.DoesNotExist:
                    response = self.get_error_response(
                        message="User not found",
                        status="error",
                        errors=[],
                        error_code="USER_NOT_FOUND",
                        status_code=status.HTTP_404_NOT_FOUND,
                    )
                    return response
            grp = None
            if group_name:
                # group and roles - for OTP generation, we only need the group
                # Role will be validated during actual signup
                grp, role = authentication_utils.get_group_based_on_name(group_name)
                if not grp:
                    response = self.get_error_response(
                        message="Group doesn't exist",
                        status="error",
                        errors=[],
                        error_code="GROUP_NOT_EXIST",
                        status_code=status.HTTP_406_NOT_ACCEPTABLE,
                    )
                    return response
                # Note: Role is optional for OTP generation, will be validated during signup

            # For Google auth cases, skip duplicate checks since user already exists
            if otp_for not in ["GOOGLE-SIGNUP", "GOOGLE-LOGIN"]:
                user_objs = db_utils.get_userid_list(username, group=grp)
                print("user_objs:", user_objs)

                # allow B2C-GRP sign up for guest user
                is_role_exist = False
                if group_name == "B2C-GRP":
                    # check if B2C-CUST role exist for guest user
                    is_role_exist = db_utils.is_role_exist(user_objs, role)
                else:
                    if user_objs:
                        is_role_exist = True

                if otp_for == "LOGIN":
                    if not user_objs:
                        response = self.get_error_response(
                            message="Invalid User Credentials!",
                            status="error",
                            errors=[],
                            error_code="MISSING_USERNAME",
                            status_code=status.HTTP_406_NOT_ACCEPTABLE,
                        )
                        return response
                elif otp_for == "SIGNUP":
                    if is_role_exist:
                        response = self.get_error_response(
                            message=f"User {medium_type} is already associated with the account!",
                            status="error",
                            errors=[],
                            error_code="USERNAME_DUPLICATE",
                            status_code=status.HTTP_406_NOT_ACCEPTABLE,
                        )
                        return response
            else:
                # For Google auth, user_objs not needed
                user_objs = []

            # Check if user has exceeded OTP generation limit
            can_generate, error_message = (
                authentication_utils.check_otp_generation_limit(username)
            )
            if not can_generate:
                response = self.get_error_response(
                    message=error_message,
                    status="error",
                    errors=[],
                    error_code="OTP_LIMIT_EXCEEDED",
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                )
                return response

            # generate otp
            otp = generate_otp(no_digits=4)

            if medium_type == "email":
                # Pass group_name for SIGNUP to personalize email
                group_name_for_otp = group_name if otp_for == "SIGNUP" else None
                authentication_utils.email_generate_otp_process(otp, username, otp_for, group_name_for_otp)
            elif medium_type == "mobile":
                authentication_utils.mobile_generate_otp_process(otp, username, otp_for)

            data = {"user_list": user_objs}
            if user_id and otp_for in ["GOOGLE-SIGNUP", "GOOGLE-LOGIN"]:
                data["user_id"] = user_id
            response = self.get_response(
                data=data,
                status="success",
                message="OTP Success",
                status_code=status.HTTP_200_OK,
            )
        except Exception as e:
            print(traceback.format_exc())
            print(e)
            response = self.get_error_response(
                message="Internal server error. Please try again later.",
                status="error",
                errors=[],
                error_code="INTERNAL_SERVER_ERROR",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return response

    @action(
        detail=False, methods=["POST"], url_path="verify-otp", url_name="verify-otp"
    )
    def verify_otp(self, request):

        username = request.data.get("username", "")
        otp = request.data.get("otp", None)
        otp_for = request.data.get("otp_for", None)

        if not username:
            response = self.get_error_response(
                message="Missing username",
                status="error",
                errors=[],
                error_code="INVALID_PARAM",
                status_code=status.HTTP_406_NOT_ACCEPTABLE,
            )
            return response

        if not otp_for:
            response = self.get_error_response(
                message="Missing otp_for",
                status="error",
                errors=[],
                error_code="INVALID_PARAM",
                status_code=status.HTTP_406_NOT_ACCEPTABLE,
            )
            return response

        can_attempt, error_message = authentication_utils.check_verify_attempt_limit(
            username
        )
        if not can_attempt:
            response = self.get_error_response(
                message=error_message,
                status="error",
                errors=[],
                error_code="VERIFY_LIMIT_EXCEEDED",
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            )
            return response

        # Increment verification attempts before processing
        db_utils.increment_verify_attempts(username)

        # get the otp details
        user_otp = UserOtp.objects.filter(
            user_account=username, otp=otp, otp_for=otp_for
        ).first()
        if not user_otp:
            response = self.get_error_response(
                message="Invalid Credentials",
                status="error",
                errors=[],
                error_code="INVALID_CREDENTIALS",
                status_code=status.HTTP_406_NOT_ACCEPTABLE,
            )
            return response

        # get the time difference
        current_time = timezone.now()
        timediff_in_minutes = get_timediff_in_minutes(user_otp.created, current_time)

        if timediff_in_minutes >= settings.OTP_EXPIRY_MIN:
            response = self.get_error_response(
                message="OTP Expired",
                status="error",
                errors=[],
                error_code="OTP_EXPIRED",
                status_code=status.HTTP_406_NOT_ACCEPTABLE,
            )
            return response

        data = {}
        
        # Handle VERIFY-GUEST case
        if otp_for == "VERIFY-GUEST":
            grp, role = authentication_utils.get_group_based_on_name("B2C-GRP")
            if not grp:
                response = self.get_error_response(
                    message="Group doesn't exist",
                    status="error",
                    errors=[],
                    error_code="GROUP_NOT_EXIST",
                    status_code=status.HTTP_406_NOT_ACCEPTABLE,
                )
                return response

            user_detail = db_utils.get_group_based_user_details(grp, username)
            if user_detail:
                data = authentication_utils.generate_refresh_token(user_detail)
        
        # Handle GOOGLE-SIGNUP and GOOGLE-LOGIN cases
        elif otp_for in ["GOOGLE-SIGNUP", "GOOGLE-LOGIN"]:
            # Get user by mobile number or email
            is_mobile = validate_mobile_number(username)
            if is_mobile:
                user = User.objects.filter(mobile_number=username).first()
            else:
                user = User.objects.filter(email=username).first()
            
            if not user:
                response = self.get_error_response(
                    message="User not found",
                    status="error",
                    errors=[],
                    error_code="USER_NOT_FOUND",
                    status_code=status.HTTP_404_NOT_FOUND,
                )
                return response
            
            # Mark mobile as verified
            if is_mobile:
                user.mobile_number = username
                user.mobile_verified = True
            user.email_verified = True
            user.save()
            
            # Ensure Customer exists
            customer = Customer.objects.filter(user_id=user.id).first()
            if not customer:
                Customer.objects.create(user_id=user.id, active=True)
            
            # Get group_name from request if provided, otherwise use user's default group
            group_name = request.data.get("group_name", user.default_group or "B2C-GRP")
            
            # Generate tokens
            data = authentication_utils.generate_refresh_token(user, active_group=group_name)

        db_utils.reset_otp_counter(username)
        response = self.get_response(
            data=data,
            status="success",
            message="Otp Verification Success",
            status_code=status.HTTP_200_OK,
        )
        return response


class PasswordProcessViewSet(
    viewsets.ModelViewSet, StandardResponseMixin, LoggingMixin
):
    queryset = User.objects.all()
    serializer_class = UserSignupSerializer

    @action(
        detail=False,
        methods=["POST"],
        url_path="otp-reset",
        url_name="password-otp-reset",
        permission_classes=[],
    )
    def otp_based_password_reset(self, request):
        email = request.data.get("email", "")
        password = request.data.get("password", None)
        otp = request.data.get("otp", None)

        valid = email_validation(email)
        if not valid:
            response = self.get_error_response(
                message="Invalid Email",
                status="error",
                errors=[],
                error_code="INVALID_EMAIL",
                status_code=status.HTTP_406_NOT_ACCEPTABLE,
            )
            return response

        if not otp:
            response = self.get_error_response(
                message="OTP Missing",
                status="error",
                errors=[],
                error_code="OTP_MISSING",
                status_code=status.HTTP_406_NOT_ACCEPTABLE,
            )
            return response

        if not password:
            response = self.get_error_response(
                message="Password Missing",
                status="error",
                errors=[],
                error_code="PASSWORD_MISSING",
                status_code=status.HTTP_406_NOT_ACCEPTABLE,
            )
            return response

        # Check if user has exceeded password reset attempt limit
        can_attempt, error_message = authentication_utils.check_pwd_reset_attempt_limit(
            email
        )
        if not can_attempt:
            response = self.get_error_response(
                message=error_message,
                status="error",
                errors=[],
                error_code="PWD_RESET_LIMIT_EXCEEDED",
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            )
            return response

        # Increment password reset attempts before processing
        db_utils.increment_pwd_reset_attempts(email)

        user_otp = UserOtp.objects.filter(user_account=email, otp=otp).first()
        print(user_otp)

        if not user_otp:
            response = self.get_error_response(
                message="Invalid Credentials",
                status="error",
                errors=[],
                error_code="INVALID_CREDENTIALS",
                status_code=status.HTTP_406_NOT_ACCEPTABLE,
            )
            return response

        current_time = timezone.now()
        timediff = current_time - user_otp.created
        timediff_in_minutes = timediff.total_seconds() / 60

        if timediff_in_minutes >= settings.OTP_EXPIRY_MIN:
            response = self.get_error_response(
                message="OTP Expired",
                status="error",
                errors=[],
                error_code="OTP_EXPIRED",
                status_code=status.HTTP_406_NOT_ACCEPTABLE,
            )
            return response

        user = User.objects.filter(email=email).first()
        if not user:
            response = self.get_error_response(
                message="User Not Found",
                status="error",
                errors=[],
                error_code="USER_MISSING",
                status_code=status.HTTP_406_NOT_ACCEPTABLE,
            )
            return response

        user.set_password(password)
        user.save()
        db_utils.reset_otp_counter(email)
        response = self.get_response(
            data={},
            status="success",
            message="Password has been successfully reset. Please login",
            status_code=status.HTTP_201_CREATED,
        )
        return response

    @action(
        detail=False,
        methods=["POST"],
        url_path="profile-reset",
        url_name="password-otp-reset",
        permission_classes=[IsAuthenticated],
    )
    def profile_password_reset(self, request):
        user = request.user
        password = request.data.get("password", "")
        old_password = request.data.get("old_password", "")
        token = request.auth

        if "" in (user, password, old_password):
            response = self.get_error_response(
                message="Missing Fields",
                status="error",
                errors=[],
                error_code="INVALID_FIELDS",
                status_code=status.HTTP_406_NOT_ACCEPTABLE,
            )
            return response

        try:
            user = User.objects.get(id=user.id)

            if not user.check_password(old_password):
                response = self.get_error_response(
                    message="Invalid Password",
                    status="error",
                    errors=[],
                    error_code="INVALID_PASSWORD",
                    status_code=status.HTTP_401_UNAUTHORIZED,
                )

                return response

            user.set_password(password)
            user.save()

            response = self.get_response(
                data={},
                status="success",
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
                is_error=True,
            )
            self.log_response(response)  # Log the response before returning
            return response


class ForgotPasswordAPIView(GenericAPIView, StandardResponseMixin, LoggingMixin):
    def post(self, request):
        self.log_request(request)  # Log the incoming request
        email = request.data.get("email")

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
                    is_error=True,
                )
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
        # token = request.data.get('token')
        password = request.data.get("password", "")
        old_password = request.data.get("old_password", "")
        token = request.auth

        if user and password:
            try:
                ##                token_obj = RefreshToken(token)
                ##                user_id = token_obj.get('user_id')
                user = User.objects.get(id=user.id)

                if not user.check_password(old_password):
                    response = self.get_error_response(
                        message="Invalid Password",
                        status="error",
                        errors=[],
                        error_code="INVALID_PASSWORD",
                        status_code=status.HTTP_401_UNAUTHORIZED,
                    )

                    return response

                user.set_password(password)
                user.save()

                # Blacklist the token used for password reset
                # token.blacklist()
                response = self.get_response(
                    data={},
                    status="success",
                    message="Password has been successfully reset.",
                    status_code=status.HTTP_200_OK,
                )
                self.log_response(response)  # Log the response before returning
                return response
            except Exception:
                response = self.get_response(
                    message="Something went wrong",
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    is_error=True,
                )
                self.log_response(response)  # Log the response before returning
                return response

        response = self.get_error_response(
            message="Invalid token or missing password",
            status="error",
            errors=[],
            error_code="INVALID_CREDENTIALS",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )
        self.log_response(response)  # Log the response before returning
        return response


class ResetPasswordTokenAPIView(APIView, StandardResponseMixin, LoggingMixin):
    permission_classes = (IsAuthenticated,)

    def post(self, request):
        self.log_request(request)  # Log the incoming request
        user = request.user
        # token = request.data.get('token')
        password = request.data.get("password")
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
                response = self.get_response(
                    data={},
                    status="success",
                    message="Password has been successfully reset.",
                    status_code=status.HTTP_200_OK,
                )

                self.log_response(response)  # Log the response before returning
                return response
            except Exception:
                response = self.get_response(
                    message="Something went wrong",
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    is_error=True,
                )
                self.log_response(response)  # Log the response before returning
                return response

        response = self.get_response(
            message="Invalid token or missing password",
            status_code=status.HTTP_401_UNAUTHORIZED,
            is_error=True,
        )
        self.log_response(response)  # Log the response before returning
        return response


class UserProfileViewset(viewsets.ModelViewSet, StandardResponseMixin, LoggingMixin):
    queryset = User.objects.all()
    serializer_class = UserListSerializer
    http_method_names = ["get", "post", "put", "patch", "delete"]

    @action(
        detail=True,
        methods=["delete"],
        url_path="delete_user",
        permission_classes=[IsAuthenticated],
        url_name="delete-user",
    )
    def delete_user(self, request, pk=None):
        try:
            user = self.get_object()
            user_email = user.email
            user_phone_number = user.mobile_number
            user_id = user.id

            with transaction.atomic():
                # ========== DELETE LOGS FIRST (they reference other models) ==========
                # Delete booking-related logs
                BookingInvoiceLog.objects.filter(booking__user=user).delete()
                BookingPaymentLog.objects.filter(booking__user=user).delete()
                BookingRefundLog.objects.filter(booking__user=user).delete()
                
                # Delete user subscription logs (must be deleted before UserSubscription)
                from apps.org_resources.models import UserSubscription
                user_subscriptions = UserSubscription.objects.filter(user=user)
                
                # Delete logs that reference user subscriptions
                UserSubscriptionLogs.objects.filter(user=user).delete()
                for user_sub in user_subscriptions:
                    UserSubscriptionLogs.objects.filter(user_sub=user_sub).delete()
                
                # Delete wallet transaction logs
                WalletTransactionLog.objects.filter(user=user).delete()
                
                # ========== DELETE SUBSCRIPTIONS ==========
                # Delete user subscriptions (after logs are deleted)
                user_subscriptions.delete()
                
                # ========== DELETE BOOKINGS ==========
                # Delete bookings (after logs are deleted)
                Booking.objects.filter(user=user).delete()
                
                # ========== DELETE WALLET-RELATED DATA ==========
                WalletTransaction.objects.filter(user=user).delete()
                Wallet.objects.filter(user=user).delete()
                
                # ========== DELETE CUSTOMER PROFILE ==========
                from apps.customer.models import Customer
                Customer.objects.filter(user=user).delete()
                # Also handle cases where user is the added_user
                Customer.objects.filter(added_user=user).update(added_user=None)
                
                # ========== DELETE PROPERTY-RELATED DATA (if user manages/added properties) ==========
                try:
                    from apps.hotels.models import Property, PayAtHotelSpendLimit
                    # Get properties managed by or added by this user
                    properties_managed = Property.objects.filter(managed_by=user)
                    properties_added = Property.objects.filter(added_by=user)
                    all_properties = (properties_managed | properties_added).distinct()
                    
                    # Delete PayAtHotelSpendLimit records that reference these properties
                    # This must be done BEFORE deleting properties due to DO_NOTHING constraint
                    for property in all_properties:
                        PayAtHotelSpendLimit.objects.filter(property=property).delete()
                    
                    # Properties will be automatically deleted due to CASCADE on managed_by/added_by
                    # But we can also explicitly delete them if needed
                    # all_properties.delete()  # Not needed due to CASCADE, but safe to keep
                except Exception as prop_error:
                    # If Property model doesn't exist or has different structure, continue
                    print(f"Warning: Could not delete property-related data: {prop_error}")
                
                # ========== DELETE OTHER USER-RELATED DATA ==========
                # Delete OTP records
                UserOtp.objects.filter(
                    Q(user_account=user_email) | Q(user_account=user_phone_number)
                ).delete()
                
                # Clear ManyToMany relationships
                user.groups.clear()
                user.roles.clear()
                user.user_permissions.clear()
                
                # ========== DELETE USER ==========
                # Finally, delete the user
                user.delete()
                print(
                    f"Deleted user with ID: {user_id}, Email: {user_email}, Phone: {user_phone_number}"
                )

            return Response(
                {
                    "detail": "User and related data deleted successfully.",
                    "email": user_email,
                    "phone_number": user_phone_number,
                },
                status=status.HTTP_204_NO_CONTENT,
            )

        except Exception as e:
            import traceback
            error_trace = traceback.format_exc()
            print(f"Error deleting user: {str(e)}")
            print(f"Traceback: {error_trace}")
            return Response(
                {"detail": f"Error deleting user: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

    @action(
        detail=False,
        methods=["GET"],
        url_path="detail",
        permission_classes=[IsAuthenticated],
        url_name="user-profile-detail",
    )
    def get_user_profile_detail(self, request):

        user = request.user
        # print("customer profile", user.customer_profile.all())
        userlist_serializer = UserListSerializer(user)
        response = self.get_response(
            data=userlist_serializer.data,
            status="success",
            message="Profile Retrieved",
            status_code=status.HTTP_200_OK,
        )
        return response

    @action(
        detail=False,
        methods=["GET"],
        url_path="referral",
        permission_classes=[IsAuthenticated],
        url_name="referral-link",
    )
    def get_referral_link(self, request):
        user = request.user
        referral_code = user.referral

        if user.default_group == "B2C-GRP":
            signup_link = (
                f"{settings.FRONTEND_URL}/signup/?referral_code={referral_code}"
            )
        elif user.default_group == "BUSINESS-GRP":
            signup_link = (
                f"{settings.FRONTEND_URL}/signup/?referral_code={referral_code}"
            )
        elif user.default_group == "CORPORATE-GRP":
            signup_link = f"{settings.FRONTEND_URL}/corporate-register/?referral_code={referral_code}"
        else:
            signup_link = (
                f"{settings.FRONTEND_URL}/signup/?referral_code={referral_code}"
            )

        data = {"signup_link": signup_link}

        response = self.get_response(
            data=data,
            status="success",
            message="Referral Link",
            status_code=status.HTTP_200_OK,
        )
        return response

    @action(
        detail=False,
        methods=["GET"],
        url_path="referral/summary",
        permission_classes=[IsAuthenticated],
        url_name="referral-summary",
    )
    def get_referral_summary(self, request):
        user_id = request.query_params.get("user", None)
        if not user_id:
            user = request.user
            user_id = user.id
        else:
            user = User.objects.filter(id=user_id).first()

        if not user or not user_id:
            response = self.get_error_response(
                message="Invalid User",
                status="error",
                errors=[],
                error_code="INVALID_USER",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
            return response

        referral = user.referral

        if not referral:
            response = self.get_error_response(
                message="Missing referral code",
                status="error",
                errors=[],
                error_code="MISSING_REFERRAL_CODE",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
            return response

        referred_users = list(
            User.objects.filter(referred_code=referral).values_list("id", flat=True)
        )

        no_of_referred_users = len(referred_users)
        referred_users.append(-1)

        total_amount, credited_user_list = customer_db_utils.get_referral_bonus(
            referred_users, user_id
        )
        if total_amount is None:
            total_amount = 0
        else:
            total_amount = str(total_amount)

        no_of_credited_users = len(credited_user_list)

        data = {
            "no_of_referred_users": no_of_referred_users,
            "no_of_credited_user": no_of_credited_users,
            "total_credited_amount": total_amount,
        }

        response = self.get_response(
            data=data,
            count=1,
            status="success",
            message="Referral Summary",
            status_code=status.HTTP_200_OK,
        )
        return response

    @action(
        detail=False,
        methods=["GET"],
        url_path="referral/users",
        permission_classes=[IsAuthenticated],
        url_name="referral-users",
    )
    def get_referral_user(self, request):
        user_id = request.query_params.get("user", None)
        if not user_id:
            user = request.user
            user_id = user.id
        else:
            user = User.objects.filter(id=user_id).first()

        if not user or not user_id:
            response = self.get_error_response(
                message="Invalid User",
                status="error",
                errors=[],
                error_code="INVALID_USER",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
            return response

        referral = user.referral

        if not referral:
            response = self.get_error_response(
                message="Missing referral code",
                status="error",
                errors=[],
                error_code="MISSING_REFERRAL_CODE",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
            return response

        referred_users = User.objects.filter(referred_code=referral)

        count, referred_users = paginate_queryset(self.request, referred_users)

        credited_user_dict = customer_db_utils.get_credited_referred_user(user_id)
        context = {"credited_user_dict": credited_user_dict}

        serializer = UserRefferalSerializer(referred_users, many=True, context=context)

        ##        referred_users = referred_users.values(
        ##            'id','name', 'email','first_booking')
        ##
        ##        data = {"referred_list":}

        response = self.get_response(
            data=serializer.data,
            count=count,
            status="success",
            message="Referral User List",
            status_code=status.HTTP_200_OK,
        )
        return response

    @action(
        detail=False,
        methods=["POST"],
        url_path="default/group",
        permission_classes=[IsAuthenticated],
        url_name="default-group",
    )
    def update_default_group(self, request):
        self.log_request(request)
        instance = self.request.user
        user_groups = []

        try:
            user_groups = [
                ugroups.get("name", "") for ugroups in instance.groups.values("name")
            ]
        except Exception as e:
            logger.error(f"Error getting user groups: {str(e)}", exc_info=True)

        default_group = request.data.get("default_group", None)

        if instance:
            if not default_group:
                custom_response = self.get_error_response(
                    message="Missing default group",
                    status="error",
                    errors=[],
                    error_code="GROUP_MISSING",
                    status_code=status.HTTP_404_NOT_FOUND,
                )
                self.log_response(custom_response)
                return custom_response

            if not default_group in user_groups:
                custom_response = self.get_error_response(
                    message="Group Not Mapped",
                    status="error",
                    errors=[],
                    error_code="GROUP_MISSING",
                    status_code=status.HTTP_404_NOT_FOUND,
                )
                self.log_response(custom_response)
                return custom_response

            instance.default_group = default_group
            instance.save()

            # Generate new tokens with updated default_group as active_group (same format as login)
            from apps.authentication.tokens import CustomRefreshToken

            try:
                refresh = CustomRefreshToken.for_user(
                    instance, active_group=default_group
                )

                # Invalidate cached groups (user might have switched contexts)
                from apps.authentication.utils.group_utils import (
                    invalidate_user_groups_cache,
                )

                invalidate_user_groups_cache(instance.id)

                # Get user representation with new tokens (same format as login)
                data = authentication_utils.user_representation(
                    instance, refresh_token=refresh
                )
                # Add active_group to response (matching login endpoint format)
                if refresh.get("active_group"):
                    data["user"]["active_group"] = refresh["active_group"]
                else:
                    data["user"]["active_group"] = default_group

                logger.info(
                    f"User {instance.id} updated default group to: {default_group}"
                )

                custom_response = self.get_response(
                    data=data,
                    status="success",
                    message="Default Group Updated",
                    status_code=status.HTTP_200_OK,
                )
                self.log_response(custom_response)
                return custom_response

            except Exception as e:
                logger.error(
                    f"Error generating tokens for user {instance.id}: {str(e)}",
                    exc_info=True,
                )
                return self.get_error_response(
                    message="Failed to update default group. Please try again.",
                    status="error",
                    errors=[],
                    error_code="UPDATE_GROUP_ERROR",
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )
        else:
            custom_response = self.get_error_response(
                message="User Not Found",
                status="error",
                errors=[],
                error_code="USER_MISSING",
                status_code=status.HTTP_404_NOT_FOUND,
            )
            self.log_response(custom_response)
            return custom_response

    @action(
        detail=False,
        methods=["POST"],
        url_path="update-groups-roles",
        permission_classes=[IsAuthenticated],
        url_name="update-groups-roles",
    )
    def update_user_groups_roles(self, request):
        self.log_request(request)

        user_id = request.data.get("user_id", None)

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
                    status_code=status.HTTP_404_NOT_FOUND,
                )
                self.log_response(response)
                return response
        else:
            response = self.get_error_response(
                message="User ID is required",
                status="error",
                errors=[],
                error_code="USER_ID_REQUIRED",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
            self.log_response(response)
            return response

        users_groups = request.data.get("users_groups", [])
        users_roles = request.data.get("users_roles", [])
        removal_groups = request.data.get("removal_groups", [])
        removal_roles = request.data.get("removal_roles", [])

        current_groups = list(user.groups.values_list("name", flat=True))
        current_roles = list(user.roles.values_list("name", flat=True))

        if (
            all(group in current_groups for group in users_groups)
            and all(role in current_roles for role in users_roles)
            and not removal_groups
            and not removal_roles
        ):
            response = self.get_response(
                data=[],
                status="success",
                message="Already existed.",
                status_code=status.HTTP_200_OK,
            )
            self.log_response(response)
            return response

        if removal_groups:
            remaining_groups = [
                group for group in current_groups if group not in removal_groups
            ]
            if not remaining_groups and not users_groups:
                response = self.get_error_response(
                    message="At least one group and role required",
                    status="error",
                    errors=[],
                    error_code="VALIDATION_ERROR",
                    status_code=status.HTTP_400_BAD_REQUEST,
                )
                self.log_response(response)
                return response

            for group_name in removal_groups:
                group = db_utils.get_group_by_name(group_name)
                if group and group in user.groups.all():
                    user.groups.remove(group)

        if removal_roles:
            remaining_roles = [
                role for role in current_roles if role not in removal_roles
            ]
            if not remaining_roles and not users_roles:
                response = self.get_error_response(
                    message="At least one group and role required",
                    status="error",
                    errors=[],
                    error_code="VALIDATION_ERROR",
                    status_code=status.HTTP_400_BAD_REQUEST,
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
        updated_groups = list(user.groups.values_list("name", flat=True))
        updated_roles = list(user.roles.values_list("name", flat=True))

        # Invalidate cached groups since they've changed
        from apps.authentication.utils.group_utils import invalidate_user_groups_cache

        invalidate_user_groups_cache(user.id)

        response_data = {
            "user_id": user.id,
            "email": user.email,
            "groups": updated_groups,
            "roles": updated_roles,
        }

        response = self.get_response(
            data=response_data,
            status="success",
            message="User groups and roles updated successfully",
            status_code=status.HTTP_200_OK,
        )
        self.log_response(response)
        return response

    @action(
        detail=False,
        methods=["POST"],
        url_path="switch-group",
        permission_classes=[IsAuthenticated],
        url_name="switch-group",
        throttle_classes=[SwitchGroupThrottle],
    )
    def switch_active_group(self, request):
        """
        Switch active group and get new tokens with the selected group.
        This allows users to have different active groups in different sessions.

        Security:
        - Validates user belongs to requested group (from database)
        - Validates user account is active
        - Logs all group switch attempts

        Request Body:
            - active_group: Group name to switch to (required)

        Returns:
            New tokens with active_group claim set
        """
        self.log_request(request)

        user = request.user
        active_group = request.data.get("active_group")

        # Input validation
        if not active_group:
            logger.warning(
                f"User {user.id} attempted group switch without active_group"
            )
            return self.get_error_response(
                message="active_group is required",
                status="error",
                errors=[
                    {"field": "active_group", "message": "active_group is required"}
                ],
                error_code="MISSING_ACTIVE_GROUP",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        # Validate active_group format (basic validation)
        if not isinstance(active_group, str) or len(active_group) > 50:
            logger.warning(
                f"User {user.id} provided invalid active_group format: {active_group}"
            )
            return self.get_error_response(
                message="Invalid active_group format",
                status="error",
                errors=[{"field": "active_group", "message": "Invalid format"}],
                error_code="INVALID_FORMAT",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        # Validate that user belongs to this group (from database for security, no cache)
        from apps.authentication.utils.group_utils import validate_user_group_membership

        is_valid, error_msg = validate_user_group_membership(
            user, active_group, use_cache=False
        )

        if not is_valid:
            logger.warning(
                f"User {user.id} attempted to switch to invalid group '{active_group}': {error_msg}"
            )
            return self.get_error_response(
                message=error_msg or f"User does not belong to group: {active_group}",
                status="error",
                errors=[
                    {
                        "field": "active_group",
                        "message": error_msg or f"Invalid group: {active_group}",
                    }
                ],
                error_code="INVALID_GROUP",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        # Generate new tokens with active_group
        from apps.authentication.tokens import CustomRefreshToken

        try:
            refresh = CustomRefreshToken.for_user(user, active_group=active_group)

            # Invalidate cached groups (user might have switched contexts)
            from apps.authentication.utils.group_utils import (
                invalidate_user_groups_cache,
            )

            invalidate_user_groups_cache(user.id)

            # Get user representation with new tokens (same format as login)
            data = authentication_utils.user_representation(user, refresh_token=refresh)
            # Add active_group to response (matching login endpoint format)
            if refresh.get("active_group"):
                data["user"]["active_group"] = refresh["active_group"]
            else:
                data["user"]["active_group"] = active_group

            logger.info(
                f"User {user.id} successfully switched to group: {active_group}"
            )

            response = self.get_response(
                data=data,
                status="success",
                message=f"Active group switched to {active_group}",
                status_code=status.HTTP_200_OK,
            )
            self.log_response(response)
            return response

        except Exception as e:
            logger.error(
                f"Error switching group for user {user.id}: {str(e)}", exc_info=True
            )
            return self.get_error_response(
                message="Failed to switch group. Please try again.",
                status="error",
                errors=[],
                error_code="SWITCH_GROUP_ERROR",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(
        detail=False,
        methods=["post"],
        url_path="billed-to-user",
        permission_classes=[IsAuthenticated],
        url_name="billed-to-user",
    )
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
                    status_code=status.HTTP_400_BAD_REQUEST,
                )

            validated_data = serializer.validated_data
            mobile_number = validated_data["mobile_number"]
            email = validated_data["email"]
            name = validated_data["name"]
            user_group = validated_data["user_group"]

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
                    status_code=status.HTTP_409_CONFLICT,
                )

            # Get group and role based on user_group
            grp, role = authentication_utils.get_group_based_on_name(user_group)
            if not grp or not role:
                return self.get_error_response(
                    message="Group or role doesn't exist",
                    status="error",
                    errors=[],
                    error_code="GROUP_ROLE_NOT_EXIST",
                    status_code=status.HTTP_406_NOT_ACCEPTABLE,
                )

            # Create user within transaction
            with transaction.atomic():
                # Create the user
                user = User.objects.create(
                    email=email,
                    mobile_number=mobile_number,
                    name=name,
                    first_name=name.split(" ")[0] if name else "",
                    last_name=(
                        " ".join(name.split(" ")[1:])
                        if len(name.split(" ")) > 1
                        else ""
                    ),
                    default_group=user_group,
                    is_active=True,
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
                    "id": user.id,
                    "email": user.email,
                    "mobile_number": user.mobile_number,
                    "name": user.name,
                    "user_group": user_group,
                    "groups": [{"id": grp.id, "name": grp.name}] if grp else [],
                    "roles": [{"id": role.id, "name": role.name}] if role else [],
                    "default_group": user.default_group,
                    "created": user.created,
                    "is_active": user.is_active,
                }

                return Response(
                    {
                        "status": "success",
                        "message": "User created successfully for billing",
                        "data": user_data,
                    },
                    status=status.HTTP_201_CREATED,
                )

        except Exception as e:
            return Response(
                {
                    "status": "error",
                    "message": f"Error creating billed user: {str(e)}",
                    "data": {},
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class SocialAuthentication(viewsets.ModelViewSet, StandardResponseMixin, LoggingMixin):
    queryset = User.objects.all()
    serializer_class = UserListSerializer
    http_method_names = ["get", "post", "put", "patch"]

    @action(
        detail=False,
        methods=["POST"],
        url_path="google",
        permission_classes=[],
        url_name="google",
    )
    def google_based_authentication(self, request):
        gtoken = request.data.get("id_token", None)
        referred_code = request.data.get("referred_code", "")
        group_name = request.data.get("group_name", "B2C-GRP")
        mobile_number = request.data.get("mobile_number", "")

        if not gtoken:
            custom_response = self.get_error_response(
                message="Missing token",
                status="error",
                errors=[],
                error_code="TOKEN_MISSING",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
            return custom_response

        token_status, name, email = authentication_utils.validate_google_token(gtoken)
        if not token_status:
            custom_response = self.get_error_response(
                message="Invalid token",
                status="error",
                errors=[],
                error_code="INVALID_TOKEN",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
            return custom_response

        if not email:
            custom_response = self.get_error_response(
                message="Missing Email",
                status="error",
                errors=[],
                error_code="MISSING_EMAIL",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
            return custom_response

        email = email.lower()
        grp, role = authentication_utils.get_group_based_on_name(group_name)
        if not grp or not role:
            custom_response = self.get_error_response(
                message="Group or role doesn't exist",
                status="error",
                errors=[],
                error_code="GROUP_ROLE_NOT_EXIST",
                status_code=status.HTTP_406_NOT_ACCEPTABLE,
            )
            return custom_response

        # mobile uniqueness only within target group
        if mobile_number:
            mobile_group_user = User.objects.filter(
                mobile_number=mobile_number, groups=grp
            ).first()
            if mobile_group_user:
                custom_response = self.get_error_response(
                    message="Mobile already exist",
                    status="error",
                    errors=[],
                    error_code="MOBILE_EXIST",
                    status_code=status.HTTP_406_NOT_ACCEPTABLE,
                )
                return custom_response

        check_existing_user = User.objects.filter(email=email).first()
        if check_existing_user:
            # User exists - handle login or signup to new group
            user_has_group = check_existing_user.groups.filter(id=grp.id).exists()
            
            # If user already has this group, this is a LOGIN
            if user_has_group:
                # Update user details if needed
                if name and not check_existing_user.name:
                    check_existing_user.name = name
                if (
                    mobile_number
                    and not check_existing_user.mobile_number
                    and validate_mobile_number(mobile_number)
                ):
                    check_existing_user.mobile_number = mobile_number
                
                check_existing_user.email_verified = True
                check_existing_user.default_group = group_name
                check_existing_user.save()
                
                # Ensure Customer exists for login
                customer = Customer.objects.filter(user_id=check_existing_user.id).first()
                if not customer:
                    Customer.objects.create(user_id=check_existing_user.id, active=True)
                
                # Check mobile verification
                if not check_existing_user.mobile_verified:
                    mobile = check_existing_user.mobile_number
                    if not mobile or not validate_mobile_number(mobile):
                        # Mobile number is missing - return clear response for frontend
                        custom_response = self.get_response(
                            data={
                                "mobile_required": True,
                                "user_id": check_existing_user.id,
                                "user_email": check_existing_user.email,
                                "has_mobile": False,
                                "mobile_number": None,
                            },
                            status="error",
                            message="Mobile number is required. Please add your mobile number to complete authentication.",
                            status_code=status.HTTP_200_OK,
                        )
                        return custom_response

                    # Mobile exists but not verified - send OTP
                    otp = generate_otp(no_digits=4)
                    authentication_utils.mobile_generate_otp_process(
                        otp, mobile, "LOGIN"
                    )
                    response = self.get_response(
                        data={
                            "mobile_required": True,
                            "mobile_verification_required": True,
                            "user_id": check_existing_user.id,
                            "user_email": check_existing_user.email,
                            "has_mobile": True,
                            "mobile_number": mobile,
                            "otp_sent": True,
                        },
                        status="error",
                        message="Mobile verification required. OTP sent to your mobile number.",
                        status_code=status.HTTP_200_OK,
                    )
                    return response

                # Login successful - generate tokens
                data = authentication_utils.generate_refresh_token(
                    check_existing_user, active_group=group_name
                )
                response = self.get_response(
                    data=data,
                    status="success",
                    message="Login successful",
                    status_code=status.HTTP_200_OK,
                )
                return response
            
            # User exists but doesn't have this group - this is SIGNUP to new group
            # Attach group/role if missing
            if grp and not check_existing_user.groups.filter(id=grp.id).exists():
                check_existing_user.groups.add(grp)
            if role and not check_existing_user.roles.filter(id=role.id).exists():
                check_existing_user.roles.add(role)

            # Update user details if needed
            if name and not check_existing_user.name:
                check_existing_user.name = name
            check_existing_user.default_group = group_name
            check_existing_user.email_verified = True
            if (
                mobile_number
                and not check_existing_user.mobile_number
                and validate_mobile_number(mobile_number)
            ):
                check_existing_user.mobile_number = mobile_number
            check_existing_user.save()
            
            # Ensure Customer exists
            customer = Customer.objects.filter(user_id=check_existing_user.id).first()
            if not customer:
                Customer.objects.create(user_id=check_existing_user.id, active=True)

            # Add signup bonus for new group signup
            authentication_utils.add_signup_bonus(check_existing_user, group_name, role)

            if not check_existing_user.mobile_verified:
                mobile = check_existing_user.mobile_number
                if not mobile or not validate_mobile_number(mobile):
                    # Mobile number is missing - return clear response for frontend
                    custom_response = self.get_response(
                        data={
                            "mobile_required": True,
                            "user_id": check_existing_user.id,
                            "user_email": check_existing_user.email,
                            "has_mobile": False,
                            "mobile_number": None,
                        },
                        status="error",
                        message="Mobile number is required. Please add your mobile number to complete signup.",
                        status_code=status.HTTP_200_OK,
                    )
                    return custom_response

                # Mobile exists but not verified - send OTP
                otp = generate_otp(no_digits=4)
                authentication_utils.mobile_generate_otp_process(
                    otp, mobile, "LOGIN"
                )
                response = self.get_response(
                    data={
                        "mobile_required": True,
                        "mobile_verification_required": True,
                        "user_id": check_existing_user.id,
                        "user_email": check_existing_user.email,
                        "has_mobile": True,
                        "mobile_number": mobile,
                        "otp_sent": True,
                    },
                    status="error",
                    message="Mobile verification required. OTP sent to your mobile number.",
                    status_code=status.HTTP_200_OK,
                )
                return response

            data = authentication_utils.generate_refresh_token(
                check_existing_user, active_group=group_name
            )
            response = self.get_response(
                data=data,
                status="success",
                message="Signup successful - Group added to existing account",
                status_code=status.HTTP_200_OK,
            )
            return response

        # for new user
        new_user = User.objects.create(
            name=name,
            email=email,
            mobile_number=mobile_number,
            referred_code=referred_code,
            default_group=group_name,
            email_verified=True,
            mobile_verified=False,
        )
        Customer.objects.create(user_id=new_user.id, active=True)

        if grp:
            new_user.groups.add(grp)
        if role:
            new_user.roles.add(role)

        authentication_utils.add_signup_bonus(new_user, group_name, role)

        if not new_user.mobile_verified:
            mobile = new_user.mobile_number
            if not mobile or not validate_mobile_number(mobile):
                # Mobile number is missing - return clear response for frontend
                custom_response = self.get_response(
                    data={
                        "mobile_required": True,
                        "user_id": new_user.id,
                        "user_email": new_user.email,
                        "has_mobile": False,
                        "mobile_number": None,
                    },
                    status="error",
                    message="Mobile number is required. Please add your mobile number to complete signup.",
                    status_code=status.HTTP_200_OK,
                )
                return custom_response

            # Mobile exists but not verified - send OTP
            otp = generate_otp(no_digits=4)
            authentication_utils.mobile_generate_otp_process(otp, mobile, "LOGIN")
            response = self.get_response(
                data={
                    "mobile_required": True,
                    "mobile_verification_required": True,
                    "user_id": new_user.id,
                    "user_email": new_user.email,
                    "has_mobile": True,
                    "mobile_number": mobile,
                    "otp_sent": True,
                },
                status="error",
                message="Mobile verification required. OTP sent to your mobile number.",
                status_code=status.HTTP_200_OK,
            )
            return response

        data = authentication_utils.generate_refresh_token(
            new_user, active_group=group_name
        )

        response = self.get_response(
            data=data,
            status="success",
            message="Signup successful",
            status_code=status.HTTP_200_OK,
        )
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
