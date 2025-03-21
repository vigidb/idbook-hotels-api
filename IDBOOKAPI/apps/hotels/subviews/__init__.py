from rest_framework import viewsets
from rest_framework import status
from rest_framework.decorators import action

from django.conf import settings

from IDBOOKAPI.mixins import StandardResponseMixin, LoggingMixin
from IDBOOKAPI.utils import paginate_queryset, validate_date

from rest_framework.permissions import IsAuthenticated, AllowAny

