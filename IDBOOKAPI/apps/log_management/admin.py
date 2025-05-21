from django.contrib import admin
from .models import (
    BookingInvoiceLog, BookingPaymentLog,
    WalletTransactionLog, SmsOtpLog, BookingRefundLog,
    UserSubscriptionLogs, HotelierPayoutLog)

# Register your models here.

class BookingPaymentLogAdmin(admin.ModelAdmin):
    list_display = ('id', 'booking', 'created', 'updated')

class BookingInvoiceLogAdmin(admin.ModelAdmin):
    list_display = ('id', 'booking', 'status_code', 'created', 'updated')

class WalletTransactionLogAdmin(admin.ModelAdmin):
    list_display = ('id', 'user','company','created', 'updated')

class BookingRefundLogAdmin(admin.ModelAdmin):
    list_display = ('id', 'booking', 'merchant_refund_id', 'original_transaction_id', 'refund_amount', 'status', 'created', 'updated')

admin.site.register(BookingInvoiceLog, BookingInvoiceLogAdmin)
admin.site.register(BookingPaymentLog, BookingPaymentLogAdmin)
admin.site.register(WalletTransactionLog, WalletTransactionLogAdmin)
admin.site.register(SmsOtpLog)
admin.site.register(BookingRefundLog, BookingRefundLogAdmin)  # Register the refund log model
admin.site.register(UserSubscriptionLogs)
admin.site.register(HotelierPayoutLog)

