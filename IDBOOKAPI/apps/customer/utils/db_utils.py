# Customer Db Utils
from apps.customer.models import Customer

def create_customer_signup_entry(user, added_user=None, gender='',
                                 employee_id='',
                                 group_name='DEFAULT',
                                 department=''):
    customer = Customer.objects.create(
        user=user, added_user=added_user, gender=gender,
        employee_id=employee_id, group_name=group_name,
        department=department)
    return customer

def check_customer_exist(user_id):
    try:
        customer = Customer.objects.get(user=user_id)
    except Exception as e:
        customer = None
        print("Customer doesn't exist")
        
    return customer 
