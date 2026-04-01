from __future__ import annotations

from typing import Optional, Tuple

from django.db import transaction
from django.db.models import Q

from apps.customer.models import Customer
from apps.org_resources.models import AgentDetail, CompanyDetail


def _safe_name(value: str, *, max_len: int) -> str:
    value = (value or "").strip()
    if not value:
        return ""
    return value[:max_len]


def ensure_company_detail_for_user(user) -> Optional[CompanyDetail]:
    """
    Ensure a Corporate user's CompanyDetail exists and user.company_id is set.

    Idempotent:
    - If user.company_id points to an existing CompanyDetail, returns it.
    - Else tries to find by company_email/contact_email_address == user.email.
    - Else creates a minimal CompanyDetail and links user.company_id.
    """
    if not user or not getattr(user, "email", None):
        return None

    with transaction.atomic():
        company = (
            CompanyDetail.objects.filter(id=getattr(user, "company_id", None)).first()
            if getattr(user, "company_id", None)
            else None
        )
        if not company:
            company = CompanyDetail.objects.filter(
                Q(company_email__iexact=user.email) | Q(contact_email_address__iexact=user.email)
            ).first()

        if not company:
            customer = Customer.objects.filter(user=user).first()
            company = CompanyDetail.objects.create(
                added_user=user,
                business_rep=user,
                company_name=_safe_name(user.name or user.email, max_len=50) or _safe_name(user.email, max_len=50),
                company_email=user.email,
                company_phone=getattr(user, "mobile_number", None),
                contact_person_name=_safe_name(user.name, max_len=50) or None,
                contact_email_address=user.email,
                contact_number=getattr(user, "mobile_number", None),
                registered_address=getattr(customer, "address", None) if customer else None,
                state=(getattr(customer, "state", "") or "") if customer else "",
                gstin_no=(getattr(customer, "gstin", "") or "") if customer else "",
                pan_no=(getattr(customer, "pan_card_number", "") or "") if customer else "",
                approved=True,
                is_active=True,
            )

        if getattr(user, "company_id", None) != company.id:
            user.company_id = company.id
            user.save(update_fields=["company_id"])
        return company


def ensure_agent_detail_for_user(user) -> Optional[AgentDetail]:
    """
    Ensure an Agent user's AgentDetail exists.

    Idempotent:
    - Tries to find AgentDetail by added_user or contact_email_address == user.email.
    - If none, creates a minimal AgentDetail.
    """
    if not user or not getattr(user, "email", None):
        return None

    with transaction.atomic():
        agent = AgentDetail.objects.filter(
            Q(added_user=user) | Q(contact_email_address__iexact=user.email)
        ).order_by("-id").first()
        if agent:
            return agent

        customer = Customer.objects.filter(user=user).first()
        agent = AgentDetail.objects.create(
            added_user=user,
            agent_name=_safe_name(user.name or user.email, max_len=50) or _safe_name(user.email, max_len=50),
            agent_email=user.email,
            agent_phone=getattr(user, "mobile_number", None),
            contact_person_name=_safe_name(user.name, max_len=50) or None,
            contact_email_address=user.email,
            contact_number=getattr(user, "mobile_number", None),
            registered_address=getattr(customer, "address", None) if customer else None,
            state=(getattr(customer, "state", "") or "") if customer else "",
            gstin_no=(getattr(customer, "gstin", "") or "") if customer else "",
            pan_no=(getattr(customer, "pan_card_number", "") or "") if customer else "",
            approved=True,
            is_active=True,
        )
        return agent

