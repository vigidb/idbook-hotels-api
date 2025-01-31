from django.contrib import admin
from .models import BookingInvoiceLog, BookingPaymentLog

# Register your models here.

class BookingPaymentLogAdmin(admin.ModelAdmin):
    list_display = ('id', 'booking', 'created', 'updated')

class BookingInvoiceLogAdmin(admin.ModelAdmin):
    list_display = ('id', 'booking', 'status_code', 'created', 'updated')

admin.site.register(BookingInvoiceLog, BookingInvoiceLogAdmin)
admin.site.register(BookingPaymentLog, BookingPaymentLogAdmin)

