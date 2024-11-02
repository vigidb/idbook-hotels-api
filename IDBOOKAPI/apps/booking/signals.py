# code
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from .models import Booking
from apps.booking.tasks import (
        send_booking_email_task, create_invoice_task,
        send_cancelled_booking_task)
from apps.booking.utils.booking_utils import (
        generate_booking_confirmation_code, calculate_total_amount)
import time

@receiver(pre_save, sender=Booking)
def update_total_amount(sender, instance:Booking, **kwargs):
        total_booking_amount = calculate_total_amount(instance)
        instance.final_amount = total_booking_amount

@receiver(post_save, sender=Booking) 
def check_booking_status(sender, instance:Booking, **kwargs):
	print("Booking Status Changes")
	booking_id = instance.id
	booking_status = instance.status
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
                        booking_type = 'confirmed-booking'
                        send_booking_email_task.apply_async(args=[booking_id, booking_type])
                        # time.sleep(3)
                        create_invoice_task.apply_async(args=[booking_id])
                if booking_status == 'canceled':
                        send_cancelled_booking_task.apply_async(args=[booking_id])
	


