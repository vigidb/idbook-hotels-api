from .__init__ import *

from apps.hotels.models import PolicyDetails, Property, PropertyLandmark
from apps.hotels.serializers import (
    PolicySerializer, TopDestinationsSerializer,
    PropertyLandmarkSerializer, PropertyCommissionSerializer, TrendingPlacesSerializer)
from apps.hotels.submodels.related_models import TopDestinations, PropertyCommission, TrendingPlaces
from apps.hotels.utils.db_utils import (
    get_property_count_by_location, is_top_destination_exist, is_property_commission_active, is_trending_place_exist)

from decimal import Decimal

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

        location_name = request.data.get('location_name', '')
        if location_name:
            is_exist = is_top_destination_exist(location_name)
            if is_exist:
                response = self.get_error_response(
                    message="Location already exist", status="error",
                    errors=[],error_code="LOCATION_EXIST",
                    status_code=status.HTTP_400_BAD_REQUEST)
           
                return response

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

        location_name = request.data.get('location_name', '')
        if location_name:
            is_exist = is_top_destination_exist(location_name, exclude_id=instance.id)
            if is_exist:
                response = self.get_error_response(
                    message="Location already exist", status="error",
                    errors=[],error_code="LOCATION_EXIST",
                    status_code=status.HTTP_400_BAD_REQUEST)
           
                return response

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

    @action(detail=False, methods=['PATCH'], url_path='total-hotels',
            url_name='total-hotels', permission_classes=[IsAuthenticated])
    def update_total_hotels(self, request):
        top_destination_objs = self.queryset.filter(active=True)

        for top_destination_obj in top_destination_objs:
            location_name = top_destination_obj.location_name
            total_count = get_property_count_by_location(location_name)
            top_destination_obj.no_of_hotels = total_count
            top_destination_obj.save()

        custom_response = self.get_response(
            data=[], count=0, status="success",
            message="Total count updated",
            status_code=status.HTTP_200_OK,  # 200 for successful update
        )
        return custom_response
        
class PropertyLandmarkViewSet(viewsets.ModelViewSet, StandardResponseMixin, LoggingMixin):
    queryset = PropertyLandmark.objects.all()
    serializer_class = PropertyLandmarkSerializer
    http_method_names = ['get', 'post', 'put', 'patch', 'delete']
    
    permission_classes_by_action = {
        'create': [IsAuthenticated], 
        'update': [IsAuthenticated],
        'partial_update': [IsAuthenticated],
        'destroy': [IsAuthenticated], 
        'list': [AllowAny], 
        'retrieve': [AllowAny]
    }

    def get_permissions(self):
        try: 
            return [permission() for permission in self.permission_classes_by_action[self.action]]
        except KeyError: 
            return [permission() for permission in self.permission_classes]

    def get_queryset(self):
        """
        Optionally restricts the returned landmarks to a given property,
        by filtering against a `property_id` query parameter in the URL.
        """
        queryset = PropertyLandmark.objects.all()
        property_id = self.request.query_params.get('property_id', None)
        
        if property_id is not None:
            queryset = queryset.filter(property=property_id)
            
        return queryset

    def create(self, request, *args, **kwargs):
        self.log_request(request)
        
        # Extract property_id from URL parameters
        property_id = request.query_params.get('property_id', None)
        if property_id and 'property' not in request.data:
            # Add property_id to request data if provided in URL
            request.data['property'] = property_id
        
        # Check if the same landmark with same distance already exists for this property
        property_id = request.data.get('property')
        landmark_name = request.data.get('landmark')
        distance = request.data.get('distance')
        
        if property_id and landmark_name and distance:
            existing_landmark = PropertyLandmark.objects.filter(
                property_id=property_id,
                landmark=landmark_name,
                distance=distance
            ).exists()
            
            if existing_landmark:
                custom_response = self.get_error_response(
                    message="A landmark with the same name and distance already exists for this property", 
                    status="error",
                    errors=["Duplicate landmark"],
                    error_code="DUPLICATE_LANDMARK",
                    status_code=status.HTTP_400_BAD_REQUEST
                )
                self.log_response(custom_response)
                return custom_response
                
        serializer = self.get_serializer(data=request.data)

        if serializer.is_valid():
            response = super().create(request, *args, **kwargs)
            custom_response = self.get_response(
                data=response.data,
                count=1,
                status="success",
                message="Landmark Created",
                status_code=status.HTTP_201_CREATED,
            )
        else:
            serializer_errors = self.custom_serializer_error(serializer.errors)
            custom_response = self.get_error_response(
                message="Validation Error", 
                status="error",
                errors=serializer_errors,
                error_code="VALIDATION_ERROR",
                status_code=status.HTTP_400_BAD_REQUEST
            )

        self.log_response(custom_response)
        return custom_response

    def partial_update(self, request, *args, **kwargs):
        instance = self.get_object()

        landmark_name = request.data.get('landmark', instance.landmark)
        distance = request.data.get('distance', instance.distance)
        property_id = instance.property_id

        existing_landmark = PropertyLandmark.objects.filter(
            property_id=property_id,
            landmark=landmark_name
        ).exclude(id=instance.id).first()

        if existing_landmark:
            # If a landmark with the same name exists, update it instead of creating a new one
            serializer = self.get_serializer(existing_landmark, data=request.data, partial=True)
        else:
            # If no duplicate, update the current landmark
            serializer = self.get_serializer(instance, data=request.data, partial=True)

        if serializer.is_valid():
            serializer.save()
            return self.get_response(
                data=serializer.data,
                count=1,
                status="success",
                message="Landmark Updated",
                status_code=status.HTTP_200_OK,
            )
        
        return self.get_error_response(
            message="Validation Error",
            status="error",
            errors=self.custom_serializer_error(serializer.errors),
            error_code="VALIDATION_ERROR",
            status_code=status.HTTP_400_BAD_REQUEST
        )

        return custom_response
    
    def list(self, request, *args, **kwargs):
        self.log_request(request)
        
        queryset = self.filter_queryset(self.get_queryset())
        
        offset_param = request.query_params.get('offset')
        limit_param = request.query_params.get('limit')
        
        # If pagination parameters are provided, use pagination
        if offset_param is not None or limit_param is not None:
            total_count, paginated_queryset = paginate_queryset(self.request, queryset)
            serializer = self.get_serializer(paginated_queryset, many=True)
            retrieved_count = len(paginated_queryset)
        else:
            serializer = self.get_serializer(queryset, many=True)
            retrieved_count = queryset.count()
        
        custom_response = self.get_response(
            count=retrieved_count,
            status="success",
            data=serializer.data,
            message="Landmarks Retrieved",
            status_code=status.HTTP_200_OK,
        )

        self.log_response(custom_response)
        return custom_response

    def retrieve(self, request, *args, **kwargs):
        self.log_request(request)
        
        try:
            instance = self.get_object()
        except:
            custom_response = self.get_error_response(
                message="Landmark not found", 
                status="error",
                errors=[],
                error_code="LANDMARK_MISSING",
                status_code=status.HTTP_404_NOT_FOUND
            )
            return custom_response
            
        serializer = self.get_serializer(instance)
        
        custom_response = self.get_response(
            count=1, 
            status="success",
            data=serializer.data,
            message="Landmark Retrieved",
            status_code=status.HTTP_200_OK,
        )

        self.log_response(custom_response)
        return custom_response

    def destroy(self, request, *args, **kwargs):
        self.log_request(request)
        
        try:
            instance = self.get_object()
            self.perform_destroy(instance)
            
            custom_response = self.get_response(
                data={},
                count=0,
                status="success",
                message="Landmark Deleted Successfully",
                status_code=status.HTTP_200_OK,
            )
        except Exception as e:
            custom_response = self.get_error_response(
                message=f"Error deleting landmark: {str(e)}", 
                status="error",
                errors=[str(e)],
                error_code="DELETE_ERROR",
                status_code=status.HTTP_400_BAD_REQUEST
            )
            
        self.log_response(custom_response)
        return custom_response

class PropertyCommissionViewSet(viewsets.ModelViewSet, StandardResponseMixin, LoggingMixin):
    queryset = PropertyCommission.objects.all()
    serializer_class = PropertyCommissionSerializer
    permission_classes = [IsAuthenticated]

##    permission_classes_by_action = {'create': [IsAuthenticated], 'update': [IsAuthenticated],
##                                    'partial_update': [IsAuthenticated],
##                                    'destroy': [IsAuthenticated], 'list':[AllowAny], 'retrieve':[AllowAny]}
##
##    def get_permissions(self):
##        try: 
##            return [permission() for permission in self.permission_classes_by_action[self.action]]
##        except KeyError: 
##            # action is not set return default permission_classes
##            return [permission() for permission in self.permission_classes]

    def create(self, request, *args, **kwargs):
        self.log_request(request)  # Log the incoming request

        property_comm = request.data.get('property_comm', None)
        active = request.data.get('active', None)
        if active and property_comm:
            is_comm_active = is_property_commission_active(property_comm)
            if is_comm_active:
                custom_response = self.get_error_response(
                    message="Only one property commission can be active at a time",
                    status="error", errors=[],error_code="ACTIVE_DUPLICATE",
                    status_code=status.HTTP_400_BAD_REQUEST)
                return custom_response
            

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
                message="Property Commission Created",
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
        instance = self.get_object()
        active = instance.active

        active = request.data.get('active', None)
        property_comm = request.data.get('property_comm', None)
        current_property = instance.property_comm_id

        if property_comm and (current_property != property_comm):
            custom_response = self.get_error_response(
                message="Property cannot be updated. You should delete the existing and add new.",
                status="error", errors=[],error_code="PROPERT_UPDATE_ERROR",
                status_code=status.HTTP_400_BAD_REQUEST)
            return custom_response
        
        if active:
            is_comm_active = is_property_commission_active(current_property, instance.id)
            if is_comm_active:
                custom_response = self.get_error_response(
                    message="Only one property commission can be active at a time",
                    status="error", errors=[],error_code="ACTIVE_DUPLICATE",
                    status_code=status.HTTP_400_BAD_REQUEST)
                return custom_response

    # Create an instance of your serializer with the request data and the object to be updated
        serializer = self.get_serializer(instance, data=request.data, partial=True)

        if serializer.is_valid():
            # If the serializer is valid, perform the default update logic
            response = super().partial_update(request, *args, **kwargs)
            #response = self.perform_update(serializer)
            # Create a custom response
            custom_response = self.get_response(
                data=response.data,  # Use the data from the default response
                count=1,
                status="success",
                message="Commission updated",
                status_code=status.HTTP_200_OK,  # 200 for successful update

            )
        else:
            # If the serializer is not valid, create a custom response with error details
            serializer_errors = self.custom_serializer_error(serializer.errors)
            custom_response = self.get_error_response(
                message="Validation Error", status="error",
                errors=serializer_errors,error_code="VALIDATION_ERROR",
                status_code=status.HTTP_400_BAD_REQUEST)

        return custom_response

    def destroy(self, request, *args, **kwargs):
        self.log_request(request)

        instance = self.get_object()
        if instance.active:
            custom_response = self.get_error_response(
                message="Active property commission cannot be deleted",
                status="error", errors=[],error_code="COMMISSION_ACTIVE",
                status_code=status.HTTP_400_BAD_REQUEST)
            return custom_response
            
        self.perform_destroy(instance)
        
        custom_response = self.get_response(
            data={},
            count=0,
            status="success",
            message="Property Commission Deleted Successfully",
            status_code=status.HTTP_200_OK,
        )

        return custom_response
                
            
class TrendingPlacesViewSet(viewsets.ModelViewSet, StandardResponseMixin, LoggingMixin):
    queryset = TrendingPlaces.objects.all()
    serializer_class = TrendingPlacesSerializer
    
    permission_classes_by_action = {
        'create': [IsAuthenticated], 
        'update': [IsAuthenticated],
        'partial_update': [IsAuthenticated],
        'destroy': [IsAuthenticated], 
        'list': [AllowAny], 
        'retrieve': [AllowAny]
    }

    def get_permissions(self):
        try: 
            return [permission() for permission in self.permission_classes_by_action[self.action]]
        except KeyError: 
            return [permission() for permission in self.permission_classes]

    def create(self, request, *args, **kwargs):
        self.log_request(request)

        location_name = request.data.get('location_name', '')
        if location_name:
            is_exist = is_trending_place_exist(location_name)
            if is_exist:
                response = self.get_error_response(
                    message="Location already exists", status="error",
                    errors=[], error_code="LOCATION_EXIST",
                    status_code=status.HTTP_400_BAD_REQUEST)
                return response

        serializer = self.get_serializer(data=request.data)

        if serializer.is_valid():
            response = super().create(request, *args, **kwargs)
            custom_response = self.get_response(
                data=response.data,
                count=1,
                status="success",
                message="Trending Place Created",
                status_code=status.HTTP_201_CREATED,
            )
        else:
            serializer_errors = self.custom_serializer_error(serializer.errors)
            custom_response = self.get_error_response(
                message="Validation Error", 
                status="error",
                errors=serializer_errors,
                error_code="VALIDATION_ERROR",
                status_code=status.HTTP_400_BAD_REQUEST
            )

        self.log_response(custom_response)
        return custom_response

    def list(self, request, *args, **kwargs):
        self.log_request(request)
        active = self.request.query_params.get('active', None)
        if active is not None:
            self.queryset = self.queryset.filter(active=active)
        
        count, self.queryset = paginate_queryset(self.request, self.queryset)

        trending_places_dict = self.queryset.values(
            'id', 'location_name', 'display_name', 'media', 
            'no_of_hotels', 'active'
        )        

        data = {
            "base_url": f"{settings.CDN}{settings.PUBLIC_MEDIA_LOCATION}/",
            "trending_places": trending_places_dict
        }
        
        custom_response = self.get_response(
            count=count,
            data=data,
            message="Trending Places Retrieved",
            status_code=status.HTTP_200_OK,  
        )
        return custom_response

    @action(detail=False, methods=['PATCH'], url_path='total-hotels', 
        url_name='total-hotels', permission_classes=[IsAuthenticated])
    def update_total_hotels(self, request):
        trending_places_objs = self.queryset.filter(active=True)

        for trending_place_obj in trending_places_objs:
            location_name = trending_place_obj.location_name
            total_count = get_property_count_by_location(location_name)  # Fetch hotel count
            trending_place_obj.no_of_hotels = total_count
            trending_place_obj.save()

        custom_response = self.get_response(
            data=[], count=0, status="success",
            message="Total count updated",
            status_code=status.HTTP_200_OK,
        )
        return custom_response

