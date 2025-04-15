from .__init__ import *

from apps.booking.models import Review, BookingPaymentDetail, Booking, Invoice
from apps.booking.serializers import ReviewSerializer, InvoiceSerializer
from apps.booking.utils.db_utils import (
    get_overall_booking_rating, check_review_exist_for_booking,
    update_payment_details)
from apps.log_management.utils.db_utils import create_booking_invoice_log
from apps.booking.utils.invoice_utils import create_invoice_number, manual_generate_invoice_pdf
from apps.hotels.tasks import send_hotel_sms_task
import json

class ReviewViewSet(viewsets.ModelViewSet, StandardResponseMixin, LoggingMixin):
    queryset = Review.objects.all()
    serializer_class = ReviewSerializer
    # permission_classes = [IsAuthenticated,]
    # permission_classes = [AnonymousCanViewOnlyPermission,]
    http_method_names = ['get', 'post', 'put', 'patch', 'delete']

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
            review_id = response.data.get("id")
            if review_id:
                send_hotel_sms_task.apply_async(
                    kwargs={
                        'notification_type': 'HOTELIER_PROPERTY_REVIEW_NOTIFICATION',
                        'params': {
                            'review_id': review_id
                        }
                    }
                )
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

    def partial_update(self, request, *args, **kwargs):
        self.log_request(request)  # Log the incoming request
        # Get the object to be updated
        instance = self.get_object()

        # Create an instance of your serializer with the request data and the object to be updated
        serializer = self.get_serializer(instance, data=request.data, partial=True)

        if serializer.is_valid():
            # If the serializer is valid, perform the default update logic
            #response = super().partial_update(request, *args, **kwargs)
            response = self.perform_update(serializer)
            custom_response = self.get_response(
                status="success",
                count=1,
                data=serializer.data,  # Use the data from the default response
                message="Update success",
                status_code=status.HTTP_200_OK,  # 200 for successful listing
            )
            return custom_response
        else:
            # If the serializer is not valid, create a custom response with error details
            serializer_errors = self.custom_serializer_error(serializer.errors)
            custom_response = self.get_error_response(message="Validation Error", status="error",
                                                      errors=serializer_errors,error_code="VALIDATION_ERROR",
                                                      status_code=status.HTTP_400_BAD_REQUEST)
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

    def destroy(self, request, pk=None):

        instance = self.get_object()
        booking_id = instance.booking_id
        instance.delete()
        Booking.objects.filter(id=booking_id).update(is_reviewed=False)
        custom_response = self.get_response(
            status='success', data=None,
            message="Review deleted successfully",
            status_code=status.HTTP_200_OK,
            )
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
        

class InvoiceViewSet(viewsets.ModelViewSet, StandardResponseMixin, LoggingMixin):
    queryset = Invoice.objects.all()
    serializer_class = InvoiceSerializer
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

    def invoice_filter_ops(self):
        filter_dict = {}
        param_dict = self.request.query_params
        
        # Filter by booking_id, invoice_id or invoice_number
        for key in param_dict:
            if key in ('billed_by', 'billed_to'):
                filter_dict[key] = param_dict[key]
            elif key == 'booking_id':
                bookings = Booking.objects.filter(id=param_dict[key])
                if bookings.exists():
                    filter_dict['invoice_number'] = bookings.first().invoice_id
            elif key == 'invoice_number':
                filter_dict['invoice_number'] = param_dict[key]
            elif key == 'invoice_id':
                filter_dict['id'] = param_dict[key]

        if filter_dict:
            self.queryset = self.queryset.filter(**filter_dict)

    def get_object(self):
        """
        Custom method to retrieve object by ID or invoice_number
        """
        pk = self.kwargs.get('pk')
        
        if isinstance(pk, str) and not pk.isdigit():
            queryset = self.filter_queryset(Invoice.objects.filter(invoice_number=pk))
        else:
            queryset = self.filter_queryset(Invoice.objects.filter(id=pk))
        if not queryset.exists():
            raise ValueError("No invoice found with the given ID or invoice number")
        
        obj = queryset.first()
        return obj

    def create(self, request, *args, **kwargs):
        self.log_request(request)
        
        data = request.data.copy()

        # Check if invoice_number is provided, if not generate one
        if not data.get('invoice_number'):
            data['invoice_number'] = create_invoice_number()

        items = data.get('items', [])
        total = 0
        total_tax = 0
        total_amount = 0

        for item in items:
            # Calculate the price excluding GST
            base_price = item['rate'] * item['quantity']
            
            # Calculate GST
            gst_amount = (item['rate'] * item['gst'] / 100) * item['quantity']
            
            # Calculate the total amount (price + GST)
            item_total = base_price + gst_amount
            
            # Add item totals to the overall totals
            total += base_price
            total_tax += gst_amount
            total_amount += item_total
            
            # Update the item with correct calculated values
            item['amount'] = item_total  # Update with GST included amount

        # Add discount if applicable (keeping discount separate)
        additional_options = data.get('additional_options', {})
        discount_value = additional_options.get('discountValue')
        discount_type = additional_options.get('discountType')
        final_discount = 0

        if additional_options.get('totalDiscount') and discount_value:
            try:
                discount_value = float(discount_value)
                if discount_type == 'AMOUNT':
                    final_discount = discount_value
                elif discount_type == 'PERCENT':
                    final_discount = (discount_value / 100) * total_amount

                data['discount'] = round(final_discount, 2)
            except Exception as e:
                print(f"Discount Calculation Error: {str(e)}")

        # Save the calculated totals in the data dictionary
        data['total'] = total
        data['total_tax'] = total_tax
        data['total_amount'] = total_amount

        # Booking check
        booking_id = data.get('booking_id')
        if booking_id:
            try:
                booking = Booking.objects.get(id=booking_id)
                if booking.invoice_id:
                    return self.get_error_response(
                        message="Invoice already exists for this booking",
                        status="error",
                        errors=[],
                        error_code="DUPLICATE_INVOICE",
                        status_code=status.HTTP_400_BAD_REQUEST
                    )
                data['reference'] = 'Booking'
            except Booking.DoesNotExist:
                return self.get_error_response(
                    message="Booking not found",
                    status="error",
                    errors=[],
                    error_code="BOOKING_NOT_FOUND",
                    status_code=status.HTTP_404_NOT_FOUND
                )

        # Create invoice
        serializer = self.get_serializer(data=data)
        
        if serializer.is_valid():
            invoice = serializer.save()

            if booking_id:
                booking.invoice_id = invoice.invoice_number
                booking.save()
                update_payment_details(booking, invoice)

            try:
                pdf_payload = data.copy()
                pdf_payload['invoiceNumber'] = invoice.invoice_number
                pdf_payload['discount'] = data.get('discount', 0)
                pdf_payload['billed_mob_num'] = data.get('billed_mob_num', '') 
                manual_generate_invoice_pdf(pdf_payload, booking_id)
                invoice.refresh_from_db()
            except Exception as e:
                print(f"PDF Generation Error: {str(e)}")

            return self.get_response(
                status="success",
                data=serializer.data,
                message="Invoice Created",
                status_code=status.HTTP_201_CREATED
            )

        return self.get_error_response(
            message="Validation Error",
            status="error",
            errors=serializer.errors,
            error_code="VALIDATION_ERROR",
            status_code=status.HTTP_400_BAD_REQUEST
        )

    def list(self, request, *args, **kwargs):
        self.log_request(request)
        
        self.invoice_filter_ops()
        count, self.queryset = paginate_queryset(self.request, self.queryset)
        
        response = super().list(request, *args, **kwargs)
        
        if response.status_code == status.HTTP_200_OK:
            custom_response = self.get_response(
                status="success",
                count=count,
                data=response.data,
                message="Invoices Retrieved",
                status_code=status.HTTP_200_OK,
            )
        else:
            custom_response = self.get_error_response(
                message="Error Retrieving Invoices",
                status="error",
                errors=[],
                error_code="RETRIEVAL_ERROR",
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        self.log_response(custom_response)
        return custom_response

    def retrieve(self, request, *args, **kwargs):
        self.log_request(request)
        
        # Perform default retrieval logic
        try:
            response = super().retrieve(request, *args, **kwargs)
            
            custom_response = self.get_response(
                status="success",
                data=response.data,
                message="Invoice Retrieved",
                status_code=status.HTTP_200_OK,
            )
        except Exception as e:
            custom_response = self.get_error_response(
                message=f"Error retrieving invoice: {str(e)}",
                status="error",
                errors=[],
                error_code="RETRIEVAL_ERROR",
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        self.log_response(custom_response)
        return custom_response

    def partial_update(self, request, *args, **kwargs):
        self.log_request(request)

        try:
            instance = self.get_object()  # This might raise ValueError if the invoice is not found
        except ValueError as e:
            return self.get_error_response(
                message="Invoice not found with the given ID or invoice number",
                status="error",
                errors=[],
                error_code="INVOICE_NOT_FOUND",
                status_code=status.HTTP_404_NOT_FOUND
            )

        # Prevent updating invoice_number
        if 'invoice_number' in request.data and request.data['invoice_number'] != instance.invoice_number:
            return self.get_error_response(
                message="Invoice number cannot be updated",
                status="error",
                errors=[],
                error_code="INVOICE_NUMBER_IMMUTABLE",
                status_code=status.HTTP_400_BAD_REQUEST
            )

        data = request.data.copy()

        # Load existing items if not provided in the update payload
        items = data.get('items') or instance.items  # Use existing items if not updating them
        total = 0
        total_tax = 0
        total_amount = 0

        for item in items:
            rate = item['rate']
            quantity = item['quantity']
            gst = item['gst']

            base_price = rate * quantity
            gst_amount = (rate * gst / 100) * quantity
            item_total = base_price + gst_amount

            total += base_price
            total_tax += gst_amount
            total_amount += item_total

            item['amount'] = item_total  # Update item amount in place

        # Add discount if applicable
        additional_options = data.get('additional_options') or instance.additional_options
        discount_value = additional_options.get('discountValue') if additional_options else None
        discount_type = additional_options.get('discountType') if additional_options else None
        final_discount = 0

        if additional_options and additional_options.get('totalDiscount') and discount_value:
            try:
                discount_value = float(discount_value)
                if discount_type == 'AMOUNT':
                    final_discount = discount_value
                elif discount_type == 'PERCENT':
                    final_discount = (discount_value / 100) * total_amount

                data['discount'] = round(final_discount, 2)
            except Exception as e:
                print(f"Discount Calculation Error: {str(e)}")

        # Save recalculated values into the update data
        data['total'] = total
        data['total_tax'] = total_tax
        data['total_amount'] = total_amount
        data['items'] = items 

        # Handle booking reference if booking is present
        booking_id = data.get('booking_id')
        booking = None

        if booking_id:
            try:
                booking = Booking.objects.get(id=booking_id)
            except Booking.DoesNotExist:
                return self.get_error_response(
                    message="Booking not found",
                    status="error",
                    errors=[],
                    error_code="BOOKING_NOT_FOUND",
                    status_code=status.HTTP_404_NOT_FOUND
                )

            if booking.invoice_id != instance.invoice_number:
                return self.get_error_response(
                    message="Invoice does not belong to the specified booking",
                    status="error",
                    errors=[],
                    error_code="INVOICE_MISMATCH",
                    status_code=status.HTTP_400_BAD_REQUEST
                )

        # Update invoice
        serializer = self.get_serializer(instance, data=data, partial=True)

        if serializer.is_valid():
            invoice = serializer.save()

            if booking:
                invoice.reference = 'Booking'
                invoice.save()
                update_payment_details(booking, invoice)

            # if invoice.invoice_pdf:
            #     invoice.invoice_pdf.delete(save=False)
            #     print("json.dumps(data)", json.dumps(data))

            #     manual_generate_invoice_pdf(json.dumps(data), booking_id=booking_id)

            response = self.get_response(
                status="success",
                data=serializer.data,
                message="Invoice Updated",
                status_code=status.HTTP_200_OK
            )
        else:
            response = self.get_error_response(
                message="Validation Error",
                status="error",
                errors=serializer.errors,
                error_code="VALIDATION_ERROR",
                status_code=status.HTTP_400_BAD_REQUEST
            )

        self.log_response(response)

        if booking:
            create_booking_invoice_log({
                'booking': booking,
                'status_code': response.status_code,
                'response': response.data
            })

        return response

    def destroy(self, request, *args, **kwargs):
        self.log_request(request)
        
        # Get the invoice to be deleted
        instance = self.get_object()
        invoice_number = instance.invoice_number
        
        bookings = Booking.objects.filter(invoice_id=invoice_number)
        
        for booking in bookings:
            booking.invoice_id = None
            booking.save()
            
            # Remove invoice references from payment details
            payment_details = BookingPaymentDetail.objects.filter(booking=booking, invoice=instance)
            for payment in payment_details:
                if payment.reference == invoice_number:
                    payment.reference = ''
                payment.invoice = None
                payment.save()
        
        # Delete the invoice
        instance.delete()
        
        custom_response = self.get_response(
            status="success",
            data=None,
            message="Invoice deleted successfully",
            status_code=status.HTTP_200_OK,
        )
        
        self.log_response(custom_response)
        return custom_response

    @action(detail=False, methods=['POST'], url_path='generate-invoice-number', permission_classes=[IsAuthenticated])
    def generate_invoice_number(self, request):
        invoice_number = create_invoice_number()
        data = {"invoice_number": invoice_number}

        custom_response = self.get_response(
            status="success",
            data=data,
            message="Invoice number generated successfully",
            status_code=status.HTTP_200_OK
        )
        return custom_response

