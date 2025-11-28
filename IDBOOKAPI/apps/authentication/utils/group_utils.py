"""
Centralized utilities for user group validation and management.
Eliminates code duplication and provides consistent group handling.
"""
import logging
from typing import Optional, List, Tuple
from django.core.cache import cache
from django.db.models import QuerySet

logger = logging.getLogger(__name__)


def get_user_groups_cached(user) -> List[str]:
    """
    Get user's groups with caching to avoid repeated database queries.
    
    Args:
        user: User instance
    
    Returns:
        List of group names
    """
    # Handle AnonymousUser
    if not user or not user.is_authenticated:
        return []
    
    cache_key = f"user_{user.id}_groups"
    groups = cache.get(cache_key)
    
    if groups is None:
        # Fetch from database
        groups = list(user.groups.values_list('name', flat=True))
        # Cache for 5 minutes
        cache.set(cache_key, groups, 300)
    
    return groups


def invalidate_user_groups_cache(user_id: int):
    """
    Invalidate cached groups for a user.
    Call this when user's groups are updated.
    
    Args:
        user_id: User ID
    """
    cache_key = f"user_{user_id}_groups"
    cache.delete(cache_key)


def validate_user_group_membership(user, group_name: str, use_cache: bool = True) -> Tuple[bool, Optional[str]]:
    """
    Validate that a user belongs to a specific group.
    
    Args:
        user: User instance
        group_name: Group name to validate
        use_cache: Whether to use cached groups (False for security-critical operations)
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not user:
        return False, "User is required"
    
    # Handle AnonymousUser
    if not user.is_authenticated:
        return False, "User is not authenticated"
    
    if not user.is_active:
        return False, "User is not active"
    
    # For security-critical operations (like group switching), fetch fresh from DB
    if use_cache:
        user_groups = get_user_groups_cached(user)
    else:
        # Fetch fresh from database to ensure we have latest groups
        user_groups = list(user.groups.values_list('name', flat=True))
    
    # Safely access default_group (only for authenticated users)
    user_default_group = getattr(user, 'default_group', None) or ''
    
    # Check if user belongs to the group
    if group_name in user_groups or group_name == user_default_group:
        return True, None
    
    return False, f"User does not belong to group: {group_name}"


def is_corporate_user(active_group: Optional[str]) -> bool:
    """
    Check if active group indicates a corporate user.
    
    Args:
        active_group: Active group name
    
    Returns:
        bool: True if corporate user
    """
    from apps.authentication.constants import CORPORATE_GROUPS
    return active_group in CORPORATE_GROUPS if active_group else False


def is_b2c_user(active_group: Optional[str]) -> bool:
    """
    Check if active group indicates a B2C user.
    
    Args:
        active_group: Active group name
    
    Returns:
        bool: True if B2C user
    """
    from apps.authentication.constants import B2C_GROUPS
    return active_group in B2C_GROUPS if active_group else False


def get_user_default_group(user) -> Optional[str]:
    """
    Get user's default group with fallback logic.
    
    Args:
        user: User instance
    
    Returns:
        Default group name or None
    """
    # Handle AnonymousUser
    if not user or not user.is_authenticated:
        return None
    
    # Safely access default_group (only for authenticated users)
    default_group = getattr(user, 'default_group', None)
    if default_group:
        return default_group
    
    user_groups = get_user_groups_cached(user)
    if user_groups:
        return user_groups[0]
    
    return None

