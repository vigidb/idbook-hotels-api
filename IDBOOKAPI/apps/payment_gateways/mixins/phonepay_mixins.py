import hashlib
import requests
import base64
import json

from django.conf import settings

class PhonePayMixin:
    
    def encode_using_sha256(self, data):
        sha256_data = hashlib.sha256(data.encode())
        encoded_data = sha256_data.hexdigest()
        return encoded_data

    def data_to_base64(self, data):
        encoded_data = base64.b64encode(data.encode())
        return encoded_data.decode()
        
        
    def get_encrypted_header_and_payload(self, payload, req_trigger=False,
                                         endpoint=None, callback_url=None):
        json_data = json.dumps(payload)
        base64_request = self.data_to_base64(json_data)
        if not payload:
            base64_request = ""
            

        # X-VERIFY Header
        salt_index = settings.SALT_INDEX
        salt_key = settings.SALT_KEY #"96434309-7796-489d-8924-ab56988a6076"
        # verify_x_header =  self.encode_using_sha256(base64_request + "/pg/v1/pay" + salt_key)+"###"+ str(salt_index)
        if not endpoint:
            endpoint = "/pg/v1/refund" if req_trigger else "/pg/v1/pay"
            
        verify_x_header = self.encode_using_sha256(base64_request + endpoint + salt_key) + "###" + str(salt_index)
        print("endpoint", endpoint)
    
        req = {"request": base64_request}
        

        auth_header = {
            "Content-Type": "application/json",
            "X-VERIFY": verify_x_header}

        if callback_url:
            auth_header['X-CALLBACK-URL'] = callback_url

        return req, auth_header

    def post_pay_page(self, req, auth_header):
        phonepay_url = settings.PHONEPAY_URL #"https://api-preprod.phonepe.com/apis/pg-sandbox/pg/v1/pay"
        response = requests.post(phonepay_url, headers=auth_header, json=req)
        return response

    def post_refund_request(self, req, auth_header):
        phonepay_refund_url = settings.PHONEPAY_REFUND_URL
        response = requests.post(phonepay_refund_url, headers=auth_header, json=req)
        return response

    def create_subscription(self, payload):
        # https://api.phonepe.com/apis/hermes/pg/v1/pay

##        payload = {
##            "merchantId": settings.MERCHANT_ID,
##            "merchantSubscriptionId": "MSUB123456789012348",
##            "merchantUserId": "MU123456789",
##            "authWorkflowType": "PENNY_DROP",
##            "amountType": "FIXED",
##            "amount": 100,
##            "frequency": "MONTHLY",
##            "recurringCount": 12,
##            "mobileNumber": "9567068425"
####            "deviceContext": {
####                "phonePeVersionCode": 400922
####                }
##        }

        
        phonepay_base_url = settings.PHONEPE_BASE_URL
        endpoint = "/v3/recurring/subscription/create"
        phonepay_sub_url = phonepay_base_url + endpoint
        req, auth_header = self.get_encrypted_header_and_payload(payload, endpoint=endpoint)
        response = requests.post(phonepay_sub_url, headers=auth_header, json=req)
        return response

    def set_recurring_init(self, payload):
##        payload = {
##            "merchantId": settings.MERCHANT_ID,
##            "merchantUserId": "MU123456789",
##            "subscriptionId": "OM2504151542543110597496",
##            "transactionId": "TX1234567827A",
##            "autoDebit": True,
##            "amount": 100
##        }

        phonepay_base_url = settings.PHONEPE_BASE_URL
        endpoint = "/v3/recurring/debit/init"
        callback_url = settings.CALLBACK_URL + "/api/v1/org-resources/user-subscription/recur-init/pe-callbackurl/"
        #callback_url = "https://webhook.site/612a9220-e7f4-4c71-b44f-91d16f65773f"

        phonepay_sub_url = phonepay_base_url + endpoint
        req, auth_header = self.get_encrypted_header_and_payload(payload, endpoint=endpoint)
        response = requests.post(phonepay_sub_url, headers=auth_header, json=req)
        return response

    def set_recurring_execute(self):

        payload = {
            "merchantId": settings.MERCHANT_ID,
            "merchantUserId": "MU123456789",
            "subscriptionId": "OM2504151542543110597496",
            "notificationId": "OM2504151559556890597569",
            "transactionId": "TX1234567827A"
        }

        phonepay_base_url = settings.PHONEPE_BASE_URL
        endpoint = "/v3/recurring/debit/execute"

        phonepay_sub_url = phonepay_base_url + endpoint
        req, auth_header = self.get_encrypted_header_and_payload(payload, endpoint=endpoint)
        response = requests.post(phonepay_sub_url, headers=auth_header, json=req)

        print(response)
        print(response.json())

    def check_recurring_status(self):
        phonepay_base_url = settings.PHONEPE_BASE_URL
        

        merchant_id = settings.MERCHANT_ID
        transaction_id = "TX1234567827A"
        endpoint = f"/v3/recurring/debit/status/{merchant_id}/{transaction_id}"
        
        phonepay_sub_url = phonepay_base_url + endpoint
        req, auth_header = self.get_encrypted_header_and_payload({}, endpoint=endpoint)
        response = requests.get(phonepay_sub_url, headers=auth_header, json=req)

        print(response)
        print(response.json())

    def verify_vpa(self, vpa):
        phonepay_base_url = settings.PHONEPE_BASE_URL
        

        merchant_id = settings.MERCHANT_ID
        #vpa = "test-vpa@ybl"
        endpoint = f"/v3/vpa/{merchant_id}/{vpa}/validate"
        
        phonepay_sub_url = phonepay_base_url + endpoint
        req, auth_header = self.get_encrypted_header_and_payload({}, endpoint=endpoint)
        response = requests.get(phonepay_sub_url, headers=auth_header, json=req)

        return response

    def submit_auth_init(self, payload):
        
##        payload = {
##          "merchantId": settings.MERCHANT_ID,
##          "merchantUserId": "MU123456789",
##          "subscriptionId": "OM2504151542543110597496",
##          "authRequestId": "TX123456789",
##          "amount": 100,
##          "paymentInstrument": {
##            "type": "UPI_COLLECT",
##            "vpa": "test-vpa@ybl"
##          }
##        }


        phonepay_base_url = settings.PHONEPE_BASE_URL
        endpoint = "/v3/recurring/auth/init"
        callback_url = settings.CALLBACK_URL + "/api/v1/org-resources/user-subscription/submit-auth-init/pe-callbackurl/" #"https://webhook.site/612a9220-e7f4-4c71-b44f-91d16f65773f"
        #callback_url = "https://webhook.site/612a9220-e7f4-4c71-b44f-91d16f65773f"
        phonepay_sub_url = phonepay_base_url + endpoint
        req, auth_header = self.get_encrypted_header_and_payload(
            payload, endpoint=endpoint, callback_url=callback_url)
        response = requests.post(phonepay_sub_url, headers=auth_header, json=req)
        return response

    def submit_auth_request_status(self):

        phonepay_base_url = settings.PHONEPE_BASE_URL
        

        merchant_id = settings.MERCHANT_ID
        auth_requestid = "TX11744817531"#"TX123456789"
        endpoint = f"/v3/recurring/auth/status/{merchant_id}/{auth_requestid}"
        
        phonepay_sub_url = phonepay_base_url + endpoint
        req, auth_header = self.get_encrypted_header_and_payload({}, endpoint=endpoint)
        response = requests.get(phonepay_sub_url, headers=auth_header, json=req)

        print(response)
        print(response.json())
        

        
        
        
        



        
