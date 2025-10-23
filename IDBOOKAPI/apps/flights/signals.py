from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone
import uuid
import logging

from .models import FlightSearchSession
from apps.booking.models import FlightBooking


@receiver(pre_save, sender=FlightBooking)
def generate_booking_reference(sender, instance, **kwargs):
    """Generate unique booking reference if not already set"""
    if not instance.booking_reference:
        # Generate booking reference in format: FB + YYYYMMDD + 4 random chars
        date_str = timezone.now().strftime('%Y%m%d')
        random_suffix = str(uuid.uuid4())[:4].upper()
        instance.booking_reference = f"FB{date_str}{random_suffix}"


@receiver(pre_save, sender=FlightSearchSession)
def generate_search_session_id(sender, instance, **kwargs):
    """Generate unique session ID if not already set"""
    if not instance.session_id:
        instance.session_id = str(uuid.uuid4())


@receiver(post_save, sender=FlightBooking)
def update_inventory_on_booking(sender, instance, created, **kwargs):
    """Update flight inventory when booking is made (only when inventory context is available)."""
    try:
        if created and instance.booking_mode == 'INVENTORY':
            selected_flight = getattr(instance, 'selected_flight', None)
            if not selected_flight or not getattr(selected_flight, 'inventory_flight', None):
                return
            inventory = selected_flight.inventory_flight
            flight_class = getattr(selected_flight, 'flight_class', 'E')
            if flight_class == 'E':
                inventory.economy_available = max(0, inventory.economy_available - 1)
            elif flight_class == 'B':
                inventory.business_available = max(0, inventory.business_available - 1)
            elif flight_class == 'F':
                inventory.first_available = max(0, inventory.first_available - 1)
            inventory.available_seats = max(0, inventory.available_seats - 1)
            inventory.booked_seats += 1
            if inventory.available_seats == 0:
                inventory.status = 'FULL'
            inventory.save()
    except Exception:
        logger = logging.getLogger(__name__)
        logger.exception("Inventory update on booking failed")


@receiver(post_save, sender=FlightBooking)
def handle_booking_status_change(sender, instance, **kwargs):
    """Handle booking status changes"""
    try:
        if instance.status in ['BOOKING_CONFIRMED', 'CONFIRMED'] and not instance.confirmed_at:
            instance.confirmed_at = timezone.now()
            FlightBooking.objects.filter(id=instance.id).update(confirmed_at=instance.confirmed_at)
        
        if instance.status in ['BOOKING_CANCELLED', 'CANCELLED'] and not instance.cancelled_at:
            instance.cancelled_at = timezone.now()
            FlightBooking.objects.filter(id=instance.id).update(cancelled_at=instance.cancelled_at)
            
            if instance.booking_mode == 'INVENTORY':
                selected_flight = getattr(instance, 'selected_flight', None)
                if selected_flight and getattr(selected_flight, 'inventory_flight', None):
                    inventory = selected_flight.inventory_flight
                    flight_class = getattr(selected_flight, 'flight_class', 'E')
                    if flight_class == 'E':
                        inventory.economy_available += 1
                    elif flight_class == 'B':
                        inventory.business_available += 1
                    elif flight_class == 'F':
                        inventory.first_available += 1
                    inventory.available_seats += 1
                    inventory.booked_seats = max(0, inventory.booked_seats - 1)
                    if inventory.status == 'FULL':
                        inventory.status = 'ACTIVE'
                    inventory.save()
    except Exception:
        logger = logging.getLogger(__name__)
        logger.exception("Post-save booking status handler failed")
