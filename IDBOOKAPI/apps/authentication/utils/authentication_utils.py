# authentication utils

def user_representation(user, refresh_token=None):
    
    profile_picture = ''
    customer_profile = user.customer_profile.last()
    if customer_profile:
        if customer_profile.profile_picture:
            profile_picture = customer_profile.profile_picture.url
        employee_id = customer_profile.employee_id

    user_roles = [uroles for uroles in user.roles.values('id','name')]
    user_groups = [ugrps for ugrps in user.groups.values('id', 'name')]
        

    user_data = {'id': user.id, 'mobile_number': user.mobile_number if user.mobile_number else '',
                 'email': user.email if user.email else '', 'name': user.get_full_name(),
                 'groups': user_groups, 'roles': user_roles, 'permissions': [],
                 'category': user.category, 'profile_picture':profile_picture,
                 'business_id': user.business_id if user.business_id else '',
                 'company_id' : user.company_id if user.company_id else '',
                 'is_active': user.is_active}

    if refresh_token:
        data = {'refreshToken': str(refresh_token), 'accessToken': str(refresh_token.access_token),
                'expiresIn': 0, 'user': user_data}

        return data

    return user_data
