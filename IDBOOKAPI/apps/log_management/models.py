from django.db import models
from apps.booking.models import Booking

from apps.authentication.models import User
from apps.org_resources.models import CompanyDetail
from IDBOOKAPI.basic_resources import SMS_TYPES_CHOICES

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

class BookingRefundLog(models.Model):
    booking = models.ForeignKey(Booking, on_delete=models.DO_NOTHING,
                               null=True, blank=True,
                               verbose_name="booking_refund_logs")
    merchant_refund_id = models.CharField(
        max_length=150, blank=True, default='')
    original_transaction_id = models.CharField(
        max_length=150, blank=True, default='')
    transaction_id = models.CharField(
        max_length=150, blank=True, default='')
    x_verify = models.CharField(max_length=800, blank=True, default='')
    refund_amount = models.FloatField(default=0)
    status = models.CharField(max_length=50, blank=True, default='initiated')
    response_code = models.CharField(max_length=100, blank=True, default='')
    response_message = models.CharField(max_length=255, blank=True, default='')
    error_message = models.CharField(max_length=255, blank=True, default='')
    request = models.JSONField(blank=True, null=True)
    response = models.JSONField(blank=True, null=True)
    transaction_details = models.JSONField(blank=True, null=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        if self.merchant_refund_id:
            return self.merchant_refund_id
        else:
            return str(self.id)

class WalletTransactionLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.DO_NOTHING,
                             null=True, related_name='wallet_transaction_logs')
    company = models.ForeignKey(CompanyDetail, on_delete=models.DO_NOTHING,
                                null=True, related_name='wallet_company_transaction_logs')
    
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

class SmsOtpLog(models.Model):
    mobile_number = models.CharField(max_length=100, blank=True)
    response =  models.JSONField(blank=True, null=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    
class SmsNotificationLog(models.Model):
    mobile_number = models.CharField(max_length=20)
    response = models.JSONField(blank=True, null=True)
    sms_for = models.CharField(max_length=50, choices=SMS_TYPES_CHOICES, default='other')
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.sms_for} - {self.mobile_number}" 
    
