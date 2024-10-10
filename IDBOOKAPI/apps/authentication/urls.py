from django.urls import path, include
from django.contrib.auth import views as auth_views
from apps.authentication.viewsets import *
from rest_framework import routers


router = routers.DefaultRouter()
router.register(r'', UserCreateAPIView, basename='')

user_router = routers.DefaultRouter()
user_router.register(r'profile', UserProfileViewset, basename='profile')

urlpatterns = [
    # path('auth/signup', UserCreateAPIView.as_view(), name='signup'),
    path('auth/login', LoginAPIView.as_view(), name='login'),
    path('auth/logout', LogoutAPIView.as_view(), name='logout'),
    path('auth/forgot-password/', ForgotPasswordAPIView.as_view(), name='forgot-password'),
    path('auth/reset-password/', ResetPasswordAPIView.as_view(), name='reset-password'),
    path('auth/reset-password/token', ResetPasswordTokenAPIView.as_view(), name='reset-password-token'),
    # path('auth/password_reset/', auth_views.PasswordResetView.as_view(), name='password_reset'),
    path('auth/password_reset/done/', auth_views.PasswordResetDoneView.as_view(), name='password_reset_done'),
    path('auth/reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(),
         name='password_reset_confirm'),
    path('auth/reset/done/', auth_views.PasswordResetCompleteView.as_view(), name='password_reset_complete'),
    path('auth/signup/', include(router.urls)),
    path('auth/user/', include(user_router.urls))
]

# path('', include(router.urls)),
