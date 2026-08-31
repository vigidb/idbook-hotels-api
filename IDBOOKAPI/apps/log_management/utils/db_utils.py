from apps.log_management.models import (
    BookingInvoiceLog,
    BookingPaymentLog,
    WalletTransactionLog,
    BookingRefundLog,
    UserSubscriptionLogs,
    HotelierPayoutLog,
)
from apps.booking.models import Booking
from apps.authentication.models import User
from apps.org_resources.models import CompanyDetail, AgentDetail
import traceback


def create_booking_invoice_log(log_dict):
    try:
        BookingInvoiceLog.objects.create(**log_dict)
    except Exception as e:
        print(e)


def create_booking_payment_log(log_dict: dict):
    try:
        BookingPaymentLog.objects.create(**log_dict)
    except Exception as e:
        print(traceback.format_exc())
        print(e)


def create_wallet_payment_log(log_dict: dict):
    try:
        # Convert ID fields to ForeignKey objects
        log_dict_clean = log_dict.copy()
        
        # Convert user_id to user object
        if 'user_id' in log_dict_clean:
            user_id = log_dict_clean.pop('user_id')
            if user_id:
                try:
                    log_dict_clean['user'] = User.objects.get(id=user_id)
                except User.DoesNotExist:
                    pass  # Skip if user doesn't exist
        
        # Convert company_id to company object
        if 'company_id' in log_dict_clean:
            company_id = log_dict_clean.pop('company_id')
            if company_id:
                try:
                    log_dict_clean['company'] = CompanyDetail.objects.get(id=company_id)
                except CompanyDetail.DoesNotExist:
                    pass  # Skip if company doesn't exist
        
        # Convert agent_id to agent object
        if 'agent_id' in log_dict_clean:
            agent_id = log_dict_clean.pop('agent_id')
            if agent_id:
                try:
                    log_dict_clean['agent'] = AgentDetail.objects.get(id=agent_id)
                except AgentDetail.DoesNotExist:
                    pass  # Skip if agent doesn't exist
        
        WalletTransactionLog.objects.create(**log_dict_clean)
    except Exception as e:
        print(traceback.format_exc())
        print(e)


def create_booking_refund_log(log_dict: dict):
    try:
        # Extract booking_id to get the Booking object
        booking_id = log_dict.pop("booking_id", None)
        if booking_id:
            booking = Booking.objects.get(id=booking_id)
            log_dict["booking"] = booking

        # BookingRefundLog.objects.create(**log_dict)
        merchant_refund_id = log_dict.get("merchant_refund_id")

        refund_log, created = BookingRefundLog.objects.update_or_create(
            merchant_refund_id=merchant_refund_id, defaults=log_dict
        )
    except Exception as e:
        print(traceback.format_exc())
        print(e)


def create_user_subscription_logs(log_dict: dict):
    UserSubscriptionLogs.objects.create(**log_dict)


def create_hotelier_payout_log(log_dict: dict):
    HotelierPayoutLog.objects.create(**log_dict)
