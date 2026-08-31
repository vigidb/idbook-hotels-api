from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("messaging", "0005_contactuploadsession_duplicate_in_file_count"),
    ]

    operations = [
        migrations.AddField(
            model_name="campaignstep",
            name="messaging_provider",
            field=models.ForeignKey(
                blank=True,
                help_text="Optional: send this step via this provider (must match channel). If empty, uses the email template's provider (email only), then the default provider for the channel, then server environment settings.",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="campaign_steps",
                to="messaging.messagingproviderconfig",
            ),
        ),
    ]
