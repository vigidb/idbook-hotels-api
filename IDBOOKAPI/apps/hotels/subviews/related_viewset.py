from .__init__ import *

from apps.hotels.models import PolicyDetails
from apps.hotels.serializers import PolicySerializer, TopDestinationsSerializer

from apps.hotels.submodels.related_models import TopDestinations

class PropertyPolicyViewSet(viewsets.ModelViewSet, StandardResponseMixin, LoggingMixin):
    queryset = PolicyDetails.objects.all()
    serializer_class = PolicySerializer
    permission_classes = [IsAuthenticated]

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
                count=1,
                status="success",
                message="Policy Created",
                status_code=status.HTTP_201_CREATED,  # 201 for successful creation

            )
        else:
            # If the serializer is not valid, create a custom response with error details
            serializer_errors = self.custom_serializer_error(serializer.errors)
            custom_response = self.get_error_response(message="Validation Error", status="error",
                                                      errors=serializer_errors,error_code="VALIDATION_ERROR",
                                                      status_code=status.HTTP_400_BAD_REQUEST)

        self.log_response(custom_response)  # Log the custom response before returning
        return custom_response

    def partial_update(self, request, *args, **kwargs):
        # self.log_request(request)  # Log the incoming request
        # print(dir(self))
        # Get the object to be updated
        instance = self.get_object()

        # Create an instance of your serializer with the request data and the object to be updated
        serializer = self.get_serializer(instance, data=request.data, partial=True)

        if serializer.is_valid():
            # If the serializer is valid, perform the default update logic
            #response = super().partial_update(request, *args, **kwargs)
            response = self.perform_update(serializer)
            # Create a custom response
            custom_response = self.get_response(
                data=serializer.data,  # Use the data from the default response
                count=1,
                status="success",
                message="Policy Updated",
                status_code=status.HTTP_200_OK,  # 200 for successful update

            )
        else:
            # If the serializer is not valid, create a custom response with error details
            serializer_errors = self.custom_serializer_error(serializer.errors)
            custom_response = self.get_error_response(message="Validation Error", status="error",
                                                      errors=serializer_errors,error_code="VALIDATION_ERROR",
                                                      status_code=status.HTTP_400_BAD_REQUEST)

        # self.log_response(custom_response)  # Log the custom response before returning
        return custom_response

    @action(detail=False, methods=['GET'], url_path='structure',
            url_name='policy-structure', permission_classes=[])
    def get_policy_data_structure(self, request):
        self.log_request(request)
        hotel_policies = {}
        policy_obj = PolicyDetails.objects.filter(active=True).first()
        if policy_obj:
            hotel_policies = policy_obj.policy_details
        
        response = self.get_response(data=hotel_policies, count = 1,
                                     status="success", message="List Hotel Policies Data Structure",
                                     status_code=status.HTTP_200_OK)
        return response

class TopDestinationViewSet(viewsets.ModelViewSet, StandardResponseMixin, LoggingMixin):
    queryset = TopDestinations.objects.all()
    serializer_class = TopDestinationsSerializer
    #permission_classes = [IsAuthenticated]

    permission_classes_by_action = {'create': [IsAuthenticated], 'update': [IsAuthenticated],
                                    'partial_update': [IsAuthenticated],
                                    'destroy': [IsAuthenticated], 'list':[AllowAny], 'retrieve':[AllowAny]}

    def get_permissions(self):
        try: 
            return [permission() for permission in self.permission_classes_by_action[self.action]]
        except KeyError: 
            # action is not set return default permission_classes
            return [permission() for permission in self.permission_classes]

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
                count=1,
                status="success",
                message="Top Destination Created",
                status_code=status.HTTP_201_CREATED,  # 201 for successful creation
            )
        else:
            # If the serializer is not valid, create a custom response with error details
            serializer_errors = self.custom_serializer_error(serializer.errors)
            custom_response = self.get_error_response(message="Validation Error", status="error",
                                                      errors=serializer_errors,error_code="VALIDATION_ERROR",
                                                      status_code=status.HTTP_400_BAD_REQUEST)

        self.log_response(custom_response)  # Log the custom response before returning
        return custom_response

    def partial_update(self, request, *args, **kwargs):
        # self.log_request(request)  # Log the incoming request
        # print(dir(self))
        # Get the object to be updated
        instance = self.get_object()

        # Create an instance of your serializer with the request data and the object to be updated
        serializer = self.get_serializer(instance, data=request.data, partial=True)

        if serializer.is_valid():
            # If the serializer is valid, perform the default update logic
            #response = super().partial_update(request, *args, **kwargs)
            response = self.perform_update(serializer)
            # Create a custom response
            custom_response = self.get_response(
                data=serializer.data,  # Use the data from the default response
                count=1,
                status="success",
                message="Top destination updated",
                status_code=status.HTTP_200_OK,  # 200 for successful update

            )
        else:
            # If the serializer is not valid, create a custom response with error details
            serializer_errors = self.custom_serializer_error(serializer.errors)
            custom_response = self.get_error_response(message="Validation Error", status="error",
                                                      errors=serializer_errors,error_code="VALIDATION_ERROR",
                                                      status_code=status.HTTP_400_BAD_REQUEST)

        # self.log_response(custom_response)  # Log the custom response before returning
        return custom_response

    def list(self, request, *args, **kwargs):
        self.log_request(request)  # Log the incoming request
        active = self.request.query_params.get('active', None)
        if active is not None:
            self.queryset = self.queryset.filter(active=active)
        count, self.queryset = paginate_queryset(self.request, self.queryset)

        top_destination_dict = self.queryset.values(
            'id', 'location_name', 'display_name', 'media', 'no_of_hotels', 'active')        

        data = {"base_url": f"{settings.CDN}{settings.PUBLIC_MEDIA_LOCATION}/","top_destinations": top_destination_dict}
        custom_response = self.get_response(
            count = count,
            data=data,
            message="List Retrieved",
            status_code=status.HTTP_200_OK,  
        )
        return custom_response



    

    

    
