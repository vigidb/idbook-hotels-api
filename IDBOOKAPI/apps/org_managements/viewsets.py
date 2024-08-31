from django.http import HttpResponse
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import Permission, Group
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes
from django.core.mail import send_mail
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import viewsets
from rest_framework import views, status
from rest_framework.permissions import AllowAny, IsAuthenticated, IsAdminUser
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.generics import (
    CreateAPIView, ListAPIView, GenericAPIView, RetrieveAPIView, UpdateAPIView
)


from authentication.models import *
from booking.models import *
from carts.models import *
from coupons.models import *
from customer.models import *
from holiday_package.models import *
from hotel_managements.models import *
from hotels.models import *
from org_managements.models import *
from org_resources.models import *
from payment_gateways.models import *

from .serializers import ORGMUserSerializer


class ORGMUserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = ORGMUserSerializer
    permission_classes = [IsAuthenticated, IsAdminUser, ]
    http_method_names = ['get', ]
