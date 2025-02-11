from django.urls import path
from rest_framework import routers
from apps.booking.viewsets import *

router = routers.DefaultRouter()

router.register(r'bookings', BookingViewSet, basename='bookings')
router.register(r'applied-coupons', AppliedCouponViewSet, basename='applied-coupons')
router.register(r'reviews', ReviewViewSet, basename='reviews')
router.register(r'payment', BookingPaymentDetailViewSet,
                basename='payment')

urlpatterns = [

]
