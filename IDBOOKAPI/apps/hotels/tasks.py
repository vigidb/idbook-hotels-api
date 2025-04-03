from IDBOOKAPI.celery import app as celery_idbook
from .models import Property
from apps.authentication.models import User
from apps.sms_gateway.mixins.fastwosms_mixins import send_template_sms
from django.template.loader import get_template
from django.conf import settings
from IDBOOKAPI.email_utils import send_booking_email
from IDBOOKAPI.utils import shorten_url


@celery_idbook.task(bind=True)
def send_hotel_sms_task(self, notification_type='', params=None):

    if params is None:
        params = {}
    print(f"Inside {notification_type} SMS task")
    try:
        if notification_type == 'HOTEL_PROPERTY_ACTIVATION':
            property_id = params.get('property_id')
            if not property_id:
                print("No property_id provided in params")
                return

            try:
                property = Property.objects.get(id=property_id)
                
                if property and property.phone_no:
                    mobile_number = property.phone_no
                    print("mobile_number", mobile_number)
                    template_code = "HOTEL_PROPERTY_ACTIVATION"
                    
                    hotelier_name = "Hotelier"
                    
                    property_name = property.name
                    # website_link = "IDBOOK Official Site"
                    website_link = f"{settings.FRONTEND_URL}/login"
                    short_login_link = shorten_url(website_link)
                    
                    variables_values = f"{hotelier_name}|{property_name}|{short_login_link}"
                    print("variables_values", variables_values)
                    
                    response = send_template_sms(mobile_number, template_code, variables_values)
                    print(f"SMS sent for property activation. Response: {response}")
                    return response
                else:
                    print(f"Property not found or no phone number available for property_id: {property_id}")
            except Property.DoesNotExist:
                print(f"Property with id {property_id} not found")
                
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
                    login_link = f"{settings.FRONTEND_URL}/login"
                    short_login_link = shorten_url(login_link)
                    
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
