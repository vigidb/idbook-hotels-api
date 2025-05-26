import requests, json
# authentication utils
from apps.authentication.utils import db_utils
from apps.authentication.models import User, UserOtp
from apps.authentication.tasks import (
    send_email_task, send_mobile_otp_task)

from django.conf import settings

from rest_framework_simplejwt.tokens import RefreshToken
from apps.customer.utils.db_utils import (
    update_wallet_transaction,add_user_wallet_amount)
from apps.org_resources.models import BasicAdminConfig
from datetime import datetime
import pytz

def user_representation(user, refresh_token=None):
    
    profile_picture = ''
    customer_profile = user.customer_profile.last()
    if customer_profile:
        if customer_profile.profile_picture:
            profile_picture = settings.MEDIA_URL + str(customer_profile.profile_picture)
        employee_id = customer_profile.employee_id


    user_roles = [uroles for uroles in user.roles.values('id','name')]
    user_groups = [ugrps for ugrps in user.groups.values('id', 'name')]

    subscription_name = ""
    user_subscription_id = None
    sub_start_date = None
    sub_end_date = None
    subscription_amount = None
    last_paid_date = None
    next_payment_date = None
    user_subscription = user.user_subscription.filter(active=True).last()
    user_subscription_details = {}
    if user_subscription:
        subscription_name = user_subscription.idb_sub.name
        user_subscription_id = user_subscription.id
        sub_start_date = user_subscription.sub_start_date
        sub_end_date = user_subscription.sub_end_date
        subscription_amount = user_subscription.subscription_amount
        last_paid_date = user_subscription.last_paid_date
        next_payment_date = user_subscription.next_payment_date
        

    user_data = {'id': user.id, 'mobile_number': user.mobile_number if user.mobile_number else '',
                 'email': user.email if user.email else '', 'name': user.get_full_name(),
                 'groups': user_groups, 'roles': user_roles, 'permissions': [],
                 'category': user.category, 'profile_picture':profile_picture,
                 'business_id': user.business_id if user.business_id else '',
                 'company_id' : user.company_id if user.company_id else '',
                 'default_group': user.default_group, 'subscription_name':subscription_name,
                 'user_subscription_id':user_subscription_id, "sub_start_date":sub_start_date,
                 "sub_end_date":sub_end_date, "subscription_amount":subscription_amount,
                 "last_paid_date":last_paid_date, "next_payment_date":next_payment_date,
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
    elif group_name == 'BUSINESS-GRP':
        grp = db_utils.get_group_by_name('BUSINESS-GRP')
        role = db_utils.get_role_by_name('BUS-ADMIN')
        
    return grp, role
    

def add_signup_bonus(user, group_name, role):
    if group_name == 'B2C-GRP' and role and role.name == 'B2C-CUST':
        # reward_amount = 250
        reward_config = BasicAdminConfig.objects.get(code='signup_bonus')
        reward_amount = float(reward_config.value)
        company_id = None  # No company context at signup
        status = add_user_wallet_amount(user.id, reward_amount)

        transaction_details = "Signup reward for B2C-CUST"
        other_details = {"signup_reward": True}

        wallet_transact_dict = {
            'user_id': user.id,
            'amount': reward_amount,
            'transaction_type': 'Credit',
            'transaction_details': transaction_details,
            'company_id': company_id,
            'transaction_for': 'signup_reward',
            'is_transaction_success': status,
            'other_details': other_details
        }
        update_wallet_transaction(wallet_transact_dict)
       
def check_otp_generation_limit(user_account):
    try:
        user_otp = UserOtp.objects.filter(user_account=user_account).first()
        
        # If no previous OTP exists, allow generation
        if not user_otp:
            return True, None
        
        # Check if user has exceeded the maximum attempts (5)
        if user_otp.otp_generate_tries >= 5:
            ist = pytz.timezone('Asia/Kolkata')
            now = datetime.now(ist)
            time_difference = now - user_otp.last_attempt_time
            minutes_passed = time_difference.total_seconds() / 60
            
            if minutes_passed < 30:
                remaining_minutes = int(30 - minutes_passed)
                return False, f"Maximum OTP attempts exceeded. Please try again after {remaining_minutes} minutes."
            else:
                # If 30 minutes have passed, reset the counter to 0
                user_otp.otp_generate_tries = 0
                user_otp.save()
        
        return True, None
    except Exception as e:
        print(f"Error checking OTP limit: {e}")
        return False, "Error checking OTP limit. Please try again later."

def check_login_attempt_limit(user_account):
    try:
        user_otp = UserOtp.objects.filter(user_account=user_account).first()
        
        # If no OTP record exists, don't allow login (should generate OTP first)
        if not user_otp:
            return False, "Please generate OTP first"
        
        if user_otp.login_tries >= 5:
            if user_otp.last_login_attempt_time:
                ist = pytz.timezone('Asia/Kolkata')
                now = datetime.now(ist)
                time_difference = now - user_otp.last_login_attempt_time
                minutes_passed = time_difference.total_seconds() / 60
                
                if minutes_passed < 30:
                    remaining_minutes = int(30 - minutes_passed)
                    return False, f"Maximum login attempts exceeded. Please try again after {remaining_minutes} minutes."
                else:
                    user_otp.login_tries = 0
                    user_otp.save()
        
        return True, None
    except Exception as e:
        print(f"Error checking login attempt limit: {e}")
        return False, "Error checking login limit. Please try again later."

def check_pwd_reset_attempt_limit(user_account):
    try:
        user_otp = UserOtp.objects.filter(user_account=user_account).first()
        
        # If no OTP record exists, don't allow password reset (should generate OTP first)
        if not user_otp:
            return False, "Please generate OTP first"
        
        # Check if user has exceeded the maximum password reset attempts (5)
        if user_otp.pwd_reset_tries >= 5:
            # Check if 30 minutes have passed since last password reset attempt
            if user_otp.last_pwd_reset_attempt_time:
                ist = pytz.timezone('Asia/Kolkata')
                now = datetime.now(ist)
                time_difference = now - user_otp.last_pwd_reset_attempt_time
                minutes_passed = time_difference.total_seconds() / 60
                
                if minutes_passed < 30:
                    remaining_minutes = int(30 - minutes_passed)
                    return False, f"Maximum password reset attempts exceeded. Please try again after {remaining_minutes} minutes."
                else:
                    # If 30 minutes have passed, reset the password reset counter to 0
                    user_otp.pwd_reset_tries = 0
                    user_otp.save()
        
        return True, None
    except Exception as e:
        print(f"Error checking password reset attempt limit: {e}")
        return False, "Error checking password reset limit. Please try again later."

def check_verify_attempt_limit(user_account):
    try:
        user_otp = UserOtp.objects.filter(user_account=user_account).first()
        
        # If no OTP record exists, don't allow verification (should generate OTP first)
        if not user_otp:
            return False, "Please generate OTP first"
        
        # Check if user has exceeded the maximum verification attempts (5)
        if user_otp.verify_tries >= 5:
            # Check if 30 minutes have passed since last verification attempt
            if user_otp.last_verify_attempt_time:
                ist = pytz.timezone('Asia/Kolkata')
                now = datetime.now(ist)
                time_difference = now - user_otp.last_verify_attempt_time
                minutes_passed = time_difference.total_seconds() / 60
                
                if minutes_passed < 30:
                    remaining_minutes = int(30 - minutes_passed)
                    return False, f"Maximum verification attempts exceeded. Please try again after {remaining_minutes} minutes."
                else:
                    # If 30 minutes have passed, reset the verification counter to 0
                    user_otp.verify_tries = 0
                    user_otp.save()
        
        return True, None
    except Exception as e:
        print(f"Error checking verification attempt limit: {e}")
        return False, "Error checking verification limit. Please try again later."