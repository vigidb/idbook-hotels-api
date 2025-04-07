import json
from django.core.serializers.json import DjangoJSONEncoder
from apps.hotels.models import Room, Property
from apps.hotels.submodels.related_models import DynamicRoomPricing
from apps.hotels.utils import db_utils as hotel_db_utils
from django.db import transaction


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

def convert_dict_values(data, fields):
    changes = []
    modified = False
    for field in fields:
        if field in data and is_numeric_string(data[field]):
            changes.append(f"{field}: '{data[field]}' -> {int(data[field])}")
            data[field] = int(data[field])
            modified = True
    return modified, changes

def convert_child_bed_prices(child_list):
    changes = []
    modified = False
    fields = ["child_bed_price", "child_bed_price_4hrs", "child_bed_price_8hrs", "child_bed_price_12hrs"]
    for i, child in enumerate(child_list):
        # Convert age_limit array
        if "age_limit" in child and isinstance(child["age_limit"], list):
            for j, age in enumerate(child["age_limit"]):
                if is_numeric_string(age):
                    changes.append(f"child_bed_price[{i}].age_limit[{j}]: '{age}' -> {int(age)}")
                    child["age_limit"][j] = int(age)
                    modified = True
        # Convert child bed price fields
        mod, chg = convert_dict_values(child, fields)
        if mod:
            modified = True
            changes.extend([f"child_bed_price[{i}].{c}" for c in chg])
    return modified, changes

def convert_room_data(room_obj):
    changes = []

    numeric_fields = ["room_size", "no_available_rooms"]
    modified, chg = convert_dict_values(room_obj.__dict__, numeric_fields)
    changes.extend(chg)

    occupancy_data = room_obj.room_occupancy or {}
    mod_occ, chg_occ = convert_dict_values(occupancy_data, ["base_adults", "max_adults", "max_children", "max_occupancy"])
    if mod_occ:
        room_obj.room_occupancy = occupancy_data
        changes.extend([f"room_occupancy.{c}" for c in chg_occ])

    price_data = room_obj.room_price or {}
    price_fields = ["price_4hrs", "price_8hrs", "price_12hrs", "base_rate", "extra_bed_price", "extra_bed_price_4hrs", "extra_bed_price_8hrs", "extra_bed_price_12hrs"]
    mod_price, chg_price = convert_dict_values(price_data, price_fields)
    changes.extend([f"room_price.{c}" for c in chg_price])

    if "child_bed_price" in price_data and isinstance(price_data["child_bed_price"], list):
        mod_cb, chg_cb = convert_child_bed_prices(price_data["child_bed_price"])
        if mod_cb:
            changes.extend([f"room_price.{c}" for c in chg_cb])

    room_obj.room_price = price_data
    if changes:
        room_obj.save()

    return changes

def convert_dynamic_pricing_data(pricing_obj):
    changes = []

    price_data = pricing_obj.room_price or {}
    price_fields = ["price_4hrs", "price_8hrs", "price_12hrs", "base_rate", "extra_bed_price", "extra_bed_price_4hrs", "extra_bed_price_8hrs", "extra_bed_price_12hrs"]
    mod_price, chg_price = convert_dict_values(price_data, price_fields)
    changes.extend([f"room_price.{c}" for c in chg_price])

    if "child_bed_price" in price_data and isinstance(price_data["child_bed_price"], list):
        mod_cb, chg_cb = convert_child_bed_prices(price_data["child_bed_price"])
        if mod_cb:
            changes.extend([f"room_price.{c}" for c in chg_cb])

    pricing_obj.room_price = price_data
    if changes:
        pricing_obj.save()

    return changes

def generate_conversion_report():
    converted_rooms = []
    converted_pricings = []

    for room in Room.objects.all():
        changes = convert_room_data(room)
        if changes:
            try:
                prop = Property.objects.get(id=room.property_id)
                prop_name = prop.name
            except:
                prop_name = f"Unknown (ID: {room.property_id})"

            converted_rooms.append({
                "id": room.id,
                "name": room.name,
                "property_id": room.property_id,
                "property_name": prop_name,
                "changes": changes
            })

    for pricing in DynamicRoomPricing.objects.all():
        changes = convert_dynamic_pricing_data(pricing)
        if changes:
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

            converted_pricings.append({
                "id": pricing.id,
                "for_property_id": pricing.for_property_id,
                "property_name": prop_name,
                "for_room_id": pricing.for_room_id,
                "room_name": room_name,
                "start_date": pricing.start_date.strftime("%Y-%m-%d %H:%M:%S") if pricing.start_date else None,
                "end_date": pricing.end_date.strftime("%Y-%m-%d %H:%M:%S") if pricing.end_date else None,
                "changes": changes
            })

    return {
        "converted_rooms_count": len(converted_rooms),
        "converted_dynamic_pricings_count": len(converted_pricings),
        "converted_rooms": converted_rooms,
        "converted_dynamic_pricings": converted_pricings
    }

def update_all_properties_starting_prices():
    all_properties = Property.objects.all()
    updated_count = 0

    for prop in all_properties:
        property_id = prop.id
        has_active_rooms = Room.objects.filter(property_id=property_id, active=True).exists()
        if not has_active_rooms:
            continue  # Skip if no active rooms for this property

        try:
            with transaction.atomic():
                previous_price_details = prop.starting_price_details or {}
                
                starting_price_details = hotel_db_utils.get_slot_based_starting_room_price(property_id)
                is_slot_price_enabled = hotel_db_utils.check_slot_price_enabled(property_id)
                hotel_db_utils.room_based_property_update(property_id, starting_price_details, is_slot_price_enabled)

                updated_count += 1
                print(f"Updated Property ID {property_id}\nFROM: {json.dumps(previous_price_details, sort_keys=True)}\nTO:   {json.dumps(starting_price_details, sort_keys=True)}\n")
        except Exception as e:
            print(f"Failed to update Property ID {property_id}: {e}")

    print(f"\nTotal Properties Updated: {updated_count}")


