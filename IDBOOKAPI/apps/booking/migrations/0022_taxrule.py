# Generated by Django 4.2.3 on 2024-11-26 05:58

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('booking', '0021_hotelbooking_confirmed_room_details'),
    ]

    operations = [
        migrations.CreateModel(
            name='TaxRule',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('booking_type', models.CharField(choices=[('HOLIDAYPACK', 'HOLIDAYPACK'), ('HOTEL', 'HOTEL'), ('VEHICLE', 'VEHICLE'), ('FLIGHT', 'FLIGHT')], default='HOTEL', help_text='booking type.', max_length=25)),
                ('math_compare_symbol', models.CharField(choices=[('EQUALS', 'EQUALS'), ('LESS-THAN', 'LESS-THAN'), ('LESS-THAN-OR-EQUALS', 'LESS-THAN-OR-EQUALS'), ('GREATER-THAN', 'GREATER-THAN'), ('GREATER-THAN-OR-EQUALS', 'GREATER-THAN-OR-EQUALS'), ('BETWEEN', 'BETWEEN')], default='EQUALS', help_text='for comparison', max_length=50)),
                ('tax_rate_in_percent', models.DecimalField(decimal_places=2, default=0, help_text='gst rate in percent', max_digits=6)),
                ('amount1', models.PositiveIntegerField()),
                ('amount2', models.PositiveIntegerField(null=True)),
            ],
        ),
    ]
