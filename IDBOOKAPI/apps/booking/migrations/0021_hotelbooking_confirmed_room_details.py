# Generated by Django 4.2.3 on 2024-11-25 16:21

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('booking', '0020_rename_company_id_booking_company'),
    ]

    operations = [
        migrations.AddField(
            model_name='hotelbooking',
            name='confirmed_room_details',
            field=models.JSONField(default=list, null=True),
        ),
    ]
