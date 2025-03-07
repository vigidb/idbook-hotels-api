# Generated by Django 4.2.3 on 2024-11-06 07:39

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('org_resources', '0027_alter_usernotification_notification_type'),
        ('customer', '0013_wallet_company'),
    ]

    operations = [
        migrations.AddField(
            model_name='wallettransaction',
            name='company',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.DO_NOTHING, related_name='wallet_company_transaction', to='org_resources.companydetail'),
        ),
    ]
