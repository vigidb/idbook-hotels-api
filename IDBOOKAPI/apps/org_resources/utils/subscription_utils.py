from django.conf import settings

from apps.payment_gateways.mixins.phonepay_mixins import PhonePayMixin
from apps.log_management.models import UserSubscriptionLogs
from apps.org_resources.models import UserSubscription

from apps.payment_gateways.mixins.payu_mixins import PayUMixin

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
        total_amount = subscription_amount * 12
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

    subscription_amount = subscription.price
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
        
    
        
