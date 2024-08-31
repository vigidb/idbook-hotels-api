from django.urls import path
from rest_framework import routers
from apps.org_resources.viewsets import *

router = routers.DefaultRouter()

router.register(r'company-details', CompanyDetailViewSet, basename='company_details')
router.register(r'upload-media', UploadedMediaViewSet, basename='upload_media')
router.register(r'amenity-categories', AmenityCategoryViewSet, basename='amenity_category')
router.register(r'amenities', AmenityViewSet, basename='amenity')
router.register(r'enquiries', EnquiryViewSet, basename='enquiry')
router.register(r'room-types', RoomTypeViewSet, basename='room_types')
router.register(r'occupancies', OccupancyViewSet, basename='occupancies')
router.register(r'addresses', AddressViewSet, basename='addresses')
router.register(r'about-us', AboutUsViewSet, basename='about_us')
router.register(r'privacy-policy', PrivacyPolicyViewSet, basename='privacy_policy')
router.register(r'refund-and-cancellation-policy', RefundAndCancellationPolicyViewSet, basename='refund_and_cancellation_policy')
router.register(r'terms-and-conditions', TermsAndConditionsViewSet, basename='terms_and_conditions')
router.register(r'legality', LegalityViewSet, basename='legality')
router.register(r'career', CareerViewSet, basename='career')
router.register(r'faqs', FAQsViewSet, basename='faqs')

urlpatterns = [
    path('get-state-and-district/<str:query>/', GetDistrictStateView.as_view(), name='district-state'),
]