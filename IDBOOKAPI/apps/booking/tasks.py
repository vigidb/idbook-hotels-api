from IDBOOKAPI.celery import app as celery_idbook
from IDBOOKAPI.email_utils import send_booking_email, send_booking_email_with_attachment
from apps.booking.utils.db_utils import get_booking, save_invoice_to_database, update_payment_details, update_invoice_in_database
from apps.booking.utils.booking_utils import (
    generate_htmlcontext_search_booking,
    generate_context_confirmed_booking,
    generate_context_cancelled_booking,
    generate_context_completed_booking,
    set_firstbooking_reward)

from apps.booking.utils.invoice_utils import (
    invoice_json_data, create_invoice, get_invoice_number, update_invoice, create_invoice_number, 
    create_invoice_response_data, generate_invoice_pdf)

from django.template.loader import get_template
from django.conf import settings

from apps.org_managements.utils import get_active_business #get_business_by_name
from apps.org_resources.db_utils import get_company_details, create_notification
from apps.org_resources.utils.notification_utils import (
    wallet_minbalance_notification_template, booking_comfirmed_notification_template,
    booking_cancelled_notification_template, booking_completed_notification_template,
    generate_user_notification)
from apps.log_management.utils.db_utils import create_booking_invoice_log
from apps.customer.utils.db_utils import (
    get_wallet_balance, get_company_wallet_balance, get_user_based_customer)
from apps.authentication.utils.db_utils import update_user_first_booking
from apps.sms_gateway.mixins.fastwosms_mixins import send_template_sms
from apps.authentication.models import User


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
                #business_name = "Idbook"
                bus_details = get_active_business() #get_business_by_name(business_name)
                if bus_details:
                    send_by = bus_details.user

                group_name = "CORPORATE-GRP" if booking.company_id else "B2C-GRP"
                notification_dict = {'user':booking.user, 'send_by':send_by, 'notification_type':'BOOKING',
                                     'title':'', 'description':'', 'redirect_url':'',
                                     'image_link':'', 'group_name': group_name}
                
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
                    if booking.user.company_id:
                        balance = get_company_wallet_balance(booking.user.company_id)
                    else:
                        balance = get_wallet_balance(booking.user.id)
                    if balance < 1000:
                        send_by = None
                        # business_name = "Idbook"
                        bus_details = get_active_business() #get_business_by_name(business_name)
                        if bus_details:
                            send_by = bus_details.user
                        group_name = "CORPORATE-GRP" if booking.company_id else "B2C-GRP"
                        notification_dict = {'user':booking.user, 'send_by':send_by, 'notification_type':'GENERAL',
                                             'title':'', 'description':'', 'redirect_url':'',
                                             'image_link':'', 'group_name': group_name}
                        notification_dict = wallet_minbalance_notification_template(balance, notification_dict)
                        create_notification(notification_dict)
            except Exception as e:
                print("Error in search booking email task", e)
                    
                        
                    
                    
    
    #send_otp_email(otp, to_emails)

@celery_idbook.task(bind=True)
def create_invoice_task(self, booking_id, pay_at_hotel=False):
    company_details = None
    customer_details = None
    print("Inside Invoice Task")
    try:
        booking = get_booking(booking_id)

        if booking:
            try:
                if booking.user and booking.user.referred_code:
                    if not booking.user.first_booking:
                        set_firstbooking_reward(booking.user.referred_code, booked_user_id=booking.user.id)
                        update_user_first_booking(booking.user.id)
            except Exception as e:
                print("Error in setting reward points", e)
            
            # business_name = "Idbook"
            bus_details = get_active_business() #get_business_by_name(business_name)
            print("booking.invoice_id", booking.invoice_id)
            if booking.user:
                company_id = booking.company_id
                if company_id:
                    company_details = get_company_details(company_id)
                else:
                    customer_details = get_user_based_customer(booking.user.id)

            if not booking.invoice_id:
                # invoice_number = get_invoice_number()
                invoice_number = create_invoice_number()
                print("invoice_number", invoice_number)
                payload = invoice_json_data(booking, bus_details,
                                            company_details, customer_details, invoice_number, pay_at_hotel=pay_at_hotel)


                invoice = save_invoice_to_database(booking, payload, invoice_number)
                
                if invoice:
                    # Generate the PDF invoice
                    try:
                        print("inside generate invoice")
                        generate_invoice_pdf(payload, booking_id=booking_id)
                    except Exception as e:
                        print(f"Error generating invoice PDF: {str(e)}")
                    booking = get_booking(booking_id)
                    booking.invoice_id = invoice_number
                    booking.save()
                    
                    update_payment_details(booking, invoice)
                # Create full response data similar to external API format
                response_data = create_invoice_response_data(invoice, payload)
                
                invoice_log = {
                    'booking': booking, 
                    'status_code': 201 if invoice else 400,
                    'response': response_data
                }
                create_booking_invoice_log(invoice_log)

                # response = create_invoice(payload)

                # print(response.status_code)
                # if response.status_code == 201:
                #     data = response.json()
                #     invoice_data = data.get('data', '')
                #     invoice_id = invoice_data.get('_id', '')
                #     if invoice_id:
                #         booking = get_booking(booking_id)
                #         booking.invoice_id = invoice_number
                #         booking.save()

           
                # invoice_log = {'booking':booking, 'status_code':response.status_code,
                #                'response': response.json()}
                # create_booking_invoice_log(invoice_log)
                    
            else:
                payload = invoice_json_data(booking, bus_details, company_details,
                                            customer_details, None, invoice_action='update', pay_at_hotel=pay_at_hotel)
                invoice = update_invoice_in_database(booking.invoice_id, payload, booking)
                print("invoice", invoice)

                if invoice:
                    update_payment_details(booking, invoice)

                response_data = create_invoice_response_data(invoice, payload)
                response = update_invoice(booking.invoice_id, payload)
                # invoice_log = {'booking':booking, 'status_code':response.status_code,
                #                'response': response.json()}
                invoice_log = {
                    'booking': booking, 
                    'status_code': 200 if invoice else 400,
                    'response': response_data
                }
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
            # business_name = "Idbook"
            bus_details =  get_active_business() #get_business_by_name(business_name)
            if bus_details:
                send_by = bus_details.user
            group_name = "CORPORATE-GRP" if booking.company_id else "B2C-GRP"
            notification_dict = {'user':booking.user, 'send_by':send_by, 'notification_type':'BOOKING',
                                 'title':'', 'description':'', 'redirect_url':'',
                                 'image_link':'', 'group_name': group_name}
            
            notification_dict = booking_cancelled_notification_template(
                booking.id, booking.booking_type, f'CNCL-{booking.id}',
                notification_dict)
            create_notification(notification_dict)
            
    except Exception as e:
        print('Cancelled Email Task', e)
        
@celery_idbook.task(bind=True)
def send_completed_booking_task(self, booking_id):
    print("Inside completed booking task")
    try:
        booking = get_booking(booking_id)
        if booking:
            if booking.booking_type == "HOTEL":
                subject = "Hotel Stay Completed"
                user_email = booking.user.email
                print("user_email", user_email)
                email_template = get_template('email_template/booking-complete-review.html')
                print("email_template", email_template)
                context = generate_context_completed_booking(booking)
                html_content = email_template.render(context)
                send_booking_email(subject, booking, [user_email], html_content)
                
                bus_details = get_active_business()
                if bus_details:
                    send_by = bus_details.user
                group_name = "CORPORATE-GRP" if booking.company_id else "B2C-GRP"
                notification_dict = {'user': booking.user, 'send_by': send_by, 'notification_type': 'BOOKING',
                                    'title': '', 'description': '', 'redirect_url': '',
                                    'image_link': '', 'group_name': group_name}
                
                notification_dict = booking_completed_notification_template(
                    booking.id, booking.booking_type, notification_dict)
                create_notification(notification_dict)
            
    except Exception as e:
        print('Completion Email Task Error:', e)

@celery_idbook.task(bind=True)
def send_booking_sms_task(self, notification_type='', params=None):
    """
    Send SMS notification for different types of events
    
    Args:
        notification_type (str): Type of notification ('cancel', 'refund', 'wallet_recharge', etc.)
        params (dict): Dictionary containing all parameters needed for the specific notification type
    """
    if params is None:
        params = {}

    print(f"Inside {notification_type} SMS task")

    try:
        if notification_type == 'HOTEL_BOOKING_CANCEL':
            booking_id = params.get('booking_id')
            refund_amount = params.get('refund_amount', 0)

            booking = get_booking(booking_id)
            if booking and booking.user.mobile_number:
                mobile_number = booking.user.mobile_number
                template_code = "HOTEL_BOOKING_CANCEL"
                # variables_values = f"User|{booking.reference_code}|{refund_amount}"
                variables_values = f"{booking.user.name}|{booking.reference_code}|{refund_amount}"

                print("variables_values", variables_values)
                send_template_sms(mobile_number, template_code, variables_values)
                # generate_user_notification(
                #     notification_type='HOTEL_BOOKING_CONFIRMATION',
                #     user = booking.user,
                #     variables_values=variables_values,
                #     booking_id=booking.id
                # )

        elif notification_type == 'HOTEL_PAYMENT_REFUND':
            booking_id = params.get('booking_id')
            refund_amount = params.get('refund_amount', 0)

            booking = get_booking(booking_id)
            if booking and booking.user.mobile_number:
                mobile_number = booking.user.mobile_number
                template_code = "HOTEL_PAYMENT_REFUND"
                # variables_values = f"User|{refund_amount}|{booking.reference_code}"
                variables_values = f"{booking.user.name}|{refund_amount}|{booking.reference_code}"

                print("variables_values", variables_values)
                send_template_sms(mobile_number, template_code, variables_values)
                group_name = "CORPORATE-GRP" if booking.company_id else "B2C-GRP"
                generate_user_notification(
                    notification_type='HOTEL_PAYMENT_REFUND',
                    user=booking.user,
                    variables_values=variables_values,
                    booking_id=booking.id,
                    group_name=group_name
                )

        elif notification_type == 'WALLET_RECHARGE_CONFIRMATION':
            user_id = params.get('user_id')
            recharge_amount = params.get('recharge_amount', 0)
            wallet_balance = params.get('wallet_balance', 0)

            if user_id:
                user = User.objects.get(id=user_id)
                if user and user.mobile_number:
                    mobile_number = user.mobile_number
                    template_code = "WALLET_RECHARGE_CONFIRMATION"
                    # variables_values = f"User|{recharge_amount}|{wallet_balance}"
                    variables_values = f"{user.name}|{recharge_amount}|{wallet_balance}"

                    print("wallet recharge variables_values", variables_values)
                    send_template_sms(mobile_number, template_code, variables_values)
                    generate_user_notification(
                        notification_type='WALLET_RECHARGE_CONFIRMATION',
                        user=user,
                        variables_values=variables_values,
                        booking_id=None,
                        group_name=group_name
                    )

        elif notification_type == 'WALLET_DEDUCTION_CONFIRMATION':
            user_id = params.get('user_id')
            deduct_amount = params.get('deduct_amount', 0)
            wallet_balance = params.get('wallet_balance', 0)
            booking_id = params.get('booking_id')

            if user_id:
                user = User.objects.get(id=user_id)
                if user and user.mobile_number:
                    mobile_number = user.mobile_number
                    template_code = "WALLET_DEDUCTION_CONFIRMATION"
                    # variables_values = f"User|{deduct_amount}|{wallet_balance}"
                    variables_values = f"{user.name}|{deduct_amount}|{wallet_balance}"

                    print("wallet deduction variables_values", variables_values)
                    send_template_sms(mobile_number, template_code, variables_values)
                    group_name = None
                    if booking_id:
                        booking = get_booking(booking_id)
                        if booking:
                            group_name = "CORPORATE-GRP" if booking.company_id else "B2C-GRP"
                    
                    generate_user_notification(
                        notification_type='WALLET_DEDUCTION_CONFIRMATION',
                        user=user,
                        variables_values=variables_values,
                        booking_id=booking_id,
                        group_name=group_name
                    )

        elif notification_type == 'HOTEL_BOOKING_CONFIRMATION':
            booking_id = params.get('booking_id')

            booking = get_booking(booking_id)
            if booking and booking.user.mobile_number:
                mobile_number = booking.user.mobile_number
                template_code = "HOTEL_BOOKING_CONFIRMATION"

                property_name = ""
                if booking.hotel_booking and booking.hotel_booking.confirmed_property:
                    property_name = booking.hotel_booking.confirmed_property.name

                # variables_values = f"User|{property_name}|{booking.reference_code}"
                variables_values = f"{booking.user.name}|{property_name}|{booking.reference_code}"

                print("booking confirmation variables_values", variables_values)
                send_template_sms(mobile_number, template_code, variables_values)
                # generate_user_notification(
                #     notification_type='HOTEL_BOOKING_CONFIRMATION',
                #     user = booking.user,
                #     variables_values=variables_values,
                #     booking_id=booking.id
                # )

        elif notification_type == 'PAYMENT_FAILED_INFO':
            booking_id = params.get('booking_id', None)
            user_id = params.get('user_id', None)
            failed_amount = params.get('failed_amount', 0)
            payment_purpose = params.get('payment_purpose', 'Hotel Booking')  # Default to Hotel Booking if not specified
            
            mobile_number = None
            
            # Handle booking-related payment failures
            if booking_id:
                booking = get_booking(booking_id)
                if booking and booking.user.mobile_number:
                    mobile_number = booking.user.mobile_number
            
            # Handle wallet-related payment failures
            elif user_id:
                try:
                    user = User.objects.get(id=user_id)
                    if user and user.mobile_number:
                        mobile_number = user.mobile_number
                except User.DoesNotExist:
                    print(f"User with ID {user_id} not found")
                    return
            
            # Send SMS if we have a valid mobile number
            if mobile_number:
                template_code = "PAYMENT_FAILED_INFO"
                user_name = booking.user.name if booking else user.name  # Get the actual user name
                variables_values = f"{user_name}|{failed_amount}|{payment_purpose}"
                # variables_values = f"User|{failed_amount}|{payment_purpose}"
                
                print("payment failed variables_values", variables_values)
                send_template_sms(mobile_number, template_code, variables_values)
                group_name = "CORPORATE-GRP" if booking.company_id else "B2C-GRP"
                generate_user_notification(
                    notification_type='PAYMENT_FAILED_INFO',
                    user=booking.user,
                    variables_values=variables_values,
                    booking_id=booking.id,
                    group_name=group_name  # Pass the group_name here
                )

        elif notification_type == 'PAYMENT_PROCEED_INFO':
            booking_id = params.get('booking_id', None)
            user_id = params.get('user_id', None)
            amount = params.get('amount', 0)
            payment_purpose = params.get('payment_purpose', 'Hotel Booking')
            transaction_id = params.get('transaction_id', '')
            
            mobile_number = None
            
            if booking_id:
                booking = get_booking(booking_id)
                if booking and booking.user.mobile_number:
                    mobile_number = booking.user.mobile_number
            
            elif user_id:
                try:
                    user = User.objects.get(id=user_id)
                    if user and user.mobile_number:
                        mobile_number = user.mobile_number
                        transaction_id = booking.reference_code
                except User.DoesNotExist:
                    print(f"User with ID {user_id} not found")
                    return
            
            if mobile_number:
                template_code = "PAYMENT_PROCEED_INFO"
                # variables_values = f"User|{amount}|{payment_purpose}|{transaction_id}"
                user_name = booking.user.name if booking else user.name  # Get the actual user name
                variables_values = f"{user_name}|{amount}|{payment_purpose}|{transaction_id}"
                
                print("payment processed variables_values", variables_values)
                send_template_sms(mobile_number, template_code, variables_values)
                group_name = "CORPORATE-GRP" if booking.company_id else "B2C-GRP"
                generate_user_notification(
                    notification_type='PAYMENT_PROCEED_INFO',
                    user=booking.user,
                    variables_values=variables_values,
                    booking_id=booking.id,
                    group_name=group_name
                )

        elif notification_type == 'PAY_AT_HOTEL_BOOKING_CONFIRMATION':
            booking_id = params.get('booking_id')

            booking = get_booking(booking_id)
            if booking and booking.user.mobile_number:
                mobile_number = booking.user.mobile_number
                template_code = "PAY_AT_HOTEL_BOOKING_CONFIRMATION"

                property_name = ""
                if booking.hotel_booking and booking.hotel_booking.confirmed_property:
                    property_name = booking.hotel_booking.confirmed_property.name

                variables_values = f"{booking.user.name}|{property_name}|{float(booking.final_amount)}"
                group_name = "CORPORATE-GRP" if booking.company_id else "B2C-GRP"
                print("pay at hotel booking confirmation variables_values", variables_values)
                send_template_sms(mobile_number, template_code, variables_values)
                generate_user_notification(
                    notification_type='PAY_AT_HOTEL_BOOKING_CONFIRMATION',
                    user = booking.user,
                    variables_values=variables_values,
                    booking_id=booking.id,
                    group_name=group_name
                )

        elif notification_type == 'ELIGIBILITY_LOSS_WARNING':
            booking_id = params.get('booking_id')

            booking = get_booking(booking_id)
            if booking and booking.user and booking.user.mobile_number:
                user = booking.user
                mobile_number = user.mobile_number
                template_code = "ELIGIBILITY_LOSS_WARNING"

                reason = params.get('reason', 'unpaid hotel charges')
                amount = params.get('amount', 0)

                variables_values = f"{user.name}|{reason}|{float(amount)}"
                group_name = "CORPORATE-GRP" if booking.company_id else "B2C-GRP"
                print("eligibility loss warning variables_values", variables_values)
                send_template_sms(mobile_number, template_code, variables_values)
                generate_user_notification(
                    notification_type='ELIGIBILITY_LOSS_WARNING',
                    user=user,
                    variables_values=variables_values,
                    booking_id=booking.id,
                    group_name=group_name
                )

        elif notification_type == 'PAH_PAYMENT_CONFIRMATION':
            booking_id = params.get('booking_id')
            amount = params.get('amount', 0)

            booking = get_booking(booking_id)
            if booking and booking.user and booking.user.mobile_number:
                user = booking.user
                mobile_number = user.mobile_number
                template_code = "PAH_PAYMENT_CONFIRMATION"

                property_name = ""
                if booking.hotel_booking and booking.hotel_booking.confirmed_property:
                    property_name = booking.hotel_booking.confirmed_property.name

                variables_values = f"{user.name}|{float(amount)}|{property_name}"
                group_name = "CORPORATE-GRP" if booking.company_id else "B2C-GRP"

                print("Pay at hotel payment confirmation variables_values", variables_values)
                send_template_sms(mobile_number, template_code, variables_values)
                generate_user_notification(
                    notification_type='PAH_PAYMENT_CONFIRMATION',
                    user=user,
                    variables_values=variables_values,
                    booking_id=booking.id,
                    group_name=group_name
                )

        elif notification_type == 'ELIGIBILITY_LOSS_NOTIFICATION':
            user_id = params.get('user_id')
            if user_id:
                user = User.objects.get(id=user_id)
                if user and user.mobile_number:
                    mobile_number = user.mobile_number
                template_code = "ELIGIBILITY_LOSS_NOTIFICATION"

                # Custom message details
                variables_values = f"{user.name}|multiple unpaid bookings|support@idbookhotels.com"
                group_name = "CORPORATE-GRP" if user.company_id else "B2C-GRP"
                print("eligibility loss notification variables_values", variables_values)

                # Send the SMS
                send_template_sms(mobile_number, template_code, variables_values)
                generate_user_notification(
                    notification_type='ELIGIBILITY_LOSS_NOTIFICATION',
                    user=user,
                    variables_values=variables_values,
                    group_name=group_name
                )

        elif notification_type == 'PAH_SPECIAL_LIMIT_OVERRIDE':
            user_id = params.get('user_id')
            if user_id:
                user = User.objects.get(id=user_id)
                if user and user.mobile_number:
                    mobile_number = user.mobile_number
                template_code = "PAH_SPECIAL_LIMIT_OVERRIDE"

                user_name = user.name
                limit = params.get('limit')
                valid_till = params.get('valid_till')

                variables_values = f"{user_name}|{limit}|{valid_till}"
                group_name = "CORPORATE-GRP" if user.company_id else "B2C-GRP"

                send_template_sms(mobile_number, template_code, variables_values)
                generate_user_notification(
                    notification_type='PAH_SPECIAL_LIMIT_OVERRIDE',
                    user=user,
                    variables_values=variables_values,
                    group_name=group_name
                )
        # elif notification_type == 'otp':
        #     mobile_number = params.get('mobile_number')
        #     otp = params.get('otp')
        #     otp_for = params.get('otp_for')

        #     template_code = 'VERIFY' if otp_for == 'VERIFY-GUEST' else otp_for

        #     variables_values = f"User|{otp}"

        #     print(f"OTP {otp_for} variables_values", variables_values)
        #     send_template_sms(mobile_number, template_code, variables_values)

    except Exception as e:
        print(f'{notification_type} SMS Task Error: {e}')