from django.urls import path
from rest_framework import routers

from apps.analytics.views import *

router = routers.DefaultRouter()

router.register(r'property', PropertyAnalyticsViewSet, basename='property')

urlpatterns = [

]
