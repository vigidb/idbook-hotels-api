from apps.booking.utils.db_utils import get_booked_room
from apps.hotels.utils.db_utils import get_room_by_id


# booked_hotel_dict = {property_id:{room_id:no_of_rooms}

def get_booked_property(check_in, check_out):
    booked_hotel_dict = {}
    # get booked room details
    booked_hotel = get_booked_room(check_in, check_out)
    print(booked_hotel)
    for hotel_details in booked_hotel:
        property_id = hotel_details.get('confirmed_property_id')
        room_id = hotel_details.get('room_id')
        
        if property_id and room_id:
            if booked_hotel_dict.get(property_id, None):
                room_dict = booked_hotel_dict.get(property_id)
                if room_dict.get(room_id, None):
                    booked_room_count =  room_dict.get(room_id) + 1
                    room_dict[room_id] = booked_room_count
                else:
                    room_dict[room_id] = 1
                
                booked_hotel_dict[property_id] = room_dict
            else:
                booked_hotel_dict[property_id] = {room_id:1}

    print("booked hotel dict::", booked_hotel_dict)
                
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
            
                    
##    print("non availability property", nonavailable_property_list)
##    print("available rooms::", available_property_dict)

    return nonavailable_property_list, available_property_dict
                
        
        
 # checkin, checkout, property, room_id, booked_room_count, available_room_count       
        
