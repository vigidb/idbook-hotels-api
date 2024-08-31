from django.urls import path
from rest_framework import routers
from apps.customer.viewsets import *

router = routers.DefaultRouter()

router.register(r'customers', CustomerViewSet, basename='customers')

urlpatterns = [

]