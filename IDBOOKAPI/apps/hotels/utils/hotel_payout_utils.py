from apps.hotels.utils.db_utils import (
    get_property_bank_details, bulk_create_property_payout_details,
    bulk_update_property_payout_details, update_property_payout_error_details)
from apps.booking.utils.db_utils import get_hotelier_amount_payout

from apps.payment_gateways.mixins.payu_mixins import PayUPayOutMixin

from django.db.models import Sum

from IDBOOKAPI.utils import get_unique_id_from_time
from django.conf import settings
import traceback, pytz

from datetime import datetime


def get_payout_property_details(property_ids):
    payout_payload_list = []
    property_payout_list = []
    payment_type = "IMPS"
    payment_medium = "PayU"

    prop_bank_obj = get_property_bank_details(property_ids)
    
    batch_id = "%s" %("BATCH")
    batch_id  = get_unique_id_from_time(batch_id)

    for indx, prop_bank in enumerate(prop_bank_obj):
        property_id = prop_bank.get('id')
        account_number = prop_bank.get('property_bank__account_number')
        ifsc_code = prop_bank.get('property_bank__ifsc')

        prop_booking_obj = get_hotelier_amount_payout(property_id)
        booking_ids = list(prop_booking_obj.values_list('id', flat=True))
        print("booking ids", booking_ids)

        if booking_ids:
            hotelier_amount_dict = prop_booking_obj.aggregate(
                total=Sum('commission_info__hotelier_amount'))
            hotelier_amount = hotelier_amount_dict.get('total')

            merchant_ref_id = "%s%d" %("TX", indx)
            merchant_ref_id  = get_unique_id_from_time(merchant_ref_id)

            payload = {
                "disableApprovalFlow": True,
                "beneficiaryIfscCode": ifsc_code,
                "beneficiaryAccountNumber": account_number,
                "beneficiaryName": "Sonu George",
                "beneficiaryMobile": "9567068425",
                "beneficiaryEmail": "sonu@idbookhotels.com",
                "purpose": "Payment from company",
                "amount": float(hotelier_amount),
                "batchId": batch_id,
                "merchantRefId": merchant_ref_id,
                "paymentType": payment_type,
                "retry": False
                }

            payout_payload_list.append(payload)

            # property payout details
            property_payout_dict={
                "payout_property_id":property_id,
                "amount":hotelier_amount,
                "transaction_id":merchant_ref_id,
                "batch_id":batch_id,
                "payment_type":payment_type,
                "booking_list": booking_ids,
                "payment_medium":payment_medium,
                "initiate_status":True
                }
            property_payout_list.append(property_payout_dict)

    print(payout_payload_list)
    return payout_payload_list, property_payout_list

def process_initiate_payout_data_error(error_data, current_date):
    payout_error_ids = []
    for edata in error_data:
        tnx_id = edata.get('merchantRefId', '')
        message = edata.get('error', '')
        payout_data = {
            "initiate_status":400, "initiate_message": message,
            "initiate_response": error_data, "initiate_date":current_date}
        payout_id = update_property_payout_error_details(tnx_id, payout_data)
        payout_error_ids.append(payout_id)
    return payout_error_ids
    

def initiate_payout(payload, property_payout_list, payment_medium):

    response_data = {}
    pg_response = None

    timezone = pytz.timezone(settings.TIME_ZONE)
    current_date = datetime.now(timezone)

    if payment_medium == 'PayU':
        payout_obj = PayUPayOutMixin()
        response = payout_obj.initiate_transfer_api(payload)
        response_data = response.json()
        

    payout_pk_list = []
    if property_payout_list:
        prop_payout_obj = bulk_create_property_payout_details(
            property_payout_list)
        # fetch payout ids to update
        payout_pk_list = [obj.id for obj in prop_payout_obj]

    print("response data", response_data)
    response_status = response_data.get('status', '')
    if response_status == 0:
        print("success")
        payout_update_data = {
            "initiate_status":200, "initiate_message": response_data.get('msg', ''),
            "initiate_response": response_data, "initiate_date":current_date}
        print("payout list::", payout_pk_list)
        bulk_update_property_payout_details(payout_pk_list, payout_update_data)

        payout_response = {'status':'success', 'payout_success_list': payout_pk_list,
                           'payout_error_list':[]}

        return payout_response
    elif response_status == 1:
        error_data = response_data.get('data', [])
        payout_error_ids = process_initiate_payout_data_error(error_data, current_date)
        # get success list
        payout_success_list = list(set(payout_pk_list) - set(payout_error_ids))
        if payout_success_list:
            payout_update_data = {
                "initiate_status":200, "initiate_message": response_data.get('msg', ''),
                "initiate_response": response_data, "initiate_date":current_date}
            bulk_update_property_payout_details(payout_success_list, payout_update_data)

        payout_response = {'status':'partial_success', 'payout_success_list': payout_success_list,
                           'payout_error_list':payout_error_ids}

        return payout_response
            
    else:
        payout_update_data = {
            "initiate_status":400, "initiate_message": response_data.get('msg', ''),
            "initiate_response": response_data, "initiate_date":current_date}
        print("payout list::", payout_pk_list)

        bulk_update_property_payout_details(payout_pk_list, payout_update_data)

        payout_response = {'status':'error', 'payout_success_list': [],
                           'payout_error_list':payout_pk_list}

        return payout_response

        
        
        
        

        
    
        
        
        
        
