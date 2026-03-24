import django.core.validators
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("coupons", "0001_initial"),
        ("booking", "0010_query_coupon_and_booking_min_payment"),
        ("authentication", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="CouponPartner",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.CharField(max_length=200)),
                (
                    "partner_type",
                    models.CharField(
                        blank=True,
                        default="",
                        help_text="e.g. bank, pg, media, matrimony",
                        max_length=50,
                    ),
                ),
                ("display_name", models.CharField(blank=True, default="", max_length=200)),
                ("contact_email", models.EmailField(blank=True, default="", max_length=254)),
                ("notes", models.TextField(blank=True, default="")),
                ("active", models.BooleanField(default=True)),
                ("created", models.DateTimeField(auto_now_add=True)),
                ("updated", models.DateTimeField(auto_now=True)),
            ],
            options={
                "ordering": ["name"],
            },
        ),
        migrations.CreateModel(
            name="CouponCampaign",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.CharField(max_length=200)),
                (
                    "internal_code",
                    models.CharField(
                        blank=True,
                        default="",
                        help_text="Optional reference for ops",
                        max_length=100,
                    ),
                ),
                (
                    "allowed_booking_types",
                    models.JSONField(
                        blank=True,
                        default=list,
                        help_text="Subset of BOOKING_TYPE values, e.g. ['HOLIDAYPACK','HOTEL']. Empty = all types.",
                    ),
                ),
                (
                    "max_redemptions_total",
                    models.PositiveIntegerField(
                        blank=True,
                        help_text="Stop after this many successful redemptions (campaign-wide).",
                        null=True,
                    ),
                ),
                (
                    "max_redemptions_per_user",
                    models.PositiveIntegerField(
                        blank=True,
                        help_text="Max redemptions per user for this campaign.",
                        null=True,
                    ),
                ),
                (
                    "max_total_discount_budget",
                    models.DecimalField(
                        blank=True,
                        decimal_places=2,
                        help_text="Sum of discount_applied across redemptions must not exceed this.",
                        max_digits=20,
                        null=True,
                    ),
                ),
                ("campaign_valid_from", models.DateTimeField(blank=True, null=True)),
                ("campaign_valid_to", models.DateTimeField(blank=True, null=True)),
                ("funding_source", models.CharField(blank=True, default="", max_length=100)),
                ("terms_url", models.URLField(blank=True, default="")),
                ("active", models.BooleanField(default=True)),
                ("created", models.DateTimeField(auto_now_add=True)),
                ("updated", models.DateTimeField(auto_now=True)),
                (
                    "partner",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="campaigns",
                        to="coupons.couponpartner",
                    ),
                ),
            ],
            options={
                "ordering": ["-created"],
            },
        ),
        migrations.AddField(
            model_name="coupon",
            name="name",
            field=models.CharField(blank=True, default="", max_length=200),
        ),
        migrations.AddField(
            model_name="coupon",
            name="campaign",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="coupons",
                to="coupons.couponcampaign",
            ),
        ),
        migrations.AddField(
            model_name="coupon",
            name="partner",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="coupons",
                to="coupons.couponpartner",
            ),
        ),
        migrations.AlterField(
            model_name="coupon",
            name="code",
            field=models.CharField(db_index=True, max_length=64, unique=True),
        ),
        migrations.CreateModel(
            name="CouponAmountSlab",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("sort_order", models.PositiveSmallIntegerField(default=0)),
                (
                    "min_amount",
                    models.DecimalField(
                        decimal_places=2,
                        max_digits=20,
                        validators=[django.core.validators.MinValueValidator(0)],
                    ),
                ),
                (
                    "max_amount",
                    models.DecimalField(
                        blank=True,
                        decimal_places=2,
                        help_text="Upper bound exclusive; null = no upper limit",
                        max_digits=20,
                        null=True,
                    ),
                ),
                (
                    "discount_type",
                    models.CharField(
                        choices=[("AMOUNT", "AMOUNT"), ("PERCENT", "PERCENT")],
                        default="AMOUNT",
                        max_length=20,
                    ),
                ),
                (
                    "discount_value",
                    models.DecimalField(
                        decimal_places=4,
                        max_digits=15,
                        validators=[django.core.validators.MinValueValidator(0)],
                    ),
                ),
                (
                    "max_discount_per_booking",
                    models.DecimalField(
                        blank=True,
                        decimal_places=2,
                        help_text="Cap discount for this slab",
                        max_digits=20,
                        null=True,
                    ),
                ),
                (
                    "campaign",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="slabs",
                        to="coupons.couponcampaign",
                    ),
                ),
            ],
            options={
                "ordering": ["campaign", "sort_order", "id"],
            },
        ),
        migrations.CreateModel(
            name="CouponRedemption",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "booking_type",
                    models.CharField(
                        choices=[
                            ("HOLIDAYPACK", "HOLIDAYPACK"),
                            ("HOTEL", "HOTEL"),
                            ("VEHICLE", "VEHICLE"),
                            ("FLIGHT", "FLIGHT"),
                            ("VISA", "VISA"),
                            ("EVENT", "EVENT"),
                        ],
                        default="HOTEL",
                        max_length=25,
                    ),
                ),
                (
                    "booking_subtotal",
                    models.DecimalField(
                        decimal_places=6,
                        max_digits=20,
                        validators=[django.core.validators.MinValueValidator(0)],
                    ),
                ),
                (
                    "discount_applied",
                    models.DecimalField(
                        decimal_places=6,
                        max_digits=20,
                        validators=[django.core.validators.MinValueValidator(0)],
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("confirmed", "Confirmed"),
                            ("reversed", "Reversed"),
                        ],
                        default="confirmed",
                        max_length=20,
                    ),
                ),
                ("created", models.DateTimeField(auto_now_add=True)),
                ("updated", models.DateTimeField(auto_now=True)),
                (
                    "booking",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="coupon_redemptions",
                        to="booking.booking",
                    ),
                ),
                (
                    "coupon",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="redemptions",
                        to="coupons.coupon",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="coupon_redemptions",
                        to="authentication.user",
                    ),
                ),
            ],
        ),
        migrations.AddConstraint(
            model_name="couponredemption",
            constraint=models.UniqueConstraint(
                fields=("booking", "coupon"),
                name="unique_coupon_redemption_per_booking",
            ),
        ),
        migrations.AddIndex(
            model_name="couponredemption",
            index=models.Index(fields=["coupon", "status"], name="coupons_cou_coupon__idx"),
        ),
        migrations.AddIndex(
            model_name="couponredemption",
            index=models.Index(fields=["booking", "status"], name="coupons_cou_booking_idx"),
        ),
    ]
