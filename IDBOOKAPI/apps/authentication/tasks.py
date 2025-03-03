# task
from IDBOOKAPI.celery import app as celery_idbook
from IDBOOKAPI.email_utils import (
    send_otp_email, send_signup_link_email, send_welcome_email)
from django.template.loader import get_template
from apps.sms_gateway.mixins.fastwosms_mixins import Fast2SmsMixin
from apps.log_management.models import SmsOtpLog


@celery_idbook.task(bind=True)
def send_email_task(self, otp, to_emails):
    print("Initiated Email OTP Sent Process")
    email_template = get_template('email_template/otp-verification.html')
    print(email_template)
    context = {'otp': otp}
    html_content = email_template.render(context)
    send_otp_email(otp, to_emails, template=html_content)

@celery_idbook.task(bind=True)
def send_mobile_otp_task(self, otp, mobile_number):
    try:
        print("otp::", otp, "mobile_number::", mobile_number)
        obj = Fast2SmsMixin()
        response = obj.post_dlt_otpsms(mobile_number, otp)
        SmsOtpLog.objects.create(mobile_number=mobile_number, response=response.json())
    except Exception as e:
        print(e)
    

@celery_idbook.task(bind=True)
def customer_signup_link_task(self, signup_link, name, to_emails):
    print("Initiated Customer Signup Link Email")
    email_template = get_template('email_template/signup-link.html')
    context = {'name': name, 'sign_up_link': signup_link}
    html_content = email_template.render(context)
    send_signup_link_email(signup_link, to_emails, html_content)


@celery_idbook.task(bind=True)
def send_signup_email_task(self, name, to_emails):
    print("Initiated Welcome Email")
    email_template = get_template('email_template/signup.html')
    context = {'name': name}
    html_content = email_template.render(context)
    send_welcome_email(html_content, to_emails)
    
