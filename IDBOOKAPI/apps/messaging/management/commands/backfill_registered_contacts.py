from django.core.management.base import BaseCommand

from apps.authentication.constants import ALL_GROUP_CHOICES
from apps.authentication.models import User
from apps.messaging.services import upsert_contact_for_registered_user


class Command(BaseCommand):
    help = "Backfill messaging contacts for existing registered users."

    def add_arguments(self, parser):
        parser.add_argument(
            "--group",
            dest="group",
            default="",
            help="Optional group filter (e.g. B2C-GRP, CORPORATE-GRP).",
        )
        parser.add_argument(
            "--limit",
            dest="limit",
            type=int,
            default=0,
            help="Optional limit for number of users to process.",
        )

    def handle(self, *args, **options):
        allowed_groups = set(dict(ALL_GROUP_CHOICES).keys())
        selected_group = (options.get("group") or "").strip()
        if selected_group and selected_group not in allowed_groups:
            self.stderr.write(
                self.style.ERROR(f"Invalid --group '{selected_group}'.")
            )
            return

        qs = User.objects.all().order_by("id")
        if selected_group:
            qs = qs.filter(default_group=selected_group)
        else:
            qs = qs.filter(default_group__in=allowed_groups)

        limit = options.get("limit") or 0
        if limit > 0:
            qs = qs[:limit]

        created_count = 0
        linked_count = 0
        skipped_count = 0

        for user in qs.iterator():
            stats = upsert_contact_for_registered_user(
                user, source="registration_backfill"
            )
            created_count += stats.get("created", 0)
            linked_count += stats.get("updated", 0)
            skipped_count += stats.get("skipped", 0)

        self.stdout.write(
            self.style.SUCCESS(
                "Backfill completed. "
                f"created={created_count}, linked_or_updated={linked_count}, skipped={skipped_count}"
            )
        )
