# Generated by Django 4.2.3 on 2024-12-11 05:13

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('coupons', '0003_remove_coupon_coupon_type_coupon_booking_end_date_and_more'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='coupon',
            name='valid_from',
        ),
        migrations.RemoveField(
            model_name='coupon',
            name='valid_to',
        ),
    ]
