from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("coupons", "0002_partner_coupons_campaign_redemption"),
    ]

    operations = [
        migrations.AddField(
            model_name="coupon",
            name="max_redemptions_per_user",
            field=models.PositiveIntegerField(
                blank=True,
                help_text="Maximum times the same user can redeem this coupon code.",
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="coupon",
            name="max_redemptions_total",
            field=models.PositiveIntegerField(
                blank=True,
                help_text="Maximum successful redemptions allowed for this coupon code.",
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="coupon",
            name="max_total_discount_budget",
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text="Total discount amount allowed for this coupon code across all redemptions.",
                max_digits=20,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="coupon",
            name="use_coupon_value_override",
            field=models.BooleanField(
                default=False,
                help_text="If true, this coupon's own discount_type/discount is used even when campaign slabs are configured.",
            ),
        ),
    ]
