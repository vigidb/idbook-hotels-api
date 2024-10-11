# Generated by Django 4.2.3 on 2024-10-09 07:06

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('coupons', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('holiday_package', '0019_alter_inclusionexclusion_status'),
        ('hotels', '0021_property_franchise'),
        ('booking', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='FlightBooking',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('flight_trip', models.CharField(choices=[('ONE-WAY', 'ONE-WAY'), ('ROUND', 'ROUND')], default='ROUND', help_text='flight trip (one-way or round).', max_length=25)),
                ('flight_class', models.CharField(choices=[('ECONOMY', 'ECONOMY'), ('BUSINESS', 'BUSINESS'), ('FIRST', 'FIRST')], default='ECONOMY', help_text='flight class', max_length=25)),
                ('departure_date', models.DateField(blank=True, help_text='Departure Date', null=True)),
                ('return_date', models.DateField(blank=True, help_text='Return Date', null=True)),
                ('flying_from', models.CharField(blank=True, max_length=255, null=True)),
                ('flying_to', models.CharField(blank=True, max_length=255, null=True)),
            ],
            options={
                'verbose_name_plural': 'FlightBookings',
            },
        ),
        migrations.CreateModel(
            name='HolidayPackageBooking',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('enquired_holiday_package', models.CharField(blank=True, max_length=255, null=True)),
                ('confirmed_holiday_package', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.DO_NOTHING, to='holiday_package.tourpackage', verbose_name='holiday_package')),
            ],
        ),
        migrations.CreateModel(
            name='VehicleBooking',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('pickup_addr', models.CharField(blank=True, max_length=255, null=True)),
                ('dropoff_addr', models.CharField(blank=True, max_length=255, null=True)),
                ('pickup_time', models.DateField(blank=True, help_text='Pickup date and time', null=True)),
                ('vehicle_type', models.CharField(choices=[('CAR', 'CAR'), ('TRAVELLER', 'TRAVELLER'), ('BUS', 'BUS')], default='CAR', help_text='vehicle type.', max_length=25)),
            ],
            options={
                'verbose_name_plural': 'VehicleBookings',
            },
        ),
        migrations.RenameField(
            model_name='booking',
            old_name='person_capacity',
            new_name='adult_count',
        ),
        migrations.RenameField(
            model_name='booking',
            old_name='child_capacity',
            new_name='child_count',
        ),
        migrations.RemoveField(
            model_name='booking',
            name='bed_count',
        ),
        migrations.RemoveField(
            model_name='booking',
            name='checkin_time',
        ),
        migrations.RemoveField(
            model_name='booking',
            name='checkout_time',
        ),
        migrations.RemoveField(
            model_name='booking',
            name='property',
        ),
        migrations.RemoveField(
            model_name='booking',
            name='room',
        ),
        migrations.RemoveField(
            model_name='booking',
            name='room_type',
        ),
        migrations.AddField(
            model_name='booking',
            name='infant_count',
            field=models.PositiveSmallIntegerField(default=0, help_text='infant count'),
        ),
        migrations.AlterField(
            model_name='booking',
            name='booking_type',
            field=models.CharField(choices=[('HOLIDAYPACK', 'HOLIDAYPACK'), ('HOTEL', 'HOTEL'), ('VEHICLE', 'VEHICLE'), ('FLIGHT', 'FLIGHT')], default='HOTEL', help_text='booking type.', max_length=25),
        ),
        migrations.AlterField(
            model_name='booking',
            name='coupon',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='coupons.coupon', verbose_name='booking_coupon'),
        ),
        migrations.AlterField(
            model_name='booking',
            name='deal_price',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=10),
        ),
        migrations.AlterField(
            model_name='booking',
            name='final_amount',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=10),
        ),
        migrations.AlterField(
            model_name='booking',
            name='user',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.DO_NOTHING, to=settings.AUTH_USER_MODEL, verbose_name='booking_user'),
        ),
        migrations.CreateModel(
            name='HotelBooking',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('enquired_property', models.CharField(blank=True, max_length=255, null=True)),
                ('booking_slot', models.CharField(choices=[('4 HOURS', 4), ('8 HOURS', 8), ('12 HOURS', 12), ('24 HOURS', 24)], default='24 HOURS', help_text='booking type.', max_length=25)),
                ('room_type', models.CharField(choices=[('DELUXE', 'DELUXE'), ('CLASSIC', 'CLASSIC'), ('PREMIUM', 'PREMIUM')], default='DELUXE', help_text='booked room type.', max_length=25)),
                ('checkin_time', models.DateField(blank=True, help_text='Check-in time for the property.', null=True)),
                ('checkout_time', models.DateField(blank=True, help_text='Check-out time for the property.', null=True)),
                ('bed_count', models.PositiveIntegerField(default=1, help_text='bed count')),
                ('confirmed_property', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.DO_NOTHING, to='hotels.property', verbose_name='booking_property')),
                ('room', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.DO_NOTHING, to='hotels.room', verbose_name='booking_room')),
            ],
        ),
        migrations.CreateModel(
            name='HolidayPackageHotelDetail',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('holiday_package_booking', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.DO_NOTHING, to='booking.holidaypackagebooking', verbose_name='holiday_package_booking')),
                ('hotel_booking', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.DO_NOTHING, to='booking.hotelbooking', verbose_name='hotel_booking')),
            ],
        ),
        migrations.AddField(
            model_name='booking',
            name='flight_booking',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.DO_NOTHING, to='booking.flightbooking', verbose_name='hotel_booking'),
        ),
        migrations.AddField(
            model_name='booking',
            name='holiday_package_booking',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.DO_NOTHING, to='booking.holidaypackagebooking', verbose_name='hotel_package_booking'),
        ),
        migrations.AddField(
            model_name='booking',
            name='hotel_booking',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.DO_NOTHING, to='booking.hotelbooking', verbose_name='hotel_booking'),
        ),
        migrations.AddField(
            model_name='booking',
            name='vehicle_booking',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.DO_NOTHING, to='booking.vehiclebooking', verbose_name='hotel_booking'),
        ),
    ]