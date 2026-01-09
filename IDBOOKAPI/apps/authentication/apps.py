from django.apps import AppConfig


class AuthenticationConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.authentication"
    verbose_name = "Authentication & Authorization"

    def ready(self):
        # import apps.authentication.signals  # Import your signals module
        from . import signals
