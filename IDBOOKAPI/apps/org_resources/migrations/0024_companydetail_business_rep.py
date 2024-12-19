# Generated by Django 4.2.3 on 2024-10-25 01:31

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('org_resources', '0023_alter_companydetail_company_email_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='companydetail',
            name='business_rep',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='business_representative', to=settings.AUTH_USER_MODEL),
        ),
    ]
