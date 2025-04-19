# Generated by Django 4.2.3 on 2025-04-17 05:39

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('org_resources', '0036_usersubscription_idb_sub_and_more'),
        ('log_management', '0007_smsnotificationlog'),
    ]

    operations = [
        migrations.CreateModel(
            name='UserSubscriptionLogs',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('pg_subid', models.CharField(blank=True, help_text='payment gateway subscription id', max_length=100)),
                ('api_code', models.CharField(blank=True, choices=[('VPA-CHECK', 'VPA-CHECK'), ('CRT-SUB', 'CRT-SUB'), ('MANDATE', 'MANDATE'), ('MNDT-CLBAK', 'MNDT-CLBAK'), ('RECUR-INIT', 'RECUR-INIT'), ('RECRINIT-CALBAK', 'RECRINIT-CALBAK')], default='', max_length=50)),
                ('status_code', models.CharField(blank=True, default='', max_length=10)),
                ('status_response', models.JSONField(blank=True, null=True)),
                ('error_message', models.TextField(default='')),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('updated', models.DateTimeField(auto_now=True)),
                ('user_sub', models.ForeignKey(on_delete=django.db.models.deletion.DO_NOTHING, related_name='user_subscription_log', to='org_resources.usersubscription')),
            ],
        ),
    ]
