from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("customer", "0007_wallettransaction_other_details_blank"),
    ]

    operations = [
        migrations.AddConstraint(
            model_name="wallet",
            constraint=models.CheckConstraint(
                check=(
                    models.Q(
                        user_id__isnull=False,
                        company_id__isnull=True,
                        agent_id__isnull=True,
                    )
                    | models.Q(
                        user_id__isnull=True,
                        company_id__isnull=False,
                        agent_id__isnull=True,
                    )
                    | models.Q(
                        user_id__isnull=True,
                        company_id__isnull=True,
                        agent_id__isnull=False,
                    )
                ),
                name="customer_wallet_one_owner_scope",
            ),
        ),
        migrations.AddConstraint(
            model_name="wallettransaction",
            constraint=models.CheckConstraint(
                check=(
                    models.Q(
                        user_id__isnull=False,
                        company_id__isnull=True,
                        agent_id__isnull=True,
                    )
                    | models.Q(
                        user_id__isnull=True,
                        company_id__isnull=False,
                        agent_id__isnull=True,
                    )
                    | models.Q(
                        user_id__isnull=True,
                        company_id__isnull=True,
                        agent_id__isnull=False,
                    )
                ),
                name="customer_wallettransaction_one_owner_scope",
            ),
        ),
    ]
