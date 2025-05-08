from django.urls import path
from rest_framework import routers

from apps.log_management.views import *
router = routers.DefaultRouter()
router.register(r'user-subscription', UserSubscriptionLogsViewSet, basename='user-subscription')

urlpatterns = [

]
