from apps.hotels.utils.db_utils import (
    get_property_room_for_booking, get_dynamic_room_pricing_list,
    get_property_commission, get_room_price, get_room_by_id)
from apps.booking.utils.booking_utils import (
    get_tax_rate, calculate_xbed_amount, calculate_room_booking_amount)

from rest_framework import status

from IDBOOKAPI.utils import (
    calculate_tax, get_dates_from_range,
    get_date_from_string)
from apps.hotels.models import Room
from apps.hotels.utils.hotel_utils import get_available_room
from apps.org_resources.models import BasicAdminConfig
from decimal import Decimal
import traceback

class BookingMixins:

    def get_dynamic_pricing_applicable_room(self, start_date, end_date):
        room_ids = []
        room_dprice_dict = {}
        dprice_roomids = []
        for room in self.room_list:
            room_id = room.get('room_id', None)
            if room_id:
                room_ids.append(room_id)

        date_list = get_dates_from_range(start_date, end_date)
        # avoid checkout date
        if len(date_list) >=2:
            date_list.pop()

        # print("date list::", date_list)
        pricing_objs = get_dynamic_room_pricing_list(
            start_date, end_date, room_ids)

        if not pricing_objs.exists():
            return room_dprice_dict, date_list, dprice_roomids

        # store dynamic price based on date and room
        for date in date_list:
            print("date::", date)
            pricing_date_objs = pricing_objs.filter(
                start_date__date__lte=date, end_date__date__gte=date)
            
            for pricing_obj in pricing_date_objs:
                room_price = pricing_obj.room_price
                room_id = pricing_obj.for_room_id
                dprice_key = f"""{str(room_id)}__{str(date)}"""
                room_dprice_dict[dprice_key] = {'price': room_price}
                dprice_roomids.append(room_id)
        # print("room price dict::", room_dprice_dict)
        return room_dprice_dict, date_list, dprice_roomids

    def get_booking_slot_price(self, room_price):   
        if self.booking_slot == '12 Hrs':
            slot_price = room_price.get('price_12hrs', None)
            extra_bed_price = room_price.get('extra_bed_price_12hrs', 0)
            booking_room_price = slot_price
        elif self.booking_slot == '8 Hrs':
            slot_price = room_price.get('price_8hrs', None)
            extra_bed_price = room_price.get('extra_bed_price_8hrs', 0)
            booking_room_price = slot_price
        elif self.booking_slot == '4 Hrs':
            slot_price = room_price.get('price_4hrs', None)
            extra_bed_price = room_price.get('extra_bed_price_4hrs', 0)
            booking_room_price = slot_price
        else:
            slot_price = None
            extra_bed_price = room_price.get('extra_bed_price', 0)
            booking_room_price = room_price.get('base_rate', 0)

        return slot_price, extra_bed_price, booking_room_price

    def get_booking_dynamic_slot_price(self, age, room_price):
        age_price = None
        child_bed_price = room_price.get('child_bed_price')
        for price_details in child_bed_price:
            age_list = price_details.get('age_limit', [])
            
            if age_list[0] <= age <= age_list[1]:
                
                if self.booking_slot == '12 Hrs':
                    age_price = price_details.get('child_bed_price_12hrs', 0)
                elif self.booking_slot == '8 Hrs':
                    age_price = price_details.get('child_bed_price_8hrs', 0)
                elif self.booking_slot == '4 Hrs':
                    age_price = price_details.get('child_bed_price_4hrs', 0)
                else:
                    age_price = price_details.get('child_bed_price', 0)

                break

        # if age not withing the price range then provide adult extra bed price
        if age_price is None:
            if self.booking_slot == '12 Hrs':
                age_price =  room_price.get('extra_bed_price_12hrs', 0)
            elif self.booking_slot == '8 Hrs':
                age_price =  room_price.get('extra_bed_price_8hrs', 0)
            elif self.booking_slot == '4 Hrs':
                age_price = room_price.get('extra_bed_price_4hrs', 0)
            else:
                age_price = room_price.get('extra_bed_price', 0)

        return age_price
        
        

    def room_allocation(self):
        self.room_detail_dict = {}
        self.room_occupancy_dict = {}
        allotted_person = 0
        
        need_to_allot = self.adult_count
        child_need_to_allot = self.child_count
        child_age_need_to_allot = self.child_age_list

        for room in self.room_list:
            child_allotted_list = []
            room_id = room.get('room_id', None)
            no_of_rooms = room.get('no_of_rooms', None)
            # room_id_list.append(room_id)

            room_detail = get_property_room_for_booking(self.property_id, room_id)
            if not room_detail:
                custom_response = self.get_error_response(
                    message=f"The room: {room_id} is missing for the property", status="error",
                    errors=[],error_code="ROOM_MISSING",
                    status_code=status.HTTP_400_BAD_REQUEST)
                is_status = False
                return is_status, custom_response

            self.room_detail_dict[room_id] = room_detail

            child_bed_price = room_detail.get('room_price', {}).get('child_bed_price', {})

            
            room_occupancy = room_detail.get('room_occupancy', {})
            base_adults = room_occupancy.get('base_adults', None)
            max_occupancy = room_occupancy.get('max_occupancy', None)

            is_extra_bed_available = room_detail.get('is_extra_bed_available', False)

            if not no_of_rooms:
                custom_response = self.get_error_response(
                    message=f"The no of rooms for {room_id} is missing", status="error",
                    errors=[],error_code="NO_ROOM_MISSING",
                    status_code=status.HTTP_400_BAD_REQUEST)
                is_status = False
                return is_status, custom_response

            
            total_base_adults =  base_adults * no_of_rooms
            total_max_occupancy = max_occupancy * no_of_rooms

            if need_to_allot <= total_base_adults:
                allotted_person = need_to_allot
                need_to_allot = 0
            elif need_to_allot > total_base_adults:
                allotted_person = total_base_adults
                need_to_allot = need_to_allot - allotted_person 
                
            extra_persons_allowed = total_max_occupancy - allotted_person
            len_child_to_allot = len(child_age_need_to_allot)

            if  len_child_to_allot and extra_persons_allowed:
                remove_alloted_list = []
                for age in child_age_need_to_allot:
                    print("age::", age, "extra_persons_allowed::", extra_persons_allowed)
                    if not extra_persons_allowed:
                        break
                    else:
                        allotted_status = False
                        for price_details in child_bed_price:
                            age_list = price_details.get('age_limit', [])
                            
                            if age_list[0] <= age <= age_list[1]:
                                if self.booking_slot == '12 Hrs':
                                    age_price = price_details.get('child_bed_price_12hrs', 0)
                                elif self.booking_slot == '8 Hrs':
                                    age_price = price_details.get('child_bed_price_8hrs', 0)
                                elif self.booking_slot == '4 Hrs':
                                    age_price = price_details.get('child_bed_price_4hrs', 0)
                                else:
                                    age_price = price_details.get('child_bed_price', 0)

                                child_allotted = {'age': age, 'price':age_price}
                                child_allotted_list.append(child_allotted)
                                extra_persons_allowed = extra_persons_allowed - 1
                                remove_alloted_list.append(age)
                                allotted_status = True
                                break

                        # if age not withing the price range then provide adult extra bed price
                        if not allotted_status:
                            if self.booking_slot == '12 Hrs':
                                age_price =  room_detail.get('room_price', {}).get('extra_bed_price_12hrs', 0)
                            elif self.booking_slot == '8 Hrs':
                                age_price =  room_detail.get('room_price', {}).get('extra_bed_price_8hrs', 0)
                            elif self.booking_slot == '4 Hrs':
                                age_price =  room_detail.get('room_price', {}).get('extra_bed_price_4hrs', 0)
                            else:
                                age_price = room_detail.get('room_price', {}).get('extra_bed_price', 0)
                                
                            child_allotted = {'age': age, 'price':age_price}
                            child_allotted_list.append(child_allotted)
                            extra_persons_allowed = extra_persons_allowed - 1
                            remove_alloted_list.append(age)
                                
                # remove alloted list
                for pop_age in remove_alloted_list:
                    child_age_need_to_allot.remove(pop_age)

            self.room_occupancy_dict[room_id] = {'total_base_adults':total_base_adults,
                                            'total_max_occupancy': total_max_occupancy,
                                            'allotted_person': allotted_person,
                                            'is_extra_bed_available':is_extra_bed_available,
                                            'extra_persons_allowed':extra_persons_allowed,
                                            'extra_adults_allotted':0,
                                            'child_allotted': child_allotted_list
                                            }  
            
        if need_to_allot:
            for room_occupancy_key in self.room_occupancy_dict:
                room_occupancy_details = self.room_occupancy_dict.get(room_occupancy_key)
                extra_persons_allowed = room_occupancy_details.get('extra_persons_allowed', 0)

                if need_to_allot <= extra_persons_allowed:
                    room_occupancy_details['extra_adults_allotted'] = need_to_allot
                    need_to_allot = 0
                elif need_to_allot > extra_persons_allowed:
                    need_to_allot = need_to_allot - extra_persons_allowed
                    room_occupancy_details['extra_adults_allotted'] = extra_persons_allowed
        

        if need_to_allot or child_age_need_to_allot:
            custom_response = self.get_error_response(
                message=f"The no of guests is more for selected room(s)", status="error",
                errors=[],error_code="INADEQUATE_ROOM",
                status_code=status.HTTP_400_BAD_REQUEST)
            is_status = False
            return is_status, custom_response
        return True, None


    def tax_calculation(self, base_price, slot_price, no_of_days,
                        no_of_rooms, total_extra_bed_price,
                        total_child_price, total_tax_amount):
        tax_in_percent = get_tax_rate(base_price, self.tax_rules_dict)
        if not tax_in_percent:
            return 0, 0, 0
        
        tax_in_percent = float(tax_in_percent)

        # tax calculation based on booked 
        if self.booking_slot == '24 Hrs':
            tax_amount = calculate_tax(tax_in_percent, base_price)
            
        else:
            tax_amount = calculate_tax(tax_in_percent, slot_price)

        # calculate total tax amount
        # add previous tax amount for date base list
        total_tax_amount =   calculate_room_booking_amount(
            tax_amount, no_of_days, no_of_rooms) + total_tax_amount


        # extra adult calculation
        if total_extra_bed_price:
            # calculate tax amount for extra person
            tax_amount_xbed = calculate_tax(tax_in_percent, total_extra_bed_price)
            total_tax_amount_xbed = calculate_xbed_amount(tax_amount_xbed, no_of_days) 

            # total tax amount including extra bed
            total_tax_amount = total_tax_amount + total_tax_amount_xbed

        # calculate tax amount for children
        if total_child_price:
            tax_amount_child = calculate_tax(tax_in_percent, total_child_price)
            total_tax_amount_child = calculate_xbed_amount(tax_amount_child, no_of_days)

            # total tax amount including extra bed
            total_tax_amount = total_tax_amount + total_tax_amount_child

        return total_tax_amount, tax_in_percent, tax_amount

    def room_calculation(self, base_price, slot_price, no_of_days, no_of_rooms,
                         total_extra_bed_price, total_child_price, total_room_amount):
        
        # calculate total room amount
        # add previous room amount for date base list
        if self.booking_slot == '24 Hrs':
            total_room_amount = calculate_room_booking_amount(
                base_price, no_of_days, no_of_rooms) + total_room_amount
        else:
            total_room_amount = calculate_room_booking_amount(
                slot_price, no_of_days, no_of_rooms) + total_room_amount

        # calculate extra bed amount
        if total_extra_bed_price:
            total_room_amount_xbed = calculate_xbed_amount(total_extra_bed_price, no_of_days)
            total_room_amount = total_room_amount + total_room_amount_xbed

        # calculate children price
        if total_child_price:
            total_child_amount = calculate_xbed_amount(total_child_price, no_of_days)
            total_room_amount = total_room_amount + total_child_amount

        return total_room_amount

            
    def amount_calculation(self):

        # Initialize total room amount tracking variables
        self.total_room_amount_without_room_discount = 0
        self.total_room_amount_with_room_discount = 0
        
        for room in self.room_list:
            room_id = room.get('room_id', None)
            no_of_rooms = room.get('no_of_rooms', None)
            base_price = 0

            room_detail = self.room_detail_dict.get(room_id)

            # get room details
            room_type = room_detail.get('room_type')
            room_price = room_detail.get('room_price')
            # Get room discount information from room table
            room_db_info = get_room_by_id(room_id)
            room_discount = room_db_info.discount if room_db_info else 0
            room_discount_type = room_db_info.discount_type if room_db_info else 'PERCENT'

            if not room_price:
                custom_response = self.get_error_response(
                    message=f"The room price details for the room {room_type} is missing", status="error",
                    errors=[],error_code="ROOM_PRICE_MISSING",
                    status_code=status.HTTP_400_BAD_REQUEST)
                is_status = False
                return is_status, custom_response

            # get 24 hours price
            base_price = room_price.get('base_rate', None)
            if not base_price:
                custom_response = self.get_error_response(
                    message=f"The room price details for the room {room_type} is missing", status="error",
                    errors=[],error_code="ROOM_PRICE_MISSING",
                    status_code=status.HTTP_400_BAD_REQUEST)
                is_status = False
                return is_status, custom_response

            # get pricing based on slot
            slot_price, extra_bed_price, booking_room_price = self.get_booking_slot_price(room_price)
                
            if not slot_price and not self.booking_slot == '24 Hrs':
                custom_response = self.get_error_response(
                    message=f"The {self.booking_slot} hrs room price for the room {room_type} is missing", status="error",
                    errors=[],error_code="ROOM_PRICE_MISSING",
                    status_code=status.HTTP_400_BAD_REQUEST)
                is_status = False
                return is_status, custom_response
                    

            # for extra bed calculation
            occup_details = self.room_occupancy_dict.get(room_id)
            # extra adults
            extra_adults_allotted = occup_details.get('extra_adults_allotted', 0)
            # extra child
            child_allotted = occup_details.get('child_allotted', [])

            
            total_tax_amount = 0
            total_room_amount = 0

            date_based_price_list = []

            # check whether room id has dynamic pricing
            if room_id in self.dprice_roomids:
                for date in self.date_list:
                    date_based_price_dict = {"date": str(date)}
                    
                    total_child_price = 0
                    price_dict_key = f"{str(room_id)}__{str(date)}"
                    dynamic_price = self.room_dprice_dict.get(price_dict_key, {}).get('price',{})
                    if dynamic_price:
                        dslot_price, dextra_bed_price, dbase_price = self.get_booking_slot_price(dynamic_price)
                        date_based_price_dict["extra_bed_price"] = dextra_bed_price
                        # adult price
                        total_extra_bed_price = dextra_bed_price * extra_adults_allotted
                        # child price
                        dynamic_child_allotted = []
                        for child_price in child_allotted:
                            age = child_price.get('age', 0)
                            age_price = self.get_booking_dynamic_slot_price(age, dynamic_price)
                            total_child_price = total_child_price + age_price
                            dynamic_child_allotted.append({"age":age, "price":age_price})
                    else:
                        dbase_price, dslot_price = base_price, slot_price
                        total_extra_bed_price = extra_bed_price * extra_adults_allotted
                        date_based_price_dict["extra_bed_price"] = extra_bed_price
                        # child price
                        dynamic_child_allotted = child_allotted
                        for child_price in child_allotted:
                            ch_price = child_price.get('price', 0)
                            total_child_price = total_child_price + ch_price
                        
                    date_based_price_dict["base_price"] = dbase_price
                    date_based_price_dict["slot_price"] = dslot_price
                    date_based_price_dict["child_allotted"] = dynamic_child_allotted
                    
                    # calculate tax
                    no_of_days = 1
                    total_tax_amount, tax_in_percent, tax_amount = self.tax_calculation(
                        dbase_price, dslot_price, no_of_days, no_of_rooms,
                        total_extra_bed_price, total_child_price, total_tax_amount)

                    # calculate total room amount
                    total_room_amount = self.room_calculation(dbase_price, dslot_price, no_of_days, no_of_rooms,
                                                              total_extra_bed_price, total_child_price,
                                                              total_room_amount)
                    date_based_price_dict["tax_in_percent"] = tax_in_percent
                    date_based_price_dict["tax_amount"] = tax_amount
                    date_based_price_list.append(date_based_price_dict)
                    
                    
            else:
                total_child_price = 0
                for child_price in child_allotted:
                    total_child_price = total_child_price + child_price.get('price', 0)
                # calculate tax
                no_of_days = self.no_of_days
                total_extra_bed_price = extra_bed_price * extra_adults_allotted
                total_tax_amount, tax_in_percent, tax_amount = self.tax_calculation(
                    base_price, slot_price, no_of_days, no_of_rooms,
                    total_extra_bed_price, total_child_price, total_tax_amount)

                # calculate total room amount
                total_room_amount = self.room_calculation(base_price, slot_price, no_of_days, no_of_rooms,
                                                     total_extra_bed_price, total_child_price,
                                                     total_room_amount)
                
            
            # Calculate room discount
            if room_discount_type == 'AMOUNT':
                room_discount_value = min(room_discount, total_room_amount)
            else:
                discount_percentage = min(room_discount, 100)
                room_discount_value = (total_room_amount * discount_percentage) / 100
                
            # Calculate room amount with discount
            total_room_amount_with_discount = total_room_amount - room_discount_value
            
            self.total_room_amount_without_room_discount += int(total_room_amount)
            self.total_room_amount_with_room_discount += int(total_room_amount_with_discount)
                
            # Final amount calculation (using discounted room amount)
            final_room_total = total_room_amount_with_discount + total_tax_amount

            # final_room_total = total_room_amount + total_tax_amount

            confirmed_room = {"room_id": room_id, "room_type":room_type, "base_price":base_price,
                              "price": booking_room_price,
                              "no_of_rooms": no_of_rooms,
                              "tax_in_percent": tax_in_percent, "tax_amount": tax_amount,
                              "total_tax_amount": total_tax_amount,
                              "no_of_days": self.no_of_days, "total_room_amount":total_room_amount,
                              "room_discount": room_discount,
                              "room_discount_type": room_discount_type,
                              "room_discount_value": room_discount_value,
                              "room_amount_with_discount": total_room_amount_with_discount,
                              "room_amount_without_discount": float(total_room_amount),
                              "final_room_total": final_room_total, "booking_slot":self.booking_slot,
                              "extra_adults_allotted":extra_adults_allotted, "extra_bed_price":extra_bed_price,
                              "child_allotted":child_allotted, "date_based_price_list": date_based_price_list
                              }
            
            self.confirmed_room_details.append(confirmed_room)
            # final amount
            # final_amount = final_amount + final_room_total
            self.final_tax_amount = self.final_tax_amount + total_tax_amount
            # self.subtotal = self.subtotal + int(total_room_amount_with_discount) # total room amount without tax and services
            self.subtotal = self.subtotal + total_room_amount # total room amount without tax and services

        #print("confirmed room details::", self.confirmed_room_details)

        return True, None

        

    def commission_calculation(self):
        com_amnt = 0
        tax_amount, tax_in_percent = 0, 0
        commission_details = None
        try:
            prop_comm = get_property_commission(self.property_id)
            if prop_comm:
                comm_type = prop_comm.commission_type
                commission = prop_comm.commission
                if comm_type == "PERCENT":
                    com_amnt = (commission * self.subtotal) / 100
                elif comm_type == "AMOUNT":
                    com_amnt = commission

                # tax_in_percent = get_tax_rate(com_amnt, self.tax_rules_dict)
                config = BasicAdminConfig.objects.get(code='commission_tax_percent')
                tax_in_percent = Decimal(config.value)
                tax_amount = calculate_tax(tax_in_percent, com_amnt)

                com_amnt_withtax = com_amnt + tax_amount
                commission_details = {"com_amnt":com_amnt, "tax_amount":tax_amount,
                                      "tax_percentage":tax_in_percent,
                                      "com_amnt_withtax":com_amnt_withtax,
                                      "commission": commission,
                                      "tcs":0.0, "tds":0.0,
                                      "commission_type": comm_type}
        except Exception as e:
            print(traceback.format_exc())
            print(e)
            
              
        return commission_details 
    
    def auto_room_allocation(self, request, property_id):
        """
        Automatically allocate rooms based on adult and child count if room_list is not provided.
        Uses lowest price rooms while ensuring all guests can be accommodated.
        """
        # property_id = request.data.get('property', None)
        adult_count = request.data.get('adult_count', 1)
        child_count = request.data.get('child_count', 0)
        booking_slot = request.data.get('booking_slot', '24 Hrs')
        
        if not property_id:
            return False, self.get_error_response(
                message="Property ID is required", status="error",
                errors=[], error_code="PROPERTY_MISSING",
                status_code=status.HTTP_400_BAD_REQUEST)
        
        # Get all available rooms for the property
        available_rooms = Room.objects.filter(
            property_id=property_id,
            active=True
        )
        
        # Check availability for these rooms
        available_room_list = get_available_room(
            self.checkin_datetime, self.checkout_datetime, property_id)
        
        # Create a dict of available room counts
        available_room_counts = {}
        for avail_room in available_room_list:
            room_id = avail_room.get('id')
            available_count = avail_room.get('current_available_room', 0)
            if available_count > 0:
                available_room_counts[room_id] = available_count
        
        # Filter available_rooms to only include rooms with available inventory
        available_rooms = [room for room in available_rooms if room.id in available_room_counts]

        # Sort rooms by price
        available_rooms = sorted(available_rooms, key=lambda room: get_room_price(room, booking_slot))
        
        # Construct room allocation
        allocated_rooms = []
        remaining_adults = adult_count
        remaining_children = child_count
        total_guests = remaining_adults + remaining_children
        
        for room in available_rooms:
            room_id = room.id
            available_count = available_room_counts.get(room_id, 0)
            
            if available_count <= 0:
                continue
            
            # Get room details for occupancy info
            room_detail = get_property_room_for_booking(property_id, room_id)
            if not room_detail:
                continue
                
            max_occupancy = room_detail.get('room_occupancy', {}).get('max_occupancy', 1)
            print(f"Room ID: {room_id}, Max Occupancy: {max_occupancy}, Available Count: {available_count}")
            
            # Calculate how many rooms of this type we need
            guests_per_room = max_occupancy
            rooms_needed = min(
                (total_guests + guests_per_room - 1) // guests_per_room,  # Ceiling division
                available_count
            )
            
            # How many guests can we accommodate with these rooms
            guests_accommodated = min(rooms_needed * guests_per_room, total_guests)
            total_guests -= guests_accommodated
            
            # If we need rooms of this type, add to allocation
            if rooms_needed > 0:
                print(f"Allocating {rooms_needed} rooms of Room ID: {room_id} for {guests_accommodated} guests")
                allocated_rooms.append({
                    "room_id": room_id,
                    "no_of_rooms": rooms_needed
                })
            
            # If all guests are allocated, break
            if total_guests == 0:
                break
        
        # Check if all guests could be allocated
        if total_guests > 0:
            return False, self.get_error_response(
                message="Could not find enough rooms to accommodate all guests",
                status="error",
                errors=[],
                error_code="INADEQUATE_ROOMS",
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        # Successfully allocated rooms
        self.room_list = allocated_rooms
        print(f"Final allocated rooms: {allocated_rooms}")
        return True, None

##    def amount_calculations(self):
##        
##        for room in self.room_list:
##            room_id = room.get('room_id', None)
##            no_of_rooms = room.get('no_of_rooms', None)
##            base_price = 0
##
##            room_detail = self.room_detail_dict.get(room_id)
##
##            # get room details
##            room_type = room_detail.get('room_type')
##            room_price = room_detail.get('room_price')
##            if not room_price:
##                custom_response = self.get_error_response(
##                    message=f"The room price details for {room_id} is missing", status="error",
##                    errors=[],error_code="ROOM_PRICE_MISSING",
##                    status_code=status.HTTP_400_BAD_REQUEST)
##                is_status = False
##                return is_status, custom_response
##
##            # get 24 hours price
##            base_price = room_price.get('base_rate', None)
##            if not base_price:
##                custom_response = self.get_error_response(
##                    message=f"The room price details for room id {room_id} is missing", status="error",
##                    errors=[],error_code="ROOM_PRICE_MISSING",
##                    status_code=status.HTTP_400_BAD_REQUEST)
##                is_status = False
##                return is_status, custom_response
##
##            if self.booking_slot == '12 Hrs':
##                slot_price = room_price.get('price_12hrs', None)
##                extra_bed_price = room_price.get('extra_bed_price_12hrs', 0)
##                booking_room_price = slot_price
##            elif self.booking_slot == '8 Hrs':
##                slot_price = room_price.get('price_8hrs', None)
##                extra_bed_price = room_price.get('extra_bed_price_8hrs', 0)
##                booking_room_price = slot_price
##            elif self.booking_slot == '4 Hrs':
##                slot_price = room_price.get('price_4hrs', None)
##                extra_bed_price = room_price.get('extra_bed_price_4hrs', 0)
##                booking_room_price = slot_price
##            else:
##                slot_price = None
##                extra_bed_price = room_price.get('extra_bed_price', 0)
##                booking_room_price = base_price
##                
##            if not slot_price and not self.booking_slot == '24 Hrs':
##                custom_response = self.get_error_response(
##                    message=f"The {booking_slot} hrs room price for room id {room_id} is missing", status="error",
##                    errors=[],error_code="ROOM_PRICE_MISSING",
##                    status_code=status.HTTP_400_BAD_REQUEST)
##                is_status = False
##                return is_status, custom_response
##                    
##            print("extra bed price::", extra_bed_price)    
##            # get tax percent based on amount
##            tax_in_percent = get_tax_rate(base_price, self.tax_rules_dict)
##            if not tax_in_percent:
##                custom_response = self.get_error_response(
##                    message=f"The room price details for room id {room_id} is missing", status="error",
##                    errors=[],error_code="ROOM_PRICE_MISSING",
##                    status_code=status.HTTP_400_BAD_REQUEST)
##                is_status = False
##                return is_status, custom_response
##
##            # tax percentage based on base price
##            tax_in_percent = float(tax_in_percent)
##
##            # for extra bed calculation
##            occup_details = self.room_occupancy_dict.get(room_id)
##            extra_adults_allotted = occup_details.get('extra_adults_allotted', 0)
##            child_allotted = occup_details.get('child_allotted', [])
##
##            if extra_adults_allotted:
##                total_extra_bed_price = extra_bed_price * extra_adults_allotted
##
##            
##            # tax calculation based on booked 
##            if self.booking_slot == '24 Hrs':
##                tax_amount = calculate_tax(tax_in_percent, base_price)
##                
##            else:
##                tax_amount = calculate_tax(tax_in_percent, slot_price)
##
##            # calculate total tax amount
##            total_tax_amount =   calculate_room_booking_amount(
##                tax_amount, self.no_of_days, no_of_rooms)
##
##            # calculate tax amount for extra person
##            if extra_adults_allotted:
##                tax_amount_xbed = calculate_tax(tax_in_percent, total_extra_bed_price)
##                total_tax_amount_xbed = calculate_xbed_amount(tax_amount_xbed, self.no_of_days)
##
##                # total tax amount including extra bed
##                total_tax_amount = total_tax_amount + total_tax_amount_xbed
##
##            total_child_price = 0
##            if child_allotted:
##                for child_price in child_allotted:
##                    total_child_price = total_child_price + child_price.get('price', 0)
##            # calculate tax amount for children
##            if total_child_price:
##                tax_amount_child = calculate_tax(tax_in_percent, total_child_price)
##                total_tax_amount_child = calculate_xbed_amount(tax_amount_child, self.no_of_days)
##
##                # total tax amount including extra bed
##                total_tax_amount = total_tax_amount + total_tax_amount_child
##                
##                
##            
##            # calculate total room amount
##            if self.booking_slot == '24 Hrs':
##                total_room_amount = calculate_room_booking_amount(
##                    base_price, self.no_of_days, no_of_rooms)
##            else:
##                total_room_amount = calculate_room_booking_amount(
##                    slot_price, self.no_of_days, no_of_rooms)
##
##            # calculate extra bed amount
##            if extra_adults_allotted:
##                total_room_amount_xbed = calculate_xbed_amount(total_extra_bed_price, self.no_of_days)
##                total_room_amount = total_room_amount + total_room_amount_xbed
##
##            # calculate children price
##            if total_child_price:
##                total_child_amount = calculate_xbed_amount(total_child_price, self.no_of_days)
##                total_room_amount = total_room_amount + total_child_amount
##            
##            
##            final_room_total = total_room_amount + total_tax_amount
##
##            
##            confirmed_room = {"room_id": room_id, "room_type":room_type, "base_price":base_price,
##                              "price": booking_room_price,
##                              "no_of_rooms": no_of_rooms,
##                              "tax_in_percent": tax_in_percent, "tax_amount": tax_amount,
##                              "total_tax_amount": total_tax_amount,
##                              "no_of_days": self.no_of_days, "total_room_amount":total_room_amount,
##                              "final_room_total": final_room_total, "booking_slot":self.booking_slot,
##                              "extra_adults_allotted":extra_adults_allotted, "extra_bed_price":extra_bed_price,
##                              "child_allotted":child_allotted
##                              }
##            
##            self.confirmed_room_details.append(confirmed_room)
##            # final amount
##            # final_amount = final_amount + final_room_total
##            self.final_tax_amount = self.final_tax_amount + total_tax_amount
##            self.subtotal = self.subtotal + total_room_amount # total room amount without tax and services
##
##        print("confirmed room details::", self.confirmed_room_details)
##
##        return True, None

    

            
