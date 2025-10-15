from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone
import uuid

from .models import FlightBooking, FlightSearchSession


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
    """Update flight inventory when booking is made"""
    if created and instance.booking_mode == 'INVENTORY':
        # Update inventory availability if using inventory mode
        if instance.selected_flight.inventory_flight:
            inventory = instance.selected_flight.inventory_flight
            flight_class = instance.selected_flight.flight_class
            
            # Decrease available seats based on class
            if flight_class == 'E':
                inventory.economy_available = max(0, inventory.economy_available - 1)
            elif flight_class == 'B':
                inventory.business_available = max(0, inventory.business_available - 1)
            elif flight_class == 'F':
                inventory.first_available = max(0, inventory.first_available - 1)
            
            # Update total available seats
            inventory.available_seats = max(0, inventory.available_seats - 1)
            inventory.booked_seats += 1
            
            # Update status if fully booked
            if inventory.available_seats == 0:
                inventory.status = 'FULL'
            
            inventory.save()


@receiver(post_save, sender=FlightBooking)
def handle_booking_status_change(sender, instance, **kwargs):
    """Handle booking status changes"""
    if instance.status == 'BOOKING_CONFIRMED' and not instance.confirmed_at:
        instance.confirmed_at = timezone.now()
        FlightBooking.objects.filter(id=instance.id).update(confirmed_at=instance.confirmed_at)
    
    if instance.status == 'BOOKING_CANCELLED' and not instance.cancelled_at:
        instance.cancelled_at = timezone.now()
        FlightBooking.objects.filter(id=instance.id).update(cancelled_at=instance.cancelled_at)
        
        # If inventory mode, restore seat availability
        if instance.booking_mode == 'INVENTORY' and instance.selected_flight.inventory_flight:
            inventory = instance.selected_flight.inventory_flight
            flight_class = instance.selected_flight.flight_class
            
            # Increase available seats based on class
            if flight_class == 'E':
                inventory.economy_available += 1
            elif flight_class == 'B':
                inventory.business_available += 1
            elif flight_class == 'F':
                inventory.first_available += 1
            
            # Update total available seats
            inventory.available_seats += 1
            inventory.booked_seats = max(0, inventory.booked_seats - 1)
            
            # Update status if no longer full
            if inventory.status == 'FULL':
                inventory.status = 'ACTIVE'
            
            inventory.save()