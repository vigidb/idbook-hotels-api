"""
Permission utility functions for RBAC + ABAC hybrid permission system.
"""
from typing import Optional, List, Dict, Tuple
from django.contrib.auth.models import Permission
from apps.authentication.models import User, UserRole, Role
from apps.org_managements.models import BusinessDetail


def get_permission_code(permission: Permission) -> str:
    """
    Convert Django Permission to custom permission code format.
    Examples:
        view_booking -> booking.view
        add_booking -> booking.create
        change_booking -> booking.update
        delete_booking -> booking.delete
    """
    codename = permission.codename
    app_label = permission.content_type.app_label
    
    # Map Django action prefixes to custom codes
    action_map = {
        'view': 'view',
        'add': 'create',
        'change': 'update',
        'delete': 'delete',
    }
    
    # Extract action and model name
    for action, custom_action in action_map.items():
        if codename.startswith(f"{action}_"):
            model_name = codename[len(action) + 1:]  # Remove "action_" prefix
            return f"{model_name}.{custom_action}"
    
    # Fallback: use app_label.codename
    return f"{app_label}.{codename}"


def get_permission_by_code(permission_code: str) -> Optional[Permission]:
    """
    Find Django Permission by custom permission code.
    Examples:
        booking.view -> Permission with codename='view_booking'
        booking.create -> Permission with codename='add_booking'
    """
    if '.' not in permission_code:
        return None
    
    model_name, action = permission_code.split('.', 1)
    
    # Map custom actions back to Django actions
    action_map = {
        'view': 'view',
        'create': 'add',
        'update': 'change',
        'delete': 'delete',
    }
    
    django_action = action_map.get(action, action)
    codename = f"{django_action}_{model_name}"
    
    return Permission.objects.filter(codename=codename).first()


def has_permission(
    user: User,
    permission_code: str,
    business: Optional[BusinessDetail] = None,
    obj=None
) -> bool:
    """
    Check if user has a specific permission in a business context.
    
    Args:
        user: User to check permissions for
        permission_code: Permission code (e.g., 'booking.view', 'accounts.refund')
        business: Business context (optional, will use user.business_id if not provided)
        obj: Object for association/region-based access checks (optional)
    
    Returns:
        True if user has the permission, False otherwise
    """
    # Get business from user if not provided
    if business is None and user.business_id:
        try:
            business = BusinessDetail.objects.get(id=user.business_id)
        except BusinessDetail.DoesNotExist:
            return False
    
    if business is None:
        return False
    
    # Get active UserRole records for user + business
    user_roles = UserRole.objects.filter(
        user=user,
        business=business,
        is_active=True
    ).select_related("role").prefetch_related("role__permissions")
    
    # Check if any role has the permission
    for user_role in user_roles:
        # Get permission code from PermissionMetadata
        role_permissions = user_role.role.permissions.all()
        
        for perm in role_permissions:
            # Convert Django permission to custom code format
            perm_code = get_permission_code(perm)
            
            # Check if permission code matches (exact match or Django codename match)
            if (perm_code == permission_code or 
                perm.codename == permission_code or 
                f"{perm.content_type.app_label}.{perm.codename}" == permission_code):
                # Check region/association scopes if obj provided
                if obj:
                    if not check_region_access(user_role, obj):
                        continue
                    if not check_association_access(user_role, obj):
                        continue
                return True
    
    return False


def get_user_permissions(user: User, business: Optional[BusinessDetail] = None) -> List[str]:
    """
    Get all permission codes for a user in a business context.
    
    Args:
        user: User to get permissions for
        business: Business context (optional)
    
    Returns:
        List of permission codes
    """
    if business is None and user.business_id:
        try:
            business = BusinessDetail.objects.get(id=user.business_id)
        except BusinessDetail.DoesNotExist:
            return []
    
    if business is None:
        return []
    
    user_roles = UserRole.objects.filter(
        user=user,
        business=business,
        is_active=True
    ).select_related("role").prefetch_related("role__permissions")
    
    permission_codes = set()
    
    for user_role in user_roles:
        role_permissions = user_role.role.permissions.all()
        
        for perm in role_permissions:
            # Convert Django permission to custom code format
            perm_code = get_permission_code(perm)
            permission_codes.add(perm_code)
    
    return sorted(list(permission_codes))


def check_region_access(user_role: UserRole, obj) -> bool:
    """
    Check if user_role has access to obj based on region scope.
    
    Args:
        user_role: UserRole instance
        obj: Object to check access for (should have region attribute or method)
    
    Returns:
        True if access allowed, False otherwise
    """
    # If no region restriction on user_role, allow access
    if not user_role.region:
        return True
    
    # Check if obj has region attribute
    obj_region = None
    if hasattr(obj, 'region'):
        obj_region = obj.region
    elif hasattr(obj, 'get_region'):
        obj_region = obj.get_region()
    
    if obj_region is None:
        # If obj doesn't have region, allow access (no restriction)
        return True
    
    # Check if regions match
    return str(obj_region).upper() == str(user_role.region).upper()


def check_association_access(user_role: UserRole, obj) -> bool:
    """
    Check if user_role has access to obj based on association scope.
    
    Args:
        user_role: UserRole instance
        obj: Object to check access for (should have company_id, hotel_id, or agent_id)
    
    Returns:
        True if access allowed, False otherwise
    """
    # If no association restriction on user_role, allow access
    if not user_role.association_id:
        return True
    
    # Check if obj has association attributes
    obj_association_id = None
    
    # Check for company_id
    if hasattr(obj, 'company_id'):
        obj_association_id = obj.company_id
    elif hasattr(obj, 'company') and hasattr(obj.company, 'id'):
        obj_association_id = obj.company.id
    
    # Check for hotel_id or property_id
    if obj_association_id is None:
        if hasattr(obj, 'hotel_id'):
            obj_association_id = obj.hotel_id
        elif hasattr(obj, 'property_id'):
            obj_association_id = obj.property_id
        elif hasattr(obj, 'property') and hasattr(obj.property, 'id'):
            obj_association_id = obj.property.id
    
    # Check for agent_id
    if obj_association_id is None:
        if hasattr(obj, 'agent_id'):
            obj_association_id = obj.agent_id
        elif hasattr(obj, 'agent') and hasattr(obj.agent, 'id'):
            obj_association_id = obj.agent.id
    
    if obj_association_id is None:
        # If obj doesn't have association, allow access (no restriction)
        return True
    
    # Check if association IDs match
    return obj_association_id == user_role.association_id


def get_user_roles_for_business(user: User, business: Optional[BusinessDetail] = None) -> List[UserRole]:
    """
    Get all active UserRole records for a user in a business.
    
    Args:
        user: User to get roles for
        business: Business context (optional)
    
    Returns:
        List of UserRole instances
    """
    if business is None and user.business_id:
        try:
            business = BusinessDetail.objects.get(id=user.business_id)
        except BusinessDetail.DoesNotExist:
            return []
    
    if business is None:
        return []
    
    return list(
        UserRole.objects.filter(
            user=user,
            business=business,
            is_active=True
        ).select_related("role", "business", "assigned_by")
    )


def can_manage_user(admin_user: User, target_user: User, business: Optional[BusinessDetail] = None) -> bool:
    """
    Check if admin_user can manage target_user based on admin scope.
    
    Args:
        admin_user: Admin user trying to manage
        target_user: Target user to be managed
        business: Business context (optional)
    
    Returns:
        True if admin_user can manage target_user, False otherwise
    """
    # Super admin can manage anyone
    if admin_user.is_superuser:
        return True
    
    # Get admin scope
    scope = get_admin_scope(admin_user)
    
    if not scope:
        return False
    
    # Check if target_user is within admin's scope
    if scope.get('business_id'):
        if target_user.business_id != scope['business_id']:
            return False
    
    if scope.get('company_id'):
        if target_user.company_id != scope['company_id']:
            return False
    
    # For hotel and agent, we'd need additional checks based on associations
    # This is a simplified version - can be enhanced based on specific models
    
    return True


def get_admin_scope(user: User) -> Dict:
    """
    Get admin scope (business_id, company_id, hotel_id, agent_id) for a user.
    
    Args:
        user: User to get scope for
    
    Returns:
        Dictionary with scope information
    """
    scope = {}
    
    if user.business_id:
        scope['business_id'] = user.business_id
    
    if user.company_id:
        scope['company_id'] = user.company_id
    
    # Additional scope extraction can be added here based on user's roles
    # For now, using direct user fields
    
    return scope


def filter_users_by_scope(queryset, admin_user: User):
    """
    Filter user queryset by admin's scope.
    
    Args:
        queryset: User queryset to filter
        admin_user: Admin user whose scope to apply
    
    Returns:
        Filtered queryset
    """
    # Super admin sees all
    if admin_user.is_superuser:
        return queryset
    
    scope = get_admin_scope(admin_user)
    
    if scope.get('business_id'):
        queryset = queryset.filter(business_id=scope['business_id'])
    
    if scope.get('company_id'):
        queryset = queryset.filter(company_id=scope['company_id'])
    
    return queryset


def validate_role_assignment(
    admin_user: User,
    target_user: User,
    role: Role,
    business: Optional[BusinessDetail] = None
) -> Tuple[bool, Optional[str]]:
    """
    Validate if admin_user can assign role to target_user.
    
    Args:
        admin_user: Admin user trying to assign role
        target_user: Target user to assign role to
        role: Role to assign
        business: Business context (optional)
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    # Super admin can assign any role
    if admin_user.is_superuser:
        return True, None
    
    # Check if admin can manage target user
    if not can_manage_user(admin_user, target_user, business):
        return False, "You don't have permission to manage this user"
    
    # Get admin scope
    scope = get_admin_scope(admin_user)
    
    # Business admin can assign roles in their business
    if scope.get('business_id'):
        if role.business and role.business.id != scope['business_id']:
            return False, "You can only assign roles from your business"
        if role.is_system_role and role.group:
            # Business admin can use system roles
            pass
    
    # Corporate/Hotelier/Agent admins can only assign system roles from their group
    if scope.get('company_id') or scope.get('hotel_id') or scope.get('agent_id'):
        if not role.is_system_role:
            return False, "You can only assign system roles"
        # Additional group validation can be added here
    
    return True, None
