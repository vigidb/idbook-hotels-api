from apps.org_resources.models import Enquiry
import traceback

def get_enquiry_details(enquiry_id):
    try:
        enquiry_obj = Enquiry.objects.get(id=enquiry_id)
        return enquiry_obj
    except Exception as e:
        print(e)
        print(traceback.format_exc())
        return None
    
