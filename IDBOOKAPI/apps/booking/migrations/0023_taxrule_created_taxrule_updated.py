# Generated by Django 4.2.3 on 2024-11-26 06:43

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('booking', '0022_taxrule'),
    ]

    operations = [
        migrations.AddField(
            model_name='taxrule',
            name='created',
            field=models.DateTimeField(auto_now_add=True, null=True),
        ),
        migrations.AddField(
            model_name='taxrule',
            name='updated',
            field=models.DateTimeField(auto_now=True, null=True),
        ),
    ]
