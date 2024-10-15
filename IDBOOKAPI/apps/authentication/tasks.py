# task
from IDBOOKAPI.celery import app as celery_idbook
from IDBOOKAPI.email_utils import (send_otp_email, send_signup_link_email)


@celery_idbook.task(bind=True)
def send_email_task(self, otp, to_emails):
    print("Initiated Email OTP Sent Process")
    send_otp_email(otp, to_emails)

@celery_idbook.task(bind=True)
def customer_signup_link_task(self, signup_link, to_emails):
    print("Initiated Customer Signup Link Email")
    send_signup_link_email(signup_link, to_emails)
    
    
