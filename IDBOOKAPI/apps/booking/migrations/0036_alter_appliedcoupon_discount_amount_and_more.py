# Generated by Django 4.2.3 on 2025-02-03 05:24

import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('booking', '0035_rename_child_age_count_booking_child_age_list'),
    ]

    operations = [
        migrations.AlterField(
            model_name='appliedcoupon',
            name='discount_amount',
            field=models.DecimalField(decimal_places=2, max_digits=10, validators=[django.core.validators.MinValueValidator(0)]),
        ),
        migrations.AlterField(
            model_name='booking',
            name='final_amount',
            field=models.DecimalField(decimal_places=6, default=0, help_text='Final amount after considering gst, discount', max_digits=20),
        ),
        migrations.AlterField(
            model_name='booking',
            name='gst_amount',
            field=models.DecimalField(decimal_places=6, default=0.0, help_text='GST amount for the booking', max_digits=20),
        ),
        migrations.AlterField(
            model_name='booking',
            name='gst_percentage',
            field=models.DecimalField(decimal_places=6, default=0.0, help_text='GST % for the booking', max_digits=20),
        ),
        migrations.AlterField(
            model_name='booking',
            name='service_tax',
            field=models.DecimalField(decimal_places=6, default=0.0, help_text='Service tax for the booking', max_digits=20),
        ),
        migrations.AlterField(
            model_name='booking',
            name='subtotal',
            field=models.DecimalField(decimal_places=6, default=0.0, help_text='Price for the booking', max_digits=20),
        ),
        migrations.AlterField(
            model_name='booking',
            name='total_payment_made',
            field=models.DecimalField(decimal_places=6, default=0.0, help_text='Total Payment made', max_digits=20),
        ),
        migrations.AlterField(
            model_name='bookingpaymentdetail',
            name='amount',
            field=models.DecimalField(decimal_places=6, max_digits=20, null=True),
        ),
    ]
