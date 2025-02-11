# Generated by Django 4.2.3 on 2024-11-09 05:01

import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('coupons', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='coupon',
            name='discount_type',
            field=models.CharField(choices=[('AMOUNT', 'AMOUNT'), ('PERCENT', 'PERCENT')], default='AMOUNT', max_length=20),
        ),
        migrations.AlterField(
            model_name='coupon',
            name='discount',
            field=models.DecimalField(decimal_places=4, max_digits=15, validators=[django.core.validators.MinValueValidator(0)]),
        ),
    ]
