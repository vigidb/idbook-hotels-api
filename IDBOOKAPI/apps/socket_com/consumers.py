import json

from asgiref.sync import async_to_sync
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async

from apps.hotels.utils.hotel_utils import get_available_room

class RoomAvailabilityConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        self.room_name = "room_availability"
        self.room_group_name = f"customer_{self.room_name}"
        
        # Join room group
        await self.channel_layer.group_add(self.room_group_name, self.channel_name)

        await self.accept()
    
    async def disconnect(self, close_code):
        # Leave room group
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    # Receive message from WebSocket
    async def receive(self, text_data):
        try:
            text_data_json = json.loads(text_data)
            self.confirmed_checkin_time = text_data_json["confirmed_checkin_time"]
            self.confirmed_checkout_time = text_data_json["confirmed_checkout_time"]
            self.property_id = text_data_json["property"]
            
            room_availability_list = await self.get_room_availability_list()

            # Send message to room group
            await self.channel_layer.group_send(
                self.room_group_name, {"type": "broadcast.message", "message": room_availability_list}
            )
        except Exception as e:
            print(e)

    @database_sync_to_async
    def get_room_availability_list(self):
        room_availability_list = get_available_room(
            self.confirmed_checkin_time, self.confirmed_checkout_time,
            self.property_id)
        return room_availability_list 
    

    # Receive message from room group
    async def broadcast_message(self, event):
        message = event["message"]

        # Send message to WebSocket
        await self.send(text_data=json.dumps({"message": message}))

    
        
