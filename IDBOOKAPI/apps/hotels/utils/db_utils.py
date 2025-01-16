from apps.hotels.models import (
    Property, Room, PropertyGallery,
    RoomGallery, FavoriteList, BlockedProperty)

from django.db.models.fields.json import KT
from django.db.models import Min, Max
from django.db.models import Count, Sum
from django.db.models import IntegerField
from django.db.models.functions import Cast, Coalesce
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

def check_slot_price_enabled(property_id):
    room_obj = Room.objects.filter(is_slot_price_enabled=True, property=property_id)
    return room_obj.exists()

def get_slot_based_starting_room_price(property_id):
    try:
##        is_exists = check_slot_price_enabled(property_id)
        room_obj = Room.objects.filter(property=property_id)

        starting_price_slot_list = room_obj.filter(is_slot_price_enabled=True).annotate(
            hrs4=Cast(KT('room_price__price_4hrs'), IntegerField()),
            hrs8=Cast(KT('room_price__price_8hrs'), IntegerField()),
            hrs12=Cast(KT('room_price__price_12hrs'), IntegerField())).aggregate(
                    starting_4hr_price=Coalesce(Min('hrs4'), 0),
                    starting_8hr_price=Coalesce(Min('hrs8'), 0),
                    starting_12hr_price=Coalesce(Min('hrs12'), 0))

        starting_price_list = room_obj.annotate(
            base_price=Cast(KT('room_price__base_rate'), IntegerField())).aggregate(
                    starting_base_price=Coalesce(Min('base_price'), 0))

        starting_price_list.update(starting_price_slot_list)
        
        return starting_price_list
    except Exception as e:
        print(e)
        starting_price_list = {'starting_4hr_price': 0, 'starting_8hr_price': 0,
                               'starting_12hr_price': 0, 'starting_base_price': 0}
        return starting_price_list

def room_based_property_update(property_id, starting_price_details, is_slot_price_enabled):
    try:
        Property.objects.filter(id=property_id).update(
            starting_price_details=starting_price_details, is_slot_price_enabled=is_slot_price_enabled)
    except Exception as e:
        print(e)

def update_property_with_starting_price(property_id, starting_price_details):
    try:
        Property.objects.filter(id=property_id).update(starting_price_details=starting_price_details)
    except Exception as e:
        print(e)
        
        
    
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

def check_room_blocked(room_id, start_date, end_date, instance_id=None):
    blocked_property_obj = BlockedProperty.objects.filter(
        blocked_room=room_id, start_date__lt=end_date, end_date__gt=start_date, active=True)
    # for update 
    if instance_id:
        blocked_property_obj = blocked_property_obj.exclude(id=instance_id)
        
    return blocked_property_obj.exists()


def get_blocked_room_list(property_id, start_date, end_date):
    blocked_room_list = BlockedProperty.objects.filter(
        start_date__lt=end_date, end_date__gt=start_date,
        is_entire_property=False, active=True).values_list('blocked_room', flat=True)

    return blocked_room_list

##def get_available_room_count(start_date, end_date, property_id=None, room_list=[]):
##
##    room_objs = Room.objects.all()
##    if property_id:
##        room_objs = room_objs.filter(property=property_id)
##    if room_list:
##        room_objs = room_objs.filter(id__in=room_list)

    
    


##def get_blocked_based_room_availability(start_date, end_date, property_id=None):
##    blocked_room_objs = BlockedProperty.objects.filter(
##        start_date__lt=end_date, end_date__gt=start_date,
##        active=True)
##
##    .values(
##            'blocked_room_id', 'no_of_blocked_rooms', 'is_entire_property')
##
##    if property_id:
##        blocked_room_objs = blocked_room_objs.filter(blocked_property=property_id)
##
    
    

def get_blocked_property(start_date, end_date):
    blocked_property = BlockedProperty.objects.filter(
        active=True, start_date__lt=end_date, end_date__gt=start_date)

    # blocked_property = BlockedProperty.objects.filter(active=True)

##    blocked_entire_property = blocked_property.filter(
##        is_entire_property=True).values('blocked_property').values_aslist()

    blocked_property_room = blocked_property.filter(
        is_entire_property=False).values('blocked_room').annotate(
        total_blocked_rooms=Sum('no_of_blocked_rooms'))

    return blocked_property_room
            
    
    
    
