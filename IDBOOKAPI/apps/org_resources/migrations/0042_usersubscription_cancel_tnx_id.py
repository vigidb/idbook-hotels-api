# Generated by Django 4.2.3 on 2025-05-03 05:18

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('org_resources', '0041_usersubscription_is_cancel_initiated_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='usersubscription',
            name='cancel_tnx_id',
            field=models.CharField(blank=True, help_text='Cancel transaction id', max_length=100),
        ),
    ]
