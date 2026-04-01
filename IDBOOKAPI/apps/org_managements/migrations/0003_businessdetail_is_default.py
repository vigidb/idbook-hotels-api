from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("org_managements", "0002_alter_businessdetail_options"),
    ]

    operations = [
        migrations.AddField(
            model_name="businessdetail",
            name="is_default",
            field=models.BooleanField(
                default=False,
                help_text="Default billed-by business (fallback when specific business not found).",
            ),
        ),
    ]

