from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q

from apps.messaging.models import Contact


class Command(BaseCommand):
    help = (
        "Fill empty Contact.name with the local part of the email (text before '@') "
        "for contacts that have an email but no name. Dry-run by default; pass --apply to write."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            dest="apply",
            default=False,
            help="Actually write changes. Without this flag the command only reports (dry run).",
        )
        parser.add_argument(
            "--limit",
            dest="limit",
            type=int,
            default=0,
            help="Optional cap on the number of contacts to process.",
        )
        parser.add_argument(
            "--batch-size",
            dest="batch_size",
            type=int,
            default=1000,
            help="Number of rows per bulk_update batch (default 1000).",
        )

    def handle(self, *args, **options):
        apply_changes = options.get("apply", False)
        limit = options.get("limit") or 0
        batch_size = max(1, options.get("batch_size") or 1000)

        # Empty name (blank=True stores ""), but a non-empty email present.
        qs = (
            Contact.objects.filter(Q(name__isnull=True) | Q(name__exact=""))
            .exclude(Q(email__isnull=True) | Q(email__exact=""))
            .order_by("id")
        )
        if limit > 0:
            qs = qs[:limit]

        total = 0
        updated = 0
        skipped = 0
        batch = []

        for contact in qs.iterator():
            total += 1
            local_part = (contact.email or "").split("@", 1)[0].strip()
            if not local_part:
                # Email had no usable local part (e.g. "@example.com"); leave it alone.
                skipped += 1
                continue

            if apply_changes:
                contact.name = local_part
                batch.append(contact)
                if len(batch) >= batch_size:
                    with transaction.atomic():
                        Contact.objects.bulk_update(batch, ["name"])
                    batch.clear()
            else:
                # Preview a few examples so you can eyeball the mapping.
                if updated < 20:
                    self.stdout.write(f"  {contact.id}: '{contact.email}' -> name='{local_part}'")
            updated += 1

        if apply_changes and batch:
            with transaction.atomic():
                Contact.objects.bulk_update(batch, ["name"])
            batch.clear()

        mode = "APPLIED" if apply_changes else "DRY RUN (no changes written)"
        self.stdout.write(
            self.style.SUCCESS(
                f"{mode}. matched={total}, would_update={updated}, skipped_no_local_part={skipped}"
            )
        )
        if not apply_changes and updated:
            self.stdout.write(
                self.style.WARNING("Re-run with --apply to write these changes.")
            )
