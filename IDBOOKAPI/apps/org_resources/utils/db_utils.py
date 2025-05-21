from apps.org_resources.models import (
    Enquiry, CompanyDetail, Subscription,
    UserSubscription, SubRecurringTransaction)
from apps.customer.models import WalletTransaction
import traceback
from apps.customer.utils.db_utils import add_user_wallet_amount
from dateutil.relativedelta import relativedelta
from django.db.models import Q

def get_enquiry_details(enquiry_id):
    try:
        enquiry_obj = Enquiry.objects.get(id=enquiry_id)
        return enquiry_obj
    except Exception as e:
        print(e)
        print(traceback.format_exc())
        return None

def is_corporate_email_exist(email):
    is_exist = CompanyDetail.objects.filter(
        company_email=email).exists()
    return is_exist

def is_corporate_number_exist(company_phone):
    is_exist = CompanyDetail.objects.filter(
        company_phone=company_phone).exists()
    return is_exist

def get_subscription(subscription_id):
    try:
        subscription = Subscription.objects.get(id=subscription_id)
        return subscription
    except Exception as e:
        return None

def fetch_subscription_for_mandate_check(current_date):
    # 3 days gap
    mandate_date = current_date - relativedelta(days=2)
    user_subscriptions = UserSubscription.objects.exclude(mandate_tnx_id='')

    # check for mandate initiated and mandate cancelled initiated
    user_subscriptions = user_subscriptions.filter(
        Q(mandate_status='initiated') | Q(mandate_status='cancel_initiated'))
    # check each subscription every 2 days
    user_subscriptions = user_subscriptions.filter(Q(last_mandate_check__isnull=True)
                                                   |Q(last_mandate_check__lte=mandate_date))
    return user_subscriptions
    
    

def fetch_rec_subscribers_to_notify(current_date, payment_medium=None):
    try:
        user_subscriptions = UserSubscription.objects.filter(
            notification_id='', next_notify_date__date=current_date,
            mandate_status='active')
        if payment_medium:
            user_subscriptions = user_subscriptions.filter(
                payment_medium=payment_medium)        
        return user_subscriptions
    except Exception as e:
        print(e)
        return []

def fetch_rec_subscribers_to_debit(current_date, payment_medium=None):
    try:
        user_subscriptions = UserSubscription.objects.filter(
            recrinit_tnx_id='', next_payment_date__date=current_date,
            mandate_status='active').exclude(
                notification_id='')
        if payment_medium:
            user_subscriptions = user_subscriptions.filter(
                payment_medium=payment_medium)        
        return user_subscriptions
    except Exception as e:
        print(e)
        return []

def fetch_rec_init_subscriptions(current_date, payment_medium=None):
    try:
        user_subscriptions = UserSubscription.objects.filter(
            notification_id='', next_notify_date__date=current_date)
        if payment_medium:
            user_subscriptions = user_subscriptions.filter(
                payment_medium=payment_medium)
            
        return user_subscriptions
    except Exception as e:
        print(e)
        return []

##def fetch_for_rec_notification(start_date, end_date):
##    try:
##        user_subscriptions = UserSubscription.objects.filter(
##            notification_id='', next_notify_date__lte=end_date,
##            next_notify_date__gte=start_date)
##        return user_subscriptions
##    except Exception as e:
##        print(e)
##        return []

def add_sub_recurring_transaction(trans_dict:dict):
    SubRecurringTransaction.objects.create(**trans_dict)

def update_subrecur_transaction(transaction_id, trans_dict:dict):
    
    trans_obj = SubRecurringTransaction.objects.get(
        recrinit_tnx_id=transaction_id)
    if trans_dict:
        trans_obj.transaction_amount = trans_dict['transaction_amount']
        trans_obj.paid = trans_dict['paid']
        trans_obj.callbak_state = trans_dict['callbak_state']
        trans_obj.save()

def add_wallet_bonus_for_subscription(user_sub_obj):
    """
    Adds wallet bonus based on subscription type and level.
    Returns True if wallet bonus was successfully added, else False.
    """
    user_id = user_sub_obj.user.id
    user_subid = user_sub_obj.id
    subscription_type = user_sub_obj.idb_sub.subscription_type
    subscription_level = user_sub_obj.idb_sub.level

    bonus_amount = 0
    if subscription_type == "Yearly":
        if subscription_level == 2:
            bonus_amount = 200
        elif subscription_level == 3:
            bonus_amount = 500

        if bonus_amount > 0:
            wallet_status = add_user_wallet_amount(user_id, bonus_amount)

            if wallet_status:
                transaction_details = f"Pro member bonus {bonus_amount} INR for {subscription_type} {user_sub_obj.idb_sub.name} is credited into Wallet"
                other_details = {
                    "subscription": {
                        "id": user_subid,
                        "level": subscription_level,
                        "type": subscription_type,
                        "amount": bonus_amount
                    }
                }

                wtransact_dict = {
                    'user_id': user_id,
                    'amount': bonus_amount,
                    'transaction_type': 'Credit',
                    'transaction_details': transaction_details,
                    'company_id': None,
                    'transaction_for': 'pro_member_bonus',
                    'is_transaction_success': True,
                    'other_details': other_details,
                    'expiry_date': user_sub_obj.sub_end_date,
                    'used_amount': 0,
                    'remaining_amount': bonus_amount
                }

                WalletTransaction.objects.create(**wtransact_dict)
                return True
    return False
        
    
    
