from django.utils.text import slugify
import random
import string
import datetime
import re
from django.utils import timezone
from decimal import Decimal
import calendar


def get_current_date():
    current_date = timezone.now()
    return current_date

def last_calendar_month_day(date):
    day = None
    try:
        day = calendar.monthrange(date.year, date.month)[1]
    except Exception as e:
        print(e)
    return day
    

def random_string_generator(size=10, chars=string.ascii_lowercase + string.digits):
    return ''.join(random.choice(chars) for _ in range(size))


def unique_key_generator(instance):
    size = random.randint(30, 40)
    key = random_string_generator(size=size)

    Klass = instance.__class__
    qs_exists = Klass.objects.filter(key=key).exists()
    if qs_exists:
        return unique_slug_generator(instance)
    return key


def unique_verification_key_generator(instance):
    size = random.randint(10, 15)
    verification_key = random_string_generator(size=size)

    Klass = instance.__class__
    qs_exists = Klass.objects.filter(verification_key=verification_key).exists()
    if qs_exists:
        return unique_slug_generator(instance)
    return verification_key


def unique_id_generator(instance):
    size = random.randint(10, 12)
    verification_key = random_string_generator(size=size)

    Klass = instance.__class__
    qs_exists = Klass.objects.filter(verification_key=verification_key).exists()
    if qs_exists:
        return unique_slug_generator(instance)
    return verification_key


def unique_referral_id_generator(instance):
    size = random.randint(11, 15)
    referral_key = random_string_generator(size=size)

    Klass = instance.__class__
    qs_exists = Klass.objects.filter(referral=referral_key).exists()
    if qs_exists:
        return unique_slug_generator(instance)
    return referral_key


def unique_slug_generator(instance, new_slug=None):
    if new_slug is not None:
        slug = new_slug
    else:
        slug = slugify(instance.title)

    Klass = instance.__class__
    qs_exists = Klass.objects.filter(slug=slug).exists()
    if qs_exists:
        new_slug = "{slug}-{randstr}".format(
                    slug=slug,
                    randstr=random_string_generator(size=4)
                )
        return unique_slug_generator(instance, new_slug=new_slug)
    return slug

def get_last_month_data(today):
    '''
    Simple method to get the datetime objects for the
    start and end of last month.
    '''
    this_month_start = datetime.datetime(today.year, today.month, 1)
    last_month_end = this_month_start - datetime.timedelta(days=1)
    last_month_start = datetime.datetime(last_month_end.year, last_month_end.month, 1)
    return (last_month_start, last_month_end)


def get_month_data_range(months_ago=1, include_this_month=False):
    '''
    A method that generates a list of dictionaires
    that describe any given amout of monthly data.
    '''
    today = datetime.datetime.now().today()
    dates_ = []
    if include_this_month:
        # get next month's data with:
        next_month = today.replace(day=28) + datetime.timedelta(days=4)
        # use next month's data to get this month's data breakdown
        start, end = get_last_month_data(next_month)
        dates_.insert(0, {
            "start": start.timestamp(),
            "end": end.timestamp(),
            "start_json": start.isoformat(),
            "end_json": end.isoformat(),
            "timesince": 0,
            "year": start.year,
            "month": str(start.strftime("%B")),
            })
    for x in range(0, months_ago):
        start, end = get_last_month_data(today)
        today = start
        dates_.insert(0, {
            "start": start.timestamp(),
            "end": end.timestamp(),
            "start_json": start.isoformat(),
            "end_json": end.isoformat(),
            "timesince": int((datetime.datetime.now() - end).total_seconds()),
            "year": start.year,
            "month": str(start.strftime("%B"))
        })
    #dates_.reverse()
    return dates_


def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(",")[0]
    else:
        ip = request.META.get("REMOTE_ADDR", None)
    return ip


def format_custom_id(prefix, number):
    formatted_number = str(number).zfill(6)
    formatted_id = f'{prefix}{formatted_number}'
    return formatted_id


def format_room_id(hotel_custom_id, room_type_prefix, room_number):
    formatted_number = str(room_number).zfill(7)
    formatted_room_id = f'{hotel_custom_id}{room_type_prefix}{formatted_number}'
    return formatted_room_id


def format_tour_id(prefix, number):
    formatted_number = str(number).zfill(6)
    formatted_id = f'{prefix}{formatted_number}'
    return formatted_id


def get_default_time():
    return datetime.datetime.now().time()


def format_tour_duration(input_str):
    if not input_str:
        return None

    # Use regular expression to extract nights and days
    match = re.match(r'(\d+)N/(\d+)D', input_str)

    if match:
        nights = int(match.group(1))
        days = int(match.group(2))
        total_nights = nights + days
        formatted_output = f"{total_nights} Night & {days} Days"
        return formatted_output

    return None

def paginate_queryset(request, queryset):
    offset = int(request.query_params.get('offset', 0))
    limit = int(request.query_params.get('limit', 10))

    count = queryset.count()
    queryset = queryset[offset:offset+limit]

    return count, queryset

def calculate_tax(tax_in_percent, amount):
    tax_amount = (tax_in_percent * amount) / 100
    return tax_amount

def get_days_from_string(start_date: str, end_date: str, string_format='%Y-%m-%d'):
    try:
        #string_format = "%Y-%m-%dT%H:%M%z"
        
        start_date = datetime.datetime.strptime(start_date, string_format).date()
        end_date = datetime.datetime.strptime(end_date, string_format).date()
        
        diff_date = end_date - start_date
        
        return diff_date.days
    except Exception as e:
        print(e)
        return None
    
    
    

##def quantize_decimal_value(value: Decimal):
##    try:
##        if value == value.to_integral():
##            return value.quantize(Decimal(1))
##        else:
##            return value.normalize()
##    except Exception as e:
##        print("Error in decimal conversion::", e)
##        return value


from IDBOOKAPI.basic_resources import DISTRICT_DATA


# Find districts for a specific state
def find_districts(state_name):
    for state_data in DISTRICT_DATA:
        if state_data["state"] == state_name.title():
            return state_data["districts"]
    return []


# Find state for a specific district
def find_state(district_name):
    for state_data in DISTRICT_DATA:
        if district_name.title() in state_data["districts"]:
            return state_data["state"]
    return None

def default_address_json():
    address_json = {"building_or_hse_no": "",
                    "pincode":"", "coordinates":{"lat":"", "lng":""},
                    "location_url": ""}
    return address_json


# Example usage
# state_name = "madhya Pradesh"
# print(state_name.title())
# districts_in_state = find_districts(state_name)
# print(f"Districts in {state_name}: {districts_in_state}")

# district_name = "Guntur"
# state_of_district = find_state(district_name)
# if state_of_district:
#     print(f"{district_name} is in the state of {state_of_district}")
# else:
#     print(f"District {district_name} not found in the data.")
