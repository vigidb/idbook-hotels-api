# Generated by Django 4.2.3 on 2024-11-08 05:33

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('org_resources', '0027_alter_usernotification_notification_type'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='usernotification',
            options={'ordering': ['-created']},
        ),
    ]
