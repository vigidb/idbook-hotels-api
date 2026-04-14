"""
CSV export helpers for admin superuser exports.
"""
import csv
import json
from typing import Iterable, List

from django.http import HttpResponse

# Safety cap for bulk exports
MAX_EXPORT_ROWS = 50_000

# CSV column order: all email-related fields, then name-related, then phone-related,
# then remaining keys A–Z. Nested keys use "__" (e.g. customer_details__email) — we match
# on the last path segment (covers users, business details, companies, agents).

_NAME_LEAVES_EXACT = frozenset(
    {
        "name",
        "first_name",
        "last_name",
        "company_name",
        "agent_name",
        "business_name",
        "brand_name",
        "contact_person_name",
    }
)

_PHONE_LEAVES_EXACT = frozenset(
    {
        "phone",
        "phone_no",
        "company_phone",
        "agent_phone",
        "business_phone",
        "contact_number",
        "mobile_number",
        "alternate_phone",
    }
)


def _column_leaf(col: str) -> str:
    return col.split("__")[-1].lower()


def _is_name_leaf(leaf: str) -> bool:
    if leaf in _NAME_LEAVES_EXACT:
        return True
    # e.g. nested *username*, *display_name*; avoid classifying *email* / *phone* here
    if "email" in leaf or "phone" in leaf or "mobile" in leaf:
        return False
    if leaf.endswith("name"):
        return True
    return False


def _is_phone_leaf(leaf: str) -> bool:
    if leaf in _PHONE_LEAVES_EXACT:
        return True
    if "phone" in leaf or "mobile" in leaf:
        return True
    return False


def order_csv_fieldnames(keys: Iterable[str]) -> List[str]:
    """Email columns first, then name-related, then phone-related; rest sorted A–Z."""

    def sort_key(col: str) -> tuple:
        leaf = _column_leaf(col)
        if "email" in leaf:
            return (0, col)
        if _is_name_leaf(leaf):
            return (1, col)
        if _is_phone_leaf(leaf):
            return (2, col)
        return (3, col)

    return sorted(set(keys), key=sort_key)


def flatten_for_csv(obj, parent_key="", sep="__"):
    """Flatten nested dict/list structures for CSV columns."""
    items = {}
    if obj is None:
        return {}
    if isinstance(obj, dict):
        for k, v in obj.items():
            new_key = f"{parent_key}{sep}{k}" if parent_key else str(k)
            if isinstance(v, dict):
                items.update(flatten_for_csv(v, new_key, sep))
            elif isinstance(v, list):
                items[new_key] = json.dumps(v, default=str)
            else:
                items[new_key] = "" if v is None else v
    return items


def csv_http_response_from_records(records, filename_base):
    """
    Build a CSV HttpResponse from a list of plain dicts (e.g. serializer.data).
    Adds UTF-8 BOM for Excel compatibility.
    """
    rows = [flatten_for_csv(r) for r in records]
    if rows:
        keys_set = set()
        for r in rows:
            keys_set.update(r.keys())
        all_keys = order_csv_fieldnames(keys_set)
    else:
        all_keys = []

    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename_base}"'
    response.write("\ufeff")
    writer = csv.DictWriter(response, fieldnames=all_keys, extrasaction="ignore")
    writer.writeheader()
    for r in rows:
        writer.writerow({k: r.get(k, "") for k in all_keys})
    return response
