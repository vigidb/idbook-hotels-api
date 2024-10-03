from django.core.mail import send_mail
from django.conf import settings


def send_otp_email(otp, to_emails):
    subject = 'Idbook Sign Up Verification Code'
    message = "Please use the verification code below to sign in.\
\n {OTP} \n If you didn’t request this, you can ignore this email.".format(OTP=otp)
    from_email = settings.EMAIL_HOST_USER
    status = send_mail(subject, message, from_email, to_emails)
    print("email status::", status)

def send_password_forget_email(reset_password_link, to_emails):
    subject = 'Idbook Password Reset'
    message = "Click the following link to reset your password: {reset_password_link}".format(
        reset_password_link=reset_password_link)
    from_email = settings.EMAIL_HOST_USER
    status = send_mail(subject, message, from_email, to_emails)
    print("email status::", status)

def send_welcome_email(user_email):
    subject = 'Welcome to IDbook Hotels!'
    message = 'Thank you for joining us. We hope you enjoy your experience.'
    from_email = settings.EMAIL_HOST_USER  # Using the sender's email from settings
    recipient_list = [user_email]

    send_mail(subject, message, from_email, recipient_list)
