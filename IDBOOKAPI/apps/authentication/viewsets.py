# django import
from django.http import HttpResponse
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.conf import settings
# rest framework import
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.generics import (
    CreateAPIView, ListAPIView, GenericAPIView, RetrieveAPIView, UpdateAPIView
)
from IDBOOKAPI.mixins import StandardResponseMixin, LoggingMixin
from IDBOOKAPI.email_utils import (send_otp_email, send_password_forget_email,
                                   email_validation, get_domain)
from IDBOOKAPI.otp_utils import generate_otp
from .models import User, UserOtp
from apps.customer.models import Customer
from .serializers import (UserSignupSerializer, LoginSerializer,
                          UserListSerializer)
# from .emails import send_welcome_email

from rest_framework.decorators import action
from rest_framework import viewsets
from django.utils import timezone

from apps.org_managements.utils import get_domain_business_details
from apps.customer.utils import db_utils 

from apps.authentication.tasks import (
    send_email_task, customer_signup_link_task)



User = get_user_model()


def homepage(request):
    from IDBOOKAPI.settings import BASE_URL as HOST
    return HttpResponse(f"Welcome to APIs server please visit <a href='/api/v1/docs'>{HOST}/api/v1/docs</a> or <a href='/api/v1/docs2'>{HOST}/api/v1/docs2</a> ")


class UserCreateAPIView(viewsets.ModelViewSet, StandardResponseMixin, LoggingMixin):
    queryset = User.objects.all()
    serializer_class = UserSignupSerializer
    http_method_names = ['get', 'post', 'put', 'patch']

    def get_user_with_tokens(self, user):
        user_data = {'id': user.id, 'mobile_number': user.mobile_number if user.mobile_number else '',
                     'email': user.email if user.email else '', 'name': user.get_full_name(),
                     'roles': [], 'permissions': []}
            
        refresh = RefreshToken.for_user(user)

        data = {'refreshToken': str(refresh), 'accessToken': str(refresh.access_token),
                'expiresIn': 0, 'user': user_data}

        return data


    def create(self, request, *args, **kwargs):
        self.log_request(request)  # Log the incoming request
        serializer = self.get_serializer(data=request.data)

        if serializer.is_valid():
            user = serializer.save()
            customer_id = user.id
            Customer.objects.create(user_id=customer_id, active=True)
            # userlist_serializer = UserListSerializer(user)
            user_data = {'id': user.id,
                         'mobile_number': user.mobile_number if user.mobile_number else '',
                         'email': user.email if user.email else '',
                         'name': user.get_full_name(),
                         'category': user.category,
                         'roles': [],
                         'permissions': []}
            # send welcome email to user
            # send_welcome_email(user.email)
            refresh = RefreshToken.for_user(user)

            data = {'refreshToken': str(refresh),
                    'accessToken': str(refresh.access_token),
                    'expiresIn': 0,
                    'user': user_data,
                    }

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
            customer = db_utils.create_customer_signup_entry(user, added_user=company_user, gender=gender,
                                                             employee_id=employee_id, group_name=group_name,
                                                             department=department)
        else:
            customer = db_utils.check_customer_exist(user.id)
            if not customer:
                customer = db_utils.create_customer_signup_entry(user, added_user=company_user, gender=gender,
                                                                 employee_id=employee_id, group_name=group_name,
                                                                 department=department)
            #user.category = 'CL-CUST'
            user.company_id = company_id
            user.save()

        refresh = RefreshToken.for_user(user)
        customer_signup_token = str(refresh.access_token)

        customer_signup_link = f"{settings.FRONTEND_URL}/signup-link/?token={customer_signup_token}&email={email}"
        print(customer_signup_link)
        customer_signup_link_task.apply_async(args=[customer_signup_link, [email]])

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
        user.save()

        user_data = {'id': user.id,
                     'mobile_number': user.mobile_number if user.mobile_number else '',
                     'email': user.email if user.email else '',
                     'name': user.get_full_name(),
                     'category': user.category,
                     'roles': [],
                     'permissions': []}
            # send welcome email to user
            # send_welcome_email(user.email)
        refresh = RefreshToken.for_user(user)

        data = {'refreshToken': str(refresh),
                'accessToken': str(refresh.access_token),
                'expiresIn': 0,
                'user': user_data,
                }

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
        try:
            to_email = request.data.get('email', '')
            valid = email_validation(to_email)
            if not valid:
                response = self.get_error_response(message="Invalid Email", status="error",
                                                   errors=[], error_code="INVALID_EMAIL",
                                                   status_code=status.HTTP_406_NOT_ACCEPTABLE)
                return response
            
            # generate otp
            otp = generate_otp(no_digits=4)
            # delete any previous otp for the user account
            UserOtp.objects.filter(user_account=to_email).delete()
            # save otp
            UserOtp.objects.create(otp=otp, otp_type='EMAIL', user_account=to_email)
            # send email
            # send_otp_email(otp, [to_email])
            send_email_task.apply_async(args=[otp, [to_email]])
            
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
                            category = "B-USR"
                            new_user = User.objects.create(name=name, email=email, mobile_number=mobile_number,
                                                           business_id=business_id, category=category)
                        else:
                            category = "B-CUST"
                            new_user = User.objects.create(name=name, email=email,
                                                           mobile_number=mobile_number,
                                                           category=category)
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
            data = {'refreshToken': str(refresh),
                    'accessToken': str(refresh.access_token),
                    'expiresIn': 0,
                    'user': serializer.data,
                    }
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
    http_method_names = ['get', 'post', 'put', 'patch']

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

