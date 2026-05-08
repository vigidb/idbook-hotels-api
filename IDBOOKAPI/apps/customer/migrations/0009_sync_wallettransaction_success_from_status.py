from django.db import migrations


def _sync_success_flag(apps, schema_editor):
    WalletTransaction = apps.get_model("customer", "WalletTransaction")
    WalletTransaction.objects.filter(status__iexact="Completed").exclude(
        is_transaction_success=True
    ).update(is_transaction_success=True)
    WalletTransaction.objects.exclude(status__iexact="Completed").exclude(
        is_transaction_success=False
    ).update(is_transaction_success=False)


class Migration(migrations.Migration):

    dependencies = [
        ("customer", "0008_wallet_owner_scope_constraints"),
    ]

    operations = [
        migrations.RunPython(_sync_success_flag, migrations.RunPython.noop),
    ]
