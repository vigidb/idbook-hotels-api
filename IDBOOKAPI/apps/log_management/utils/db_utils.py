from apps.log_management.models import BookingInvoiceLog

def create_booking_invoice_log(log_dict):
    try:
        BookingInvoiceLog.objects.create(**log_dict)
    except Exception as e:
        print(e)
