from django.urls import path
from rest_framework import routers
from apps.administrator.viewsets import *

router = routers.DefaultRouter()

router.register(r'users', UserViewSet, basename='users')
router.register(r'roles', RoleViewSet, basename='roles')
router.register(r'permissions', PermissionViewSet, basename='permissions')

urlpatterns = [
    path('users/<int:mobile_number>/roles_and_permissions/', UserRolesAndPermissionsAPIView.as_view(),
         name='user_roles_and_permissions'),
]