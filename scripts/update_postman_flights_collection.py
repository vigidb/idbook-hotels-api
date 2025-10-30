#!/usr/bin/env python3
"""
Update Postman collection for Flights Enhanced API to current request structure.
- Fix search endpoint to /flights/search/availability/
- Set booking endpoint to /booking/flight-bookings/create-booking/
- For each booking request, transform body to the same SCHEMA as Scenario 1 'Create Booking'
  (do NOT copy values; keep scenario-specific passengers/contact; infer trip/route from the
   scenario's Search request; use Postman vars like {{track_id}}, {{pricing_token}}, {{total_amount}} for unknowns).

Usage:
  python3 scripts/update_postman_flights_collection.py \
    --file "IDBOOKAPI/postman/IDBOOK Flights - Enhanced API Test Scenarios (22).postman_collection.json"

Creates a .bak backup and overwrites the original.
"""

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple


def _json_loads(s: str) -> Dict[str, Any]:
    try:
        return json.loads(s)
    except Exception:
        return {}


def _json_dumps(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2)


def fix_search_url(url: Dict[str, Any]) -> None:
    if not isinstance(url, dict):
        return
    raw = url.get("raw")
    path = url.get("path") or []
    if isinstance(raw, str) and "/flights/search/search/" in raw:
        url["raw"] = raw.replace("/flights/search/search/", "/flights/search/availability/")
        try:
            i = path.index("search")
            if i + 1 < len(path) and path[i + 1] == "search":
                path[i + 1] = "availability"
                url["path"] = path
        except ValueError:
            pass


def fix_booking_url(url: Dict[str, Any]) -> None:
    if not isinstance(url, dict):
        return
    raw = url.get("raw")
    path = url.get("path") or []
    if isinstance(raw, str) and raw.endswith("/booking/flight-bookings/"):
        url["raw"] = raw + "create-booking/"
        if path:
            if path and path[-1] == "":
                if "create-booking" not in path:
                    path.insert(len(path)-1, "create-booking")
            else:
                if "create-booking" not in path:
                    path.append("create-booking")
            url["path"] = path


def parse_search_defaults(folder_items: List[Dict[str, Any]]) -> Tuple[str, str, str]:
    """Return (origin, destination, trip_type) from the folder's Search request body if present."""
    origin = destination = ""
    trip_type = "O"
    for it in folder_items:
        req = it.get("request") or {}
        url = req.get("url") or {}
        raw = url.get("raw") if isinstance(url, dict) else None
        if not isinstance(raw, str):
            continue
        if "/flights/search/" in raw:
            body = req.get("body") or {}
            if body.get("mode") == "raw" and isinstance(body.get("raw"), str):
                data = _json_loads(body["raw"]) or {}
                origin = (data.get("origin") or origin or "").upper()
                destination = (data.get("destination") or destination or "").upper()
                trip_type = (data.get("trip_type") or trip_type or "O").upper()
            break
    return origin, destination, trip_type


def title_case_gender(g: str) -> str:
    g = (g or "").strip().lower()
    if g.startswith("f"):
        return "Female"
    return "Male"


def pax_to_airiq(p: Dict[str, Any], ref_default: int) -> Dict[str, Any]:
    return {
        "PaxRefNumber": str(p.get("passenger_ref", ref_default)),
        "Title": (p.get("title") or "MR").upper(),
        "FirstName": (p.get("first_name") or "").upper(),
        "LastName": (p.get("last_name") or "").upper(),
        "DOB": p.get("date_of_birth") or "01/01/1990",
        "Gender": title_case_gender(p.get("gender")),
        "PaxType": (p.get("passenger_type") or "ADT").upper(),
        "PassportNo": p.get("passport_number", ""),
        "PassportExpiry": p.get("passport_expiry", ""),
        "PassportIssuedDate": p.get("passport_issued_date", ""),
        "InfantRef": str(p.get("infant_ref", "")) if p.get("infant_ref") else "",
    }


def build_booking_body(template_schema: Dict[str, Any]) -> Dict[str, Any]:
    """Return a new booking body matching the canonical schema, preserving passengers/contact and
    inferring counts + base route; unknowns use Postman variables.
    template_schema keys expected: passengers (list), contact (dict), base_origin, base_destination, trip_type
    """
    passengers = template_schema.get("passengers") or []
    contact = template_schema.get("contact") or {}
    base_origin = template_schema.get("base_origin") or ""
    base_destination = template_schema.get("base_destination") or ""
    trip_type = (template_schema.get("trip_type") or "O").upper()

    # Count pax types
    adults = sum(1 for p in passengers if (p.get("passenger_type") or "ADT").upper() == "ADT") or 1
    children = sum(1 for p in passengers if (p.get("passenger_type") or "").upper() == "CHD")
    infants = sum(1 for p in passengers if (p.get("passenger_type") or "").upper() == "INF")

    pax_list = [pax_to_airiq(p, i+1) for i, p in enumerate(passengers)] or [
        pax_to_airiq({"passenger_type": "ADT", "title": "MR", "first_name": "TEST", "last_name": "USER", "date_of_birth": "01/01/1990", "gender": "male"}, 1)
    ]

    return {
        "AdultCount": adults,
        "ChildCount": children,
        "InfantCount": infants,
        "ItineraryFlightsInfo": [
            {
                "Token": "{{pricing_token}}",
                "FlighstInfo": [
                    {
                        "FlightID": "{{flight_id1}}",
                        "FlightNumber": "{{flight_number1}}",
                        "Origin": base_origin,
                        "Destination": base_destination,
                        "DepartureDateTime": "{{dep_dt1}}",
                        "ArrivalDateTime": "{{arr_dt1}}",
                    }
                ],
                "SeatsSSRInfo": [],
                "BaggSSRInfo": [],
                "MealsSSRInfo": [],
                "OtherSSRInfo": [],
                "PaymentInfo": [
                    {
                        "TotalAmount": "{{total_amount}}",
                        "BaseAmount": "{{base_amount}}",
                        "GrossAmount": "{{gross_amount}}",
                    }
                ],
            }
        ],
        "PaxDetailsInfo": pax_list,
        "AddressDetails": {
            "CountryCode": contact.get("country_code") or "91",
            "ContactNumber": contact.get("phone") or "",
            "EmailID": contact.get("email") or "",
        },
        "GSTInfo": {
            "GSTNumber": "",
            "GSTCompanyName": "",
            "GSTAddress": "",
            "GSTEmailID": "",
            "GSTMobileNumber": "",
        },
        "TripType": trip_type,
        "BlockPNR": False,
        "BaseOrigin": base_origin,
        "BaseDestination": base_destination,
        "TrackId": "{{track_id}}",
    }


def transform_folder(folder: Dict[str, Any]) -> None:
    items = folder.get("item") or []
    base_origin, base_destination, trip_type = parse_search_defaults(items)

    for it in items:
        # Recurse subfolders
        if "item" in it:
            transform_folder(it)
            continue

        req = it.get("request") or {}
        method = (req.get("method") or "").upper()
        url = req.get("url") or {}
        raw = url.get("raw") if isinstance(url, dict) else ""

        # Normalize search URLs
        if isinstance(raw, str) and "/flights/search/" in raw:
            fix_search_url(url)
            continue

        # Only operate on POST booking creation calls
        if not (method == "POST" and isinstance(raw, str) and "/booking/flight-bookings/" in raw and "cancel" not in raw and "reschedule" not in raw):
            continue

        # Normalize booking URL to create-booking endpoint
        fix_booking_url(url)

        # If body already looks canonical (has AdultCount and ItineraryFlightsInfo), skip
        body = req.get("body") or {}
        raw_body = body.get("raw") if body.get("mode") == "raw" else None
        existing = _json_loads(raw_body) if isinstance(raw_body, str) else {}
        if isinstance(existing, dict) and ("AdultCount" in existing and "ItineraryFlightsInfo" in existing):
            continue

        # Build template schema from existing simplified body if present
        passengers = []
        contact = {}
        if isinstance(existing, dict):
            passengers = existing.get("passengers") or existing.get("PaxDetailsInfo") or []
            contact = existing.get("contact") or existing.get("AddressDetails") or {}

        new_body = build_booking_body({
            "passengers": passengers,
            "contact": contact,
            "base_origin": base_origin,
            "base_destination": base_destination,
            "trip_type": trip_type,
        })

        req["body"] = {"mode": "raw", "raw": _json_dumps(new_body)}
        it["request"] = req


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", required=True, help="Postman collection JSON file path")
    args = ap.parse_args()

    p = Path(args.file)
    data = json.loads(p.read_text())

    # Transform top-level items
    for node in data.get("item", []):
        if "item" in node:
            transform_folder(node)
        else:
            # standalone requests (rare) — still fix search URLs
            req = node.get("request") or {}
            url = req.get("url") or {}
            fix_search_url(url)

    # Backup and write
    backup = p.with_suffix(p.suffix + ".bak")
    backup.write_text(_json_dumps(data))
    p.write_text(_json_dumps(data))
    print(f"Updated: {p}\nBackup: {backup}")


if __name__ == "__main__":
    main()
