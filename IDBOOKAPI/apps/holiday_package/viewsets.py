from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import viewsets
from rest_framework import views, status
from rest_framework.permissions import AllowAny, IsAuthenticated, IsAuthenticatedOrReadOnly
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.generics import (
    CreateAPIView, ListAPIView, GenericAPIView, RetrieveAPIView, UpdateAPIView
)
from IDBOOKAPI.mixins import StandardResponseMixin, LoggingMixin
from IDBOOKAPI.permissions import AnonymousCanViewOnlyPermission
from .serializers import (TourPackageSerializer, AccommodationSerializer, InclusionExclusionSerializer,
VehicleSerializer, DailyPlanSerializer, TourBankDetailSerializer, CustomerTourEnquirySerializer
)
from apps.org_resources.serializers import CompanyDetailSerializer
from apps.org_resources.models import CompanyDetail
from .models import (TourPackage, Accommodation, InclusionExclusion, Vehicle, DailyPlan, TourBankDetail,
                     CustomerTourEnquiry)


class TourPackageViewSet(viewsets.ModelViewSet, StandardResponseMixin, LoggingMixin):
    queryset = TourPackage.objects.all()
    serializer_class = TourPackageSerializer
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
                message="Applied Coupon Created",
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
                message="Applied Coupon Updated",
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



class AccommodationViewSet(viewsets.ModelViewSet, StandardResponseMixin, LoggingMixin):
    queryset = Accommodation.objects.all()
    serializer_class = AccommodationSerializer
    permission_classes = [AnonymousCanViewOnlyPermission,]
    http_method_names = ['get', 'post']

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
                message="Applied Coupon Created",
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
                message="Applied Coupon Updated",
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


class InclusionExclusionViewSet(viewsets.ModelViewSet, StandardResponseMixin, LoggingMixin):
    queryset = InclusionExclusion.objects.all()
    serializer_class = InclusionExclusionSerializer
    permission_classes = [AnonymousCanViewOnlyPermission,]
    http_method_names = ['get', 'post']

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
                message="Applied Coupon Created",
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
                message="Applied Coupon Updated",
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


class VehicleViewSet(viewsets.ModelViewSet, StandardResponseMixin, LoggingMixin):
    queryset = Vehicle.objects.all()
    serializer_class = VehicleSerializer
    permission_classes = [AnonymousCanViewOnlyPermission,]
    http_method_names = ['get', 'post']

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
                message="Applied Coupon Created",
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
                message="Applied Coupon Updated",
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


class DailyPlanViewSet(viewsets.ModelViewSet, StandardResponseMixin, LoggingMixin):
    queryset = DailyPlan.objects.all()
    serializer_class = DailyPlanSerializer
    permission_classes = [AnonymousCanViewOnlyPermission,]
    http_method_names = ['get', 'post']

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
                message="Applied Coupon Created",
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
                message="Applied Coupon Updated",
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


class TourBankDetailViewSet(viewsets.ModelViewSet, StandardResponseMixin, LoggingMixin):
    queryset = TourBankDetail.objects.all()
    serializer_class = TourBankDetailSerializer
    permission_classes = [AnonymousCanViewOnlyPermission,]
    http_method_names = ['get',]

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
                message="Applied Coupon Created",
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
                message="Applied Coupon Updated",
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


class CustomerTourEnquiryViewSet(viewsets.ModelViewSet, StandardResponseMixin, LoggingMixin):
    queryset = CustomerTourEnquiry.objects.all()
    serializer_class = CustomerTourEnquirySerializer
    permission_classes = [AnonymousCanViewOnlyPermission,]
    http_method_names = ['get', 'post']

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
                message="Applied Coupon Created",
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
                message="Applied Coupon Updated",
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


class TourPackageDetailView(APIView):
    def get(self, request, id=None, format=None):
        # Query all the model data
        if id is None:
            # If no id is provided, return data for all TourPackages
            tour_packages = TourPackage.objects.all()
            accommodations = Accommodation.objects.all()
            inclusions_exclusions = InclusionExclusion.objects.all()
            vehicles = Vehicle.objects.all()
            daily_plans = DailyPlan.objects.all()

        else:
            # If id is provided, filter data for the specified TourPackage id
            try:
                tour_packages = TourPackage.objects.filter(id=id)
                accommodations = Accommodation.objects.filter(tour_id=id)
                inclusions_exclusions = InclusionExclusion.objects.filter(tour_id=id)
                vehicles = Vehicle.objects.filter(tour_id=id)
                daily_plans = DailyPlan.objects.filter(tour_id=id)
                # tour_bank_details = TourBankDetail.objects.filter(tour_id=id)
            except TourPackage.DoesNotExist:
                return Response({"error": "TourPackage with the specified id does not exist."}, status=404)

        # static serializers
        tour_bank_details = TourBankDetail.objects.filter(active=True)
        tour_company_details = CompanyDetail.objects.filter(id=1)

        # Serialize the data for each model
        tour_package_serializer = TourPackageSerializer(tour_packages, many=True)
        accommodation_serializer = AccommodationSerializer(accommodations, many=True)
        inclusion_exclusion_serializer = InclusionExclusionSerializer(inclusions_exclusions, many=True)
        vehicle_serializer = VehicleSerializer(vehicles, many=True)
        daily_plan_serializer = DailyPlanSerializer(daily_plans, many=True)
        tour_bank_detail_serializer = TourBankDetailSerializer(tour_bank_details, many=True, context={'request': request})
        tour_company_details_serializer = CompanyDetailSerializer(tour_company_details, many=True, context={'request': request})

        # Combine the serialized data into a single dictionary
        data = {
            'tour_packages': tour_package_serializer.data[0],
            'accommodations': accommodation_serializer.data[0],
            'inclusions_exclusions': inclusion_exclusion_serializer.data,
            'vehicles': vehicle_serializer.data[0],
            'daily_plans': daily_plan_serializer.data,
            'tour_bank_details': tour_bank_detail_serializer.data[0],
            'tour_company_details': tour_company_details_serializer.data[0],
        }

        return Response(data)


#
# from django.http import HttpResponse
# from django.http import request, response
# from django.shortcuts import render, get_object_or_404
# from django.urls import reverse
# import requests
# from django.template.loader import get_template
# from xhtml2pdf import pisa
# from io import BytesIO

#
# def render_tour_packages(request):
#     tour_packages = TourPackage.objects.all()
#     return render(request, 'tour_packages.html', {'tour_packages': tour_packages})
#
#
# def render_tour_package_detail(request, pk):
#     tour_package = get_object_or_404(TourPackage, pk=pk)
#     # Accommodation, InclusionExclusion, Vehicle, DailyPlan
#     #
#     named_url = reverse('tour_package_detail_with_id', args=[pk])
#     # print(named_url)
#
#
#     # Make the HTTP GET request
#     try:
#     	response = requests.get('http://127.0.0.1:8000/' + named_url)
#     except:
# 	    response = requests.get('http://139.59.15.128/' + named_url)
#
#     # Check if the request was successful (status code 200)
#     if response.status_code == 200:
#         # Get the JSON data from the response
#         data = response.json()
#
#         # Now 'data' contains the JSON data returned by the view
#         print(data)
#         return render(request, 'tour_package_detail.html', data)
#     else:
#         # Handle errors if needed
#         print("Error: Unable to fetch data.")
#
#         return render(request, 'tour_package_detail.html', {'tour_package': {}})
#
#
# from django.http import HttpResponse
# from django.template.loader import get_template
# from xhtml2pdf import pisa
#
#
# def pdf_view(request):
#     template = get_template('pdf_template.html')
#     context = {}  # Add any context data if needed
#     html = template.render(context)
#
#     response = HttpResponse(content_type='application/pdf')
#     response['Content-Disposition'] = 'attachment; filename="output.pdf"'
#
#     # Create a PDF using xhtml2pdf
#     pisa.CreatePDF(html, dest=response)
#
#     return response
#
#
# def generate_multipage_pdf(request):
#     # Get the HTML template
#     template = get_template('multiple_page_pdf.html')
#     # template = get_template('complete_page_1.html')
#     context = {}  # Add any context data if needed
#     html = template.render(context)
#
#     # Create a PDF using xhtml2pdf
#     response = HttpResponse(content_type='application/pdf')
#     response['Content-Disposition'] = 'attachment; filename="multipage.pdf"'
#     pisa_status = pisa.CreatePDF(html, dest=response)
#
#     # Check if PDF generation was successful
#     if pisa_status.err:
#         return HttpResponse('Error while generating PDF: %s' % pisa_status.err, content_type='text/plain')
#         # return render(request, 'multiple_page_pdf.html', {'tour_package': {}})
#         # return render(request, 'complete_page_1.html', {'tour_package': {}})
#
#     # return response
#     return render(request, 'multiple_page_pdf.html', {'tour_package': {}})

# def generate_pdf(request):
#     return render(request, 'index.html')

# import os
# import pdfkit
# from pyhtml2pdf import converter
#
# path = os.path.abspath('index.html')
# converter.convert('tour_package_detail', 'sample.pdf')
#
# def generate_pdf(request):
#     # Render the HTML template
#     template = get_template('index.html')
#     context = {'title': 'PDF Generation', 'content': 'This is an example PDF generated from HTML.'}
#     html_content = template.render(context)
#
#     # Create a PDF object and generate the PDF
#     result = BytesIO()
#     pdf = pisa.CreatePDF(html_content, dest=result)
#
#     # Check if the PDF generation was successful
#     if not pdf.err:
#         response = HttpResponse(result.getvalue(), content_type='application/pdf')
#         response['Content-Disposition'] = 'attachment; filename="output.pdf"'
#         return response
#
#     return HttpResponse('PDF generation error: {}'.format(pdf.err))
#
# import pdfkit
#
# def generate_pdf(request, pk):
#     tour_package = get_object_or_404(TourPackage, pk=pk)
#     context = {'tour_package': tour_package}
#
#     # Render HTML template
#     html_content = render(request, 'tour_package_detail.html', context).content.decode('utf-8')
#
#     # Convert HTML to PDF
#     output_pdf_path = 'sample.pdf'
#     # pdfkit.from_string(html_content, output_pdf_path)
#     pdfkit.from_string(html_content, output_pdf_path, options={'base_url': f'http://127.0.0.1:8000/generate_pdf/{pk}'})
#
#     # Set response headers
#     with open(output_pdf_path, 'rb') as pdf_file:
#         response = HttpResponse(pdf_file.read(), content_type='application/pdf')
#     response['Content-Disposition'] = 'attachment; filename="sample.pdf"'
#
#     # Delete the generated PDF file
#     os.remove(output_pdf_path)
#
#     return response
#
# from io import BytesIO
# from django.http import HttpResponse
# from django.template.loader import get_template
# # from xhtml2pdf import pisa
# from django.conf import settings
# from .models import TourPackage
#
# def generate_pdf(request, pk):
#     # Retrieve the TourPackage object based on the pk parameter
#     tour_package = TourPackage.objects.get(pk=pk)
#
#     # Get the HTML template
#     template = get_template('tour_package_detail.html')
#
#     import pdfkit
#
#     # Define path to wkhtmltopdf.exe
#     path_to_wkhtmltopdf = settings.WKHTMLTOPDF_CMD
#
#     # Define url
#     url = f'http://127.0.0.1:8000/generate_pdf/{pk}'
#
#     # Point pdfkit configuration to wkhtmltopdf.exe
#     config = pdfkit.configuration(wkhtmltopdf=path_to_wkhtmltopdf)
#
#     # Convert Webpage to PDF
#     pdf = pdfkit.from_url(url, output_path='webpage.pdf', configuration=config)
#     print(pdf)
#
#     # # Render the template with the tour_package object as context
#     # context = {
#     #     'tour_package': tour_package,
#     # }
#     # html = template.render(context)
#     #
#     # # Create a BytesIO buffer to receive the PDF data
#     # buffer = BytesIO()
#     #
#     # # Create the PDF object using the buffer
#     # pisa.CreatePDF(BytesIO(html.encode("UTF-8")), buffer)
#     #
#     # # Get the buffer's content and create the HttpResponse
#     # pdf = buffer.getvalue()
#     # buffer.close()
#
#     response = HttpResponse(pdf, content_type='application/pdf')
#     response['Content-Disposition'] = 'attachment; filename="tour_package.pdf"'
#     return response

#
# from django.urls import reverse_lazy
# from django.views.generic import CreateView
# from .forms import TourPackageForm, AccommodationFormSet, InclusionExclusionFormSet, VehicleFormSet, DailyPlanFormSet
# from .models import TourPackage
#
#
# class TourPackageCreateView(CreateView):
#     model = TourPackage
#     form_class = TourPackageForm
#     template_name = 'tour_package_create.html'
#     success_url = reverse_lazy('tour_package_list')
#
#     def get_context_data(self, **kwargs):
#         context = super().get_context_data(**kwargs)
#         if self.request.POST:
#             context['accommodation_formset'] = AccommodationFormSet(self.request.POST)
#             context['inclusion_exclusion_formset'] = InclusionExclusionFormSet(self.request.POST)
#             context['vehicle_formset'] = VehicleFormSet(self.request.POST)
#             context['daily_plan_formset'] = DailyPlanFormSet(self.request.POST)
#         else:
#             context['accommodation_formset'] = AccommodationFormSet()
#             context['inclusion_exclusion_formset'] = InclusionExclusionFormSet()
#             context['vehicle_formset'] = VehicleFormSet()
#             context['daily_plan_formset'] = DailyPlanFormSet()
#         return context
#
#     def form_valid(self, form):
#         context = self.get_context_data()
#         accommodation_formset = context['accommodation_formset']
#         inclusion_exclusion_formset = context['inclusion_exclusion_formset']
#         vehicle_formset = context['vehicle_formset']
#         daily_plan_formset = context['daily_plan_formset']
#         self.object = form.save()
#         if (accommodation_formset.is_valid() and inclusion_exclusion_formset.is_valid()
#             and vehicle_formset.is_valid() and daily_plan_formset.is_valid()):
#             accommodation_formset.instance = self.object
#             accommodation_formset.save()
#             inclusion_exclusion_formset.instance = self.object
#             inclusion_exclusion_formset.save()
#             vehicle_formset.instance = self.object
#             vehicle_formset.save()
#             daily_plan_formset.instance = self.object
#             daily_plan_formset.save()
#         return super().form_valid(form)
