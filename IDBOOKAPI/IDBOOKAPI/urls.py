from django.contrib import admin
from django.urls import path, re_path, include
from django.conf import settings
from django.conf.urls.static import static
from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from rest_framework_simplejwt.views import (TokenObtainPairView, TokenRefreshView, TokenVerifyView)

from IDBOOKAPI.img_kit import ImagekitioService
from apps.authentication.viewsets import homepage
from apps.administrator.urls import router as administrator_router
from apps.org_resources.urls import router as org_resources_router
from apps.org_managements.urls import router as org_managements_router
from apps.holiday_package.urls import router as holiday_package_router
from apps.customer.urls import router as customer_router
from apps.coupons.urls import router as coupons_router
from apps.booking.urls import router as booking_router
from apps.hotels.urls import router as hotels_router
from apps.vehicle_management.urls import router as vehicle_router
from apps.log_management.urls import router as log_router


schema_view = get_schema_view(
   openapi.Info(
      title="IDBOOK APIs",
      default_version='v1',
      description="IDBOOKAPI APIs: All apis for web application, android/IOS application",
      terms_of_service="https://www.google.com/policies/terms/",
      contact=openapi.Contact(email="contact@idbookhotels.com"),
      license=openapi.License(name="BSD License"),
   ),
   public=True,
   permission_classes=([permissions.AllowAny]),
)

urlpatterns = [
    path('', homepage, name="welcome"),
    path('api/v1/upload-file/', ImagekitioService.as_view(), name="imagekitio service"),
    # admin
    re_path('admin/', admin.site.urls),
    # authentication
    re_path('api/v1/', include('apps.authentication.urls')),
    # administrator
    re_path('api/v1/administrator/', include('apps.administrator.urls')),
    # holiday_package
    re_path('api/v1/holiday-package/', include('apps.holiday_package.urls')),
    # org_resources
    re_path('api/v1/org-resources/', include('apps.org_resources.urls')),

    # include routers
    re_path('api/v1/administrator/', include(administrator_router.urls)),
    re_path('api/v1/org-resources/', include(org_resources_router.urls)),
    re_path('api/v1/org-managements/', include(org_managements_router.urls)),
    re_path('api/v1/holiday-package/', include(holiday_package_router.urls)),
    re_path('api/v1/customer/', include(customer_router.urls)),
    re_path('api/v1/coupons/', include(coupons_router.urls)),
    re_path('api/v1/booking/', include(booking_router.urls)),
    re_path('api/v1/hotels/', include(hotels_router.urls)),
    re_path('api/v1/vehcile-management/', include(vehicle_router.urls)),
    re_path('api/v1/log-management/', include(log_router.urls)),

    # JWT token authentication
    # order is important
    re_path('api/v1/auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    re_path('api/v1/auth/token/verify/', TokenVerifyView.as_view(), name='token_verify'),
    re_path('api/v1/auth/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    # re_path('api/v1/auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    # re_path('api/v1/auth/token/verify/', TokenVerifyView.as_view(), name='token_verify'),

    # API documents
    re_path(r'^api/v1/docs2/(?P<format>\.json|\.yaml)$', schema_view.without_ui(cache_timeout=0), name='schema-json'),
    re_path(r'^api/v1/docs2/$', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    re_path(r'^api/v1/docs/$', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),

]
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# error handler
# handler400 = views.error_400
# handler403 = views.error_403
# handler404 = views.error_404
# handler413 = views.error_413
# handler500 = views.error_500
