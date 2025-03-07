# Generated by Django 4.2.3 on 2024-10-23 06:29

import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('org_resources', '0022_alter_companydetail_contact_email_address'),
    ]

    operations = [
        migrations.AlterField(
            model_name='companydetail',
            name='company_email',
            field=models.EmailField(blank=True, help_text='Email address of the company.', max_length=254, null=True, validators=[django.core.validators.EmailValidator]),
        ),
        migrations.AlterField(
            model_name='companydetail',
            name='contact_email_address',
            field=models.EmailField(blank=True, help_text='Email address of the contact person.', max_length=254, null=True, validators=[django.core.validators.EmailValidator]),
        ),
    ]
