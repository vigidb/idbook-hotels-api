"""
Custom permissions for booking viewsets
"""

from rest_framework import permissions
from apps.booking.utils.booking_utils import validate_guest_access_token


class BookingRetrievePermission(permissions.BasePermission):
    """
    Custom permission that allows:
    1. Authenticated users (JWT)
    2. Users with valid guest tokens
    """

    def has_permission(self, request, view):
        # Allow authenticated users (JWT tokens)
        if request.user and request.user.is_authenticated:
            # Check if they're using a JWT token (not a guest token)
            auth_header = request.META.get("HTTP_AUTHORIZATION", "")
            if auth_header.startswith("Bearer "):
                token_string = auth_header.split(" ", 1)[1]
                # If it's a guest token, don't allow here (will be handled below)
                if not (
                    token_string.startswith("guest_")
                    or token_string.startswith("user_")
                ):
                    return True

        # Check for guest token in Authorization header
        auth_header = request.META.get("HTTP_AUTHORIZATION", "")
        if auth_header.startswith("Bearer "):
            token_string = auth_header.split(" ", 1)[1]
            # Check if it's a guest token (starts with 'guest_' or 'user_')
            if token_string.startswith("guest_") or token_string.startswith("user_"):
                booking = validate_guest_access_token(token_string)
                if booking:
                    # Set the user to booking.user to allow access
                    request.user = booking.user
                    # Mark as guest access
                    request._guest_booking = booking
                    request._is_guest_access = True
                    return True

        # Check for guest token in query params
        guest_token = request.query_params.get("guest_token")
        if guest_token:
            booking = validate_guest_access_token(guest_token)
            if booking:
                request.user = booking.user
                request._guest_booking = booking
                request._is_guest_access = True
                return True

        # Default: require authentication
        return False

    def has_object_permission(self, request, view, obj):
        # If this is a guest token access, verify the booking matches
        if hasattr(request, "_guest_booking"):
            return request._guest_booking.id == obj.id

        # For authenticated users, check if they own the booking
        if request.user and request.user.is_authenticated:
            return obj.user == request.user

        return False
