# Generated by Django 4.2.3 on 2024-11-15 04:18

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('hotels', '0025_alter_room_options_remove_property_amenity_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='RoomAmenityCategory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=200, unique=True)),
                ('active', models.BooleanField(default=True)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('updated', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name_plural': 'RoomAmenity_Categories',
            },
        ),
        migrations.AlterField(
            model_name='hotelamenity',
            name='detail',
            field=models.JSONField(default=dict, help_text='Hotel Amenity', null=True),
        ),
        migrations.CreateModel(
            name='RoomAmenity',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=200, unique=True)),
                ('detail', models.JSONField(default=dict, help_text='room amenity', null=True)),
                ('active', models.BooleanField(default=True)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('updated', models.DateTimeField(auto_now=True)),
                ('room_amenity_category', models.ForeignKey(on_delete=django.db.models.deletion.DO_NOTHING, related_name='room_amenity_category', to='hotels.roomamenitycategory')),
            ],
            options={
                'verbose_name_plural': 'RoomAmenities',
            },
        ),
    ]
