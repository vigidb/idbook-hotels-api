# code
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Booking
from apps.booking.tasks import send_booking_email_task
from apps.booking.utils.booking_utils import generate_booking_confirmation_code

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
	


