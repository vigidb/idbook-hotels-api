from django.db import migrations, models
import django.core.validators


class Migration(migrations.Migration):

    dependencies = [
        ("booking", "0009_add_agent_to_query"),
    ]

    operations = [
        migrations.AddField(
            model_name="query",
            name="coupon_code",
            field=models.CharField(
                blank=True,
                default="",
                help_text="Optional partner coupon captured on the query",
                max_length=64,
            ),
        ),
        migrations.AddField(
            model_name="booking",
            name="min_payment_amount",
            field=models.DecimalField(
                blank=True,
                decimal_places=6,
                help_text="Minimum rupee payment required for confirmation (optional).",
                max_digits=20,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="booking",
            name="min_payment_percent",
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text="Minimum %% of post-coupon final_amount required as first/advance payment",
                max_digits=5,
                null=True,
                validators=[
                    django.core.validators.MinValueValidator(0),
                    django.core.validators.MaxValueValidator(100),
                ],
            ),
        ),
        migrations.AlterField(
            model_name="booking",
            name="coupon_code",
            field=models.CharField(blank=True, default="", max_length=64),
        ),
    ]
