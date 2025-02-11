from apps.hotels.models import (
    Property, Room, PropertyGallery,
    RoomGallery, FavoriteList)

from django.db.models.fields.json import KT
from django.db.models import Min, Max
from django.db.models import IntegerField
from django.db.models.functions import Cast
from django.db.models import Q


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

def get_total_rooms(room_id):
    room_detail = Room.objects.get(id=room_id)
    if room_detail:
        return room_detail.no_available_rooms
    return 0

def get_property_gallery(property_id):
    property_gallery = PropertyGallery.objects.filter(property_id=property_id, active=True)
    return property_gallery

def get_room_gallery(room_id):
    room_gallery = RoomGallery.objects.filter(room_id=room_id, active=True)
    return room_gallery

def get_property_featured_image(property_id):
    property_gallery = PropertyGallery.objects.filter(
        property_id=property_id, featured_image=True, active=True).first()
    return property_gallery

def get_rooms_by_property(property_id):
    rooms = Room.objects.filter(property_id=property_id)
    return rooms

def get_property_room_for_booking(property_id:int, room_id:int):
    room_detail = Room.objects.filter(
        id=room_id, property_id=property_id).values(
            'id', 'room_type', 'room_price').first()
    return room_detail

def get_favorite_property(user_id):
    favorite_list = FavoriteList.objects.filter(
        user_id=user_id, property__isnull=False).values_list('property_id', flat=True)
    return list(favorite_list)

def get_starting_room_price(property_id):
    try:
        starting_price = Room.objects.annotate(val=KT('room_price__base_rate')).filter(
            property_id=property_id).aggregate(min=Min('val'))
        sprice = starting_price.get('min', 0)
        if sprice:
            return int(sprice)
        else:
            return 0
    except Exception as e:
        print(e)
        return 0

def get_slot_based_starting_room_price(property_id):
    try:
        starting_price_list = Room.objects.annotate(
            hrs4=Cast(KT('room_price__price_4hrs'), IntegerField()),
            hrs8=Cast(KT('room_price__price_8hrs'), IntegerField()),
            hrs12=Cast(KT('room_price__price_12hrs'), IntegerField()),
            base_price=Cast(KT('room_price__base_rate'), IntegerField())).filter(
                property_id=property_id).aggregate(
                    starting_4hr_price=Min('hrs4'),
                    starting_8hr_price=Min('hrs8'),
                    starting_12hr_price=Min('hrs12'),
                    starting_base_price=Min('base_price'))
        
        return starting_price_list
    except Exception as e:
        print(e)
        starting_price_list = {'starting_4hr_price': 0, 'starting_8hr_price': 0,
                               'starting_12hr_price': 0, 'starting_base_price': 0}
        return starting_price_list
        
        
    
def get_property_from_price_range(start_price, end_price):
    property_list = Room.objects.filter(
        room_price__base_rate__gte=start_price,
        room_price__base_rate__lte=end_price).values_list('property_id', flat=True)
    return list(property_list)

def get_price_range():
    min_price = Room.objects.annotate(val=KT('room_price__base_rate')).aggregate(min=Min('val')) 
    max_price = Room.objects.annotate(val=KT('room_price__base_rate')).aggregate(max=Max('val'))
        
    return min_price, max_price

def update_property_review_details(property_id, review_star, review_count):
    Property.objects.filter(id=property_id).update(
        review_star=review_star, review_count=review_count)

def get_slot_price_enabled_property():
    property_list = Room.objects.filter(is_slot_price_enabled=True).values_list('property_id', flat=True)
    return list(property_list)


def filter_property_by_room_amenity(room_amenity):
    property_list = []
    if room_amenity:
        query_room_amenity = Q()
        room_amenity_list = room_amenity.split(',')

        for ramenity in room_amenity_list:
            query_room_amenity &= Q(
                amenity_details__contains=[{'room_amenity':[
                    {'title': ramenity.strip(), 'detail':[{'Yes': []}] }] }])

        property_list = Room.objects.filter(query_room_amenity).values_list('property_id', flat=True)
    return list(property_list)
    
    
