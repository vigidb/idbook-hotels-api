# Generated by Django 4.2.3 on 2025-04-11 15:01

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('customer', '0020_wallettransaction_other_details_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='wallettransaction',
            name='payment_medium',
            field=models.CharField(choices=[('PHONE PAY', 'PHONE PAY'), ('Idbook', 'Idbook'), ('Hotel', 'Hotel')], default='Idbook', max_length=50),
        ),
        migrations.AlterField(
            model_name='wallettransaction',
            name='payment_type',
            field=models.CharField(choices=[('PAYMENT GATEWAY', 'PAYMENT GATEWAY'), ('WALLET', 'WALLET'), ('NBFC', 'NBFC'), ('DIRECT', 'DIRECT')], default='WALLET', max_length=50),
        ),
    ]
