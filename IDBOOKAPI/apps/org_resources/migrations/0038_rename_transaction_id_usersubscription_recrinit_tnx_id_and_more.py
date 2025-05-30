# Generated by Django 4.2.3 on 2025-04-18 14:37

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('org_resources', '0037_remove_usersubscription_payment_frequency_and_more'),
    ]

    operations = [
        migrations.RenameField(
            model_name='usersubscription',
            old_name='transaction_id',
            new_name='recrinit_tnx_id',
        ),
        migrations.AddField(
            model_name='usersubscription',
            name='next_notify_date',
            field=models.DateTimeField(null=True),
        ),
        migrations.CreateModel(
            name='SubRecurringTransaction',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('recrinit_tnx_id', models.CharField(blank=True, help_text='Recurring init transaction id', max_length=100)),
                ('notification_id', models.CharField(blank=True, max_length=100)),
                ('transaction_amount', models.IntegerField(default=0)),
                ('paid', models.BooleanField(default=False)),
                ('init_state', models.CharField(blank=True, max_length=50)),
                ('callbak_state', models.CharField(blank=True, max_length=50)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('updated', models.DateTimeField(auto_now=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='user_sub_recurtrans', to=settings.AUTH_USER_MODEL)),
                ('user_sub', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='usersub_recur_transaction', to='org_resources.usersubscription')),
            ],
        ),
    ]
