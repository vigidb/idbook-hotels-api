# Generated by Django 4.2.3 on 2025-04-16 15:19

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('org_resources', '0034_usersubscription'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='usersubscription',
            name='idb_sub',
        ),
        migrations.AlterField(
            model_name='usersubscription',
            name='transaction_id',
            field=models.CharField(blank=True, help_text='Recurring init transaction id', max_length=100),
        ),
    ]
