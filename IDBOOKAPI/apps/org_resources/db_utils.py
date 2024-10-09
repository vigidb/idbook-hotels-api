# db utils
from .models import CompanyDetail

def get_company_details(company_id):
    try:
        company_details = CompanyDetail.objects.get(id=company_id)
        return company_details
    except Exception as e:
        return None
