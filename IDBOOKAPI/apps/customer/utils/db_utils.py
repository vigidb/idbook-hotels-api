# Customer Db Utils
from apps.customer.models import (
    Customer, Wallet, WalletTransaction)

from decimal import Decimal
from django.db.models import Q, Sum

def create_customer_signup_entry(user, added_user=None, gender='',
                                 employee_id='',
                                 group_name='DEFAULT',
                                 department=''):
    customer = Customer.objects.create(
        user=user, added_user=added_user, gender=gender,
        employee_id=employee_id, group_name=group_name,
        department=department)
    return customer

def get_user_based_customer(user_id):
    try:
        customer = Customer.objects.get(user=user_id)
        return customer
    except Exception as e:
        print(e)
        return None

def check_customer_exist(user_id):
    try:
        customer = Customer.objects.get(user=user_id)
    except Exception as e:
        customer = None
        print("Customer doesn't exist")
        
    return customer


def get_wallet_balance(user_id):
    balance = 0
    wallet = None
    if user_id:
        wallet = Wallet.objects.filter(user__id=user_id).first()
        if wallet:
            balance = wallet.balance
    return balance

def get_company_wallet_balance(company_id):
    balance = 0
    if company_id:
        wallet = Wallet.objects.filter(company__id=company_id).first()
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
        wallet = Wallet.objects.get(user__id=user_id, company_id__isnull=True)
        if wallet.balance < deduct_amount:
            return False
        wallet.balance = wallet.balance - deduct_amount
        wallet.save()
        return True
    except Exception as e:
        print("Wallet Balance deduct error::", e)
        return False

def deduct_company_wallet_balance(company_id, deduct_amount):
    try:
        wallet = Wallet.objects.get(company__id=company_id)
        if wallet.balance < deduct_amount:
            return False
        wallet.balance = wallet.balance - deduct_amount
        wallet.save()
        return True
    except Exception as e:
        print("Wallet Balance deduct error::", e)
        return False

def add_user_wallet_amount(user_id, amount):
    try:
        if not user_id:
            return False
        
        wallet = Wallet.objects.filter(user__id=user_id, company_id__isnull=True).first()
        if wallet:
            wallet.balance = wallet.balance + amount
            wallet.save()
        else:
            Wallet.objects.create(user_id=user_id, balance=amount)
    except Exception as e:
        print("Wallet Balance add error::", e)
        return False
    return True

def add_company_wallet_amount(company_id, amount):
    try:
        if not company_id:
            return False
        
        wallet = Wallet.objects.filter(company_id=company_id).first()
        if wallet:
            wallet.balance = wallet.balance + amount
            wallet.save()
        else:
            Wallet.objects.create(company_id=company_id, balance=amount)
    except Exception as e:
        print("Wallet Balance add error::", e)
        return False
    return True

def update_wallet_transaction_detail(merchant_transaction_id, payment_details):
    user_id, company_id = None, None
    
    payment_objs = WalletTransaction.objects.filter(
        transaction_id=merchant_transaction_id)
    payment_objs.update(**payment_details)

    payment_obj = payment_objs.first()
    if payment_obj:
        if payment_obj.user:
            user_id = payment_obj.user.id
        company_id = payment_obj.company_id
        # add wallet amount
    return user_id, company_id
        

def update_wallet_recharge_details(user_id, company_id, amount):

##    user_id, company_id = None, None
    amount = Decimal(str(amount))

    # update wallet transaction
##    payment_objs = WalletTransaction.objects.filter(
##        transaction_id=merchant_transaction_id)
##    payment_objs.update(**payment_details)
##    payment_obj = payment_objs.first()
##    if payment_obj:
##        user_id = payment_obj.user.id
##        company_id = payment_obj.company_id
        # add wallet amount
    if company_id:
        add_company_wallet_amount(company_id, amount)
    elif user_id:
        add_user_wallet_amount(user_id, amount)
    return user_id, company_id

def get_referral_bonus(referred_users:list, user_id):
    referral_transaction = WalletTransaction.objects.filter(
        is_transaction_success=True, transaction_for='referral_booking',
        transaction_type='Credit', user_id=user_id)

    # filter based on transaction user ids
    query_referral_transaction = Q()
    for rusers in referred_users:
        key_search = "other_details__referral__user__contains"
        filter_dict = {key_search: rusers}
        query_referral_transaction|= Q(**filter_dict)
    referral_transaction = referral_transaction.filter(query_referral_transaction)
    credited_user_list = list(referral_transaction.values_list(
        'other_details__referral__user', flat=True))

    # sum
    total_amount = referral_transaction.aggregate(Sum('amount'))

##    print(referral_transaction.values('id', 'amount', 'other_details'))
    return total_amount.get('amount__sum'), credited_user_list

def get_credited_referred_user(user_id):
    referral_transaction = WalletTransaction.objects.filter(
        is_transaction_success=True, transaction_for='referral_booking',
        transaction_type='Credit', user_id=user_id)

    credited_user_list = referral_transaction.values(
        'other_details__referral__user', 'amount')
    credited_user_dict = {}
    for credited_user in credited_user_list:
        credited_user_dict[credited_user.get(
            'other_details__referral__user')] = {'amount':str(credited_user.get('amount'))}
        
    return credited_user_dict

    
    
    
    
            
    
    
        
    
