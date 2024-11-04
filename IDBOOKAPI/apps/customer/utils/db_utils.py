# Customer Db Utils
from apps.customer.models import (
    Customer, Wallet, WalletTransaction)

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


def get_wallet_balance(user_id):
    balance = 0
    wallet = Wallet.objects.filter(user__id=user_id).first()
    if wallet:
        balance = wallet.balance
    return balance

def update_wallet_transaction(wtransact):
    try:
        instance = WalletTransaction.objects.create(**wtransact)
    except Exception as e:
        print(e)

def deduct_wallet_balance(user_id, deduct_amount):
    try:
        wallet = Wallet.objects.get(user__id=user_id)
        wallet.balance = float(wallet.balance) - float(deduct_amount)
        wallet.save()
    except Exception as e:
        print("Wallet Balance deduct error::", e)
