# booking utils
from IDBOOKAPI.otp_utils import generate_otp
from django.conf import settings
from IDBOOKAPI.utils import get_current_date

from apps.authentication.utils.db_utils import get_user_by_referralcode
from apps.authentication.utils.authentication_utils import generate_refresh_access_token

from apps.customer.utils.db_utils import (
    add_company_wallet_amount,
    update_wallet_transaction,
    deduct_wallet_balance,
    deduct_company_wallet_balance,
    add_user_wallet_amount,
)
from apps.customer.utils.db_utils import get_wallet_balance, get_company_wallet_balance

from apps.org_resources.db_utils import create_notification
from apps.org_resources.utils.notification_utils import (
    wallet_booking_balance_notification_template,
)

from apps.org_managements.utils import get_active_business
from decimal import Decimal
from IDBOOKAPI.utils import get_unique_id_from_time
from apps.customer.models import Wallet, WalletTransaction
from apps.log_management.models import WalletTransactionLog
from apps.booking.models import BookingPaymentDetail, Booking, Invoice
from datetime import datetime, timedelta
import pytz
from apps.hotels.models import MonthlyPayAtHotelEligibility
from apps.org_resources.models import (
    BasicAdminConfig,
    FeatureSubscription,
    BasicRulesConfig,
)
from IDBOOKAPI.utils import shorten_url
import random, traceback
from django.db.models import Sum
from apps.hotels.utils.db_utils import get_property_commission
from IDBOOKAPI.utils import calculate_tax


def generate_booking_confirmation_code(booking_id, booking_type):
    ##    random_number = generate_otp(no_digits=4)
    ##    cdate = get_current_date()
    ##
    ##    confirmation_code = "IDB{booking_type}CNF{booking_id}-{month}{year}{random_number}".format(
    ##        booking_type=booking_type, booking_id=booking_id,
    ##        random_number=random_number, month=cdate.month, year=cdate.year)

    confirmation_code = "Idbook-CNF"
    confirmation_code = get_unique_id_from_time(confirmation_code)

    return confirmation_code


def generate_booking_reference_code(booking_id, booking_type):
    ##    random_number = generate_otp(no_digits=4)
    ##    cdate = get_current_date()

    ##    reference_code = "IDB{booking_type}BKG{booking_id}-{month}{year}{random_number}".format(
    ##        booking_type=booking_type, booking_id=booking_id,
    ##        random_number=random_number, month=cdate.month, year=cdate.year)

    reference_code = "Idbook-"
    reference_code = get_unique_id_from_time(reference_code)

    return reference_code


def generate_guest_access_token(booking_id, user=None):
    """
    Generate a secure, unique token for users to access their booking.
    This token includes user group information to determine wallet type.

    Args:
        booking_id: The booking ID to generate token for
        user: User instance (optional, used to include group info in token)

    Returns:
        str: A unique secure token that includes group information
    """
    import secrets
    import hashlib
    from django.utils import timezone

    # Determine user group for token
    user_group = None
    if user:
        user_group = user.default_group or ""
        # If no default_group, check groups
        if not user_group:
            user_groups = list(user.groups.values_list("name", flat=True))
            if user_groups:
                user_group = user_groups[0]

    # Generate a cryptographically secure random token
    # Combine booking_id, user_group, timestamp, and random bytes for uniqueness
    timestamp = str(int(timezone.now().timestamp()))
    random_bytes = secrets.token_bytes(32)
    group_suffix = user_group[:10] if user_group else "B2C"  # Limit group name length

    # Create a hash-based token that's URL-safe
    token_data = f"{booking_id}-{group_suffix}-{timestamp}-{random_bytes.hex()}"
    token_hash = hashlib.sha256(token_data.encode()).hexdigest()

    # Use a prefix to identify tokens and include group info
    # Format: {type}_{group}_{hash}
    from apps.authentication.constants import B2C_GROUPS

    token_type = "guest" if user_group in B2C_GROUPS or not user_group else "user"
    guest_token = f"{token_type}_{group_suffix}_{token_hash[:40]}"

    return guest_token


def validate_guest_access_token(token):
    """
    Validate a guest access token and return the associated booking.
    Token format: {type}_{group}_{hash}

    Args:
        token: The guest access token to validate

    Returns:
        Booking object if valid, None otherwise
    """
    from apps.booking.models import Booking

    try:
        if not token or not (token.startswith("guest_") or token.startswith("user_")):
            return None

        booking = Booking.objects.filter(guest_access_token=token).first()
        return booking
    except Exception as e:
        return None


def get_user_group_from_token(token):
    """
    Extract user group information from token.
    Token format: {type}_{group}_{hash}

    Args:
        token: The access token

    Returns:
        str: User group name if found, None otherwise
    """
    try:
        if not token:
            return None

        # Token format: {type}_{group}_{hash}
        parts = token.split("_")
        if len(parts) >= 3:
            # Group is the second part
            return parts[1]
        return None
    except Exception:
        return None


def validate_company_id_for_corporate_user(user, company_id=None, request=None):
    """
    Validate that corporate users have company_id.
    Uses active_group from token if available, otherwise falls back to default_group.

    Args:
        user: User instance
        company_id: Optional company_id to validate
        request: Optional request object to extract active_group from token

    Returns:
        tuple: (is_valid, error_message)
    """
    if not user or not user.is_authenticated:
        # Anonymous users don't need company_id validation
        return True, None

    # Get active group from token or user
    from apps.authentication.utils.token_utils import get_user_active_group
    from apps.authentication.utils.group_utils import is_corporate_user

    active_group = get_user_active_group(user, request)

    # Determine if user is corporate based on active_group
    is_corporate = is_corporate_user(active_group)

    if is_corporate:
        # Corporate users must have company_id
        if not company_id:
            company_id = getattr(user, "company_id", None)

        if not company_id:
            return False, "Company ID is required for corporate users"

    return True, None


def get_booking_by_guest_credentials(
    confirmation_code=None, email=None, guest_token=None
):
    """
    Retrieve a booking using guest credentials (confirmation_code + email or guest_token).
    This is used for guest users who don't have authentication.

    Args:
        confirmation_code: Booking confirmation code
        email: Email address associated with the booking
        guest_token: Guest access token (alternative to confirmation_code + email)

    Returns:
        Booking object if found and valid, None otherwise
    """
    from apps.booking.models import Booking

    try:
        # Option 1: Use guest token (most secure and convenient)
        if guest_token:
            booking = validate_guest_access_token(guest_token)
            if booking:
                return booking

        # Option 2: Use confirmation_code + email (fallback)
        if confirmation_code and email:
            booking = Booking.objects.filter(
                confirmation_code=confirmation_code, user__email__iexact=email
            ).first()

            if booking:
                return booking

        return None
    except Exception as e:
        return None


def generate_htmlcontext_search_booking(booking):
    if booking:
        booking_type = booking.booking_type
        adult_count = booking.adult_count
        child_count = booking.child_count
        name = booking.user.name
        email = booking.user.email
        mobile_number = booking.user.mobile_number

        context = {
            "booking_type": booking_type,
            "name": name,
            "email": email,
            "mobile_number": mobile_number,
        }

        if booking_type == "HOTEL":
            hotel_booking = booking.hotel_booking
            if hotel_booking:
                enquired_property = hotel_booking.enquired_property
                checkin_time = hotel_booking.checkin_time
                checkout_time = hotel_booking.checkout_time

                context["enquired_property"] = enquired_property
                context["checkin_time"] = checkin_time
                context["checkout_time"] = checkout_time
                context["adult_count"] = adult_count
                context["child_count"] = child_count
                # html_content = email_template.render(context)

        elif booking_type == "HOLIDAYPACK":
            holidaypack_booking = booking.holiday_package_booking
            if holidaypack_booking:
                enquired_holiday_package = holidaypack_booking.enquired_holiday_package
                no_days = holidaypack_booking.no_days
                available_start_date = holidaypack_booking.available_start_date

                context["enquired_holiday_package"] = enquired_holiday_package
                context["no_days"] = no_days
                context["available_start_date"] = available_start_date
                context["adult_count"] = adult_count
                context["child_count"] = child_count

        elif booking_type == "VEHICLE":
            vehicle_booking = booking.vehicle_booking

            if vehicle_booking:
                pickup_addr = vehicle_booking.pickup_addr
                dropoff_addr = vehicle_booking.dropoff_addr
                pickup_time = vehicle_booking.pickup_time
                vehicle_type = vehicle_booking.vehicle_type

                context["pickup_addr"] = pickup_addr
                context["dropoff_addr"] = dropoff_addr
                context["pickup_time"] = pickup_time
                context["vehicle_type"] = vehicle_type
                context["adult_count"] = adult_count
                context["child_count"] = child_count

        elif booking_type == "FLIGHT":
            flight_booking = booking.flight_booking

            if flight_booking:
                flight_trip = flight_booking.flight_trip
                flight_class = flight_booking.flight_class
                departure_date = flight_booking.departure_date
                return_date = flight_booking.return_date
                flying_from = flight_booking.flying_from
                flying_to = flight_booking.flying_to

                context["flight_trip"] = flight_trip
                context["flight_class"] = flight_class
                context["departure_date"] = departure_date
                context["return_date"] = return_date
                context["flying_from"] = flying_from
                context["flying_to"] = flying_to
                context["adult_count"] = adult_count
                context["child_count"] = child_count

        return context


def generate_context_confirmed_booking(booking):
    booking_type = booking.booking_type
    adult_count = booking.adult_count
    child_count = booking.child_count
    name = booking.user.name
    email = booking.user.email
    mobile_number = booking.user.mobile_number
    total_payment_made = booking.total_payment_made
    coupon_code = booking.coupon_code
    discount = booking.discount
    pro_discount = booking.pro_member_discount_percent
    pro_discount_value = booking.pro_member_discount_value
    confirmation_code = booking.confirmation_code
    final_amount = booking.final_amount
    total_balance_due = final_amount - total_payment_made
    # subtotal = booking.subtotal
    subtotal = booking.subtotal - (
        booking.total_discount - booking.discount - booking.pro_member_discount_value
    )
    tax = booking.gst_amount

    invoice_id = booking.invoice_id
    
    # Build booking link with guest_token (works for both registered and guest users)
    # guest_token is sufficient and doesn't expire, unlike JWT tokens
    if booking.guest_access_token:
        booking_link = f"{settings.FRONTEND_URL}/bookings/{booking.id}/?guest_token={booking.guest_access_token}"
    else:
        # Fallback: if no guest_token, use booking ID only (frontend may require login)
        booking_link = f"{settings.FRONTEND_URL}/bookings/{booking.id}/"

    invoice_link = ""
    receipt_link = ""
    document_cta_label = ""
    document_cta_url = ""
    invoice_status = ""
    invoice = None

    if invoice_id:
        try:
            # Refresh invoice from database to get latest PDF
            invoice = Invoice.objects.select_related().get(invoice_number=invoice_id)
            invoice_status = invoice.status or ""
            # Get invoice PDF URL if it exists
            if invoice.invoice_pdf:
                try:
                    invoice_link = invoice.invoice_pdf.url
                except (ValueError, AttributeError) as e:
                    print(f"Error getting invoice PDF URL: {e}")
                    invoice_link = ""
            else:
                print(f"Invoice {invoice_id} exists but invoice_pdf is not set")
        except Invoice.DoesNotExist:
            print(f"Invoice {invoice_id} not found in database")
            invoice = None
        except Exception as e:
            print(f"Error retrieving invoice {invoice_id}: {e}")
            invoice = None

    # Determine payment status
    is_paid = float(total_balance_due) <= 0
    if invoice and (invoice.status or "").lower() == "paid":
        is_paid = True

    # Set document link and label based on payment status
    if invoice_link:
        if is_paid:
            document_cta_label = "View Receipt"
            document_cta_url = invoice_link
        else:
            document_cta_label = "View Invoice"
        document_cta_url = invoice_link
        print(
            f"Invoice PDF link set: {document_cta_url}, Label: {document_cta_label}, Status: {invoice_status}, Is Paid: {is_paid}"
        )
    else:
        print(
            f"No invoice link available for booking {booking.id}, invoice_id: {invoice_id}"
        )

    # invoice_link = f"{settings.INV_FE_URL}/invoice/{invoice_id}"
    occupancy = "{adult_count} Adults".format(adult_count=adult_count)
    if child_count:
        occupancy = occupancy + "{child_count} Child".format(child_count=child_count)

    context = {
        "booking_type": booking_type,
        "name": name,
        "email": email,
        "mobile_number": mobile_number,
        "total_payment_made": float(total_payment_made),
        "coupon_code": coupon_code,
        "discount": float(discount),
        "pro_discount": pro_discount,
        "pro_discount_value": float(pro_discount_value),
        "confirmation_code": confirmation_code,
        "occupancy": occupancy,
        "total_balance_due": float(total_balance_due),
        "total_booking_amount": float(final_amount),
        "subtotal": float(subtotal),
        "tax": float(tax),
        "booking_link": booking_link,
        "invoice_link": invoice_link,
        "receipt_link": receipt_link,
        "document_cta_label": document_cta_label,
        "document_cta_url": document_cta_url,
        "invoice_status": invoice_status,
    }

    if booking_type == "HOTEL":
        property_name, property_address = "", ""
        property_email, property_phone_no = "", ""
        room_type = ""
        area_name, city_name, state, country = "", "", "", ""

        confirmed_checkin_time, confirmed_checkout_time = None, None
        room_subtotal, service_tax = None, None

        hotel_booking = booking.hotel_booking
        if hotel_booking:
            confirmed_checkin_time = hotel_booking.confirmed_checkin_time
            confirmed_checkout_time = hotel_booking.confirmed_checkout_time

            confirmed_property = hotel_booking.confirmed_property
            if confirmed_property:
                property_name = confirmed_property.name
                property_address = confirmed_property.address
                property_email = confirmed_property.email
                property_phone_no = confirmed_property.phone_no
                area_name = confirmed_property.area_name
                city_name = confirmed_property.city_name
                state = confirmed_property.state
                country = confirmed_property.country

            confirmed_rooms = hotel_booking.confirmed_room_details
            if not confirmed_rooms:
                context["confirmed_rooms"] = []
            else:
                context["confirmed_rooms"] = confirmed_rooms

        ##                room_type = confirmed_room.room_type
        ##                price_for_24_hours = confirmed_room.price_for_24_hours

        context["confirmed_checkin_time"] = confirmed_checkin_time
        context["confirmed_checkout_time"] = confirmed_checkout_time

        context["property_name"] = property_name

        {
            "pincode": "",
            "coordinates": {"lat": "", "lng": ""},
            "location_url": "",
            "building_or_hse_no": "",
        }
        if property_address:
            pincode = property_address.get("pincode", "")
            building_no = property_address.get("building_or_hse_no", "")
            final_address = f"{building_no}, {area_name}, {city_name}, {state} - {pincode}, {country}"
        else:
            final_address = f" {area_name}, {city_name}, {state}, {country}"

        context["property_address"] = final_address
        context["property_email"] = property_email
        context["property_phone_no"] = property_phone_no

        # context['room_type'] = room_type

    elif booking_type == "HOLIDAYPACK":
        holidaypack_booking = booking.holiday_package_booking
        trip_id, trip_name = "", ""
        tour_duration, date_of_journey = "", ""

        daily_plans = []

        if holidaypack_booking:
            confirmed_pack = holidaypack_booking.confirmed_holiday_package
            if confirmed_pack:
                trip_id = confirmed_pack.trip_id
                trip_name = confirmed_pack.trip_name
                tour_duration = confirmed_pack.tour_duration
                date_of_journey = confirmed_pack.date_of_journey
                daily_plans = confirmed_pack.tour_daily_plan.all()
                print("daily plan::", daily_plans)

        ##               for dplan in daily_plans:
        ##                   title = dplan.title
        ##                   plan_date = dplan.plan_date
        ##                   stay = dplan.stay
        ##                   check_in = dplan.check_in
        ##                   check_out = dplan.check_out
        ##                   detailed_plan

        context["trip_id"] = trip_id
        context["trip_name"] = trip_name
        context["tour_duration"] = tour_duration
        context["date_of_journey"] = date_of_journey
        context["daily_plans"] = daily_plans

    elif booking_type == "VEHICLE":
        pickup_addr, dropoff_addr = "", ""
        pickup_time, vehicle_type = "", ""
        vehicle_no, driver_name = "", ""
        contact_email, contact_number = "", ""
        vehicle_subtotal, service_tax = "", ""

        vehicle_booking = booking.vehicle_booking
        if vehicle_booking:
            pickup_addr = vehicle_booking.pickup_addr
            dropoff_addr = vehicle_booking.dropoff_addr
            pickup_time = vehicle_booking.pickup_time

            confirmed_vehicle = vehicle_booking.confirmed_vehicle
            if confirmed_vehicle:
                vehicle_type = confirmed_vehicle.vehicle_type
                vehicle_no = confirmed_vehicle.vehicle_no
                driver_name = confirmed_vehicle.driver_name
                contact_email = confirmed_vehicle.contact_email
                contact_number = confirmed_vehicle.contact_number

        context["pickup_addr"] = pickup_addr
        context["dropoff_addr"] = dropoff_addr
        context["pickup_time"] = pickup_time
        context["vehicle_type"] = vehicle_type
        context["vehicle_no"] = vehicle_no
        context["driver_name"] = driver_name
        context["contact_email"] = contact_email
        context["contact_number"] = contact_number

    elif booking_type == "FLIGHT":
        flight_trip, flight_class = "", ""
        departure_date, return_date = "", ""
        flying_from, flying_to = "", ""
        flight_subtotal, service_tax = "", ""

        flight_booking = booking.flight_booking
        if flight_booking:
            flight_trip = flight_booking.flight_trip
            flight_class = flight_booking.flight_class
            departure_date = flight_booking.departure_date
            return_date = flight_booking.return_date
            flying_from = flight_booking.flying_from
            flying_to = flight_booking.flying_to

        context["flight_trip"] = flight_trip
        context["flight_class"] = flight_class
        context["departure_date"] = departure_date
        context["return_date"] = return_date
        context["flying_from"] = flying_from
        context["flying_to"] = flying_to

    return context


def generate_context_cancelled_booking(booking):
    booking_type = booking.booking_type
    name = booking.user.name
    email = booking.user.email
    mobile_number = booking.user.mobile_number
    total_payment_made = booking.total_payment_made

    booking_link = f"{settings.FRONTEND_URL}/bookings/{booking.id}"

    context = {
        "booking_type": booking_type,
        "name": name,
        "email": email,
        "mobile_number": mobile_number,
        "total_payment_made": float(total_payment_made),
        "reference_number": booking.reference_code,
        "booking_link": booking_link,
    }

    if booking_type == "HOTEL":
        property_name, room_type = "", ""
        confirmed_checkin_time, confirmed_checkout_time = None, None

        hotel_booking = booking.hotel_booking
        if hotel_booking:
            confirmed_checkin_time = hotel_booking.confirmed_checkin_time
            confirmed_checkout_time = hotel_booking.confirmed_checkout_time

            confirmed_property = hotel_booking.confirmed_property
            if confirmed_property:
                property_name = confirmed_property.name

            confirmed_room = hotel_booking.room
            if confirmed_room:
                room_type = confirmed_room.room_type

        context["confirmed_checkin_time"] = confirmed_checkin_time
        context["confirmed_checkout_time"] = confirmed_checkout_time
        context["property_name"] = property_name
        context["room_type"] = room_type

    elif booking_type == "HOLIDAYPACK":
        holidaypack_booking = booking.holiday_package_booking
        trip_id, trip_name = "", ""
        tour_duration, date_of_journey = "", ""

        if holidaypack_booking:
            confirmed_pack = holidaypack_booking.confirmed_holiday_package
            if confirmed_pack:
                trip_id = confirmed_pack.trip_id
                trip_name = confirmed_pack.trip_name
                tour_duration = confirmed_pack.tour_duration
                date_of_journey = confirmed_pack.date_of_journey

        context["trip_id"] = trip_id
        context["trip_name"] = trip_name
        context["tour_duration"] = tour_duration
        context["date_of_journey"] = date_of_journey

    elif booking_type == "VEHICLE":
        pickup_addr, dropoff_addr = "", ""
        pickup_time, vehicle_type = "", ""
        vehicle_no = ""

        vehicle_booking = booking.vehicle_booking
        if vehicle_booking:
            pickup_addr = vehicle_booking.pickup_addr
            dropoff_addr = vehicle_booking.dropoff_addr
            pickup_time = vehicle_booking.pickup_time

            confirmed_vehicle = vehicle_booking.confirmed_vehicle
            if confirmed_vehicle:
                vehicle_type = confirmed_vehicle.vehicle_type
                vehicle_no = confirmed_vehicle.vehicle_no

        context["pickup_addr"] = pickup_addr
        context["dropoff_addr"] = dropoff_addr
        context["pickup_time"] = pickup_time
        context["vehicle_type"] = vehicle_type
        context["vehicle_no"] = vehicle_no

    elif booking_type == "FLIGHT":
        flight_trip, flight_class = "", ""
        departure_date, return_date = "", ""
        flying_from, flying_to = "", ""

        flight_booking = booking.flight_booking
        if flight_booking:
            flight_trip = flight_booking.flight_trip
            flight_class = flight_booking.flight_class
            departure_date = flight_booking.departure_date
            return_date = flight_booking.return_date
            flying_from = flight_booking.flying_from
            flying_to = flight_booking.flying_to

        context["flight_trip"] = flight_trip
        context["flight_class"] = flight_class
        context["departure_date"] = departure_date
        context["return_date"] = return_date
        context["flying_from"] = flying_from
        context["flying_to"] = flying_to

    return context


def generate_context_completed_booking(booking):
    name = booking.user.name
    email = booking.user.email
    mobile_number = booking.user.mobile_number

    booking_link = f"{settings.FRONTEND_URL}/bookings/{booking.id}"
    review_link = "https://www.ambitionbox.com/overview/idbook-hotels-overview"
    review_link = shorten_url(review_link)
    context = {
        "name": name,
        "email": email,
        "mobile_number": mobile_number,
        "reference_number": booking.reference_code,
        "booking_link": booking_link,
        "review_link": review_link,
    }

    property_name, room_type = "", ""
    confirmed_checkin_time, confirmed_checkout_time = None, None

    hotel_booking = booking.hotel_booking
    if hotel_booking:
        confirmed_checkin_time = hotel_booking.confirmed_checkin_time
        confirmed_checkout_time = hotel_booking.confirmed_checkout_time

        confirmed_property = hotel_booking.confirmed_property
        if confirmed_property:
            property_name = confirmed_property.name

        confirmed_room = hotel_booking.room
        if confirmed_room:
            room_type = confirmed_room.room_type

    context["confirmed_checkin_time"] = confirmed_checkin_time
    context["confirmed_checkout_time"] = confirmed_checkout_time
    context["property_name"] = property_name
    context["room_type"] = room_type

    return context


def calculate_total_amount(booking):
    total_booking_amount = 0
    booking_type = booking.booking_type
    coupon = booking.coupon
    coupon_discount, gst_amount = 0, 0

    try:
        total_booking_amount = booking.subtotal

        # coupon deduction
        if coupon and coupon.discount:
            if coupon.discount_type == "AMOUNT":
                total_booking_amount = total_booking_amount - coupon.discount
                coupon_discount = coupon.discount
            elif coupon.discount_type == "PERCENT":
                coupon_discount = (coupon.discount * total_booking_amount) / 100
                total_booking_amount = total_booking_amount - coupon_discount

        #  gst calculation
        gst_percentage = booking.gst_percentage
        if gst_percentage:
            gst_amount = (gst_percentage * total_booking_amount) / 100

        total_booking_amount = total_booking_amount + gst_amount
    except Exception as e:
        print("Error in booking total amount calculation", e)

    return total_booking_amount, gst_amount, coupon_discount


def set_firstbooking_reward(referred_code, booked_user_id=None):
    user = get_user_by_referralcode(referred_code)
    if user:
        # reward_amount = 250
        reward_config = BasicAdminConfig.objects.get(code="referral_bonus")
        reward_amount = float(reward_config.value)
        ##        company_id = user.company_id
        ##        if company_id:
        ##            status = add_company_wallet_amount(company_id, reward_amount)
        ##        else:
        ##            status = add_user_wallet_amount(user.id, reward_amount)

        company_id = None
        status = add_user_wallet_amount(user.id, reward_amount)

        if status:
            transaction_details = f"Amount credited based on referral code"
            other_details = {"referral": {"user": booked_user_id}}
            wtransact_dict = {
                "user_id": user.id,
                "amount": reward_amount,
                "transaction_type": "Credit",
                "transaction_details": transaction_details,
                "company_id": company_id,
                "transaction_for": "referral_booking",
                "is_transaction_success": True,
                "other_details": other_details,
            }
            update_wallet_transaction(wtransact_dict)
        else:
            transaction_details = f"Amount credited based on referral code (failed)"
            other_details = {"referral": {"user": booked_user_id}}
            wtransact_dict = {
                "user_id": user.id,
                "amount": reward_amount,
                "transaction_type": "Credit",
                "transaction_details": transaction_details,
                "company_id": company_id,
                "transaction_for": "referral_booking",
                "is_transaction_success": False,
                "other_details": other_details,
            }
            update_wallet_transaction(wtransact_dict)


def deduct_booking_amount(booking, company_id=None, request=None):
    """
    Deduct booking amount from appropriate wallet based on user's active group.

    Business Rules:
    - Corporate users (CORP-ADMIN, CORP-EMP, CORPORATE-GRP): Must use company wallet (company_id required)
    - B2C users (B2C-GRP, B2C-GUEST): Use personal wallet
    - Other users: Use personal wallet

    Args:
        booking: Booking instance
        company_id: Optional company_id (will be determined from user if not provided for corporate users)
        request: Optional request object to extract active_group from token

    Returns:
        bool: True if deduction successful, False otherwise
    """
    deduct_amount = booking.final_amount  # - float(booking.total_payment_made)

    if not booking.user:
        # Guest booking without user - should not happen for wallet payment
        return False

    # Determine user's active group (from token if available, otherwise from user)
    user = booking.user
    from apps.authentication.utils.token_utils import get_user_active_group
    from apps.authentication.utils.group_utils import is_corporate_user

    active_group = get_user_active_group(user, request)

    # Check if user is a corporate user based on active_group
    is_corporate = is_corporate_user(active_group)

    # For corporate users, company_id is required
    if is_corporate:
        # Use provided company_id or get from user
        if not company_id:
            company_id = getattr(user, "company_id", None)

        if not company_id:
            # Corporate user must have company_id
            print(
                f"Error: Corporate user {user.id} does not have company_id for booking {booking.id}"
            )
            return False

        # Deduct from company wallet
        status = deduct_company_wallet_balance(company_id, deduct_amount)

        if status:
            transaction_details = f"Amount debited for {booking.booking_type} \
    booking ({booking.confirmation_code})"
            wtransact_dict = {
                "user": booking.user,
                "amount": deduct_amount,
                "transaction_type": "Debit",
                "transaction_details": transaction_details,
                "company_id": company_id,
            }
            update_wallet_transaction(wtransact_dict)

        return status
    else:
        # B2C or other users - deduct from personal wallet
        # Ensure company_id is None for personal wallet
        status = deduct_wallet_balance(booking.user.id, deduct_amount, booking)
        return status


def calculate_room_booking_amount(amount, no_of_days, no_of_rooms):
    total_amount = (amount * no_of_rooms) * no_of_days
    return total_amount


def calculate_xbed_amount(amount, no_of_days):
    total_amount = amount * no_of_days
    return total_amount


def get_tax_rate(amount, tax_rules_dict):
    tax_rate_in_percent = None
    for tax_rule in tax_rules_dict:
        symbol = tax_rule.get("math_compare_symbol", "")
        amount1 = tax_rule.get("amount1", None)
        tax_rate_in_percent = tax_rule.get("tax_rate_in_percent", None)

        if not amount1 or not symbol or not tax_rate_in_percent:
            break

        if symbol == "EQUALS" and amount == amount1:
            return tax_rate_in_percent
        elif symbol == "LESS-THAN" and amount < amount1:
            return tax_rate_in_percent
        elif symbol == "LESS-THAN-OR-EQUALS" and amount <= amount1:
            return tax_rate_in_percent
        elif symbol == "GREATER-THAN" and amount > amount1:
            return tax_rate_in_percent
        elif symbol == "GREATER-THAN-OR-EQUALS" and amount >= amount1:
            return tax_rate_in_percent
        elif symbol == "BETWEEN":
            amount2 = tax_rule.get("amount2", None)
            if not amount2:
                break
            if amount1 <= amount <= amount2:
                return tax_rate_in_percent

    return tax_rate_in_percent


def check_wallet_balance_for_booking(booking, user, company_id=None):
    try:
        if company_id:
            balance = get_company_wallet_balance(company_id)
        else:
            balance = get_wallet_balance(user.id)

        if balance < booking.final_amount:

            # send wallet balance notification
            send_by = None
            bus_details = get_active_business()
            if bus_details:
                send_by = bus_details.user
            from apps.authentication.constants import UserGroups

            group_name = (
                UserGroups.CORPORATE_GRP if booking.company_id else UserGroups.B2C_GRP
            )
            notification_dict = {
                "user": user,
                "send_by": send_by,
                "notification_type": "GENERAL",
                "title": "",
                "description": "",
                "redirect_url": "",
                "group_name": group_name,
                "image_link": "",
            }
            notification_dict = wallet_booking_balance_notification_template(
                booking, balance, notification_dict
            )
            create_notification(notification_dict)

            return False, balance
        else:
            return True, balance
    except Exception as e:
        print(e)


def calculate_refund_amount(total_payment_made, applicable_policy):

    if not isinstance(total_payment_made, Decimal):
        total_payment_made = Decimal(str(total_payment_made))

    # Get refund percentage and convert to Decimal
    refund_percentage = applicable_policy.get("refund_percentage", 0)
    refund_percentage_decimal = (
        Decimal(str(refund_percentage))
        if not isinstance(refund_percentage, Decimal)
        else refund_percentage
    )

    # Get cancellation fee and convert to Decimal
    cancellation_fee_value = applicable_policy.get("cancellation_fee", 0)
    cancellation_fee = (
        Decimal(str(cancellation_fee_value))
        if not isinstance(cancellation_fee_value, Decimal)
        else cancellation_fee_value
    )

    if refund_percentage_decimal == 0 and cancellation_fee == 0:
        # Full charge case (no refund)
        refund_amount = Decimal("0")
        amount_after_cancel_fee = Decimal("0")
    else:
        # Calculate refund based on percentage and fee
        amount_after_cancel_fee = total_payment_made - cancellation_fee
        refund_amount = amount_after_cancel_fee * (
            refund_percentage_decimal / Decimal("100")
        )

    refund_details = {
        "total_amount": float(total_payment_made),
        "refund_percentage": float(refund_percentage_decimal),
        "cancellation_fee": float(cancellation_fee),
        "amount_after_cancel_fee": float(
            amount_after_cancel_fee
            if "amount_after_cancel_fee" in locals()
            else Decimal("0")
        ),
        "refund_amount": float(refund_amount),
    }
    return refund_amount, refund_details


def refund_wallet_payment(instance, refund_amount, cancellation_details):

    refund_log = {}
    refund_log["booking_id"] = instance.id

    try:
        # Generate unique merchant transaction ID for refund
        append_id = "WLRF{}".format(instance.user.id)
        merchant_refund_id = get_unique_id_from_time(append_id)
        refund_log["merchant_refund_id"] = merchant_refund_id

        # Credit amount back to user's wallet
        wallet = Wallet.objects.filter(
            user__id=instance.user.id, company__isnull=True
        ).first()
        wallet.balance = wallet.balance + Decimal(refund_amount)
        wallet.save()

        # Create wallet transaction record
        transaction_details = f"Amount credited for canceled {instance.booking_type} booking ({instance.confirmation_code})"
        WalletTransaction.objects.create(
            user=instance.user,
            amount=refund_amount,
            transaction_type="Credit",
            transaction_for="booking_refund",
            transaction_id=merchant_refund_id,
            transaction_details=transaction_details,
            payment_type="WALLET",
            payment_medium="Idbook",
            is_transaction_success=True,
            code="REFUND_SUCCESS",
        )
        BookingPaymentDetail.objects.create(
            booking=instance,
            merchant_transaction_id=merchant_refund_id,
            transaction_id="",
            code="REFUND_SUCCESS",
            message="Refund processed successfully",
            payment_type="WALLET",
            payment_medium="Idbook",
            amount=refund_amount,
            is_transaction_success=True,
            transaction_for="booking_refund",
            transaction_details={
                "refund_amount": float(refund_amount),
                "refund_type": "wallet_credit",
                "transaction_details": transaction_details,
            },
        )

        # Log the refund transaction
        log_data = {
            "user": instance.user,
            "merchant_transaction_id": merchant_refund_id,
            "request": {
                "booking_id": instance.id,
                "refund_amount": float(refund_amount),
                "transaction_type": "Credit",
                "payment_type": "WALLET",
            },
            "response": {
                "status": "success",
                "code": "REFUND_SUCCESS",
                "message": "Refund processed successfully",
            },
        }
        WalletTransactionLog.objects.create(**log_data)

        # Update cancellation details only for HOTEL bookings (field exists there)
        refund_status = "refund_completed"
        cancellation_details["refund_status"] = refund_status
        if getattr(instance, "booking_type", "") == "HOTEL" and getattr(
            instance, "hotel_booking", None
        ):
            instance.hotel_booking.cancellation_details = cancellation_details
            instance.hotel_booking.save(update_fields=["cancellation_details"])

        # Add to refund log for return
        refund_log["status"] = "completed"
        refund_log["transaction_id"] = merchant_refund_id
        refund_log["refund_amount"] = float(refund_amount)

        return (True, refund_status, refund_log)

    except Exception as e:
        print("Wallet refund error:", e)
        # Update cancellation details for failure (only for HOTEL bookings)
        refund_status = "refund_failed"
        cancellation_details["refund_status"] = refund_status
        cancellation_details["refund_error"] = str(e)
        if getattr(instance, "booking_type", "") == "HOTEL" and getattr(
            instance, "hotel_booking", None
        ):
            instance.hotel_booking.cancellation_details = cancellation_details
            instance.hotel_booking.save(update_fields=["cancellation_details"])

        refund_log["status"] = "failed"
        refund_log["error_message"] = str(e)

        return (False, refund_status, refund_log)


def update_no_show_status(user_id):
    """
    Updates 'pending' hotel bookings for a specific user with a confirmed checkout time of yesterday to 'no_show'.
    """
    india_tz = pytz.timezone("Asia/Kolkata")
    curr_time = datetime.now(india_tz)
    print("curr_time", curr_time)
    # yesterday = curr_time.replace(hour=23, minute=59, second=59) - timedelta(days=1)
    # print("yesterday", yesterday)

    updated_count = Booking.objects.filter(
        booking_type="HOTEL",
        status="pending",
        hotel_booking__confirmed_checkout_time__lt=curr_time,
        user_id=user_id,
    ).update(status="no_show")

    print(f"Updated {updated_count} bookings to no-show status for user ID {user_id}")


def check_pay_at_hotel_eligibility(user, amount):
    """
    Check if user is eligible for pay-at-hotel based on their monthly limit
    """
    # Get current month
    current_month = datetime.now().strftime("%B")

    # Check if user has a monthly pay-at-hotel eligibility record
    eligibility = MonthlyPayAtHotelEligibility.objects.filter(
        user=user, month=current_month
    ).first()

    if not eligibility:
        return False, "No pay-at-hotel eligibility found for this month"

    if not eligibility.is_eligible:
        return False, "You are not eligible for pay-at-hotel this month"

    remaining_limit = eligibility.eligible_limit - eligibility.spent_amount
    if float(amount) > float(remaining_limit):
        return (
            False,
            f"Booking amount exceeds your available limit of {remaining_limit}",
        )

    return True, "Eligible for pay-at-hotel"


def handle_pay_at_hotel_payment_cancellation(
    instance, cancellation_details, applicable_policy
):
    try:
        # Checking for Non-Refundable policy
        cancellation_policy = instance.hotel_booking.cancel_policy or {}
        policies = cancellation_policy.get("cancellation_policy", [])

        payment_details = BookingPaymentDetail.objects.filter(booking=instance).first()

        cancellation_fee = applicable_policy.get("cancellation_fee", 0)

        if "Non-Refundable" in policies:
            if payment_details:
                cancellation_fee = payment_details.amount
            print(
                f"Non-Refundable policy applied. Fee set to full amount: {cancellation_fee}"
            )

        if cancellation_fee <= 0:
            # No cancellation fee to charge
            return (
                True,
                "booking_cancelled_no_fee",
                {
                    "fee_charged": 0,
                    "message": "Booking cancelled with no cancellation fee",
                },
            )

        # Try to get the user's wallet
        wallet = Wallet.objects.filter(
            user__id=instance.user.id, company__isnull=True
        ).first()

        if not wallet:
            # Create wallet if it doesn't exist
            wallet = Wallet.objects.create(user=instance.user, balance=0, company=None)
        # Generate a unique transaction ID for the fee
        append_id = f"CNCL{instance.user.id}"
        merchant_transaction_id = get_unique_id_from_time(append_id)

        # Update wallet balance - can go negative
        previous_balance = wallet.balance
        wallet.balance = wallet.balance - Decimal(cancellation_fee)
        wallet.save()

        # Create wallet transaction record for the fee
        transaction_details = f"Cancellation fee charged for {instance.booking_type} booking ({instance.confirmation_code})"
        wallet_transaction = WalletTransaction.objects.create(
            user=instance.user,
            amount=cancellation_fee,
            transaction_type="Debit",
            transaction_for="others",
            transaction_id=merchant_transaction_id,
            transaction_details=transaction_details,
            payment_type="WALLET",
            payment_medium="Idbook",
            is_transaction_success=True,
            code="CANCEL_FEE_CHARGED",
        )

        # Create a record in booking payment details
        booking_payment = BookingPaymentDetail.objects.create(
            booking=instance,
            merchant_transaction_id=merchant_transaction_id,
            transaction_id="",
            code="CANCEL_FEE_CHARGED",
            message="Cancellation fee charged successfully",
            payment_type="WALLET",
            payment_medium="Idbook",
            amount=cancellation_fee,
            is_transaction_success=True,
            transaction_for="others",
            transaction_details={
                "fee_amount": float(cancellation_fee),
                "previous_wallet_balance": float(previous_balance),
                "new_wallet_balance": float(wallet.balance),
                "transaction_details": transaction_details,
            },
        )

        # Log the fee transaction
        log_data = {
            "user": instance.user,
            "merchant_transaction_id": merchant_transaction_id,
            "request": {
                "booking_id": instance.id,
                "fee_amount": float(cancellation_fee),
                "transaction_type": "Debit",
                "payment_type": "WALLET",
            },
            "response": {
                "status": "success",
                "code": "CANCEL_FEE_CHARGED",
                "message": "Cancellation fee charged successfully",
            },
        }
        wallet_log = WalletTransactionLog.objects.create(**log_data)

        # Update cancellation details
        fee_status = "fee_charged"
        cancellation_details["fee_status"] = fee_status
        cancellation_details["fee_amount"] = float(cancellation_fee)
        cancellation_details["wallet_balance_after_fee"] = float(wallet.balance)
        instance.hotel_booking.cancellation_details = cancellation_details
        instance.hotel_booking.save()

        return (
            True,
            fee_status,
            {
                "merchant_transaction_id": merchant_transaction_id,
                "fee_amount": float(cancellation_fee),
                "wallet_previous_balance": float(previous_balance),
                "wallet_current_balance": float(wallet.balance),
            },
        )

    except Exception as e:
        print("Cancellation fee charge error:", e)
        fee_status = "fee_charge_failed"
        cancellation_details["fee_status"] = fee_status
        cancellation_details["fee_error"] = str(e)
        instance.hotel_booking.cancellation_details = cancellation_details
        instance.hotel_booking.save()

        return False, fee_status, {"error_message": str(e)}


def get_gst_type(bus_details, company_details=None, customer_details=None):
    business_state = (
        bus_details.state.lower() if bus_details and bus_details.state else None
    )

    if company_details and company_details.state:
        return (
            "CGST/SGST" if business_state == company_details.state.lower() else "IGST"
        )
    elif customer_details and customer_details.state:
        return (
            "CGST/SGST" if business_state == customer_details.state.lower() else "IGST"
        )
    return ""


def process_subscription_cashback(user, booking_id):
    """
    Process cashback rewards based on user's subscription level and booking count
    """

    # Check if user has an active subscription
    user_subscription = user.user_subscription.filter(active=True).last()
    if not user_subscription or not user_subscription.idb_sub:
        return False

    # Get subscription features
    subscription = user_subscription.idb_sub

    # Get all features for the subscription
    cashback_features = FeatureSubscription.objects.filter(
        subscription=subscription,
        feature_key__in=["cashback_3", "cashback_5"],
        is_active=True,
    )

    if not cashback_features:
        return False

    # Count confirmed bookings for this user - exclude direct hotel payments
    confirmed_bookings_count = (
        Booking.objects.filter(
            user_id=user.id,
            status="confirmed",
        )
        .exclude(
            booking_payment__payment_type="DIRECT",
            booking_payment__payment_medium="Hotel",
        )
        .count()
    )
    print("confirmed_bookings_count----", confirmed_bookings_count)
    cashback_applied = False

    # Check each cashback feature
    for feature in cashback_features:
        if feature.feature_key == "cashback_3" and confirmed_bookings_count % 3 == 0:
            # Apply cashback for every 3rd booking
            cashback_amount = random.randint(1, 30)
            transaction_details = f"Credited {cashback_amount} as cashback on your {confirmed_bookings_count}th booking"
            cashback_applied = apply_cashback(
                user, booking_id, cashback_amount, transaction_details
            )
            # Create notification for cashback
            if cashback_applied:
                create_cashback_notification(
                    user, booking_id, cashback_amount, confirmed_bookings_count
                )
            break

        elif feature.feature_key == "cashback_5" and confirmed_bookings_count % 5 == 0:
            # Apply cashback for every 5th booking
            cashback_amount = random.randint(1, 30)
            transaction_details = f"Credited {cashback_amount} as cashback on your {confirmed_bookings_count}th booking"
            cashback_applied = apply_cashback(
                user, booking_id, cashback_amount, transaction_details
            )
            # Create notification for cashback
            if cashback_applied:
                create_cashback_notification(
                    user, booking_id, cashback_amount, confirmed_bookings_count
                )
            break

    return cashback_applied


def apply_cashback(user, booking_id, cashback_amount, transaction_details):
    """
    Apply cashback to user's wallet and create transaction record
    """
    booking = Booking.objects.get(id=booking_id)
    company_id = booking.company_id

    # Determine which wallet to credit based on company_id
    if company_id:
        status = add_company_wallet_amount(company_id, cashback_amount)
    else:
        status = add_user_wallet_amount(user.id, cashback_amount)

    if not status:
        return False

    # Create wallet transaction record
    other_details = {"booking_id": booking_id, "cashback_reward": True}

    wallet_transact_dict = {
        "user_id": user.id,
        "amount": cashback_amount,
        "transaction_type": "Credit",
        "transaction_details": transaction_details,
        "company_id": company_id,
        "transaction_for": "booking_cashback",
        "is_transaction_success": status,
        "other_details": other_details,
    }

    update_wallet_transaction(wallet_transact_dict)
    return True


def create_cashback_notification(user, booking_id, cashback_amount, booking_count):
    """
    Create and save notification for cashback rewards
    """
    try:
        booking = Booking.objects.get(id=booking_id)

        # Get sender (business user)
        send_by = None
        bus_details = get_active_business()
        if bus_details:
            send_by = bus_details.user

        # Determine group name based on company_id
        group_name = "CORPORATE-GRP" if booking.company_id else "B2C-GRP"

        # Prepare notification dictionary
        notification_dict = {
            "user": user,
            "send_by": send_by,
            "notification_type": "GENERAL",
            "title": "",
            "description": "",
            "redirect_url": "",
            "image_link": "",
            "group_name": group_name,
        }

        # Apply notification template
        notification_dict = booking_cashback_notification_template(
            booking_id, cashback_amount, booking_count, notification_dict
        )

        # Create the notification
        create_notification(notification_dict)
        print(f"Cashback notification created for user {user.id}")

    except Exception as e:
        print(f"Error creating cashback notification: {e}")


def booking_cashback_notification_template(
    booking_id, cashback_amount, booking_count, notification_dict
):
    """
    Create notification template for cashback rewards
    """
    try:
        title = "Cashback Reward Credited"
        description = f"Congratulations! You've received ₹{cashback_amount} cashback on your {booking_count}th booking."
        redirect_url = ""

        notification_dict["title"] = title
        notification_dict["description"] = description
        notification_dict["redirect_url"] = redirect_url

    except Exception as e:
        print("Cashback Notification Error", e)
    return notification_dict


def calculate_subscription_discount(user, current_booking_subtotal):
    discount_percent = 0
    discount_value = 0

    # Handle AnonymousUser
    if not user or not user.is_authenticated:
        return discount_percent, discount_value

    # Check if user has active subscription
    user_subscription = user.user_subscription.filter(active=True).last()

    if user_subscription and user_subscription.idb_sub:
        subscription_level = user_subscription.idb_sub.level

        # Get user's total payment made from confirmed and completed bookings
        total_payment_made = (
            Booking.objects.filter(
                user=user,
                status__in=["confirmed", "completed"],
                booking_payment__is_transaction_success=True,
            ).aggregate(total=Sum("total_payment_made"))["total"]
            or 0
        )
        print("total_payment_made", total_payment_made)
        # If user has no previous bookings, use current booking subtotal
        if total_payment_made == 0:
            amount_to_check = current_booking_subtotal
        else:
            amount_to_check = total_payment_made

        # Find applicable discount rule based on subscription level
        discount_rule = None

        # Find the rule that matches the amount range for PRO_DISCOUNT
        try:
            discount_rule = BasicRulesConfig.objects.filter(
                rules_for="PRO_DISCOUNT",
                start_limit__lte=amount_to_check,
                end_limit__gte=amount_to_check,
            ).first()

            if discount_rule:
                discount_percent = discount_rule.value
                print("discount_percent", discount_percent)
                discount_value = (current_booking_subtotal * discount_percent) / 100

        except BasicRulesConfig.DoesNotExist:
            # No applicable rule found, no discount
            pass

    return discount_percent, discount_value


def hotelier_commission_calculation(
    commission_details, final_amount, final_tax_amount, pay_at_hotel
):

    if commission_details:
        hotelier_amount = (float(final_amount) - float(final_tax_amount)) - float(
            commission_details.get("com_amnt_withtax", 0)
        )
        hotelier_amount_with_tax = float(final_amount) - float(
            commission_details.get("com_amnt_withtax", 0)
        )
        commission_details["hotelier_amount"] = hotelier_amount
        commission_details["hotelier_amount_with_tax"] = hotelier_amount_with_tax
        if pay_at_hotel:
            commission_details["final_payout"] = -float(
                commission_details.get("com_amnt_withtax", 0)
            )
        else:
            commission_details["final_payout"] = hotelier_amount_with_tax

    return commission_details


def commission_calculation(
    property_id,
    subtotal,
    total_discount,
    final_amount,
    final_tax_amount,
    pay_at_hotel=False,
):
    com_amnt = 0
    tax_amount, tax_in_percent = 0, 0
    commission_details = None
    try:
        prop_comm = get_property_commission(property_id)
        if prop_comm:
            comm_type = prop_comm.commission_type
            commission = prop_comm.commission
            discounted_subtotal = Decimal(subtotal) - Decimal(total_discount)

            if comm_type == "PERCENT":
                com_amnt = (commission * discounted_subtotal) / Decimal(100)
                # com_amnt = (commission * subtotal) / 100
            elif comm_type == "AMOUNT":
                com_amnt = commission

            # tax_in_percent = get_tax_rate(com_amnt, self.tax_rules_dict)
            config = BasicAdminConfig.objects.get(code="commission_tax_percent")
            tax_in_percent = Decimal(config.value)
            tax_amount = calculate_tax(tax_in_percent, com_amnt)

            com_amnt_withtax = com_amnt + tax_amount
            commission_details = {
                "com_amnt": com_amnt,
                "tax_amount": tax_amount,
                "tax_percentage": tax_in_percent,
                "com_amnt_withtax": com_amnt_withtax,
                "commission": commission,
                "tcs": 0.0,
                "tds": 0.0,
                "commission_type": comm_type,
            }
            commission_details = hotelier_commission_calculation(
                commission_details, final_amount, final_tax_amount, pay_at_hotel
            )
    except Exception as e:
        print(traceback.format_exc())
        print(e)

    return commission_details
