# Generated by Django 4.2.3 on 2025-05-09 07:40

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('org_resources', '0044_alter_featuresubscription_options_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='subscription',
            name='is_popular',
            field=models.BooleanField(default=False),
        ),
    ]
