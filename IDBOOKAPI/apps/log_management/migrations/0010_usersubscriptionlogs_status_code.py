# Generated by Django 4.2.3 on 2025-04-17 13:02

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('log_management', '0009_remove_usersubscriptionlogs_status_code_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='usersubscriptionlogs',
            name='status_code',
            field=models.IntegerField(null=True),
        ),
    ]
