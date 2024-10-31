import os
import environ
from pathlib import Path
from datetime import timedelta

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env()
environ.Env.read_env()

if env('DEBUG'):
    BASE_URL = env('BASE_URL')
else:
    BASE_URL = env('BASE_URL_')
# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/4.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
# SECRET_KEY = 'django-insecure-pr#pwd&(i6#4n%$+regb8ddufbf8k5mb$^e!$jz*t)ny)y%_f='
SECRET_KEY = env('SECRET_KEY')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = env('DEBUG')

ALLOWED_HOSTS = [env('ALLOWED_HOSTS')]

IMAGEKIT_PRIVATE_KEY = env('IMAGEKIT_PRIVATE_KEY')
IMAGEKIT_PUBLIC_KEY = env('IMAGEKIT_PUBLIC_KEY')
IMAGEKIT_ENDPOINT = env('IMAGEKIT_ENDPOINT')
# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # third party apps
    'rest_framework',
    'rest_framework.authtoken',
    'rest_framework_simplejwt',
    # 'rest_framework_tracking',
    'django_filters',
    'storages',
    'corsheaders',
    'drf_yasg',
    'imagekit',
    # 'django_faker',
    # our apps
    # 'api',
    'apps.administrator',
    'apps.authentication',
    'apps.booking',
    'apps.coupons',
    'apps.customer',
    'apps.org_resources',
    'apps.org_managements',
    'apps.hotels',
    'apps.holiday_package',
    'apps.vehicle_management',
    'apps.log_management',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'IDBOOKAPI.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'templates')],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'IDBOOKAPI.wsgi.application'


# Database
# https://docs.djangoproject.com/en/4.2/ref/settings/#databases

# DATABASES = {
#     'default': {
#         'ENGINE': 'django.db.backends.sqlite3',
#         'NAME': BASE_DIR / 'db.sqlite3',
#     }
# }

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': env('DATABASE_NAME'),
        'USER': env('DATABASE_USER'),
        'PASSWORD': env('DATABASE_PASSWORD'),
        'HOST': env('DATABASE_HOST'),
        'PORT': env('DATABASE_PORT'),
    }
 }

# Password validation
# https://docs.djangoproject.com/en/4.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/4.2/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'Asia/Kolkata'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/4.2/howto/static-files/

# Default primary key field type
# https://docs.djangoproject.com/en/4.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

CORS_ORIGIN_ALLOW_ALL = True
# CORS_ALLOW_ALL_ORIGINS = True
# CORS_ALLOWED_ORIGINS = [
#     "http://127.0.0.1:3000",
#     "https://sub.example.com",
#     "http://localhost:3000",
#     "http://127.0.0.1:9000",
#     "http://139.59.15.128",
#     "http://127.0.0.1:9000",
# ]

AUTHENTICATION_BACKENDS = [
    'apps.authentication.mobile_authentication.PhonePasswordAuthBackend',
    'django.contrib.auth.backends.ModelBackend',
]

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework.authentication.BasicAuthentication',  # enables simple command line authentication
        'rest_framework_simplejwt.authentication.JWTAuthentication',
        # 'rest_framework.authentication.SessionAuthentication',
        # 'rest_framework.authentication.TokenAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': [
        # 'rest_framework.permissions.IsAdminUser'
        # 'rest_framework.permissions.DjangoModelPermissionsOrAnonReadOnly',
    ],
    'DEFAULT_RENDERER_CLASSES': (
        'rest_framework.renderers.JSONRenderer',
    ),
    'DEFAULT_METADATA_CLASS': 'rest_framework.metadata.SimpleMetadata',
    'DEFAULT_FILTER_BACKENDS': ['django_filters.rest_framework.DjangoFilterBackend'],
    # 'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.LimitOffsetPagination',
    # 'PAGE_SIZE': 10
}

STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'static/')
##MEDIA_URL = '/media/'
##MEDIA_ROOT = os.path.join(BASE_DIR, 'media/')

PUBLIC_MEDIA_LOCATION = 'media'
MEDIA_URL = f'https://idbookhotels.s3.eu-north-1.amazonaws.com/{PUBLIC_MEDIA_LOCATION}/'
DEFAULT_FILE_STORAGE = 'IDBOOKAPI.storage_backend.PublicMediaStorage'

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

basic_auth_key = env('AUTH_KEY')

AUTH_USER_MODEL = 'authentication.User'
LOGIN_REDIRECT_URL = 'logout'
LOGOUT_REDIRECT_URL = 'login'


FRONTEND_URL = env('FRONTEND_URL')
# celery and redis server url
CELERY_BROKER_URL = env('CELERY_BROKER_URL')
CELERY_RESULT_BACKEND = env('CELERY_BROKER_URL')
CELERY_ACCEPT_CONTENT = ['application/json']
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TASK_SERIALIZER = 'json'
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
# email configuration
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = env("EMAIL_HOST")
EMAIL_PORT = env("EMAIL_PORT")
EMAIL_USE_TLS = env("EMAIL_USE_TLS")
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL")
EMAIL_HOST_USER = env("NOREPLY_EMAIL")
EMAIL_HOST_PASSWORD = env("NOREPLY_PAASWORD")
CORPORATE_EMAIL = env("CORPORATE_EMAIL")

OTP_EXPIRY_MIN = int(env("OTP_EXPIRY_MIN"))



AWS_S3_URL = env("AWS_S3_URL")
AWS_ACCESS_KEY_ID = env("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = env("AWS_SECRET_ACCESS_KEY")
AWS_STORAGE_BUCKET_NAME = env("AWS_STORAGE_BUCKET_NAME")
AWS_S3_REGION_NAME = env("AWS_S3_REGION_NAME")

COUNTRY_API_KEY = env("COUNTRY_API_KEY")

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
    "AUTH_TOKEN_CLASSES": ("rest_framework_simplejwt.tokens.AccessToken",),
    "TOKEN_TYPE_CLAIM": "token_type",
    "JTI_CLAIM": "jti",
}
# FAKER_LOCALE = None
# FAKER_PROVIDERS = None
# WKHTMLTOPDF_CMD='/usr/local/bin/wkhtmltopdf'
