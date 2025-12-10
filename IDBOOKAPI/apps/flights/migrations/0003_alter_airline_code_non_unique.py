from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("flights", "0002_airline_active_airline_alias_airline_callsign_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="airline",
            name="code",
            field=models.CharField(
                max_length=3,
                null=True,
                blank=True,
                db_index=True,
                help_text="2-letter IATA airline code (may be blank or reused across airlines)",
            ),
        ),
    ]
