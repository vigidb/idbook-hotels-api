import re
from typing import Any, Dict, List, Optional

from django.core.mail import send_mail, EmailMultiAlternatives, get_connection
from django.conf import settings
from django.core.validators import validate_email


def _is_non_production_email() -> bool:
    env = str(getattr(settings, "ENVIRONMENT", "") or "").strip().strip("'\"").lower()
    # Add test markers for every non-production environment.
    # Only prod/live variants are treated as production-safe.
    return env not in ["prod", "production", "live"]


def _normalize_subject_for_env(subject: str) -> str:
    raw_subject = (subject or "").strip()
    # Remove any legacy/stored test marker first.
    base_subject = re.sub(r"^\s*\[(?:TEST[\]\}]?)\s*", "", raw_subject, flags=re.IGNORECASE)
    if _is_non_production_email():
        return f"[TEST] {base_subject}" if base_subject else "[TEST]"
    return base_subject


def _decorate_email_content(subject: str, message: str = "", html_message: str = ""):
    tagged_subject = _normalize_subject_for_env(subject)
    if not _is_non_production_email():
        return tagged_subject, message or "", html_message or ""
    text_notice = (
        "TEST EMAIL NOTICE: This email is sent from IDBOOK development/test "
        "environment. It is not a real production communication."
    )
    html_notice = (
        '<div style="padding:10px 12px;margin:0 0 12px 0;'
        'background:#fff3cd;border:1px solid #ffecb5;color:#664d03;'
        'font-family:Arial,sans-serif;font-size:12px;line-height:1.4;">'
        "<strong>TEST EMAIL NOTICE:</strong> This email is sent from IDBOOK "
        "development/test environment. It is not a real production communication."
        "</div>"
    )
    tagged_message = f"{text_notice}\n\n{message or ''}"
    if html_message:
        tagged_html = f"{html_notice}{html_message}"
    else:
        tagged_html = (
            f"{html_notice}<pre style=\"white-space:pre-wrap;font-family:Arial,sans-serif;\">"
            f"{(message or '').replace('<', '&lt;').replace('>', '&gt;')}</pre>"
        )
    return tagged_subject, tagged_message, tagged_html


def email_validation(email):
    try:
        validate_email(email)
        return True
    except Exception as e:
        return False


def get_domain(email):
    domain_name = ""
    if email:
        try:
            domain_name = email[email.index("@") + 1 :]
        except Exception as e:
            print(e)
    return domain_name


def send_otp_email(otp, to_emails, template=None, subject=None, bcc=None):
    if not subject:
        subject = "Idbook Hotels - Verification Code"

    from_email = settings.EMAIL_HOST_USER
    bcc_list = []
    if bcc:
        bcc_list = [x.strip() for x in bcc if x and str(x).strip()]
    subject, body_text, body_html = _decorate_email_content(subject, template or "", template or "")
    subject = _normalize_subject_for_env(subject)
    if bcc_list:
        msg = EmailMultiAlternatives(
            subject=subject,
            body=body_text,
            from_email=from_email,
            to=to_emails if isinstance(to_emails, list) else [to_emails],
            bcc=bcc_list,
        )
        msg.attach_alternative(body_html, "text/html")
        status = msg.send()
    else:
        status = send_mail(
            subject,
            body_text,
            from_email,
            to_emails,
            fail_silently=False,
            html_message=body_html,
        )
    print("email status::", status)


def send_password_forget_email(reset_password_link, to_emails):
    subject = "Idbook Password Reset"
    message = (
        "Click the following link to reset your password: {reset_password_link}".format(
            reset_password_link=reset_password_link
        )
    )
    from_email = settings.EMAIL_HOST_USER
    subject, message, html_message = _decorate_email_content(subject, message, "")
    subject = _normalize_subject_for_env(subject)
    status = send_mail(subject, message, from_email, to_emails, html_message=html_message)
    print("email status::", status)


def send_signup_link_email(signup_link, to_emails, html_content):
    subject = "Idbook SignUp Link"
    ##    message = "Click the following link to sign up: {signup_link}".format(
    ##        signup_link=signup_link)
    from_email = settings.EMAIL_HOST_USER
    subject, message, html_message = _decorate_email_content(subject, html_content, html_content)
    subject = _normalize_subject_for_env(subject)
    status = send_mail(
        subject,
        message,
        from_email,
        to_emails,
        fail_silently=False,
        html_message=html_message,
    )
    print("email status::", status)


def send_welcome_email(subject, template, to_emails, bcc=None):
    from_email = settings.EMAIL_HOST_USER
    bcc_list = []
    if bcc:
        bcc_list = [x.strip() for x in bcc if x and str(x).strip()]
    subject, body_text, body_html = _decorate_email_content(subject, template or "", template or "")
    subject = _normalize_subject_for_env(subject)
    if bcc_list:
        msg = EmailMultiAlternatives(
            subject=subject,
            body=body_text,
            from_email=from_email,
            to=to_emails if isinstance(to_emails, list) else [to_emails],
            bcc=bcc_list,
        )
        msg.attach_alternative(body_html, "text/html")
        status = msg.send()
    else:
        status = send_mail(
            subject,
            body_text,
            from_email,
            to_emails,
            fail_silently=False,
            html_message=body_html,
        )
    print("welcome email status::", status)


def collect_internal_booking_bcc_emails(booking):
    """
    Ops inboxes to BCC on booking-related emails (customer confirmation, hotelier receipt).
    - FLIGHT -> airlines@; all other types -> bookings@
    - Agent bookings -> agents@
    - Corporate bookings -> corporates@
    """
    emails = set()
    if booking.booking_type == "FLIGHT":
        emails.add(settings.INTERNAL_BOOKING_EMAIL_FLIGHT)
    else:
        emails.add(settings.INTERNAL_BOOKING_EMAIL_HOTELS_OTHERS)
    if booking.agent_id or getattr(booking, "booking_source", None) == "AGENT":
        emails.add(settings.INTERNAL_BOOKING_EMAIL_AGENTS)
    if booking.company_id or getattr(booking, "booking_source", None) == "CORPORATE":
        emails.add(settings.INTERNAL_BOOKING_EMAIL_CORPORATES)
    return [e for e in emails if e and str(e).strip()]


def partner_b2b_bcc_list():
    """Partner B2B inbox: BCC whenever email is addressed to hoteliers (property/partner)."""
    addr = getattr(settings, "PARTNER_B2B_EMAIL", None) or "partner.b2b@idbookhotels.com"
    return [addr.strip()] if addr and str(addr).strip() else []


def merge_bcc_lists(*lists):
    """Dedupe addresses (case-insensitive) across multiple BCC lists."""
    seen = set()
    out = []
    for lst in lists:
        if not lst:
            continue
        for x in lst:
            if not x or not str(x).strip():
                continue
            k = str(x).strip().lower()
            if k not in seen:
                seen.add(k)
                out.append(str(x).strip())
    return out


def send_booking_email(subject, booking, to_emails, html_content, bcc=None):

    from_email = settings.EMAIL_HOST_USER
    print("from mail", from_email)
    bcc_list = None
    if bcc:
        bcc_list = [x.strip() for x in bcc if x and str(x).strip()]
    subject, body_text, body_html = _decorate_email_content(subject, html_content or "", html_content or "")
    subject = _normalize_subject_for_env(subject)
    if bcc_list:
        msg = EmailMultiAlternatives(
            subject=subject,
            body=body_text,
            from_email=from_email,
            to=to_emails,
            bcc=bcc_list,
        )
        msg.attach_alternative(body_html, "text/html")
        status = msg.send()
        print(status)
    else:
        status = send_mail(
            subject,
            body_text,
            from_email,
            to_emails,
            fail_silently=False,
            html_message=body_html,
        )
        print(status)


def send_booking_email_with_attachment(subject, file, to_emails, html_content, bcc=None):

    from_email = settings.EMAIL_HOST_USER
    bcc_list = []
    if bcc:
        bcc_list = [x.strip() for x in bcc if x and str(x).strip()]
    extra = {}
    if bcc_list:
        extra["bcc"] = bcc_list
    subject, body_text, body_html = _decorate_email_content(subject, html_content or "", html_content or "")
    subject = _normalize_subject_for_env(subject)
    msg = EmailMultiAlternatives(
        subject=subject,
        body=body_text,
        from_email=from_email,
        to=to_emails,
        **extra,
    )
    if file:
        msg.attach("flight-ticket.pdf", file.read())
    msg.attach_alternative(body_html, "text/html")
    status = msg.send()
    print(status)


def send_email(subject, message, to_emails: list, from_email, html_message=None):
    subject, message, html_message = _decorate_email_content(subject, message or "", html_message or "")
    subject = _normalize_subject_for_env(subject)
    status = send_mail(
        subject,
        message,
        from_email,
        to_emails,
        fail_silently=False,
        html_message=html_message,
    )
    print("email status::", status)


def send_email_with_smtp_config(
    *,
    subject: str,
    message: str,
    to_emails: List[str],
    html_message: Optional[str],
    smtp: Dict[str, Any],
) -> int:
    """
    Send using an explicit SMTP connection (for per-campaign / per-template providers).
    `smtp` keys: host, port, username, password, use_tls, from_email
    """
    subject, message, html_message = _decorate_email_content(
        subject, message or "", html_message or ""
    )
    subject = _normalize_subject_for_env(subject)
    conn = get_connection(
        backend="django.core.mail.backends.smtp.EmailBackend",
        host=smtp["host"],
        port=int(smtp["port"]),
        username=smtp["username"],
        password=smtp["password"],
        use_tls=bool(smtp.get("use_tls", True)),
    )
    from_addr = smtp.get("from_email") or smtp["username"]
    msg = EmailMultiAlternatives(
        subject=subject,
        body=message or "",
        from_email=from_addr,
        to=to_emails,
        connection=conn,
    )
    if html_message:
        msg.attach_alternative(html_message, "text/html")
    return msg.send()
