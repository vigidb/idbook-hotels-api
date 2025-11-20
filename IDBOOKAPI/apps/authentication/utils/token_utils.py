"""
Utility functions for working with JWT tokens and active groups.
Optimized to avoid duplicate token decoding and database queries.
"""
import logging
from typing import Optional
from rest_framework_simplejwt.tokens import UntypedToken
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from django.core.cache import cache

from apps.authentication.utils.group_utils import (
    get_user_groups_cached,
    get_user_default_group,
    validate_user_group_membership
)

logger = logging.getLogger(__name__)


def get_active_group_from_token(token_string: str) -> Optional[str]:
    """
    Extract active_group from JWT token.
    
    Args:
        token_string: JWT token string (without 'Bearer ' prefix)
    
    Returns:
        str: Active group name if found, None otherwise
    """
    try:
        # Decode token
        untyped_token = UntypedToken(token_string)
        # Get active_group claim
        active_group = untyped_token.get('active_group')
        return active_group
    except (TokenError, InvalidToken, KeyError) as e:
        logger.debug(f"Error extracting active_group from token: {e}")
        return None


def get_active_group_from_request(request) -> Optional[str]:
    """
    Extract active_group from request's JWT token.
    Uses cached decoded token if available to avoid re-decoding.
    
    Args:
        request: Django request object
    
    Returns:
        str: Active group name if found, None otherwise
    """
    # Check if we've already decoded the token in this request
    if hasattr(request, '_cached_active_group'):
        return request._cached_active_group
    
    # Get token from Authorization header
    auth_header = request.META.get('HTTP_AUTHORIZATION', '')
    if not auth_header.startswith('Bearer '):
        return None
    
    token_string = auth_header.split(' ')[1]
    active_group = get_active_group_from_token(token_string)
    
    # Cache in request context to avoid re-decoding
    request._cached_active_group = active_group
    
    return active_group


def get_user_active_group(user, request=None) -> Optional[str]:
    """
    Get the active group for a user, checking token first, then falling back to default_group.
    
    Priority:
    1. active_group from JWT token (if request provided) - validated against current groups
    2. user.default_group
    3. First group from user.groups
    
    Args:
        user: User instance
        request: Optional request object to extract token from
    
    Returns:
        str: Active group name or None
    """
    if not user:
        return None
    
    # Try to get from token first
    if request:
        active_group = get_active_group_from_request(request)
        if active_group:
            # Validate that user actually has this group (from database for security)
            # This ensures groups removed from user are not honored
            # Use cache=True here for performance (token validation happens on every request)
            # The token was already validated when issued, this is just a safety check
            is_valid, error_msg = validate_user_group_membership(user, active_group, use_cache=True)
            if is_valid:
                return active_group
            else:
                logger.warning(
                    f"User {user.id} token has invalid active_group '{active_group}': {error_msg}. "
                    f"Falling back to default_group"
                )
    
    # Fall back to default_group
    return get_user_default_group(user)

