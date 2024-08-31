import requests
import json
from decimal import Decimal
from faker import Faker
import random
from faker.providers.phone_number import Provider as PhoneNumberProvider


def generate_indian_phone_number():
    fake = Faker()

    # Custom provider for Indian phone numbers
    class IndianPhoneNumberProvider(PhoneNumberProvider):
        formats = (
            '+91##########',
        )

    # Add the custom provider
    fake.add_provider(IndianPhoneNumberProvider)

    # Generate Indian phone number
    indian_phone_number = fake.phone_number()

    return indian_phone_number


def generate_dummy_data_hotel():
    fake = Faker()

    dummy_data = {
        "id": 0,
        "service_category": "Hotel",
        "name": fake.name(),
        "slug": fake.slug(),
        "checkin_time": fake.time(),
        "checkout_time": fake.time(),
        "full_address": fake.address(),
        "district": fake.city(),
        "state": "Andaman and Nicobar Islands",
        "country": fake.country(),
        "pin_code": fake.random_int(min=100000, max=999999),
        "location": fake.address(),
        "area_name": fake.city_suffix(),
        "city_name": fake.city(),
        "latitude": fake.latitude(),
        "longitude": fake.longitude(),
        "email": fake.email(),
        "phone_no": generate_indian_phone_number(),
        "description": fake.text(),
        "starting_price": fake.random_number(digits=5),
        "featured": fake.boolean(),
        "active": fake.boolean(),
        "created": fake.date_time_this_decade().isoformat(),
        "updated": fake.date_time_this_decade().isoformat(),
        "amenity": [1]
    }

    return dummy_data


class DecimalEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, Decimal):
            return float(o)
        return super().default(o)


def insert_dummy_data():
    dummy_data = generate_dummy_data_hotel()  # Assuming `generate_dummy_data()` is defined as shown in the previous response
    url = "http://127.0.0.1:8000/api/v1/hotel/"  # Replace with the actual API endpoint URL

    headers = {
        "Content-Type": "application/json"
    }
    # print(dummy_data)
    payload = json.dumps(dummy_data, cls=DecimalEncoder)

    response = requests.post(url, data=payload, headers=headers)

    if response.status_code == 201:  # Assuming a successful response returns HTTP status code 201 (Created)
        print("Dummy data inserted successfully.")
    else:
        print("Failed to insert dummy data. Error:", response.text)


# for i in range(5000):
#     insert_dummy_data()


def generate_dummy_data_room():
    fake = Faker()
    hotel_ids = [254, 253, 252, 251, 250, 249, 248, 247, 246, 245, 244, 243, 242, 241, 240, 239, 238, 237, 236, 235, 234,
                 233, 232, 231, 230, 229, 228, 227, 226, 225, 224, 223, 222, 221, 220, 219, 218, 217, 216, 215, 214, 213,
                 212, 211, 210, 209, 208, 207, 206, 205, 204, 203, 202, 201, 200, 199, 198, 197, 196, 195, 194, 193, 192,
                 191, 190, 189, 188, 187, 186, 185, 184, 183, 182, 181, 180, 179, 178, 177, 176, 175, 174, 173, 172, 171,
                 170, 169, 168, 167, 166, 165, 164, 163, 162, 161, 160, 159, 158, 157, 156, 155, 154, 153, 152, 151, 150,
                 149, 148, 147, 146, 145, 144, 143, 142, 141, 140, 139, 138, 137, 136, 135, 134, 133, 132, 131, 130, 129,
                 128, 127, 126, 125, 124, 123, 122, 121, 120, 119, 118, 117, 116, 115, 114, 113, 112, 111, 110, 109, 108,
                 107, 106, 105, 104, 103, 102, 101, 100, 99, 98, 97, 96, 95, 94, 93, 92, 91, 90, 89, 88, 87, 86, 85, 84,
                 83, 82, 81, 80, 79, 78, 77, 76, 75, 74, 73, 72, 71, 70, 69, 68, 67, 66, 65, 64, 63, 62, 61, 60, 59, 58,
                 57, 56, 55, 54, 53, 52, 51, 50, 49, 48, 47, 46, 45, 44, 43, 42, 41, 40, 39, 38, 37, 36, 35, 34, 33, 32,
                 31, 30, 29, 28, 27, 26, 25, 24, 23, 22, 21, 20, 19, 18, 17, 16, 15, 14, 13, 12, 11, 10, 9, 8, 7, 6, 5,
                 4, 3, 2, 1]
    random_hotel_id = random.choice(hotel_ids)
    amenities = [6, 5, 4, 3, 2, 1]
    amenities_id = random.choice(amenities)
    room_type_ids = [3, 2, 1]
    room_type_id = random.choice(room_type_ids)

    dummy_data = {
        "id": 0,
        "time_duration": "4 HOURS",
        "area": 32767,
        "person_capacity": 32767,
        "child_capacity": 32767,
        "price": fake.random_number(digits=4),
        "discount": 32767,
        "availability": fake.boolean(),
        "created": fake.date_time_this_decade().isoformat(),
        "updated": fake.date_time_this_decade().isoformat(),
        "hotel": random_hotel_id,
        "room_type": room_type_id,
        "amenities": [amenities_id]
    }

    return dummy_data


def insert_dummy_data_room():
    dummy_data = generate_dummy_data_room()  # Assuming `generate_dummy_data()` is defined as shown in the previous response
    url = "http://127.0.0.1:8000/api/v1/room/"  # Replace with the actual API endpoint URL
    # print(dummy_data)
    headers = {
        "Content-Type": "application/json"
    }

    payload = json.dumps(dummy_data, cls=DecimalEncoder)

    response = requests.post(url, data=payload, headers=headers)

    if response.status_code == 201:  # Assuming a successful response returns HTTP status code 201 (Created)
        print(".")
    else:
        print("Failed to insert dummy data. Error:", response.text)

for i in range(400000000):
    insert_dummy_data_room()
