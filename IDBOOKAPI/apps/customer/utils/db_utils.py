# Customer Db Utils
from apps.customer.models import (
    Customer, Wallet, WalletTransaction)
from datetime import datetime
import pytz
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

# def deduct_wallet_balance(user_id, deduct_amount):
#     try:
#         wallet = Wallet.objects.get(user__id=user_id, company_id__isnull=True)
#         if wallet.balance < deduct_amount:
#             return False
#         wallet.balance = wallet.balance - deduct_amount
#         wallet.save()
#         return True
#     except Exception as e:
#         print("Wallet Balance deduct error::", e)
#         return False

def deduct_wallet_balance(user_id, deduct_amount, booking=None):
    try:
        # Get the wallet for the user
        wallet = Wallet.objects.get(user__id=user_id, company_id__isnull=True)
        
        # First check if the total wallet balance is sufficient
        if wallet.balance < deduct_amount:
            return False
        
        # Get any active pro wallet bonuses with remaining balance
        india_tz = pytz.timezone('Asia/Kolkata')
        today = datetime.now(india_tz)
        print("today--", today)
        pro_wallet_transactions = WalletTransaction.objects.filter(
            user_id=user_id,
            transaction_type='Credit',
            expiry_date__gte=today,
            remaining_amount__gt=0
        ).order_by('expiry_date')  # Prioritize bonuses expiring soonest
        
        amount_to_deduct = deduct_amount
        pro_wallet_deductions = []
        
        # First use pro wallet bonuses if available
        for pro_txn in pro_wallet_transactions:
            if amount_to_deduct <= 0:
                break
                
            available_bonus = pro_txn.remaining_amount
            used_from_bonus = min(available_bonus, amount_to_deduct)
            
            # Track how much was used from this bonus
            pro_wallet_deductions.append({
                'original_txn': pro_txn,
                'amount_used': used_from_bonus
            })
            
            amount_to_deduct -= used_from_bonus
        
        # Update pro wallet transactions
        for deduction in pro_wallet_deductions:
            pro_txn = deduction['original_txn']
            amount_used = deduction['amount_used']
            
            # Update the pro wallet transaction
            pro_txn.used_amount += amount_used
            pro_txn.remaining_amount -= amount_used
            pro_txn.save()
            
            # Create corresponding debit transaction record
            pro_debit = {
                'user': wallet.user,
                'amount': amount_used,
                'transaction_type': 'Debit',
                'transaction_details': f"Pro bembership wallet bonus deduction for {booking.booking_type} booking ({booking.confirmation_code})",
                'transaction_for': 'booking',
                'payment_type': 'WALLET',
                'payment_medium': 'Idbook',
                'is_transaction_success': True
            }
            update_wallet_transaction(pro_debit)

            print( "deducted "+str(amount_used)+" from pro wallet")
        
        # If there's remaining amount to deduct, use regular wallet
        regular_wallet_deduction = amount_to_deduct
        if regular_wallet_deduction > 0:
            # Create debit transaction for regular wallet
            regular_debit = {
                'user': wallet.user,
                'amount': regular_wallet_deduction,
                'transaction_type': 'Debit',
                'transaction_details': f"Amount debited for {booking.booking_type} booking ({booking.confirmation_code})",
                'transaction_for': 'booking',
                'payment_type': 'WALLET',
                'payment_medium': 'Idbook',
                'is_transaction_success': True
            }
            update_wallet_transaction(regular_debit)
            print( "deducted "+str(regular_wallet_deduction)+"from normal wallet")
        # Finally, update the main wallet balance
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

    
    
    
    
            
    
    
        
    
