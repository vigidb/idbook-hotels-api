# Generated by Django 4.2.3 on 2025-04-11 05:14

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('hotels', '0063_alter_property_slug'),
    ]

    operations = [
        migrations.CreateModel(
            name='PayAtHotelSpendLimit',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('start_limit', models.PositiveIntegerField(default=0, help_text='Start range of bookings for paying at hotel')),
                ('end_limit', models.PositiveIntegerField(default=0, help_text='End range of bookings for paying at hotel')),
                ('spend_limit', models.DecimalField(decimal_places=2, default=0.0, help_text='Max allowed spend for this booking range', max_digits=10)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('updated', models.DateTimeField(auto_now=True)),
            ],
            options={
                'ordering': ('created',),
            },
        ),
        migrations.AddField(
            model_name='property',
            name='pay_at_hotel',
            field=models.BooleanField(default=False, help_text='If true, customer can pay at the hotel.'),
        ),
        migrations.CreateModel(
            name='MonthlyPayAtHotelEligibility',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('is_eligible', models.BooleanField(default=False, help_text='Is the user eligible for Pay at Hotel this month?')),
                ('eligible_limit', models.DecimalField(decimal_places=2, default=0.0, help_text='Eligible spend limit for this month', max_digits=10, null=True)),
                ('total_booking_count', models.PositiveIntegerField(default=0, help_text='Total bookings made by the user this month', null=True)),
                ('month', models.CharField(blank=True, default='', help_text='Month name like January, February etc.', max_length=20)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('updated', models.DateTimeField(auto_now=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='monthly_pay_at_hotel_eligibility', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ('-created',),
                'unique_together': {('user', 'month')},
            },
        ),
    ]
