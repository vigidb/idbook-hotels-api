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

email_send_queue = "email-send-queue"
#email_booking_queue = "email-booking-queue"
app.conf.task_routes = {
    'apps.authentication.tasks.send_email_task': {'queue': email_send_queue},
    'apps.authentication.tasks.customer_signup_link_task': {'queue': email_send_queue},
    'apps.authentication.tasks.send_signup_email_task': {'queue': email_send_queue},
    'apps.booking.tasks.send_booking_email_task': {'queue': email_send_queue},
    'apps.booking.tasks.create_invoice_task': {'queue': email_send_queue}
}


# TASK = os.getenv('TASK')

##
##BEAT_CONFIG = {
##    multiupload_task_name: {
##        'add-every-3-minutes': {
##            'task': 'apps.authenteication.tasks.email_task',
##            'schedule': crontab(minute="*/3"),
##            'options': {'queue': queue_name}
##        },
##    },
##}
##
##
##if TASK:
##    app.conf.beat_schedule = BEAT_CONFIG[f'{TASK}_group']
