from django.urls import path
from rest_framework import routers
from apps.administrator.viewsets import *

router = routers.DefaultRouter(trailing_slash=True)

router.register(r"users", UserViewSet, basename="users")
router.register(r"groups", GroupViewSet, basename="groups")
router.register(r"roles", RoleViewSet, basename="roles")
router.register(r"permissions", PermissionViewSet, basename="permissions")
router.register(r"user-roles", UserRoleViewSet, basename="user-roles")

urlpatterns = [
    path(
        "users/<int:mobile_number>/roles_and_permissions/",
        UserRolesAndPermissionsAPIView.as_view(),
        name="user_roles_and_permissions",
    ),
] + router.urls
