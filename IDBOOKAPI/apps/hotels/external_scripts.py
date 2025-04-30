from apps.hotels.models import Room, Property
from apps.hotels.utils.db_utils import (
    get_slot_based_starting_room_price,
    update_property_with_starting_price,
    get_slot_price_enabled_property)
from apps.hotels.utils.hotel_utils import process_property_confirmed_booking_total
from apps.hotels.submodels.related_models import PropertyCommission


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

def update_property_slot_price():
    property_list = get_slot_price_enabled_property()
    print(property_list)
    data = Property.objects.filter(id__in=property_list).update(is_slot_price_enabled=True)
    print(data)

def update_property_confirmed_booking():
    property_ids = list(Property.objects.values_list('id', flat=True))
    for pid in property_ids:
        process_property_confirmed_booking_total(pid)

def check_property_coordinates():
    objs = Property.objects.values(
        'id','address__coordinates__lat', 'address__coordinates__lng').exclude(
            address__coordinates__lat='', address__coordinates__lng='')
    for obj in objs:
        try:
            s = float(obj.get('address__coordinates__lat'))
            s1 = float(obj.get('address__coordinates__lng'))
        except Exception as e:
            print(e)
            print(obj.get('id'))
        
def create_or_update_property_commissions():
    for prop in Property.objects.all():
        commission_code = f"Idb_comm_{prop.id}"
        commission_obj, created = PropertyCommission.objects.update_or_create(
            property_comm=prop,
            defaults={
                "code": commission_code,
                "commission_type": "PERCENT",
                "commission": 20.0,
                "active": True
            }
        )
        if created:
            print(f"Created commission for Property ID {prop.id}")
        else:
            print(f"Updated commission for Property ID {prop.id}") 
    
        
