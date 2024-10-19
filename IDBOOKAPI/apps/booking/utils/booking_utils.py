# booking utils

def generate_html_for_mail(booking):
    if booking:
        booking_type = booking.booking_type
        adult_count = booking.adult_count
        child_count = booking.child_count
        name = booking.user.name
        email = booking.user.email
        mobile_number = booking.user.mobile_number

##        html_content = f'''<p>Booking Enquiry as follows: </p>
##Booking Type:: {booking_type} <br> No.of Adult::{adult_count} <br>
##No.of Child::{child_count} <br>'''

        context = {'booking_type': booking_type, 'name':name,
                   'email':email, 'mobile_number':mobile_number}

        if booking_type == "HOTEL":
            hotel_booking = booking.hotel_booking
            if hotel_booking:
                enquired_property = hotel_booking.enquired_property
                checkin_time = hotel_booking.checkin_time
                checkout_time = hotel_booking.checkout_time

##                hotel_booking_content = f'''Enquired Property:: {enquired_property} <br>
##CheckIn Time::{checkin_time} <br>
##CheckOut Time:: {checkout_time} <br>'''
##
##                html_content = html_content + hotel_booking_content
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

##                holidaypack_booking_content = f'''Enquired Holiday Package:: {enquired_holiday_package} <br>
##No of Days:: {no_days} <br> Available Start Date:: {available_start_date} <br>'''
##                html_content = html_content + holidaypack_booking_content
                
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

##                vehicle_booking_content = f'''PickUp Address:: {pickup_addr} <br>
##Drop Off Address:: {dropoff_addr} <br> 'PickUp Time:: {pickup_time} <br>'''
##
##                html_content = html_content + vehicle_booking_content
                
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

##                flight_booking_content = f'''Flight Trip:: {flight_trip} <br>
##Flight Class:: {flight_class} <br> Departure Date:: {departure_date} <br>
##Return Date:: {return_date} <br> Flying From:: {flying_from} <br>
##Flying To:: {flying_to} <br>'''
##                html_content = html_content + flight_booking_content
                
                
        return context

                
                
            
            
