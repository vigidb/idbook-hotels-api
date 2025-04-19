from apps.hotels.models import (
    Property, Room, PropertyGallery,
    RoomGallery, FavoriteList, BlockedProperty,
    PayAtHotelSpendLimit, MonthlyPayAtHotelEligibility)

from apps.hotels.submodels.raw_sql_models import CalendarRoom
from apps.hotels.submodels.related_models import (
    DynamicRoomPricing, TopDestinations, UnavailableProperty,
    PropertyCommission, TrendingPlaces, PropertyCommission)

# from apps.hotels.serializers import UnavailablePropertySerializer
from django.db.models.fields.json import KT
from django.db.models import Min, Max
from django.db.models import Count, Sum
from django.db.models import IntegerField, FloatField
from django.db.models.functions import Cast, Coalesce
from django.db.models import Q, F

from django.db.models import Subquery, OuterRef
from django.db.models.functions import Least
from django.utils.text import slugify

from datetime import datetime

from functools import reduce
from apps.booking.models import Booking
from decimal import Decimal
from django.db.models import ExpressionWrapper, Value
from django.db.models.functions import ACos, Cos, Radians, Sin


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

def get_room_gallery(room_id, active=True):
    room_gallery = RoomGallery.objects.filter(room_id=room_id)
    if active is not None:
        room_gallery = room_gallery.filter(active=active)
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
            'id', 'room_type', 'room_price',
            'is_extra_bed_available', 'room_occupancy').first()
    return room_detail    

def get_favorite_property(user_id):
    favorite_list = FavoriteList.objects.filter(
        user_id=user_id, property__isnull=False).values_list('property_id', flat=True)
    return list(favorite_list)

def is_property_favorite(user_id, property_id):
    is_favorite = FavoriteList.objects.filter(
        user_id=user_id, property_id=property_id).exists()
    return is_favorite
    

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
        room_obj = Room.objects.filter(property=property_id, active=True)

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

def get_price_range(location_list=[], slot="24 Hrs"):

    property_obj = Property.objects.filter(status='Active')

    if location_list:
        query = reduce(lambda a, b: a | b,
                       (Q(area_name__icontains=loc.strip())
                        | Q(city_name=loc.strip())
                        | Q(state=loc.strip())
                        | Q(country=loc.strip())  for loc in location_list),)
        property_obj = property_obj.filter(query)

    property_ids = list(property_obj.values_list('id', flat=True))
        
    room_obj = Room.objects.filter(property_id__in=property_ids)
    if slot == "4 Hrs":
        min_price = room_obj.annotate(
            val=Cast(KT('room_price__price_4hrs'), IntegerField())).aggregate(
                min=Coalesce(Min('val'), 0)) 
        max_price = room_obj.annotate(
            val=Cast(KT('room_price__price_4hrs'), IntegerField())).aggregate(
                max=Coalesce(Max('val'), 0))
    elif slot == "8 Hrs":
        min_price = room_obj.annotate(
            val=Cast(KT('room_price__price_8hrs'), IntegerField())).aggregate(
                min=Coalesce(Min('val'), 0)) 
        max_price = room_obj.annotate(
            val=Cast(KT('room_price__price_8hrs'), IntegerField())).aggregate(
                max=Coalesce(Max('val'), 0))
    elif slot == "12 Hrs":
        min_price = room_obj.annotate(
            val=Cast(KT('room_price__price_12hrs'), IntegerField())).aggregate(
                min=Coalesce(Min('val'), 0)) 
        max_price = room_obj.annotate(
            val=Cast(KT('room_price__price_12hrs'), IntegerField())).aggregate(
                max=Coalesce(Max('val'), 0))
    else:
        # 24 hrs
        min_price = room_obj.annotate(
            val=Cast(KT('room_price__base_rate'), IntegerField())).aggregate(
                min=Coalesce(Min('val'), 0)) 
        max_price = room_obj.annotate(
            val=Cast(KT('room_price__base_rate'), IntegerField())).aggregate(
                max=Coalesce(Max('val'), 0))
        
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

def check_is_room_dynamic_price_set(room_id, start_date, end_date, instance_id=None):
    dynamic_pricing_obj = DynamicRoomPricing.objects.filter(
        for_room=room_id, start_date__lt=end_date,
        end_date__gt=start_date, active=True)
    # for update
    if instance_id:
        dynamic_pricing_obj = dynamic_pricing_obj.exclude(id=instance_id)

    return dynamic_pricing_obj.exists()
        


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

def get_blocked_property_ids(start_date, end_date, property_id):
    blocked_property = BlockedProperty.objects.filter(
        active=True, start_date__lt=end_date, end_date__gt=start_date)
    
    if property_id:
        blocked_property = blocked_property.filter(blocked_property_id=property_id)
        blocked_ids = blocked_property.values_list('id', flat=True)
        return list(blocked_ids)
    else:
        blocked_ids = blocked_property.values_list('id', flat=True)
        property_ids = blocked_property.values_list(
            'blocked_property_id', flat=True).distinct()
        return list(blocked_ids), list(property_ids)
    

##def get_room_availability(start_date, end_date, property_id, hotel_booking_ids):
##    """
##    get room details based on single property
##    """
##
##    # for single value list throws error during tuple conversion in sql
##    if hotel_booking_ids:
##        hotel_booking_ids.append(-1)
##        hotel_booking_ids = tuple(hotel_booking_ids)
##    else:
##        hotel_booking_ids = (-1,-2)
##    
##
##
##    LEFT_JOIN_BLOCKED_PROPERTY = f'''(select blocked_room_id, SUM(no_of_blocked_rooms) as no_of_blocked_rooms
##from hotels_blockedproperty where hotels_blockedproperty.blocked_property_id={property_id} GROUP BY blocked_room_id)
##hotels_blockedproperty ON hotels_blockedproperty.blocked_room_id = hotels_room.id'''
##
##    LEFT_JOIN_BOOKED_PROPERTY = f'''(SELECT (hb.room_id)::int, SUM((hb.no_of_rooms)::int) as no_booked_room
##FROM(SELECT jsonb_path_query(confirmed_room_details, '$.room_id') AS room_id,
##jsonb_path_query(confirmed_room_details, '$.no_of_rooms') AS no_of_rooms
##FROM booking_hotelbooking where confirmed_property_id={property_id} and id IN {hotel_booking_ids})
##hb GROUP BY hb.room_id) hb ON hb.room_id = hotels_room.id'''
##
##
##    raw_sql_query= f'''
##select hotels_room.id, hotels_room.room_type, hotels_room.no_available_rooms, coalesce(hb.no_booked_room,0) as no_booked_room,
##coalesce(hotels_blockedproperty.no_of_blocked_rooms,0) as no_of_blocked_rooms,
##(hotels_room.no_available_rooms - (coalesce(hotels_blockedproperty.no_of_blocked_rooms,0) + coalesce(hb.no_booked_room,0))) AS current_available_room
##from hotels_room LEFT JOIN {LEFT_JOIN_BLOCKED_PROPERTY} LEFT JOIN {LEFT_JOIN_BOOKED_PROPERTY}
##where hotels_room.property_id=%s '''
##
##    room_raw_obj = Room.objects.raw(raw_sql_query, [property_id])
##    #room_raw_obj = Room.objects.raw(raw_sql_query)
##    print(room_raw_obj.query)
##    return room_raw_obj

def get_property_availability(property_ids, hotel_booking_ids, blocked_ids):
    
    if hotel_booking_ids:
        hotel_booking_ids.append(-1)
        hotel_booking_ids = tuple(hotel_booking_ids)
    else:
        hotel_booking_ids = (-1,-2)

    if blocked_ids:
        blocked_ids.append(-1)
        blocked_ids = tuple(blocked_ids)
    else:
        blocked_ids = (-1, -2)
        
        

    if property_ids:
        property_ids.append(-1)
        property_ids = tuple(property_ids)
    else:
        property_ids = (-1, -2)

    LEFT_JOIN_BLOCKED_PROPERTY = f'''(select blocked_room_id, SUM(no_of_blocked_rooms) as no_of_blocked_rooms
from hotels_blockedproperty where hotels_blockedproperty.id IN {blocked_ids} GROUP BY blocked_room_id)
hotels_blockedproperty ON hotels_blockedproperty.blocked_room_id = hotels_room.id'''

    LEFT_JOIN_BOOKED_PROPERTY = f'''(SELECT (hb.room_id)::int, SUM((hb.no_of_rooms)::int) as no_booked_room
FROM(SELECT jsonb_path_query(confirmed_room_details, '$.room_id') AS room_id,
jsonb_path_query(confirmed_room_details, '$.no_of_rooms') AS no_of_rooms
FROM booking_hotelbooking where id IN {hotel_booking_ids})
hb GROUP BY hb.room_id) hb ON hb.room_id = hotels_room.id'''


    raw_sql_query= f'''
select hotels_room.id, hotels_room.property_id, hotels_room.room_type, hotels_room.no_available_rooms, coalesce(hb.no_booked_room,0) as no_booked_room,
coalesce(hotels_blockedproperty.no_of_blocked_rooms,0) as no_of_blocked_rooms,
(hotels_room.no_available_rooms - (coalesce(hotels_blockedproperty.no_of_blocked_rooms,0) + coalesce(hb.no_booked_room,0))) AS current_available_room
from hotels_room LEFT JOIN {LEFT_JOIN_BLOCKED_PROPERTY} LEFT JOIN {LEFT_JOIN_BOOKED_PROPERTY}
where hotels_room.property_id IN %s order by hotels_room.property_id'''

    room_raw_obj = Room.objects.raw(raw_sql_query, [property_ids])
    #room_raw_obj = Room.objects.raw(raw_sql_query)
##    print(room_raw_obj.query)
    return room_raw_obj

def update_property_confirmed_booking(property_id, no_of_confirmed_booking):
    try:
        property_obj = Property.objects.get(id=property_id)
        property_obj.additional_fields['no_confirmed_booking'] = no_of_confirmed_booking
        property_obj.save()
    except Exception as e:
        print(e)

def get_calendar_unavailable_property(hotel_booking_ids, blocked_ids):

    if hotel_booking_ids:
        hotel_booking_ids.append(-1)
        hotel_booking_ids = tuple(hotel_booking_ids)
    else:
        hotel_booking_ids = (-1,-2)

    if blocked_ids:
        blocked_ids.append(-1)
        blocked_ids = tuple(blocked_ids)
    else:
        blocked_ids = (-1, -2)

    BLOCKED_PROPERY = f'''
select id, blocked_property_id as property_id, blocked_room_id as room_id, 
no_of_blocked_rooms as no_unavailable_rooms, 'blocked' as blocked_booked,
start_date as start_date, end_date as end_date 
from hotels_blockedproperty where id in {blocked_ids}
'''
    BOOKED_PROPERTY = f'''
SELECT hb.id, hb.confirmed_property_id as property_id, (hb.room_id)::int as room_id, 
(hb.no_of_rooms)::int as no_unavailable_rooms, 'booked' as blocked_booked,
hb.confirmed_checkin_time as start_date, hb.confirmed_checkout_time as end_date
FROM(SELECT id, confirmed_property_id, jsonb_path_query(confirmed_room_details, '$.room_id') AS room_id,
jsonb_path_query(confirmed_room_details, '$.no_of_rooms') AS no_of_rooms,
confirmed_checkin_time, confirmed_checkout_time
FROM booking_hotelbooking as hb where id in {hotel_booking_ids}) as hb
'''


    raw_sql_query = f''' {BLOCKED_PROPERY} UNION ALL {BOOKED_PROPERTY} '''

    room_unavailable_obj = CalendarRoom.objects.raw(raw_sql_query)
    return room_unavailable_obj

def get_dynamic_pricing(property_id, start_date, end_date):
    dynamic_pricing_obj = DynamicRoomPricing.objects.filter(
        for_property_id=property_id, start_date__lt=end_date,
        end_date__gt=start_date, active=True)
    
    return dynamic_pricing_obj

def get_dynamic_room_pricing_list(start_date, end_date, room_ids:list):

    pricing_objs = DynamicRoomPricing.objects.filter(
        for_room__in=room_ids, active=True)
        #start_date__date__lt=end_date, end_date__date__gt=start_date)

##    .filter(
##            Q(start_date__date__lte=start_date, end_date__date__gte=start_date)
##            | Q(start_date__date__gt=end_date, end_date__date__gt=end_date))
    # print("-- query", pricing_objs.query)

    return pricing_objs

def get_dynamic_pricing_with_date_list(room_id, date_list):
    pricing_obj = DynamicRoomPricing.objects.filter(
        for_room_id=room_id, active=True)
    date_price_dict = {}
    is_price_available = False
    if pricing_obj.exists():
        for date in date_list:
            date_pricing_obj = pricing_obj.filter(
                start_date__date__lte=date, end_date__date__gte=date).values(
                    'room_price').first()
            if date_pricing_obj:
                date_price_dict[str(date)] = date_pricing_obj
                is_price_available = True
            else:
                date_price_dict[str(date)] = ""
    if not is_price_available:
        return {}
    return date_price_dict

def get_property_count_by_location(location_name):

    property_objs = Property.objects.filter(status='Active') 
    property_objs = property_objs.filter(Q(city_name=location_name.strip())
                                         | Q(state=location_name.strip())
                                         | Q(country=location_name.strip()))
    total_count = property_objs.count()
    return total_count

def update_destination_property_count(location_name, total_count):
    destination_objs = TopDestinations.objects.filter(
        location_name=location_name)
    destination_objs.update(no_of_hotels=total_count)

def is_top_destination_exist(location_name, exclude_id=None):
    top_destination = TopDestinations.objects.filter(
        location_name__iexact=location_name)
    if exclude_id:
        top_destination = top_destination.exclude(id=exclude_id)
    is_exist = top_destination.exists()
    return is_exist
    

def check_top_destination_exist(location_list):
    existing_list =  list(TopDestinations.objects.filter(
        location_name__in=location_list).values_list(
            'location_name', flat=True))
    return existing_list

def process_property_based_topdest_count(location_list):
    try:
        existing_list = check_top_destination_exist(location_list)
        for location_name in existing_list:
            total_count = get_property_count_by_location(location_name)
            update_destination_property_count(location_name, total_count)
    except Exception as e:
        print(e)

def is_trending_place_exist(location_name, exclude_id=None):
    query = TrendingPlaces.objects.filter(location_name__iexact=location_name.strip())
    if exclude_id:
        query = query.exclude(id=exclude_id)
    return query.exists()

##def get_checkin_based_dynamic_pricing(checkin_date, booking_slot):
##    try:
##        pricing_obj = DynamicRoomPricing.objects.filter(
##            active=True, start_date__date__lte=checkin_date,
##            end_date__date__gte=checkin_date)
##
##        if slot == "4 Hrs":
##            min_price = pricing_obj.annotate(
##                val=Cast(KT('room_price__price_4hrs'), IntegerField())).aggregate(
##                    min=Coalesce(Min('val'), 0)) 
##        elif slot == "8 Hrs":
##            min_price = pricing_obj.annotate(
##                val=Cast(KT('room_price__price_8hrs'), IntegerField())).aggregate(
##                    min=Coalesce(Min('val'), 0)) 
##        elif slot == "12 Hrs":
##            min_price = pricing_obj.annotate(
##                val=Cast(KT('room_price__price_12hrs'), IntegerField())).aggregate(
##                    min=Coalesce(Min('val'), 0)) 
##        else:
##            min_price = pricing_obj.annotate(
##                val=Cast(KT('room_price__base_rate'), IntegerField())).aggregate(
##                    min=Coalesce(Min('val'), 0)) 
##    except Excpetion as e:
##        print(e)



def get_lowest_property_pricing(queryset, checkin_date, booking_slot):
    
    if not checkin_date:
        checkin_date = datetime.strptime('1700-01-20T00:00+05:30', '%Y-%m-%dT%H:%M%z')
    
    if booking_slot == "4 Hrs":
        dynamic_room_rate = 'room_price__price_4hrs'
        normal_rate = 'starting_price_details__starting_4hr_price'
    elif booking_slot == "8 Hrs":
        dynamic_room_rate = 'room_price__price_8hrs'
        normal_rate = 'starting_price_details__starting_8hr_price'
    elif booking_slot == "12 Hrs":
        dynamic_room_rate = 'room_price__price_12hrs'
        normal_rate = 'starting_price_details__starting_12hr_price'
    else:
        dynamic_room_rate = 'room_price__base_rate'
        normal_rate = 'starting_price_details__starting_base_price'

    # dynamic room price as subquery
    dynamic_pricing_subquery = DynamicRoomPricing.objects.filter(
        for_property_id=OuterRef("pk"), active=True,
        start_date__date__lte=checkin_date,
        end_date__date__gte=checkin_date)

    
    # annotate for the lowest dynamic price
    dynamic_pricing_subquery = dynamic_pricing_subquery.annotate(
        val=Cast(KT(dynamic_room_rate),
                 IntegerField())).values('val').order_by('val')[:1]
     
    # store lowest dynamic price for each property
    queryset = queryset.annotate(dynamic_price=Coalesce(
        Subquery(dynamic_pricing_subquery), 999999999))
    
    # get the lowest price by comparing dynamic lowest price
    # and normal starting price
    queryset = queryset.annotate(lowest_price=Least("dynamic_price", Cast(KT(normal_rate), IntegerField())))

    return queryset



def get_property_distance(queryset, lat, lon):

    property_lat = Cast(KT('address__coordinates__lat'), FloatField())
    property_lng = Cast(KT('address__coordinates__lng'), FloatField())
    unit = 6371.0
##
##    # Trivandrum location
##    lat1 = 8.524139
##    lon1 = 76.936638

    lat, lon = float(lat), float(lon)
    print("latitude ------", lat, "longitude", lon)
    # distance using great circle distance
    expression_wrapper = ExpressionWrapper((unit * ACos(Cast((Cos(Radians(lat)) * Cos(Radians(property_lat))
                                                              * Cos(Radians(property_lng) - Radians(lon))
                                                              + Sin(Radians(lat)) * Sin(Radians(property_lat))), FloatField()
                                                              ))),
                                           output_field=FloatField(),)

    
    
##    queryset = Property.objects.all()
    queryset = queryset.exclude(address__coordinates__lat='', address__coordinates__lng='')
    queryset = queryset.annotate(
        distance=expression_wrapper)

    return queryset
    

def query_annotate():

##    dynamic_price_query = DynamicRoomPricing.objects.filter(
##        for_property=OuterRef("pk")).annotate(
##                val=Cast(KT('room_price__base_rate'), IntegerField())).aggregate(
##                    min=Coalesce(Min('val'), 0)) 
    property_obj = Property.objects.annotate(dynamic_price=Coalesce(Subquery(
        DynamicRoomPricing.objects.filter(
        for_property_id=OuterRef("pk")).annotate(
                val=Cast(KT('room_price__base_rate'), IntegerField())).values('val').order_by('val')[:1]
        ),999999999)).annotate(lowest_price=Least("dynamic_price", Cast(KT('starting_price_details__starting_base_price'), IntegerField())))
    property_obj = property_obj.order_by('lowest_price')

    #query= DynamicRoomPricing.objects.filter(for_property_id=21).values('id', 'for_property_id','room_price__base_rate')
##    query= DynamicRoomPricing.objects.filter(for_property_id=21).annotate(
##        val=Cast(KT('room_price__base_rate'), IntegerField())).values_list('val', flat=True)
##
##    query= DynamicRoomPricing.objects.filter(for_property_id=21).annotate(
##        val=Cast(KT('room_price__base_rate'), IntegerField())).values('val').order_by('val')[0]
##    print(query)


##    property_dynamic_pricing

##    property_obj = Property.objects.select_related(
##        'property_dynamic_pricing').annotate(val=Cast(KT('property_dynamic_pricing__room_price__base_rate'),
##                                                      IntegerField())).aggregate(
##                                                          min=Coalesce(Min('val'), 0))
##
##    property_obj = Property.objects.exclude(property_dynamic_pricing=None).select_related(
##        'property_dynamic_pricing').annotate(
##            val=Cast(KT('property_dynamic_pricing__room_price__base_rate'),
##                     IntegerField())).aggregate(
##                         min=Coalesce(Min('val'), 0))
##
##    property_obj = Property.objects.exclude(property_dynamic_pricing=None).prefetch_related(
##        'property_dynamic_pricing__room_price__base_rate').annotate(
##            val=Cast(KT('property_dynamic_pricing__room_price__base_rate'),
##                     IntegerField())).aggregate(
##                         min=Coalesce(Min('val'), 0))

##    property_obj = Property.objects.exclude(property_dynamic_pricing=None).prefetch_related(
##        'property_dynamic_pricing__room_price__base_rate').values('id', 'property_dynamic_pricing__id')

##    property_obj = Property.objects.exclude(property_dynamic_pricing=None).prefetch_related(
##        Prefetch('property_dynamic_pricing',
##                 queryset=DynamicRoomPricing.objects.annotate(student_count=Count('for_property_id'))
##                 )
##        ).values('id', 'property_dynamic_pricing')


##    property_obj = Property.objects.exclude(property_dynamic_pricing=None).annotate(dcount=Count('property_dynamic_pricing'))

##    property_obj = Property.objects.exclude(property_dynamic_pricing=None).annotate(
##        val=Min(Cast(KT('property_dynamic_pricing__room_price__base_rate'),
##                 IntegerField())))#.aggregate(min=Coalesce(Min('val'), 0))
    
    print(property_obj.values('id', 'name', 'dynamic_price', 'lowest_price'))
   

##    for prop in property_obj:
##        print("id", prop.get('id'), "student count", prop.get('property_dynamic_pricing__student_count'))

    
def save_unavailable_property_search(query_params):    
    location = query_params.get('location', '')
    property_search = query_params.get('property_search', '')

    search_term = location or property_search
    search_term = search_term.strip()
    
    if search_term:
        UnavailableProperty.objects.create(
            search_term=search_term,
            full_params=dict(query_params)
        )

    
def is_property_commission_active(property_id, exclude_comm_id=None):
    prop_comm = PropertyCommission.objects.filter(
        property_comm=property_id, active=True)
    
    if exclude_comm_id:
        prop_comm = prop_comm.exclude(id=exclude_comm_id)

    return prop_comm.exists()

def get_property_commission(property_id):
    prop_comm = PropertyCommission.objects.filter(
        property_comm=property_id, active=True)
    return prop_comm.first()

def check_property_slug(slug_value, exclude=None):
    slug = slugify(slug_value)
    property_obj = Property.objects.filter(slug=slug)
    if exclude:
        property_obj = property_obj.exclude(id=exclude)

    slug_exist = property_obj.exists()
    return slug_exist, slug

    
def get_user_booking_data(user_id, booking_date):
    """
    Fetch confirmed bookings and cancelled bokings count and eligible spend limit for a user in a given month.
    """
    booking_datetime = datetime.strptime(booking_date, '%Y-%m-%d %H:%M:%S')
    current_month_name = booking_datetime.strftime('%B')
    current_month = booking_datetime.month
    current_year = booking_datetime.year

    confirmed_bookings_count = Booking.objects.filter(
        user_id=user_id,
        status__in=['confirmed', 'completed'],
        booking_payment__is_transaction_success=True,
        created__month=current_month,
        created__year=current_year
    ).count()

    canceled_bookings = Booking.objects.filter(
        user_id=user_id,
        status='canceled',
        booking_payment__payment_type='DIRECT',
        booking_payment__payment_medium='Hotel',
        created__month=current_month,
        created__year=current_year
    )

    total_cancel_count = canceled_bookings.count()
    cancel_limit = 0
    for b in canceled_bookings:
        booking_payment = b.booking_payment.first()
        if booking_payment and booking_payment.amount:
            cancel_limit += booking_payment.amount

    spend_limit_obj = PayAtHotelSpendLimit.objects.filter(
        start_limit__lte=confirmed_bookings_count,
        end_limit__gte=confirmed_bookings_count
    ).first()

    eligible_limit = spend_limit_obj.spend_limit if spend_limit_obj else 0

    monthly_eligibility = MonthlyPayAtHotelEligibility.objects.filter(
        user_id=user_id,
        month=current_month_name
    ).first()

    spent_amount = monthly_eligibility.spent_amount if monthly_eligibility else Decimal('0.00')
    remaining_limit = eligible_limit - spent_amount
    is_eligible = remaining_limit > 0

    # Blacklist check
    is_blacklisted = False
    if spend_limit_obj:
        if (spend_limit_obj.cancel_count and total_cancel_count >= spend_limit_obj.cancel_count) or \
           (spend_limit_obj.cancel_limit and cancel_limit >= spend_limit_obj.cancel_limit):
            is_eligible = False
            is_blacklisted = True

    return {
        'month_name': current_month_name,
        'booking_count': confirmed_bookings_count,
        'eligible_limit': eligible_limit,
        'spent_amount': spent_amount,
        'remaining_limit': remaining_limit,
        'is_eligible': is_eligible,
        'total_cancel_count': total_cancel_count,
        'cancel_limit': cancel_limit,
        'is_blacklisted': is_blacklisted
    }   
    
    
    
