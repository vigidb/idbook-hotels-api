# Generated by Django 4.2.3 on 2024-11-11 03:52

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('booking', '0019_booking_company_id'),
    ]

    operations = [
        migrations.RenameField(
            model_name='booking',
            old_name='company_id',
            new_name='company',
        ),
    ]
