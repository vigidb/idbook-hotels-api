from IDBOOKAPI.celery import app as celery_idbook
from .models import Property
from apps.authentication.models import User
from apps.sms_gateway.mixins.fastwosms_mixins import send_template_sms


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
                    website_link = "IDBOOK Official Site"
                    
                    variables_values = f"{hotelier_name}|{property_name}|{website_link}"
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