from django.apps import AppConfig


class SocketComConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.socket_com"
    
    def ready(self):
        """Import signals when app is ready"""
        from . import signals  # noqa