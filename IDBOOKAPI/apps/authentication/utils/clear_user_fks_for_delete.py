"""
Null out FKs pointing at a User when those relations use on_delete=DO_NOTHING.

PostgreSQL will reject DELETE on authentication_user while rows in e.g.
booking_booking still reference user_id unless we clear them first.
"""


def clear_user_fks_for_hard_delete(user_id: int) -> None:
    if not user_id:
        return

    from apps.booking.models import Booking, Query
    from apps.customer.models import Wallet, WalletTransaction
    from apps.log_management.models import UserSubscriptionLogs, WalletTransactionLog

    Booking.objects.filter(user_id=user_id).update(user=None)
    Query.objects.filter(raised_by_id=user_id).update(raised_by=None)
    Query.objects.filter(assigned_to_id=user_id).update(assigned_to=None)
    Query.objects.filter(referred_by_id=user_id).update(referred_by=None)
    Wallet.objects.filter(user_id=user_id).update(user=None)
    WalletTransaction.objects.filter(user_id=user_id).update(user=None)
    WalletTransactionLog.objects.filter(user_id=user_id).update(user=None)
    UserSubscriptionLogs.objects.filter(user_id=user_id).update(user=None)
