"""
Management command to migrate existing user.roles + user.business_id to UserRole records.
This is a manual migration script that should be run after the new permission system is set up.
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from apps.authentication.models import User, Role, UserRole
from apps.org_managements.models import BusinessDetail


class Command(BaseCommand):
    help = "Migrate existing user.roles + user.business_id to UserRole records"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Preview changes without applying them",
        )
        parser.add_argument(
            "--user-id",
            type=int,
            help="Migrate only a specific user (for testing)",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        user_id = options.get("user_id")

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN MODE - No changes will be saved"))

        # Get users to migrate
        if user_id:
            users = User.objects.filter(id=user_id)
            if not users.exists():
                self.stdout.write(self.style.ERROR(f"User with id {user_id} not found"))
                return
        else:
            users = User.objects.filter(roles__isnull=False).distinct()

        total_users = users.count()
        self.stdout.write(f"Found {total_users} users to migrate\n")

        migrated_count = 0
        skipped_count = 0
        error_count = 0

        for user in users:
            try:
                # Get user's roles
                user_roles = user.roles.all()
                if not user_roles.exists():
                    skipped_count += 1
                    continue

                # Get user's business
                business = None
                if user.business_id:
                    try:
                        business = BusinessDetail.objects.get(id=user.business_id)
                    except BusinessDetail.DoesNotExist:
                        self.stdout.write(
                            self.style.WARNING(
                                f"  User {user.id}: Business {user.business_id} not found, skipping"
                            )
                        )
                        skipped_count += 1
                        continue
                else:
                    # If no business_id, we can't create UserRole (business is required)
                    self.stdout.write(
                        self.style.WARNING(
                            f"  User {user.id}: No business_id, skipping"
                        )
                    )
                    skipped_count += 1
                    continue

                # Create UserRole records for each role
                created_for_user = 0
                for role in user_roles:
                    # Check if UserRole already exists
                    existing = UserRole.objects.filter(
                        user=user, role=role, business=business
                    ).first()

                    if existing:
                        self.stdout.write(
                            f"  User {user.id}: UserRole for role {role.name} already exists, skipping"
                        )
                        continue

                    if not dry_run:
                        with transaction.atomic():
                            UserRole.objects.create(
                                user=user,
                                role=role,
                                business=business,
                                is_active=True,
                                assigned_by=None,  # Migration, so no assigned_by
                            )
                            created_for_user += 1
                    else:
                        created_for_user += 1
                        self.stdout.write(
                            f"  Would create UserRole: user={user.id}, role={role.name}, business={business.id}"
                        )

                if created_for_user > 0:
                    migrated_count += 1
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"  User {user.id}: Created {created_for_user} UserRole records"
                        )
                    )

            except Exception as e:
                error_count += 1
                self.stdout.write(
                    self.style.ERROR(f"  User {user.id}: Error - {str(e)}")
                )

        # Summary
        self.stdout.write("\n" + "=" * 50)
        self.stdout.write("Migration Summary:")
        self.stdout.write(f"  Total users processed: {total_users}")
        self.stdout.write(f"  Successfully migrated: {migrated_count}")
        self.stdout.write(f"  Skipped: {skipped_count}")
        self.stdout.write(f"  Errors: {error_count}")

        if dry_run:
            self.stdout.write(
                self.style.WARNING("\nDRY RUN - No changes were saved. Run without --dry-run to apply.")
            )
        else:
            self.stdout.write(self.style.SUCCESS("\nMigration completed successfully!"))
