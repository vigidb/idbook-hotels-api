# Generated by Django 4.2.3 on 2024-11-13 11:22

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('hotels', '0023_hotelamenitycategory_hotelamenity'),
    ]

    operations = [
        migrations.AlterField(
            model_name='hotelamenity',
            name='detail',
            field=models.JSONField(default=dict, null=True),
        ),
    ]
