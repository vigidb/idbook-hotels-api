from apps.booking.utils.db_utils import get_booked_room

def get_available_property(check_in, check_out):
    booked_hotel_dict = {}
    booked_hotel = get_booked_room(checkin, checkout)
    for hotel_details in booked_hotel:
        property_id = hotel_details.get('confirmed_property_id')
        room_id = hotel_details.get('room_id')
        if property_id and room_id:
        if booked_hotel_dict.get(property_id, None):
            room_list = booked_hotel_dict.get(property_id)
            room_list.append(room_id)
            booked_hotel_dict[property_id] = room_id
        else:
            booked_hotel_dict[property_id] = [room_id]
            
            
        
