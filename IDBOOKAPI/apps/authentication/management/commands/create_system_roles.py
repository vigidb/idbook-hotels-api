"""
Management command to create system roles for all groups.
Creates system roles (BUS-ADMIN, CORP-ADMIN, etc.) with default permissions.
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission
from apps.authentication.models import Role, GroupMetadata
from apps.authentication.constants import UserGroups


class Command(BaseCommand):
    help = "Create system roles for all groups with default permissions"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Preview changes without applying them",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN MODE - No changes will be saved"))

        # System role definitions
        system_roles = {
            # BUSINESS-GRP roles
            UserGroups.BUSINESS_GRP: [
                {
                    "name": "Business Admin",
                    "short_code": "BA",
                    "permissions": [
                        "view_booking",
                        "add_booking",
                        "change_booking",
                        "view_wallet",
                        "add_wallet",
                        "view_corporate",
                        "add_corporate",
                        "change_corporate",
                        "view_hotel",
                        "view_agent",
                    ],
                },
                {
                    "name": "Business Finance",
                    "short_code": "BF",
                    "permissions": [
                        "view_booking",
                        "view_wallet",
                        "refund",
                        "invoice_generate",
                    ],
                },
                {
                    "name": "Business Corporate",
                    "short_code": "BC",
                    "permissions": [
                        "view_corporate",
                        "add_corporate",
                        "change_corporate",
                        "approve_corporate",
                    ],
                },
                {
                    "name": "Business Customer",
                    "short_code": "BCU",
                    "permissions": [
                        "view_booking",
                        "add_booking",
                    ],
                },
            ],
            # CORPORATE-GRP roles
            UserGroups.CORPORATE_GRP: [
                {
                    "name": "Corporate Admin",
                    "short_code": "CA",
                    "permissions": [
                        "view_booking",
                        "add_booking",
                        "view_corporate",
                        "change_corporate",
                    ],
                },
                {
                    "name": "Corporate Employee",
                    "short_code": "CE",
                    "permissions": [
                        "view_booking",
                        "add_booking",
                    ],
                },
            ],
            # HOTELIER-GRP roles
            UserGroups.HOTELIER_GRP: [
                {
                    "name": "Hotelier Admin",
                    "short_code": "HA",
                    "permissions": [
                        "view_hotel",
                        "change_hotel",
                        "manage_hotel",
                        "view_booking",
                    ],
                },
            ],
            # AGENT-GRP roles (name "AGENT-ADMIN" matches constants and get_group_based_on_name)
            UserGroups.AGENT_GRP: [
                {
                    "name": "AGENT-ADMIN",
                    "short_code": "AGT",
                    "permissions": [
                        "view_agent",
                        "change_agent",
                        "manage_agent",
                        "view_booking",
                        "add_booking",
                    ],
                },
            ],
            # B2C-GRP roles
            UserGroups.B2C_GRP: [
                {
                    "name": "B2C Customer",
                    "short_code": "B2C",
                    "permissions": [
                        "view_booking",
                        "add_booking",
                    ],
                },
            ],
        }

        created_roles = 0
        for group_code, roles in system_roles.items():
            try:
                group = Group.objects.get(name=group_code)
                self.stdout.write(f"\nProcessing group: {group_code}")

                for role_def in roles:
                    role_name = role_def["name"]
                    short_code = role_def["short_code"]

                    # Check if role already exists
                    existing_role = Role.objects.filter(
                        name=role_name, is_system_role=True, business=None
                    ).first()

                    if existing_role:
                        self.stdout.write(
                            f"  Role {role_name} already exists, skipping"
                        )
                        continue

                    # Create role
                    if not dry_run:
                        role = Role.objects.create(
                            name=role_name,
                            short_code=short_code,
                            group=group,
                            business=None,
                            is_system_role=True,
                        )

                        # Assign permissions
                        permission_codenames = role_def["permissions"]
                        permissions = Permission.objects.filter(
                            codename__in=permission_codenames
                        )
                        role.permissions.set(permissions)

                        created_roles += 1
                        self.stdout.write(
                            self.style.SUCCESS(
                                f"  Created role: {role_name} ({short_code}) with {permissions.count()} permissions"
                            )
                        )
                    else:
                        self.stdout.write(
                            f"  Would create role: {role_name} ({short_code}) with permissions: {permission_codenames}"
                        )

            except Group.DoesNotExist:
                self.stdout.write(
                    self.style.WARNING(f"  Group {group_code} does not exist, skipping")
                )

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f"\nDRY RUN - Would create {created_roles} roles. Run without --dry-run to apply."
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(f"\nCreated {created_roles} system roles successfully!")
            )
