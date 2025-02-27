# Generated by Django 4.2.3 on 2024-11-19 07:18

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('hotels', '0030_alter_propertygallery_caption'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='property',
            name='checkin_24_hours',
        ),
        migrations.AddField(
            model_name='property',
            name='legal_documents',
            field=models.FileField(null=True, upload_to='hotels/property/legal-document/'),
        ),
        migrations.AddField(
            model_name='property',
            name='policies',
            field=models.JSONField(default=dict, help_text='check default policy data in utils'),
        ),
        migrations.AddField(
            model_name='property',
            name='property_ownership',
            field=models.CharField(blank=True, default='', max_length=100),
        ),
    ]
