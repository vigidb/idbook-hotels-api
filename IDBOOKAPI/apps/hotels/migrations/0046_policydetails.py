# Generated by Django 4.2.3 on 2025-01-27 04:35

import apps.hotels.utils.hotel_policies_utils
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('hotels', '0045_calendarroom'),
    ]

    operations = [
        migrations.CreateModel(
            name='PolicyDetails',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('policy_details', models.JSONField(default=apps.hotels.utils.hotel_policies_utils.default_hotel_policy_json, null=True)),
                ('active', models.BooleanField(default=True)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('updated', models.DateTimeField(auto_now=True)),
            ],
        ),
    ]
