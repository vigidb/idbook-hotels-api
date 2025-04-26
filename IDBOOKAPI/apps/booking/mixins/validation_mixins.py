from IDBOOKAPI.utils import (
    get_days_from_string, get_date_from_string)
from apps.booking.utils.db_utils import (
    get_booking_based_tax_rule)



class ValidationMixins:

    def validate_pre_confirm_booking(self):

        child_count = self.request.data.get('child_count', 0)
        child_age_list = self.request.data.get('child_age_list', [])

        if not isinstance(child_age_list, list):
            error_info = {"message": "invalid child age list format",
                          "error_code":"CHILD_AGE_ERROR"}
            return False, error_info


        if child_count != len(child_age_list):
            error_info = {"message": "Mismatch between child count and age list",
                          "error_code":"MISMATCH_CHILD_COUNT_AGE"}
            return False, error_info

        self.confirmed_checkin_time = self.request.data.get('confirmed_checkin_time', None)
        self.confirmed_checkout_time = self.request.data.get('confirmed_checkout_time', None)

        if not self.confirmed_checkin_time or not self.confirmed_checkout_time:
            error_info = {"message": "check in and check out missing",
                          "error_code":"DATE_MISSING"}
            return False, error_info

        property_id = self.request.data.get('property', None)
        if not property_id:
            error_info = {"message": "Property missing",
                          "error_code":"PROPERTY_MISSING"}
            return False, error_info

        # room_list = self.request.data.get('room_list', [])
        # if not room_list or not isinstance(room_list, list):
        #     error_info = {"message": "Missing Room list or invalid list format",
        #                   "error_code":"ROOM_MISSING"}
        #     return False, error_info

        self.no_of_days = get_days_from_string(
            self.confirmed_checkin_time, self.confirmed_checkout_time,
            string_format="%Y-%m-%dT%H:%M%z")

        if self.no_of_days is None:
            error_info = {"message": "Error in date conversion",
                          "error_code":"DATE_ERROR"}
            return False, error_info

        self.checkin_datetime = get_date_from_string(self.confirmed_checkin_time)
        self.checkout_datetime = get_date_from_string(self.confirmed_checkout_time)

        self.tax_rules_dict = get_booking_based_tax_rule('HOTEL')
        if not self.tax_rules_dict:
            error_info = {"message": "Tax Rule Missing",
                          "error_code":"TAX_RULE_MISSING"}
            return False, error_info

        success_info = {"message":"Success"}
        return True, success_info
