# Generated by Django 4.2.3 on 2025-01-10 06:15

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('hotels', '0040_property_starting_price_details'),
    ]

    operations = [
        migrations.AddField(
            model_name='property',
            name='is_slot_price_enabled',
            field=models.BooleanField(default=False),
        ),
    ]
