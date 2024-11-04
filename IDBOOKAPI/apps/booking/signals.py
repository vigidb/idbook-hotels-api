# code
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from .models import Booking
from apps.booking.tasks import (
        send_booking_email_task, create_invoice_task,
        send_cancelled_booking_task)
from apps.booking.utils.booking_utils import (
        generate_booking_confirmation_code, calculate_total_amount)
from apps.customer.utils.db_utils import (
        get_wallet_balance, deduct_wallet_balance,
        update_wallet_transaction)
from apps.org_resources.db_utils import create_notification
from apps.org_resources.utils.notification_utils import  wallet_booking_balance_notification_template

from apps.org_managements.utils import get_business_by_name

import time

@receiver(pre_save, sender=Booking)
def update_total_amount(sender, instance:Booking, **kwargs):
        total_booking_amount = calculate_total_amount(instance)
        instance.final_amount = total_booking_amount

        booking_status = instance.status
        if booking_status == 'confirmed':
                balance = get_wallet_balance(instance.user.id)
                if balance < total_booking_amount:
                        instance.status = instance.cached_status
                        # send wallet balance notification
                        send_by = None
                        business_name = "Idbook"
                        bus_details = get_business_by_name(business_name)
                        if bus_details:
                            send_by = bus_details.user
                            
                        notification_dict = {'user':instance.user, 'send_by':send_by, 'notification_type':'GENERAL',
                                             'title':'', 'description':'', 'redirect_url':'',
                                             'image_link':''}
                        notification_dict = wallet_booking_balance_notification_template(
                                instance, balance, notification_dict)
                        create_notification(notification_dict)

@receiver(post_save, sender=Booking) 
def check_booking_status(sender, instance:Booking, **kwargs):
	print("Booking Status Changes")
	booking_id = instance.id
	booking_status = instance.status
	final_amount = instance.final_amount
	print("Booking Status::", booking_status)
	print("cached status::", instance.cached_status)
	if booking_status != instance.cached_status:
                if booking_status == 'confirmed':
                        if not instance.confirmation_code:
                                confirmation_code = generate_booking_confirmation_code(
                                        booking_id, instance.booking_type)
                                print("Confirmation Code::", confirmation_code)
                                instance.confirmation_code = confirmation_code
                                instance.save()
                        # create invoice 
                        create_invoice_task.apply_async(args=[booking_id])
                        booking_type = 'confirmed-booking'
                        deduct_amount = float(final_amount) - float(instance.total_payment_made)
                        deduct_wallet_balance(instance.user.id, deduct_amount)
                        transaction_details = f"Amount debited for {instance.booking_type} \
booking ({instance.confirmation_code})"
                        wtransact_dict = {'user':instance.user, 'amount':deduct_amount,
                                          'transaction_type':'Debit', 'transaction_details':transaction_details}
                        update_wallet_transaction(wtransact_dict)
                        # send confirmed email
                        # send_booking_email_task.apply_async(args=[booking_id, booking_type])
                        # time.sleep(3)
                        
                if booking_status == 'canceled':
                        send_cancelled_booking_task.apply_async(args=[booking_id])
	


