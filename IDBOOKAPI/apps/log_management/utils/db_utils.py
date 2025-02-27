from apps.log_management.models import (
    BookingInvoiceLog, BookingPaymentLog,
    WalletTransactionLog)
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
    
