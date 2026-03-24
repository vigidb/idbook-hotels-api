from django.contrib import admin
from django.urls import path, re_path, include
from django.conf import settings
from django.conf.urls.static import static
from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
    TokenVerifyView,
)

from IDBOOKAPI.img_kit import ImagekitioService
from apps.authentication.viewsets import homepage
from apps.org_resources.urls import router as org_resources_router
from apps.org_managements.urls import router as org_managements_router
from apps.holiday_package.urls import router as holiday_package_router
from apps.customer.urls import router as customer_router
from apps.coupons.urls import router as coupons_router
from apps.booking.urls import router as booking_router
from apps.hotels.urls import router as hotels_router
from apps.vehicle_management.urls import router as vehicle_router
from apps.log_management.urls import router as log_router
from apps.analytics.urls import router as analytics_router
from apps.messaging.urls import router as messaging_router


schema_view = get_schema_view(
    openapi.Info(
        title="IDBOOK APIs",
        default_version="v1",
        description=(
            "IDBOOKAPI APIs: All APIs for web application, Android/iOS application.\n\n"
            "Authentication in Swagger (`/api/v1/docs/swagger/`):\n"
            "1. Generate JWT token from `POST /api/v1/auth/token/` with your credentials.\n"
            "2. Copy the `access` token from the response.\n"
            "3. Click the `Authorize` button in Swagger UI.\n"
            "4. In `Bearer`, enter: `Bearer <access_token>` and click `Authorize`.\n"
            "5. Call protected APIs. Re-authorize after token expiry."
        ),
        terms_of_service="https://www.google.com/policies/terms/",
        contact=openapi.Contact(email="contact@idbookhotels.com"),
        license=openapi.License(name="BSD License"),
    ),
    public=True,
    permission_classes=([permissions.AllowAny]),
)

# Dedicated schema for authentication/user onboarding flows only
schema_view_auth = get_schema_view(
    openapi.Info(
        title="IDBOOK Auth & User Flows",
        default_version="v1",
        description=(
            "Focused documentation for authentication and user onboarding flows:\n"
            "- Username/password login\n"
            "- OTP login/signup\n"
            "- Google login/signup\n"
            "- Password reset & profile endpoints"
        ),
        contact=openapi.Contact(email="contact@idbookhotels.com"),
        license=openapi.License(name="BSD License"),
    ),
    public=True,
    permission_classes=([permissions.AllowAny]),
    patterns=[
        # Limit this schema to authentication-related URLs under /api/v1/auth/
        re_path("api/v1/", include("apps.authentication.urls")),
    ],
)

# Dedicated schema for Messaging & Campaign APIs
schema_view_messaging = get_schema_view(
    openapi.Info(
        title="IDBOOK Messaging & Campaign APIs",
        default_version="v1",
        description=(
            "Customer Engagement & Messaging Automation System.\n\n"
            "Authentication requirement:\n"
            "- Step 0: Obtain a JWT access token using /api/v1/auth/token/ as a BUSINESS group user.\n"
            "- Include `Authorization: Bearer <token>` in all subsequent requests.\n\n"
            "Recommended flow:\n"
            "1. Upload or create Contacts (B2C, Corporate, Agents, Hoteliers, etc.).\n"
            "2. Configure Email/SMS templates (marketing-focused).\n"
            "3. Create a Campaign (target group + filters like city, country).\n"
            "4. Add one or more Campaign Steps (email/SMS, template, delays in hours/days/weeks).\n"
            "5. Schedule the campaign or send immediately.\n"
            "6. Monitor campaign status and message logs.\n\n"
            "This documentation focuses on messaging-related endpoints under /api/v1/messaging/ "
            "and the login endpoint under /api/v1/auth/token/ to make it easy to understand, "
            "test, and iterate on campaigns in the correct order."
        ),
        contact=openapi.Contact(email="contact@idbookhotels.com"),
        license=openapi.License(name="BSD License"),
    ),
    public=True,
    permission_classes=([permissions.AllowAny]),
    patterns=[
        # Include auth token endpoints so users can authenticate first
        re_path("api/v1/auth/", include("apps.authentication.urls")),
        # Include the messaging router URLs so drf_yasg can introspect endpoints
        re_path("api/v1/messaging/", include(messaging_router.urls)),
    ],
)

urlpatterns = [
    path("", homepage, name="welcome"),
    path("api/v1/upload-file/", ImagekitioService.as_view(), name="imagekitio service"),
    # admin
    re_path("admin/", admin.site.urls),
    # authentication
    re_path("api/v1/", include("apps.authentication.urls")),
    # administrator (includes router URLs)
    re_path("api/v1/administrator/", include("apps.administrator.urls")),
    # holiday_package
    re_path("api/v1/holiday-package/", include("apps.holiday_package.urls")),
    # org_resources
    re_path("api/v1/org-resources/", include("apps.org_resources.urls")),
    # include routers (administrator router is now included in apps.administrator.urls)
    re_path("api/v1/org-resources/", include(org_resources_router.urls)),
    re_path("api/v1/org-managements/", include(org_managements_router.urls)),
    re_path("api/v1/holiday-package/", include(holiday_package_router.urls)),
    re_path("api/v1/customer/", include(customer_router.urls)),
    re_path("api/v1/coupons/", include(coupons_router.urls)),
    re_path("api/v1/booking/", include("apps.booking.urls")),
    # Unified Razorpay webhook (single endpoint for all payment types)
    re_path("api/v1/payment-gateways/", include("apps.payment_gateways.urls")),
    re_path("api/v1/hotels/", include(hotels_router.urls)),
    re_path("api/v1/vehcile-management/", include(vehicle_router.urls)),
    re_path("api/v1/log-management/", include(log_router.urls)),
    re_path("api/v1/analytics/", include(analytics_router.urls)),
    re_path("api/v1/messaging/", include(messaging_router.urls)),
    re_path("api/v1/flights/", include("apps.flights.urls")),
    re_path("api/v1/socket-com/", include("apps.socket_com.urls")),
    # JWT token authentication
    # order is important
    re_path(
        "api/v1/auth/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"
    ),
    re_path(
        "api/v1/auth/token/verify/", TokenVerifyView.as_view(), name="token_verify"
    ),
    re_path(
        "api/v1/auth/token/", TokenObtainPairView.as_view(), name="token_obtain_pair"
    ),
    # re_path('api/v1/auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    # re_path('api/v1/auth/token/verify/', TokenVerifyView.as_view(), name='token_verify'),
    # API documentation (ReDoc + Swagger under /api/v1/docs/)
    re_path(
        r"^api/v1/docs/swagger/$",
        schema_view.with_ui("swagger", cache_timeout=0),
        name="schema-swagger-ui",
    ),
    re_path(
        r"^api/v1/docs/(?P<format>\.json|\.yaml)$",
        schema_view.without_ui(cache_timeout=0),
        name="schema-json",
    ),
    re_path(
        r"^api/v1/docs/$",
        schema_view.with_ui("redoc", cache_timeout=0),
        name="schema-redoc",
    ),
    # Auth-focused documentation (separate Swagger/ReDoc for user flows)
    re_path(
        r"^api/v1/docs/auth/swagger/$",
        schema_view_auth.with_ui("swagger", cache_timeout=0),
        name="schema-auth-swagger-ui",
    ),
    re_path(
        r"^api/v1/docs/auth/$",
        schema_view_auth.with_ui("redoc", cache_timeout=0),
        name="schema-auth-redoc",
    ),
    # Messaging-focused documentation (separate Swagger/ReDoc for messaging flows)
    re_path(
        r"^api/v1/docs/messaging/swagger/$",
        schema_view_messaging.with_ui("swagger", cache_timeout=0),
        name="schema-messaging-swagger-ui",
    ),
    re_path(
        r"^api/v1/docs/messaging/$",
        schema_view_messaging.with_ui("redoc", cache_timeout=0),
        name="schema-messaging-redoc",
    ),
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
