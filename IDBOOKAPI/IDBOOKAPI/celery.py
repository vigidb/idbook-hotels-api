import logging
import os
import time

from celery import Celery
from celery.schedules import crontab
from celery.signals import task_failure, task_postrun, task_prerun
from django.conf import settings

lifecycle_logger = logging.getLogger("celery.lifecycle")
_task_start_monotonic: dict[str, float] = {}

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
use_code_beat_schedule = str(
    os.getenv("CELERY_USE_CODE_BEAT_SCHEDULE", "false")
).strip().lower() in {"1", "true", "yes", "on"}

email_send_queue = f"{queue_prefix}email-send-queue"
marketing_campaign_queue = f"{queue_prefix}marketing-campaign-queue"
# Default unrouted queue: CELERY_TASK_DEFAULT_QUEUE in settings.py (`dev-general-queue` vs `general-queue`).
recpay_queue = f"{queue_prefix}recpay-initiate-queue"
airiq_queue = f"{queue_prefix}airiq-token-queue"
resolved_default_queue = getattr(settings, "CELERY_TASK_DEFAULT_QUEUE", "general-queue")

lifecycle_logger.info(
    "celery.startup environment=%s queue_prefix=%s queues={default:%s,email:%s,marketing:%s,recpay:%s,airiq:%s}",
    normalized_environment or "unknown",
    queue_prefix or "<none>",
    resolved_default_queue,
    email_send_queue,
    marketing_campaign_queue,
    recpay_queue,
    airiq_queue,
)

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
    "apps.org_resources.tasks.initiate_recurring_payment": {"queue": recpay_queue},
    # Booking tasks not listed above (explicit routes keep them off the general queue).
    "apps.booking.tasks.wallet_expiry_task": {"queue": recpay_queue},
    "apps.booking.tasks.send_flight_booking_task": {"queue": email_send_queue},
    "apps.booking.tasks.issue_flight_ticket_task": {"queue": email_send_queue},
    # AirIQ token management tasks
    "apps.flights.tasks.refresh_airiq_token_task": {"queue": airiq_queue},
    "apps.flights.tasks.cleanup_expired_airiq_tokens_task": {
        "queue": airiq_queue
    },
    "apps.flights.tasks.check_airiq_token_status_task": {"queue": airiq_queue},
    "apps.flights.tasks.emergency_airiq_token_refresh_task": {
        "queue": airiq_queue
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

if use_code_beat_schedule:
    # Keep this as a fallback for environments that do not use django-celery-beat.
    # Production should prefer DB-managed schedules from Django admin.
    app.conf.beat_schedule = {
        "recurring-payment-daily": {
            "task": "apps.org_resources.tasks.initiate_recurring_payment",
            "schedule": crontab(hour=1, minute=0),
            "options": {"queue": recpay_queue},
        },
        "wallet-expiry-daily": {
            "task": "apps.booking.tasks.wallet_expiry_task",
            "schedule": crontab(hour=2, minute=0),
            "options": {"queue": recpay_queue},
        },
        "airiq-token-daily-refresh": {
            "task": "apps.flights.tasks.refresh_airiq_token_task",
            "schedule": crontab(hour=6, minute=0),
            "options": {"queue": airiq_queue},
        },
        "airiq-token-cleanup": {
            "task": "apps.flights.tasks.cleanup_expired_airiq_tokens_task",
            "schedule": crontab(hour=3, minute=0),
            "options": {"queue": airiq_queue},
        },
        # Campaign due scan can stay frequent; volume-driven and isolated in marketing queue.
        "process-due-campaign-contacts": {
            "task": "apps.messaging.tasks.process_due_campaign_contacts_task",
            "schedule": crontab(minute="*/5"),
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


def _safe_kwarg_keys(kwargs: dict | None, *, limit: int = 25) -> list[str]:
    if not kwargs:
        return []
    keys = sorted(kwargs.keys())
    return keys[:limit] + (["…"] if len(keys) > limit else [])


def _celery_task_name(task=None, sender=None) -> str:
    """Resolve Celery task name from signal kwargs (sender vs task differ by Celery version)."""
    for obj in (task, sender):
        if obj is None:
            continue
        name = getattr(obj, "name", None)
        if name:
            return name
    return str(sender or task or "unknown")


@task_prerun.connect
def _celery_log_task_prerun(
    sender=None, task_id=None, task=None, args=None, kwargs=None, **extra
):
    """Structured INFO logs for every Celery task start (no positional values — avoids PII)."""
    _task_start_monotonic[task_id] = time.monotonic()
    args_len = len(args) if args is not None else 0
    lifecycle_logger.info(
        "celery.task.start task=%s id=%s args_len=%s kwargs_keys=%s",
        _celery_task_name(task=task, sender=sender),
        task_id,
        args_len,
        _safe_kwarg_keys(kwargs),
    )


@task_postrun.connect
def _celery_log_task_postrun(
    sender=None, task_id=None, task=None, args=None, kwargs=None, retval=None, **extra
):
    start = _task_start_monotonic.pop(task_id, None)
    elapsed_ms = (
        int((time.monotonic() - start) * 1000) if start is not None else None
    )
    lifecycle_logger.info(
        "celery.task.success task=%s id=%s elapsed_ms=%s",
        _celery_task_name(task=task, sender=sender),
        task_id,
        elapsed_ms,
    )


@task_failure.connect
def _celery_log_task_failure(
    sender=None,
    task_id=None,
    exception=None,
    args=None,
    kwargs=None,
    traceback=None,
    einfo=None,
    **extra,
):
    _task_start_monotonic.pop(task_id, None)
    lifecycle_logger.error(
        "celery.task.failure task=%s id=%s error=%s",
        _celery_task_name(task=None, sender=sender),
        task_id,
        exception,
    )
