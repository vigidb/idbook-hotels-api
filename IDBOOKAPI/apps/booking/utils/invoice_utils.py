# invoice
import requests
import json

from IDBOOKAPI.utils import (
    get_current_date, last_calendar_month_day)

invoice_url = "https://invoice-api.idbookhotels.com"

def get_invoice_number():

    url = "{invoice_url}/api/invoices/generate-invoice-number".format(
        invoice_url=invoice_url)

    payload = {}
    headers = {}
    invoice_number = ""

    response = requests.request("GET", url, headers=headers, data=payload)
    print(response.status_code)
    if response.status_code == 200:
        data = response.json()
        if data:
            invoice_number = data.get('invoiceNumber', '')
    else:
        print(response.json())
    return invoice_number

def invoice_json_hotel_booking(hotel_booking):
    property_name, room_type = '', ''
    room_subtotal, service_tax = 0.0, 0.0
    
    # property details
    if hotel_booking.confirmed_property:
        confirmed_property = hotel_booking.confirmed_property
        property_name = confirmed_property.name
    # room details    
    if hotel_booking.room:
        room = hotel_booking.room
        room_type = room.room_type

    room_subtotal = float(hotel_booking.room_subtotal)
    service_tax = hotel_booking.service_tax
    
    item = { "name": room_type, "description": property_name, "quantity": 1,
     "price": room_subtotal, "amount": room_subtotal }
    
    return item

def invoice_json_holidaypack_booking(hpackage):
    trip_name = ""
    if hpackage.confirmed_holiday_package:
        confirmed_pack = hpackage.confirmed_holiday_package
        trip_name = confirmed_pack.trip_name
    holidaypack_subtotal = float(hpackage.holidaypack_subtotal)
    item = { "name": trip_name, "description": trip_name, "quantity": 1,
         "price": holidaypack_subtotal, "amount": holidaypack_subtotal}
    return item

def invoice_json_vehicle_booking(vehicle_booking):
    vehicle_type = ""
    if vehicle_booking.confirmed_vehicle:
        confirmed_vehicle = vehicle_booking.confirmed_vehicle
        vehicle_type = confirmed_vehicle.vehicle_type
    vehicle_subtotal = float(vehicle_booking.vehicle_subtotal)

    item = { "name": vehicle_type, "description": vehicle_type, "quantity": 1,
         "price": vehicle_subtotal, "amount": vehicle_subtotal}
        
    return item

def invoice_json_flight_booking(flight_booking):
    flying_from = flight_booking.flying_from
    flying_to = flight_booking.flying_to
    flight_subtotal = float(flight_booking.flight_subtotal)
    flight_class = flight_booking.flight_class
    flight_trip = flight_booking.flight_trip

    description = "Flight Class: {flight_class}, Flight trip {flight_trip}".format(
       flight_class=flight_class, flight_trip=flight_trip)
    name = "{flying_from}--{flying_to}".format(flying_from=flying_from, flying_to=flying_to)
    item = { "name": name, "description": description, "quantity": 1,
         "price": flight_subtotal, "amount": flight_subtotal}
    return item

def invoice_json_data(booking, bus_details, company_details, invoice_number, invoice_action='create'):
    logo = ""
    billed_by =  { "name": "", "address": "",
                   "GSTIN": "", "PAN": "",
                   "email": "", "website": ""}
    billed_to = { "name": "", "address": "",
                 "GSTIN": "", "PAN": ""}
    supply_details = { "countryOfSupply": "", "placeOfSupply": ""}
    item = { "name": "", "description": "", "quantity": 0,
             "price": 0, "amount": 0 }
    total, gst = 0, 0
    
    if bus_details:
        logo = bus_details.business_logo
        billed_by =  { "name": bus_details.business_name, "address": bus_details.full_address,
                       "GSTIN": bus_details.gstin_no, "PAN": bus_details.pan_no,
                       "email": bus_details.business_email,
                       "website": bus_details.website_url}
    if company_details:
        billed_to = { "name": company_details.company_name, "address": company_details.registered_address,
                      "GSTIN": company_details.gstin_no, "PAN": company_details.pan_no}
        supply_details = { "countryOfSupply": company_details.country,
                           "placeOfSupply": company_details.state}

    if booking:
        booking_type = booking.booking_type
        if booking_type == 'HOTEL':
            if booking.hotel_booking:
                item = invoice_json_hotel_booking(booking.hotel_booking)
                gst = float(booking.hotel_booking.service_tax)
                
        elif booking_type == 'HOLIDAYPACK':
            if booking.holiday_package_booking:
                item = invoice_json_holidaypack_booking(booking.holiday_package_booking)
                gst = float(booking.holiday_package_booking.service_tax)
            
        elif booking_type == 'VEHICLE':
            if booking.vehicle_booking:
                item = invoice_json_vehicle_booking(booking.vehicle_booking)
                gst = float(booking.vehicle_booking.service_tax)
        elif booking_type == 'FLIGHT':
            if booking.flight_booking:
                item = invoice_json_flight_booking(booking.flight_booking)
                gst = float(booking.flight_booking.service_tax)
                
            
        total = float(booking.final_amount)
        
##        booking.total_payment_made
    if invoice_action == 'create':
        invoice_date = get_current_date()
        last_day = last_calendar_month_day(invoice_date)
        if last_day:
            invoice_due_date = invoice_date.replace(day=last_day)
        else:
            invoice_due_date = invoice_date
        payload = json.dumps({
            "logo": logo, "header": "string", "footer": "string",
            "invoiceNumber": invoice_number,
            "invoiceDate": invoice_date.isoformat(), "dueDate": invoice_due_date.isoformat(),
            "notes": "string",
            "billedBy": billed_by, "billedTo": billed_to, "supplyDetails": supply_details,
            "items": [item],
            "GST": gst, "GSTType": "string", "total": total, "status": "Pending",
            "nextScheduleDate": "2024-10-29T03:31:39.493Z",
            "tags": ["string"] })
    elif invoice_action == 'update':
        payload = json.dumps({
            "logo": logo, 
            "notes": "string",
            "billedBy": billed_by, "billedTo": billed_to, "supplyDetails": supply_details,
            "items": [item],
            "GST": gst, "GSTType": "string", "total": total, "status": "Pending",
            "nextScheduleDate": "2024-10-29T03:31:39.493Z",
            "tags": ["string"] })
    else:
        payload = {}
    
    print("payload::", payload)
    
    return payload

def create_invoice(payload):
    url = "{invoice_url}/api/invoices".format(
        invoice_url=invoice_url)
    
    headers = {
      'Content-Type': 'application/json'
    }

    response = requests.request("POST", url, headers=headers, data=payload)
    print(response.status_code)
    if response.status_code == 201:
        data = response.json()
        invoice_data = data.get('data', '')
        invoice_id = invoice_data.get('_id', '')
        print("id::", invoice_id)
        return invoice_id
        #print("id::", data.get('_id', ''))
    else:
        print(response.json())
        return None

def update_invoice(invoice_id, payload):
    url = "{invoice_url}/api/invoices/{invoice_id}".format(
        invoice_url=invoice_url, invoice_id=invoice_id)

    headers = {
      'accept': 'application/json',
      'Content-Type': 'application/json'
    }

    response = requests.request("PATCH", url, headers=headers, data=payload)
    print("response status code", response.status_code)
    if response.status_code == 200:
        data = response.json()
        print(data)
    else:
        print(response.json())
    

def mark_invoice_as_paid(invoice_id):

    url = "{invoice_url}/api/invoices/{invoice_id}".format(
        invoice_url=invoice_url, invoice_id=invoice_id)

    payload = json.dumps({
      "status": "Pending"
    })
    headers = {
      'accept': 'application/json',
      'Content-Type': 'application/json'
    }

    response = requests.request("PATCH", url, headers=headers, data=payload)
    if response.status_code == 200:
        data = response.json()
        print(data)
