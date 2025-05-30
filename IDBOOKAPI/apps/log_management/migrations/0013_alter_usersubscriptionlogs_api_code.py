# Generated by Django 4.2.3 on 2025-05-03 07:23

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('log_management', '0012_usersubscriptionlogs_tnx_id_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='usersubscriptionlogs',
            name='api_code',
            field=models.CharField(blank=True, choices=[('VPA-CHECK', 'VPA-CHECK'), ('CRT-SUB', 'CRT-SUB'), ('MANDATE', 'MANDATE'), ('MNDT-CLBAK', 'MNDT-CLBAK'), ('RECUR-INIT', 'RECUR-INIT'), ('RECRINIT-CALBAK', 'RECRINIT-CALBAK'), ('SUB-CANC', 'SUB-CANC'), ('SUBCANC-CALBAK', 'SUBCANC-CALBAK'), ('CMN-CALBAK', 'CMN-CALBAK')], default='', max_length=50),
        ),
    ]
