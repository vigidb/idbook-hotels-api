# Generated by Django 4.2.3 on 2023-07-29 17:19

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('holiday_package', '0016_alter_tourpackage_trip_name'),
    ]

    operations = [
        migrations.AlterField(
            model_name='accommodation',
            name='hotel_name',
            field=models.CharField(blank=True, max_length=50),
        ),
        migrations.AlterField(
            model_name='tourpackage',
            name='payment_link',
            field=models.URLField(default=''),
        ),
    ]
