from django.urls import path
from rest_framework import routers
from apps.booking.viewsets import *
from apps.booking.subviews import payment_viewset, related_viewset, flight_viewset
from apps.booking.subviews.enhanced_flight_viewset import EnhancedFlightBookingViewSet

router = routers.DefaultRouter()

router.register(r'bookings', BookingViewSet, basename='bookings')
router.register(r'applied-coupons', AppliedCouponViewSet, basename='applied-coupons')
router.register(r'reviews', related_viewset.ReviewViewSet, basename='reviews')
router.register(r'invoices', related_viewset.InvoiceViewSet, basename='invoices')
router.register(r'payment', BookingPaymentDetailViewSet,
                basename='payment')
router.register(r'property-payment-info', payment_viewset.PaymentPropertyViewSet,
                basename='property-payment-info')
# Enhanced flight booking endpoints with pricing sessions (RECOMMENDED)
router.register(r'flight-bookings', EnhancedFlightBookingViewSet,
                basename='flight-bookings')
# Legacy flight booking endpoints for backward compatibility
router.register(r'legacy-flight-bookings', flight_viewset.FlightBookingViewSet,
                basename='legacy-flight-bookings')

urlpatterns = [

]
