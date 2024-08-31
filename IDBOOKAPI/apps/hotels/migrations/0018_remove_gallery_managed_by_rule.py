# Generated by Django 4.2.3 on 2024-01-29 06:55

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('hotels', '0017_remove_gallery_upload_image_or_video_and_more'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='gallery',
            name='managed_by',
        ),
        migrations.CreateModel(
            name='Rule',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('json_data', models.JSONField()),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('updated', models.DateTimeField(auto_now=True)),
                ('active', models.BooleanField(default=True)),
                ('property', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='property_rule', to='hotels.property')),
            ],
            options={
                'ordering': ('created',),
            },
        ),
    ]
