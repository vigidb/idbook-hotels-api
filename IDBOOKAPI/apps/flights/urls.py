from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .viewsets import FlightSearchViewSet, FlightPricingViewSet  # Legacy
from .enhanced_viewsets import EnhancedFlightSearchViewSet

# Create DRF router
router = DefaultRouter()
# Enhanced flight search with pricing sessions (RECOMMENDED)
router.register(r'search', EnhancedFlightSearchViewSet, basename='flight-search')
# Legacy flight search for backward compatibility
router.register(r'legacy-search', FlightSearchViewSet, basename='legacy-flight-search')
router.register(r'pricing', FlightPricingViewSet, basename='flight-pricing')

app_name = 'flights'

urlpatterns = [
    path('', include(router.urls)),
]

# URL patterns will be:
# /api/v1/flights/search/availability/ - POST - Get flight availability (grouped by flight number)
# /api/v1/flights/search/pricing/ - POST - Create pricing session and get detailed pricing
# /api/v1/flights/search/booking-total/ - POST - Calculate final booking total with GST
# /api/v1/flights/search/seat-map/ - GET - Get seat map for selected flights
# /api/v1/flights/search/extend-session/ - POST - Extend pricing session expiry
# /api/v1/flights/search/airports/ - GET - List airports
# /api/v1/flights/search/airlines/ - GET - List airlines
# Note: Enhanced booking endpoints live under the booking app.
