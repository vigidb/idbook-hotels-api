from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("booking", "0010_query_coupon_and_booking_min_payment"),
    ]

    operations = [
        migrations.AddField(
            model_name="query",
            name="guest_access_token",
            field=models.CharField(
                blank=True,
                null=True,
                unique=True,
                max_length=255,
                help_text="Secure token for guest users to access their query without authentication",
            ),
        ),
    ]

