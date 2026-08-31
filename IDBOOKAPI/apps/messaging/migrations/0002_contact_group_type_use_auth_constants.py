# Generated manually: migrate Contact/Campaign group_type to auth constants

from django.db import migrations

# Map legacy group_type values to apps.authentication.constants (UserGroups)
LEGACY_TO_NEW_GROUP_TYPE = {
    "GUEST": "B2C-GUEST",
    "B2C": "B2C-GRP",
    "CORPORATE": "CORPORATE-GRP",
    "AGENT": "AGENT-GRP",
    "HOTELIER": "HOTELIER-GRP",
    "BUSINESS_STAFF": "BUSINESS-GRP",
}


def migrate_group_types_forward(apps, schema_editor):
    Contact = apps.get_model("messaging", "Contact")
    Campaign = apps.get_model("messaging", "Campaign")
    for old_val, new_val in LEGACY_TO_NEW_GROUP_TYPE.items():
        Contact.objects.filter(group_type=old_val).update(group_type=new_val)
        Campaign.objects.filter(target_group_type=old_val).update(target_group_type=new_val)


def migrate_group_types_backward(apps, schema_editor):
    Contact = apps.get_model("messaging", "Contact")
    Campaign = apps.get_model("messaging", "Campaign")
    for old_val, new_val in LEGACY_TO_NEW_GROUP_TYPE.items():
        Contact.objects.filter(group_type=new_val).update(group_type=old_val)
        Campaign.objects.filter(target_group_type=new_val).update(target_group_type=old_val)


class Migration(migrations.Migration):

    dependencies = [
        ("messaging", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(migrate_group_types_forward, migrate_group_types_backward),
    ]
