from rest_framework.permissions import BasePermission
from django.contrib.contenttypes.models import ContentType
from apps.authentication.utils.permission_utils import has_permission
from apps.org_managements.models import BusinessDetail


def get_related_model_codenames(queryset):
    all_related_codename = set()
    model_class = queryset.model
    content_type = ContentType.objects.get_for_model(model_class)

    # # get all related model actions
    # for field in model_class._meta.get_fields():
    #     if field.is_relation and field.concrete:
    #         related_model_class = field.related_model
    #         related_content_type = ContentType.objects.get_for_model(related_model_class)
    #
    #         actions = ["add", "change", "view"]
    #         for action in actions:
    #             codename = f"{action}_{related_content_type.model}"
    #             all_related_codename.add(codename)

    actions = ["add", "change", "view"]
    content = [f"{action}_{content_type.model}" for action in actions]
    all_related_codename.update(content)

    return all_related_codename


class HasRoleModelPermission(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        if not user.is_authenticated:
            return False

        # Superuser and staff have full access
        if user.is_superuser or user.is_staff:
            return True

        codenames = get_related_model_codenames(view.queryset)
        if request.method == "GET":
            filtered_codenames = {
                action for action in codenames if action.startswith("view_")
            }
        elif request.method == "POST":
            filtered_codenames = {
                action for action in codenames if action.startswith("add_")
            }
        elif request.method == "PUT" or request.method == "PATCH":
            filtered_codenames = {
                action for action in codenames if action.startswith("change_")
            }
        elif request.method == "DELETE":
            filtered_codenames = {
                action for action in codenames if action.startswith("delete_")
            }
        else:
            filtered_codenames = []

        # Check if user has required permissions through roles
        user_roles = user.roles.all()
        if user_roles and user_roles.filter(
            permissions__codename__in=filtered_codenames
        ):
            return True

        return False


class AnonymousCanViewOnlyPermission(BasePermission):
    def has_permission(self, request, view):
        if request.method == "GET" and not request.user.is_authenticated:
            # Allow anonymous users to perform GET requests (view permissions)
            return True
        elif request.user.is_authenticated:
            user = request.user
            codenames = get_related_model_codenames(view.queryset)

            if request.method == "GET":
                filtered_codenames = {
                    action for action in codenames if action.startswith("view_")
                }
            elif request.method == "POST":
                filtered_codenames = {
                    action for action in codenames if action.startswith("add_")
                }
            elif request.method in ("PUT", "PATCH"):
                filtered_codenames = {
                    action for action in codenames if action.startswith("change_")
                }
            else:
                filtered_codenames = []

            user_roles = user.roles.all()
            if user_roles and user_roles.filter(
                permissions__codename__in=filtered_codenames
            ):
                return True

        return False


class IsOwnerOrSuperAdmin(BasePermission):
    """
    Custom permission to only allow owners of an object or super admins to edit/delete it.
    For list and retrieve, allows authenticated users.
    """

    def has_permission(self, request, view):
        # Allow GET requests for authenticated users
        if request.method == "GET":
            return request.user.is_authenticated
        
        # For other methods (POST, PUT, PATCH, DELETE), require authentication
        if not request.user.is_authenticated:
            return False
        
        # Super admin can do everything
        if request.user.is_superuser:
            return True
        
        # For POST (create), allow authenticated users (ownership will be set during creation)
        if request.method == "POST":
            return True
        
        # For PUT, PATCH, DELETE, check object-level permissions
        return True  # Will be checked in has_object_permission

    def has_object_permission(self, request, view, obj):
        # Super admin can do everything
        if request.user.is_superuser:
            return True
        
        # Read permissions are allowed for authenticated users
        if request.method in ["GET", "HEAD", "OPTIONS"]:
            return request.user.is_authenticated
        
        # Write permissions are only allowed to the owner of the object
        # For AgentDetail, check both added_user and the user with contact_email_address
        if hasattr(obj, "added_user"):
            # Check if user is the added_user
            if obj.added_user and obj.added_user == request.user:
                return True
            
            # Also check if user's email matches contact_email_address (for agent accounts)
            # This handles cases where added_user might not be set but user owns the account
            if hasattr(obj, "contact_email_address") and obj.contact_email_address:
                if request.user.email == obj.contact_email_address:
                    # Ensure added_user is set for future checks
                    if not obj.added_user:
                        obj.added_user = request.user
                        obj.save(update_fields=['added_user'])
                    return True
        
        # If no ownership match, deny by default
        return False


class HasPermission(BasePermission):
    """
    Permission class that checks for custom permission codes.
    Usage: permission_classes = [HasPermission('booking.view')]
    """
    
    def __init__(self, permission_code: str):
        """
        Initialize with a permission code.
        
        Args:
            permission_code: Permission code to check (e.g., 'booking.view', 'accounts.refund')
        """
        self.permission_code = permission_code
    
    def has_permission(self, request, view):
        """
        Check if user has the required permission.
        """
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Get business from request
        business = None
        
        # Try to get business_id from query params
        business_id = request.query_params.get('business_id')
        if business_id:
            try:
                business = BusinessDetail.objects.get(id=business_id)
            except (BusinessDetail.DoesNotExist, ValueError):
                pass
        
        # Fallback to user's business_id
        if business is None and request.user.business_id:
            try:
                business = BusinessDetail.objects.get(id=request.user.business_id)
            except BusinessDetail.DoesNotExist:
                pass
        
        # Check permission
        return has_permission(request.user, self.permission_code, business)
    
    def has_object_permission(self, request, view, obj):
        """
        Check object-level permission (includes region/association scoping).
        """
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Get business from request or user
        business = None
        business_id = request.query_params.get('business_id')
        if business_id:
            try:
                business = BusinessDetail.objects.get(id=business_id)
            except (BusinessDetail.DoesNotExist, ValueError):
                pass
        
        if business is None and request.user.business_id:
            try:
                business = BusinessDetail.objects.get(id=request.user.business_id)
            except BusinessDetail.DoesNotExist:
                pass
        
        # Check permission with object for region/association scoping
        return has_permission(request.user, self.permission_code, business, obj=obj)


class IsSuperUserOrHasRolePermission(BasePermission):
    """
    Permission class that allows superusers full access, 
    otherwise checks role-based permissions.
    """
    
    def has_permission(self, request, view):
        user = request.user
        if not user.is_authenticated:
            return False
        
        # Superusers have full access
        if user.is_superuser:
            return True
        
        # For staff, also allow (optional - can remove if needed)
        if user.is_staff:
            return True
        
        # For others, use HasRoleModelPermission logic (inline to avoid circular import)
        codenames = get_related_model_codenames(view.queryset)
        if request.method == "GET":
            filtered_codenames = {
                action for action in codenames if action.startswith("view_")
            }
        elif request.method == "POST":
            filtered_codenames = {
                action for action in codenames if action.startswith("add_")
            }
        elif request.method == "PUT" or request.method == "PATCH":
            filtered_codenames = {
                action for action in codenames if action.startswith("change_")
            }
        elif request.method == "DELETE":
            filtered_codenames = {
                action for action in codenames if action.startswith("delete_")
            }
        else:
            filtered_codenames = []

        # Check if user has required permissions through roles
        user_roles = user.roles.all()
        if user_roles and user_roles.filter(
            permissions__codename__in=filtered_codenames
        ):
            return True

        return False
