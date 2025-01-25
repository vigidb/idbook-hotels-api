# filter search order mixins
from django.db.models import Q

class PaymentPropertyFilterMixins:

    def payment_property_filter_ops(self):
        filter_dict = {}

        self.queryset = self.queryset.filter(
            Q(booking_payment__booking__isnull=False)
            |Q(booking_payment__booking__isnull=True))
        
        param_dict = self.request.query_params
        for key in param_dict:
            param_value = param_dict[key]

            if key == 'property':
                filter_dict['hotel_booking__confirmed_property'] = param_value
                
            elif key == 'booking_status':
                status_list = param_value.split(',')
                filter_dict['status__in'] = status_list

        
                
        if filter_dict:
            self.queryset = self.queryset.filter(**filter_dict)

