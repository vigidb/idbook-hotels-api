import hashlib
import requests, json
from django.conf import settings

class PayUMixin:

    def encode_using_sha512(self, data):
        hash_object = hashlib.sha512()
        hash_object.update(data.encode('utf-8'))
        hex_digest = hash_object.hexdigest()
        return hex_digest


    def recurring_payment_notification(self, var1):

        # url = "https://info.payu.in/merchant/"
##        url = "https://test.payu.in/merchant/postservice.php?form=2"
        url = settings.PAYU_MERCH_URL + "/postservice.php?form=2"

        #7043873219

        key = settings.PAYU_KEY
        command = "pre_debit_SI" 
##        var1 = {"authPayuId":"403993715533858347","requestId":"TNX589","debitDate":"2025-05-09","amount":"500",
##                "invoiceDisplayNumber":"INV3RTU6"}
        var1 = json.dumps(var1)

        salt = settings.PAYU_SALT

        data_to_hash = f"{key}|{command}|{var1}|{salt}"
        hex_digest = self.encode_using_sha512(data_to_hash)
        print("hex digest::", hex_digest)
        

        payload = {
            "key": key,
            "var1": var1,
            "command": command,
            "hash": hex_digest
        }
        headers = {
            "accept": "application/json",
            "content-type": "application/x-www-form-urlencoded"
        }
        print("payload::", payload)

        response = requests.post(url, data=payload, headers=headers)

        return response

    def recurring_payment_transaction(self, var1):

        # url = "https://info.payu.in/merchant/"
        #url = "https://test.payu.in/merchant/postservice.php?form=2"
        url = settings.PAYU_MERCH_URL + "/postservice.php?form=2"

        #7043873219

        key = settings.PAYU_KEY
        command = "si_transaction"
        
##        var1 = {"authpayuid":"403993715533858347","txnid":"TNX58908", "amount":"500",
##                "invoiceDisplayNumber":"M4kOsEOAj1","phone":"9567068425","email":"sonu@idbookhotels.com"}
        var1 = json.dumps(var1)

        salt = settings.PAYU_SALT

        data_to_hash = f"{key}|{command}|{var1}|{salt}"
        hex_digest = self.encode_using_sha512(data_to_hash)
        print("hex digest::", hex_digest)
        

        payload = {
            "key": key,
            "var1": var1,
            "command": command,
            "hash": hex_digest
        }
        headers = {
            "accept": "application/json",
            "content-type": "application/x-www-form-urlencoded"
        }
        print("payload::", payload)

        response = requests.post(url, data=payload, headers=headers)

        return response


    def check_mandate(self, auth_id, request_id):
        # url = "https://test.payu.in/merchant/postservice?form=2"
        url = settings.PAYU_MERCH_URL + "/postservice.php?form=2"
        key = settings.PAYU_KEY
        command = "check_mandate_status"

        var1 = {"authPayuId":auth_id, "requestId": request_id}
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

        # url = "https://test.payu.in/merchant/postservice?form=2"
        url = settings.PAYU_MERCH_URL + "/postservice.php?form=2"
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

        url = settings.PAYU_URL
        
##        si_details = {"billingAmount": "200.00","billingCurrency": "INR",
##                      "billingCycle": "MONTHLY","billingInterval": 1,
##                      "paymentStartDate": "2025-04-30",
##                      "paymentEndDate": "2025-07-29", "siTokenRequestor":1}
        # convert dict to json
        si_details = json.dumps(si_details)

##        params = {"key":settings.PAYU_KEY, "txnid":"ST0189z22", "amount":200.00,
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

        # surl = settings.CALLBACK_URL + "/api/v1/org-resources/user-subscription/payu-sucess/"
        # furl = settings.CALLBACK_URL + "/api/v1/org-resources/user-subscription/payu-sucess/"
        surl = "https://www.idbookhotels.com/api/payment"
        # surl = "https://www.idbookhotels.com/payment/status/success?type=SUBSCRIPTION"
        furl = "https://www.idbookhotels.com/api/payment"
        # furl = "https://www.idbookhotels.com/payment/status/failed?type=SUBSCRIPTION"

        api_version = 7
        si =  1  # for recurring payment

        salt = settings.PAYU_SALT

        data_to_hash = f"{key}|{txnid}|{amount}|{productinfo}|{firstname}|{email}|{udf1}|{udf2}|{udf3}|{udf4}|{udf5}||||||{si_details}|{salt}"
        hex_digest = self.encode_using_sha512(data_to_hash)
        print("hex digest::", hex_digest)
        
        payload = {
            "key": key, "txnid":txnid, "amount":amount,
            "productinfo":productinfo, "firstname":firstname,
            "email":email, "phone":phone,
            "surl": surl, "furl": furl,
            "api_version":api_version,
            "si":si, #"free_trial":1,
            "si_details":si_details,
            "hash":hex_digest
        }
        
        headers = {
            "accept": "application/json",
            "content-type": "application/x-www-form-urlencoded"
        }


        response = requests.post(url, data=payload, headers=headers)
        return response

    def zion_data_to_hash(self):
        key = "QE93eb"
        salt = settings.PAYU_SALT
        data_to_hash = f"merchantId:{key}|subscriptionId:403993715533837880|{salt}"
        hex_digest = self.encode_using_sha512(data_to_hash)
        print("hex_digest:", hex_digest)


    def cancel_subscription_card(self, authpayuid, requestid):
        url = settings.PAYU_URL

##        403993715533903533
##        authPayuId
##        
        si_details = {"authpayuid":"403993715533891316", "action":"delete"}
##        si_details = {"authPayuId":"403993715533903533", "action":"delete"}
        # convert dict to json
        si_details = json.dumps(si_details)

        params = {"key":settings.PAYU_KEY, "txnid":"ST0189y22", "amount":500.00,
                  "udf1":"", "udf2":"", "udf3":"", "udf4":"", "udf5":"",
                  "subscription_name":"subscription", "firstname":"Sonu",
                  "email":"sonu@idbookhotels.com", "phone":"9567068425"
                  }

        key, txnid = params.get("key", ""), params.get("txnid", "")
        amount = params.get("amount", 0)
        
        udf1, udf2, udf3 = params.get("udf1", ""), params.get("udf2", ""), params.get("udf3", "")
        udf4, udf5 =  params.get("udf4", ""), params.get("udf5", "")
        
        productinfo = params.get("subscription_name", "")
        firstname = params.get("firstname", "")
        email, phone = params.get("email", ""), params.get("phone", "")

        # surl = settings.CALLBACK_URL + "/api/v1/org-resources/user-subscription/payu-sucess/"
        # furl = settings.CALLBACK_URL + "/api/v1/org-resources/user-subscription/payu-sucess/"
        surl = "https://www.idbookhotels.com/api/payment"
        # surl = "https://www.idbookhotels.com/payment/status/success?type=SUBSCRIPTION"
        furl = "https://www.idbookhotels.com/api/payment"
        # furl = "https://www.idbookhotels.com/payment/status/failed?type=SUBSCRIPTION"

        api_version = 7
        si =  3  # for recurring payment

        salt = settings.PAYU_SALT

        data_to_hash = f"{key}|{txnid}|{amount}|{productinfo}|{firstname}|{email}|{udf1}|{udf2}|{udf3}|{udf4}|{udf5}||||||{si_details}|{salt}"
        hex_digest = self.encode_using_sha512(data_to_hash)
        print("hex digest::", hex_digest)
        
        payload = {
            "key": key, "txnid":txnid, "amount":amount,
            "productinfo":productinfo, "firstname":firstname,
            "email":email, "phone":phone,
            "surl": surl, "furl": furl,
            "api_version":api_version,
            "si":si, #"free_trial":1,
            "pg":"CC",
            "bankcode":"CC", #MAST
            "ccnum":"5506900480000008",
            "ccname":"Sonu",
            "ccvv":"123",
            "ccexpmon":"05",
            "ccexpyr":"2025",
            "si_details":si_details,
            "hash":hex_digest
        }
        print("payload", payload)


##        payload = 'key=QE93eb&txnid=ST0189y22&amount=500.0&productinfo=subscription&firstname=Sonu&\
##email=sonu@idbokhotels.com&phone=9567068425&surl=https://www.idbookhotels.com/api/payment&\
##furl=https://www.idbookhotels.com/api/payment&api_version=7&si=3&pg=CC&bankcode=CC&ccnum=5506900480000008&ccname=Sonu&\
##ccvv=123&ccexpmom=05&ccexpyr=2025&\
##si_details={"authpayuid": "403993715533891316", "action": "delete"}&\
##hash=43f713336d522f2f1ad47dd4fafebecd0961b784853dc27b82c84166bae02314178edb73678fcaebf4abacb8973b77eb296c83513c915c45540d2bc79eb2e0b9'
##
        
        headers = {
            "accept": "application/json",
            "content-type": "application/x-www-form-urlencoded"
        }

        print("payload::", payload)


        response = requests.post(url, data=payload, headers=headers)
        return response
        


    def cancel_subscription(self, authpayuid, requestid):

        #url = "https://test.payu.in/merchant/postservice.php?form=2"#settings.PAYU_URL
        url = settings.PAYU_MERCH_URL + "/postservice.php?form=2"

        # 403993715533837880
        #authpayuid = "403993715533829815"
        var1 = {"authPayuId": authpayuid,
                "requestId": requestid}
        # convert dict to json
        var1 = json.dumps(var1)

        key = settings.PAYU_KEY
        salt = settings.PAYU_SALT
        command = "mandate_revoke"

        data_to_hash = f"{key}|{command}|{var1}|{salt}"
        hex_digest = self.encode_using_sha512(data_to_hash)
        print("hex digest::", hex_digest)
        
        payload = {
            "key": key,
            "command":command,
            "var1":var1,
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


class PayUPayOutMixin:

    client_id = "75a4e32b06257d1e02a56099a1d06c87f1b8551c9653fe7e7f3a77b9039c86e3"
    client_secret = "1da115b1cdda89d4400f277af5925779e8e507a4814641825fccf0ce1cb9ad43"

    def generate_token_using_clientid(self):

        url = "https://uat-accounts.payu.in/oauth/token"

        payload = {
            "grant_type":"client_credentials",
            "client_id":"75a4e32b06257d1e02a56099a1d06c87f1b8551c9653fe7e7f3a77b9039c86e3",
            "client_secret":"1da115b1cdda89d4400f277af5925779e8e507a4814641825fccf0ce1cb9ad43",
            "scope":"create_payout_transactions"
            }


        headers = {
            "cache-control": "no-cache",
            "content-type": "application/x-www-form-urlencoded"
        }

        response = requests.post(url, data=payload, headers=headers)
        return response

    def get_account_details(self):

        url = "https://uatoneapi.payu.in/payout/merchant/getAccountDetail"

        headers = {
            "cache-control": "no-cache",
            "content-type": "application/x-www-form-urlencoded",
            "authorization": "bearer aab9dc927c4a68af7eb95ef694f0b48bb731c5a1a7111786d6658d774db14188",
            "payoutMerchantId": "1111123"
        }

        response = requests.get(url, headers=headers)
        return response

    def initiate_transfer_api(self, payload):
        url = "https://uatoneapi.payu.in/payout/v2/payment"

##        payload = [
##            {
##                "disableApprovalFlow": True,
##                "beneficiaryIfscCode": "SBIN0005943",
##                "beneficiaryAccountNumber": "012345678912",
##                "beneficiaryName": "Ashish Kumar",
##                "beneficiaryMobile": "9567068425",
##                "beneficiaryEmail": "sonu@idbookhotels.com",
##                "purpose": "Payment from company",
##                "amount": 100,
##                "batchId": "1",
##                "merchantRefId": "123X1",
##                "paymentType": "IMPS",
##                "retry": False
##            }
##        ]
        
        headers = {
            "pid": "245",
            "content-type": "application/json"
        }

        response = requests.post(url, json=payload, headers=headers)
        return response

    def check_transfer_status(self):
        url = "https://uatoneapi.payu.in/payout/payment/listTransactions"

        payload = {
            #"transferStatus": "SUCCESS",
            "merchantRefId": "123X1",
            "batchId": 1
        }
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "payoutMerchantId": "65454333",
            "authorization": "Bearer hgdhgdgh"
        }

        response = requests.post(url, data=payload, headers=headers)
        return response


        

        

        
    

    
    
    
    
