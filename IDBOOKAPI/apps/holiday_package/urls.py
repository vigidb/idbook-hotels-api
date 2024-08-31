from django.urls import path
from rest_framework import routers
from apps.holiday_package.viewsets import *

router = routers.DefaultRouter()

router.register('tour-packages', TourPackageViewSet, basename='tour_packages')
router.register('tour-accommodations', AccommodationViewSet, basename='tour_accommodations')
router.register('tour-inclusions-exclusions', InclusionExclusionViewSet, basename='tour_inclusions-exclusions')
router.register('tour-vehicles', VehicleViewSet, basename='tour_vehicles')
router.register('tour-daily-plans', DailyPlanViewSet, basename='tour_daily_plans')
router.register('tour-bank-details', TourBankDetailViewSet, basename='tour_bank_details')
router.register('customer-tour-enquiries', CustomerTourEnquiryViewSet, basename='customer_tour_enquiries')

urlpatterns = [
    # path('tour-packages/<int:pk>/', render_tour_package_detail, name='tour_package_detail'),
    # path('tour_package/create/', TourPackageCreateView.as_view(), name='tour_package_create'),
    # path('pdf_view/', pdf_view, name='pdf_view'),
    # path('generate_multipage_pdf/', generate_multipage_pdf, name='generate_multipage_pdf'),
    # path('tour-package-detail/', TourPackageDetailView.as_view(), name='tour_package_detail'),
    path('tour-package-detail/<int:id>', TourPackageDetailView.as_view(), name='tour_package_detail_with_id'),

]