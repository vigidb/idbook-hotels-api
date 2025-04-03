from apps.org_resources.models import Enquiry, CompanyDetail
import traceback

def get_enquiry_details(enquiry_id):
    try:
        enquiry_obj = Enquiry.objects.get(id=enquiry_id)
        return enquiry_obj
    except Exception as e:
        print(e)
        print(traceback.format_exc())
        return None

def is_corporate_email_exist(email):
    is_exist = CompanyDetail.objects.filter(
        company_email=email).exists()
    return is_exist

def is_corporate_number_exist(company_phone):
    is_exist = CompanyDetail.objects.filter(
        company_phone=company_phone).exists()
    return is_exist

        
    
    
