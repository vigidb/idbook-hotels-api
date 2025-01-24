from .__init__ import *

from apps.booking.models import Booking
from apps.booking.serializers import PropertyPaymentBookingSerializer

from apps.booking.mixins.filter_mixins import PaymentPropertyFilterMixins
from apps.booking.mixins.booking_db_mixins import CommonDbMixins

class PaymentPropertyViewSet(viewsets.ModelViewSet, PaymentPropertyFilterMixins,
                             CommonDbMixins, StandardResponseMixin, LoggingMixin):
    queryset = Booking.objects.all()
    serializer_class = PropertyPaymentBookingSerializer
    permission_classes = []
        

    def list(self, request, *args, **kwargs):

        # filter
        self.payment_property_filter_ops()
        
        # booking payment aggregate
        self.booking_payment_aggregate()
        booking_payment_agg = {"total_booking_amount": self.total_booking_amount,
                               "total_payment_made": self.total_payment_made}

        self.queryset = self.queryset.order_by('id')
        count = self.queryset.count()

        booking_payment_dict = self.queryset.values(
            'id', 'reference_code', 'confirmation_code', 'invoice_id',
            'hotel_booking__confirmed_checkin_time', 'hotel_booking__confirmed_checkout_time',
            'booking_payment__merchant_transaction_id', 'booking_payment__payment_type',
            'booking_payment__payment_medium', 'booking_payment__amount',
            'booking_payment__is_transaction_success')
        serializer = PropertyPaymentBookingSerializer(booking_payment_dict, many=True)
        
        
        custom_response = self.get_response(
            status="success",
            data=serializer.data,  # Use the data from the default response
            message="List Retrieved",
            count=count,
            status_code=status.HTTP_200_OK,  # 200 for successful listing
            )
        return custom_response

    
