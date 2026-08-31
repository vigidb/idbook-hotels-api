"""
Prepare related rows before deleting Booking instances.

log_management.* models use on_delete=DO_NOTHING toward Booking, which blocks
deletes at the database level. Queries keep a FK to the converted booking;
we clear that so the query remains but is no longer tied to a removed booking.
"""


def detach_booking_related_records(booking_ids: list) -> None:
    """Null out DO_NOTHING FKs and delink queries that point at these bookings."""
    from apps.booking.models import Query
    from apps.log_management.models import (
        BookingInvoiceLog,
        BookingPaymentLog,
        BookingRefundLog,
    )

    ids = sorted({int(i) for i in booking_ids if i is not None})
    if not ids:
        return

    Query.objects.filter(booking_id__in=ids).update(booking=None)

    BookingPaymentLog.objects.filter(booking_id__in=ids).update(booking=None)
    BookingInvoiceLog.objects.filter(booking_id__in=ids).update(booking=None)
    BookingRefundLog.objects.filter(booking_id__in=ids).update(booking=None)
