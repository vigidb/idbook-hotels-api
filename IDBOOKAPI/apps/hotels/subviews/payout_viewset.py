from .__init__ import *

from apps.hotels.models import PropertyPayoutDetails
from apps.hotels.serializers import PropertyPayoutDetailsSerializer
from apps.hotels.utils.hotel_payout_utils import (
    get_payout_property_details, initiate_payout)

class PropertyPayoutViewset(viewsets.ModelViewSet, StandardResponseMixin, LoggingMixin):
    queryset = PropertyPayoutDetails.objects.all()
    serializer_class = PropertyPayoutDetailsSerializer

    permission_classes = [IsAuthenticated]

    def create(self, request, *args, **kwargs):
        self.log_request(request)  # Log the incoming request

        property_ids = request.data.get('property_ids', [])
        purpose = request.data.get('purpose', '')
        payment_type = request.data.get('payment_type', '')
        payment_medium = request.data.get('payment_medium', '')
        data = {"payout_success":[], "payout_error":[]}
        
        if not property_ids:
            custom_response = self.get_error_response(
                message="Property Missing", status="error",
                errors=[],error_code="PROPERTY_MISSING",
                status_code=status.HTTP_400_BAD_REQUEST)
            return custom_response
        
        payload, property_payout_list, batch_id = get_payout_property_details(property_ids)
        payout_response = initiate_payout(payload,  property_payout_list, payment_medium, batch_id)
        payout_status = payout_response.get('status')
        if payout_status == "partial_success" or payout_status == "success":
            payout_success_list = payout_response.get('payout_success_list')
            payout_error_list = payout_response.get('payout_error_list')

            if payout_success_list:
                payout_success_obj = PropertyPayoutDetails.objects.filter(id__in=payout_success_list)
                payout_success_serializer = PropertyPayoutDetailsSerializer(payout_success_obj, many=True)
                data["payout_success"] = payout_success_serializer.data

            if payout_error_list:
                payout_error_obj = PropertyPayoutDetails.objects.filter(id__in=payout_error_list)
                payout_error_serializer = PropertyPayoutDetailsSerializer(payout_error_obj, many=True)
                data["payout_error"] = payout_error_serializer.data

            
            custom_response = self.get_response(
                data=data,
                count=1,
                status=payout_status,
                message="Request Initiated",
                status_code=status.HTTP_201_CREATED,  # 201 for successful creation
            )
        else:
            payout_error_list = payout_response.get('payout_error_list', [])
            data = []
            
            if payout_error_list:
                payout_error_obj = PropertyPayoutDetails.objects.filter(id__in=payout_error_list)
                payout_error_serializer = PropertyPayoutDetailsSerializer(payout_error_obj, many=True)
                data = payout_error_serializer.data
                
            custom_response = self.get_error_response(
                message="Initiation Error", status="error",
                errors=data,error_code="INITIATE_ERROR",
                status_code=status.HTTP_400_BAD_REQUEST)

        return custom_response
            

        

    
    
    
    
