from django.db import models
from apps.booking.models import Booking

# Create your models here.

class BookingInvoiceLog(models.Model):
    booking = models.ForeignKey(Booking, on_delete=models.DO_NOTHING,
                                null=True, blank=True,
                                verbose_name="booking_invoice_logs")
    status_code = models.IntegerField(default=0)
    response =  models.JSONField(blank=True, null=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return str(self.booking.id)


class BookingPaymentLog(models.Model):
    booking = models.ForeignKey(Booking, on_delete=models.DO_NOTHING,
                                null=True, blank=True,
                                verbose_name="booking_payment_logs")
    merchant_transaction_id = models.CharField(
        max_length=150, blank=True, default='')
    x_verify = models.CharField(max_length=800,blank=True, default='')
    request = models.JSONField(blank=True, null=True)
    response =  models.JSONField(blank=True, null=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        if self.merchant_transaction_id:
            return self.merchant_transaction_id
        else:
            return str(self.id)
    
