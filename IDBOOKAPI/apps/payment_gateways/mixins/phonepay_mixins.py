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
        
        
    def get_encrypted_header_and_payload(self, payload):
        json_data = json.dumps(payload)
        base64_request = self.data_to_base64(json_data)

        # X-VERIFY Header
        salt_index = settings.SALT_INDEX
        salt_key = settings.SALT_KEY #"96434309-7796-489d-8924-ab56988a6076"
        verify_x_header =  self.encode_using_sha256(base64_request + "/pg/v1/pay" + salt_key)+"###"+ str(salt_index)
    
        req = {"request": base64_request}
        

        auth_header = {
            "Content-Type": "application/json",
            "X-VERIFY": verify_x_header}

        return req, auth_header

    def post_pay_page(self, req, auth_header):
        phonepay_url = settings.PHONEPAY_URL #"https://api-preprod.phonepe.com/apis/pg-sandbox/pg/v1/pay"
        response = requests.post(phonepay_url, headers=auth_header, json=req)
        return response
        
        
        



        
