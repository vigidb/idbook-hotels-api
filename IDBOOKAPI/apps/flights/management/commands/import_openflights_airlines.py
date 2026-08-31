import csv
from typing import Optional

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
import requests

from apps.flights.models import Airline


OPENFLIGHTS_AIRLINES_URL = (
    "https://raw.githubusercontent.com/jpatokal/openflights/master/data/airlines.dat"
)


class Command(BaseCommand):
    help = "Import or update airlines from the OpenFlights airlines.dat dataset"

    def add_arguments(self, parser):
        parser.add_argument(
            "--source",
            dest="source",
            help=(
                "Path to local airlines.dat file. "
                "If omitted, data is downloaded from the official OpenFlights GitHub URL."
            ),
        )
        parser.add_argument(
            "--truncate",
            action="store_true",
            help="Delete existing Airline rows before import (use with caution)",
        )

    def handle(self, *args, **options):
        source = options.get("source")
        truncate = options.get("truncate", False)

        if truncate:
            self.stdout.write(self.style.WARNING("Truncating existing Airline data..."))
            Airline.objects.all().delete()

        try:
            if source:
                self.stdout.write(f"Loading airlines from local file: {source}")
                with open(source, "r", encoding="utf-8") as f:
                    self._import_file(f)
            else:
                self.stdout.write(
                    f"Downloading airlines.dat from {OPENFLIGHTS_AIRLINES_URL}..."
                )
                resp = requests.get(OPENFLIGHTS_AIRLINES_URL, timeout=60)
                resp.raise_for_status()
                content = resp.content.decode("utf-8", errors="replace")
                self._import_file(content.splitlines())

        except Exception as exc:
            raise CommandError(f"Failed to import airlines: {exc}")

    def _parse_field(self, value: Optional[str]) -> str:
        """Convert OpenFlights special null markers ("\\N", "N/A", "-") to empty strings."""
        if value is None:
            return ""
        value = value.strip()
        if value in {"\\N", "N/A", "-"}:
            return ""
        return value

    @transaction.atomic
    def _import_file(self, iterable):
        reader = csv.reader(iterable)
        count = 0
        created = 0
        updated = 0

        for row in reader:
            # print(row)
            if not row or len(row) < 8:
                continue

            try:
                openflights_id = int(row[0])
            except (TypeError, ValueError):
                # Skip rows without a valid numeric ID
                continue

            name = self._parse_field(row[1])
            alias = self._parse_field(row[2])
            iata = self._parse_field(row[3])  # 2-letter IATA code
            icao = self._parse_field(row[4])  # 3-letter ICAO code
            callsign = self._parse_field(row[5])
            country = self._parse_field(row[6])
            active = row[7].strip() if len(row) > 7 else "Y"
            if active not in {"Y", "N"}:
                active = "Y"

            # We allow null/blank IATA code because many entries lack one.
            # Keep code unique where present.
            defaults = {
                "name": name,
                "alias": alias,
                "code": iata or None,
                "icao_code": icao,
                "callsign": callsign,
                "country": country,
                "active": active,
                # Keep existing internal flags/category where possible
            }

            obj, created_flag = Airline.objects.update_or_create(
                openflights_id=openflights_id,
                defaults=defaults,
            )

            count += 1
            if created_flag:
                created += 1
            else:
                updated += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Imported {count} airline rows (created={created}, updated={updated}) from OpenFlights"
            )
        )
