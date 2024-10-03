from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import AbstractUser, Permission
from django.contrib.auth.admin import UserAdmin
# from django.contrib.auth.forms import UserChangeForm, UserCreationForm
from .models import Role, UserOtp

User = get_user_model()


# class CustomUserChangeForm(UserChangeForm):
#     class Meta(UserChangeForm.Meta):
#         model = User
#
#
# class CustomUserCreationForm(UserCreationForm):
#     class Meta(UserCreationForm.Meta):
#         model = User


# class CustomUserAdmin(UserAdmin):
#     form = CustomUserChangeForm
#     add_form = CustomUserCreationForm
#     fieldsets = UserAdmin.fieldsets + (
#         ('Roles', {'fields': ('roles',)}),
#     )
#
#
# admin.site.register(User, CustomUserAdmin)
# admin.site.unregister(Group)
# admin.site.register(Group, GroupAdmin)
# admin.site.register(Permission)


class CustomUserAdmin(BaseUserAdmin):
    # The forms to add and change user instances
    # form = UserAdminChangeForm
    # add_form = UserAdminCreationForm

    # The fields to be used in displaying the User model.
    # These override the definitions on the base UserAdmin
    # that reference specific fields on auth.User.
    list_display = ('id', 'custom_id', 'email', 'mobile_number', 'category')
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
       # ('Full name', {'fields': ()}),
       #  ('Permissions', {'fields': ('is_active',)}),
    )
    # add_fieldsets is not a standard ModelAdmin attribute. UserAdmin
    # overrides get_fieldsets to use this attribute when creating a user.
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'password1', 'password2')}
        ),
    )
    search_fields = ('email', 'category')
    ordering = ('id',)
    filter_horizontal = ()


# admin.site.register(User, CustomUserAdmin)
admin.site.register(User)
admin.site.register(Permission)
# Remove Group Model from admin. We're not using it.
admin.site.unregister(Group)


class RoleAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'short_code')


admin.site.register(Role, RoleAdmin)
admin.site.register(UserOtp)

admin.site.site_title = 'IDBookHotels Admin Panel'
admin.site.site_header = 'IDBookHotels'
admin.site.index_title = 'Welcome to IDBookHotels'

