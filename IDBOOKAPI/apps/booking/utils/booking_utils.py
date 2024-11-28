# booking utils
from IDBOOKAPI.otp_utils import generate_otp
from django.conf import settings
from IDBOOKAPI.utils import get_current_date

from apps.authentication.utils.db_utils import get_user_by_referralcode

from apps.customer.utils.db_utils import (
    add_company_wallet_amount, update_wallet_transaction,
    deduct_wallet_balance, deduct_company_wallet_balance,
    add_user_wallet_amount)
from apps.customer.utils.db_utils import (
        get_wallet_balance,  get_company_wallet_balance)

from apps.org_resources.db_utils import create_notification
from apps.org_resources.utils.notification_utils import  wallet_booking_balance_notification_template

from apps.org_managements.utils import get_active_business


def generate_booking_confirmation_code(booking_id, booking_type):
    random_number = generate_otp(no_digits=4)
    cdate = get_current_date()
    
    confirmation_code = "IDB{booking_type}CNF{booking_id}-{month}{year}{random_number}".format(
        booking_type=booking_type, booking_id=booking_id,
        random_number=random_number, month=cdate.month, year=cdate.year)

    return confirmation_code

def generate_booking_reference_code(booking_id, booking_type):
    random_number = generate_otp(no_digits=4)
    cdate = get_current_date()

    reference_code = "IDB{booking_type}BKG{booking_id}-{month}{year}{random_number}".format(
        booking_type=booking_type, booking_id=booking_id,
        random_number=random_number, month=cdate.month, year=cdate.year)

    return reference_code
    

def generate_htmlcontext_search_booking(booking):
    if booking:
        booking_type = booking.booking_type
        adult_count = booking.adult_count
        child_count = booking.child_count
        name = booking.user.name
        email = booking.user.email
        mobile_number = booking.user.mobile_number

        context = {'booking_type': booking_type, 'name':name,
                   'email':email, 'mobile_number':mobile_number}

        if booking_type == "HOTEL":
            hotel_booking = booking.hotel_booking
            if hotel_booking:
                enquired_property = hotel_booking.enquired_property
                checkin_time = hotel_booking.checkin_time
                checkout_time = hotel_booking.checkout_time

                context['enquired_property'] =  enquired_property
                context['checkin_time'] =  checkin_time
                context['checkout_time'] =  checkout_time
                context['adult_count'] = adult_count
                context['child_count'] = child_count
                # html_content = email_template.render(context)
                
        elif booking_type == "HOLIDAYPACK":
            holidaypack_booking = booking.holiday_package_booking
            if holidaypack_booking:
                enquired_holiday_package = holidaypack_booking.enquired_holiday_package
                no_days = holidaypack_booking.no_days
                available_start_date = holidaypack_booking.available_start_date

                context['enquired_holiday_package'] = enquired_holiday_package
                context['no_days'] =  no_days
                context['available_start_date'] =  available_start_date
                context['adult_count'] = adult_count
                context['child_count'] = child_count
                
        elif booking_type == "VEHICLE":
            vehicle_booking = booking.vehicle_booking
            
            if vehicle_booking:
                pickup_addr = vehicle_booking.pickup_addr
                dropoff_addr = vehicle_booking.dropoff_addr
                pickup_time = vehicle_booking.pickup_time
                vehicle_type = vehicle_booking.vehicle_type

                context['pickup_addr'] = pickup_addr
                context['dropoff_addr'] =  dropoff_addr
                context['pickup_time'] =  pickup_time
                context['vehicle_type'] =  vehicle_type
                context['adult_count'] = adult_count
                context['child_count'] = child_count
                
        elif booking_type == 'FLIGHT':
            flight_booking = booking.flight_booking
            
            if flight_booking:
                flight_trip = flight_booking.flight_trip
                flight_class = flight_booking.flight_class
                departure_date = flight_booking.departure_date
                return_date = flight_booking.return_date
                flying_from = flight_booking.flying_from
                flying_to = flight_booking.flying_to

                context['flight_trip'] =  flight_trip
                context['flight_class'] =  flight_class
                context['departure_date'] =  departure_date
                context['return_date'] = return_date
                context['flying_from'] = flying_from
                context['flying_to'] = flying_to
                context['adult_count'] = adult_count
                context['child_count'] = child_count
                
                
        return context

                
def generate_context_confirmed_booking(booking):
    booking_type = booking.booking_type
    adult_count = booking.adult_count
    child_count = booking.child_count
    name = booking.user.name
    email = booking.user.email
    mobile_number = booking.user.mobile_number
    total_payment_made = booking.total_payment_made
    confirmation_code = booking.confirmation_code
    final_amount = booking.final_amount
    total_balance_due = final_amount - total_payment_made
    subtotal = booking.subtotal
    tax = booking.gst_amount

    invoice_id = booking.invoice_id    
    booking_link = f"{settings.FRONTEND_URL}/bookings/{booking.id}"
    invoice_link = f"{settings.INV_FE_URL}/invoice/{invoice_id}"
    occupancy = "{adult_count} Adults".format(adult_count=adult_count)
    if child_count:
        occupancy = occupancy + "{child_count} Child".format(
            child_count=child_count)
        
    context = {'booking_type': booking_type, 'name':name,
               'email':email, 'mobile_number':mobile_number,
               'total_payment_made':float(total_payment_made),
               'confirmation_code':confirmation_code,
               'occupancy':occupancy,
               'total_balance_due':float(total_balance_due),
               'total_booking_amount':float(final_amount),
               'subtotal':float(subtotal), 'tax':float(tax),
               'booking_link':booking_link,
               'invoice_link':invoice_link}
    
    if booking_type == "HOTEL":
        property_name, property_address = '', ''
        property_email, property_phone_no = '', ''
        room_type = ''
        area_name, city_name, state, country = '', '', '', ''
        
        confirmed_checkin_time, confirmed_checkout_time = None, None
        room_subtotal, service_tax = None, None
        
        
        hotel_booking = booking.hotel_booking
        if hotel_booking:
            confirmed_checkin_time = hotel_booking.confirmed_checkin_time
            confirmed_checkout_time = hotel_booking.confirmed_checkout_time
            
            confirmed_property = hotel_booking.confirmed_property
            if confirmed_property:
                property_name = confirmed_property.name
                property_address = confirmed_property.address
                property_email = confirmed_property.email
                property_phone_no = confirmed_property.phone_no
                area_name = confirmed_property.area_name
                city_name = confirmed_property.city_name
                state = confirmed_property.state
                country = confirmed_property.country
                
            confirmed_rooms = hotel_booking.confirmed_room_details
            if not confirmed_rooms:
                context['confirmed_rooms'] = []
            else:
                context['confirmed_rooms'] = confirmed_rooms
                
##                room_type = confirmed_room.room_type
##                price_for_24_hours = confirmed_room.price_for_24_hours

        

        context['confirmed_checkin_time'] = confirmed_checkin_time
        context['confirmed_checkout_time'] = confirmed_checkout_time

        context['property_name'] = property_name

        {"pincode": "", "coordinates": {"lat": "", "lng": ""}, "location_url": "", "building_or_hse_no": ""}
        if property_address:
            pincode = property_address.get('pincode', '')
            building_no = property_address.get('building_or_hse_no', '')
            final_address = f"{building_no}, {area_name}, {city_name}, {state} - {pincode}, {country}"
        else:
            final_address = f" {area_name}, {city_name}, {state}, {country}"
            
        context['property_address'] = final_address
        context['property_email'] = property_email
        context['property_phone_no'] = property_phone_no

        # context['room_type'] = room_type
        
    elif booking_type == "HOLIDAYPACK":
        holidaypack_booking = booking.holiday_package_booking
        trip_id, trip_name = "", ""
        tour_duration, date_of_journey = "", ""

        daily_plans = []
        
        if holidaypack_booking:
           confirmed_pack = holidaypack_booking.confirmed_holiday_package
           if confirmed_pack:
               trip_id = confirmed_pack.trip_id
               trip_name = confirmed_pack.trip_name
               tour_duration = confirmed_pack.tour_duration
               date_of_journey = confirmed_pack.date_of_journey
               daily_plans = confirmed_pack.tour_daily_plan.all()
               print("daily plan::", daily_plans)

##               for dplan in daily_plans:
##                   title = dplan.title
##                   plan_date = dplan.plan_date
##                   stay = dplan.stay
##                   check_in = dplan.check_in
##                   check_out = dplan.check_out
##                   detailed_plan

        context['trip_id'] = trip_id
        context['trip_name'] = trip_name
        context['tour_duration'] = tour_duration
        context['date_of_journey'] = date_of_journey
        context['daily_plans'] = daily_plans

    elif booking_type == "VEHICLE":
        pickup_addr, dropoff_addr = '', ''
        pickup_time, vehicle_type = '', ''
        vehicle_no, driver_name = '', ''
        contact_email, contact_number = '', ''
        vehicle_subtotal, service_tax = '', ''
        
        vehicle_booking = booking.vehicle_booking
        if vehicle_booking:
                pickup_addr = vehicle_booking.pickup_addr
                dropoff_addr = vehicle_booking.dropoff_addr
                pickup_time = vehicle_booking.pickup_time

                confirmed_vehicle = vehicle_booking.confirmed_vehicle
                if confirmed_vehicle:
                    vehicle_type = confirmed_vehicle.vehicle_type
                    vehicle_no = confirmed_vehicle.vehicle_no
                    driver_name = confirmed_vehicle.driver_name
                    contact_email = confirmed_vehicle.contact_email
                    contact_number = confirmed_vehicle.contact_number       
            
        context['pickup_addr'] = pickup_addr
        context['dropoff_addr'] =  dropoff_addr
        context['pickup_time'] =  pickup_time
        context['vehicle_type'] =  vehicle_type
        context['vehicle_no'] = vehicle_no
        context['driver_name'] =  driver_name
        context['contact_email'] =  contact_email
        context['contact_number'] = contact_number
        
    elif booking_type == "FLIGHT":
        flight_trip, flight_class = '', ''
        departure_date, return_date = '', ''
        flying_from, flying_to = '', ''
        flight_subtotal, service_tax = '', ''
        
        flight_booking = booking.flight_booking
        if flight_booking:
            flight_trip = flight_booking.flight_trip
            flight_class = flight_booking.flight_class
            departure_date = flight_booking.departure_date
            return_date = flight_booking.return_date
            flying_from = flight_booking.flying_from
            flying_to = flight_booking.flying_to

        context['flight_trip'] = flight_trip
        context['flight_class'] =  flight_class
        context['departure_date'] =  departure_date
        context['return_date'] =  return_date
        context['flying_from'] = flying_from
        context['flying_to'] =  flying_to

    return context

def generate_context_cancelled_booking(booking):
    booking_type = booking.booking_type
    name = booking.user.name
    email = booking.user.email
    mobile_number = booking.user.mobile_number
    total_payment_made = booking.total_payment_made

    booking_link = f"{settings.FRONTEND_URL}/bookings/{booking.id}"

    context = {'booking_type': booking_type, 'name':name,
               'email':email, 'mobile_number':mobile_number,
               'total_payment_made':float(total_payment_made),
               'reference_number':booking.reference_code,
               'booking_link':booking_link}

    if booking_type == "HOTEL":
        property_name, room_type = '', ''
        confirmed_checkin_time, confirmed_checkout_time = None, None
        
        
        hotel_booking = booking.hotel_booking
        if hotel_booking:
            confirmed_checkin_time = hotel_booking.confirmed_checkin_time
            confirmed_checkout_time = hotel_booking.confirmed_checkout_time

            confirmed_property = hotel_booking.confirmed_property
            if confirmed_property:
                property_name = confirmed_property.name
                
            confirmed_room = hotel_booking.room
            if confirmed_room:
                room_type = confirmed_room.room_type
        

        context['confirmed_checkin_time'] = confirmed_checkin_time
        context['confirmed_checkout_time'] = confirmed_checkout_time
        context['property_name'] = property_name
        context['room_type'] = room_type

    elif booking_type == "HOLIDAYPACK":
        holidaypack_booking = booking.holiday_package_booking
        trip_id, trip_name = "", ""
        tour_duration, date_of_journey = "", ""

        if holidaypack_booking:
           confirmed_pack = holidaypack_booking.confirmed_holiday_package
           if confirmed_pack:
               trip_id = confirmed_pack.trip_id
               trip_name = confirmed_pack.trip_name
               tour_duration = confirmed_pack.tour_duration
               date_of_journey = confirmed_pack.date_of_journey

        context['trip_id'] = trip_id
        context['trip_name'] = trip_name
        context['tour_duration'] = tour_duration
        context['date_of_journey'] = date_of_journey

    elif booking_type == "VEHICLE":
        pickup_addr, dropoff_addr = '', ''
        pickup_time, vehicle_type = '', ''
        vehicle_no = ''
        
        vehicle_booking = booking.vehicle_booking
        if vehicle_booking:
            pickup_addr = vehicle_booking.pickup_addr
            dropoff_addr = vehicle_booking.dropoff_addr
            pickup_time = vehicle_booking.pickup_time

            confirmed_vehicle = vehicle_booking.confirmed_vehicle
            if confirmed_vehicle:
                vehicle_type = confirmed_vehicle.vehicle_type
                vehicle_no = confirmed_vehicle.vehicle_no
                 
            
        context['pickup_addr'] = pickup_addr
        context['dropoff_addr'] =  dropoff_addr
        context['pickup_time'] =  pickup_time
        context['vehicle_type'] =  vehicle_type
        context['vehicle_no'] = vehicle_no

    elif booking_type == "FLIGHT":
        flight_trip, flight_class = '', ''
        departure_date, return_date = '', ''
        flying_from, flying_to = '', ''
        
        flight_booking = booking.flight_booking
        if flight_booking:
            flight_trip = flight_booking.flight_trip
            flight_class = flight_booking.flight_class
            departure_date = flight_booking.departure_date
            return_date = flight_booking.return_date
            flying_from = flight_booking.flying_from
            flying_to = flight_booking.flying_to

        context['flight_trip'] = flight_trip
        context['flight_class'] =  flight_class
        context['departure_date'] =  departure_date
        context['return_date'] =  return_date
        context['flying_from'] = flying_from
        context['flying_to'] =  flying_to
        
        
    return context
    

    

def calculate_total_amount(booking):
    total_booking_amount = 0
    booking_type = booking.booking_type
    coupon = booking.coupon
    coupon_discount, gst_amount = 0, 0

    try:
        total_booking_amount = booking.subtotal

        # coupon deduction
        if coupon and coupon.discount:
            if coupon.discount_type == 'AMOUNT':
                total_booking_amount = total_booking_amount - coupon.discount
                coupon_discount = coupon.discount
            elif coupon.discount_type == 'PERCENT':
                coupon_discount = (coupon.discount * total_booking_amount) / 100
                total_booking_amount = total_booking_amount - coupon_discount

        #  gst calculation
        gst_percentage = booking.gst_percentage
        if gst_percentage:
            gst_amount = (gst_percentage * total_booking_amount) / 100
        
        
        total_booking_amount = total_booking_amount + gst_amount
    except Exception as e:
        print('Error in booking total amount calculation', e)

    return total_booking_amount, gst_amount, coupon_discount
    
def set_firstbooking_reward(referred_code):
    user = get_user_by_referralcode(referred_code)
    if user:
        reward_amount = 1000
        company_id = user.company_id
        if company_id:
            status = add_company_wallet_amount(company_id, reward_amount)
        else:
            status = add_user_wallet_amount(user.id, reward_amount)

        if status:
            transaction_details = f"Amount credited based on referral code"
            wtransact_dict = {'user_id':user.id, 'amount':reward_amount,
                              'transaction_type':'Credit', 'transaction_details':transaction_details,
                              'company_id':company_id}
            update_wallet_transaction(wtransact_dict)
        

def deduct_booking_amount(booking, company_id=None):
    deduct_amount = booking.final_amount # - float(booking.total_payment_made)
    if company_id:
        status = deduct_company_wallet_balance(company_id, deduct_amount)
    else:
        status = deduct_wallet_balance(booking.user.id, deduct_amount)

    if status:
        transaction_details = f"Amount debited for {booking.booking_type} \
booking ({booking.confirmation_code})"
        wtransact_dict = {'user':booking.user, 'amount':deduct_amount,
                          'transaction_type':'Debit', 'transaction_details':transaction_details,
                          'company_id':company_id}
        update_wallet_transaction(wtransact_dict)

    return status

def calculate_room_booking_amount(amount, no_of_days, no_of_rooms):
    total_amount = (amount * no_of_rooms) * no_of_days 
    return total_amount

def get_tax_rate(amount, tax_rules_dict):
    tax_rate_in_percent = None
    for tax_rule in tax_rules_dict:
        symbol = tax_rule.get('math_compare_symbol','')
        amount1 = tax_rule.get('amount1', None)
        tax_rate_in_percent = tax_rule.get('tax_rate_in_percent', None)

        if not amount1 or not symbol or not tax_rate_in_percent:
            break
        

        if symbol == 'EQUALS' and amount == amount1:
            return tax_rate_in_percent
        elif symbol == 'LESS-THAN' and amount < amount1:
            return tax_rate_in_percent
        elif symbol == 'LESS-THAN-OR-EQUALS' and amount <= amount1:
            return tax_rate_in_percent
        elif symbol == 'GREATER-THAN' and amount > amount1:
            return tax_rate_in_percent
        elif symbol == 'GREATER-THAN-OR-EQUALS' and amount >= amount1:
            return tax_rate_in_percent
        elif symbol == 'BETWEEN':
            amount2 = tax_rule.get('amount2', None)
            if not amount2:
                break
            if amount1 <= amount <= amount2:
                return tax_rate_in_percent
        
    return tax_rate_in_percent


def check_wallet_balance_for_booking(booking, user, company_id=None):
    try:
        if company_id:
                balance = get_company_wallet_balance(company_id)
        else:
                balance = get_wallet_balance(user.id)
             
        if balance < booking.final_amount:
            
            # send wallet balance notification
            send_by = None
            bus_details = get_active_business() 
            if bus_details:
                send_by = bus_details.user
                
            notification_dict = {'user':user, 'send_by':send_by, 'notification_type':'GENERAL',
                                 'title':'', 'description':'', 'redirect_url':'',
                                 'image_link':''}
            notification_dict = wallet_booking_balance_notification_template(
                    booking, balance, notification_dict)
            create_notification(notification_dict)
    except Exception as e:
        print(e)
    
            
            
            
            
        
    
           
   
    
    
         
         

    
        
            
            
            
