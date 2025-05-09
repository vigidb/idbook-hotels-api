from django.conf import settings
from dateutil.relativedelta import relativedelta

from apps.org_resources.utils.db_utils import (
    fetch_rec_init_subscriptions, fetch_rec_subscribers_to_notify,
    fetch_rec_subscribers_to_debit)

from apps.payment_gateways.mixins.phonepay_mixins import PhonePayMixin
from apps.log_management.models import UserSubscriptionLogs
from apps.org_resources.models import UserSubscription, SubRecurringTransaction
from apps.log_management.utils .db_utils import create_user_subscription_logs

from apps.payment_gateways.mixins.payu_mixins import PayUMixin

from IDBOOKAPI.utils import get_unique_id_from_time

def subscription_payu_process(user_subscription_dict, params):
    error_response_dict = {}
    usersub_obj = None
    user_id = user_subscription_dict.get('user_id')

    merchant_userid = params.get('merchant_userid')
    merchant_subid = params.get('merchant_subid')
    transaction_id = params.get('txnid')
    start_date = params.get('start_date')
    end_date = params.get('end_date')
    daily = params.get('daily')
    
    subscription_amount = params.get('amount')
    subscription_name = params.get('subscription_name')
    subscription_type = params.get('subscription_type')
    
    user_subscription_dict['subscription_amount'] = subscription_amount
    user_subscription_dict['merchant_userid'] = merchant_userid
    user_subscription_dict['merchant_subid'] = merchant_subid
    user_subscription_dict['sub_workflow'] = "TRANSACTION"
    user_subscription_dict['mandate_tnx_id'] = transaction_id
    user_subscription_dict['sub_start_date'] = start_date
    user_subscription_dict['sub_end_date'] = end_date
   
    if subscription_type == "Monthly":
        payment_frequency = "MONTHLY"
        total_amount = subscription_amount
        user_subscription_dict['total_amount'] = total_amount
    elif subscription_type == "Yearly":
        total_amount = subscription_amount
        user_subscription_dict['total_amount'] = total_amount
        payment_frequency = "YEARLY"

    # initiate payu 
    payu_obj = PayUMixin()

    if daily:
        payment_frequency = "DAILY"
        si_details = {"billingAmount": subscription_amount,"billingCurrency": "INR",
                      "billingCycle": payment_frequency,"billingInterval": daily,
                      "paymentStartDate": str(start_date.date()),
                      "paymentEndDate": str(end_date.date())}
    else:
        params['amount'] = total_amount
        si_details = {"billingAmount": total_amount,"billingCurrency": "INR",
                      "billingCycle": payment_frequency,"billingInterval": 1,
                      "paymentStartDate": str(start_date.date()),
                      "paymentEndDate": str(end_date.date()),
                      "remarks":"Subscription"}


    key = settings.PAYU_KEY#"QE93eb"#"12936989"#8680557  #"JPM7Fg"
    params.update({"key":key,"udf1":"", "udf2":"", "udf3":"", "udf4":"", "udf5":""})  

    response = payu_obj.subscribe_consent_transaction(si_details, params)

    # user subscription
    usersub_obj = UserSubscription.objects.create(**user_subscription_dict)
    # user subscription logs
    UserSubscriptionLogs.objects.create(user_id=user_id, user_sub=usersub_obj, tnx_id=transaction_id,
                                        api_code='CRT-SUB', status_code=response.status_code)
    
    return response, usersub_obj

def subscription_cancel_payu_process(pg_subid, tnx_id):

    # initiate payu 
    payu_obj = PayUMixin()
    response = payu_obj.cancel_subscription(pg_subid, tnx_id)

    return response

def subscription_phone_pe_process(
    user_subscription_dict, merchant_subid, merchant_userid,
    subscription, mobile_number, upi, auth_request_id, user_id):
    """
    - Verify UPI ID
    - Create User Subscription
    - Submit auth request for mandate
    """
    error_response_dict = {}
    usersub_obj = None
    phonepe_obj = PhonePayMixin()

    subscription_amount = subscription.final_price
    # subscription_amount = subscription.price
    user_subscription_dict['subscription_amount'] = subscription_amount
   
    if subscription.subscription_type == "Monthly":
        payment_frequency = "MONTHLY"
    elif subscription.subscription_type == "Yearly":
        payment_frequency = "YEARLY"


    vpa_response = phonepe_obj.verify_vpa(upi)
    if vpa_response.status_code == 200:
        is_upi_valid = True
        user_subscription_dict['upi_id'] = upi
        user_subscription_dict['is_upi_valid'] = is_upi_valid
    else:
        pass
##        error_response_dict = {
##            "message":"UPI Invalid",
##            "error_code":"INVALID_UPI"
##        }
##        return error_response_dict, None

    # create subscription
    sub_payload = {
        "merchantId": settings.MERCHANT_ID,
        "merchantSubscriptionId": merchant_subid,
        "merchantUserId": merchant_userid,
        "authWorkflowType": "TRANSACTION",
        "amountType": "FIXED",
        "amount": subscription_amount,
        "frequency": payment_frequency,
        "recurringCount": 12,
        "mobileNumber": mobile_number
    }

    sub_response = phonepe_obj.create_subscription(sub_payload)
    if sub_response.status_code == 200:
        sub_response_json = sub_response.json()
        sub_data = sub_response_json.get('data',{})
        pg_subid = sub_data.get('subscriptionId')
        print("subscription id::", pg_subid)
        user_subscription_dict['pg_subid'] = pg_subid
        user_subscription_dict['merchant_userid'] = merchant_userid
        user_subscription_dict['merchant_subid'] = merchant_subid
        user_subscription_dict['sub_workflow'] = "TRANSACTION"
        
        usersub_obj = UserSubscription.objects.create(**user_subscription_dict)

        # subscription vpa log
        usr_sublogs_vpa = UserSubscriptionLogs(
            user_id=user_id, user_sub_id=usersub_obj.id,
            pg_subid=pg_subid, api_code="VPA-CHECK",
            status_code=vpa_response.status_code,
            #status_response=vpa_response.json()
        )
        # subscription create log
        usr_sublogs_subcreate = UserSubscriptionLogs(
            user_id=user_id, user_sub_id=usersub_obj.id,
            pg_subid=pg_subid, api_code="CRT-SUB",
            status_code=sub_response.status_code,
            status_response=sub_response.json())
        
        UserSubscriptionLogs.objects.bulk_create([
            usr_sublogs_vpa, usr_sublogs_subcreate])

    else:
        # error log
        UserSubscriptionLogs.objects.create(
            user_id=user_id, api_code="CRT-SUB",
            status_code=sub_response.status_code,
            status_response=sub_response.json())

        error_response_dict = {
            "message":"Subscription creation failed",
            "error_code":"SUBSCRIPTION_CREATE_ERROR"
        }
        return error_response_dict, None

    # submit auth request, for mandate
    payload = {
        "merchantId": settings.MERCHANT_ID,
        "merchantUserId": merchant_userid,
        "subscriptionId": pg_subid,
        "authRequestId": auth_request_id,
        "amount": subscription_amount,
        "paymentInstrument": {
            "type": "UPI_COLLECT",
            "vpa": upi
        }
    }

    submit_init_response = phonepe_obj.submit_auth_init(payload)
    if not submit_init_response.status_code == 200:
        UserSubscriptionLogs.objects.create(
            user_id=user_id, api_code="MANDATE",
            user_sub_id=usersub_obj.id, pg_subid=pg_subid,
            status_code=submit_init_response.status_code,
            status_response=submit_init_response.json())

        error_response_dict = {
            "message":"Subscription Mandate Request failed",
            "error_code":"SUBSCRIPTION_MANDATE_REQUEST_ERROR"
        }
        return error_response_dict, None

    
    usersub_obj.mandate_tnx_id = auth_request_id
    usersub_obj.save()

    UserSubscriptionLogs.objects.create(
        user_id=user_id, api_code="MANDATE",
        user_sub_id=usersub_obj.id, pg_subid=pg_subid,
        status_code=submit_init_response.status_code,
        status_response=submit_init_response.json())

    return error_response_dict, usersub_obj

def subscription_recurring_notification(current_date, payment_medium, pg_obj):
    trans_dict = {}
##    payment_medium = "PayU"
##    user_subscriptions = fetch_rec_init_subscriptions(
##        current_date, payment_medium=payment_medium)

    user_subscriptions = fetch_rec_subscribers_to_notify(
        current_date, payment_medium=payment_medium)

    print("user subscriptions notification ---------", user_subscriptions)

    for user_subscription in user_subscriptions:

        # for logs
        user_sub_logs = {
            "user_id":user_subscription.user_id,
            "user_sub_id":user_subscription.id,
            "pg_subid":user_subscription.pg_subid,
            "api_code":"RECUR-NOTIF"
        }
        
        try:
            if payment_medium == "PayU":
                # send notification
                request_id = "%s%d" %("RQT", user_subscription.id)
                request_id  = get_unique_id_from_time(request_id)

                # for transaction debit
                trans_dict['notify_request_id'] = request_id 
                trans_dict['user_id'] = user_subscription.user_id 
                trans_dict['user_sub_id'] = user_subscription.id
                
                user_sub_logs["tnx_id"] = request_id # for log

                inv_display_no = "%s%d" %("INV", user_subscription.id)
                inv_display_no  = get_unique_id_from_time(inv_display_no)
                trans_dict['invoice_display_no'] = inv_display_no # for transaction debit

                debit_date = str(user_subscription.next_payment_date.date())
                
                var1 = {
                    "authPayuId": user_subscription.pg_subid,
                    "requestId": request_id,
                    "debitDate":debit_date,
                    "amount":user_subscription.total_amount,
                    "invoiceDisplayNumber":inv_display_no
                }

                # pg_obj = PayUMixin()
                resp = pg_obj.recurring_payment_notification(var1)

                notify_response =  resp.json()
                notify_status_code = notify_response.get('status', 0)
                
                if notify_status_code == 1:
                    notify_status_code = 200
                    # clear existing transaction id
                    user_subscription.recrinit_tnx_id = ""
                    # for user subscription, will be cleared after transaction debit
                    user_subscription.notification_id = notify_response.get('invoiceid', '')
                    # save notification id for recurring transaction
                    trans_dict['notification_id'] = notify_response.get('invoiceid', '')
                else:
                    notify_status_code = 400
                    
                user_sub_logs["status_code"] = notify_status_code
                user_sub_logs["status_response"] = notify_response

                user_subscription.notify_request_id = request_id
                user_subscription.save()

                # save recurring transaction notification details
                SubRecurringTransaction.objects.create(**trans_dict)
  
                
        except Exception as e:
            print(e)
            user_sub_logs["error_message"] = str(e)

        # logs
        create_user_subscription_logs(user_sub_logs)


def subscription_recurring_debit(current_date,payment_medium, pg_obj):
    trans_dict = {}
##    payment_medium = "PayU"

    # fetch subscriptions to be debited
    user_subscriptions = fetch_rec_subscribers_to_debit(
        current_date, payment_medium=payment_medium)

    print("user subscriptions debit ---------", user_subscriptions)

    for user_subscription in user_subscriptions:
        
        subscription_type = user_subscription.idb_sub.subscription_type
        notification_id = user_subscription.notification_id

        sub_rec_obj = SubRecurringTransaction.objects.get(
            notification_id=notification_id)
        inv_display_no = sub_rec_obj.invoice_display_no

        # for logs
        user_sub_logs = {
            "user_id":user_subscription.user_id,
            "user_sub_id":user_subscription.id,
            "pg_subid":user_subscription.pg_subid,
            "api_code":"RECUR-INIT"
        }

        try:
            if payment_medium == "PayU":

                transaction_id = "%s%d" %("RTX", user_subscription.id)
                transaction_id  = get_unique_id_from_time(transaction_id)

                user_sub_logs["tnx_id"] = transaction_id

##                inv_display_no = "%s%d" %("INV", user_subscription.id)
##                inv_display_no  = get_unique_id_from_time(inv_display_no)
                
                var1 = {
                    "authpayuid":user_subscription.pg_subid,
                    "txnid":transaction_id, "amount":user_subscription.total_amount,
                    "invoiceDisplayNumber":inv_display_no,
                    "phone":user_subscription.user.mobile_number,
                    "email":user_subscription.user.email
                }

                # debit payment
                # pg_obj = PayUMixin()
                resp = pg_obj.recurring_payment_transaction(var1)
                debit_response =  resp.json()
                
                debit_status_code = debit_response.get('status', 0)
                amount = debit_response.get('details', {}).get(transaction_id, {}).get('amount', 0)
                #log
                user_sub_logs["status_response"] = debit_response

                # recurring transaction
                sub_rec_obj.transaction_amount = int(amount) if amount else 0
                sub_rec_obj.recrinit_tnx_id = transaction_id
                
                if debit_status_code == 1:
                    user_sub_logs["status_code"] = 200 #log
                    # recurring transaction 
                    sub_rec_obj.init_state = True
                    sub_rec_obj.paid = True

                    user_subscription.last_paid_date = current_date
                    user_subscription.paid = True
                    # clear the existing notification id once transaction is success
                    user_subscription.notification_id = ""

                    if subscription_type == "Monthly":
                        sub_next_payment_date = current_date + relativedelta(months=1)
                        user_subscription.next_payment_date = sub_next_payment_date
                        # notify the customer 3 days before the payment date (mininum 2 days before for payu
                        user_subscription.next_notify_date = sub_next_payment_date - relativedelta(days=3)
                    elif subscription_type == "Yearly":
                        sub_next_payment_date = current_date + relativedelta(years=1)
                        user_subscription.next_payment_date = sub_next_payment_date
                        user_subscription.next_notify_date = sub_next_payment_date - relativedelta(days=3)
                        
                else:
                    user_subscription.paid = False
                    user_subscription.active = False
                # update user subscription
                user_subscription.recrinit_tnx_id = transaction_id
                user_subscription.save()
                sub_rec_obj.save()
                        
        except Exception as e:
            print(e)
            user_sub_logs["error_message"] = str(e)

        UserSubscriptionLogs.objects.create(**user_sub_logs)
        
    
    
    
    
        
    
        
