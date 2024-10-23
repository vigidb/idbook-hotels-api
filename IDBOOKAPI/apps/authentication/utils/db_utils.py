from django.contrib.auth.models import Group
from apps.authentication.models import Role

def get_group_by_name(name):
    #CORPORATE-GRP
    group = Group.objects.filter(name=name).first()
    return group

def get_role_by_name(name):
    role = Role.objects.filter(name=name).first()
    return role
