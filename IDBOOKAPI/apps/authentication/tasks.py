# task
from IDBOOKAPI.celery import app as celery_idbook
from IDBOOKAPI.email_utils import (
    send_otp_email,
    send_signup_link_email,
    send_welcome_email,
)
from django.template.loader import get_template
from apps.sms_gateway.mixins.fastwosms_mixins import Fast2SmsMixin
from apps.log_management.models import SmsOtpLog, SmsNotificationLog
from IDBOOKAPI.basic_resources import SMS_TYPES_CHOICES


@celery_idbook.task(bind=True)
def send_email_task(self, otp, to_emails, otp_for="OTHER", group_name=None):
    try:
        print(f"Initiated Email OTP Sent Process - OTP: {otp}, Email: {to_emails}, OTP_FOR: {otp_for}, Group: {group_name}")
        email_template = get_template("email_template/otp-verification.html")
        
        # Normalize otp_for to handle both underscore and hyphen variants
        normalized_otp_for = otp_for.replace("-", "_") if otp_for else "OTHER"
        
        # Personalize subject and content based on otp_for and group_name
        # Base subjects and messages
        base_otp_subjects = {
            "SIGNUP": "Welcome to Idbook Hotels - Verify Your Email",
            "LOGIN": "Idbook Hotels - Your Login Verification Code",
            "PASSWORD_RESET": "Idbook Hotels - Password Reset Verification Code",
            "PASSWORD-RESET": "Idbook Hotels - Password Reset Verification Code",
            "VERIFY": "Idbook Hotels - Email Verification Code",
            "VERIFY-GUEST": "Idbook Hotels - Guest Booking Verification Code",
            "VERIFY_GUEST": "Idbook Hotels - Guest Booking Verification Code",
            "OTHER": "Idbook Hotels - Verification Code",
        }
        
        base_otp_messages = {
            "SIGNUP": "Thank you for signing up with Idbook Hotels! Use the verification code below to complete your registration and start your travel journey with us.",
            "LOGIN": "You've requested to log in to your Idbook Hotels account. Use the verification code below to securely access your account.",
            "PASSWORD_RESET": "You've requested to reset your password for your Idbook Hotels account. Use the verification code below to proceed with password reset.",
            "PASSWORD-RESET": "You've requested to reset your password for your Idbook Hotels account. Use the verification code below to proceed with password reset.",
            "VERIFY": "Please verify your email address with Idbook Hotels. Use the verification code below to complete the verification process.",
            "VERIFY-GUEST": "Please verify your email for your guest booking with Idbook Hotels. Use the verification code below to complete the verification.",
            "VERIFY_GUEST": "Please verify your email for your guest booking with Idbook Hotels. Use the verification code below to complete the verification.",
            "OTHER": "Please use the verification code below to complete your request with Idbook Hotels.",
        }
        
        # Group-specific personalization for SIGNUP
        if otp_for == "SIGNUP" and group_name:
            group_subjects = {
                "B2C-GRP": "Welcome to Idbook Hotels - Verify Your Customer Account",
                "HOTELIER-GRP": "Welcome to Idbook Hotels - Verify Your Hotelier Partner Account",
                "CORPORATE-GRP": "Welcome to Idbook Corporate - Verify Your Business Travel Account",
                "BUSINESS-GRP": "Welcome to Idbook Business - Verify Your Business Account",
                "FRANCHISE-GRP": "Welcome to Idbook Hotels - Verify Your Franchise Partner Account",
                "AGENT-GRP": "Welcome to Idbook Hotels - Verify Your Travel Agent Account",
            }
            
            group_messages = {
                "B2C-GRP": "Thank you for signing up with Idbook Hotels! Use the verification code below to complete your customer registration and start booking amazing hotels at great prices.",
                "HOTELIER-GRP": "Welcome to the Idbook Hotels family! As a hotelier partner, you're joining a platform that connects you with travelers worldwide. Use the verification code below to complete your partner registration.",
                "CORPORATE-GRP": "Welcome to Idbook Corporate! Your business travel program is being set up. Use the verification code below to complete your corporate account registration and start managing your team's travel needs.",
                "BUSINESS-GRP": "Welcome to Idbook Business! Use the verification code below to complete your business account registration and unlock exclusive business travel solutions.",
                "FRANCHISE-GRP": "Welcome to Idbook Hotels as a franchise partner! Use the verification code below to complete your franchise registration and start growing your business with us.",
                "AGENT-GRP": "Welcome to Idbook Hotels as a travel agent partner! Use the verification code below to complete your agent registration and start offering amazing travel solutions to your customers.",
            }
            
            subject = group_subjects.get(group_name, base_otp_subjects.get(otp_for, base_otp_subjects["OTHER"]))
            message = group_messages.get(group_name, base_otp_messages.get(otp_for, base_otp_messages["OTHER"]))
        else:
            # Use base subjects and messages
            subject = base_otp_subjects.get(otp_for, base_otp_subjects.get(normalized_otp_for, base_otp_subjects["OTHER"]))
            message = base_otp_messages.get(otp_for, base_otp_messages.get(normalized_otp_for, base_otp_messages["OTHER"]))
        
        context = {
            "otp": otp,
            "otp_for": otp_for,  # Keep original for template logic
            "group_name": group_name,  # Pass group_name to template
            "subject": subject,
            "message": message,
        }
        html_content = email_template.render(context)
        print(f"Sending OTP email to {to_emails} with subject: {subject}")
        send_otp_email(otp, to_emails, template=html_content, subject=subject)
        print(f"OTP email sent successfully to {to_emails}")
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"Error in send_email_task: {str(e)}")
        print(f"Traceback: {error_trace}")
        # Re-raise to let Celery handle retries
        raise


@celery_idbook.task(bind=True)
def send_mobile_otp_task(self, otp, mobile_number, otp_for=""):
    try:
        print("otp::", otp, "mobile_number::", mobile_number)
        # Map otp_for to valid SMS template codes
        if otp_for == "VERIFY-GUEST":
            template_code = "VERIFY"
        elif otp_for == "GOOGLE-SIGNUP":
            template_code = "SIGNUP"
        elif otp_for == "GOOGLE-LOGIN":
            template_code = "LOGIN"
        else:
            template_code = otp_for
        obj = Fast2SmsMixin()
        response = obj.post_dlt_otpsms(mobile_number, otp, template_code)
        if response.status_code != 200:
            SmsOtpLog.objects.create(
                mobile_number=mobile_number, response=response.json()
            )
            SmsNotificationLog.objects.create(
                mobile_number=mobile_number,
                sms_for=(
                    template_code
                    if template_code in dict(SMS_TYPES_CHOICES)
                    else "other"
                ),
                response=response.json(),
            )
    except Exception as e:
        print(e)


@celery_idbook.task(bind=True)
def customer_signup_link_task(self, signup_link, name, to_emails):
    print("Initiated Customer Signup Link Email")
    email_template = get_template("email_template/signup-link.html")
    context = {"name": name, "sign_up_link": signup_link}
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
def send_signup_email_task(self, name, to_emails, group_name, extra_context=None):
    print("Initiated Welcome Email")

    # Decide template and subject based on group
    if group_name == "B2C-GRP":
        email_template = get_template("signup_welcome_templates/customer-welcome.html")
        subject = "Welcome to Idbook Hotels - Your Travel Journey Begins"
    elif group_name == "HOTELIER-GRP":
        email_template = get_template("signup_welcome_templates/hotelier-welcome.html")
        subject = "Welcome to Idbook Hotels Family - Hotelier Partner"
    elif group_name == "CORPORATE-GRP":
        email_template = get_template("signup_welcome_templates/corporate-welcome.html")
        subject = "Welcome to Idbook Corporate - Business Travel Program"
    elif group_name == "BUSINESS-GRP":
        email_template = get_template("signup_welcome_templates/corporate-welcome.html")
        subject = "Welcome to Idbook Business - Your Business Travel Solution"
    elif group_name == "FRANCHISE-GRP":
        email_template = get_template("signup_welcome_templates/hotelier-welcome.html")
        subject = "Welcome to Idbook Hotels - Franchise Partner"
    elif group_name == "AGENT-GRP":
        email_template = get_template("signup_welcome_templates/agent-welcome.html")
        subject = "Welcome to Idbook Hotels - Travel Agent Partner"
    else:
        email_template = get_template("email_template/signup.html")
        subject = "Welcome to Idbook Hotels!"

    context = {"name": name}
    if extra_context:
        context.update(extra_context)

    html_content = email_template.render(context)
    send_welcome_email(subject, html_content, to_emails)
