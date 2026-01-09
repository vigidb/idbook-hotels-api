"""
Custom JWT Token classes with active group/role support
Allows users to have different active groups in different sessions
"""

import logging
from rest_framework_simplejwt.tokens import RefreshToken, AccessToken
from apps.authentication.utils.group_utils import (
    get_user_groups_cached,
    get_user_default_group,
    validate_user_group_membership,
)
from apps.authentication.utils.permission_utils import (
    get_user_permissions,
    get_user_roles_for_business,
)
from apps.org_managements.models import BusinessDetail

logger = logging.getLogger(__name__)


class CustomAccessToken(AccessToken):
    """
    Custom access token that includes active_group, business_id, permissions, and scopes.
    Note: company_id is NOT stored in token to avoid stale data.
    Always fetch from database when needed.
    """

    pass


class CustomRefreshToken(RefreshToken):
    """
    Custom refresh token that includes active_group in the token claims.
    This allows users to have different active groups in different sessions.

    Security Note:
    - company_id is NOT stored in token (fetched from DB when needed)
    - active_group is validated against current user groups
    """

    # Set the access token class to our custom one
    access_token_class = CustomAccessToken

    @classmethod
    def for_user(cls, user, active_group=None):
        """
        Generate a token for a user with optional active_group.

        Args:
            user: User instance
            active_group: Optional active group name. If not provided, uses user.default_group

        Returns:
            CustomRefreshToken instance with active_group claim
        """
        if not user or not user.is_active:
            raise ValueError("Cannot create token for inactive user")

        token = super().for_user(user)

        # Determine active group with validation
        if active_group:
            # Validate that user belongs to this group (from database, not cache for security)
            is_valid, error_msg = validate_user_group_membership(
                user, active_group, use_cache=False
            )
            if not is_valid:
                logger.warning(
                    f"User {user.id} attempted to use invalid group {active_group}: {error_msg}. "
                    f"Falling back to default_group"
                )
                # Fall back to default_group if validation fails
                active_group = get_user_default_group(user)
        else:
            # Use default_group if no active_group specified
            active_group = get_user_default_group(user)

        # Add active_group to both refresh and access token claims
        if active_group:
            token["active_group"] = active_group
            # Also add to access token
            token.access_token["active_group"] = active_group
            logger.info(
                f"Generated token for user {user.id} with active_group: {active_group}"
            )

        # Add business_id, permissions, and scopes to token
        business = None
        if user.business_id:
            try:
                business = BusinessDetail.objects.get(id=user.business_id)
            except BusinessDetail.DoesNotExist:
                pass

        if business:
            token["business_id"] = business.id
            token.access_token["business_id"] = business.id

            # Get user permissions for this business
            permissions = get_user_permissions(user, business)
            token["permissions"] = permissions
            token.access_token["permissions"] = permissions

            # Get scopes (regions and association_ids) from user roles
            user_roles = get_user_roles_for_business(user, business)
            regions = set()
            association_ids = set()

            for user_role in user_roles:
                if user_role.region:
                    regions.add(user_role.region)
                if user_role.association_id:
                    association_ids.add(str(user_role.association_id))

            scopes = {
                "regions": sorted(list(regions)) if regions else [],
                "association_ids": sorted(list(association_ids)) if association_ids else [],
            }

            token["scopes"] = scopes
            token.access_token["scopes"] = scopes

            logger.info(
                f"Added business_id={business.id}, permissions={len(permissions)}, "
                f"scopes={scopes} to token for user {user.id}"
            )

        # NOTE: company_id is NOT stored in token to avoid stale data
        # Always fetch from database when needed

        return token

    @classmethod
    def for_user_with_group(cls, user, group_name):
        """
        Convenience method to create token with specific active group.

        Args:
            user: User instance
            group_name: Group name to set as active

        Returns:
            CustomRefreshToken instance
        """
        return cls.for_user(user, active_group=group_name)
