from django.urls import path
from rest_framework import routers
from apps.coupons.viewsets import *

router = routers.DefaultRouter()

router.register(r"coupon-partners", CouponPartnerViewSet, basename="coupon-partners")
router.register(r"coupon-campaigns", CouponCampaignViewSet, basename="coupon-campaigns")
router.register(r"coupon-slabs", CouponAmountSlabViewSet, basename="coupon-slabs")
router.register(r"coupon-redemptions", CouponRedemptionViewSet, basename="coupon-redemptions")
router.register(r"coupon-claims", CouponClaimViewSet, basename="coupon-claims")
router.register(r"user-coupon-claims", UserCouponClaimViewSet, basename="user-coupon-claims")
router.register(r"coupons", CouponViewSet, basename="coupons")

urlpatterns = []
