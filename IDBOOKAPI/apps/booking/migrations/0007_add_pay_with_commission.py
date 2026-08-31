# Generated manually for pay_with_commission option

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("booking", "0006_alter_booking_booking_source_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="booking",
            name="pay_with_commission",
            field=models.BooleanField(
                default=False,
                help_text="True: customer pays amount including agent commission/markup; False: pay net amount only. Used for hotel and flight bookings.",
            ),
        ),
    ]
