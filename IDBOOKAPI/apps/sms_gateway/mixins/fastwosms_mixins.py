import requests

from django.conf import settings


class Fast2SmsMixin:
    sms_url = "https://www.fast2sms.com/dev/bulkV2"

    def post_dlt_otpsms(self, number, otp):
        #1201163403990155099
##        numbers = "9999999999,8888888888"
        # IDHTLS, 712893
        api_key = settings.FAST2SMS_APIKEY
        dlt_sender_id = settings.FAST_DLT_SENDER_ID
        message_id = settings.FAST_MESSAGE_ID
        payload = f"sender_id={dlt_sender_id}&message={message_id}&variables_values={otp}&route=dlt&numbers={number}"
        headers = {
            'authorization': api_key,
            'Content-Type': "application/x-www-form-urlencoded",
            'Cache-Control': "no-cache",
            }

        response = requests.request("POST", self.sms_url, data=payload, headers=headers)
        print("status code::", response.status_code)

        print(response.json())
        return response
