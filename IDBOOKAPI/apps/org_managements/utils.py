from .models import BusinessDetail


def get_domain_business_details(domain_name):
    bdetails = BusinessDetail.objects.filter(
        domain_name=domain_name).first()
    return bdetails
