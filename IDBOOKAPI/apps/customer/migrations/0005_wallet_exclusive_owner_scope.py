# Cleanup wallet ownership scope data before constraints.

from django.db import migrations


def _cleanup_wallet_owner_scope(apps, schema_editor):
    Wallet = apps.get_model("customer", "Wallet")
    WalletTransaction = apps.get_model("customer", "WalletTransaction")

    # 1) Delete orphan rows where all owner scopes are null.
    Wallet.objects.filter(
        user_id__isnull=True, company_id__isnull=True, agent_id__isnull=True
    ).delete()
    WalletTransaction.objects.filter(
        user_id__isnull=True, company_id__isnull=True, agent_id__isnull=True
    ).delete()

    # 2) Explicit rule from business:
    # if user + company or user + agent are set, clear user.
    Wallet.objects.filter(user_id__isnull=False, company_id__isnull=False).update(
        user_id=None
    )
    Wallet.objects.filter(user_id__isnull=False, agent_id__isnull=False).update(
        user_id=None
    )
    WalletTransaction.objects.filter(
        user_id__isnull=False, company_id__isnull=False
    ).update(user_id=None)
    WalletTransaction.objects.filter(
        user_id__isnull=False, agent_id__isnull=False
    ).update(user_id=None)

    # 3) Final normalization safety: if company exists, keep company only.
    Wallet.objects.filter(company_id__isnull=False).update(user_id=None, agent_id=None)
    WalletTransaction.objects.filter(company_id__isnull=False).update(
        user_id=None, agent_id=None
    )

    # 4) If no company but agent exists with user, keep agent only.
    Wallet.objects.filter(
        company_id__isnull=True, agent_id__isnull=False, user_id__isnull=False
    ).update(user_id=None)
    WalletTransaction.objects.filter(
        company_id__isnull=True, agent_id__isnull=False, user_id__isnull=False
    ).update(user_id=None)


class Migration(migrations.Migration):

    dependencies = [
        ("customer", "0004_customer_gstin"),
    ]

    operations = [
        migrations.RunPython(
            _cleanup_wallet_owner_scope, migrations.RunPython.noop
        ),
    ]
