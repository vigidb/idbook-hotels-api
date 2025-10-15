from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .viewsets import FlightSearchViewSet, FlightPricingViewSet, FlightBookingViewSet

# Create DRF router
router = DefaultRouter()
router.register(r'search', FlightSearchViewSet, basename='flight-search')
router.register(r'pricing', FlightPricingViewSet, basename='flight-pricing')
router.register(r'bookings', FlightBookingViewSet, basename='flight-booking')

app_name = 'flights'

urlpatterns = [
    path('', include(router.urls)),
]

# URL patterns will be:
# /api/v1/flights/search/search/ - POST - Search flights
# /api/v1/flights/search/airports/ - GET - List airports
# /api/v1/flights/search/airlines/ - GET - List airlines
# /api/v1/flights/pricing/price/ - POST - Get flight pricing
# /api/v1/flights/pricing/fare-rules/ - POST - Get fare rules
# /api/v1/flights/bookings/ - GET - List user bookings
# /api/v1/flights/bookings/ - POST - Create booking
# /api/v1/flights/bookings/{id}/ - GET - Get booking details
# /api/v1/flights/bookings/{id}/ - PUT/PATCH - Update booking
# /api/v1/flights/bookings/{id}/ - DELETE - Cancel booking