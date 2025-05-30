# Generated by Django 4.2.3 on 2025-04-22 10:56

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('log_management', '0010_usersubscriptionlogs_status_code'),
    ]

    operations = [
        migrations.AlterField(
            model_name='smsnotificationlog',
            name='sms_for',
            field=models.CharField(choices=[('HOTEL_BOOKING_CANCEL', 'Hotel Booking Cancellation'), ('HOTEL_PAYMENT_REFUND', 'Hotel Payment Refund'), ('WALLET_RECHARGE_CONFIRMATION', 'Wallet Recharge Confirmation'), ('WALLET_DEDUCTION_CONFIRMATION', 'Wallet Deduction Confirmation'), ('HOTEL_BOOKING_CONFIRMATION', 'Hotel Booking Confirmation'), ('PAYMENT_FAILED_INFO', 'Payment Failed Information'), ('PAYMENT_PROCEED_INFO', 'Payment Proceed Information'), ('VERIFY', 'Verify OTP'), ('SIGNUP', 'Signup OTP'), ('LOGIN', 'Login OTP'), ('HOTEL_PROPERTY_ACTIVATION', 'Property Activated'), ('HOTEL_PROPERTY_DEACTIVATION', 'Property Deactivated'), ('HOTELIER_BOOKING_NOTIFICATION', 'Hotelier Booking Notification'), ('HOTELER_BOOKING_CANCEL_NOTIFICATION', 'Hotelier Booking Cancel Notification'), ('HOTELER_PAYMENT_NOTIFICATION', 'Hotelier Payment Notification'), ('HOTELIER_PROPERTY_REVIEW_NOTIFICATION', 'Property Review Notification'), ('HOTEL_PROPERTY_SUBMISSION', 'Property Submission'), ('other', 'Other Notification')], default='other', max_length=50),
        ),
    ]
