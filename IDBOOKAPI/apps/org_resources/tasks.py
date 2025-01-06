from django.conf import settings

from IDBOOKAPI.celery import app as celery_idbook
from IDBOOKAPI.email_utils import send_email

from apps.org_resources.utils.db_utils import get_enquiry_details

@celery_idbook.task(bind=True)
def send_enquiry_email_task(self, enquiry_id):
    print("Enquiry Id", enquiry_id)
    try:
        enquiry_obj = get_enquiry_details(enquiry_id)
        if enquiry_obj:
            name = enquiry_obj.name
            phone_no = enquiry_obj.phone_no
            email = enquiry_obj.email
            enquiry_message = enquiry_obj.enquiry_msg
            message = f" Name: {name}, Email: {email}, Phone No: {phone_no} \n \
Message: {enquiry_message}"
            from_email = settings.EMAIL_HOST_USER
            subject = "Enquiry"
            to_emails = [from_email, 'sonu@idbookhotels.com']
            send_email(subject, message, to_emails, from_email)
        else:
            print("Missing enquiry id", enquiry_id)
    except Exception as e:
        print(e)
        print(traceback.format_exc())

