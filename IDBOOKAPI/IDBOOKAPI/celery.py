# celery.py
from celery import Celery
from django.conf import settings

# Create a Celery instance and configure it using the Django settings
app = Celery('apps.authentication')
app.config_from_object(settings, namespace='CELERY')
app.autodiscover_tasks(lambda: settings.INSTALLED_APPS)
