# Generated by Django 4.2.3 on 2025-03-19 05:57

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('org_resources', '0029_subscriber_enquiry_email_enquiry_name_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='MessageTemplate',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('temp_id', models.CharField(max_length=50, unique=True)),
                ('temp_description', models.CharField(max_length=255)),
                ('temp_message', models.TextField()),
            ],
        ),
    ]
