from apps.hotels.models import Room, Property
from apps.hotels.utils.db_utils import (
    get_slot_based_starting_room_price,
    update_property_with_starting_price)


def change_json_12hr_price():
    rooms = Room.objects.all()
    for room in rooms:
        try:
            room_json = room.room_price
            room_json['price_12hrs'] = room_json.pop('price_12_hrs')
            room.room_price = room_json
            room.save()
            print(room.id)
        except Exception as e:
            print(e)


def update_property_starting_price():
    property_list = list(Property.objects.values_list('id', flat=True))
    for property_id in property_list:
        starting_price_details = get_slot_based_starting_room_price(property_id)
        update_property_with_starting_price(
            property_id, starting_price_details)
        
