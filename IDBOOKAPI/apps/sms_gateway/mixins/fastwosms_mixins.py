import requests

from django.conf import settings
from apps.org_resources.models import MessageTemplate
from apps.log_management.models import SmsOtpLog, SmsNotificationLog
from IDBOOKAPI.basic_resources import SMS_TYPES_CHOICES

class Fast2SmsMixin:
    sms_url = "https://www.fast2sms.com/dev/bulkV2"

    def post_dlt_otpsms(self, number, otp, template_code=None):
        #1201163403990155099
##        numbers = "9999999999,8888888888"
        # IDHTLS, 712893
        api_key = settings.FAST2SMS_APIKEY
        dlt_sender_id = settings.FAST_DLT_SENDER_ID
        message_id = get_message_template_by_code(template_code)
        # message_id = settings.FAST_MESSAGE_ID
        payload = f"sender_id={dlt_sender_id}&message={message_id}&variables_values=User|{otp}&route=dlt&numbers={number}"
        headers = {
            'authorization': api_key,
            'Content-Type': "application/x-www-form-urlencoded",
            'Cache-Control': "no-cache",
            }

        response = requests.request("POST", self.sms_url, data=payload, headers=headers)
        print("status code::", response.status_code)

        print(response.json())
        return response

def get_message_template_by_code(template_code):

    try:
        template = MessageTemplate.objects.get(template_code=template_code)
        return template.message_id
    except MessageTemplate.DoesNotExist:
        print(f"Message template with code {template_code} not found")
        return None, None

def send_template_sms(mobile_number, template_code, variables_values):

    try:
        # Get message_id from template code
        message_id = get_message_template_by_code(template_code)
        print("message_id, template_code", message_id, template_code)
        if not message_id:
            print(f"Failed to get message_id for template_code {template_code}")
            return None
            
        sms_url = "https://www.fast2sms.com/dev/bulkV2"
        
        api_key = settings.FAST2SMS_APIKEY
        dlt_sender_id = settings.FAST_DLT_SENDER_ID
        
        payload = f"sender_id={dlt_sender_id}&message={message_id}&variables_values={variables_values}&route=dlt&numbers={mobile_number}"
        headers = {
            'authorization': api_key,
            'Content-Type': "application/x-www-form-urlencoded",
            'Cache-Control': "no-cache",
        }
        
        response = requests.request("POST", sms_url, data=payload, headers=headers)
        print(f"Template SMS status code: {response.status_code}")
        print("response",response.json())
        if response.status_code != 200:
            SmsNotificationLog.objects.create(
                mobile_number=mobile_number,
                sms_for=template_code if template_code in dict(SMS_TYPES_CHOICES) else 'other',
                response=response.json()
            )
        # otp_related_templates = ['LOGIN_OTP', 'VERIFY_OTP', 'SIGNUP_OTP']
        
        # if template_code in otp_related_templates and response.status_code != 200:
        #     SmsOtpLog.objects.create(
        #         mobile_number=mobile_number,
        #         response=response.json()
        #     )
        
        return response
    except Exception as e:
        print(f"Error sending template SMS: {e}")
        return None