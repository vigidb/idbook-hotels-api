# Generated by Django 4.2.3 on 2025-02-27 06:19

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('log_management', '0004_wallettransactionlog'),
    ]

    operations = [
        migrations.CreateModel(
            name='SmsOtpLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('mobile_number', models.CharField(blank=True, max_length=100)),
                ('response', models.JSONField(blank=True, null=True)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('updated', models.DateTimeField(auto_now=True)),
            ],
        ),
    ]
