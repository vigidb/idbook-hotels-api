from django.urls import path
from rest_framework import routers
from apps.hotels.viewsets import *
from apps.hotels.subviews import calendar_viewset

router = routers.DefaultRouter()

router.register(r'properties', PropertyViewSet, basename='properties')
router.register(r'galleries', GalleryViewSet, basename='galleries')
router.register(r'rooms', RoomViewSet, basename='rooms')
router.register(r'rules', RuleViewSet, basename='rules')
router.register(r'inclusions', InclusionViewSet, basename='inclusions')
router.register(r'financial-details', FinancialDetailViewSet, basename='financial_details')
#router.register(r'reviews', ReviewViewSet, basename='reviews')
router.register(r'amenity-category', HotelAmenityCategoryViewSet, basename='amenity-category')
router.register(r'room-category', RoomAmenityCategoryViewSet, basename='room-category')
router.register(r'property-bank', PropertyBankDetailViewSet, basename='property-bank')
router.register(r'block/property', BlockedPropertyViewSet, basename='blocked-property')
router.register(r'calendar', calendar_viewset.PropertyCalendarViewSet, basename='calendar')

urlpatterns = [
]
