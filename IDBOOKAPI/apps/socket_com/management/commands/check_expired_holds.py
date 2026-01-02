"""
Management command to check for expired booking holds and broadcast availability updates.

This should be run periodically (e.g., every minute) via cron or Celery beat to ensure
real-time updates when holds expire.

Usage:
    python manage.py check_expired_holds
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from apps.booking.models import Booking
from apps.socket_com.signals import broadcast_availability_update


class Command(BaseCommand):
    help = 'Check for expired booking holds and broadcast availability updates'

    def handle(self, *args, **options):
        now = timezone.now()
        
        # Find bookings that just expired (within the last minute)
        # This ensures we catch holds that expired since last check
        expired_holds = Booking.objects.filter(
            status="on_hold",
            on_hold_end_time__lt=now,
            on_hold_end_time__gte=now - timedelta(minutes=1),
            booking_type="HOTEL",
        ).select_related('hotel_booking')
        
        count = 0
        for booking in expired_holds:
            try:
                hotel_booking = booking.hotel_booking
                if hotel_booking and hotel_booking.confirmed_property_id:
                    property_id = hotel_booking.confirmed_property_id
                    checkin_time = hotel_booking.confirmed_checkin_time
                    checkout_time = hotel_booking.confirmed_checkout_time
                    
                    if checkin_time and checkout_time:
                        self.stdout.write(
                            f"Broadcasting update for expired hold: Booking {booking.id}, Property {property_id}"
                        )
                        broadcast_availability_update(property_id, checkin_time, checkout_time)
                        count += 1
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"Error processing expired hold {booking.id}: {e}")
                )
        
        self.stdout.write(
            self.style.SUCCESS(f"Processed {count} expired holds")
        )
