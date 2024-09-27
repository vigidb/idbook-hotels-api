from django.urls import path
from rest_framework import routers
from apps.org_managements.viewsets import *

router = routers.DefaultRouter()

router.register(r'business-detail', BusinessDetailViewSet, basename='business_detail')
