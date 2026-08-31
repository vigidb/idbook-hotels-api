"""
Utility functions for determining booking_source based on user, agent, and company.
"""
from apps.authentication.utils.token_utils import get_user_active_group
from apps.authentication.constants import CORPORATE_GROUPS, B2C_GROUPS
from apps.booking.utils.agent_linking_utils import get_agent_for_user


def determine_booking_source(user, agent=None, company_id=None, request=None):
    """
    Determine the appropriate booking_source based on user, agent, and company.
    
    Priority: AGENT > GUEST > CORPORATE > B2C > DIRECT
    
    Args:
        user: User instance (can be None for guest bookings)
        agent: AgentDetail instance (optional, will be detected if user is agent)
        company_id: Company ID (optional, will be checked from user if not provided)
        request: Request object (optional, for getting active_group from token)
    
    Returns:
        str: Booking source ('AGENT', 'GUEST', 'CORPORATE', 'B2C', or 'DIRECT')
    """
    # Priority 1: Agent booking
    if agent:
        return 'AGENT'
    
    # Check if user is an agent (if agent not explicitly provided)
    if user:
        detected_agent = get_agent_for_user(user)
        if detected_agent:
            return 'AGENT'
    
    # Priority 2: Guest booking (no user or user not authenticated)
    if not user or not hasattr(user, 'is_authenticated') or not user.is_authenticated:
        return 'GUEST'
    
    # Priority 3: Corporate booking
    active_group = get_user_active_group(user, request)
    default_group = active_group or getattr(user, 'default_group', None)
    
    # Check if corporate user (by group or company_id)
    if default_group in CORPORATE_GROUPS:
        return 'CORPORATE'
    
    # Check company_id from parameter or user
    final_company_id = company_id or getattr(user, 'company_id', None)
    if final_company_id:
        return 'CORPORATE'
    
    # Priority 4: B2C booking
    if default_group in B2C_GROUPS:
        return 'B2C'
    
    # Default: Direct booking
    return 'DIRECT'
