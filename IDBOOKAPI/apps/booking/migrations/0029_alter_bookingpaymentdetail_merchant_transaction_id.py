# Generated by Django 4.2.3 on 2024-12-14 03:32

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('booking', '0028_bookingpaymentdetail_merchant_transaction_id_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='bookingpaymentdetail',
            name='merchant_transaction_id',
            field=models.CharField(max_length=150, unique=True),
        ),
    ]
