# database mixins
from django.db.models import Sum

class CommonDbMixins:

    def booking_payment_aggregate(self):
        self.total_booking_amount = 0
        self.total_payment_made = 0

        try:
            # final amount aggregate
            booking_amount_dict = self.queryset.aggregate(Sum('final_amount'))
            self.total_booking_amount = booking_amount_dict.get('final_amount__sum')

            # payment made aggregate
            payment_made_dict = self.queryset.aggregate(Sum('total_payment_made'))
            self.total_payment_made = payment_made_dict.get('total_payment_made__sum')
        except Exception as e:
            print(e)
    
