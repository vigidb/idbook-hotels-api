import json
from datetime import datetime
from django.utils import timezone

from asgiref.sync import async_to_sync
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async

from apps.hotels.utils.hotel_utils import get_available_room


class RoomAvailabilityConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        self.property_id = self.scope["url_route"]["kwargs"]["property_id"]
        print(f"[Socket] Connected to property_id: {self.property_id}")
        
        # Validate property exists and is active
        property_valid = await self.validate_property()
        if not property_valid:
            await self.close(code=4004)  # Invalid property
            return
        
        self.room_name = f"room_availability_{self.property_id}"
        self.room_group_name = f"customer_{self.room_name}"

        # Join room group
        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()
        print(f"[Socket] Connection accepted for {self.room_group_name}")
    
    @database_sync_to_async
    def validate_property(self):
        """Validate that property exists and is active"""
        from apps.hotels.utils.db_utils import get_property_by_id
        
        try:
            property_obj = get_property_by_id(self.property_id)
            if not property_obj:
                print(f"[Socket] Property {self.property_id} does not exist")
                return False
            
            if property_obj.status != "Active":
                print(f"[Socket] Property {self.property_id} is not active (status: {property_obj.status})")
                return False
            
            print(f"[Socket] Property {self.property_id} validated - status: {property_obj.status}")
            return True
        except Exception as e:
            print(f"[Socket] Error validating property: {e}")
            return False

    async def disconnect(self, close_code):
        # Leave room group
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)
        print(f"[Socket] Disconnected from {self.room_group_name}")

    def parse_datetime_string(self, date_string):
        """Parse ISO datetime string to datetime object, handling various formats"""
        if isinstance(date_string, datetime):
            return date_string
        
        if not isinstance(date_string, str):
            raise ValueError(f"Invalid date format: {date_string} (expected string)")
        
        # Handle common ISO formats
        formats = [
            "%Y-%m-%dT%H:%M:%SZ",  # ISO with Z (UTC)
            "%Y-%m-%dT%H:%M:%S.%fZ",  # ISO with microseconds and Z
            "%Y-%m-%dT%H:%M:%S%z",  # ISO with timezone offset
            "%Y-%m-%dT%H:%M:%S.%f%z",  # ISO with microseconds and timezone
            "%Y-%m-%dT%H:%M:%S",  # ISO without timezone
            "%Y-%m-%dT%H:%MZ",  # ISO without seconds, with Z
            "%Y-%m-%dT%H:%M%z",  # ISO without seconds, with timezone
            "%Y-%m-%dT%H:%M",  # ISO without seconds and timezone
        ]
        
        # Replace Z with +00:00 for timezone-aware parsing
        if date_string.endswith('Z'):
            date_string = date_string[:-1] + '+00:00'
        
        for fmt in formats:
            try:
                # Try parsing with timezone
                if '%z' in fmt or '+00:00' in date_string:
                    # Parse as timezone-aware
                    if '+00:00' in date_string:
                        # Replace +00:00 with +0000 for strptime
                        date_string_parsed = date_string.replace('+00:00', '+0000')
                        fmt_parsed = fmt.replace('%z', '%z').replace('+00:00', '+0000')
                        try:
                            dt = datetime.strptime(date_string_parsed, fmt_parsed.replace('%z', '%z'))
                            # Make timezone-aware
                            return timezone.make_aware(dt)
                        except:
                            # Try simpler approach
                            dt = datetime.fromisoformat(date_string.replace('Z', '+00:00'))
                            return timezone.make_aware(dt) if timezone.is_naive(dt) else dt
                    else:
                        dt = datetime.strptime(date_string, fmt)
                        return timezone.make_aware(dt) if timezone.is_naive(dt) else dt
                else:
                    # Parse as naive datetime, then make aware
                    dt = datetime.strptime(date_string, fmt)
                    return timezone.make_aware(dt)
            except (ValueError, AttributeError):
                continue
        
        # Last resort: try fromisoformat (Python 3.7+)
        try:
            dt = datetime.fromisoformat(date_string.replace('Z', '+00:00'))
            return timezone.make_aware(dt) if timezone.is_naive(dt) else dt
        except ValueError:
            raise ValueError(f"Could not parse datetime string: {date_string}")

    # Receive message from WebSocket
    async def receive(self, text_data):
        try:
            print(f"[Socket] Received message: {text_data}")
            text_data_json = json.loads(text_data)
            
            # Validate required fields
            if "confirmed_checkin_time" not in text_data_json:
                await self.send_error("Missing required field: confirmed_checkin_time")
                return
            
            if "confirmed_checkout_time" not in text_data_json:
                await self.send_error("Missing required field: confirmed_checkout_time")
                return
            
            # Parse datetime strings
            try:
                self.confirmed_checkin_time = self.parse_datetime_string(
                    text_data_json["confirmed_checkin_time"]
                )
                self.confirmed_checkout_time = self.parse_datetime_string(
                    text_data_json["confirmed_checkout_time"]
                )
                print(f"[Socket] Parsed checkin: {self.confirmed_checkin_time}, checkout: {self.confirmed_checkout_time}")
            except ValueError as e:
                await self.send_error(f"Invalid date format: {str(e)}")
                return
            
            # Validate date range
            if self.confirmed_checkin_time >= self.confirmed_checkout_time:
                await self.send_error("Checkout time must be after checkin time")
                return
            
            # Validate dates are not in the past
            now = timezone.now()
            if self.confirmed_checkin_time < now:
                await self.send_error("Check-in time cannot be in the past")
                return
            
            if self.confirmed_checkout_time < now:
                await self.send_error("Check-out time cannot be in the past")
                return
            
            # Calculate duration to determine if it's a slot booking
            duration = self.confirmed_checkout_time - self.confirmed_checkin_time
            duration_hours = duration.total_seconds() / 3600
            
            # Store booking type for response
            if duration_hours <= 4:
                self.booking_type = "4 Hrs"
            elif duration_hours <= 8:
                self.booking_type = "8 Hrs"
            elif duration_hours <= 12:
                self.booking_type = "12 Hrs"
            else:
                self.booking_type = "24 Hrs"
            
            print(f"[Socket] Booking type detected: {self.booking_type} (duration: {duration_hours:.2f} hours)")

            # Get room availability
            room_availability_list = await self.get_room_availability_list()
            print(f"[Socket] Found {len(room_availability_list)} rooms")

            # Send message to room group (which will broadcast to all clients)
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type": "broadcast.message",
                    "room_availability": room_availability_list,
                },
            )
        except json.JSONDecodeError as e:
            await self.send_error(f"Invalid JSON: {str(e)}")
        except Exception as e:
            error_msg = f"Error processing request: {str(e)}"
            print(f"[Socket] {error_msg}")
            import traceback
            traceback.print_exc()
            await self.send_error(error_msg)

    async def send_error(self, error_message):
        """Send error message to client"""
        await self.send(
            text_data=json.dumps({
                "error": error_message,
                "property": int(self.property_id),
            })
        )

    @database_sync_to_async
    def get_room_availability_list(self):
        room_availability_list = get_available_room(
            self.confirmed_checkin_time, self.confirmed_checkout_time, self.property_id
        )
        return room_availability_list

    # Receive message from room group
    async def broadcast_message(self, event):
        room_availability = event.get("room_availability", [])
        
        print(f"[Socket] ===== broadcast_message called =====")
        print(f"[Socket] property_id: {self.property_id}")
        print(f"[Socket] room_availability count: {len(room_availability)}")
        
        # Check if this is an automatic update (no date range in event)
        # or a manual request (has date range stored in instance)
        response_data = {
            "room_availability": room_availability,
            "property": int(self.property_id),
        }
        
        # Include date range if this was a manual request
        if hasattr(self, 'confirmed_checkin_time') and hasattr(self, 'confirmed_checkout_time'):
            response_data["checkin_time"] = self.confirmed_checkin_time.isoformat()
            response_data["checkout_time"] = self.confirmed_checkout_time.isoformat()
            if hasattr(self, 'booking_type'):
                response_data["booking_type"] = self.booking_type
            print(f"[Socket] Manual request - including date range")
        else:
            response_data["auto_update"] = True
            print(f"[Socket] Auto update - no date range")

        # Send message to WebSocket
        await self.send(
            text_data=json.dumps(response_data)
        )
        print(f"[Socket] ✅ Sent availability data for {len(room_availability)} rooms (auto_update: {response_data.get('auto_update', False)})")