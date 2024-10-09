from .models import BusinessDetail


def get_domain_business_details(domain_name):
    bdetails = BusinessDetail.objects.filter(
        domain_name=domain_name).first()
    return bdetails

def get_business_details(business_id):
    try:
        business_details = BusinessDetail.objects.get(id=business_id)
        return business_details
    except Excpetion as e:
        return None
