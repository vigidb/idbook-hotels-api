from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("customer", "0009_alter_wallettransaction_payment_medium"),
        ("customer", "0009_sync_wallettransaction_success_from_status"),
    ]

    operations = []
