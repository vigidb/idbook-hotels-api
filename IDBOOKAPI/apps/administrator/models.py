from django.db import models
from django.db.models import Q
from apps.authentication.models import Permission


available_permission_queryset = Permission.objects.exclude(
            Q(codename__icontains='delete_')).exclude(
            Q(codename__icontains='logentry')).exclude(
            Q(codename__icontains='group')).exclude(
            Q(codename__icontains='logentry')).exclude(
            Q(codename__icontains='permission')).exclude(
            Q(codename__icontains='token')).exclude(
            Q(codename__icontains='tokenproxy')).exclude(
            Q(codename__icontains='session')).exclude(
            Q(codename__icontains='contenttype'))

available_permission_ids = available_permission_queryset.values_list('id', flat=True)
