from django.contrib.auth.models import Group
from apps.authentication.models import Role
from apps.authentication.models import User
from apps.customer.models import Customer

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

def update_user_first_booking(user_id):
    if user_id:
        User.objects.filter(id=user_id).update(first_booking=True)

def get_user_from_email(email):
    user = User.objects.filter(email=email).first()
    return user

def create_user(user_details):
    user = User.objects.create(**user_details)
    Customer.objects.create(user=user, active=True)
    return user
