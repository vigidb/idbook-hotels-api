from apps.hotels.models import (
    Property, Room, PropertyGallery, RoomGallery)


def get_property_by_id(property_id):
    try:
        property_detail = Property.objects.get(id=property_id)
    except Exception as e:
        property_detail = None

    return property_detail

def get_room_by_id(room_id):
    try:
        room_detail = Room.objects.get(id=room_id)
    except Exception as e:
        room_detail = None
    return room_detail

def get_property_gallery(property_id):
    property_gallery = PropertyGallery.objects.filter(property_id=property_id)
    return property_gallery

def get_room_gallery(room_id):
    room_gallery = RoomGallery.objects.filter(room_id=room_id)
    return room_gallery

def get_property_featured_image(property_id):
    property_gallery = PropertyGallery.objects.filter(
        property_id=property_id, featured_image=True).first()
    return property_gallery

def get_rooms_by_property(property_id):
    rooms = Room.objects.filter(property_id=property_id)
    return rooms

def get_property_room_for_booking(property_id:int, room_id:int):
    room_detail = Room.objects.filter(
        id=room_id, property_id=property_id).values(
            'id', 'room_type', 'room_price').first()
    return room_detail
    
    
