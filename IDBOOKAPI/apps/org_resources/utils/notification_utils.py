from IDBOOKAPI.utils import shorten_url
from apps.org_resources.models import MessageTemplate
from apps.org_managements.utils import get_active_business
from apps.org_resources.db_utils import create_notification
from apps.authentication.models import User
import re

def booking_comfirmed_notification_template(booking_id, booking_type, confirmation_code, notification_dict):
    try:
        # Notification
        title = "{booking_type} Booking Confirmed".format(booking_type=booking_type)
        description = "We are pleased to confirm your {booking_type} booking. \
The confirmation code is: {confirmation_code}".format(booking_type=booking_type,
                                              confirmation_code=confirmation_code)
        redirect_url = "/bookings/{booking_id}".format(booking_id=booking_id)
     
        
        notification_dict['title'] = title
        notification_dict['description'] = description
        notification_dict['redirect_url'] = redirect_url
        
    except Exception as e:
        print('Notification Error', e)

    return notification_dict

def booking_cancelled_notification_template(booking_id, booking_type, cancellation_code, notification_dict):
    try:
        # Notification
        title = "{booking_type} Booking Cancelled".format(booking_type=booking_type)
        description = " We regret to inform you that your {booking_type} booking has been successfully cancelled.\
The cancellation code is: {cancellation_code}".format(booking_type=booking_type,
                                                      cancellation_code=cancellation_code)
        redirect_url = "/bookings/{booking_id}".format(booking_id=booking_id)
     
        
        notification_dict['title'] = title
        notification_dict['description'] = description
        notification_dict['redirect_url'] = redirect_url
        
    except Exception as e:
        print('Notification Error', e)

    return notification_dict

def booking_completed_notification_template(booking_id, booking_type, notification_dict):
    try:
        # Notification
        title = "Hotel Stay Completed"
        description = "Thank you for choosing Idbook! Your Hotel stay has been completed. We hope you enjoyed your stay and would appreciate your feedback."
        redirect_url = "https://www.ambitionbox.com/overview/idbook-hotels-overview"
        redirect_url = shorten_url(redirect_url)
        
        notification_dict['title'] = title
        notification_dict['description'] = description
        notification_dict['redirect_url'] = redirect_url
        
    except Exception as e:
        print('Notification Error', e)
    return notification_dict

def wallet_minbalance_notification_template(wallet_balance, notification_dict):
    try:

        wallet_balance = float(wallet_balance)
        
        title = "Low Wallet Balance Notification"
        description = " A gentle reminder that your Idbook wallet balance \
is LOW ({wallet_balance} INR)".format(wallet_balance=wallet_balance)
        
        notification_dict['title'] = title
        notification_dict['description'] = description
        
    except Exception as e:
        print('Notification Wallet Balance Template Error', e)

    return notification_dict

def wallet_booking_balance_notification_template(booking, wallet_balance, notification_dict):
    try:
        booking_type = booking.booking_type
        wallet_balance = float(wallet_balance)
        booking_amount = float(booking.final_amount)
        
        # balance_amount = booking_amount - booking.total_payment_made
        title = "Low Wallet Balance Notification"
        description = " A gentle reminder that your Idbook wallet balance \
is LOW ({wallet_balance} INR) for the {booking_type} booking. \
Your total booking amount is {booking_amount}. \
Please recharge your wallet to confirm booking".format(
    wallet_balance=wallet_balance, booking_type=booking_type, booking_amount=booking_amount)
        redirect_url = "/bookings/{booking_id}".format(booking_id=booking.id)
        
        notification_dict['title'] = title
        notification_dict['description'] = description
        notification_dict['redirect_url'] = redirect_url
        
    except Exception as e:
        print('Notification Wallet Balance Template Error', e)

    return notification_dict

def generate_user_notification(notification_type, booking=None, user=None, variables_values="", booking_id=None, group_name=None):
    try:
        # Get template message from DB
        template_code = notification_type
        template = MessageTemplate.objects.get(template_code=template_code)
        raw_message = template.template_message
        
        raw_message = re.sub(r"\{#var#\}", "{}", raw_message)
        split_values = variables_values.split('|')
        description = raw_message.format(*split_values)

        # Notification title mapping
        titles = {
            'HOTEL_BOOKING_CONFIRMATION': 'Hotel Booking Confirmed',
            'HOTEL_BOOKING_CANCEL': 'Hotel Booking Cancelled',
            'HOTEL_PAYMENT_REFUND': 'Booking Payment Refunded',
            'WALLET_RECHARGE_CONFIRMATION': 'Wallet Recharge Success',
            'WALLET_DEDUCTION_CONFIRMATION': 'Wallet Deduction Info',
            'PAYMENT_FAILED_INFO': 'Payment Failed',
            'PAYMENT_PROCEED_INFO': 'Payment Successful',
            'PAY_AT_HOTEL_BOOKING_CONFIRMATION': 'Pay at Hotel Booking Confirmed',
            'ELIGIBILITY_LOSS_WARNING': 'Pay at Hotel Eligibility Loss Warning',
            'PAH_PAYMENT_CONFIRMATION': 'Pay at Hotel Payment Confirmation',
            'ELIGIBILITY_LOSS_NOTIFICATION': 'Pay at Hotel Eligibility Loss Notification',
            'PAH_SPECIAL_LIMIT_OVERRIDE': 'Pay at Hotel Special Limit'
        }
        title = titles.get(notification_type, "Notification")

        # Determine user and redirect_url
        user = booking.user if booking else user
        # If group_name is not provided, determine it from booking
        if group_name is None:
            group_name = "CORPORATE-GRP" if booking and getattr(booking, "company_id", None) else "B2C-GRP"
            
        send_by = get_active_business().user
        notif_type = notification_type  # backup original type

        if notif_type in ['WALLET_RECHARGE_CONFIRMATION', 'ELIGIBILITY_LOSS_WARNING', 'ELIGIBILITY_LOSS_NOTIFICATION', 'PAH_SPECIAL_LIMIT_OVERRIDE']:
            notification_type = 'GENERAL'
        else:
            notification_type = 'BOOKING'
        if notif_type in ["WALLET_RECHARGE_CONFIRMATION", "WALLET_DEDUCTION_CONFIRMATION", "ELIGIBILITY_LOSS_WARNING", "ELIGIBILITY_LOSS_NOTIFICATION", 
            "PAH_SPECIAL_LIMIT_OVERRIDE"]:
            redirect_url = ""
        else:
            redirect_url = f"/bookings/{booking_id}"

        # Create dictionary
        notification_dict = {
            'user': user,
            'send_by': send_by,
            'notification_type': notification_type,
            'title': title,
            'description': description,
            'redirect_url': redirect_url,
            'image_link': '',
            'group_name': group_name
        }
        print("creating_notification", notification_dict)
        create_notification(notification_dict)
    except Exception as e:
        print("Notification Error", e)

def create_hotelier_notification(property, notification_type, variables_values):
    # Create notification for hotelier
    try:
        # Map notification types to titles
        titles = {
            'HOTEL_PROPERTY_ACTIVATION': 'Property Activated',
            'HOTEL_PROPERTY_DEACTIVATION': 'Property Deactivated',
            'HOTELIER_BOOKING_NOTIFICATION': 'New Booking Received',
            'HOTELER_BOOKING_CANCEL_NOTIFICATION': 'Booking Cancelled',
            'HOTELER_PAYMENT_NOTIFICATION': 'Payment Received',
            'HOTELIER_PROPERTY_REVIEW_NOTIFICATION': 'New Review Received',
            'HOTEL_PROPERTY_SUBMISSION': 'Property Submission Received',
            'HOTELIER_PAH_FEATURE': 'Property Pay at Hotel Facility Added',
            'HOTELIER_PAH_BOOKING_ALERT': 'New Pay at Hotel Booking Received'
        }
        
        # Determine appropriate notification_type (GENERAL or BOOKING)
        app_notification_type = 'BOOKING' if notification_type in [
            'HOTELIER_BOOKING_NOTIFICATION',
            'HOTELER_BOOKING_CANCEL_NOTIFICATION',
            'HOTELER_PAYMENT_NOTIFICATION',
            'HOTELIER_PAH_BOOKING_ALERT'
        ] else 'GENERAL'
        
        # Get template message from DB
        template_code = notification_type
        template = MessageTemplate.objects.get(template_code=template_code)
        raw_message = template.template_message
        
        raw_message = re.sub(r"\{#var#\}", "{}", raw_message)
        split_values = variables_values.split('|')
        description = raw_message.format(*split_values)
        
        title = titles.get(notification_type, "Notification")
        
        # Get the user associated with property using managed_by_id
        user = User.objects.filter(id=property.managed_by_id).first()
        if not user:
            return
        
        send_by = get_active_business().user
        
        # Create notification dictionary
        notification_dict = {
            'user': user,
            'send_by': send_by,
            'notification_type': app_notification_type,
            'title': title,
            'description': description,
            'redirect_url': '',
            'image_link': '',
            'group_name': 'HOTELIER-GRP'
        }
        
        print("creating_hotelier_notification", notification_dict)
        create_notification(notification_dict)
    except Exception as e:
        print("Hotelier Notification Error", e)

def admin_create_notification(user, notification_type, variables_values):
    try:
        titles = {
            'ADMIN_PAH_HIGH_VALUE_ALERT': 'High-Value Pay at Hotel Booking Alert',
            'ADMIN_PAH_PAYMENT_DISPUTE_ALERT': 'Payment Dispute Alert'
        }
        app_notification_type = 'BOOKING' if notification_type in [
            'ADMIN_PAH_HIGH_VALUE_ALERT', 'ADMIN_PAH_PAYMENT_DISPUTE_ALERT'
        ] else 'GENERAL'

        template = MessageTemplate.objects.get(template_code=notification_type)
        raw_message = template.template_message
        raw_message = re.sub(r"\{#var#\}", "{}", raw_message)
        split_values = variables_values.split('|')
        description = raw_message.format(*split_values)

        title = titles.get(notification_type, "Admin Notification")

        send_by = get_active_business().user

        notification_dict = {
            'user': user,
            'send_by': send_by,
            'notification_type': app_notification_type,
            'title': title,
            'description': description,
            'redirect_url': '',
            'image_link': '',
            'group_name': 'BUSINESS-GRP'
        }

        print("creating_admin_notification", notification_dict)
        create_notification(notification_dict)
    except Exception as e:
        print("Admin Notification Error", e)
