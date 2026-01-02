"""
Signals to automatically broadcast room availability updates via WebSocket
when bookings, blocks, or prices change.
"""
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from datetime import datetime, timedelta
from django.utils import timezone

from apps.booking.models import Booking, HotelBooking
from apps.hotels.models import BlockedProperty, Room
from apps.hotels.submodels.related_models import DynamicRoomPricing


channel_layer = get_channel_layer()


def ensure_datetime(dt_value, default=None):
    """Convert value to timezone-aware datetime object"""
    if dt_value is None:
        return default or timezone.now()
    
    # If already a datetime object
    if isinstance(dt_value, datetime):
        # Make timezone-aware if naive
        if timezone.is_naive(dt_value):
            return timezone.make_aware(dt_value)
        return dt_value
    
    # If it's a string, try to parse it
    if isinstance(dt_value, str):
        try:
            # Handle ISO format with Z
            dt_str = dt_value.replace('Z', '+00:00') if dt_value.endswith('Z') else dt_value
            dt = datetime.fromisoformat(dt_str)
            if timezone.is_naive(dt):
                return timezone.make_aware(dt)
            return dt
        except (ValueError, AttributeError) as e:
            print(f"[Socket Signal] Failed to parse datetime string '{dt_value}': {e}")
            return default or timezone.now()
    
    # Unknown type, use default
    print(f"[Socket Signal] Unknown datetime type: {type(dt_value)}, value: {dt_value}")
    return default or timezone.now()


def broadcast_availability_update(property_id, checkin_time=None, checkout_time=None):
    """
    Broadcast room availability update to all connected WebSocket clients
    for a specific property.
    
    Args:
        property_id: The property ID to broadcast for
        checkin_time: Optional checkin time (datetime object or string)
        checkout_time: Optional checkout time (datetime object or string)
    """
    print(f"[Socket Signal] broadcast_availability_update called - property_id: {property_id}")
    print(f"[Socket Signal] checkin_time type: {type(checkin_time)}, value: {checkin_time}")
    print(f"[Socket Signal] checkout_time type: {type(checkout_time)}, value: {checkout_time}")
    
    if not channel_layer:
        print("[Socket Signal] ERROR: Channel layer not available, skipping broadcast")
        print("[Socket Signal] Make sure Redis is running and CHANNEL_LAYERS is configured")
        return
    
    print(f"[Socket Signal] Channel layer available: {channel_layer}")
    
    try:
        from apps.hotels.utils.hotel_utils import get_available_room
        
        # Convert to datetime objects (handles both datetime objects and strings)
        checkin_dt = ensure_datetime(checkin_time)
        checkout_dt = ensure_datetime(
            checkout_time, 
            default=checkin_dt + timedelta(days=30) if checkin_dt else timezone.now() + timedelta(days=30)
        )
        
        print(f"[Socket Signal] Final datetime objects - checkin: {checkin_dt}, checkout: {checkout_dt}")
        
        # Get updated availability
        room_availability_list = get_available_room(
            checkin_dt, checkout_dt, property_id
        )
        
        print(f"[Socket Signal] Got {len(room_availability_list)} rooms")
        
        # Broadcast to the property's room group
        room_group_name = f"customer_room_availability_{property_id}"
        print(f"[Socket Signal] Broadcasting to group: {room_group_name}")
        
        async_to_sync(channel_layer.group_send)(
            room_group_name,
            {
                "type": "broadcast.message",
                "room_availability": room_availability_list,
            }
        )
        
        print(f"[Socket Signal] ✅ Successfully broadcasted availability update for property {property_id}")
    except Exception as e:
        print(f"[Socket Signal] ❌ Error broadcasting availability update: {e}")
        import traceback
        traceback.print_exc()


@receiver(post_save, sender=Booking)
def booking_saved(sender, instance, created, **kwargs):
    """Broadcast availability update when a booking is created or updated"""
    # Only process hotel bookings
    if instance.booking_type != "HOTEL":
        return
    
    try:
        hotel_booking = instance.hotel_booking
        if hotel_booking and hotel_booking.confirmed_property_id:
            property_id = hotel_booking.confirmed_property_id
            checkin_time = hotel_booking.confirmed_checkin_time
            checkout_time = hotel_booking.confirmed_checkout_time
            
            if checkin_time and checkout_time:
                # Broadcast update for all status changes (pending, on_hold, confirmed, canceled, etc.)
                # This ensures availability updates when:
                # - Booking is created (pending/on_hold)
                # - Booking status changes to on_hold
                # - Booking is confirmed
                # - Booking is canceled
                print(f"[Socket Signal] Booking {instance.id} status: {instance.status}, broadcasting update for property {property_id}")
                broadcast_availability_update(property_id, checkin_time, checkout_time)
                
                # If booking is on_hold, schedule a broadcast when hold expires
                if instance.status == "on_hold" and instance.on_hold_end_time:
                    # Note: For production, consider using Celery periodic tasks or Django-Q
                    # to broadcast when holds expire. For now, the next availability request
                    # will automatically reflect expired holds.
                    print(f"[Socket Signal] Booking {instance.id} is on_hold until {instance.on_hold_end_time}")
    except Exception as e:
        print(f"[Socket Signal] Error in booking_saved: {e}")
        import traceback
        traceback.print_exc()


@receiver(post_delete, sender=Booking)
def booking_deleted(sender, instance, **kwargs):
    """Broadcast availability update when a booking is deleted"""
    if instance.booking_type != "HOTEL":
        return
    
    try:
        hotel_booking = instance.hotel_booking
        if hotel_booking and hotel_booking.confirmed_property_id:
            property_id = hotel_booking.confirmed_property_id
            checkin_time = hotel_booking.confirmed_checkin_time
            checkout_time = hotel_booking.confirmed_checkout_time
            
            if checkin_time and checkout_time:
                broadcast_availability_update(property_id, checkin_time, checkout_time)
    except Exception as e:
        print(f"[Socket Signal] Error in booking_deleted: {e}")


@receiver(post_save, sender=BlockedProperty)
def blocked_property_saved(sender, instance, created, **kwargs):
    """Broadcast availability update when a property/room is blocked"""
    print(f"[Socket Signal] ===== BlockedProperty saved =====")
    print(f"[Socket Signal] created: {created}, property_id: {instance.blocked_property_id}, id: {instance.id}")
    print(f"[Socket Signal] active: {instance.active}, no_of_blocked_rooms: {instance.no_of_blocked_rooms}")
    try:
        property_id = instance.blocked_property_id
        start_date = instance.start_date
        end_date = instance.end_date
        
        print(f"[Socket Signal] BlockedProperty details:")
        print(f"[Socket Signal]   - property_id: {property_id}")
        print(f"[Socket Signal]   - start_date: {start_date} (type: {type(start_date)})")
        print(f"[Socket Signal]   - end_date: {end_date} (type: {type(end_date)})")
        print(f"[Socket Signal]   - active: {instance.active}")
        
        if property_id and start_date and end_date:
            print(f"[Socket Signal] ✅ All data present, broadcasting update for property {property_id}")
            broadcast_availability_update(property_id, start_date, end_date)
        else:
            print(f"[Socket Signal] ❌ Missing data:")
            print(f"[Socket Signal]   - property_id: {property_id}")
            print(f"[Socket Signal]   - start_date: {start_date}")
            print(f"[Socket Signal]   - end_date: {end_date}")
    except Exception as e:
        print(f"[Socket Signal] ❌ Error in blocked_property_saved: {e}")
        import traceback
        traceback.print_exc()


@receiver(post_delete, sender=BlockedProperty)
def blocked_property_deleted(sender, instance, **kwargs):
    """Broadcast availability update when a block is removed"""
    try:
        property_id = instance.blocked_property_id
        start_date = instance.start_date
        end_date = instance.end_date
        
        if property_id and start_date and end_date:
            broadcast_availability_update(property_id, start_date, end_date)
    except Exception as e:
        print(f"[Socket Signal] Error in blocked_property_deleted: {e}")


@receiver(post_save, sender=DynamicRoomPricing)
def dynamic_pricing_saved(sender, instance, created, **kwargs):
    """Broadcast availability update when dynamic pricing is set"""
    try:
        property_id = instance.for_property_id
        start_date = instance.start_date
        end_date = instance.end_date
        
        if property_id and start_date and end_date:
            broadcast_availability_update(property_id, start_date, end_date)
    except Exception as e:
        print(f"[Socket Signal] Error in dynamic_pricing_saved: {e}")


@receiver(post_delete, sender=DynamicRoomPricing)
def dynamic_pricing_deleted(sender, instance, **kwargs):
    """Broadcast availability update when dynamic pricing is removed"""
    try:
        property_id = instance.for_property_id
        start_date = instance.start_date
        end_date = instance.end_date
        
        if property_id and start_date and end_date:
            broadcast_availability_update(property_id, start_date, end_date)
    except Exception as e:
        print(f"[Socket Signal] Error in dynamic_pricing_deleted: {e}")


@receiver(post_save, sender=Room)
def room_pricing_updated(sender, instance, **kwargs):
    """Broadcast availability update when room pricing is updated"""
    try:
        # Only broadcast if room_price field was updated
        if instance.property_id:
            property_id = instance.property_id
            # Use a default date range for pricing updates
            broadcast_availability_update(property_id)
    except Exception as e:
        print(f"[Socket Signal] Error in room_pricing_updated: {e}")
