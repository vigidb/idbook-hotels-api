# Generated by Django 4.2.3 on 2024-01-25 02:42

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('hotels', '0013_rename_manager_property_managed_by_property_added_by'),
    ]

    operations = [
        migrations.RenameField(
            model_name='gallery',
            old_name='image_type',
            new_name='image_or_video_type',
        ),
        migrations.RemoveField(
            model_name='gallery',
            name='upload_image',
        ),
        migrations.AddField(
            model_name='gallery',
            name='upload_image_or_video',
            field=models.URLField(default='', max_length=255),
        ),
        migrations.AlterField(
            model_name='property',
            name='featured_image',
            field=models.URLField(default='', help_text='URL of the featured image for the property.', max_length=255),
        ),
    ]
