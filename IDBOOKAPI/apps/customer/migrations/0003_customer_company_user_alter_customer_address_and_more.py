# Generated by Django 4.2.3 on 2024-09-30 06:39

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('org_resources', '0011_companydetail_gstin_no_companydetail_pan_no'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('customer', '0002_customer_aadhar_card_customer_aadhar_card_number_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='customer',
            name='company_user',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='customer_cmp_profile', to=settings.AUTH_USER_MODEL),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name='customer',
            name='address',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='org_resources.address', verbose_name='customer_address'),
        ),
        migrations.AlterField(
            model_name='customer',
            name='date_of_birth',
            field=models.DateField(blank=True, help_text='Enter the date of birth of the customer.', null=True),
        ),
        migrations.AlterField(
            model_name='customer',
            name='gender',
            field=models.CharField(blank=True, choices=[('Male', 'Male'), ('Female', 'Female'), ('Other', 'Other')], help_text='Select the gender of the customer.', max_length=10, null=True),
        ),
    ]
