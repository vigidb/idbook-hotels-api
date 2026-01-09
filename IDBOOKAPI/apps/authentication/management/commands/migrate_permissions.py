"""
Management command to verify Django Groups exist.
Since we're using Django's built-in Group and Permission models directly,
this command just verifies that required groups exist.
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group
from apps.authentication.constants import UserGroups


class Command(BaseCommand):
    help = "Verify that required Django Groups exist (no metadata needed)"

    def handle(self, *args, **options):
        self.stdout.write("Verifying Django Groups exist...")
        
        required_groups = [
            UserGroups.BUSINESS_GRP,
            UserGroups.CORPORATE_GRP,
            UserGroups.B2C_GRP,
            UserGroups.HOTELIER_GRP,
            UserGroups.FRANCHISE_GRP,
            UserGroups.AGENT_GRP,
        ]
        
        missing_groups = []
        existing_groups = []
        
        for group_code in required_groups:
            group, created = Group.objects.get_or_create(name=group_code)
            if created:
                self.stdout.write(
                    self.style.WARNING(f"  Created missing group: {group_code}")
                )
                missing_groups.append(group_code)
            else:
                self.stdout.write(
                    self.style.SUCCESS(f"  Group exists: {group_code}")
                )
                existing_groups.append(group_code)
        
        self.stdout.write(f"\nSummary:")
        self.stdout.write(f"  Existing groups: {len(existing_groups)}")
        self.stdout.write(f"  Created groups: {len(missing_groups)}")
        
        if missing_groups:
            self.stdout.write(
                self.style.SUCCESS(f"\nCreated {len(missing_groups)} missing groups")
            )
        else:
            self.stdout.write(
                self.style.SUCCESS("\nAll required groups exist!")
            )
