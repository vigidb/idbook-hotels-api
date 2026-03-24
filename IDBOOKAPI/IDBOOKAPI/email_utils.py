from django.core.mail import send_mail, EmailMultiAlternatives
from django.conf import settings
from django.core.validators import validate_email


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
    if bcc_list:
        msg = EmailMultiAlternatives(
            subject=subject,
            body=template or "",
            from_email=from_email,
            to=to_emails if isinstance(to_emails, list) else [to_emails],
            bcc=bcc_list,
        )
        msg.content_subtype = "html"
        status = msg.send()
    else:
        status = send_mail(
            subject,
            template,
            from_email,
            to_emails,
            fail_silently=False,
            html_message=template,
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
    status = send_mail(subject, message, from_email, to_emails)
    print("email status::", status)


def send_signup_link_email(signup_link, to_emails, html_content):
    subject = "Idbook SignUp Link"
    ##    message = "Click the following link to sign up: {signup_link}".format(
    ##        signup_link=signup_link)
    from_email = settings.EMAIL_HOST_USER
    status = send_mail(
        subject,
        html_content,
        from_email,
        to_emails,
        fail_silently=False,
        html_message=html_content,
    )
    print("email status::", status)


def send_welcome_email(subject, template, to_emails, bcc=None):
    from_email = settings.EMAIL_HOST_USER
    bcc_list = []
    if bcc:
        bcc_list = [x.strip() for x in bcc if x and str(x).strip()]
    if bcc_list:
        msg = EmailMultiAlternatives(
            subject=subject,
            body=template,
            from_email=from_email,
            to=to_emails if isinstance(to_emails, list) else [to_emails],
            bcc=bcc_list,
        )
        msg.content_subtype = "html"
        status = msg.send()
    else:
        status = send_mail(
            subject,
            template,
            from_email,
            to_emails,
            fail_silently=False,
            html_message=template,
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
    if bcc_list:
        msg = EmailMultiAlternatives(
            subject=subject,
            body=html_content,
            from_email=from_email,
            to=to_emails,
            bcc=bcc_list,
        )
        msg.content_subtype = "html"
        status = msg.send()
        print(status)
    else:
        status = send_mail(
            subject,
            html_content,
            from_email,
            to_emails,
            fail_silently=False,
            html_message=html_content,
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
    msg = EmailMultiAlternatives(
        subject=subject,
        body=html_content,
        from_email=from_email,
        to=to_emails,
        **extra,
    )
    if file:
        msg.attach("flight-ticket.pdf", file.read())
    msg.content_subtype = "html"
    status = msg.send()
    print(status)


def send_email(subject, message, to_emails: list, from_email, html_message=None):
    status = send_mail(
        subject,
        message,
        from_email,
        to_emails,
        fail_silently=False,
        html_message=html_message,
    )
    print("email status::", status)
