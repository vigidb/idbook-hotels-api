"""
Utility functions for handling contact information in bookings
"""
from typing import Tuple, Optional
from apps.booking.models import Booking


def get_booking_contact_info(booking: Booking) -> Tuple[Optional[str], Optional[str]]:
    """
    Get contact information (mobile_number, name) for a booking.
    Priority:
    1. Contact info stored in flight_booking.selected_flight_data or search_session_data
    2. User profile (booking.user.mobile_number, booking.user.name)
    
    Args:
        booking: Booking instance
        
    Returns:
        Tuple of (mobile_number, name) or (None, None) if not found
    """
    if not booking:
        return None, None
    
    mobile_number = None
    name = None
    
    # For flight bookings, check if contact info is stored in flight_booking data
    if booking.flight_booking:
        # Check selected_flight_data for contact info
        selected_data = booking.flight_booking.selected_flight_data or {}
        contact_info = selected_data.get('contact') or {}
        
        if not contact_info:
            # Check search_session_data
            search_data = booking.flight_booking.search_session_data or {}
            contact_info = search_data.get('contact') or {}
        
        if contact_info:
            mobile_number = contact_info.get('phone') or contact_info.get('mobile_number')
            # Name might be in contact or from first passenger
            name = contact_info.get('name')
    
    # Fallback to user profile
    if booking.user:
        if not mobile_number and booking.user.mobile_number:
            mobile_number = booking.user.mobile_number
        if not name and booking.user.name:
            name = booking.user.name
    
    return mobile_number, name


def update_user_contact_info(user, contact_email: str = None, contact_phone: str = None, 
                             contact_name: str = None) -> bool:
    """
    Update user profile with contact information from booking request.
    Only updates if the field is provided and different from existing value.
    
    Args:
        user: User instance
        contact_email: Email from booking request
        contact_phone: Phone number from booking request
        contact_name: Name from booking request
        
    Returns:
        True if any field was updated, False otherwise
    """
    if not user:
        return False
    
    updated = False
    update_fields = []
    
    # Update email if provided and different
    if contact_email and contact_email.strip() and user.email != contact_email:
        user.email = contact_email.strip()
        update_fields.append('email')
        updated = True
    
    # Update mobile number if provided and different
    if contact_phone and contact_phone.strip():
        # Normalize phone number (remove spaces, dashes, etc.)
        normalized_phone = contact_phone.strip().replace(' ', '').replace('-', '').replace('(', '').replace(')', '')
        if not user.mobile_number or user.mobile_number != normalized_phone:
            user.mobile_number = normalized_phone
            update_fields.append('mobile_number')
            updated = True
    
    # Update name if provided and different
    if contact_name and contact_name.strip() and user.name != contact_name.strip():
        user.name = contact_name.strip()
        update_fields.append('name')
        updated = True
    
    # Save if any fields were updated
    if updated and update_fields:
        user.save(update_fields=update_fields)
    
    return updated

