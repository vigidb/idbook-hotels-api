from .__init__ import *


from apps.booking.serializers import (
    PropertyPaymentBookingSerializer, PaymentMediumSerializer)

from apps.booking.mixins.filter_mixins import PaymentPropertyFilterMixins


class PaymentPropertyViewSet(viewsets.ModelViewSet, PaymentPropertyFilterMixins,
                             CommonDbMixins, StandardResponseMixin, LoggingMixin):
    queryset = Booking.objects.all()
    serializer_class = PropertyPaymentBookingSerializer
    permission_classes = [IsAuthenticated, ]
        

    def list(self, request, *args, **kwargs):

        # filter
        booking_payment_filter_enabled = self.payment_property_filter_ops()
        # search
        self.payment_property_search_ops()
        
        # booking payment aggregate
        self.booking_payment_aggregate()
        # payment medium split
        booking_payment_queryset = self.total_payment_mode()
        pmedium_serializer = PaymentMediumSerializer(booking_payment_queryset, many=True)

        booking_payment_agg = {"total_booking_amount": self.total_booking_amount,
                               "total_payment_made": self.total_payment_made,
                               'payment_medium':pmedium_serializer.data}

        
        # combination of booking and booking payment
        if not booking_payment_filter_enabled:
            self.left_join_booking_payment_ops()
    
        self.queryset = self.queryset.order_by('id')
        count, self.queryset = paginate_queryset(self.request,  self.queryset)
        # print("query", self.queryset.query)
        
        # count = self.queryset.count()

        booking_payment_dict = self.queryset.values(
            'id', 'reference_code', 'confirmation_code', 'invoice_id', 'final_amount', 'total_payment_made',
            'hotel_booking__confirmed_checkin_time', 'hotel_booking__confirmed_checkout_time',
            'booking_payment__merchant_transaction_id', 'booking_payment__payment_type',
            'booking_payment__payment_medium', 'booking_payment__amount',
            'booking_payment__is_transaction_success')
        serializer = PropertyPaymentBookingSerializer(booking_payment_dict, many=True)
        
        data = {"payment_aggregate": booking_payment_agg, "booking_payment_details": serializer.data}
        
        
        custom_response = self.get_response(
            status="success",
            data=data,  # Use the data from the default response
            message="List Retrieved",
            count=count,
            status_code=status.HTTP_200_OK,  # 200 for successful listing
            )
        return custom_response

    
