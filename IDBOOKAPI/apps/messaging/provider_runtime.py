"""
Runtime helpers for MessagingProviderConfig JSON `settings`.

Email: SMTP via django.core.mail (custom connection).
SMS: Fast2SMS bulkV2 DLT route (same shape as env-based defaults).
"""

from __future__ import annotations

import copy
from typing import Any, Dict, Optional, Tuple

from django.conf import settings

from apps.messaging.models import MessagingProviderConfig

SECRET_PLACEHOLDER = "********"

# Keys treated as write-only secrets (masked on read; merged on partial update)
SECRET_KEYS = frozenset({"smtp_password", "fast2sms_api_key"})


def mask_settings_for_api(raw: Optional[dict]) -> dict:
    if not raw:
        return {}
    out = copy.deepcopy(raw)
    for k in SECRET_KEYS:
        if k in out and out[k]:
            out[k] = SECRET_PLACEHOLDER
    return out


def merge_settings_preserving_secrets(
    old: Optional[dict], new: Optional[dict]
) -> dict:
    """Merge `new` onto `old`; keep old secret values when new omits or masks them."""
    old = dict(old or {})
    new = dict(new or {})
    merged = {**old, **new}
    for k in SECRET_KEYS:
        v = new.get(k)
        if v in (None, "", SECRET_PLACEHOLDER):
            if k in old and old[k]:
                merged[k] = old[k]
            else:
                merged.pop(k, None)
    return merged


def smtp_config_from_provider(
    prov: Optional[MessagingProviderConfig],
) -> Optional[Dict[str, Any]]:
    """
    Returns kwargs for send_email_with_smtp_config, or None to use Django default EMAIL_* settings.
    """
    if not prov or prov.channel != MessagingProviderConfig.Channel.EMAIL:
        return None
    s = prov.settings or {}
    host = (s.get("smtp_host") or "").strip()
    user = (s.get("smtp_username") or "").strip()
    password = s.get("smtp_password") or ""
    from_email = (s.get("from_email") or "").strip() or user
    if not host or not user or not password or not from_email:
        return None
    port = s.get("smtp_port")
    try:
        port_int = int(port) if port is not None else 587
    except (TypeError, ValueError):
        port_int = 587
    use_tls = s.get("smtp_use_tls", True)
    if isinstance(use_tls, str):
        use_tls = use_tls.lower() in ("1", "true", "yes", "on")
    return {
        "host": host,
        "port": port_int,
        "username": user,
        "password": password,
        "use_tls": bool(use_tls),
        "from_email": from_email,
    }


def fast2sms_config_from_provider(
    prov: Optional[MessagingProviderConfig],
) -> Optional[Dict[str, str]]:
    if not prov or prov.channel != MessagingProviderConfig.Channel.SMS:
        return None
    s = prov.settings or {}
    api_key = (s.get("fast2sms_api_key") or "").strip()
    sender = (s.get("dlt_sender_id") or "").strip()
    if not api_key or not sender:
        return None
    return {"api_key": api_key, "dlt_sender_id": sender}


def fast2sms_config_from_env() -> Dict[str, str]:
    return {
        "api_key": getattr(settings, "FAST2SMS_APIKEY", "") or "",
        "dlt_sender_id": getattr(settings, "FAST_DLT_SENDER_ID", "") or "",
    }


def resolve_email_provider_for_send(
    *,
    step_provider: Optional[MessagingProviderConfig],
    template_provider: Optional[MessagingProviderConfig],
    default_resolver,
) -> Tuple[Optional[MessagingProviderConfig], Optional[Dict[str, Any]]]:
    """
    Order: step → template → DB default → (None, None) for Django EMAIL_* fallback.
    Returns (config_row_used, smtp_dict_or_none).
    """
    for prov in (step_provider, template_provider):
        if prov and prov.active and prov.channel == MessagingProviderConfig.Channel.EMAIL:
            cfg = smtp_config_from_provider(prov)
            if cfg:
                return prov, cfg

    default = default_resolver(MessagingProviderConfig.Channel.EMAIL)
    if default and default.active:
        cfg = smtp_config_from_provider(default)
        if cfg:
            return default, cfg

    return None, None


def resolve_sms_provider_for_send(
    *,
    step_provider: Optional[MessagingProviderConfig],
    default_resolver,
) -> Tuple[Optional[MessagingProviderConfig], Dict[str, str]]:
    if step_provider and step_provider.active and step_provider.channel == MessagingProviderConfig.Channel.SMS:
        cfg = fast2sms_config_from_provider(step_provider)
        if cfg:
            return step_provider, cfg

    default = default_resolver(MessagingProviderConfig.Channel.SMS)
    if default and default.active:
        cfg = fast2sms_config_from_provider(default)
        if cfg:
            return default, cfg

    return None, fast2sms_config_from_env()


def resolve_sms_config_for_test(override_provider_id: Optional[int]) -> Dict[str, str]:
    """SMS test send: optional explicit provider row, else environment defaults."""
    if override_provider_id is not None:
        prov = MessagingProviderConfig.objects.filter(
            pk=int(override_provider_id),
            channel=MessagingProviderConfig.Channel.SMS,
            active=True,
        ).first()
        if not prov:
            raise ValueError("Invalid or inactive messaging_provider_id for SMS")
        cfg = fast2sms_config_from_provider(prov)
        if not cfg:
            raise ValueError("SMS provider settings are incomplete (api key and sender ID required)")
        return cfg
    return fast2sms_config_from_env()


def resolve_email_provider_for_test(
    *,
    template_provider: Optional[MessagingProviderConfig],
    override_provider_id: Optional[int],
    default_resolver,
) -> Tuple[Optional[MessagingProviderConfig], Optional[Dict[str, Any]]]:
    """
    Test-send resolution: explicit `messaging_provider_id` wins; else template → default → Django.
    """
    if override_provider_id is not None:
        prov = MessagingProviderConfig.objects.filter(
            pk=int(override_provider_id),
            channel=MessagingProviderConfig.Channel.EMAIL,
            active=True,
        ).first()
        if not prov:
            raise ValueError("Invalid or inactive messaging_provider_id for email")
        cfg = smtp_config_from_provider(prov)
        return prov, cfg

    return resolve_email_provider_for_send(
        step_provider=None,
        template_provider=template_provider,
        default_resolver=default_resolver,
    )


def credential_guidance() -> Dict[str, Any]:
    """Short static hints for the admin provider form (keep concise)."""
    return {
        "general": {
            "channel": "Email = SMTP. SMS = Fast2SMS + DLT. Channel cannot be changed after save.",
            "display_name": "Internal label for you only—not shown to recipients.",
            "default_for_channel": (
                "Fallback when nothing else picks a provider. One default per channel; else server env is used."
            ),
            "active": "Off = not used for sends.",
        },
        "email": {
            "label": "Email (SMTP)",
            "summary": "Use an app password or SMTP credentials from your provider—not your normal web login.",
            "fields": [
                {
                    "key": "smtp_host",
                    "label": "SMTP host",
                    "hint": "e.g. smtp.gmail.com, smtp.office365.com—host only, no https://",
                },
                {
                    "key": "smtp_port",
                    "label": "SMTP port",
                    "hint": "Usually 587 + TLS on; 465 if your provider says so.",
                },
                {
                    "key": "smtp_use_tls",
                    "label": "Use TLS",
                    "hint": "Keep on for port 587 in most cases.",
                },
                {
                    "key": "smtp_username",
                    "label": "SMTP username",
                    "hint": "Often the sending mailbox address.",
                },
                {
                    "key": "smtp_password",
                    "label": "SMTP password",
                    "hint": "App / SMTP password or key from the provider.",
                },
                {
                    "key": "from_email",
                    "label": "From email",
                    "hint": "What recipients see; must be allowed for this SMTP user.",
                },
            ],
        },
        "sms": {
            "label": "SMS (Fast2SMS)",
            "summary": "API key + DLT sender; templates still come from your system.",
            "fields": [
                {
                    "key": "fast2sms_api_key",
                    "label": "Fast2SMS API key",
                    "hint": "Dashboard → API → authorization key.",
                },
                {
                    "key": "dlt_sender_id",
                    "label": "DLT sender ID",
                    "hint": "Approved header, e.g. 6 letters like IDHTLS.",
                },
            ],
        },
    }
