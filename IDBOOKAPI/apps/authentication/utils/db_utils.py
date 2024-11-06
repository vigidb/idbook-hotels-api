from django.contrib.auth.models import Group
from apps.authentication.models import Role
from apps.authentication.models import User

def get_group_by_name(name):
    #CORPORATE-GRP
    group = Group.objects.filter(name=name).first()
    return group

def get_role_by_name(name):
    role = Role.objects.filter(name=name).first()
    return role

def get_user_by_referralcode(refferal_code):
    if refferal_code:
        user = User.objects.filter(referral=refferal_code).first()
        return user
    else:
        return None
