from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("messaging", "0007_campaign_recurrence_fields"),
    ]

    operations = [
        migrations.AlterField(
            model_name="messagelog",
            name="status",
            field=models.CharField(
                choices=[
                    ("queued", "Queued"),
                    ("accepted", "Accepted by provider"),
                    ("sent", "Sent"),
                    ("delivered", "Delivered"),
                    ("bounced", "Bounced"),
                    ("deferred", "Deferred"),
                    ("failed", "Failed"),
                ],
                max_length=16,
            ),
        ),
    ]
