import os
from celery import Celery
from celery.schedules import crontab
from django.conf import settings

# set the default django settings module
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "IDBOOKAPI.settings")

app = Celery("IDBOOKAPI")

app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
# app.autodiscover_tasks(lambda: settings.INSTALLED_APPS)

environment = settings.ENVIRONMENT
normalized_environment = str(environment or "").strip().lower()
is_dev_environment = normalized_environment in {"dev", "development", "local", "test"}
queue_prefix = "dev-" if is_dev_environment else ""

email_send_queue = f"{queue_prefix}email-send-queue"
marketing_campaign_queue = f"{queue_prefix}marketing-campaign-queue"
# email_booking_queue = "email-booking-queue"
app.conf.task_routes = {
    "apps.authentication.tasks.send_email_task": {"queue": email_send_queue},
    "apps.authentication.tasks.send_mobile_otp_task": {"queue": email_send_queue},
    "apps.booking.tasks.send_booking_sms_task": {"queue": email_send_queue},
    "apps.hotels.tasks.send_hotel_sms_task": {"queue": email_send_queue},
    "apps.hotels.tasks.send_hotel_email_task": {"queue": email_send_queue},
    "apps.hotels.tasks.update_monthly_pay_at_hotel_eligibility_task": {
        "queue": email_send_queue
    },
    "apps.hotels.tasks.create_service_agreement_task": {"queue": email_send_queue},
    "apps.hotels.tasks.send_hotel_receipt_email_task": {"queue": email_send_queue},
    "apps.authentication.tasks.customer_signup_link_task": {"queue": email_send_queue},
    "apps.authentication.tasks.send_signup_email_task": {"queue": email_send_queue},
    "apps.booking.tasks.send_booking_email_task": {"queue": email_send_queue},
    "apps.booking.tasks.create_invoice_task": {"queue": email_send_queue},
    "apps.booking.tasks.send_cancelled_booking_task": {"queue": email_send_queue},
    "apps.booking.tasks.send_completed_booking_task": {"queue": email_send_queue},
    "apps.booking.tasks.send_query_email_task": {"queue": email_send_queue},
    "apps.booking.tasks.send_query_sms_task": {"queue": email_send_queue},
    "apps.org_resources.tasks.send_enquiry_email_task": {"queue": email_send_queue},
    "apps.org_resources.tasks.admin_send_sms_task": {"queue": email_send_queue},
    "apps.org_resources.tasks.pro_member_send_sms_task": {"queue": email_send_queue},
    # AirIQ token management tasks
    "apps.flights.tasks.refresh_airiq_token_task": {"queue": "airiq-token-queue"},
    "apps.flights.tasks.cleanup_expired_airiq_tokens_task": {
        "queue": "airiq-token-queue"
    },
    "apps.flights.tasks.check_airiq_token_status_task": {"queue": "airiq-token-queue"},
    "apps.flights.tasks.emergency_airiq_token_refresh_task": {
        "queue": "airiq-token-queue"
    },
    # Flight notification tasks
    "apps.flights.tasks.send_flight_booking_confirmation_task": {
        "queue": email_send_queue
    },
    "apps.flights.tasks.send_flight_status_update_task": {"queue": email_send_queue},
    # Marketing / bulk campaigns — isolated from OTP, booking, and other transactional tasks
    "apps.messaging.tasks.enqueue_campaign_contacts_task": {
        "queue": marketing_campaign_queue
    },
    "apps.messaging.tasks.send_campaign_batch_task": {
        "queue": marketing_campaign_queue
    },
    "apps.messaging.tasks.process_due_campaign_contacts_task": {
        "queue": marketing_campaign_queue
    },
}


# TASK = os.getenv('TASK')


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
    "add-every-3-minutes": {
        "task": "apps.org_resources.tasks.initiate_recurring_payment",
        "schedule": crontab(minute="*/1"),
        "options": {"queue": "recpay-initiate-queue"},
    },
    "wallet-expiry-task": {
        "task": "apps.booking.tasks.wallet_expiry_task",
        "schedule": crontab(minute="*/30"),
        "options": {"queue": "recpay-initiate-queue"},
    },
    # AirIQ Token Management Scheduled Tasks
    "airiq-token-daily-refresh": {
        "task": "apps.flights.tasks.refresh_airiq_token_task",
        "schedule": crontab(hour=6, minute=0),  # Daily at 6:00 AM
        "options": {"queue": "airiq-token-queue"},
    },
    "airiq-token-cleanup": {
        "task": "apps.flights.tasks.cleanup_expired_airiq_tokens_task",
        "schedule": crontab(hour=2, minute=0),  # Daily at 2:00 AM
        "options": {"queue": "airiq-token-queue"},
    },
    "airiq-token-status-check": {
        "task": "apps.flights.tasks.check_airiq_token_status_task",
        "schedule": crontab(minute=0),  # Every hour at minute 0
        "options": {"queue": "airiq-token-queue"},
    },
    # Messaging: process due campaign contacts (scheduled sends)
    "process-due-campaign-contacts": {
        "task": "apps.messaging.tasks.process_due_campaign_contacts_task",
        "schedule": crontab(minute="*/1"),  # Every minute
        "options": {"queue": marketing_campaign_queue},
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
# if TASK:
# app.conf.beat_schedule = BEAT_CONFIG[f'{TASK}_group']
##app.conf.beat_schedule = BEAT_CONFIG['recpay-task_group']
