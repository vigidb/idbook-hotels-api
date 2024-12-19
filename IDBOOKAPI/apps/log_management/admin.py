from django.contrib import admin
from .models import BookingInvoiceLog, BookingPaymentLog

# Register your models here.

admin.site.register(BookingInvoiceLog)
admin.site.register(BookingPaymentLog)

