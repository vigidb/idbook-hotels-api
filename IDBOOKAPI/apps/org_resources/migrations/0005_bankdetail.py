# Generated by Django 4.2.3 on 2023-07-17 17:02

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('org_resources', '0004_occupancy'),
    ]

    operations = [
        migrations.CreateModel(
            name='BankDetail',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('bank_name', models.CharField(blank=True, max_length=100, null=True)),
                ('account_holder_name', models.CharField(blank=True, max_length=100, null=True)),
                ('account_number', models.CharField(blank=True, max_length=15, null=True)),
                ('repeat_account_number', models.CharField(blank=True, max_length=15, null=True)),
                ('ifsc', models.CharField(blank=True, max_length=15, null=True)),
                ('paytm_number', models.CharField(blank=True, max_length=10, null=True)),
                ('google_pay_number', models.CharField(blank=True, max_length=10, null=True)),
                ('phonepe_number', models.CharField(blank=True, max_length=10, null=True)),
                ('upi', models.CharField(blank=True, max_length=50, null=True)),
                ('razorpay_vpa_fund_account_id', models.CharField(blank=True, max_length=100, null=True)),
                ('razorpay_bank_fund_account_id', models.CharField(blank=True, max_length=100, null=True)),
                ('active', models.BooleanField(default=False)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('updated', models.DateTimeField(auto_now=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='bank_detail', to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]
