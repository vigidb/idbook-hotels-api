# Generated by Django 4.2.3 on 2024-10-31 09:17

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('org_resources', '0026_usernotification_image_link_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='usernotification',
            name='notification_type',
            field=models.CharField(choices=[('GENERAL', 'GENERAL'), ('OFFERS', 'OFFERS'), ('BOOKING', 'BOOKING')], default='GENERAL', max_length=50),
        ),
    ]
