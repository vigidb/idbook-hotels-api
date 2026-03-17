from __future__ import annotations

from datetime import timedelta
from typing import Iterable, List, Dict, Any, Optional, Tuple

from django.conf import settings
from django.db import transaction
from django.db.models import Q, QuerySet
from django.utils import timezone

from IDBOOKAPI.email_utils import send_email as core_send_email
from apps.authentication.constants import CORPORATE_GROUPS, UserGroups
from apps.authentication.models import User
from apps.messaging.models import (
    Contact,
    Campaign,
    CampaignStep,
    CampaignContact,
    MessageLog,
    MessagingProviderConfig,
)
from apps.sms_gateway.mixins.fastwosms_mixins import send_template_sms


def normalize_phone(phone: str) -> str:
    if not phone:
        return ""
    phone = phone.strip()
    # Very light normalization for now; country-specific logic can be added later.
    return phone.replace(" ", "").replace("-", "")


def resolve_campaign_contacts(campaign: Campaign) -> QuerySet[Contact]:
    qs = Contact.objects.all()
    if campaign.target_group_type:
        qs = qs.filter(group_type=campaign.target_group_type)

    filters = campaign.target_filters or {}
    if city := filters.get("city"):
        qs = qs.filter(city__iexact=city)
    if country := filters.get("country"):
        qs = qs.filter(country__iexact=country)

    return qs


def get_delay_delta(step: CampaignStep) -> timedelta:
    amount = step.delay_amount or 0
    unit = step.delay_unit
    if unit == CampaignStep.DelayUnit.DAYS:
        return timedelta(days=amount)
    if unit == CampaignStep.DelayUnit.WEEKS:
        return timedelta(weeks=amount)
    return timedelta(hours=amount)


def build_campaign_contacts_for_step(
    campaign: Campaign, step: CampaignStep, base_time: Optional[timezone.datetime] = None
) -> int:
    if base_time is None:
        base_time = campaign.schedule_time or timezone.now()

    scheduled_at = base_time + get_delay_delta(step)
    contacts = resolve_campaign_contacts(campaign)

    created_count = 0
    bulk_objects: List[CampaignContact] = []

    for contact in contacts.iterator():
        bulk_objects.append(
            CampaignContact(
                campaign=campaign,
                step=step,
                contact=contact,
                status=CampaignContact.Status.PENDING,
                scheduled_at=scheduled_at,
            )
        )

        # Flush in chunks to keep memory bounded
        if len(bulk_objects) >= 1000:
            CampaignContact.objects.bulk_create(bulk_objects, ignore_conflicts=True)
            created_count += len(bulk_objects)
            bulk_objects.clear()

    if bulk_objects:
        CampaignContact.objects.bulk_create(bulk_objects, ignore_conflicts=True)
        created_count += len(bulk_objects)

    return created_count


def build_campaign_contacts(campaign: Campaign) -> int:
    """
    Create CampaignContact rows for all active steps and target contacts.
    Returns total created rows.
    """
    total_created = 0
    base_time = campaign.schedule_time or timezone.now()
    for step in campaign.steps.filter(active=True).order_by("order_index"):
        total_created += build_campaign_contacts_for_step(campaign, step, base_time)
        # advance base_time so delays are relative between steps
        base_time = base_time + get_delay_delta(step)
    return total_created


def get_default_provider_for_channel(channel: str) -> Optional[MessagingProviderConfig]:
    try:
        return MessagingProviderConfig.objects.filter(
            channel=channel, active=True, is_default=True
        ).first()
    except Exception:
        return None


def build_template_variables(contact: Contact, extra_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    ctx: Dict[str, Any] = {
        "name": contact.name or (contact.user.get_full_name() if contact.user else ""),
        "city": contact.city,
        "country": contact.country,
        "phone": contact.phone,
        "email": contact.email,
        "group_type": contact.group_type,
    }
    if contact.user_id:
        ctx["user_id"] = contact.user_id

    if extra_context:
        ctx.update(extra_context)
    return ctx


def render_template_string(template: str, variables: Dict[str, Any]) -> str:
    """
    Simple variable replacement using {var} placeholders.
    """
    return template.format(**variables)


def send_sms_for_campaign_contact(campaign_contact: CampaignContact) -> None:
    contact = campaign_contact.contact
    step = campaign_contact.step
    if not contact or not step:
        return

    if contact.is_blacklisted:
        campaign_contact.status = CampaignContact.Status.BLACKLISTED
        campaign_contact.save(update_fields=["status", "updated_at"])
        return
    if contact.opt_out_sms:
        campaign_contact.status = CampaignContact.Status.SKIPPED_OPT_OUT
        campaign_contact.save(update_fields=["status", "updated_at"])
        return

    phone = normalize_phone(contact.phone)
    if not phone:
        campaign_contact.status = CampaignContact.Status.FAILED
        campaign_contact.error_message = "Missing phone number"
        campaign_contact.save(update_fields=["status", "error_message", "updated_at"])
        return

    # For marketing SMS we expect template_code to map to MessageTemplate
    template_code = step.template_code
    variables = build_template_variables(contact)
    # For now we flatten variables into pipe separated string in no particular order;
    # future improvement: map to {#var#} order definition.
    variables_values = "|".join(str(v) for v in variables.values() if v is not None)

    response = send_template_sms(
        mobile_number=phone,
        template_code=template_code,
        variables_values=variables_values,
    )

    status = MessageLog.Status.SENT
    provider_response: Dict[str, Any] = {}
    provider_message_id = ""
    error_code = ""
    error_message = ""

    try:
        if response is None:
            status = MessageLog.Status.FAILED
            error_message = "No response from Fast2SMS"
        else:
            provider_response = response.json()
            if response.status_code != 200:
                status = MessageLog.Status.FAILED
                error_code = str(response.status_code)
                error_message = provider_response.get("message") or ""
            provider_message_id = str(provider_response.get("request_id", ""))
    except Exception as exc:
        status = MessageLog.Status.FAILED
        error_message = f"Exception while sending SMS: {exc}"

    MessageLog.objects.create(
        contact=contact,
        campaign=campaign_contact.campaign,
        step=step,
        channel=MessageLog.Channel.SMS,
        status=status,
        provider="fast2sms",
        provider_response=provider_response,
        sent_at=timezone.now() if status == MessageLog.Status.SENT else None,
    )

    if status == MessageLog.Status.SENT:
        campaign_contact.status = CampaignContact.Status.SENT
        campaign_contact.provider_message_id = provider_message_id
        campaign_contact.sent_at = timezone.now()
    else:
        campaign_contact.status = CampaignContact.Status.FAILED
        campaign_contact.error_code = error_code
        campaign_contact.error_message = error_message
    campaign_contact.save(
        update_fields=[
            "status",
            "provider_message_id",
            "error_code",
            "error_message",
            "sent_at",
            "updated_at",
        ]
    )


def send_email_for_campaign_contact(campaign_contact: CampaignContact) -> None:
    contact = campaign_contact.contact
    step = campaign_contact.step
    if not contact or not step:
        return

    if contact.is_blacklisted:
        campaign_contact.status = CampaignContact.Status.BLACKLISTED
        campaign_contact.save(update_fields=["status", "updated_at"])
        return
    if contact.opt_out_email:
        campaign_contact.status = CampaignContact.Status.SKIPPED_OPT_OUT
        campaign_contact.save(update_fields=["status", "updated_at"])
        return

    if not contact.email:
        campaign_contact.status = CampaignContact.Status.FAILED
        campaign_contact.error_message = "Missing email address"
        campaign_contact.save(update_fields=["status", "error_message", "updated_at"])
        return

    # Lazy import to avoid circulars
    from apps.messaging.models import EmailTemplate

    try:
        template = EmailTemplate.objects.get(slug=step.template_code, is_active=True)
    except EmailTemplate.DoesNotExist:
        campaign_contact.status = CampaignContact.Status.FAILED
        campaign_contact.error_message = f"EmailTemplate with slug '{step.template_code}' not found"
        campaign_contact.save(update_fields=["status", "error_message", "updated_at"])
        return

    variables = build_template_variables(contact)
    try:
        subject = render_template_string(template.subject, variables)
        body_html = render_template_string(template.body_html, variables)
        body_text = template.body_text or render_template_string(
            template.body_html, variables
        )
    except KeyError as e:
        campaign_contact.status = CampaignContact.Status.FAILED
        campaign_contact.error_message = f"Template variable missing: {e}"
        campaign_contact.save(update_fields=["status", "error_message", "updated_at"])
        MessageLog.objects.create(
            contact=contact,
            campaign=campaign_contact.campaign,
            step=step,
            channel=MessageLog.Channel.EMAIL,
            status=MessageLog.Status.FAILED,
            provider="django_email",
            provider_response={"error": str(e)},
            sent_at=None,
        )
        return

    try:
        core_send_email(
            subject=subject,
            message=body_text,
            to_emails=[contact.email],
            from_email=settings.EMAIL_HOST_USER,
        )
        status = MessageLog.Status.SENT
        sent_at = timezone.now()
        error_message = ""
    except Exception as exc:
        status = MessageLog.Status.FAILED
        sent_at = None
        error_message = f"Exception while sending email: {exc}"

    MessageLog.objects.create(
        contact=contact,
        campaign=campaign_contact.campaign,
        step=step,
        channel=MessageLog.Channel.EMAIL,
        status=status,
        provider="django_email",
        provider_response={},
        sent_at=sent_at,
    )

    if status == MessageLog.Status.SENT:
        campaign_contact.status = CampaignContact.Status.SENT
        campaign_contact.sent_at = sent_at
    else:
        campaign_contact.status = CampaignContact.Status.FAILED
        campaign_contact.error_message = error_message
    campaign_contact.save(
        update_fields=["status", "error_message", "sent_at", "updated_at"]
    )


def get_template_variable_definitions() -> List[Dict[str, str]]:
    """
    Central registry of available template variables. This can be expanded over time.
    """
    return [
        {"name": "name", "label": "Contact name", "category": "contact"},
        {"name": "city", "label": "City", "category": "contact"},
        {"name": "country", "label": "Country", "category": "contact"},
        {"name": "phone", "label": "Phone", "category": "contact"},
        {"name": "email", "label": "Email", "category": "contact"},
        {"name": "group_type", "label": "Group type", "category": "contact"},
        {"name": "user_id", "label": "User ID", "category": "user"},
        # booking / travel variables can be added later and resolved via extra_context
    ]


def _link_user_by_phone_email(phone: str, email: str) -> Optional[User]:
    """Find User by mobile_number or email (exact/iexact)."""
    if not phone and not email:
        return None
    q = Q()
    if phone:
        q |= Q(mobile_number=phone)
    if email:
        q |= Q(email__iexact=email)
    return User.objects.filter(q).first()


def _link_user_via_company(phone: str, email: str) -> Optional[User]:
    """If contact is corporate, resolve User from CompanyDetail by company/contact email or phone."""
    from apps.org_resources.models import CompanyDetail

    q = Q()
    if email:
        q |= Q(company_email__iexact=email) | Q(contact_email_address__iexact=email)
    if phone:
        q |= Q(company_phone=phone) | Q(contact_number=phone)
    if not q:
        return None
    company = CompanyDetail.objects.filter(q).select_related("added_user", "business_rep").first()
    if not company:
        return None
    return company.added_user or company.business_rep


def _link_user_via_agent(phone: str, email: str) -> Optional[User]:
    """If contact is agent, resolve User from AgentDetail by agent_email or agent_phone."""
    from apps.org_resources.models import AgentDetail

    q = Q()
    if email:
        q |= Q(agent_email__iexact=email)
    if phone:
        q |= Q(agent_phone=phone)
    if not q:
        return None
    agent = AgentDetail.objects.filter(q).select_related("added_user").first()
    return agent.added_user if agent else None


def link_existing_user(phone: str, email: str) -> Optional[User]:
    """
    Best-effort link to an existing User using phone or email (User table only).
    """
    return _link_user_by_phone_email(phone, email)


def link_existing_user_by_group(phone: str, email: str, group_type: str) -> Optional[User]:
    """
    Resolve User for a contact: try User by phone/email first; if not found,
    for corporate groups try CompanyDetail (company_email, contact_email_address,
    company_phone, contact_number); for agent groups try AgentDetail (agent_email,
    agent_phone). Returns the User to link to the Contact (or None).
    """
    user = _link_user_by_phone_email(phone, email)
    if user:
        return user
    if group_type in CORPORATE_GROUPS:
        user = _link_user_via_company(phone, email)
        if user:
            return user
    if group_type in (UserGroups.AGENT_GRP, UserGroups.AGENT_ADMIN):
        user = _link_user_via_agent(phone, email)
        if user:
            return user
    return None


def upsert_contact_from_row(
    *,
    name: str,
    phone: str,
    email: str,
    city: str,
    country: str,
    group_type: str,
    source: str = "excel_upload",
    remarks: str = "",
    department: str = "",
) -> Tuple[Contact, bool]:
    """
    Create or update a Contact from a single row of imported data.
    Returns (contact, created_flag).
    """
    phone_norm = normalize_phone(phone)
    email_norm = email.strip().lower() if email else ""

    # Try to find an existing contact by (phone or email) + group_type.
    contact_q = Contact.objects.all()
    contact_filter = Q(group_type=group_type)
    if phone_norm:
        contact_filter &= Q(phone=phone_norm)
    elif email_norm:
        contact_filter &= Q(email=email_norm)
    contact = contact_q.filter(contact_filter).first()

    if not contact:
        user = link_existing_user_by_group(phone_norm, email_norm, group_type)
        contact = Contact.objects.create(
            user=user,
            name=name or (user.get_full_name() if user else ""),
            phone=phone_norm,
            email=email_norm,
            city=city or "",
            country=country or "",
            group_type=group_type,
            source=source,
            remarks=(remarks or "").strip(),
            department=(department or "").strip(),
        )
        return contact, True

    # Update existing contact with any new non-empty values.
    update_fields = ["updated_at"]
    if contact.user_id is None and (phone_norm or email_norm):
        user = link_existing_user_by_group(phone_norm, email_norm, group_type)
        if user:
            contact.user = user
            update_fields.append("user")
    if name and not contact.name:
        contact.name = name
        update_fields.append("name")
    if city and not contact.city:
        contact.city = city
        update_fields.append("city")
    if country and not contact.country:
        contact.country = country
        update_fields.append("country")
    if email_norm and not contact.email:
        contact.email = email_norm
        update_fields.append("email")
    if remarks is not None and remarks.strip():
        contact.remarks = remarks.strip()
        update_fields.append("remarks")
    if department is not None and department.strip():
        contact.department = department.strip()
        update_fields.append("department")
    if len(update_fields) > 1:
        contact.save(update_fields=update_fields)
    return contact, False


