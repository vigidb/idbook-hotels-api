from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("org_resources", "0006_alter_messagetemplate_options_and_more"),
    ]

    operations = [
        migrations.AlterField(
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
                default="service_implicit",
                max_length=32,
            ),
        ),
    ]
