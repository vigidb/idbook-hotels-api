from IDBOOKAPI.celery import app as celery_idbook
from IDBOOKAPI.email_utils import send_booking_email
from apps.booking.utils.db_utils import get_booking
from apps.booking.utils.booking_utils import generate_html_for_mail

from django.template.loader import get_template
from django.conf import settings


@celery_idbook.task(bind=True)
def send_booking_email_task(self, booking_id):
    print("Initiated Booking Email Process")
    print(booking_id)
    booking = get_booking(booking_id)
    if booking:
        email_template = get_template('email_template/booking-search.html')
        context = generate_html_for_mail(booking)
        html_content = email_template.render(context)
        # corporates@idbookhotels.com
        send_email = settings.CORPORATE_EMAIL
        print(send_email)
        send_booking_email(booking, [send_email, 'sonu@idbookhotels.com'], html_content)
    
    #send_otp_email(otp, to_emails)
