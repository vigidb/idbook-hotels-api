from django.conf import settings

from IDBOOKAPI.celery import app as celery_idbook
from IDBOOKAPI.email_utils import send_email

from apps.org_resources.utils.db_utils import (
    get_enquiry_details, fetch_rec_init_subscriptions,
    add_sub_recurring_transaction)
from apps.log_management.utils .db_utils import create_user_subscription_logs
from apps.payment_gateways.mixins.phonepay_mixins import PhonePayMixin

from datetime import datetime
from dateutil.relativedelta import relativedelta
from IDBOOKAPI.utils import get_unique_id_from_time

import traceback



@celery_idbook.task(bind=True)
def send_enquiry_email_task(self, enquiry_id):
    print("Enquiry Id", enquiry_id)
    try:
        enquiry_obj = get_enquiry_details(enquiry_id)
        if enquiry_obj:
            name = enquiry_obj.name
            phone_no = enquiry_obj.phone_no
            email = enquiry_obj.email
            enquiry_message = enquiry_obj.enquiry_msg
            message = f" Name: {name}, Email: {email}, Phone No: {phone_no} \n \
Message: {enquiry_message}"
            from_email = settings.EMAIL_HOST_USER
            subject = "Enquiry"
            to_emails = ['support@idbookhotels.com', 'sonu@idbookhotels.com']
            send_email(subject, message, to_emails, from_email)
        else:
            print("Missing enquiry id", enquiry_id)
    except Exception as e:
        print(e)
        print(traceback.format_exc())


@celery_idbook.task(bind=True)
def initiate_recurring_payment(self):
    print("initiate reciurring payment")
    current_date = datetime.now()
    start_date = current_date - relativedelta(days=1)
    print("start date--", start_date)
    user_subscriptions = fetch_rec_init_subscriptions(
        start_date, current_date)
    print("user subscriptions -----------", user_subscriptions)
    # phonepe object 
    phonepe_obj = PhonePayMixin()
    
    for user_subscription in user_subscriptions:
        try:
            # generate recurrent init transaction id
            transaction_id = "%s%d" %("TX", user_subscription.id)
            transaction_id = get_unique_id_from_time(transaction_id)
            notification_id = ""
            tnx_amount = 0

            recurring_trans_dict = {
                "user_id": user_subscription.user.id,
                "user_sub_id":user_subscription.id,
                "recrinit_tnx_id":transaction_id
            }

            payload = {
                "merchantId": settings.MERCHANT_ID,
                "merchantUserId": user_subscription.merchant_userid,
                "subscriptionId": user_subscription.merchant_subid,
                "transactionId": transaction_id,
                "autoDebit": True,
                "amount": user_subscription.subscription_amount
            }
            recurinit_resp = phonepe_obj.set_recurring_init(payload)
            if recurinit_resp.status_code == 200:
                
                recurinit_resp_json = recurinit_resp.json()
                notification_id = recurinit_resp_json.get('data', {}).get('notificationId', '')
                notification_state = recurinit_resp_json.get('data', {}).get('state', '')
                tnx_amount = recurinit_resp_json.get('data', {}).get('amount', 0)

                recurring_trans_dict["notification_id"] = notification_id
                recurring_trans_dict["init_state"] = notification_state
                recurring_trans_dict["transaction_amount"] = tnx_amount


            user_subscription.recrinit_tnx_id = transaction_id
            user_subscription.notification_id = notification_id
            user_subscription.transaction_amount = tnx_amount
            user_subscription.paid = False
            user_subscription.save()

            # add recurring transaction details
            add_sub_recurring_transaction(recurring_trans_dict)

        except Exception as e:
            print(e)
            print(traceback.format_exc())

        user_sub_logs = {
            "user_id":user_subscription.user_id,
            "user_sub_id":user_subscription.id,
            "pg_subid":user_subscription.pg_subid,
            "api_code":"RECUR-INIT",
            "status_code":recurinit_resp.status_code,
            "status_response":recurinit_resp.json()}

        create_user_subscription_logs(user_sub_logs)
        
        

    

