# routing

from django.urls import re_path

from . import consumers

websocket_urlpatterns = [
    re_path(r"ws/socket/room-availability/(?P<property_id>\w+)/$", consumers.RoomAvailabilityConsumer.as_asgi()),
]
