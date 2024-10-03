from django.conf import settings
import math, random

def generate_otp(no_digits=4):
    digits = "0123456789"
    OTP = ""
    for i in range(no_digits):
        OTP += digits[math.floor(random.random()*10)]
    return OTP

