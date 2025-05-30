from apps.log_management.models import (
    BookingInvoiceLog, BookingPaymentLog,
    WalletTransactionLog, BookingRefundLog,
    UserSubscriptionLogs)
from apps.booking.models import Booking
import traceback

def create_booking_invoice_log(log_dict):
    try:
        BookingInvoiceLog.objects.create(**log_dict)
    except Exception as e:
        print(e)

def create_booking_payment_log(log_dict:dict):
    try:
        BookingPaymentLog.objects.create(**log_dict)
    except Exception as e:
        print(traceback.format_exc())
        print(e)
    

def create_wallet_payment_log(log_dict:dict):
    try:
        WalletTransactionLog.objects.create(**log_dict)
    except Exception as e:
        print(traceback.format_exc())
        print(e)
    
def create_booking_refund_log(log_dict: dict):
    try:
        # Extract booking_id to get the Booking object
        booking_id = log_dict.pop('booking_id', None)
        if booking_id:
            booking = Booking.objects.get(id=booking_id)
            log_dict['booking'] = booking
        
        # BookingRefundLog.objects.create(**log_dict)
        merchant_refund_id = log_dict.get('merchant_refund_id')

        refund_log, created = BookingRefundLog.objects.update_or_create(
            merchant_refund_id=merchant_refund_id,
            defaults=log_dict
        )
    except Exception as e:
        print(traceback.format_exc())
        print(e)

def create_user_subscription_logs(log_dict:dict):
    UserSubscriptionLogs.objects.create(**log_dict)
