from __future__ import annotations

"""Campaign Celery tasks — routed to the marketing campaign queue in IDBOOKAPI/celery.py (not the transactional email/SMS queue)."""

from datetime import timedelta

from celery import shared_task
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.messaging.models import Campaign, CampaignContact, CampaignStep, MessageLog
from apps.messaging.services import (
    build_campaign_contacts,
    send_sms_for_campaign_contact,
    send_email_for_campaign_contact,
)

# Batch size for sending (keeps memory and per-task time bounded; rate limiting can be added later)
CAMPAIGN_BATCH_SIZE = 100
CAMPAIGN_DUE_SCAN_LIMIT = 1000


def _claim_due_campaign_contact_ids(*, campaign_id: int | None = None, limit: int = CAMPAIGN_DUE_SCAN_LIMIT) -> list[int]:
    """
    Atomically claim due pending contacts by flipping status -> queued.
    This reduces duplicate sends when multiple scheduler tasks overlap.
    """
    now = timezone.now()
    due_qs = CampaignContact.objects.filter(
        status=CampaignContact.Status.PENDING,
        campaign__status__in=[Campaign.Status.SCHEDULED, Campaign.Status.RUNNING],
    ).filter(Q(scheduled_at__isnull=True) | Q(scheduled_at__lte=now))
    if campaign_id:
        due_qs = due_qs.filter(campaign_id=campaign_id)
    due_ids = list(due_qs.order_by("scheduled_at", "id").values_list("id", flat=True)[:limit])
    if not due_ids:
        return []

    with transaction.atomic():
        claimed_ids = list(
            CampaignContact.objects.filter(
                id__in=due_ids,
                status=CampaignContact.Status.PENDING,
            ).values_list("id", flat=True)
        )
        if claimed_ids:
            CampaignContact.objects.filter(id__in=claimed_ids).update(
                status=CampaignContact.Status.QUEUED
            )
    return claimed_ids


def _schedule_next_due_poll(campaign_id: int) -> None:
    """
    Schedule a focused due-contact scan for this campaign at its next pending send time.
    This provides a safety net when global beat polling is delayed under heavy load.
    """
    campaign = Campaign.objects.filter(id=campaign_id).first()
    if not campaign or campaign.status not in (Campaign.Status.SCHEDULED, Campaign.Status.RUNNING):
        return

    now = timezone.now()
    next_due = (
        CampaignContact.objects.filter(
            campaign_id=campaign_id,
            status=CampaignContact.Status.PENDING,
            scheduled_at__gt=now,
        )
        .order_by("scheduled_at")
        .values_list("scheduled_at", flat=True)
        .first()
    )
    if next_due:
        process_due_campaign_contacts_task.apply_async(kwargs={"campaign_id": campaign_id}, eta=next_due)


def _create_next_recurring_campaign(source: Campaign) -> None:
    """
    Clone campaign + steps for the next cycle when recurrence is enabled.
    """
    if not source.repeat_every_days or source.repeat_every_days <= 0:
        return

    base_time = source.schedule_time or timezone.now()
    next_schedule = base_time + timedelta(days=source.repeat_every_days)
    if timezone.is_naive(next_schedule):
        next_schedule = timezone.make_aware(next_schedule, timezone.get_current_timezone())

    with transaction.atomic():
        # Idempotency guard: avoid duplicate next-run campaigns.
        if Campaign.objects.filter(
            repeat_from_campaign=source,
            schedule_time=next_schedule,
        ).exists():
            return

        next_campaign = Campaign.objects.create(
            name=source.name,
            description=source.description,
            target_group_type=source.target_group_type,
            target_filters=source.target_filters,
            status=Campaign.Status.SCHEDULED,
            schedule_time=next_schedule,
            repeat_every_days=source.repeat_every_days,
            repeat_from_campaign=source,
            created_by=source.created_by,
        )

        steps = source.steps.all().order_by("order_index")
        CampaignStep.objects.bulk_create(
            [
                CampaignStep(
                    campaign=next_campaign,
                    order_index=step.order_index,
                    channel=step.channel,
                    template_code=step.template_code,
                    delay_amount=step.delay_amount,
                    delay_unit=step.delay_unit,
                    active=step.active,
                    messaging_provider=step.messaging_provider,
                )
                for step in steps
            ]
        )

    now = timezone.now()
    if next_schedule > now:
        enqueue_campaign_contacts_task.apply_async(
            args=[next_campaign.id], eta=next_schedule
        )
    else:
        enqueue_campaign_contacts_task.delay(next_campaign.id)


def _sync_campaign_runtime_status(campaign_id: int) -> None:
    """
    Keep campaign.status aligned with pipeline progress.

    - scheduled/running -> completed when no pending/queued contacts remain.
    - scheduled -> running once any contact has reached a terminal status.
    """
    campaign = Campaign.objects.filter(id=campaign_id).first()
    if not campaign:
        return
    if campaign.status not in (Campaign.Status.SCHEDULED, Campaign.Status.RUNNING):
        return

    qs = CampaignContact.objects.filter(campaign_id=campaign_id)
    if not qs.exists():
        return

    has_pending = qs.filter(
        status__in=[CampaignContact.Status.PENDING, CampaignContact.Status.QUEUED]
    ).exists()
    if not has_pending:
        if campaign.status != Campaign.Status.COMPLETED:
            campaign.status = Campaign.Status.COMPLETED
            campaign.save(update_fields=["status", "updated_at"])
            _create_next_recurring_campaign(campaign)
        return

    # Campaign has started processing; reflect that in status.
    if campaign.status == Campaign.Status.SCHEDULED and qs.filter(
        status__in=[
            CampaignContact.Status.SENT,
            CampaignContact.Status.FAILED,
            CampaignContact.Status.SKIPPED_OPT_OUT,
            CampaignContact.Status.BLACKLISTED,
        ]
    ).exists():
        campaign.status = Campaign.Status.RUNNING
        campaign.save(update_fields=["status", "updated_at"])


@shared_task
def enqueue_campaign_contacts_task(campaign_id: int) -> int:
    """Build CampaignContact rows for the campaign, then queue batch send tasks for due contacts."""
    campaign = Campaign.objects.filter(id=campaign_id).first()
    if not campaign:
        return 0
    # Ignore stale ETA/queued tasks if campaign was paused/deleted/closed in the meantime.
    if campaign.status not in (Campaign.Status.SCHEDULED, Campaign.Status.RUNNING):
        return 0
    # For scheduled campaigns, do not start early if an old ETA task fires after reschedule.
    if (
        campaign.status == Campaign.Status.SCHEDULED
        and campaign.schedule_time
        and campaign.schedule_time > timezone.now()
    ):
        return 0
    created = build_campaign_contacts(campaign)
    due_ids = _claim_due_campaign_contact_ids(campaign_id=campaign_id, limit=10000)
    for i in range(0, len(due_ids), CAMPAIGN_BATCH_SIZE):
        chunk = due_ids[i : i + CAMPAIGN_BATCH_SIZE]
        send_campaign_batch_task.delay(chunk)
    _schedule_next_due_poll(campaign_id)
    _sync_campaign_runtime_status(campaign_id)
    return created


@shared_task
def process_due_campaign_contacts_task(campaign_id: int | None = None) -> int:
    """
    Periodic task: queue batch send for PENDING campaign contacts whose scheduled_at is due.
    Register in Celery Beat (e.g. every 1 minute) so scheduled campaigns actually send.
    """
    due_ids = _claim_due_campaign_contact_ids(campaign_id=campaign_id, limit=CAMPAIGN_DUE_SCAN_LIMIT)
    for i in range(0, len(due_ids), CAMPAIGN_BATCH_SIZE):
        chunk = due_ids[i : i + CAMPAIGN_BATCH_SIZE]
        send_campaign_batch_task.delay(chunk)
    # Sync affected campaigns to completed/running as due rows are consumed.
    campaign_ids = (
        CampaignContact.objects.filter(id__in=due_ids)
        .values_list("campaign_id", flat=True)
        .distinct()
    )
    for affected_campaign_id in campaign_ids:
        _sync_campaign_runtime_status(affected_campaign_id)
        _schedule_next_due_poll(affected_campaign_id)
    if campaign_id and not campaign_ids:
        # If nothing was due for this campaign yet, keep one focused poll aligned to its next due time.
        _schedule_next_due_poll(campaign_id)
    return len(due_ids)


@shared_task
def send_campaign_batch_task(campaign_contact_ids: list[int]) -> None:
    contacts = CampaignContact.objects.filter(id__in=campaign_contact_ids).select_related(
        "contact", "campaign", "step"
    )
    now = timezone.now()
    for campaign_contact in contacts:
        # Do not process sends while campaign is paused/completed/failed/draft.
        if campaign_contact.campaign.status not in (
            Campaign.Status.SCHEDULED,
            Campaign.Status.RUNNING,
        ):
            continue
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
            try:
                send_sms_for_campaign_contact(campaign_contact)
            except Exception as exc:
                campaign_contact.status = CampaignContact.Status.FAILED
                campaign_contact.error_message = f"Unhandled SMS send exception: {exc}"
                campaign_contact.save(update_fields=["status", "error_message", "updated_at"])
                MessageLog.objects.create(
                    contact=campaign_contact.contact,
                    campaign=campaign_contact.campaign,
                    step=campaign_contact.step,
                    channel=MessageLog.Channel.SMS,
                    status=MessageLog.Status.FAILED,
                    provider="runtime",
                    provider_response={"error_message": str(exc), "exception_type": exc.__class__.__name__},
                    sent_at=None,
                )
        elif campaign_contact.step.channel == campaign_contact.step.Channel.EMAIL:
            try:
                send_email_for_campaign_contact(campaign_contact)
            except Exception as exc:
                campaign_contact.status = CampaignContact.Status.FAILED
                campaign_contact.error_message = f"Unhandled email send exception: {exc}"
                campaign_contact.save(update_fields=["status", "error_message", "updated_at"])
                MessageLog.objects.create(
                    contact=campaign_contact.contact,
                    campaign=campaign_contact.campaign,
                    step=campaign_contact.step,
                    channel=MessageLog.Channel.EMAIL,
                    status=MessageLog.Status.FAILED,
                    provider="runtime",
                    provider_response={"error_message": str(exc), "exception_type": exc.__class__.__name__},
                    sent_at=None,
                )

    for campaign_id in {cc.campaign_id for cc in contacts if cc.campaign_id}:
        _sync_campaign_runtime_status(campaign_id)

