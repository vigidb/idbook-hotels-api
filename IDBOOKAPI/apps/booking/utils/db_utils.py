# booking
from apps.booking.models import Booking

def get_booking(booking_id):
    try:
        booking = Booking.objects.get(id=booking_id)
        return booking
    except Exception as e:
        return None
