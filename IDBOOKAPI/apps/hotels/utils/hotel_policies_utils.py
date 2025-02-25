# hotel policies

def default_hotel_policy_json():

    
    cancellation_policy = {
        "cancellation_policy": {
            "options":["24Hrs-Free", "48Hrs-Free", "72hrs-Free", "Non-Refundable"],
            "setting":{"type": "SINGLE_SELECT", "required":True}},
        "cancellation_msg":{
            "value":"",
            "setting":{"type": "TEXT", "required":False}},
##        "percent_deduct": {
##            "value":0,
##            "setting":{"type": "NUMBER", "required":False}},
        "hour_based_deduction":[
            {
                "hours_before_checkin":{"value": 24, "setting":{"type": "NUMBER", "required":False}},
                "refund_percentage":{"value": 0, "setting":{"type": "NUMBER", "required":False}},
                "cancellation_fee":{"value": 0, "setting":{"type": "NUMBER", "required":False}},       
            },
            {
                "hours_before_checkin":{"value": 48, "setting":{"type": "NUMBER", "required":False}},
                "refund_percentage":{"value": 0, "setting":{"type": "NUMBER", "required":False}},
                "cancellation_fee":{"value": 0, "setting":{"type": "NUMBER", "required":False}},       
            },
            {
                "hours_before_checkin":{"value": 72, "setting":{"type": "NUMBER", "required":False}},
                "refund_percentage":{"value": 0, "setting":{"type": "NUMBER", "required":False}},
                "cancellation_fee":{"value": 0, "setting":{"type": "NUMBER", "required":False}},       
            },
            
        ],  
##        "cancellation_fee": {
##            "value":0,
##            "setting":{"type": "NUMBER", "required":False}},
        "refund_processing_time_days":{
            "value":0,
            "setting":{"type": "NUMBER", "required":False}},
        "cancellation_fee_currency":{
            "options":["INR", "USD"],
            "setting":{"type": "SINGLE_SELECT", "required":False}}
        }

    guest_profile = {
        "is_allowed_unmarried_couples":{
            "options":["No", "Yes"],
            "setting":{"type": "SINGLE_SELECT", "required":False}},
        "is_allowed_guest_below_18_years":{
            "options":["No", "Yes"],
            "setting":{"type": "SINGLE_SELECT", "required":False}},
        "group_with_only_male_guest":{
            "options":["No", "Yes"],
            "setting":{"type": "SINGLE_SELECT", "required":False}}
        }

    acceptable_identity_proof = {
        "identity_proofs":{
            "options":["Passport","Aadhar", "Driving Licence","Govt. ID"],
            "setting":{"type": "SINGLE_SELECT", "required":False}},
        "is_allowed_same_city_id":{
            "options": ["No", "Yes"],
            "setting":{"type": "SINGLE_SELECT", "required":False}}
        }

    property_restrictions = {
        "is_smoking_allowed":{
            "options":["No","Yes"],
            "setting":{"type": "SINGLE_SELECT", "required":False}},
        "is_private_events_allowed":{
            "options":["No","Yes"],
            "setting":{"type": "SINGLE_SELECT", "required":False}},
        "is_outside_visitors_allowed_in_room":{
            "options":["No","Yes"],
            "setting":{"type": "SINGLE_SELECT", "required":False}},
        "is_wheelchair_for_guests":{
            "options":["No","Yes"],
            "setting":{"type": "SINGLE_SELECT", "required":False}}
    }

    pet_policy = {
        "is_pet_allowed":{
            "options":["No","Yes"],
            "setting":{"type": "SINGLE_SELECT", "required":False}},
        "is_pet_living_property": {
            "options":["No","Yes"],
            "setting":{"type": "SINGLE_SELECT", "required":False}}
    }
    
    pet_policy_extra_details = {
        "is_pet_food_available":{
            "options":["No","Yes"],
            "setting":{"type": "SINGLE_SELECT", "required":False}},
        "allowed_pets":{
            "options":["Dogs","Cats", "Dogs & Cats", "All"],
            "setting":{"type": "SINGLE_SELECT", "required":False}},
        "pet_extra_charge":{
            "options":["No","Yes"],
            "setting":{"type": "SINGLE_SELECT", "required":False}}
        }

    check_in_check_out_policies = {
        "is_24hour_checkin":{
            "options":["No","Yes"],
            "setting":{"type": "SINGLE_SELECT", "required":False}}
        }

    extra_bed_policy = {
        "is_extra_bed_adults":{
            "options":["No", "Yes", "Subject to availability"],
            "setting":{"type": "SINGLE_SELECT", "required":False}},        
        "is_extra_bed_kids":{
            "options":["No", "Yes", "Subject to availability"],
            "setting":{"type": "SINGLE_SELECT", "required":False}}
    }
    
    custom_policy = {
        "custom_policy":{
            "value":"",
            "setting":{"type":"TEXT", "required":False}}
    }
    
    meal_rack_prices = {
        "breakfast":{
            "value": 0,
            "setting":{"type":"NUMBER", "required":False}},
        "lunch":{
            "value": 0,
            "setting":{"type":"NUMBER", "required":False}},
        "dinner":{
            "value": 0,
            "setting":{"type":"NUMBER", "required":False}}
    }
    

    
    property_rules = {"guest_profile": guest_profile,
                      "acceptable_identity_proof":acceptable_identity_proof,
                      "property_restrictions": property_restrictions,
                      "pet_policy": pet_policy,
                      "check_in_check_out_policies":check_in_check_out_policies,
                      "extra_bed_policy": extra_bed_policy,
                      "custom_policy":custom_policy,
                      "meal_rack_prices": meal_rack_prices,
                      "extra_details":{"pet_policy_extra_details": pet_policy_extra_details}
                      }

    hotel_policy_json = {"cancellation_policy": cancellation_policy, "property_rules": property_rules}
    
    return hotel_policy_json
    


##def default_hotel_policy_json():
##
##    cancellation_policy = {"cancellation_policy":["24Hrs-Free", "48Hrs-Free",
##                                                  "72hrs-Free", "Non-Refundable"],
##                           "cancellation_msg":"", "percent_deduct": 0}
##
##    guest_profile = {"is_allowed_unmarried_couples":["No", "Yes"],
##                     "is_allowed_guest_below_18_years":["No", "Yes"],
##                     "group_with_only_male_guest":["No", "Yes"]}
##
##    acceptable_identity_proof = {
##        "identity_proofs":["Passport","Aadhar", "Driving Licence","Govt. ID"],
##        "is_allowed_same_city_id":["No", "Yes"]}
##
##    property_restrictions = {"is_smoking_allowed":["No", "Yes"],
##                             "is_private_events_allowed": ["No", "Yes"],
##                             "is_outside_visitors_allowed_in_room": ["No", "Yes"],
##                             "is_wheelchair_for_guests":["No", "Yes"]}
##
##    pet_policy = {"is_pet_allowed":["No", "Yes"], "is_pet_living_property": ["No", "Yes"]}
##    pet_policy_extra_details = {"is_pet_food_available":["No", "Yes"],
##                                "allowed_pets":["Dogs","Cats", "Dogs & Cats", "All"],
##                                "pet_extra_charge": ["No", "Yes"]}
##
##    check_in_check_out_policies = {"is_24hour_checkin":["No", "Yes"]}
##
##    extra_bed_policy = {"is_extra_bed_adults":["No", "Yes", "Subject to availability"],
##                        "is_extra_bed_kids":["No", "Yes", "Subject to availability"]}
##    custom_policy = {"custom_policy": ""}
##    meal_rack_prices = {"breakfast": 0, "lunch": 0, "dinner": 0}
##    
##
##    
##    property_rules = {"guest_profile": guest_profile,
##                      "acceptable_identity_proof":acceptable_identity_proof,
##                      "property_restrictions": property_restrictions,
##                      "pet_policy": pet_policy,
##                      "check_in_check_out_policies":check_in_check_out_policies,
##                      "extra_bed_policy": extra_bed_policy,
##                      "custom_policy":custom_policy,
##                      "meal_rack_prices": meal_rack_prices,
##                      "extra_details":{"pet_policy_extra_details": pet_policy_extra_details}
##                      }
##
##    hotel_policy_json = {"cancellation_policy": cancellation_policy, "property_rules": property_rules}
##    
##    return hotel_policy_json
