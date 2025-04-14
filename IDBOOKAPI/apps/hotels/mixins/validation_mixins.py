class ValidationMixin:
    def validate_room_fields(self, data):
        numeric_fields = ["room_size", "no_available_rooms"]

        occupancy_fields = ["base_adults", "max_adults", "max_children", "max_occupancy"]

        room_price_fields = [
            "price_4hrs", "price_8hrs", "price_12hrs", "base_rate",
            "extra_bed_price", "extra_bed_price_4hrs", "extra_bed_price_8hrs", "extra_bed_price_12hrs"
        ]
        child_bed_fields = [
		    "child_bed_price", "child_bed_price_4hrs", "child_bed_price_8hrs", "child_bed_price_12hrs"
		]

        try:
            for field in numeric_fields:
                if field in data:
                    try:
                        data[field] = int(data[field])
                    except (ValueError, TypeError):
                        return False, {
                            "message": f"Invalid value for '{field}'. Must be an integer.",
                            "field": field,
                            "error_code": "INVALID_NUMBER_FIELD"
                        }

            if "room_occupancy" in data:
                for occ_field in occupancy_fields:
                    if occ_field in data["room_occupancy"]:
                        try:
                            data["room_occupancy"][occ_field] = int(data["room_occupancy"][occ_field])
                        except (ValueError, TypeError):
                            return False, {
                                "message": f"Invalid value for 'room_occupancy.{occ_field}'. Must be an integer.",
                                "field": f"room_occupancy.{occ_field}",
                                "error_code": "INVALID_NUMBER_FIELD"
                            }

            if "room_price" in data:
                for price_field in room_price_fields:
                    if price_field in data["room_price"]:
                        try:
                            data["room_price"][price_field] = int(data["room_price"][price_field])
                        except (ValueError, TypeError):
                            return False, {
                                "message": f"Invalid value for 'room_price.{price_field}'. Must be an integer.",
                                "field": f"room_price.{price_field}",
                                "error_code": "INVALID_NUMBER_FIELD"
                            }

                if "child_bed_price" in data["room_price"]:
                    for i, child_item in enumerate(data["room_price"]["child_bed_price"]):
                        if "age_limit" in child_item:
                            try:
                                for j, age in enumerate(child_item["age_limit"]):
                                    child_item["age_limit"][j] = int(age)
                            except (ValueError, TypeError):
                                return False, {
                                    "message": f"Invalid value for 'room_price.child_bed_price[{i}].age_limit'. Must be integers.",
                                    "field": f"room_price.child_bed_price[{i}].age_limit",
                                    "error_code": "INVALID_NUMBER_FIELD"
                                }

                        for field in child_bed_fields:
                            if field in child_item:
                                try:
                                    child_item[field] = int(child_item[field])
                                except (ValueError, TypeError):
                                    return False, {
                                        "message": f"Invalid value for 'room_price.child_bed_price[{i}].{field}'. Must be an integer.",
                                        "field": f"room_price.child_bed_price[{i}].{field}",
                                        "error_code": "INVALID_NUMBER_FIELD"
                                    }

        except Exception as e:
            return False, {
                "message": "Unexpected error during validation.",
                "error": str(e),
                "error_code": "VALIDATION_ERROR"
            }

        return True, {"message": "Validation successful"}

    def validate_dynamic_pricing_fields(self, data):
        numeric_fields = ["for_property", "for_room"]
        room_price_fields = [
            "price_4hrs", "price_8hrs", "price_12hrs", "base_rate",
            "extra_bed_price", "extra_bed_price_4hrs", "extra_bed_price_8hrs", "extra_bed_price_12hrs"
        ]
        child_bed_fields = [
            "child_bed_price", "child_bed_price_4hrs", "child_bed_price_8hrs", "child_bed_price_12hrs"
        ]
        try:
            # Validate top-level numeric fields
            for field in numeric_fields:
                if field in data:
                    try:
                        data[field] = int(data[field])
                    except (ValueError, TypeError):
                        return False, {
                            "message": f"Invalid value for '{field}'. Must be an integer.",
                            "field": field,
                            "error_code": "INVALID_NUMBER_FIELD"
                        }
            
            # Validate room_price fields
            if "room_price" in data:
                for price_field in room_price_fields:
                    if price_field in data["room_price"]:
                        try:
                            data["room_price"][price_field] = int(data["room_price"][price_field])
                        except (ValueError, TypeError):
                            return False, {
                                "message": f"Invalid value for 'room_price.{price_field}'. Must be an integer.",
                                "field": f"room_price.{price_field}",
                                "error_code": "INVALID_NUMBER_FIELD"
                            }
                
                # Validate child_bed_price array items
                if "child_bed_price" in data["room_price"]:
                    for i, child_item in enumerate(data["room_price"]["child_bed_price"]):
                        # Validate age_limit array
                        if "age_limit" in child_item:
                            try:
                                for j, age in enumerate(child_item["age_limit"]):
                                    child_item["age_limit"][j] = int(age)
                            except (ValueError, TypeError):
                                return False, {
                                    "message": f"Invalid value for 'room_price.child_bed_price[{i}].age_limit'. Must be integers.",
                                    "field": f"room_price.child_bed_price[{i}].age_limit",
                                    "error_code": "INVALID_NUMBER_FIELD"
                                }
                        
                        # Validate price fields in each child bed item
                        for field in child_bed_fields:
                            if field in child_item:
                                try:
                                    child_item[field] = int(child_item[field])
                                except (ValueError, TypeError):
                                    return False, {
                                        "message": f"Invalid value for 'room_price.child_bed_price[{i}].{field}'. Must be an integer.",
                                        "field": f"room_price.child_bed_price[{i}].{field}",
                                        "error_code": "INVALID_NUMBER_FIELD"
                                    }
        except Exception as e:
            return False, {
                "message": "Unexpected error during validation.",
                "error": str(e),
                "error_code": "VALIDATION_ERROR"
            }
        return True, {"message": "Validation successful"}