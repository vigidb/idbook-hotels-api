# Generated by Django 4.2.3 on 2023-07-19 17:10

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('holiday_package', '0006_customertourenquiry'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='tourpackage',
            name='check_in_date',
        ),
        migrations.RemoveField(
            model_name='tourpackage',
            name='check_out_date',
        ),
        migrations.RemoveField(
            model_name='tourpackage',
            name='company_email',
        ),
        migrations.RemoveField(
            model_name='tourpackage',
            name='company_location',
        ),
        migrations.RemoveField(
            model_name='tourpackage',
            name='company_phone',
        ),
        migrations.RemoveField(
            model_name='tourpackage',
            name='tour_company',
        ),
    ]
