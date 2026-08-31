import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("org_resources", "0004_agentmarkupconfig"),
    ]

    operations = [
        migrations.AddField(
            model_name="messagetemplate",
            name="name",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
        migrations.AddField(
            model_name="messagetemplate",
            name="template_type",
            field=models.CharField(
                choices=[
                    ("transactional", "Transactional"),
                    ("service_implicit", "Service implicit"),
                    ("service_explicit", "Service explicit"),
                    ("promotional", "Promotional"),
                ],
                db_index=True,
                default="promotional",
                max_length=32,
            ),
        ),
        migrations.AddField(
            model_name="messagetemplate",
            name="is_active",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="messagetemplate",
            name="created_at",
            field=models.DateTimeField(default=django.utils.timezone.now),
        ),
        migrations.AddField(
            model_name="messagetemplate",
            name="updated_at",
            field=models.DateTimeField(default=django.utils.timezone.now),
        ),
        migrations.AlterField(
            model_name="messagetemplate",
            name="created_at",
            field=models.DateTimeField(auto_now_add=True),
        ),
        migrations.AlterField(
            model_name="messagetemplate",
            name="updated_at",
            field=models.DateTimeField(auto_now=True),
        ),
    ]
