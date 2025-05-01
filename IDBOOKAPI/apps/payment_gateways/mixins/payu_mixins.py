import hashlib
import requests, json
from django.conf import settings

class PayUMixin:

    def encode_using_sha512(self, data):
        hash_object = hashlib.sha512()
        hash_object.update(data.encode('utf-8'))
        hex_digest = hash_object.hexdigest()
        return hex_digest


    def recurring_payment_notification(self):

        # url = "https://info.payu.in/merchant/"
        url = "https://test.payu.in/merchant/postservice.php?form=2"

        #7043873219

        key, command = "JPM7Fg", "pre_debit_SI" #"check_action_status_txnid"
        var1 = {"authPayuId":"403993715533817148","requestId":"1234589","debitDate":"2025-04-30","amount":"500"}
        var1 = json.dumps(var1)

        salt = settings.PAYU_SALT

        data_to_hash = f"{key}|{command}|{var1}|{salt}"
        hex_digest = self.encode_using_sha512(data_to_hash)
        print("hex digest::", hex_digest)
        

        payload = {
            "key": key,
            "var1": var1,
            "command": command,#"pre_debit_SI",
            "hash": hex_digest
        }
        headers = {
            "accept": "application/json",
            "content-type": "application/x-www-form-urlencoded"
        }

        response = requests.post(url, data=payload, headers=headers)

        return response


    def check_mandate(self, auth_id, trans_id):
        url = "https://test.payu.in/merchant/postservice?form=2"
        key = settings.PAYU_KEY
        command = "check_mandate_status"

        var1 = {"authPayuId":auth_id, "requestId": trans_id}
        var1 = json.dumps(var1)

        salt = settings.PAYU_SALT

        data_to_hash = f"{key}|{command}|{var1}|{salt}"
        hex_digest = self.encode_using_sha512(data_to_hash)

        payload = {
            "key": key,
            "command": command,
            "var1": var1,
            "hash":hex_digest
        }
        
        headers = {"content-type": "application/x-www-form-urlencoded"}

        response = requests.post(url, data=payload, headers=headers)
        return response

    def verify_payment(self, var1):

        url = "https://test.payu.in/merchant/postservice?form=2"
        key = settings.PAYU_KEY
        command = "verify_payment"
##        var1 = "TX11745850883"
        
        salt = settings.PAYU_SALT
        
        data_to_hash = f"{key}|{command}|{var1}|{salt}"
        hex_digest = self.encode_using_sha512(data_to_hash)

        payload = {
            "key": key,
            "command": command,
            "var1": var1,
            "hash":hex_digest
        }
        
        headers = {"content-type": "application/x-www-form-urlencoded"}

        response = requests.post(url, data=payload, headers=headers)
        return response

    def subscribe_consent_transaction(self, si_details, params):

        url = settings.PAYU_URL #"https://test.payu.in/_payment"
        
##        si_details = {"billingAmount": "200.00","billingCurrency": "INR",
##                      "billingCycle": "MONTHLY","billingInterval": 1,
##                      "paymentStartDate": "2025-04-30",
##                      "paymentEndDate": "2025-07-29", "siTokenRequestor":1}
        # convert dict to json
        si_details = json.dumps(si_details)

##        params = {"key":settings.PAYU_KEY, "txnid":"ST0189z21", "amount":200.00,
##                  "udf1":"", "udf2":"", "udf3":"", "udf4":"", "udf5":"",
##                  "subscription_name":"subscription", "firstname":"Sonu",
##                  "email":"sonu@idbookhotels.com", "phone":"9567068425"
##                  }

        key, txnid = params.get("key", ""), params.get("txnid", "")
        amount = params.get("amount", 0)
        
        udf1, udf2, udf3 = params.get("udf1", ""), params.get("udf2", ""), params.get("udf3", "")
        udf4, udf5 =  params.get("udf4", ""), params.get("udf5", "")
        
        productinfo = params.get("subscription_name", "")
        firstname = params.get("firstname", "")
        email, phone = params.get("email", ""), params.get("phone", "")

        surl = settings.CALLBACK_URL + "/api/v1/org-resources/user-subscription/payu-sucess/"
        furl = settings.CALLBACK_URL + "/api/v1/org-resources/user-subscription/payu-sucess/"

        api_version = 7
        si =  1  # for recurring payment

        salt = settings.PAYU_SALT #""#"QE93eb" #"TuxqAugd"

        #data_to_hash = f"{key}|{txnid}|120|subscription|Sonu|sonu@idbookhotels.com|||||||||||{si_details}|TuxqAugd"
        data_to_hash = f"{key}|{txnid}|{amount}|{productinfo}|{firstname}|{email}|{udf1}|{udf2}|{udf3}|{udf4}|{udf5}||||||{si_details}|{salt}"
        hex_digest = self.encode_using_sha512(data_to_hash)
        print("hex digest::", hex_digest)
        
        payload = {
            "key": key,
            "txnid":txnid,
            "amount":amount,
            "productinfo":productinfo,
            "firstname":firstname,
            "email":email,
            "phone":phone,
            "surl": surl,#"https://test-payment-middleware.payu.in/simulatorResponse",
            "furl": furl,
            "api_version":api_version,
            "si":si,
            #"free_trial":1,
            "si_details":si_details,
            "hash":hex_digest
        }
        
        headers = {
            "accept": "application/json",
            "content-type": "application/x-www-form-urlencoded"
        }

        print(payload)
        response = requests.post(url, data=payload, headers=headers)
        return response

    def subscribe_consent_netbnk_trans(self):
        url = "https://test.payu.in/_payment" # "https://secure.payu.in/_payment"

        key = "JPM7Fg"
        txnid = "ST0189z1"
        amount = 120
        udf1, udf2, udf3 = "","",""
        udf4, udf5 = "",""
        productinfo = "subscription"
        firstname = "Sonu"
        email="sonu@idbookhotels.com"
        phone = "9567068425"
        surl = settings.CALLBACK_URL + "api/v1/org-resources/user-subscription/payu-sucess/" #"https://test-payment-middleware.payu.in/simulatorResponse",
        furl = settings.CALLBACK_URL + "api/v1/org-resources/user-subscription/payu-sucess/"
        
        api_version, si, pg = 7, 1, "ENACH"
        bankcode = "ICICENCC"
        beneficiarydetail = {"beneficiaryName": "Ashish Kumar","beneficiaryAccountNumber": "1211450021",
                             "beneficiaryAccountType": "SAVINGS",
                             "beneficiaryIfscCode":"ICIC0000046", "verificationMode":"DEBIT_CARD"}
        beneficiarydetail = json.dumps(beneficiarydetail)
        
        si_details = {"billingAmount": "120.00","billingCurrency": "INR","billingCycle": "MONTHLY",
                      "billingInterval": 1,"paymentStartDate": "2019-09-01", "paymentEndDate": "2019-12-01"}
        si_details = json.dumps(si_details)
        salt = "TuxqAugd"

        data_to_hash = f"{key}|{txnid}|{amount}|{productinfo}|{firstname}|{email}|{udf1}|{udf2}|{udf3}|{udf4}|{udf5}||||||{si_details}|{salt}"
        hex_digest = self.encode_using_sha512(data_to_hash)

        payload = {
            "key": key,
            "txnid":txnid,
            "amount":amount,
            "productinfo":productinfo,
            "firstname":firstname,
            "email":email,
            "phone":phone,
            "surl": surl,
            "furl": furl,
            "api_version":api_version,
            "si":si,
            "pg": pg,
            "bankcode":bankcode,
            "si_details":si_details,
            "beneficiarydetail":beneficiarydetail,
            "hash":hex_digest
        }
        
        headers = {
            "accept": "text/plain",
            "content-type": "application/x-www-form-urlencoded"
        }

        response = requests.post(url, data=payload, headers=headers)
        print(response.text)
        print(response.url)

    def subscribe_consent_card_trans(self):
        url = "https://test.payu.in/_payment" # "https://secure.payu.in/_payment"

        key = "JPM7Fg"
        txnid = "ST0189z4"
        amount = 120
        udf1, udf2, udf3 = "","",""
        udf4, udf5 = "",""
        productinfo = "subscription"
        firstname = "Sonu"
        email="sonu@idbookhotels.com"
        phone = "9567068425"
        surl = "https://api.idbookhotels.com/" #"https://test-payment-middleware.payu.in/simulatorResponse",
        furl =  "https://test-payment-middleware.payu.in/simulatorResponse"
        
        api_version, si, pg = 7, 1, "CC"
        bankcode = "AMEX"
        ccnum, ccexpmon, ccexpyr = "5123456789012346", "05", "25"
        ccvv, ccname = "123", "Test User"
    ##    beneficiarydetail = {"beneficiaryName": "Ashish Kumar","beneficiaryAccountNumber": "1211450021",
    ##                         "beneficiaryAccountType": "SAVINGS",
    ##                         "beneficiaryIfscCode":"ICIC0000046", "verificationMode":"DEBIT_CARD"}
        
        si_details = {"billingAmount": "120.00","billingCurrency": "INR","billingCycle": "MONTHLY",
                      "billingInterval": 1,"paymentStartDate": "2025-09-01", "paymentEndDate": "2026-12-01",
                      "siTokenRequestor":2}
        si_details = json.dumps(si_details)
        salt = "TuxqAugd"

        data_to_hash = f"{key}|{txnid}|{amount}|{productinfo}|{firstname}|{email}|{udf1}|{udf2}|{udf3}|{udf4}|{udf5}||||||{si_details}|{salt}"
        hex_digest = self.encode_using_sha512(data_to_hash)
        print("hex digest::", hex_digest)

        payload = {
            "key": key, "txnid":txnid, "amount":amount,
            "productinfo":productinfo, "firstname":firstname,
            "email":email, "phone":phone,
            "surl": surl, "furl": furl,
            "api_version":api_version, "si":si, "pg":pg,
            "bankcode":bankcode, "ccnum":ccnum,
            "ccexpmon":ccexpmon, "ccexpyr":ccexpyr,
            "ccvv":ccvv, "ccname":ccname,
            "si_details":si_details,
            "hash":hex_digest
        }
        
        headers = {
            "accept": "text/plain",
            "content-type": "application/x-www-form-urlencoded"
        }

        response = requests.post(url, data=payload, headers=headers)
        print(dir(response))
        print(response.links)
        print(response.text)
        print(response.url)
    
    
    
