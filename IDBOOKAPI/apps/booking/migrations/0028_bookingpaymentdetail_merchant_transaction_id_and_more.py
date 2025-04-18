# Generated by Django 4.2.3 on 2024-12-14 03:23

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('booking', '0027_bookingpaymentdetail'),
    ]

    operations = [
        migrations.AddField(
            model_name='bookingpaymentdetail',
            name='merchant_transaction_id',
            field=models.CharField(blank=True, default='', max_length=150),
        ),
        migrations.AddField(
            model_name='bookingpaymentdetail',
            name='transaction_details',
            field=models.JSONField(default=dict, null=True),
        ),
        migrations.AlterField(
            model_name='bookingpaymentdetail',
            name='amount',
            field=models.DecimalField(decimal_places=6, max_digits=15, null=True),
        ),
        migrations.AlterField(
            model_name='bookingpaymentdetail',
            name='payment_medium',
            field=models.CharField(choices=[('PHONE PAY', 'PHONE PAY'), ('Idbook', 'Idbook')], max_length=50, null=True),
        ),
        migrations.AlterField(
            model_name='bookingpaymentdetail',
            name='payment_type',
            field=models.CharField(choices=[('PAYMENT GATEWAY', 'PAYMENT GATEWAY'), ('WALLET', 'WALLET'), ('NBFC', 'NBFC')], max_length=50, null=True),
        ),
        migrations.AlterField(
            model_name='bookingpaymentdetail',
            name='transaction_id',
            field=models.CharField(blank=True, default='', max_length=150),
        ),
    ]
