# task
from IDBOOKAPI.celery import app as celery_idbook
from IDBOOKAPI.email_utils import send_otp_email


@celery_idbook.task(bind=True)
def send_email_task(self, otp, to_emails):
    print("Initiated Email OTP Sent Process")
    print(otp)
    print(to_emails)
    send_otp_email(otp, to_emails)
    
    
