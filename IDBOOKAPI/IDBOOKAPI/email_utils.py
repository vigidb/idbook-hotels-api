from django.core.mail import send_mail, EmailMultiAlternatives
from django.conf import settings
from django.core.validators import validate_email


def email_validation(email):
    try:
        validate_email(email)
        return True
    except Exception as e:
        return False

def get_domain(email):
    domain_name = ""
    if email:
        try:
            domain_name = email[email.index('@') + 1 : ]
        except Exception as e:
            print(e)
    return domain_name

def send_otp_email(otp, to_emails, template=None):
    subject = 'Idbook Login or Sign Up Verification Code'
    
    message = "Please use the verification code below to sign in.\
\n {OTP} \n If you didn’t request this, you can ignore this email.".format(OTP=otp)
    from_email = settings.EMAIL_HOST_USER
    # status = send_mail(subject, message, from_email, to_emails)
    status = send_mail(subject, template, from_email, to_emails,
                       fail_silently=False, html_message=template)
    print("email status::", status)

def send_password_forget_email(reset_password_link, to_emails):
    subject = 'Idbook Password Reset'
    message = "Click the following link to reset your password: {reset_password_link}".format(
        reset_password_link=reset_password_link)
    from_email = settings.EMAIL_HOST_USER
    status = send_mail(subject, message, from_email, to_emails)
    print("email status::", status)

def send_signup_link_email(signup_link, to_emails):
    subject = 'Idbook SignUp Link'
    message = "Click the following link to sign up: {signup_link}".format(
        signup_link=signup_link)
    from_email = settings.EMAIL_HOST_USER
    status = send_mail(subject, message, from_email, to_emails)
    print("email status::", status)

def send_welcome_email(template, to_emails):
    subject = 'Welcome to Idbook Hotels!'
    from_email = settings.EMAIL_HOST_USER
    status = send_mail(subject, template, from_email, to_emails,
                       fail_silently=False, html_message=template)
    print("welcome email status::", status)

def send_booking_email(subject, booking, to_emails, html_content):
    
    from_email = settings.EMAIL_HOST_USER
    print("from mail", from_email)
    status = send_mail(subject, html_content, from_email, to_emails,
                       fail_silently=False, html_message=html_content)
    print(status)

def send_booking_email_with_attachment(subject, file, to_emails, html_content):
    
    from_email = settings.EMAIL_HOST_USER
    msg = EmailMultiAlternatives(subject, html_content, from_email,
                                 to_emails)
    if file:
        msg.attach('flight-ticket.pdf', file.read())
    msg.content_subtype = 'html'
    status = msg.send()
    print(status)
