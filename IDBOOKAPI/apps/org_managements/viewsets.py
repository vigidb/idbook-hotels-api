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
from IDBOOKAPI.mixins import StandardResponseMixin, LoggingMixin

from .models import BusinessDetail
from apps.authentication.models import User
from rest_framework.decorators import action

##from booking.models import *
##from carts.models import *
##from coupons.models import *
##from customer.models import *
##from holiday_package.models import *
##from hotel_managements.models import *
##from hotels.models import *
##from org_managements.models import *
##from org_resources.models import *
##from payment_gateways.models import *

from .serializers import (ORGMUserSerializer, BusinessDetailSerializer)


class ORGMUserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = ORGMUserSerializer
    permission_classes = [IsAuthenticated, IsAdminUser, ]
    http_method_names = ['get', ]

class BusinessDetailViewSet(viewsets.ModelViewSet, StandardResponseMixin, LoggingMixin):
    queryset = BusinessDetail.objects.all()
    serializer_class = BusinessDetailSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ['get', 'post', 'put', 'patch']

    def create(self, request, *args, **kwargs):
        user_id = request.user.id
        self.log_request(request) # log the incoming request
        # Create an instance of your serializer with the request data
        #serializer = self.get_serializer(data=request.data, context={'user_id': user_id})
        serializer = self.get_serializer(data=request.data)

        if serializer.is_valid():
            # If the serializer is valid, perform the default creation logic
            response = super().create(request, *args, **kwargs)

            # Create a custom response
            custom_response = self.get_response(
                status='success',
                data=response.data,  # Use the data from the default response
                message="Business Details Updated",
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
                status='success',
                data=response.data,  # Use the data from the default response
                message="Business Details Updated",
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
            

    
    @action(detail=False, methods=['GET'], url_path='user/retrieve', url_name='user-retrieve')
    def user_based_retrieve(self, request):
        try:
            business_detail = BusinessDetail.objects.get(user=request.user)
            serializer = BusinessDetailSerializer(business_detail)
            custom_response = self.get_response(
                status="success",
                data=serializer.data,
                status_code=status.HTTP_200_OK)
        except Exception as e:
            print(e)
            # self.log_response(e)
            custom_response = self.get_response(
                data={},  
                status_code=status.HTTP_400_BAD_REQUEST,  
            )
             
        return custom_response
   
