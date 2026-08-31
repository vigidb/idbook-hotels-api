from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("messaging", "0006_campaignstep_messaging_provider"),
    ]

    operations = [
        migrations.AddField(
            model_name="campaign",
            name="repeat_every_days",
            field=models.PositiveIntegerField(
                blank=True,
                help_text="If set (>0), auto-create the next campaign run after completion with schedule_time + repeat_every_days.",
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="campaign",
            name="repeat_from_campaign",
            field=models.ForeignKey(
                blank=True,
                help_text="Internal link to the previous run when this campaign was auto-generated.",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="generated_repeats",
                to="messaging.campaign",
            ),
        ),
    ]
