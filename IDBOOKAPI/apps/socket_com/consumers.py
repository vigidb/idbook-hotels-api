import json

from asgiref.sync import async_to_sync
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async

from apps.hotels.utils.hotel_utils import get_available_room

class RoomAvailabilityConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        self.property_id = self.scope["url_route"]["kwargs"]["property_id"]
        print("connect -------", self.property_id)
        self.room_name = f"room_availability_{self.property_id}"
        print("room name---", self.room_name)
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
            # self.property_id = text_data_json["property"]
            
            room_availability_list = await self.get_room_availability_list()

            # Send message to room group
            await self.channel_layer.group_send(
                self.room_group_name, {"type": "broadcast.message", "room_availability": room_availability_list}
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
        room_availability = event["room_availability"]

        # Send message to WebSocket
        await self.send(text_data=json.dumps({"room_availability": room_availability, "property":int(self.property_id)}))

    
        
