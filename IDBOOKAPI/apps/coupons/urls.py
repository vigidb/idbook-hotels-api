from django.urls import path
from rest_framework import routers
from apps.coupons.viewsets import *

router = routers.DefaultRouter()

router.register(r'coupons', CouponViewSet, basename='coupons')

urlpatterns = [

]