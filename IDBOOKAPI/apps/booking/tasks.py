from IDBOOKAPI.celery import app as celery_idbook
from IDBOOKAPI.email_utils import send_otp_email


@celery_idbook.task(bind=True)
def send_booking_email_task(self, booking_id):
    print("Initiated Email OTP Sent Process")
    print(booking_id)
    #send_otp_email(otp, to_emails)
