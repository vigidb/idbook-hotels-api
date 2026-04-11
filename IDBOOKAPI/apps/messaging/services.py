from __future__ import annotations

from datetime import timedelta
import json
from typing import Iterable, List, Dict, Any, Optional, Tuple

import re
from django.conf import settings
from django.core import signing
from django.db import transaction
from django.db.models import Q, QuerySet
from django.utils import timezone

from IDBOOKAPI.email_utils import send_email as core_send_email
from IDBOOKAPI.email_utils import send_email_with_smtp_config
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
from apps.messaging.provider_runtime import (
    resolve_email_provider_for_send,
    resolve_sms_provider_for_send,
)
from apps.sms_gateway.mixins.fastwosms_mixins import send_template_sms


def normalize_phone(phone: str) -> str:
    if not phone:
        return ""
    phone = phone.strip()
    # Very light normalization for now; country-specific logic can be added later.
    return phone.replace(" ", "").replace("-", "")


def normalize_segment_tags(value: Any) -> List[str]:
    """
    Normalize free-form tags to a sorted unique list of lowercase strings.
    Accepts list, comma-separated string, or JSON array string.
    """
    if value is None or value == "":
        return []
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return []
        if s.startswith("["):
            try:
                parsed = json.loads(s)
                if isinstance(parsed, list):
                    value = parsed
                else:
                    value = [s]
            except json.JSONDecodeError:
                value = [s]
        else:
            value = [x.strip() for x in s.split(",") if x.strip()]
    if not isinstance(value, (list, tuple)):
        return []
    out: List[str] = []
    for t in value:
        x = str(t).strip().lower()
        if x:
            out.append(x)
    return sorted(set(out))


def _apply_segment_tag_filters(qs: QuerySet[Contact], filters: Dict[str, Any]) -> QuerySet[Contact]:
    """
    target_filters may include:
      - tags or segment_tags: list of strings (or comma-separated string)
      - tags_match: "any" (default) or "all" — contact.segment_tags must include any / all listed tags
    Uses JSON contains on PostgreSQL (jsonb @>); tags are compared lowercase.
    """
    raw = filters.get("tags")
    if raw is None:
        raw = filters.get("segment_tags")
    if raw is None:
        return qs
    tags = normalize_segment_tags(raw)
    if not tags:
        return qs
    match_mode = str(filters.get("tags_match") or "any").strip().lower()
    if match_mode == "all":
        for t in tags:
            qs = qs.filter(segment_tags__contains=[t])
        return qs
    q = Q()
    for t in tags:
        q |= Q(segment_tags__contains=[t])
    return qs.filter(q)


def resolve_campaign_contacts(campaign: Campaign) -> QuerySet[Contact]:
    qs = Contact.objects.all()
    if campaign.target_group_type:
        qs = qs.filter(group_type=campaign.target_group_type)

    filters = campaign.target_filters or {}
    if city := filters.get("city"):
        qs = qs.filter(city__iexact=city)
    if country := filters.get("country"):
        qs = qs.filter(country__iexact=country)
    qs = _apply_segment_tag_filters(qs, filters)

    return qs


def count_campaign_audience(campaign: Campaign) -> int:
    """Number of contacts matching campaign targeting (cheap COUNT query)."""
    return resolve_campaign_contacts(campaign).count()


def campaign_has_active_steps(campaign: Campaign) -> bool:
    """At least one active step with a non-empty template (slug / SMS code)."""
    return (
        campaign.steps.filter(active=True)
        .exclude(template_code="")
        .exists()
    )


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
    company = None
    agent = None
    try:
        if contact.group_type in CORPORATE_GROUPS or contact.group_type == UserGroups.CORPORATE_GRP:
            company = resolve_company_detail_for_contact(contact)
        if contact.group_type in (UserGroups.AGENT_GRP, UserGroups.AGENT_ADMIN):
            agent = resolve_agent_detail_for_contact(contact)
    except Exception:
        # Best-effort enrichment only; never block message sending here.
        company = None
        agent = None

    ctx: Dict[str, Any] = {
        "name": contact.name or (contact.user.get_full_name() if contact.user else ""),
        "city": contact.city,
        "country": contact.country,
        "phone": contact.phone,
        "email": contact.email,
        "group_type": contact.group_type,
        # Nested access for richer templates, e.g. {contact.city}, {user.email}
        "contact": contact,
        "user": contact.user,
        # Corporate / Agent enrichment (available only for those audiences)
        "company": company,
        "agent": agent,
    }
    if contact.user_id:
        ctx["user_id"] = contact.user_id

    if extra_context:
        ctx.update(extra_context)
    return ctx


class MissingTemplateVariableError(Exception):
    def __init__(self, missing: List[str]):
        self.missing = missing
        super().__init__(f"Missing template variables: {', '.join(missing)}")


def _resolve_path(root: Any, path: str) -> Any:
    """
    Resolve dot paths like 'contact.city' or 'user.email' against dicts/objects.
    Returns None if any step is missing.
    """
    current = root
    for part in (p for p in path.split(".") if p):
        if current is None:
            return None
        if isinstance(current, dict):
            if part not in current:
                return None
            current = current.get(part)
            continue
        if not hasattr(current, part):
            return None
        current = getattr(current, part)
    return current


def render_template_string(template: str, variables: Dict[str, Any]) -> str:
    """
    Variable replacement for template placeholders.

    Supports:
    - Dot paths: {{contact.city}}, {{user.email}}
    - Defaults: {{name|default:Guest}} (used when missing/blank)
    - Backward compatible single-brace tokens for valid variable expressions:
      {name}, {contact.city}, {name|default:Guest}
    """
    if not template:
        return ""

    # Match either:
    # 1) {{ ... }} (preferred format)
    # 2) { ... } for identifier-like expressions only (legacy format)
    # This intentionally excludes CSS blocks like { margin: 0; ... }.
    pattern = re.compile(
        r"\{\{([^{}]+)\}\}|\{([a-zA-Z_][a-zA-Z0-9_.]*(?:\|default:[^{}]*)?)\}"
    )
    missing_vars: List[str] = []

    def _replace(match: re.Match) -> str:
        expr = (match.group(1) or match.group(2) or "").strip()
        if not expr:
            return ""

        default_value = ""
        if "|default:" in expr:
            expr, default_value = expr.split("|default:", 1)
            expr = expr.strip()
            default_value = default_value.strip()

        value = _resolve_path(variables, expr)
        if value is None or value == "":
            if default_value != "":
                return str(default_value)
            missing_vars.append(expr)
            return ""
        return str(value)

    rendered = pattern.sub(_replace, template)
    if missing_vars:
        # De-duplicate while preserving first-seen order
        seen = set()
        unique_missing: List[str] = []
        for v in missing_vars:
            if v in seen:
                continue
            seen.add(v)
            unique_missing.append(v)
        raise MissingTemplateVariableError(unique_missing)
    return rendered


def apply_template_variable_defaults(template_variables_schema: Any, variables: Dict[str, Any]) -> Dict[str, Any]:
    """
    Apply per-template default values stored in EmailTemplate.variables_schema.

    Backward compatible with existing schema formats:
    - list[str] (variable names)
    - list[{"name": "...", "default": "..."}]

    Defaults only apply to *top-level* variable keys (e.g. "name", "city").
    For nested paths like "user.first_name", prefer using {{user.first_name|default:Guest}}
    in the template string itself.
    """
    if not template_variables_schema:
        return variables
    if not isinstance(template_variables_schema, list):
        return variables

    for item in template_variables_schema:
        if isinstance(item, dict):
            name = (item.get("name") or "").strip()
            default_value = item.get("default")
            if not name or default_value is None:
                continue
            if variables.get(name) in (None, ""):
                variables[name] = default_value
    return variables


def build_system_variables(campaign_contact: CampaignContact) -> Dict[str, Any]:
    """
    Variables that are computed by the system at send-time (links, tokens, etc.).
    """
    frontend_base = (getattr(settings, "FRONTEND_URL", "") or "").rstrip("/")
    if not frontend_base:
        frontend_base = (getattr(settings, "BASE_URL", "") or "").rstrip("/")

    payload = {
        "contact_id": campaign_contact.contact_id,
        "campaign_id": campaign_contact.campaign_id,
        "campaign_contact_id": campaign_contact.id,
        "channel": campaign_contact.step.channel if campaign_contact.step_id else "",
    }
    token = signing.dumps(payload, salt="messaging-unsubscribe")
    unsubscribe_url = f"{frontend_base}/unsubscribe?token={token}" if frontend_base else ""
    return {"unsubscribe_token": token, "unsubscribe_url": unsubscribe_url}


def resolve_company_detail_for_contact(contact: Contact):
    """
    Best-effort CompanyDetail lookup for a messaging Contact.
    Uses contact.email/phone to match CompanyDetail fields.
    """
    from django.db.models import Q
    from apps.org_resources.models import CompanyDetail

    phone = normalize_phone(contact.phone) if contact.phone else ""
    email = (contact.email or "").strip().lower()

    q = Q()
    if email:
        q |= Q(company_email__iexact=email) | Q(contact_email_address__iexact=email)
    if phone:
        q |= Q(company_phone=phone) | Q(contact_number=phone)
    if not q:
        return None
    return CompanyDetail.objects.filter(q).select_related("added_user", "business_rep").first()


def resolve_agent_detail_for_contact(contact: Contact):
    """
    Best-effort AgentDetail lookup for a messaging Contact.
    Uses contact.email/phone to match AgentDetail fields.
    """
    from django.db.models import Q
    from apps.org_resources.models import AgentDetail

    phone = normalize_phone(contact.phone) if contact.phone else ""
    email = (contact.email or "").strip().lower()

    q = Q()
    if email:
        q |= Q(agent_email__iexact=email) | Q(contact_email_address__iexact=email)
    if phone:
        q |= Q(agent_phone=phone) | Q(contact_number=phone)
    if not q:
        return None
    return AgentDetail.objects.filter(q).select_related("added_user").first()


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
    variables = build_template_variables(
        contact, extra_context=build_system_variables(campaign_contact)
    )
    # SMS provider expects only primitive values; exclude nested objects.
    variables.pop("contact", None)
    variables.pop("user", None)
    variables.pop("company", None)
    variables.pop("agent", None)
    # For now we flatten variables into pipe separated string in no particular order;
    # future improvement: map to {#var#} order definition.
    variables_values = "|".join(str(v) for v in variables.values() if v is not None)

    step_db = (
        CampaignStep.objects.select_related("messaging_provider")
        .filter(pk=step.pk)
        .first()
    )
    sms_prov_used, sms_cfg = resolve_sms_provider_for_send(
        step_provider=step_db.messaging_provider if step_db else None,
        default_resolver=get_default_provider_for_channel,
    )
    response = send_template_sms(
        mobile_number=phone,
        template_code=template_code,
        variables_values=variables_values,
        sms_config=sms_cfg,
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

    provider_label = (
        f"fast2sms:{sms_prov_used.name}" if sms_prov_used else "fast2sms"
    )

    MessageLog.objects.create(
        contact=contact,
        campaign=campaign_contact.campaign,
        step=step,
        channel=MessageLog.Channel.SMS,
        status=status,
        provider=provider_label,
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
        template = EmailTemplate.objects.select_related("provider").get(
            slug=step.template_code, is_active=True
        )
    except EmailTemplate.DoesNotExist:
        campaign_contact.status = CampaignContact.Status.FAILED
        campaign_contact.error_message = f"EmailTemplate with slug '{step.template_code}' not found"
        campaign_contact.save(update_fields=["status", "error_message", "updated_at"])
        return

    variables = build_template_variables(
        contact, extra_context=build_system_variables(campaign_contact)
    )
    variables = apply_template_variable_defaults(getattr(template, "variables_schema", None), variables)
    try:
        subject = render_template_string(template.subject, variables)
        body_html = render_template_string(template.body_html, variables)
        body_text = (
            render_template_string(template.body_text, variables)
            if template.body_text
            else render_template_string(template.body_html, variables)
        )
    except MissingTemplateVariableError as exc:
        campaign_contact.status = CampaignContact.Status.FAILED
        campaign_contact.error_message = str(exc)
        campaign_contact.save(update_fields=["status", "error_message", "updated_at"])
        MessageLog.objects.create(
            contact=contact,
            campaign=campaign_contact.campaign,
            step=step,
            channel=MessageLog.Channel.EMAIL,
            status=MessageLog.Status.FAILED,
            provider="django_email",
            provider_response={"missing_variables": exc.missing},
            sent_at=None,
        )
        return

    step_db = (
        CampaignStep.objects.select_related("messaging_provider")
        .filter(pk=step.pk)
        .first()
    )
    email_prov_used, smtp_cfg = resolve_email_provider_for_send(
        step_provider=step_db.messaging_provider if step_db else None,
        template_provider=template.provider,
        default_resolver=get_default_provider_for_channel,
    )
    provider_label = (
        f"smtp:{email_prov_used.name}" if smtp_cfg and email_prov_used else "django_email"
    )

    try:
        if smtp_cfg:
            send_email_with_smtp_config(
                subject=subject,
                message=body_text,
                to_emails=[contact.email],
                html_message=body_html,
                smtp=smtp_cfg,
            )
        else:
            core_send_email(
                subject=subject,
                message=body_text,
                html_message=body_html,
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
        provider=provider_label,
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


def get_template_variable_definitions() -> List[Dict[str, Any]]:
    """
    Central registry of available template variables for the frontend.

    Notes:
    - Frontend should insert variables as {{variable_name}} into templates.
    - Default value syntax: {{name|default:Guest}}
    - Nested access is supported: {{contact.city}}, {{user.email}}
    """
    return [
        # Contact (flat)
        {"name": "name", "label": "Contact name", "category": "contact", "scope": "all", "type": "string", "example": "{{name}}", "default_hint": "Guest"},
        {"name": "city", "label": "City", "category": "contact", "scope": "all", "type": "string", "example": "{{city}}", "default_hint": ""},
        {"name": "country", "label": "Country", "category": "contact", "scope": "all", "type": "string", "example": "{{country}}", "default_hint": ""},
        {"name": "phone", "label": "Phone", "category": "contact", "scope": "all", "type": "string", "example": "{{phone}}", "default_hint": ""},
        {"name": "email", "label": "Email", "category": "contact", "scope": "all", "type": "string", "example": "{{email}}", "default_hint": ""},
        {"name": "group_type", "label": "Group type", "category": "contact", "scope": "all", "type": "string", "example": "{{group_type}}"},
        # User (basic)
        {"name": "user_id", "label": "User ID", "category": "user", "scope": "linked_user", "type": "number", "example": "{{user_id}}"},
        {"name": "user.email", "label": "User email", "category": "user", "scope": "linked_user", "type": "string", "example": "{{user.email}}", "default_hint": ""},
        {"name": "user.first_name", "label": "User first name", "category": "user", "scope": "linked_user", "type": "string", "example": "{{user.first_name|default:Guest}}", "default_hint": "Guest"},
        # Nested contact access (useful for consistent UI groups)
        {"name": "contact.city", "label": "Contact city", "category": "contact", "scope": "all", "type": "string", "example": "{{contact.city}}"},
        {"name": "contact.email", "label": "Contact email", "category": "contact", "scope": "all", "type": "string", "example": "{{contact.email}}"},
        # Corporate: CompanyDetail (best-effort resolution)
        {"name": "company.company_name", "label": "Company name", "category": "company", "scope": "corporate", "type": "string", "example": "{{company.company_name|default:}}"},
        {"name": "company.brand_name", "label": "Brand name", "category": "company", "scope": "corporate", "type": "string", "example": "{{company.brand_name|default:}}"},
        {"name": "company.company_email", "label": "Company email", "category": "company", "scope": "corporate", "type": "string", "example": "{{company.company_email|default:}}"},
        {"name": "company.company_phone", "label": "Company phone", "category": "company", "scope": "corporate", "type": "string", "example": "{{company.company_phone|default:}}"},
        {"name": "company.contact_person_name", "label": "Company contact person", "category": "company", "scope": "corporate", "type": "string", "example": "{{company.contact_person_name|default:}}"},
        # Agent: AgentDetail (best-effort resolution)
        {"name": "agent.agent_name", "label": "Agent name", "category": "agent", "scope": "agent", "type": "string", "example": "{{agent.agent_name|default:}}"},
        {"name": "agent.agent_code", "label": "Agent code", "category": "agent", "scope": "agent", "type": "string", "example": "{{agent.agent_code|default:}}"},
        {"name": "agent.agent_email", "label": "Agent email", "category": "agent", "scope": "agent", "type": "string", "example": "{{agent.agent_email|default:}}"},
        {"name": "agent.agent_phone", "label": "Agent phone", "category": "agent", "scope": "agent", "type": "string", "example": "{{agent.agent_phone|default:}}"},
        # System variables (computed at send-time)
        {"name": "unsubscribe_url", "label": "Unsubscribe link", "category": "system", "scope": "email", "type": "url", "example": "{{unsubscribe_url}}"},
        {"name": "unsubscribe_token", "label": "Unsubscribe token", "category": "system", "scope": "email", "type": "string", "example": "{{unsubscribe_token}}"},
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
    segment_tags: Optional[List[str]] = None,
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

    tag_list = normalize_segment_tags(segment_tags) if segment_tags is not None else []

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
            segment_tags=tag_list,
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
    if segment_tags is not None:
        existing_raw = contact.segment_tags if isinstance(contact.segment_tags, list) else []
        merged = sorted(
            set(normalize_segment_tags(existing_raw)) | set(tag_list)
        )
        if merged != normalize_segment_tags(existing_raw):
            contact.segment_tags = merged
            update_fields.append("segment_tags")
    if len(update_fields) > 1:
        contact.save(update_fields=update_fields)
    return contact, False


