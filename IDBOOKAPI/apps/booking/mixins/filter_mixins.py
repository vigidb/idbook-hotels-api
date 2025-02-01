# filter search order mixins
from django.db.models import Q

class PaymentPropertyFilterMixins:

    def payment_property_filter_ops(self):
        filter_dict = {}
        booking_payment_filter_enabled = False

        param_dict = self.request.query_params
        for key in param_dict:
            param_value = param_dict[key]

            if key == 'property':
                filter_dict['hotel_booking__confirmed_property'] = param_value
                
            elif key == 'booking_status':
                status_list = param_value.split(',')
                filter_dict['status__in'] = status_list
            elif key == 'start_checkin_date':
                start_checking_date = param_value.replace(' ', '+')
                filter_dict['hotel_booking__confirmed_checkin_time__gte'] = start_checking_date
            elif key == 'end_checkin_date':
                end_checkin_date = param_value.replace(' ', '+')
                filter_dict['hotel_booking__confirmed_checkin_time__lte'] = end_checkin_date
            elif key == 'is_transaction_success':
                is_transaction_success = True if param_value == "true" else False
                filter_dict['booking_payment__is_transaction_success'] = is_transaction_success
                booking_payment_filter_enabled = True

                
        if filter_dict:
            self.queryset = self.queryset.filter(**filter_dict)

        return booking_payment_filter_enabled

    def payment_property_search_ops(self):
        search_value = self.request.query_params.get('search', '')
        if search_value:
            self.queryset = self.queryset.filter(Q(reference_code__icontains=search_value))
            

    def left_join_booking_payment_ops(self):

        self.queryset = self.queryset.filter(
            Q(booking_payment__booking__isnull=False)
            |Q(booking_payment__booking__isnull=True))
        

