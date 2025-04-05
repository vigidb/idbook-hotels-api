import json
from django.core.serializers.json import DjangoJSONEncoder
from apps.hotels.models import Room, Property
from apps.hotels.submodels.related_models import DynamicRoomPricing


def is_numeric_string(value):
    """Check if a value is a string that should be an integer."""
    if not isinstance(value, str):
        return False
    try:
        int(value)
        return True
    except (ValueError, TypeError):
        return False


def scan_room_models():
    """Scan Room models for string values that should be integers."""
    rooms_with_issues = []
    rooms = Room.objects.all()

    for room in rooms:
        issues = {}

        numeric_fields = ["room_size", "no_available_rooms"]
        for field in numeric_fields:
            value = getattr(room, field, None)
            if is_numeric_string(value):
                issues.setdefault("top_level_fields", {})[field] = value

        if room.room_occupancy:
            occupancy_issues = {}
            for field in ["base_adults", "max_adults", "max_children", "max_occupancy"]:
                if field in room.room_occupancy and is_numeric_string(room.room_occupancy[field]):
                    occupancy_issues[field] = room.room_occupancy[field]
            if occupancy_issues:
                issues["room_occupancy"] = occupancy_issues

        if room.room_price:
            price_issues = {}
            fields = ["price_4hrs", "price_8hrs", "price_12hrs", "base_rate",
                      "extra_bed_price", "extra_bed_price_4hrs", "extra_bed_price_8hrs", "extra_bed_price_12hrs"]
            for field in fields:
                if field in room.room_price and is_numeric_string(room.room_price[field]):
                    price_issues[field] = room.room_price[field]

            if "child_bed_price" in room.room_price and isinstance(room.room_price["child_bed_price"], list):
                child_issues = []
                for i, child in enumerate(room.room_price["child_bed_price"]):
                    item_issues = {}

                    if "age_limit" in child and isinstance(child["age_limit"], list):
                        age_issues = [{"index": j, "value": v} for j, v in enumerate(child["age_limit"]) if is_numeric_string(v)]
                        if age_issues:
                            item_issues["age_limit"] = age_issues

                    for f in ["child_bed_price", "child_bed_price_4hrs", "child_bed_price_8hrs", "child_bed_price_12hrs"]:
                        if f in child and is_numeric_string(child[f]):
                            item_issues[f] = child[f]

                    if item_issues:
                        child_issues.append({"index": i, "issues": item_issues})

                if child_issues:
                    price_issues["child_bed_price"] = child_issues

            if price_issues:
                issues["room_price"] = price_issues

        if issues:
            prop_name = None
            try:
                prop = Property.objects.get(id=room.property_id)
                prop_name = prop.name
            except:
                prop_name = f"Unknown (ID: {room.property_id})"

            rooms_with_issues.append({
                "id": room.id,
                "name": room.name,
                "property_id": room.property_id,
                "property_name": prop_name,
                "issues": issues
            })

    return rooms_with_issues


def scan_dynamic_pricing_models():
    """Scan DynamicRoomPricing models for string values that should be integers."""
    prices_with_issues = []
    all_prices = DynamicRoomPricing.objects.all()

    for pricing in all_prices:
        issues = {}
        if pricing.room_price:
            price_issues = {}
            fields = ["price_4hrs", "price_8hrs", "price_12hrs", "base_rate",
                      "extra_bed_price", "extra_bed_price_4hrs", "extra_bed_price_8hrs", "extra_bed_price_12hrs"]
            for field in fields:
                if field in pricing.room_price and is_numeric_string(pricing.room_price[field]):
                    price_issues[field] = pricing.room_price[field]

            if "child_bed_price" in pricing.room_price and isinstance(pricing.room_price["child_bed_price"], list):
                child_issues = []
                for i, child in enumerate(pricing.room_price["child_bed_price"]):
                    item_issues = {}

                    if "age_limit" in child and isinstance(child["age_limit"], list):
                        age_issues = [{"index": j, "value": v} for j, v in enumerate(child["age_limit"]) if is_numeric_string(v)]
                        if age_issues:
                            item_issues["age_limit"] = age_issues

                    for f in ["child_bed_price", "child_bed_price_4hrs", "child_bed_price_8hrs", "child_bed_price_12hrs"]:
                        if f in child and is_numeric_string(child[f]):
                            item_issues[f] = child[f]

                    if item_issues:
                        child_issues.append({"index": i, "issues": item_issues})

                if child_issues:
                    price_issues["child_bed_price"] = child_issues

            if price_issues:
                issues["room_price"] = price_issues

        if issues:
            try:
                prop = Property.objects.get(id=pricing.for_property_id)
                prop_name = prop.name
            except:
                prop_name = f"Unknown (ID: {pricing.for_property_id})"

            try:
                room = Room.objects.get(id=pricing.for_room_id)
                room_name = room.name
            except:
                room_name = f"Unknown (ID: {pricing.for_room_id})"

            prices_with_issues.append({
                "id": pricing.id,
                "for_property_id": pricing.for_property_id,
                "property_name": prop_name,
                "for_room_id": pricing.for_room_id,
                "room_name": room_name,
                "start_date": pricing.start_date.strftime("%Y-%m-%d %H:%M:%S") if pricing.start_date else None,
                "end_date": pricing.end_date.strftime("%Y-%m-%d %H:%M:%S") if pricing.end_date else None,
                "issues": issues
            })

    return prices_with_issues


def generate_report():
    rooms_with_issues = scan_room_models()
    prices_with_issues = scan_dynamic_pricing_models()

    report_data = {
        "rooms_with_issues_count": len(rooms_with_issues),
        "dynamic_prices_with_issues_count": len(prices_with_issues),
        "rooms_with_issues": rooms_with_issues,
        "dynamic_prices_with_issues": prices_with_issues
    }
    return report_data
