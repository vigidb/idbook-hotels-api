from IDBOOKAPI.celery import app as celery_idbook
from IDBOOKAPI.email_utils import send_booking_email, send_booking_email_with_attachment
from apps.booking.utils.db_utils import get_booking
from apps.booking.utils.booking_utils import (
    generate_htmlcontext_search_booking,
    generate_context_confirmed_booking,
    generate_context_cancelled_booking,
    set_firstbooking_reward)

from apps.booking.utils.invoice_utils import (
    invoice_json_data, create_invoice, get_invoice_number, update_invoice)

from django.template.loader import get_template
from django.conf import settings

from apps.org_managements.utils import get_business_by_name
from apps.org_resources.db_utils import get_company_details, create_notification
from apps.org_resources.utils.notification_utils import (
    wallet_minbalance_notification_template, booking_comfirmed_notification_template,
    booking_cancelled_notification_template)
from apps.log_management.utils.db_utils import create_booking_invoice_log
from apps.customer.utils.db_utils import get_wallet_balance

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

            try:    
            # Notification
                send_by = None
##                title = "{booking_type} Booking Confirmed".format(booking_type=booking.booking_type)
##                description = "We are pleased to confirm your {booking_type} booking. \
##The confirmation code is: {confirmation_code}".format(booking_type=booking.booking_type,
##                                                      confirmation_code=booking.confirmation_code)
##                redirect_url = "/booking/bookings/{booking_id}/".format(booking_id=booking.id)
                
                business_name = "Idbook"
                bus_details = get_business_by_name(business_name)
                if bus_details:
                    send_by = bus_details.user

                    
                notification_dict = {'user':booking.user, 'send_by':send_by, 'notification_type':'BOOKING',
                                     'title':'', 'description':'', 'redirect_url':'',
                                     'image_link':''}
                
                notification_dict = booking_comfirmed_notification_template(
                    booking.id, booking.booking_type, booking.confirmation_code,
                    notification_dict)
                create_notification(notification_dict)
            except Exception as e:
                print('Notification Error', e)
                  
            
        else:
            try:
                subject = "Booking Enquiry"
                email_template = get_template('email_template/booking-search.html')
                context = generate_htmlcontext_search_booking(booking)
                html_content = email_template.render(context)
                # corporates@idbookhotels.com
                send_email = settings.CORPORATE_EMAIL
                print(send_email)
                send_booking_email(subject, booking, [send_email, 'sonu@idbookhotels.com'], html_content)
                # check wallet balance
                # if low, then send a notification
                if booking.user:
                    balance = get_wallet_balance(booking.user.id)
                    if balance < 1000:
                        send_by = None
                        business_name = "Idbook"
                        bus_details = get_business_by_name(business_name)
                        if bus_details:
                            send_by = bus_details.user
                            
                        notification_dict = {'user':booking.user, 'send_by':send_by, 'notification_type':'GENERAL',
                                             'title':'', 'description':'', 'redirect_url':'',
                                             'image_link':''}
                        notification_dict = wallet_minbalance_notification_template(balance, notification_dict)
                        create_notification(notification_dict)
            except Exception as e:
                print("Error in search booking email task", e)
                    
                        
                    
                    
    
    #send_otp_email(otp, to_emails)

@celery_idbook.task(bind=True)
def create_invoice_task(self, booking_id):
    company_details = None
    print("Inside Invoice Task")
    try:
        booking = get_booking(booking_id)

        if booking:
            try:
                if booking.user and booking.user.referred_code:
                    if not booking.user.first_booking:
                        set_firstbooking_reward(booking.user.referred_code)
            except Exception as e:
                print("Error in setting reward points", e)
            
            business_name = "Idbook"
            bus_details = get_business_by_name(business_name)

            if booking.user:
                company_id = booking.user.company_id
                if company_id:
                    company_details = get_company_details(company_id)

            if not booking.invoice_id:
                invoice_number = get_invoice_number()
                print(invoice_number)
                payload = invoice_json_data(booking, bus_details,
                                            company_details, invoice_number)
                response = create_invoice(payload)

                print(response.status_code)
                if response.status_code == 201:
                    data = response.json()
                    invoice_data = data.get('data', '')
                    invoice_id = invoice_data.get('_id', '')
                    if invoice_id:
                        booking.invoice_id = invoice_number
                        booking.save()
           
                invoice_log = {'booking':booking, 'status_code':response.status_code,
                               'response': response.json()}
                create_booking_invoice_log(invoice_log)
                    
            else:
                payload = invoice_json_data(booking, bus_details, company_details,
                                            None, invoice_action='update')
                response = update_invoice(booking.invoice_id, payload)
                invoice_log = {'booking':booking, 'status_code':response.status_code,
                               'response': response.json()}
                create_booking_invoice_log(invoice_log)

            send_booking_email_task.apply_async(args=[booking_id, 'confirmed-booking'])
    except Exception as e:
        print("Invoice Error", e)
    
@celery_idbook.task(bind=True)
def send_cancelled_booking_task(self, booking_id):
    """ send email and notification for cancelled booking """
    print("Inside cancelled booking task")
    try:
        booking = get_booking(booking_id)
        if booking:
            # send cancellation email
            subject = "Booking Cancelled"
            user_email = booking.user.email
            email_template = get_template('email_template/cancel-confirmation.html')
            context = generate_context_cancelled_booking(booking)
            html_content = email_template.render(context)
            send_booking_email(subject, booking, [user_email], html_content)

            # send notification email
            business_name = "Idbook"
            bus_details = get_business_by_name(business_name)
            if bus_details:
                send_by = bus_details.user
    
            notification_dict = {'user':booking.user, 'send_by':send_by, 'notification_type':'BOOKING',
                                 'title':'', 'description':'', 'redirect_url':'',
                                 'image_link':''}
            
            notification_dict = booking_cancelled_notification_template(
                booking.id, booking.booking_type, 'DUMMY',
                notification_dict)
            create_notification(notification_dict)
            
    except Exception as e:
        print('Cancelled Email Task', e)
        
            
        



