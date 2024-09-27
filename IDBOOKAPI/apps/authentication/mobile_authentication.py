from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from django.db.models import Q

CustomUser = get_user_model()


class PhonePasswordAuthBackend(ModelBackend):
    def authenticate(self, request=None, mobile_number=None, password=None, **kwargs):
        try:
            if not mobile_number:
                return None
            user = CustomUser.objects.get(Q(mobile_number=mobile_number))
            if user.check_password(password):
                return user
        except CustomUser.DoesNotExist:
            return None

