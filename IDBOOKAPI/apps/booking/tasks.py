from IDBOOKAPI.celery import app as celery_idbook
from IDBOOKAPI.email_utils import send_booking_email, send_booking_email_with_attachment
from apps.booking.utils.db_utils import get_booking
from apps.booking.utils.booking_utils import (
    generate_htmlcontext_search_booking,
    generate_context_confirmed_booking)

from django.template.loader import get_template
from django.conf import settings


@celery_idbook.task(bind=True)
def send_booking_email_task(self, booking_id, booking_type='search-booking'):
    print("Initiated Booking Email Process")
    print(booking_id)
    booking = get_booking(booking_id)
    subject = ""
    attachment = False
    file = None
    if booking:
        if booking_type == 'confirmed-booking':
            user_email = booking.user.email
            print("Inside Confirmd ")
            subject = "Booking Confirmed"
            if booking.booking_type == 'HOTEL':
                email_template = get_template('email_template/booking-confirmation.html')
            elif booking.booking_type == 'HOLIDAYPACK':
                email_template = get_template('email_template/booking-confirmation-holidaypack.html')
            elif booking.booking_type == 'HOLIDAYPACK':
                email_template = get_template('email_template/booking-confirmation-holidaypack.html')
            elif booking.booking_type == 'VEHICLE':
                email_template = get_template('email_template/booking-confirmation-vehicle.html')
            elif booking.booking_type == 'FLIGHT':
                email_template = get_template('email_template/booking-confirmation-flight.html')
                if booking.flight_booking and booking.flight_booking.flight_ticket:
                    file = booking.flight_booking.flight_ticket
                attachment = True
                
            context = generate_context_confirmed_booking(booking)
            print("context", context)
            html_content = email_template.render(context)
            print(user_email)
            if attachment:
                send_booking_email_with_attachment(subject, file, [user_email], html_content)
            else:
                send_booking_email(subject, booking, [user_email], html_content)
            
        else:
            subject = "Booking Enquiry"
            email_template = get_template('email_template/booking-search.html')
            context = generate_htmlcontext_search_booking(booking)
            html_content = email_template.render(context)
            # corporates@idbookhotels.com
            send_email = settings.CORPORATE_EMAIL
            print(send_email)
            send_booking_email(subject, booking, [send_email, 'sonu@idbookhotels.com'], html_content)
    
    #send_otp_email(otp, to_emails)


