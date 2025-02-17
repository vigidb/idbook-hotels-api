from .__init__ import *

from apps.booking.models import Review
from apps.booking.serializers import ReviewSerializer
from apps.booking.utils.db_utils import (
    get_overall_booking_rating, check_review_exist_for_booking)

class ReviewViewSet(viewsets.ModelViewSet, StandardResponseMixin, LoggingMixin):
    queryset = Review.objects.all()
    serializer_class = ReviewSerializer
    # permission_classes = [IsAuthenticated,]
    # permission_classes = [AnonymousCanViewOnlyPermission,]
    http_method_names = ['get', 'post', 'put', 'patch']

    permission_classes_by_action = {'create': [IsAuthenticated], 'update': [IsAuthenticated],
                                    'partial_update': [IsAuthenticated],
                                    'destroy': [IsAuthenticated], 'list':[AllowAny], 'retrieve':[AllowAny]}

    def get_permissions(self):
        try:
            return [permission() for permission in self.permission_classes_by_action[self.action]]
        except KeyError: 
            # action is not set return default permission_classes
            return [permission() for permission in self.permission_classes]

    def review_filter_ops(self):
        
        filter_dict = {}
        # fetch filter parameters
        param_dict= self.request.query_params
        for key in param_dict:
            if key in ('booking', 'property', 'user'):
                filter_dict[key] = param_dict[key]

        if filter_dict:
            self.queryset = self.queryset.filter(**filter_dict)

        

    def create(self, request, *args, **kwargs):
        self.log_request(request)  # Log the incoming request

        booking_id = request.data.get('booking', None)
        review_exist = check_review_exist_for_booking(booking_id)
        if review_exist:
            custom_response = self.get_error_response(message="Review already done for the booking", status="error",
                                                      errors=[],error_code="DUPLICATE_REVIEW",
                                                      status_code=status.HTTP_400_BAD_REQUEST)
            return custom_response
            

        # Create an instance of your serializer with the request data
        serializer = self.get_serializer(data=request.data)

        if serializer.is_valid():
            # If the serializer is valid, perform the default creation logic
            response = super().create(request, *args, **kwargs)
            # update review created for booking
            Booking.objects.filter(id=booking_id).update(is_reviewed=True)
            # Create a custom response
            custom_response = self.get_response(
                status="success",
                data=response.data,  # Use the data from the default response
                message="Review Created",
                status_code=status.HTTP_201_CREATED,  # 201 for successful creation

            )
        else:
            custom_response = self.get_error_response(message="Validation Error", status="error",
                                                      errors=[],error_code="VALIDATION_ERROR",
                                                      status_code=status.HTTP_400_BAD_REQUEST)

        self.log_response(custom_response)  # Log the custom response before returning
        return custom_response

    def list(self, request, *args, **kwargs):
        self.log_request(request)  # Log the incoming request

        self.review_filter_ops()
        # paginate the result
        count, self.queryset = paginate_queryset(self.request,  self.queryset)

        # Perform the default listing logic
        response = super().list(request, *args, **kwargs)

        if response.status_code == status.HTTP_200_OK:
            # If the response status code is OK (200), it's a successful listing
            custom_response = self.get_response(
                status="success",
                count=count,
                data=response.data,  # Use the data from the default response
                message="List Retrieved",
                status_code=status.HTTP_200_OK,  # 200 for successful listing

            )
        else:
            custom_response = self.get_error_response(message="Validation Error", status="error",
                                                      errors=[],error_code="VALIDATION_ERROR",
                                                      status_code=status.HTTP_400_BAD_REQUEST)

        self.log_response(custom_response)  # Log the custom response before returning
        return custom_response

    def retrieve(self, request, *args, **kwargs):
        self.log_request(request)  # Log the incoming request

        # Perform the default retrieval logic
        response = super().retrieve(request, *args, **kwargs)

        if response.status_code == status.HTTP_200_OK:
            # If the response status code is OK (200), it's a successful retrieval
            custom_response = self.get_response(
                status="success",
                data=response.data,  # Use the data from the default response
                message="Item Retrieved",
                status_code=status.HTTP_200_OK,  # 200 for successful retrieval

            )
        else:
            custom_response = self.get_error_response(message="Validation Error", status="error",
                                                      errors=[],error_code="VALIDATION_ERROR",
                                                      status_code=status.HTTP_400_BAD_REQUEST)

        self.log_response(custom_response)  # Log the custom response before returning
        return custom_response

    @action(detail=False, methods=['POST'], url_path='overall-rating/property',
            url_name='hold', permission_classes=[AllowAny])
    def property_overall_rating(self, request):
        property_id = request.data.get('property', None)

        property_rating_list, agency_review_list = get_overall_booking_rating(property_id)
        data = {"property_overall_rating": property_rating_list,
                "agency_overall_rating": agency_review_list}
        custom_response = self.get_response(
            status="success", data=data, message="Item Retrieved",
            status_code=status.HTTP_200_OK)
        return custom_response
        

    
