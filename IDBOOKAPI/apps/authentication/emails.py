from django.core.mail import send_mail
from django.conf import settings
from celery import shared_task


@shared_task
def send_welcome_email(user_email):
    subject = 'Welcome to IDbook Hotels!'
    message = 'Thank you for joining us. We hope you enjoy your experience.'
    from_email = settings.EMAIL_HOST_USER  # Using the sender's email from settings
    recipient_list = [user_email]

    send_mail(subject, message, from_email, recipient_list)
