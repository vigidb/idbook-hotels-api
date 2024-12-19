from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from django.db.models import Q

CustomUser = get_user_model()


class EmailPasswordAuthBackend(ModelBackend):
    def authenticate(self, request=None, email=None, password=None, **kwargs):
        try:
            if not email:
                return None
            user = CustomUser.objects.get(Q(email=email))
            if user.check_password(password):
                return user
        except CustomUser.DoesNotExist:
            return None

