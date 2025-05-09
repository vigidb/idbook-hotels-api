from apps.org_resources.models import (
    Enquiry, CompanyDetail, Subscription,
    UserSubscription, SubRecurringTransaction)
import traceback

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

def fetch_rec_subscribers_to_notify(current_date, payment_medium=None):
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

def fetch_rec_subscribers_to_debit(current_date, payment_medium=None):
    try:
        user_subscriptions = UserSubscription.objects.filter(
            recrinit_tnx_id='', next_payment_date__date=current_date).exclude(
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
    

        
    
    
