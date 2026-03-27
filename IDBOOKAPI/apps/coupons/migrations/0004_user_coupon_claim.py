from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
from django.core.validators import MinValueValidator


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("coupons", "0003_coupon_level_caps_and_value_override"),
    ]

    operations = [
        migrations.CreateModel(
            name="UserCouponClaim",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("is_exclusive", models.BooleanField(default=False, help_text="If true, this coupon is reserved to this user and cannot be used by other users.")),
                ("claimed_discount_budget", models.DecimalField(blank=True, decimal_places=2, help_text="Optional per-user discount budget reserved at claim time. When set, user redemptions should not exceed this amount.", max_digits=20, null=True, validators=[MinValueValidator(0)])),
                ("active", models.BooleanField(default=True)),
                ("created", models.DateTimeField(auto_now_add=True)),
                ("updated", models.DateTimeField(auto_now=True)),
                ("coupon", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="user_claims", to="coupons.coupon")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="claimed_coupons", to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.AddConstraint(
            model_name="usercouponclaim",
            constraint=models.UniqueConstraint(fields=("coupon", "user"), name="unique_user_coupon_claim"),
        ),
        migrations.AddIndex(
            model_name="usercouponclaim",
            index=models.Index(fields=["coupon", "active"], name="coupons_use_coupon__fdb29e_idx"),
        ),
        migrations.AddIndex(
            model_name="usercouponclaim",
            index=models.Index(fields=["user", "active"], name="coupons_use_user_id_6f39d2_idx"),
        ),
    ]

