import requests, json
# authentication utils
from apps.authentication.utils import db_utils
from apps.authentication.models import User
from apps.authentication.tasks import (
    send_email_task, send_mobile_otp_task)

from django.conf import settings

from rest_framework_simplejwt.tokens import RefreshToken

def user_representation(user, refresh_token=None):
    
    profile_picture = ''
    customer_profile = user.customer_profile.last()
    if customer_profile:
        if customer_profile.profile_picture:
            profile_picture = settings.MEDIA_URL + str(customer_profile.profile_picture)
        employee_id = customer_profile.employee_id


    user_roles = [uroles for uroles in user.roles.values('id','name')]
    user_groups = [ugrps for ugrps in user.groups.values('id', 'name')]
        

    user_data = {'id': user.id, 'mobile_number': user.mobile_number if user.mobile_number else '',
                 'email': user.email if user.email else '', 'name': user.get_full_name(),
                 'groups': user_groups, 'roles': user_roles, 'permissions': [],
                 'category': user.category, 'profile_picture':profile_picture,
                 'business_id': user.business_id if user.business_id else '',
                 'company_id' : user.company_id if user.company_id else '',
                 'default_group': user.default_group,
                 'is_active': user.is_active}

    if refresh_token:
        data = {'refreshToken': str(refresh_token), 'accessToken': str(refresh_token.access_token),
                'expiresIn': 0, 'user': user_data}

        return data

    return user_data

def generate_refresh_token(user):
    refresh = RefreshToken.for_user(user)
    data = user_representation(user, refresh_token=refresh)

    return data

def generate_refresh_access_token(user):
    refresh = RefreshToken.for_user(user)
    return str(refresh), str(refresh.access_token)

def check_mobile_exist_for_group(mobile_number, grp):
    check_mobile_existing_user = User.objects.filter(
        mobile_number=mobile_number, groups=grp).first()

    return check_mobile_existing_user

def check_email_exist_for_group(email, group_name):
    user = User.objects.filter(email=email).first()
    if user:
        group_list = list(user.groups.values_list('name', flat=True))
        if group_name in group_list:
            return user
        
    return None

def add_group_based_on_signup(user, group_name):
    grp, role = None, None
    
    if group_name == 'FRANCHISE-GRP':
        grp = db_utils.get_group_by_name('FRANCHISE-GRP')
        role = db_utils.get_role_by_name('FRANCH-ADMIN')
        user.default_group = 'FRANCHISE-GRP'
    elif group_name == 'HOTELIER-GRP':
        grp = db_utils.get_group_by_name('HOTELIER-GRP')
        role = db_utils.get_role_by_name('HTLR-ADMIN')
        user.default_group = 'HOTELIER-GRP'
    else:
        grp = db_utils.get_group_by_name('B2C-GRP')
        role = db_utils.get_role_by_name('B2C-CUST')
        user.default_group = 'B2C-GRP'
        user.category = 'B-CUST'

    if grp:
        user.groups.add(grp)
    if role:
        user.roles.add(role)

    user.is_active = True
    user.save()

    return user

def add_group_for_guest_user(user):
    grp = db_utils.get_group_by_name('B2C-GRP')
    role = db_utils.get_role_by_name('B2C-GUEST')
    user.default_group = 'B2C-GRP'

    if grp:
        user.groups.add(grp)
    if role:
        user.roles.add(role)

    user.is_active = True
    user.save()

    return user

    

def email_generate_otp_process(otp, to_email, otp_for):
    # otp create
    db_utils.create_email_otp(otp, to_email, otp_for)
    # send_otp_email(otp, [to_email])
    send_email_task.apply_async(args=[otp, [to_email]])

def mobile_generate_otp_process(otp, mobile_number, otp_for):
    # from apps.booking.tasks import send_booking_sms_task
    # otp create
    db_utils.create_mobile_otp(otp, mobile_number, otp_for)
    # send_mobile_otp_task.apply_async(args=[otp, mobile_number])
    send_mobile_otp_task.apply_async(
        args=[otp, mobile_number, otp_for]
    )
    # send_booking_sms_task.apply_async(
    #     kwargs={
    #         'notification_type': 'otp',
    #         'params': {
    #             'mobile_number': mobile_number,
    #             'otp': otp,
    #             'otp_for': otp_for
    #         }
    #     }
    # )


def validate_google_token(id_token):
    name, email = "", ""
    url = f"https://oauth2.googleapis.com/tokeninfo?id_token={id_token}"
    
    headers = {
      'Content-Type': 'application/json'
    }
    response = requests.request("POST", url, headers=headers, data={})
    if response.status_code == 200:
        data = response.json()
        name = data.get('name', '')
        email = data.get('email', '')
        return True, name, email
    else:
        return False, name, email

def get_group_based_on_name(group_name):
    grp, role = None, None
    
    if group_name == 'FRANCHISE-GRP':
        grp = db_utils.get_group_by_name('FRANCHISE-GRP')
        role = db_utils.get_role_by_name('FRANCH-ADMIN')
    elif group_name == 'HOTELIER-GRP':
        grp = db_utils.get_group_by_name('HOTELIER-GRP')
        role = db_utils.get_role_by_name('HTLR-ADMIN')
    elif group_name == 'CORPORATE-GRP':
        grp = db_utils.get_group_by_name('CORPORATE-GRP')
        role = db_utils.get_role_by_name('CORP-ADMIN')
    elif group_name == 'B2C-GRP':
        grp = db_utils.get_group_by_name('B2C-GRP')
        role = db_utils.get_role_by_name('B2C-CUST')
        
    return grp, role
    
            
        
