# Generated by Django 4.2.3 on 2024-10-24 16:46

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('booking', '0006_vehiclebooking_confirmed_vehicle'),
    ]

    operations = [
        migrations.AddField(
            model_name='flightbooking',
            name='flight_ticket',
            field=models.FileField(blank=True, null=True, upload_to='booking/flight/'),
        ),
    ]
