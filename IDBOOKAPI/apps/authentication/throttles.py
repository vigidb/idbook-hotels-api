"""
Rate limiting/throttling for authentication endpoints
"""
from rest_framework.throttling import UserRateThrottle, AnonRateThrottle


class SwitchGroupThrottle(UserRateThrottle):
    """
    Rate limiting for group switching endpoint.
    Limits to 10 switches per minute per user to prevent abuse.
    """
    scope = 'switch_group'
    rate = '10/min'


class LoginThrottle(AnonRateThrottle):
    """
    Rate limiting for login endpoint.
    Limits to 5 login attempts per minute per IP.
    """
    scope = 'login'
    rate = '5/min'

