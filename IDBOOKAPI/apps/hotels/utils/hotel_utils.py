from apps.booking.utils.db_utils import get_booked_room, check_room_booked_details
from apps.hotels.utils.db_utils import (
    get_room_by_id, get_total_rooms)


# booked_hotel_dict = {property_id:{room_id:no_of_rooms}

def total_room_count(confirmed_room_details):
    room_dict = {}
    for croom_details in confirmed_room_details:
        room_id = croom_details.get('room_id', 0)
        no_of_rooms = croom_details.get('no_of_rooms', 0)

        if room_id and no_of_rooms:
            if room_dict.get(room_id, None):
                booked_room_count =  room_dict.get(room_id) + no_of_rooms
                room_dict[room_id] = booked_room_count
            else:
                # if room not exist, add the room id and no of rooms
                room_dict[room_id] = no_of_rooms
    return room_dict

def get_aggregate_confirmed_room(booked_rooms):
    room_dict = {}
    for brooms in booked_rooms:
        confirmed_room_details = brooms.get('hotel_booking__confirmed_room_details', '')
        
        for croom_details in confirmed_room_details:
            room_id = croom_details.get('room_id', 0)
            no_of_rooms = croom_details.get('no_of_rooms', 0)

            if room_id and no_of_rooms:
                if room_dict.get(room_id, None):
                    booked_room_count =  room_dict.get(room_id) + no_of_rooms
                    room_dict[room_id] = booked_room_count
                else:
                    # if room not exist, add the room id and no of rooms
                    room_dict[room_id] = no_of_rooms
    print("room dict::", room_dict)
    return room_dict 
        
            

def get_booked_property(check_in, check_out, is_slot_price_enabled=False):
    booked_hotel_dict = {}
    # get booked room details
    booked_hotel = get_booked_room(check_in, check_out, is_slot_price_enabled)
    # print(booked_hotel)
    for hotel_details in booked_hotel:
        property_id = hotel_details.get('hotel_booking__confirmed_property_id')
        room_id = hotel_details.get('hotel_booking__room_id')

        confirmed_room_details = hotel_details.get('hotel_booking__confirmed_room_details')
        
        if property_id:
            for croom_details in confirmed_room_details:
                room_id = croom_details.get('room_id', 0)
                no_of_rooms = croom_details.get('no_of_rooms', 0)

                if room_id and no_of_rooms:
                    # check property already exist
                    if booked_hotel_dict.get(property_id, None):
                        room_dict = booked_hotel_dict.get(property_id)
                        # check room exist
                        if room_dict.get(room_id, None):
                            booked_room_count =  room_dict.get(room_id) + no_of_rooms
                            room_dict[room_id] = booked_room_count
                        else:
                            # if room not exist, add the room id and no of rooms
                            room_dict[room_id] = no_of_rooms
                        
                        booked_hotel_dict[property_id] = room_dict
                    else:
                        # if property not added, add the property with
                        # room and no of rooms
                        booked_hotel_dict[property_id] = {room_id:no_of_rooms}

    # print("booked hotel dict::", booked_hotel_dict)
                
    return booked_hotel_dict



def get_available_property(booked_hotel:dict):
    total_rooms = 0
    available_rooms = 0
    available_property_dict = {}
    nonavailable_property_list = []
    
    for property_id in booked_hotel:
        property_availability_status = False
        room_dict = booked_hotel.get(property_id, {})
        
        for room_id in room_dict:
            room_count = room_dict.get(room_id)
            # get room details
            room_detail = get_room_by_id(room_id)
            # check the room availability
            if room_detail:
                total_rooms = room_detail.no_available_rooms
                available_rooms = total_rooms - room_count
        
                if available_rooms > 0:
                    property_availability_status = True
                    
                print("---", available_property_dict)
                property_dict = available_property_dict.get(property_id, None)
                if property_dict:
                    # property_dict[room_id] = available_rooms
                    property_dict.append({'room_id': room_id, 'available_rooms': available_rooms})

                else:
                    # available_property_dict = {property_id:{room_id: available_rooms}}
                    available_property_dict[property_id] = [{'room_id': room_id, 'available_rooms': available_rooms}]
                        
        if not property_availability_status:
            nonavailable_property_list.append(property_id)
            available_property_dict.pop(property_id)
           
            
                    
##    print("non availability property", nonavailable_property_list)
##    print("available rooms::", available_property_dict)

    return nonavailable_property_list, available_property_dict
                

def check_room_count(booked_rooms, room_confirmed_dict):
    room_rejected_list = []
    # get_total_rooms(property_id, room_id)
##    print("booked rooms", booked_rooms)
    room_dict = get_aggregate_confirmed_room(booked_rooms)
    for room_confirmed in room_confirmed_dict:
        confirmed_room_count = room_confirmed_dict.get(room_confirmed)
        booked_room_count = room_dict.get(room_confirmed, 0)
        available_rooms = get_total_rooms(room_confirmed)

        if confirmed_room_count > (available_rooms - booked_room_count):
            room_rejected_list.append(room_confirmed)

        print("confirmed room count", confirmed_room_count)
        print("booked_room_count", booked_room_count)
        print("available rooms", available_rooms)
    return room_rejected_list
        
    
        
def check_room_availability_for_blocking(start_date, end_date, blocked_property, room_dict):
    
    booked_rooms = check_room_booked_details(start_date, end_date, blocked_property,
                                             is_slot_price_enabled=True, booking_id=None)
    room_rejected_list = check_room_count(booked_rooms, room_dict)
    print(room_rejected_list)
    return room_rejected_list
    
        
