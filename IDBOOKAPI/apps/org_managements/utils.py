from .models import BusinessDetail


def get_domain_business_details(domain_name):
    bdetails = BusinessDetail.objects.filter(domain_name=domain_name).first()
    return bdetails


def get_business_details(business_id):
    try:
        business_details = BusinessDetail.objects.get(id=business_id)
        return business_details
    except Excpetion as e:
        return None


##def get_business_by_name(business_name):
##    bdetails = BusinessDetail.objects.filter(
##        business_name=business_name).first()
##    return bdetails


def get_active_business():
    # Prefer explicit default if configured, else any active business
    return (
        BusinessDetail.objects.filter(active=True, is_default=True).first()
        or BusinessDetail.objects.filter(active=True).first()
    )


def get_default_business(state: str | None = None):
    """
    Resolve a billed-by business for invoices.

    Priority:
    - Active business matching `state` (case-insensitive)
    - Active default business (is_default=True)
    - Any active business
    """
    qs = BusinessDetail.objects.filter(active=True)
    if state:
        by_state = qs.filter(state__iexact=state).first()
        if by_state:
            return by_state
    return qs.filter(is_default=True).first() or qs.first()
