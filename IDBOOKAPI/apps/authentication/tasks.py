# task
from IDBOOKAPI.celery import app as celery_idbook
from IDBOOKAPI.email_utils import (
    send_otp_email, send_signup_link_email, send_welcome_email)
from django.template.loader import get_template


@celery_idbook.task(bind=True)
def send_email_task(self, otp, to_emails):
    print("Initiated Email OTP Sent Process")
    email_template = get_template('email_template/otp-verification.html')
    print(email_template)
    context = {'otp': otp}
    html_content = email_template.render(context)
    send_otp_email(otp, to_emails, template=html_content)

@celery_idbook.task(bind=True)
def customer_signup_link_task(self, signup_link, to_emails):
    print("Initiated Customer Signup Link Email")
    send_signup_link_email(signup_link, to_emails)


@celery_idbook.task(bind=True)
def send_signup_email_task(self, name, to_emails):
    print("Initiated Welcome Email")
    email_template = get_template('email_template/signup.html')
    context = {'name': name}
    html_content = email_template.render(context)
    send_welcome_email(html_content, to_emails)
    
