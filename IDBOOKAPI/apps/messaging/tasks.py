from __future__ import annotations

from celery import shared_task
from django.db.models import Q
from django.utils import timezone

from apps.messaging.models import Campaign, CampaignContact
from apps.messaging.services import (
    build_campaign_contacts,
    send_sms_for_campaign_contact,
    send_email_for_campaign_contact,
)

# Batch size for sending (keeps memory and per-task time bounded; rate limiting can be added later)
CAMPAIGN_BATCH_SIZE = 100


@shared_task
def enqueue_campaign_contacts_task(campaign_id: int) -> int:
    """Build CampaignContact rows for the campaign, then queue batch send tasks for due contacts."""
    campaign = Campaign.objects.get(id=campaign_id)
    created = build_campaign_contacts(campaign)
    now = timezone.now()
    # Queue sending for contacts that are due (scheduled_at <= now or not set)
    due_ids = list(
        CampaignContact.objects.filter(
            campaign_id=campaign_id,
            status=CampaignContact.Status.PENDING,
        )
        .filter(Q(scheduled_at__isnull=True) | Q(scheduled_at__lte=now))
        .values_list("id", flat=True)[: 10000]
    )  # cap to avoid huge queues
    for i in range(0, len(due_ids), CAMPAIGN_BATCH_SIZE):
        chunk = due_ids[i : i + CAMPAIGN_BATCH_SIZE]
        send_campaign_batch_task.delay(chunk)
    return created


@shared_task
def process_due_campaign_contacts_task() -> int:
    """
    Periodic task: queue batch send for PENDING campaign contacts whose scheduled_at is due.
    Register in Celery Beat (e.g. every 1 minute) so scheduled campaigns actually send.
    """
    now = timezone.now()
    due_ids = list(
        CampaignContact.objects.filter(status=CampaignContact.Status.PENDING)
        .filter(Q(scheduled_at__isnull=True) | Q(scheduled_at__lte=now))
        .values_list("id", flat=True)[:1000]
    )
    for i in range(0, len(due_ids), CAMPAIGN_BATCH_SIZE):
        chunk = due_ids[i : i + CAMPAIGN_BATCH_SIZE]
        send_campaign_batch_task.delay(chunk)
    return len(due_ids)


@shared_task
def send_campaign_batch_task(campaign_contact_ids: list[int]) -> None:
    contacts = CampaignContact.objects.filter(id__in=campaign_contact_ids).select_related(
        "contact", "campaign", "step"
    )
    now = timezone.now()
    for campaign_contact in contacts:
        # Skip if not yet scheduled or already processed
        if (
            campaign_contact.scheduled_at
            and campaign_contact.scheduled_at > now
        ) or campaign_contact.status not in (
            CampaignContact.Status.PENDING,
            CampaignContact.Status.QUEUED,
        ):
            continue

        if campaign_contact.step.channel == campaign_contact.step.Channel.SMS:
            send_sms_for_campaign_contact(campaign_contact)
        elif campaign_contact.step.channel == campaign_contact.step.Channel.EMAIL:
            send_email_for_campaign_contact(campaign_contact)

