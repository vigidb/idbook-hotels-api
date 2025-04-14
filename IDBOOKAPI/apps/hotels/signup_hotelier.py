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
from apps.hotels.tasks import send_hotel_sms_task, send_hotel_email_task


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
    try:
        print(f"\nCreating user for: {name}")
        print(f"Email: {email}, Phone: {mobile_number}")
        
        user = User.objects.filter(email=email).first()
        grp, role = authentication_utils.get_group_based_on_name(group_name)
        if not grp or not role:
            print(f"Group or role for {group_name} doesn't exist.")
            return None
        
        if user and group_name:
            email_grp_users = db_utils.get_userid_list(email, group=grp)
            if email_grp_users and (group_name != 'B2C-GRP' or db_utils.is_role_exist(email_grp_users, role)):
                print(f"Email {email} already exists for this group.")
                return user
        
        if mobile_number:
            mobile_grp_users = db_utils.get_userid_list(mobile_number, group=grp)
            if mobile_grp_users and (group_name != 'B2C-GRP' or db_utils.is_role_exist(mobile_grp_users, role)):
                print(f"Mobile number {mobile_number} already exists for this group.")
                
        formatted_name = f"Hotelier {name[:10]}..." if len(name) > 10 else f"Hotelier {name}"
        
        if user:
            user.mobile_number = mobile_number
            user.name = formatted_name
            user.set_password(password)
            user.save()
            print(f"↻ Updating existing user: {email}")
        else:
            user = User(
                email=email,
                mobile_number=mobile_number,
                name=formatted_name
            )
            user.set_password(password)
            user.save()
            Customer.objects.create(user_id=user.id, active=True)
            print(f"Created new user: {email}")
        
        if grp:
            user.groups.add(grp)
        if role:
            user.roles.add(role)
        
        user.default_group = group_name
        user.email_verified = False
        user.save()
        
        refresh = RefreshToken.for_user(user)
        data = authentication_utils.user_representation(user, refresh_token=refresh)
        
        print(f"User setup successfully: {email}")
        return user
    except Exception as e:
        print(f"❌ Error creating user for {email}: {e}")
        return None

def create_accounts_for_properties():
    """
    Create user accounts for each property in the contact report and update all properties with the same email.
    """
    properties = generate_existing_contact_report()
    
    if not properties:
        return
    
    print("\n\nCreating user accounts for properties...")
    print("-" * 60)
    
    users_by_email = {}
    success_list = []
    failed_list = []
    
    for prop in properties:
        try:
            if prop.email not in users_by_email:
                user = create_user_without_otp(
                    email=prop.email,
                    name=prop.name,
                    mobile_number=prop.phone_no
                )
                
                if user:
                    users_by_email[prop.email] = user
                    prop.managed_by_id = user.id
                    prop.save()
                    success_list.append((prop.email, prop.name, prop.phone_no))
                else:
                    failed_list.append((prop.email, prop.name, prop.phone_no))
        except Exception as e:
            print(f"❌ Error processing property {prop.name} ({prop.email}): {e}")
            failed_list.append((prop.email, prop.name, prop.phone_no))
    
    print("\nSummary:")
    print(f"Total properties processed: {len(properties)}")
    print(f"Successfully created accounts: {len(success_list)}")
    print(f"Failed to create accounts: {len(failed_list)}")
    
    print("\nAccounts Created:")
    for email, name, phone in success_list:
        print(f"✔ {name} | {email} | {phone}")
    
    print("\nFailed Accounts:")
    for email, name, phone in failed_list:
        print(f"❌ {name} | {email} | {phone}")
    
    return properties, users_by_email

def send_activation_notifications_to_properties():
    """
    Send activation SMS and email notifications to all active properties with valid contact details,
    only if the user ID matches the managed_by_id in the Property table.
    """
    properties = generate_existing_contact_report()
    
    if not properties:
        return
    
    print("\n\nSending activation notifications to properties...")
    print("-" * 60)
    
    sms_success_count = 0
    email_success_count = 0
    
    for prop in properties:
        # Check if the property has a valid manager assigned
        if not prop.managed_by_id:
            print(f"✗ Skipping property {prop.name} (ID: {prop.id}) - No manager assigned.")
            continue
        
        # Get the user associated with the property
        user = User.objects.filter(id=prop.managed_by_id).first()
        
        if not user:
            print(f"✗ Skipping property {prop.name} (ID: {prop.id}) - Managed user not found.")
            continue
        
        # Send SMS notification
        if prop.phone_no:
            try:
                send_hotel_sms_task.apply_async(
                    kwargs={
                        'notification_type': 'HOTEL_PROPERTY_ACTIVATION',
                        'params': {
                            'property_id': prop.id
                        }
                    }
                )
                print(f"✓ Queued activation SMS for property: {prop.name} (ID: {prop.id})")
                sms_success_count += 1
            except Exception as e:
                print(f"✗ Failed to queue SMS for property: {prop.name} (ID: {prop.id}). Error: {e}")
        
        # Send Email notification
        if prop.email:
            try:
                send_hotel_email_task.apply_async(
                    kwargs={
                        'notification_type': 'HOTEL_PROPERTY_ACTIVATION',
                        'params': {
                            'property_id': prop.id
                        }
                    }
                )
                print(f"✓ Queued activation email for property: {prop.name} (ID: {prop.id})")
                email_success_count += 1
            except Exception as e:
                print(f"✗ Failed to queue email for property: {prop.name} (ID: {prop.id}). Error: {e}")


if __name__ == "__main__":
    properties, users_by_email = create_accounts_for_properties()
    
    send_activation_notifications_to_properties()