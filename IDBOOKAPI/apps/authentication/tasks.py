# task
from IDBOOKAPI.celery import app as celery_idbook
from IDBOOKAPI.email_utils import (
    send_otp_email, send_signup_link_email, send_welcome_email)
from django.template.loader import get_template
from apps.sms_gateway.mixins.fastwosms_mixins import Fast2SmsMixin
from apps.log_management.models import SmsOtpLog, SmsNotificationLog
from IDBOOKAPI.basic_resources import SMS_TYPES_CHOICES

@celery_idbook.task(bind=True)
def send_email_task(self, otp, to_emails):
    print("Initiated Email OTP Sent Process")
    email_template = get_template('email_template/otp-verification.html')
    print(email_template)
    context = {'otp': otp}
    html_content = email_template.render(context)
    send_otp_email(otp, to_emails, template=html_content)

@celery_idbook.task(bind=True)
def send_mobile_otp_task(self, otp, mobile_number, otp_for=''):
    try:
        print("otp::", otp, "mobile_number::", mobile_number)
        template_code = 'VERIFY' if otp_for == 'VERIFY-GUEST' else otp_for
        obj = Fast2SmsMixin()
        response = obj.post_dlt_otpsms(mobile_number, otp, template_code)
        if response.status_code != 200:
            SmsOtpLog.objects.create(mobile_number=mobile_number, response=response.json())
            SmsNotificationLog.objects.create(
                mobile_number=mobile_number, 
                sms_for=template_code if template_code in dict(SMS_TYPES_CHOICES) else 'other',
                response=response.json()
            )
    except Exception as e:
        print(e)


@celery_idbook.task(bind=True)
def customer_signup_link_task(self, signup_link, name, to_emails):
    print("Initiated Customer Signup Link Email")
    email_template = get_template('email_template/signup-link.html')
    context = {'name': name, 'sign_up_link': signup_link}
    html_content = email_template.render(context)
    send_signup_link_email(signup_link, to_emails, html_content)


# @celery_idbook.task(bind=True)
# def send_signup_email_task(self, name, to_emails):
#     print("Initiated Welcome Email")
#     email_template = get_template('email_template/signup.html')
#     context = {'name': name}
#     html_content = email_template.render(context)
#     send_welcome_email(html_content, to_emails)

@celery_idbook.task(bind=True)
def send_signup_email_task(self, name, to_emails, group_name):
    print("Initiated Welcome Email")

    # Decide template and subject based on group
    if group_name == "B2C-GRP":
        email_template = get_template('signup_welcome_templates/customer-welcome.html')
        subject = "Welcome to Idbook Hotels - Your Travel Journey Begins"
    elif group_name == "HOTELIER-GRP":
        email_template = get_template('signup_welcome_templates/hotelier-welcome.html')
        subject = "Welcome to Idbook Hotels Family - Hotelier Partner"
    else:
        email_template = get_template('email_template/signup.html')
        subject = "Welcome to Idbook Hotels!"

    context = {'name': name}
    html_content = email_template.render(context)
    send_welcome_email(subject, html_content, to_emails)