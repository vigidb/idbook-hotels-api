# Generated by Django 4.2.3 on 2024-10-11 05:33

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('booking', '0003_holidaypackagebooking_available_start_date_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='flightbooking',
            name='departure_date',
            field=models.DateTimeField(blank=True, help_text='Departure Date', null=True),
        ),
        migrations.AlterField(
            model_name='flightbooking',
            name='return_date',
            field=models.DateTimeField(blank=True, help_text='Return Date', null=True),
        ),
        migrations.AlterField(
            model_name='hotelbooking',
            name='checkin_time',
            field=models.DateTimeField(blank=True, help_text='Check-in time for the property.', null=True),
        ),
        migrations.AlterField(
            model_name='hotelbooking',
            name='checkout_time',
            field=models.DateTimeField(blank=True, help_text='Check-out time for the property.', null=True),
        ),
        migrations.AlterField(
            model_name='vehiclebooking',
            name='pickup_time',
            field=models.DateTimeField(blank=True, help_text='Pickup date and time', null=True),
        ),
    ]
