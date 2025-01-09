from apps.analytics.models import PropertyAnalytics
from datetime import datetime, timedelta
from pytz import timezone
from django.db.models import F

def create_or_update_property_count(
    property_id, user_id=None, ip_address=None):

    try:
        ctime = datetime.now(timezone('UTC')) # + timedelta(days=1)
        cdate = ctime.date()

        property_obj = PropertyAnalytics.objects.filter(
            user=user_id, property_info=property_id,
            created__date=cdate)
        if property_obj.exists():
            property_obj.update(visit_count=F('visit_count') + 1)
        else:
            PropertyAnalytics.objects.create(
                user_id=user_id, property_info_id=property_id,
                visit_count=1)
    except Exception as e:
        print(e)

def get_property_visit(property_id, date=None, start_date=None, end_date=None):
    prop_analytics_obj = PropertyAnalytics.objects.filter(
        property_info=property_id)


    date_visit_count = 0
    drange_visit_count = 0

    if date:
        prop_analytics_date_obj = prop_analytics_obj.filter(created__date=date)
        date_visit_count = prop_analytics_date_obj.count()

    if start_date and end_date:
        prop_analytics_drange_obj = prop_analytics_obj.filter(
            created__date__lte=end_date, created__date__gte=start_date)

        drange_visit_count = prop_analytics_drange_obj.count()

    property_visit_analytics = {'date_visit_count': date_visit_count,
                                'drange_visit_count': drange_visit_count}

    return property_visit_analytics

    

        
        

