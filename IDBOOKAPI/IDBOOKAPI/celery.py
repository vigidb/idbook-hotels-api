import os
from celery import Celery
from celery.schedules import crontab
from django.conf import settings

# set the default django settings module 
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'IDBOOKAPI.settings')

app = Celery('IDBOOKAPI')

app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()
#app.autodiscover_tasks(lambda: settings.INSTALLED_APPS)

environment = settings.ENVIRONMENT
if environment == 'dev':
    email_send_queue = "dev-email-send-queue"
else:
    email_send_queue = "email-send-queue"
#email_booking_queue = "email-booking-queue"
app.conf.task_routes = {
    'apps.authentication.tasks.send_email_task': {'queue': email_send_queue},
    'apps.authentication.tasks.send_mobile_otp_task': {'queue': email_send_queue},
    'apps.booking.tasks.send_booking_sms_task': {'queue': email_send_queue},
    'apps.hotels.tasks.send_hotel_sms_task': {'queue': email_send_queue},
    'apps.hotels.tasks.send_hotel_email_task': {'queue': email_send_queue},
    'apps.hotels.tasks.update_monthly_pay_at_hotel_eligibility_task': {'queue': email_send_queue},
    'apps.hotels.tasks.create_service_agreement_task': {'queue': email_send_queue},
    'apps.authentication.tasks.customer_signup_link_task': {'queue': email_send_queue},
    'apps.authentication.tasks.send_signup_email_task': {'queue': email_send_queue},
    'apps.booking.tasks.send_booking_email_task': {'queue': email_send_queue},
    'apps.booking.tasks.create_invoice_task': {'queue': email_send_queue},
    'apps.booking.tasks.send_cancelled_booking_task':{'queue': email_send_queue},
    'apps.booking.tasks.send_completed_booking_task': {'queue': email_send_queue},
    'apps.org_resources.tasks.send_enquiry_email_task': {'queue': email_send_queue},
    'apps.org_resources.tasks.admin_send_sms_task': {'queue': email_send_queue}

}


#TASK = os.getenv('TASK')


##BEAT_CONFIG = {
##    'recpay-task_group': {
##        'add-every-3-minutes': {
##            'task': 'apps.org_resources.tasks.initiate_recurring_payment',
##            'schedule': crontab(minute="*/1"),
##            'options': {'queue': "recpay-initiate-queue"}
##        },
##    },
##}

app.conf.beat_schedule = {
    'add-every-3-minutes': {
        'task': 'apps.org_resources.tasks.initiate_recurring_payment',
        'schedule': crontab(minute="*/1"),
        'options': {'queue': "recpay-initiate-queue"}
    },
}

##CELERY_BEAT_SCHEDULE = {
##    'recpay-task_group': {
##        'add-every-3-minutes': {
##            'task': 'apps.org_resources.tasks.initiate_recurring_payment',
##            'schedule': crontab(minute="*/1"),
##            'options': {'queue': "recpay-initiate-queue"}
##        },
##    },
##}
#if TASK:
#app.conf.beat_schedule = BEAT_CONFIG[f'{TASK}_group']
##app.conf.beat_schedule = BEAT_CONFIG['recpay-task_group']
