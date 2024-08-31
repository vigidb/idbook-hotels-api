from django.urls import path
from rest_framework import routers
from apps.hotels.viewsets import *

router = routers.DefaultRouter()

router.register(r'properties', PropertyViewSet, basename='properties')
router.register(r'galleries', GalleryViewSet, basename='galleries')
router.register(r'rooms', RoomViewSet, basename='rooms')
router.register(r'rules', RuleViewSet, basename='rules')
router.register(r'inclusions', InclusionViewSet, basename='inclusions')
router.register(r'financial-details', FinancialDetailViewSet, basename='financial_details')
router.register(r'reviews', ReviewViewSet, basename='reviews')

urlpatterns = [
]