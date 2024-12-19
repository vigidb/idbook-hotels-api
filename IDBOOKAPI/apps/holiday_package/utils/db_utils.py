# db utils
from apps.holiday_package import DailyPlan

def get_tourpackage_based_daily_plan(tour_package):
    daily_plan = DailyPlan.objects.filter(tour=tour_package)
    return daily_plan
