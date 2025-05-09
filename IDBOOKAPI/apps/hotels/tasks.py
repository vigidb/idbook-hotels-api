from IDBOOKAPI.celery import app as celery_idbook
from .models import Property, MonthlyPayAtHotelEligibility
from apps.authentication.models import User
from apps.sms_gateway.mixins.fastwosms_mixins import send_template_sms
from django.template.loader import get_template
from django.conf import settings
from IDBOOKAPI.email_utils import send_booking_email
from IDBOOKAPI.utils import shorten_url
from apps.booking.models import Booking, Review
from .utils.db_utils import get_user_booking_data
from apps.org_resources.utils.notification_utils import create_hotelier_notification

@celery_idbook.task(bind=True)
def send_hotel_sms_task(self, notification_type='', params=None):
    if params is None:
        params = {}
    
    print(f"Inside {notification_type} SMS task")

    try:
        def get_property_from_id(property_id):
            return Property.objects.filter(id=property_id).first()

        def get_booking_property(booking_id):
            booking = Booking.objects.filter(id=booking_id).first()
            return booking, booking.hotel_booking.confirmed_property if booking and booking.hotel_booking else None

        def send_sms(mobile, template, variables):
            print("variables_values", variables)
            response = send_template_sms(mobile, template, variables)
            print(f"SMS sent with template '{template}'. Response: {response}")
            return response

        def shorten_link(url):
            print("website_link", url)
            return shorten_url(url)

        # Template logic
        if notification_type == 'HOTEL_PROPERTY_ACTIVATION':
            property = get_property_from_id(params.get('property_id'))
            if property and property.phone_no:
                website_link = f"https://www.idbookhotels.com/hotelier/login?utm_source=sms&utm_medium=notification&utm_campaign=property_activation&ref={property.slug}"
                short_link = shorten_link(website_link)
                variables_values = f"Hotelier|{property.name}|{short_link}"
                send_sms(
                    property.phone_no,
                    "HOTEL_PROPERTY_ACTIVATION",
                    variables_values
                )
                create_hotelier_notification(property, notification_type, variables_values)

        elif notification_type == 'HOTEL_PROPERTY_DEACTIVATION':
            property = get_property_from_id(params.get('property_id'))
            if property and property.phone_no:
                variables_values = f"Hotelier|{property.name}|Invalid/incomplete listing"
                send_sms(
                    property.phone_no,
                    "HOTEL_PROPERTY_DEACTIVATION",
                    variables_values
                )
                create_hotelier_notification(property, notification_type, variables_values)

        elif notification_type == 'HOTELIER_BOOKING_NOTIFICATION':
            booking, property = get_booking_property(params.get('booking_id'))
            if property and property.phone_no:
                variables_values = f"Hotelier|{property.name}|{booking.hotel_booking.confirmed_checkin_time}"
                send_sms(
                    property.phone_no,
                    "HOTELIER_BOOKING_NOTIFICATION",
                    variables_values
                )
                create_hotelier_notification(property, notification_type, variables_values)

        elif notification_type == 'HOTELER_BOOKING_CANCEL_NOTIFICATION':
            booking, property = get_booking_property(params.get('booking_id'))
            if property and property.phone_no:
                variables_values = f"Hotelier|{property.name}|{booking.reference_code}"
                send_sms(
                    property.phone_no,
                    "HOTELER_BOOKING_CANCEL_NOTIFICATION",
                    variables_values
                )
                create_hotelier_notification(property, notification_type, variables_values)

        elif notification_type == 'HOTELER_PAYMENT_NOTIFICATION':
            booking, property = get_booking_property(params.get('booking_id'))
            if property and property.phone_no:
                final_amount = float(booking.final_amount or 0)
                code = booking.confirmation_code or booking.reference_code
                variables_values = f"Hotelier|{final_amount}|{code}"
                send_sms(
                    property.phone_no,
                    "HOTELER_PAYMENT_NOTIFICATION",
                    variables_values
                )
                create_hotelier_notification(property, notification_type, variables_values)

        elif notification_type == 'HOTELIER_PROPERTY_REVIEW_NOTIFICATION':
            review = Review.objects.select_related('property').filter(id=params.get('review_id')).first()
            if review and review.property and review.property.phone_no:
                variables_values = f"Hotelier|{review.property.name}|{float(review.overall_rating)}"
                send_sms(
                    review.property.phone_no,
                    "HOTELIER_PROPERTY_REVIEW_NOTIFICATION",
                    variables_values
                )
                create_hotelier_notification(review.property, notification_type, variables_values)

        elif notification_type == 'HOTEL_PROPERTY_SUBMISSION':
            property = get_property_from_id(params.get('property_id'))
            if property and property.phone_no:
                variables_values = f"Hotelier|{property.name}"
                send_sms(
                    property.phone_no,
                    "HOTEL_PROPERTY_SUBMISSION",
                    variables_values
                )
                create_hotelier_notification(property, notification_type, variables_values)

    except Exception as e:
        print(f'{notification_type} SMS Task Error: {e}')

    return None

@celery_idbook.task(bind=True)
def send_hotel_email_task(self, notification_type='', params=None):
    """
    Background task to send email notifications to hotels
    """
    if params is None:
        params = {}
    print(f"Inside {notification_type} Email task")
    
    try:
        if notification_type == 'HOTEL_PROPERTY_ACTIVATION':
            property_id = params.get('property_id')
            if not property_id:
                print("No property_id provided in params")
                return

            try:
                property = Property.objects.get(id=property_id)
                
                if property and property.email:
                    recipient_email = property.email
                    print("recipient_email", recipient_email)
                    
                    # user = None
                    # if property.managed_by_id:
                    #     try:
                    #         user = User.objects.get(id=property.managed_by_id)
                    #     except User.DoesNotExist:
                    #         pass
                    
                    # hotelier_name = user.name if user else "Hotelier"
                    hotelier_name = "Hotelier"
                    property_name = property.name
                    # login_link = f"{settings.FRONTEND_URL}/login"
                    login_link = f"https://www.idbookhotels.com/hotelier/login?utm_source=email&utm_medium=notification&utm_campaign=property_activation&ref={property.slug}"
                    print("login_link", login_link)
                    short_login_link = shorten_url(login_link)
                    print("short_login_link", short_login_link)
                    context = {
                        'hotelier_name': hotelier_name,
                        'property_name': property_name,
                        'login_link': short_login_link
                    }
                    
                    email_template = get_template('email_template/hotelier-active-property.html')
                    html_content = email_template.render(context)

                    subject = f"Your property {property_name} is now ACTIVE on Idbook"
                    send_booking_email(subject, property, [recipient_email], html_content)
                    
                    print(f"Email sent for property activation to {recipient_email}")
                    return True
                else:
                    print(f"Property not found or no email available for property_id: {property_id}")
            except Property.DoesNotExist:
                print(f"Property with id {property_id} not found")
                
    except Exception as e:
        print(f'{notification_type} Email Task Error: {e}')
        return None


@celery_idbook.task(bind=True)
def update_monthly_pay_at_hotel_eligibility_task(self, user_id, booking_date):
    """
    Update monthly pay at hotel eligibility based on confirmed bookings count
    """
    print("Inside update monthly pay at hotel eligibility task")
    try:
        data = get_user_booking_data(user_id, booking_date)

        existing_eligibility = MonthlyPayAtHotelEligibility.objects.filter(
            user_id=user_id,
            month=data['month_name']
        ).first()

        if existing_eligibility and existing_eligibility.updated_by == "Admin":

            remaining_limit = existing_eligibility.eligible_limit - data['spent_amount']
            
            monthly_eligibility, created = MonthlyPayAtHotelEligibility.objects.update_or_create(
                user_id=user_id,
                month=data['month_name'],
                defaults={
                    'total_booking_count': data['booking_count'],
                    'total_cancel_count': data['total_cancel_count'],
                    'spent_amount': data['spent_amount'],
                    'is_eligible': existing_eligibility.is_eligible and remaining_limit > 0,
                    'eligible_limit': existing_eligibility.eligible_limit,
                    'cancel_limit': existing_eligibility.cancel_limit,
                    'is_blacklisted': existing_eligibility.is_blacklisted,
                    'updated_by': existing_eligibility.updated_by
                }
            )
            
            data['remaining_limit'] = remaining_limit
            data['eligible_limit'] = existing_eligibility.eligible_limit
            data['is_eligible'] = existing_eligibility.is_eligible and remaining_limit > 0
            data['is_blacklisted'] = existing_eligibility.is_blacklisted
            
        else:
            monthly_eligibility, created = MonthlyPayAtHotelEligibility.objects.update_or_create(
                user_id=user_id,
                month=data['month_name'],
                defaults={
                    'total_booking_count': data['booking_count'],
                    'eligible_limit': data['eligible_limit'],
                    'is_eligible': data['is_eligible'],
                    'total_cancel_count': data['total_cancel_count'],
                    'cancel_limit': data['cancel_limit'],
                    'is_blacklisted': data['is_blacklisted'],
                    'spent_amount': data['spent_amount'],
                    'updated_by': "Automatic"
                }
            )

        print(f"Updated monthly pay at hotel eligibility for user {user_id}, month: {data['month_name']}")
        print(
            f"Booking count: {data['booking_count']}, Eligible limit: {data['eligible_limit']}, "
            f"Spent amount: {data['spent_amount']}, Remaining limit: {data['remaining_limit']}, "
            f"Cancel count: {data['total_cancel_count']}, Cancel limit: {data['cancel_limit']}, "
            f"Is eligible: {data['is_eligible']}, Is blacklisted: {data['is_blacklisted']}"
        )

        return {
            'user_id': user_id,
            'month': data['month_name'],
            'booking_count': data['booking_count'],
            'eligible_limit': float(data['eligible_limit']),
            'spent_amount': float(data['spent_amount']),
            'remaining_limit': float(data['remaining_limit']),
            'is_eligible': data['is_eligible'],
            'is_blacklisted': data['is_blacklisted'],
            'updated_by': monthly_eligibility.updated_by
        }

    except Exception as e:
        print('Update Monthly Pay At Hotel Eligibility Task Error:', e)
        print(traceback.format_exc())
        return {
            'status': 'error',
            'message': str(e)
        }
