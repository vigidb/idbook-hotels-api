from .__init__ import *

from apps.hotels.models import PropertyPayoutDetails
from apps.hotels.serializers import PropertyPayoutDetailsSerializer

from apps.hotels.utils.hotel_payout_utils import (
    get_payout_property_details, initiate_payout,
    get_booking_payout_details)

from apps.hotels.utils.db_utils import create_property_payout
from apps.booking.utils.db_utils import update_payout_booking



class PropertyPayoutViewset(viewsets.ModelViewSet, StandardResponseMixin, LoggingMixin):
    queryset = PropertyPayoutDetails.objects.all()
    serializer_class = PropertyPayoutDetailsSerializer

    permission_classes = [IsAuthenticated]    

    def create(self, request, *args, **kwargs):
        self.log_request(request)  # Log the incoming request

        property_ids = request.data.get('property_ids', [])
        purpose = request.data.get('purpose', '')
        transaction_type = request.data.get('transaction_type', '')
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

    def partial_update(self, request, *args, **kwargs):
        
        instance = self.get_object()
        batch_created_by = instance.batch_created_by
        transaction_executed_by = instance.transaction_executed_by
        

        if batch_created_by == 'AUTO' or transaction_executed_by == 'AUTO':
            custom_response = self.get_error_response(
                message="Cannot update payout created or executed automatically",
                status="error", errors=data,error_code="UPDATE_PERMISSION_DENIED",
                status_code=status.HTTP_400_BAD_REQUEST)
            return custom_response
            

        paid = request.data.get('paid', None)
        # transaction_status = request.data.get('transaction_status', '')
        transaction_executed_by = "ADMIN"
        pg_ref_no = request.data.get('pg_ref_no', '')
        transaction_id = request.data.get('transaction_id', '')
        payout_reference_file = request.FILES.get('payout_reference_file')

        if paid is not None:
            instance.paid = paid
        if payout_reference_file:
            instance.payout_reference_file = payout_reference_file
        if transaction_id:
            instance.transaction_id=transaction_id
        if pg_ref_no:
            instance.pg_ref_no=pg_ref_no

        instance.transaction_executed_by = "ADMIN"
        instance.save()

        serializer = PropertyPayoutDetailsSerializer(instance)

        custom_response = self.get_response(
                data=serializer.data,  # Use the data from the default response
                count=1,
                status="success",
                message="Property Updated",
                status_code=status.HTTP_200_OK,  # 200 for successful update
        )
        return custom_response
            

    def list(self, request, *args, **kwargs):
        # paginate the result
        count, self.queryset = paginate_queryset(self.request,  self.queryset)

        serializer = PropertyPayoutDetailsSerializer(self.queryset, many=True)

        custom_response = self.get_response(
            data=serializer.data, count=count, status="success",
            message="payout list",
            status_code=status.HTTP_200_OK)
        return custom_response

    @action(detail=False, methods=['GET'], url_path='pending', 
        url_name='pending', permission_classes=[IsAuthenticated])
    def get_payout_pending_booking_details(self, request):
        property_id = request.query_params.get('property', None)
        
        if not property_id:
            custom_response = self.get_error_response(
                message="Property Missing", status="error",
                errors=[],error_code="PROPERTY_MISSING",
                status_code=status.HTTP_400_BAD_REQUEST)
            return custom_response

        prop_booking_obj, booking_ids, final_payout_amount = get_booking_payout_details(property_id)

        prop_booking_dict = prop_booking_obj.values(
            'id','confirmation_code', 'invoice_id', 'is_direct_pay', 'commission_info__commission',
            'commission_info__commission_type', 'commission_info__tax_percentage', 'commission_info__tax_amount',
            'commission_info__com_amnt',
            'commission_info__com_amnt_withtax', 'commission_info__tcs', 'commission_info__tds',
            'commission_info__hotelier_amount', 'commission_info__hotelier_amount_with_tax',
            'commission_info__is_payment_approved','commission_info__payout_status',
            'commission_info__latest_payout_reference', 'commission_info__final_payout')

        data = {"total_payout_amount":final_payout_amount, "payout_details":prop_booking_dict}

        custom_response = self.get_response(
            data=prop_booking_dict, count=1, status="success", message="pending payout list retrieved",
            status_code=status.HTTP_200_OK
        )
        return custom_response

    @action(detail=False, methods=['POST'], url_path='set-batch-payment', 
        url_name='set-batch-payment', permission_classes=[IsAuthenticated])
    def create_payout_batch(self, request):

        property_id = request.data.get('property', None)

        if not property_id:
            custom_response = self.get_error_response(
                message="Property Missing", status="error",
                errors=[],error_code="PROPERTY_MISSING",
                status_code=status.HTTP_400_BAD_REQUEST)
            return custom_response

        batch_id = "%s" %("BATCH")
        batch_id  = get_unique_id_from_time(batch_id)

        prop_booking_obj, booking_ids, final_payout_amount = get_booking_payout_details(property_id)

##        booking_ids = list(prop_booking_obj.values_list('id', flat=True))
##        print("booking ids", booking_ids)

        if not booking_ids:
            custom_response = self.get_error_response(
                message="No booking associated with hotel payout", status="error",
                errors=[],error_code="BOOKING_UNAVAILABLE",
                status_code=status.HTTP_400_BAD_REQUEST)
            return custom_response

        property_payout_dict={
            "payout_property_id":property_id,
            "amount":final_payout_amount,
            #"transaction_id":merchant_ref_id,
            "batch_id":batch_id,
            #"payment_type":payment_type,
            "booking_list": booking_ids,
            #"payment_medium":payment_medium,
            #"initiate_status":True
            "batch_created_by":"ADMIN"
        }

        # create new payout batch
        payout_obj = create_property_payout(property_payout_dict)
        payout_status = "ASSIGNED"
        latest_payout_reference_id = payout_obj.id
        # update assigned bookings with payout batch
        update_payout_booking(booking_ids, payout_status, latest_payout_reference_id)

        serializer = PropertyPayoutDetailsSerializer(payout_obj)

        custom_response = self.get_response(
            data=serializer.data, count=1, status="success",
            message="pending payout list retrieved",
            status_code=status.HTTP_200_OK)
        return custom_response
