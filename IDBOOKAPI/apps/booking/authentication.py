"""
Custom authentication for booking viewsets to support guest tokens
"""

from rest_framework import authentication
from rest_framework.exceptions import AuthenticationFailed
from apps.booking.utils.booking_utils import validate_guest_access_token


class BookingAuthentication(authentication.BaseAuthentication):
    """
    Custom authentication that supports both JWT tokens and guest tokens.
    Guest tokens are checked first, then falls back to default JWT authentication.
    """

    def authenticate(self, request):
        # Check for guest token in Authorization header
        auth_header = request.META.get("HTTP_AUTHORIZATION", "")
        if auth_header.startswith("Bearer "):
            token_string = auth_header.split(" ", 1)[1]
            # Check if it's a guest token (starts with 'guest_' or 'user_')
            if token_string.startswith("guest_") or token_string.startswith("user_"):
                booking = validate_guest_access_token(token_string)
                if booking:
                    # Return the user and None (no token needed)
                    # Store booking in request for permission checks
                    request._guest_booking = booking
                    request._is_guest_access = True
                    return (booking.user, None)

        # Check for guest token in query params
        guest_token = request.query_params.get("guest_token")
        if guest_token:
            booking = validate_guest_access_token(guest_token)
            if booking:
                request._guest_booking = booking
                request._is_guest_access = True
                return (booking.user, None)

        # Return None to let other authentication classes handle it (JWT, etc.)
        return None
