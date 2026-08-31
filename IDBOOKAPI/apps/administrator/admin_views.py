from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse
from django.views.decorators.http import require_GET

from IDBOOKAPI.celery import (
    airiq_queue,
    email_send_queue,
    marketing_campaign_queue,
    recpay_queue,
)


@staff_member_required
@require_GET
def celery_queue_routing_admin_view(request):
    """Expose resolved Celery queue routing in Django admin."""
    return JsonResponse(
        {
            "environment": str(getattr(settings, "ENVIRONMENT", "") or "").strip()
            or "unknown",
            "queues": {
                "default": getattr(settings, "CELERY_TASK_DEFAULT_QUEUE", "general-queue"),
                "email": email_send_queue,
                "marketing": marketing_campaign_queue,
                "recpay": recpay_queue,
                "airiq": airiq_queue,
            },
        }
    )
