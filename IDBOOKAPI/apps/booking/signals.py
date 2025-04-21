# code
from django.db.models.signals import (
        post_save, pre_save, post_delete)
from django.dispatch import receiver

from .models import Booking, Review

from apps.booking.tasks import (
        send_booking_email_task, create_invoice_task,
        send_cancelled_booking_task)
from apps.booking.utils.booking_utils import (
        generate_booking_confirmation_code, calculate_total_amount,
        generate_booking_reference_code, deduct_booking_amount)
from apps.customer.utils.db_utils import (
        get_wallet_balance, deduct_wallet_balance,
        update_wallet_transaction, get_company_wallet_balance)
from apps.org_resources.db_utils import create_notification
from apps.org_resources.utils.notification_utils import  wallet_booking_balance_notification_template

from apps.org_managements.utils import get_active_business #get_business_by_name

from apps.booking.utils.db_utils import(
        get_property_based_review_count, get_property_rating_average,
        check_booking_reference_code)
from apps.hotels.utils.db_utils import update_property_review_details

import time
import traceback

@receiver(post_save, sender=Review)
def update_review_in_property(sender, instance:Review, **kwargs):
        try:
                property_id = instance.property_id
                total_review_count = get_property_based_review_count(property_id)
                rating_average = get_property_rating_average(property_id)
                update_property_review_details(property_id, rating_average, total_review_count)
        except Exception as e:
                print(traceback.format_exc())
                print(e)

@receiver(post_delete,sender=Review)
def delete_review(sender,instance,*args,**kwargs):
        try:
                property_id = instance.property_id
                total_review_count = get_property_based_review_count(property_id)
                rating_average = get_property_rating_average(property_id)
                update_property_review_details(property_id, rating_average, total_review_count)
        except Exception as e:
                print(traceback.format_exc())
                print(e)
                
        
        

##@receiver(pre_save, sender=Booking)
##def update_total_amount(sender, instance:Booking, **kwargs):
##        """ update total amount, booking reference code, prevent confirm status change if wallet amount is less
##            and low wallet balance notification."""
##        # calculate total booking amount
##        if instance.user.company_id:
##                total_booking_amount, gst_amount, coupon_discount = calculate_total_amount(instance)
##                instance.final_amount = total_booking_amount
##                instance.discount = coupon_discount
##                instance.gst_amount = gst_amount
##
##                booking_status = instance.status
##                if booking_status != instance.cached_status and booking_status == 'confirmed':
##
##                        # get company wallet or use based wallet 
##                        if instance.user.company_id:
##                                balance = get_company_wallet_balance(instance.user.company_id)
##                        else:
##                                balance = get_wallet_balance(instance.user.id)
##                                
##                        if balance < total_booking_amount:
##                                instance.status = instance.cached_status
##                                # send wallet balance notification
##                                send_by = None
##                                # business_name = "Idbook"
##                                bus_details = get_active_business() #get_business_by_name(business_name)
##                                if bus_details:
##                                    send_by = bus_details.user
##                                    
##                                notification_dict = {'user':instance.user, 'send_by':send_by, 'notification_type':'GENERAL',
##                                                     'title':'', 'description':'', 'redirect_url':'',
##                                                     'image_link':''}
##                                notification_dict = wallet_booking_balance_notification_template(
##                                        instance, balance, notification_dict)
##                                create_notification(notification_dict)

@receiver(post_save, sender=Booking) 
def check_booking_status(sender, instance:Booking, **kwargs):
	print("Booking Status Changes")
	booking_id = instance.id
	booking_status = instance.status
	final_amount = instance.final_amount

	# booking reference code
	reference_code = ""
	if not instance.reference_code:
                while True:
                        reference_code = generate_booking_reference_code(
                                instance.id, instance.booking_type)
                        is_exist = check_booking_reference_code(reference_code)
                        if not is_exist:
                                break
                instance.reference_code = reference_code
                instance.save()
	
	# if booking_status != instance.cached_status:
##                if booking_status == 'confirmed' and not instance.confirmation_code:
##                        confirmation_code = generate_booking_confirmation_code(
##                                booking_id, instance.booking_type)
##                        print("Confirmation Code::", confirmation_code)
##                        instance.confirmation_code = confirmation_code
##                        instance.total_payment_made = instance.final_amount
##                        instance.save()
##                        company_id = instance.user.company_id
##                        deduct_booking_amount(instance, company_id)
##                         # create invoice 
##                        create_invoice_task.apply_async(args=[booking_id])

                        
                # if booking_status == 'canceled':
                #         send_cancelled_booking_task.apply_async(args=[booking_id])
	


