import os
import sys
import django
import json
from django.db.models import Q
from apps.authentication.models import User, UserOtp, Role
from apps.customer.models import Customer
from apps.authentication.utils import db_utils, authentication_utils
from apps.hotels.models import Property
from rest_framework_simplejwt.tokens import RefreshToken

def generate_existing_contact_report():
    """
    Generate a report of active properties that have both email and phone number.
    """
    properties = Property.objects.filter(
        status='Active'
    ).exclude(
        Q(email='') | Q(email__isnull=True) |
        Q(phone_no='') | Q(phone_no__isnull=True)
    )

    if not properties.exists():
        print("No active properties with both email and phone number.")
        return []

    print("\nActive Properties with Contact Details:")
    print("{:<10} {:<30} {:<30} {:<20}".format("ID", "Name", "Email", "Phone Number"))
    print("-" * 100)

    property_list = []
    for prop in properties:
        print("{:<10} {:<30} {:<30} {:<20}".format(
            prop.id, prop.name, prop.email, prop.phone_no
        ))
        property_list.append(prop)
    
    return property_list

def create_user_without_otp(email, name, mobile_number, password="Idbook@123", group_name="HOTELIER-GRP"):
    """
    Create a user account without OTP verification and set email_verified to False
    """
    print(f"\nCreating user for: {name}")
    print(f"Email: {email}, Phone: {mobile_number}")
    
    # First check if user exists
    user = User.objects.filter(email=email).first()
    
    # Get group and role
    grp, role = authentication_utils.get_group_based_on_name(group_name)
    if not grp or not role:
        print(f"Group or role for {group_name} doesn't exist.")
        return None
    
    # Check if email exists for this group
    if user and group_name:
        email_grp_users = db_utils.get_userid_list(email, group=grp)
        if email_grp_users:
            is_role_exist = False
            if group_name == 'B2C-GRP':
                is_role_exist = db_utils.is_role_exist(email_grp_users, role)
            else:
                is_role_exist = True
                
            if is_role_exist:
                print(f"Email {email} already exists for this group.")
                return None
    
    # Check if mobile exists for this group
    if mobile_number:
        mobile_grp_users = db_utils.get_userid_list(mobile_number, group=grp)
        if mobile_grp_users:
            is_role_exist = False
            if group_name == 'B2C-GRP':
                is_role_exist = db_utils.is_role_exist(mobile_grp_users, role)
            else:
                is_role_exist = True
                
            if is_role_exist:
                print(f"Mobile number {mobile_number} already exists for this group.")
                return None
    formatted_name = f"Hotelier {name[:10]}..." if len(name) > 10 else f"Hotelier {name}"
    # Create or update user
    if user:
        # Update existing user
        user.mobile_number = mobile_number
        user.name = formatted_name
        user.set_password(password)
        user.save()
        print(f"↻ Updating existing user: {email}")
    else:
        # Create new user
        user = User(
            email=email,
            mobile_number=mobile_number,
            name=formatted_name
        )
        user.set_password(password)
        user.save()
        
        # Create customer profile
        customer_id = user.id
        Customer.objects.create(user_id=customer_id, active=True)
        print(f"Created new user: {email}")
    
    # Set groups, roles and other attributes
    if grp:
        user.groups.add(grp)
    if role:
        user.roles.add(role)
    
    user.default_group = group_name
    user.email_verified = False  # Explicitly setting to False
    user.save()
    
    # Generate token
    refresh = RefreshToken.for_user(user)
    data = authentication_utils.user_representation(user, refresh_token=refresh)
    

    print(f"User setup successfully: {email}")
    print(f"Email verified status: {user.email_verified}")
    print(f"Token data: {json.dumps(data, indent=2)}")
    
    return user

def create_accounts_for_properties():
    """
    Create user accounts for each property in the contact report
    """
    properties = generate_existing_contact_report()
    
    if not properties:
        return
    
    print("\n\nCreating user accounts for properties...")
    print("-" * 60)
    
    success_count = 0
    for prop in properties:
        user = create_user_without_otp(
            email=prop.email,
            name=prop.name,
            mobile_number=prop.phone_no
        )
        
        if user:
            # Update manage_by_id field
            prop.managed_by_id = user.id
            prop.save()
            success_count += 1
    
    print("\nSummary:")
    print(f"Total properties processed: {len(properties)}")
    print(f"Successfully created/updated accounts: {success_count}")
    print(f"Failed to create accounts: {len(properties) - success_count}")

if __name__ == "__main__":
    create_accounts_for_properties()