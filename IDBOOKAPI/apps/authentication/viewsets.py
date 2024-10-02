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
from .models import User
from apps.customer.models import Customer
from .serializers import (UserSignupSerializer, LoginSerializer,
                          UserListSerializer)
from .emails import send_welcome_email

from rest_framework.decorators import action
from rest_framework import viewsets

User = get_user_model()


def homepage(request):
    from IDBOOKAPI.settings import BASE_URL as HOST
    return HttpResponse(f"Welcome to APIs server please visit <a href='/api/v1/docs'>{HOST}/api/v1/docs</a> or <a href='/api/v1/docs2'>{HOST}/api/v1/docs2</a> ")


class UserCreateAPIView(viewsets.ModelViewSet, StandardResponseMixin, LoggingMixin):
    queryset = User.objects.all()
    serializer_class = UserSignupSerializer
    http_method_names = ['get', 'post', 'put', 'patch']


    def create(self, request, *args, **kwargs):
        self.log_request(request)  # Log the incoming request
        serializer = self.get_serializer(data=request.data)

        if serializer.is_valid():
            user = serializer.save()
            # userlist_serializer = UserListSerializer(user)
            user_data = {'id': user.id,
                         'mobile_number': user.mobile_number if user.mobile_number else '',
                         'email': user.email if user.email else '',
                         'name': user.get_full_name(),
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

    @action(detail=False, methods=['POST'], url_path='customer', url_name='customer-signup',
            permission_classes=[IsAuthenticated])
    def company_based_customer_signup(self, request):
        user_id = request.user.id
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid() and user_id:
            user_serializer = serializer.save()
            customer_id = user_serializer.id
            Customer.objects.create(user_id=customer_id, company_user_id=user_id)
            
            

            data = {'user': serializer.data}
            response = self.get_response(
                data=data,
                status="success",
                message="Signup successful",
                status_code=status.HTTP_200_OK
                )
            return response
        else:
##            response = self.get_response(
##                status="failed",
##                message="Sign Up Failed",
##                status_code=status.HTTP_401_UNAUTHORIZED
##                )
            error_list = []
            errors = serializer.errors
            for field_name, field_errors in serializer.errors.items():
                for ferror in field_errors:
                    error_list.append({"field":field_name, "message": ferror})

            response = self.get_error_response(message="Signup Failed", status="error",
                                               errors=error_list,error_code="VALIDATION_ERROR",
                                               status_code=status.HTTP_401_UNAUTHORIZED)
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

                # Send reset password email
                send_mail(
                    'Reset Password',
                    f'Click the following link to reset your password: {reset_password_link}',
                    settings.DEFAULT_FROM_EMAIL,
                    [email],
                    fail_silently=False,
                )

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
    def post(self, request):
        self.log_request(request)  # Log the incoming request
        token = request.data.get('token')
        password = request.data.get('password')

        if token and password:
            try:
                token_obj = RefreshToken(token)
                user_id = token_obj.get('user_id')
                user = User.objects.get(id=user_id)
                user.set_password(password)
                user.save()

                # Blacklist the token used for password reset
                token.blacklist()
                response = self.get_response(
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

        response = self.get_response(
            message="Invalid token or missing password",
            status_code=status.HTTP_400_BAD_REQUEST,
            is_error=True)
        self.log_response(response)  # Log the response before returning
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

