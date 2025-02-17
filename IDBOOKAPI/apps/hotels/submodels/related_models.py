from .__init__ import *

from apps.hotels.models import default_room_price_json

class DynamicRoomPricing(models.Model):
    for_property = models.ForeignKey(Property, on_delete=models.CASCADE,
                                     related_name='property_dynamic_pricing')
    for_room = models.ForeignKey(Room, on_delete=models.CASCADE,
                                 related_name='room_dynamic_pricing')
    
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    room_price = models.JSONField(default=default_room_price_json)
    
    active = models.BooleanField(default=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
