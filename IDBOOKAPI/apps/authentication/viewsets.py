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
from .serializers import (UserSignupSerializer, LoginSerializer,
                          UserListSerializer)
from .emails import send_welcome_email

User = get_user_model()


def homepage(request):
    from IDBOOKAPI.settings import BASE_URL as HOST
    return HttpResponse(f"Welcome to APIs server please visit <a href='/api/v1/docs'>{HOST}/api/v1/docs</a> or <a href='/api/v1/docs2'>{HOST}/api/v1/docs2</a> ")


class UserCreateAPIView(CreateAPIView, StandardResponseMixin, LoggingMixin):
    serializer_class = UserSignupSerializer


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
##            token = {
##                             'refresh': str(refresh),
##                             'access': str(refresh.access_token)
##                         }
            data = {'refreshToken': str(refresh),
                    'accessToken': str(refresh.access_token),
                    'expiresIn': 0,
                    'user': user_data,
                    }
##            response = self.get_response(
##                data=[serializer.data, token],
##                message="User Created",
##                status_code=status.HTTP_200_OK,
##                )
            response = self.get_response(
                data=data,
                status="success",
                message="Signup successful",
                status_code=status.HTTP_200_OK,
                )
            self.log_response(response)  # Log the response before returning
            return response
        else:
            errors = serializer.errors
            data = {
                "password": errors.get('password', [])[0] if 'password' in errors else "",
                "email": errors.get('email',[])[0] if 'email' in errors else "",
                "mobile_number": errors.get('mobile_number', [])[0] if 'mobile_number' in errors else "",
                "roles": errors.get('roles', []) if 'roles' in errors else ""
            }
            response = self.get_response(
                data=[serializer.data],
                message=data,
                status_code=status.HTTP_401_UNAUTHORIZED,
                is_error=True)
            self.log_response(response)  # Log the response before returning
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
            errors = serializer.errors
            response = self.get_response(
                data=[serializer.data],
                message=errors['non_field_errors'][0],
                status_code=status.HTTP_401_UNAUTHORIZED,
                is_error=True)
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

