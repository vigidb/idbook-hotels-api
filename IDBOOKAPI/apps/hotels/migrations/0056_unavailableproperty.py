# Generated by Django 4.2.3 on 2025-03-25 04:40

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('hotels', '0055_remove_property_landmark_propertylandmark_property'),
    ]

    operations = [
        migrations.CreateModel(
            name='UnavailableProperty',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('search_term', models.CharField(max_length=255)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
        ),
    ]
