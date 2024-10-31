# db utils
from .models import CompanyDetail, UserNotification
from typing import Dict

def get_company_details(company_id):
    try:
        company_details = CompanyDetail.objects.get(id=company_id)
        return company_details
    except Exception as e:
        return None


def create_notification(notification_dict: Dict):
    try:
        UserNotification.objects.create(**notification_dict)
    except Exception as e:
        print(e)
