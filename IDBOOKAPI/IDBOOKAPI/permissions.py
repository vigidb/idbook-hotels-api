from rest_framework.permissions import BasePermission
from django.contrib.contenttypes.models import ContentType


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

        codenames = get_related_model_codenames(view.queryset)
        if request.method == "GET":
            filtered_codenames = {action for action in codenames if action.startswith('view_')}
        elif request.method == 'POST':
            filtered_codenames = {action for action in codenames if action.startswith('add_')}
        elif request.method == 'PUT' or request.method == 'PATCH':
            filtered_codenames = {action for action in codenames if action.startswith('change_')}
        else:
            filtered_codenames = []

        user_roles = user.roles.all()
        if user_roles and user_roles[0].permissions.filter(codename__in=filtered_codenames):
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
                filtered_codenames = {action for action in codenames if action.startswith('view_')}
            elif request.method == 'POST':
                filtered_codenames = {action for action in codenames if action.startswith('add_')}
            elif request.method in ('PUT', 'PATCH'):
                filtered_codenames = {action for action in codenames if action.startswith('change_')}
            else:
                filtered_codenames = []

            user_roles = user.roles.all()
            if user_roles and user_roles[0].permissions.filter(codename__in=filtered_codenames):
                return True

        return False
