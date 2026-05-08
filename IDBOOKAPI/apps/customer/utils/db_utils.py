# Customer Db Utils
from apps.customer.models import Customer, Wallet, WalletTransaction
from apps.customer.transaction_state import normalize_wallet_transaction_state
from datetime import datetime
import pytz
from decimal import Decimal
from django.db.models import Q, Sum
from django.db import transaction


def create_customer_signup_entry(
    user,
    added_user=None,
    gender="",
    employee_id="",
    group_name="DEFAULT",
    department="",
):
    customer = Customer.objects.create(
        user=user,
        added_user=added_user,
        gender=gender,
        employee_id=employee_id,
        group_name=group_name,
        department=department,
    )
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
        from apps.customer.wallet_owner_utils import (
            normalize_wallet_transaction_create_payload,
        )

        payload = normalize_wallet_transaction_create_payload(wtransact)
        status_value = payload.get("status", "Completed")
        success_value = payload.get("is_transaction_success", True)
        payload["status"], payload["is_transaction_success"] = (
            normalize_wallet_transaction_state(
                status_value, success_value
            )
        )
        instance = WalletTransaction.objects.create(**payload)
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
        india_tz = pytz.timezone("Asia/Kolkata")
        today = datetime.now(india_tz)
        print("today--", today)
        pro_wallet_transactions = WalletTransaction.objects.filter(
            user_id=user_id,
            transaction_type="Credit",
            expiry_date__gte=today,
            remaining_amount__gt=0,
        ).order_by(
            "expiry_date"
        )  # Prioritize bonuses expiring soonest

        amount_to_deduct = deduct_amount
        pro_wallet_deductions = []

        # First use pro wallet bonuses if available
        for pro_txn in pro_wallet_transactions:
            if amount_to_deduct <= 0:
                break

            available_bonus = pro_txn.remaining_amount
            used_from_bonus = min(available_bonus, amount_to_deduct)

            # Track how much was used from this bonus
            pro_wallet_deductions.append(
                {"original_txn": pro_txn, "amount_used": used_from_bonus}
            )

            amount_to_deduct -= used_from_bonus

        # Update pro wallet transactions
        for deduction in pro_wallet_deductions:
            pro_txn = deduction["original_txn"]
            amount_used = deduction["amount_used"]

            # Update the pro wallet transaction
            pro_txn.used_amount += amount_used
            pro_txn.remaining_amount -= amount_used
            pro_txn.save()

            # Create corresponding debit transaction record
            pro_debit = {
                "user": wallet.user,
                "amount": amount_used,
                "transaction_type": "Debit",
                "transaction_details": f"Pro bembership wallet bonus deduction for {booking.booking_type} booking ({booking.confirmation_code})",
                "transaction_for": "booking_confirmed",
                "payment_type": "WALLET",
                "payment_medium": "Idbook",
                "is_transaction_success": True,
            }
            update_wallet_transaction(pro_debit)

            print("deducted " + str(amount_used) + " from pro wallet")

        # If there's remaining amount to deduct, use regular wallet
        regular_wallet_deduction = amount_to_deduct
        if regular_wallet_deduction > 0:
            # Create debit transaction for regular wallet
            regular_debit = {
                "user": wallet.user,
                "amount": regular_wallet_deduction,
                "transaction_type": "Debit",
                "transaction_details": f"Amount debited for {booking.booking_type} booking ({booking.confirmation_code})",
                "transaction_for": "booking_confirmed",
                "payment_type": "WALLET",
                "payment_medium": "Idbook",
                "is_transaction_success": True,
            }
            update_wallet_transaction(regular_debit)
            print("deducted " + str(regular_wallet_deduction) + "from normal wallet")
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

        wallet = Wallet.objects.filter(
            user__id=user_id, company_id__isnull=True, agent_id__isnull=True
        ).first()
        if wallet:
            wallet.balance = wallet.balance + amount
            if not wallet.active:
                wallet.active = True
                wallet.save(update_fields=["balance", "active", "updated"])
            else:
                wallet.save(update_fields=["balance", "updated"])
        else:
            Wallet.objects.create(user_id=user_id, balance=amount)
    except Exception as e:
        print("Wallet Balance add error::", e)
        return False
    return True


def add_company_wallet_amount(company_id, amount):
    try:
        if not company_id:
            print("add_company_wallet_amount: company_id is None or empty")
            return False

        # Ensure company_id is an integer
        try:
            company_id = int(company_id)
        except (ValueError, TypeError):
            print(
                f"add_company_wallet_amount: Invalid company_id type: {type(company_id)}, value: {company_id}"
            )
            return False

        wallet = Wallet.objects.filter(company_id=company_id).first()
        if wallet:
            wallet.balance = wallet.balance + amount
            if not wallet.active:
                wallet.active = True
                wallet.save(update_fields=["balance", "active", "updated"])
            else:
                wallet.save(update_fields=["balance", "updated"])
            print(
                f"add_company_wallet_amount: Updated company wallet {company_id}, new balance: {wallet.balance}"
            )
        else:
            Wallet.objects.create(company_id=company_id, balance=amount)
            print(
                f"add_company_wallet_amount: Created new company wallet {company_id} with balance: {amount}"
            )
    except Exception as e:
        print(f"Wallet Balance add error for company {company_id}::", e)
        import traceback

        print(traceback.format_exc())
        return False
    return True


def add_agent_wallet_amount(agent_id, amount):
    """
    Add amount to agent wallet. Creates wallet if it doesn't exist.
    
    Args:
        agent_id: ID of the AgentDetail
        amount: Decimal amount to add
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        if not agent_id:
            print("add_agent_wallet_amount: agent_id is None or empty")
            return False

        # Ensure agent_id is an integer
        try:
            agent_id = int(agent_id)
        except (ValueError, TypeError):
            print(
                f"add_agent_wallet_amount: Invalid agent_id type: {type(agent_id)}, value: {agent_id}"
            )
            return False

        from apps.org_resources.models import AgentDetail
        wallet = Wallet.objects.filter(agent_id=agent_id).first()
        if wallet:
            wallet.balance = wallet.balance + amount
            if not wallet.active:
                wallet.active = True
                wallet.save(update_fields=["balance", "active", "updated"])
            else:
                wallet.save(update_fields=["balance", "updated"])
            print(
                f"add_agent_wallet_amount: Updated agent wallet {agent_id}, new balance: {wallet.balance}"
            )
        else:
            Wallet.objects.create(agent_id=agent_id, balance=amount)
            print(
                f"add_agent_wallet_amount: Created new agent wallet {agent_id} with balance: {amount}"
            )
    except Exception as e:
        print(f"Wallet Balance add error for agent {agent_id}::", e)
        import traceback
        print(traceback.format_exc())
        return False
    return True


def deduct_agent_wallet_balance(agent_id, deduct_amount):
    """
    Deduct amount from agent wallet.
    
    Args:
        agent_id: ID of the AgentDetail
        deduct_amount: Decimal amount to deduct
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        if not agent_id:
            return False

        wallet = Wallet.objects.filter(agent_id=agent_id).first()
        if wallet:
            if wallet.balance >= deduct_amount:
                wallet.balance = wallet.balance - deduct_amount
                wallet.save()
                return True
            else:
                print(f"Insufficient wallet balance for agent {agent_id}")
                return False
        else:
            print(f"Wallet not found for agent {agent_id}")
            return False
    except Exception as e:
        print(f"Wallet Balance deduct error for agent {agent_id}::", e)
        return False


def get_agent_wallet_balance(agent_id):
    """
    Get agent wallet balance.
    
    Args:
        agent_id: ID of the AgentDetail
        
    Returns:
        Decimal: Wallet balance or 0 if wallet doesn't exist
    """
    try:
        wallet = Wallet.objects.filter(agent_id=agent_id, active=True).first()
        if wallet:
            return wallet.balance
        return 0
    except Exception as e:
        print(f"Error getting agent wallet balance: {e}")
        return 0


def update_wallet_transaction_detail(merchant_transaction_id, payment_details):
    import logging
    logger = logging.getLogger(__name__)
    
    logger.info(f"=== update_wallet_transaction_detail CALLED ===")
    logger.info(f"merchant_transaction_id: {merchant_transaction_id}")
    logger.info(f"payment_details: {payment_details}")
    
    user_id, company_id, agent_id = None, None, None

    payment_objs = WalletTransaction.objects.filter(
        transaction_id=merchant_transaction_id
    )
    
    count = payment_objs.count()
    logger.info(f"Found {count} wallet transaction(s) with transaction_id: {merchant_transaction_id}")
    
    if count == 0:
        logger.error(f"NO TRANSACTION FOUND with transaction_id: {merchant_transaction_id}")
        # Try to find by partial match or log recent transactions for debugging
        recent_txns = WalletTransaction.objects.filter(
            transaction_id__icontains=merchant_transaction_id[:10] if merchant_transaction_id else ""
        ).order_by("-created")[:5]
        logger.info(f"Recent similar transactions: {[(t.id, t.transaction_id, t.status) for t in recent_txns]}")
        return user_id, company_id, agent_id

    # Remove transaction_id from payment_details if present to avoid updating it
    update_data = {k: v for k, v in payment_details.items() if k != "transaction_id"}
    update_data["status"], update_data["is_transaction_success"] = (
        normalize_wallet_transaction_state(
            update_data.get("status"), update_data.get("is_transaction_success")
        )
    )
    logger.info(f"Updating transaction with data: {update_data}")

    updated_count = 0
    for obj in payment_objs:
        for key, value in update_data.items():
            if hasattr(obj, key):
                setattr(obj, key, value)
        obj.save()
        updated_count += 1
    logger.info(f"Updated {updated_count} transaction(s)")

    payment_obj = payment_objs.first()
    if payment_obj:
        # Refresh from DB to get updated values
        payment_obj.refresh_from_db()
        if payment_obj.user:
            user_id = payment_obj.user.id
        # Get company_id from the transaction object
        company_id = payment_obj.company_id if payment_obj.company_id else None
        # Get agent_id from the transaction object
        agent_id = payment_obj.agent.id if payment_obj.agent else None
        logger.info(
            f"Transaction after update - id: {payment_obj.id}, status: {payment_obj.status}, "
            f"is_success: {payment_obj.is_transaction_success}, code: {payment_obj.code}, "
            f"user_id={user_id}, company_id={company_id}, agent_id={agent_id}"
        )
    else:
        logger.error(f"Could not retrieve transaction after update for transaction_id: {merchant_transaction_id}")
    
    logger.info(f"=== update_wallet_transaction_detail COMPLETED ===")
    return user_id, company_id, agent_id


def process_wallet_recharge_transaction_once(merchant_transaction_id, payment_details):
    """
    Update wallet transaction status exactly once for successful recharge flows.
    Returns metadata that callers can use to avoid duplicate wallet credits.
    """
    result = {
        "user_id": None,
        "company_id": None,
        "agent_id": None,
        "already_processed": False,
        "transaction_found": False,
    }

    if not merchant_transaction_id:
        return result

    with transaction.atomic():
        payment_obj = (
            WalletTransaction.objects.select_for_update()
            .filter(transaction_id=merchant_transaction_id)
            .order_by("-created")
            .first()
        )

        if not payment_obj:
            return result

        result["transaction_found"] = True
        if payment_obj.user:
            result["user_id"] = payment_obj.user.id
        result["company_id"] = payment_obj.company_id if payment_obj.company_id else None
        result["agent_id"] = payment_obj.agent.id if payment_obj.agent else None

        incoming_success = payment_details.get("is_transaction_success") is True
        already_success = (
            payment_obj.is_transaction_success is True
            and payment_obj.status == "Completed"
        )

        if incoming_success and already_success:
            result["already_processed"] = True
            return result

        for key, value in payment_details.items():
            if key == "transaction_id":
                continue
            if hasattr(payment_obj, key):
                setattr(payment_obj, key, value)
        payment_obj.save()

    return result


def update_wallet_recharge_details(user_id, company_id, amount, agent_id=None):
    amount = Decimal(str(amount))

    print(
        f"update_wallet_recharge_details: user_id={user_id}, company_id={company_id}, agent_id={agent_id}, amount={amount}"
    )

    # add wallet amount - prioritize in order: company > agent > user wallet
    if company_id:
        print(f"Adding {amount} to company wallet {company_id}")
        success = add_company_wallet_amount(company_id, amount)
        if not success:
            print(f"Failed to add amount to company wallet {company_id}")
    elif agent_id:
        print(f"Adding {amount} to agent wallet {agent_id}")
        success = add_agent_wallet_amount(agent_id, amount)
        if not success:
            print(f"Failed to add amount to agent wallet {agent_id}")
    elif user_id:
        print(f"Adding {amount} to user wallet {user_id}")
        success = add_user_wallet_amount(user_id, amount)
        if not success:
            print(f"Failed to add amount to user wallet {user_id}")
    else:
        print("Warning: Neither company_id, agent_id nor user_id provided for wallet recharge")

    return user_id, company_id, agent_id


def get_referral_bonus(referred_users: list, user_id):
    referral_transaction = WalletTransaction.objects.filter(
        is_transaction_success=True,
        transaction_for="referral_booking",
        transaction_type="Credit",
        user_id=user_id,
    )

    # filter based on transaction user ids
    query_referral_transaction = Q()
    for rusers in referred_users:
        key_search = "other_details__referral__user__contains"
        filter_dict = {key_search: rusers}
        query_referral_transaction |= Q(**filter_dict)
    referral_transaction = referral_transaction.filter(query_referral_transaction)
    credited_user_list = list(
        referral_transaction.values_list("other_details__referral__user", flat=True)
    )

    # sum
    total_amount = referral_transaction.aggregate(Sum("amount"))

    ##    print(referral_transaction.values('id', 'amount', 'other_details'))
    return total_amount.get("amount__sum"), credited_user_list


def get_credited_referred_user(user_id):
    referral_transaction = WalletTransaction.objects.filter(
        is_transaction_success=True,
        transaction_for="referral_booking",
        transaction_type="Credit",
        user_id=user_id,
    )

    credited_user_list = referral_transaction.values(
        "other_details__referral__user", "amount"
    )
    credited_user_dict = {}
    for credited_user in credited_user_list:
        credited_user_dict[credited_user.get("other_details__referral__user")] = {
            "amount": str(credited_user.get("amount"))
        }

    return credited_user_dict


def attach_razorpay_fee_metadata(transaction_id: str, payment_entity: dict) -> bool:
    """
    Merge Razorpay fee/tax/method onto WalletTransaction.other_details
    (lookup by transaction_id, typically Razorpay payment id after capture).
    """
    wt = WalletTransaction.objects.filter(transaction_id=transaction_id).first()
    if not wt:
        return False
    from apps.payment_gateways.utils.razorpay_fees import actual_fee_from_payment_entity

    meta = actual_fee_from_payment_entity(payment_entity)
    od = dict(wt.other_details or {})
    rz = dict(od.get("razorpay") or {})
    rz.update(meta)
    od["razorpay"] = rz
    wt.other_details = od
    wt.save(update_fields=["other_details"])
    return True
