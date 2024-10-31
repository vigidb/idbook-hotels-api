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
