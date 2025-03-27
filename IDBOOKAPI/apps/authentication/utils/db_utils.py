from django.db.models import Q

from django.contrib.auth.models import Group
from apps.authentication.models import Role
from apps.authentication.models import User, UserOtp
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

def create_user(user_details, customer_details=None):
    user = User.objects.create(**user_details)
    if not customer_details:
        Customer.objects.create(user=user, active=True)
    else:
        customer_details['user_id'] = user.id
        customer_details['active'] = True
        Customer.objects.create(**customer_details)
    return user

def create_email_otp(otp, to_email, otp_for):
    # delete any previous otp for the user account
    UserOtp.objects.filter(user_account=to_email).delete()
    # save otp
    UserOtp.objects.create(
        otp=otp, otp_type='EMAIL',
        user_account=to_email, otp_for=otp_for)

def create_mobile_otp(otp, mobile_number, otp_for):
    # delete any previous otp for the user account
    UserOtp.objects.filter(user_account=mobile_number).delete()
    # save otp
    UserOtp.objects.create(
        otp=otp, otp_type='MOBILE',
        user_account=mobile_number,
         otp_for=otp_for)

def get_userid_list(username, group=None):
    user_objs = User.objects.filter(
        Q(email=username)|Q(mobile_number=username))
    if group:
        user_objs = user_objs.filter(groups=group)
        
    user_objs = user_objs.values(
        'id', 'email', 'mobile_number')
    return user_objs

def is_role_exist(user_objs, role):
    is_exist = user_objs.filter(roles=role).exists()
    return is_exist
    

def get_user_details(user_id, username):
    """ need to remove the user id"""
    user_detail = User.objects.filter(id=user_id).filter(
        Q(email=username)|Q(mobile_number=username)).first()
    return user_detail

def get_group_based_user_details(group, username):
    user_detail = User.objects.filter(groups=group, is_active=True).filter(
        Q(email=username)|Q(mobile_number=username)).first()
    return user_detail



def get_user_otp_details(email, mobile_number, otp):
    user_otp_detail = UserOtp.objects.filter(
        otp=otp, otp_for='SIGNUP').filter(
            Q(user_account=email)|Q(user_account=mobile_number)).first()
    return user_otp_detail

def check_email_otp(email, otp, otp_for):
    user_otp = UserOtp.objects.filter(
        user_account=email, otp=otp,
        otp_for=otp_for).first()
    return user_otp

def check_mobile_otp(mobile_number, otp, otp_for):
    user_otp = UserOtp.objects.filter(
        user_account=mobile_number, otp=otp,
        otp_for=otp_for).first()
    return user_otp
    
    
    
    

    
