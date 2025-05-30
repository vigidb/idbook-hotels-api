# Generated by Django 4.2.3 on 2025-04-16 11:47

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('customer', '0021_alter_wallettransaction_payment_medium_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='wallettransaction',
            name='transaction_for',
            field=models.CharField(choices=[('booking_confirmed', 'booking_confirmed'), ('booking_refund', 'booking_refund'), ('referral_booking', 'referral_booking'), ('booking_refund', 'booking_refund'), ('signup_reward', 'signup_reward'), ('others', 'others')], default='others', max_length=30),
        ),
    ]
