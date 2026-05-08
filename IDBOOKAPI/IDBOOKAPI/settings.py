import os
import environ
from pathlib import Path
from datetime import timedelta

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env()
environ.Env.read_env()

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = env.bool("DEBUG", default=False)

# Base URL for the API (used on homepage, docs links, etc.). Defaults to localhost.
if DEBUG:
    BASE_URL = env("BASE_URL", default="http://localhost:8000")
else:
    BASE_URL = env("BASE_URL_", default="https://api.idbookhotels.com")

# Ensure BASE_URL has a scheme (http/https) so links work
if BASE_URL and not BASE_URL.startswith(("http://", "https://")):
    BASE_URL = ("https://" if "localhost" not in BASE_URL and "127.0.0.1" not in BASE_URL else "http://") + BASE_URL.rstrip("/")
# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/4.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
# SECRET_KEY = 'django-insecure-pr#pwd&(i6#4n%$+regb8ddufbf8k5mb$^e!$jz*t)ny)y%_f='
SECRET_KEY = env("SECRET_KEY")

FLIGHT_API_DEBUG = bool(env("FLIGHT_API_DEBUG", default=False)) or False
ALLOWED_HOSTS = [env("ALLOWED_HOSTS")]
ENVIRONMENT = env("ENVIRONMENT")

# Hotelier Notification Settings
# Disable email and SMS notifications to hoteliers in non-production environments
# to avoid disturbing hoteliers during testing/development
# Set HOTELIER_NOTIFICATIONS_ENABLED=True in .env to enable, defaults based on ENVIRONMENT
HOTELIER_NOTIFICATIONS_ENABLED = env.bool(
    "HOTELIER_NOTIFICATIONS_ENABLED",
    default=(ENVIRONMENT == "production")
)
# Hotelier receipt PDF email (can enable in dev without HOTELIER_NOTIFICATIONS_ENABLED / SMS)
HOTELIER_RECEIPT_EMAIL_ENABLED = env.bool(
    "HOTELIER_RECEIPT_EMAIL_ENABLED",
    default=HOTELIER_NOTIFICATIONS_ENABLED,
)

IMAGEKIT_PRIVATE_KEY = env("IMAGEKIT_PRIVATE_KEY")
IMAGEKIT_PUBLIC_KEY = env("IMAGEKIT_PUBLIC_KEY")
IMAGEKIT_ENDPOINT = env("IMAGEKIT_ENDPOINT")
# Application definition

INSTALLED_APPS = [
    "daphne",  # Must be first for ASGI/WebSocket support
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.postgres",
    # third party apps
    "rest_framework",
    "rest_framework.authtoken",
    "rest_framework_simplejwt",
    # 'rest_framework_tracking',
    "django_filters",
    "storages",
    "corsheaders",
    "drf_yasg",
    "imagekit",
    "django_celery_beat",
    "django_celery_results",
    # 'django_faker',
    # our apps
    # 'api',
    "apps.administrator",
    "apps.authentication",
    "apps.booking",
    "apps.coupons",
    "apps.customer",
    "apps.org_resources",
    "apps.org_managements",
    "apps.hotels",
    "apps.holiday_package",
    "apps.vehicle_management",
    "apps.flights",
    "apps.log_management",
    "apps.analytics",
    "apps.payment_gateways",
    "apps.socket_com",  # WebSocket support for real-time updates
    # customer engagement & messaging (contacts, campaigns, templates)
    "apps.messaging",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "IDBOOKAPI.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [os.path.join(BASE_DIR, "templates")],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "IDBOOKAPI.company_info.company_context",
            ],
            "libraries": {
                "dictionary_filter": "templatetags.dictionary_filter",
                "company_tags": "templatetags.company_tags",
            },
        },
    },
]

ASGI_APPLICATION = "IDBOOKAPI.asgi.application"
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            # Same Redis host as Celery is fine; use a different DB index in the URL if needed.
            "hosts": [env("REDIS_CHANNEL_LAYER_URL", default="redis://127.0.0.1:6379/0")],
        },
    },
}

WSGI_APPLICATION = "IDBOOKAPI.wsgi.application"


# Database
# https://docs.djangoproject.com/en/4.2/ref/settings/#databases

# DATABASES = {
#     'default': {
#         'ENGINE': 'django.db.backends.sqlite3',
#         'NAME': BASE_DIR / 'db.sqlite3',
#     }
# }

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env("DATABASE_NAME"),
        "USER": env("DATABASE_USER"),
        "PASSWORD": env("DATABASE_PASSWORD"),
        "HOST": env("DATABASE_HOST"),
        "PORT": env("DATABASE_PORT"),
    }
}

# API / view caching (optional). Use a dedicated Redis logical DB (see README examples).
_redis_cache_url = env("REDIS_CACHE_URL", default="").strip()
if _redis_cache_url:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": _redis_cache_url,
            "KEY_PREFIX": env("CACHE_KEY_PREFIX", default="idbook"),
            "TIMEOUT": env.int("CACHE_DEFAULT_TIMEOUT", default=300),
        }
    }
else:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "idbook-locmem",
        }
    }

# Password validation
# https://docs.djangoproject.com/en/4.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


# Internationalization
# https://docs.djangoproject.com/en/4.2/topics/i18n/

LANGUAGE_CODE = "en-us"

TIME_ZONE = "Asia/Kolkata"

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/4.2/howto/static-files/

# Default primary key field type
# https://docs.djangoproject.com/en/4.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# CORS Configuration
# For development: Allow all origins
CORS_ALLOW_ALL_ORIGINS = True  # Modern way (replaces CORS_ORIGIN_ALLOW_ALL)

# Allow credentials (cookies, authorization headers)
CORS_ALLOW_CREDENTIALS = True

# Allow all methods
CORS_ALLOW_METHODS = [
    "DELETE",
    "GET",
    "OPTIONS",
    "PATCH",
    "POST",
    "PUT",
]

# Allow all headers
CORS_ALLOW_HEADERS = [
    "accept",
    "accept-encoding",
    "authorization",
    "content-type",
    "dnt",
    "origin",
    "user-agent",
    "x-csrftoken",
    "x-requested-with",
]

# For production, use specific origins instead:
# CORS_ALLOW_ALL_ORIGINS = False
# CORS_ALLOWED_ORIGINS = [
#     "http://localhost:3000",
#     "http://localhost:3001",
#     "http://127.0.0.1:3000",
#     "http://127.0.0.1:3001",
#     # Add your production frontend URLs here
# ]

AUTHENTICATION_BACKENDS = [
    "apps.authentication.mobile_authentication.PhonePasswordAuthBackend",
    "django.contrib.auth.backends.ModelBackend",
]

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        # "rest_framework.authentication.BasicAuthentication",  # enables simple command line authentication
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        # 'rest_framework.authentication.SessionAuthentication',
        # 'rest_framework.authentication.TokenAuthentication',
    ),
    "DEFAULT_PERMISSION_CLASSES": [
        # 'rest_framework.permissions.IsAdminUser'
        # 'rest_framework.permissions.DjangoModelPermissionsOrAnonReadOnly',
    ],
    "DEFAULT_RENDERER_CLASSES": ("rest_framework.renderers.JSONRenderer",),
    "DEFAULT_METADATA_CLASS": "rest_framework.metadata.SimpleMetadata",
    "DEFAULT_FILTER_BACKENDS": ["django_filters.rest_framework.DjangoFilterBackend"],
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": "100/hour",
        "user": "1000/hour",
        "switch_group": "10/min",  # Rate limit for group switching
        "login": "5/min",  # Rate limit for login attempts
        "coupon_validity": "60/min",
    },
    # 'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.LimitOffsetPagination',
    # 'PAGE_SIZE': 10
}

# drf-yasg (OpenAPI docs): avoid 500 when generating schema with django-filter and no coreapi.
# django-filter's get_schema_fields() requires coreapi, which can fail on Python 3.10+.
# Disabling filter inspectors lets /api/v1/docs/ and /api/v1/docs/swagger/ load; filter params won't appear in schema.
# To get filter params in the schema, install: pip install drf-yasg[coreapi] (or coreapi + coreschema).
SWAGGER_SETTINGS = {
    "DEFAULT_FILTER_INSPECTORS": [],
    # Disable Django session-based auth buttons in Swagger; use JWT or Basic instead
    "USE_SESSION_AUTH": False,
    # Keep authorized token in Swagger UI between page refreshes.
    # (Swagger UI can't reliably auto-inject a token for security reasons.)
    "PERSIST_AUTH": True,
    "SECURITY_DEFINITIONS": {
        "Bearer": {
            "type": "apiKey",
            "name": "Authorization",
            "in": "header",
            "description": "JWT from POST /api/v1/auth/token/. Example: Bearer <access_token>",
        },
        "Basic": {
            "type": "basic",
            "description": "HTTP Basic auth (same credentials as Django admin if enabled).",
        },
    },
    # Default to Bearer globally; you can still authorize with Basic in Swagger's Authorize dialog
    "SECURITY_REQUIREMENTS": [{"Bearer": []}],
}

STATIC_URL = "/static/"
STATIC_ROOT = os.path.join(BASE_DIR, "static/")
##MEDIA_URL = '/media/'
##MEDIA_ROOT = os.path.join(BASE_DIR, 'media/')

PUBLIC_MEDIA_LOCATION = "media"
MEDIA_URL = f"https://idbookhotels.s3.eu-north-1.amazonaws.com/{PUBLIC_MEDIA_LOCATION}/"
DEFAULT_FILE_STORAGE = "IDBOOKAPI.storage_backend.PublicMediaStorage"

# Default primary key field type
# https://docs.djangoproject.com/en/3.2/ref/settings/#default-auto-field

# CSRF_COOKIE_SECURE = env('CSRF_COOKIE_SECURE')
# SESSION_COOKIE_SECURE = env('SESSION_COOKIE_SECURE')
# X_FRAME_OPTIONS = env('X_FRAME_OPTIONS')
# SECURE_HSTS_SECONDS = env('SECURE_HSTS_SECONDS')
# SECURE_HSTS_INCLUDE_SUBDOMAINS = env('SECURE_HSTS_INCLUDE_SUBDOMAINS')
# SECURE_HSTS_PRELOAD = env('SECURE_HSTS_PRELOAD')
# SECURE_CONTENT_TYPE_NOSNIFF = env('SECURE_CONTENT_TYPE_NOSNIFF')
# SECURE_BROWSER_XSS_FILTER = env('SECURE_BROWSER_XSS_FILTER')
# SECURE_SSL_REDIRECT = env('SECURE_SSL_REDIRECT')
# PREPEND_WWW = env('PREPEND_WWW')

basic_auth_key = env("AUTH_KEY")

AUTH_USER_MODEL = "authentication.User"
LOGIN_REDIRECT_URL = "logout"
LOGOUT_REDIRECT_URL = "login"


FRONTEND_URL = env("FRONTEND_URL")
INV_FE_URL = env("INV_FE_URL")
# celery and redis server url
CELERY_BROKER_URL = env("CELERY_BROKER_URL")
# Tasks with no explicit route go here (dev vs prod queue names; override via env if needed).
_is_worker_dev_queues = str(ENVIRONMENT or "").strip().lower() in {
    "dev",
    "development",
    "local",
    "test",
}
CELERY_TASK_DEFAULT_QUEUE = env(
    "CELERY_TASK_DEFAULT_QUEUE",
    default=(
        "dev-general-queue" if _is_worker_dev_queues else "general-queue"
    ),
)
# Keep Redis as broker; store task execution metadata in DB for admin observability.
CELERY_RESULT_BACKEND = "django-db"
# Use DB-backed beat scheduler so periodic tasks are visible/manageable in admin.
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"
CELERY_ACCEPT_CONTENT = ["application/json"]
CELERY_RESULT_SERIALIZER = "json"
CELERY_TASK_SERIALIZER = "json"
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
CELERY_TIMEZONE = TIME_ZONE
CELERY_ENABLE_UTC = True
CELERY_TASK_TRACK_STARTED = True
CELERY_RESULT_EXTENDED = True
# Performance/cost guardrails for production workers.
CELERY_WORKER_PREFETCH_MULTIPLIER = env.int("CELERY_WORKER_PREFETCH_MULTIPLIER", default=1)
CELERY_WORKER_MAX_TASKS_PER_CHILD = env.int("CELERY_WORKER_MAX_TASKS_PER_CHILD", default=100)
CELERY_TASK_TIME_LIMIT = env.int("CELERY_TASK_TIME_LIMIT", default=900)
CELERY_TASK_SOFT_TIME_LIMIT = env.int("CELERY_TASK_SOFT_TIME_LIMIT", default=840)
# Keep False globally; opt-in per idempotent task if needed.
CELERY_TASK_ACKS_LATE = env.bool("CELERY_TASK_ACKS_LATE", default=False)
# email configuration
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = env("EMAIL_HOST")
EMAIL_PORT = env("EMAIL_PORT")
EMAIL_USE_TLS = env("EMAIL_USE_TLS")
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL")
EMAIL_HOST_USER = env("NOREPLY_EMAIL")
EMAIL_HOST_PASSWORD = env("NOREPLY_PAASWORD")
CORPORATE_EMAIL = env("CORPORATE_EMAIL")

# Internal BCC for booking confirmation / hotelier receipt (ops inboxes)
INTERNAL_BOOKING_EMAIL_FLIGHT = env(
    "INTERNAL_BOOKING_EMAIL_FLIGHT", default="airlines@idbookhotels.com"
)
INTERNAL_BOOKING_EMAIL_HOTELS_OTHERS = env(
    "INTERNAL_BOOKING_EMAIL_HOTELS_OTHERS", default="bookings@idbookhotels.com"
)
INTERNAL_BOOKING_EMAIL_AGENTS = env(
    "INTERNAL_BOOKING_EMAIL_AGENTS", default="agents@idbookhotels.com"
)
INTERNAL_BOOKING_EMAIL_CORPORATES = env(
    "INTERNAL_BOOKING_EMAIL_CORPORATES", default="corporates@idbookhotels.com"
)
# Default business user (by email) for new Query records and query notification recipients
QUERY_DEFAULT_ASSIGNEE_EMAIL = env(
    "QUERY_DEFAULT_ASSIGNEE_EMAIL",
    default="booking@idbookhotels.com",
)
# BCC on any email sent directly to a hotelier/property contact
PARTNER_B2B_EMAIL = env(
    "PARTNER_B2B_EMAIL", default="partner.b2b@idbookhotels.com"
)

# Booking confirmation email footer (avoid hard-coded dummy contact lines in templates)
EMAIL_TEMPLATE_SUPPORT_EMAIL = env(
    "EMAIL_TEMPLATE_SUPPORT_EMAIL", default="support@idbookhotels.com"
)
EMAIL_TEMPLATE_SUPPORT_PHONE = env("EMAIL_TEMPLATE_SUPPORT_PHONE", default="")
EMAIL_TEMPLATE_COMPANY_LINE = env(
    "EMAIL_TEMPLATE_COMPANY_LINE", default="Idbook Hotels"
)
EMAIL_TEMPLATE_PRIVACY_URL = env(
    "EMAIL_TEMPLATE_PRIVACY_URL", default="https://www.idbookhotels.com/privacy-policy"
)
EMAIL_TEMPLATE_TERMS_URL = env(
    "EMAIL_TEMPLATE_TERMS_URL",
    default="https://www.idbookhotels.com/terms-and-conditions",
)

OTP_EXPIRY_MIN = int(env("OTP_EXPIRY_MIN"))

# OTP verification rate limit: max attempts before cooldown, and cooldown duration (minutes)
OTP_VERIFY_MAX_ATTEMPTS = int(env("OTP_VERIFY_MAX_ATTEMPTS", default=10))
OTP_VERIFY_COOLDOWN_MINUTES = int(env("OTP_VERIFY_COOLDOWN_MINUTES", default=30))


AWS_S3_URL = env("AWS_S3_URL")
AWS_ACCESS_KEY_ID = env("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = env("AWS_SECRET_ACCESS_KEY")
AWS_STORAGE_BUCKET_NAME = env("AWS_STORAGE_BUCKET_NAME")
AWS_S3_REGION_NAME = env("AWS_S3_REGION_NAME")
AWS_QUERYSTRING_AUTH = False

CDN = env("CDN")

COUNTRY_API_KEY = env("COUNTRY_API_KEY")
CALLBACK_URL = env("CALLBACK_URL")

# PHONE PAY
MERCHANT_ID = env("MERCHANT_ID")
SALT_KEY = env("SALT_KEY")
SALT_INDEX = env("SALT_INDEX")
PHONEPAY_URL = env("PHONEPAY_URL")
PHONEPAY_REFUND_URL = env("PHONEPAY_REFUND_URL")
PHONEPE_BASE_URL = env("PHONEPE_BASE_URL")

# PAYU
PAYU_URL = env("PAYU_URL")
PAYU_MERCH_URL = env("PAYU_MERCH_URL")
PAYU_SALT = env("PAYU_SALT")
PAYU_KEY = env("PAYU_KEY")

# FAST2SMS
FAST2SMS_APIKEY = env("FAST2SMS_APIKEY")
FAST_DLT_SENDER_ID = env("FAST_DLT_SENDER_ID")
FAST_MESSAGE_ID = env("FAST_MESSAGE_ID")

# AirIQ Flight API Configuration
AIRIQ_BASE_URL = env("AIRIQ_BASE_URL")
AIRIQ_AGENT_ID = env("AIRIQ_AGENT_ID", default="")
AIRIQ_USERNAME = env("AIRIQ_USERNAME")
AIRIQ_PASSWORD = env("AIRIQ_PASSWORD")
AIRIQ_API_VERSION = env("AIRIQ_API_VERSION", default="2.0")

# Razorpay Configuration
RAZORPAY_KEY_ID = env("RAZORPAY_KEY_ID", default="")
RAZORPAY_KEY_SECRET = env("RAZORPAY_KEY_SECRET", default="")
RAZORPAY_WEBHOOK_SECRET = env("RAZORPAY_WEBHOOK_SECRET", default="")

# PAGINATION_PAGE_SIZE = env_config("PAGINATION_PAGE_SIZE")
# NDR_EMAIL_HOST_USER = env_config("NDR_EMAIL_HOST_USER")
# NDR_EMAIL_HOST_PASSWORD = env_config("NDR_EMAIL_HOST_PASSWORD")
# NDR_HOST = env_config("NDR_HOST")

from .logger_dict import LOGGER_DICT

LOGGING = LOGGER_DICT

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(hours=12),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=1),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": False,
    "ALGORITHM": "HS256",
    "SIGNING_KEY": SECRET_KEY,
    "VERIFYING_KEY": None,
    "AUDIENCE": None,
    "ISSUER": None,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "AUTH_HEADER_NAME": "HTTP_AUTHORIZATION",
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
    "AUTH_TOKEN_CLASSES": ("apps.authentication.tokens.CustomAccessToken",),
    "TOKEN_TYPE_CLAIM": "token_type",
    "JTI_CLAIM": "jti",
}
# FAKER_LOCALE = None
# FAKER_PROVIDERS = None
# WKHTMLTOPDF_CMD='/usr/local/bin/wkhtmltopdf'
