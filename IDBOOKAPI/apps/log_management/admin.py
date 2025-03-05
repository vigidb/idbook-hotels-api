from django.contrib import admin
from .models import (
    BookingInvoiceLog, BookingPaymentLog,
    WalletTransactionLog, SmsOtpLog)

# Register your models here.

class BookingPaymentLogAdmin(admin.ModelAdmin):
    list_display = ('id', 'booking', 'created', 'updated')

class BookingInvoiceLogAdmin(admin.ModelAdmin):
    list_display = ('id', 'booking', 'status_code', 'created', 'updated')

class WalletTransactionLogAdmin(admin.ModelAdmin):
    list_display = ('id', 'user','company','created', 'updated')

admin.site.register(BookingInvoiceLog, BookingInvoiceLogAdmin)
admin.site.register(BookingPaymentLog, BookingPaymentLogAdmin)
admin.site.register(WalletTransactionLog, WalletTransactionLogAdmin)
admin.site.register(SmsOtpLog)

