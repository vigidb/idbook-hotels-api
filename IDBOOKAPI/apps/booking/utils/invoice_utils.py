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

    name = f"{room_type}, {property_name}"
    
    item = { "name": name, "description": "", "quantity": 1,
     "price": "", "amount": "" }
    
    return item

def invoice_json_holidaypack_booking(hpackage):
    trip_name = ""
    if hpackage.confirmed_holiday_package:
        confirmed_pack = hpackage.confirmed_holiday_package
        trip_name = confirmed_pack.trip_name
    
    item = { "name": trip_name, "description": "", "quantity": 1,
         "price": "", "amount": ""}
    return item

def invoice_json_vehicle_booking(vehicle_booking):
    vehicle_type = ""
    if vehicle_booking.confirmed_vehicle:
        confirmed_vehicle = vehicle_booking.confirmed_vehicle
        vehicle_type = confirmed_vehicle.vehicle_type

    item = { "name": vehicle_type, "description": "", "quantity": 1,
         "price": "", "amount": ""}
        
    return item

def invoice_json_flight_booking(flight_booking):
    flight_no = flight_booking.flight_no
    flight_trip = flight_booking.flight_trip
    
    flying_from = flight_booking.flying_from
    flying_to = flight_booking.flying_to

    departure_date = flight_booking.departure_date
    arrival_date = flight_booking.arrival_date
    departure_time = departure_date.strftime('%H:%M %Z%z') if departure_date else ''
    arrival_time = arrival_date.strftime('%H:%M %Z%z') if arrival_date else ''
    #flight_subtotal = float(flight_booking.flight_subtotal)
    
    flight_class = flight_booking.flight_class
    flight_trip = flight_booking.flight_trip

    if flight_trip == 'ONE-WAY':
        description = "Flight Class: {flight_class}, Flight trip {flight_trip}, \
Date- {departure_date}, Flight Destination- {flying_from} to {flying_to} \
Flight Number- {flight_no} \
Time - {flying_from} departure {departure_time} and \
{flying_to} arrival {arrival_time}".format(
            flight_class=flight_class, flight_trip=flight_trip,
            departure_date=departure_date, flying_from=flying_from, flying_to=flying_to,
            flight_no=flight_no, departure_time = departure_time, arrival_time=arrival_time)
    elif flight_trip == 'ROUND':
        return_date = flight_booking.return_date
        return_arrival_date = flight_booking.return_arrival_date
        return_from = flight_booking.return_from
        return_to = flight_booking.return_to
        
        description = f"Flight Class: {flight_class}, Flight trip {flight_trip}, \
Date- {departure_date}, Flight Destination- {flying_from} to {flying_to} \
Flight Number- {flight_no} \
Time - {flying_from} departure {departure_date} and \
{flying_to} arrival {arrival_date} \
Return Time - {return_from} departure {return_date} and \
{return_to} arrival {return_arrival_date}"

    
    name = "FLIGHT ({flight_no})".format(flight_no=flight_no)
    item = { "name": name, "description": description, "quantity": 1,
         "price": "", "amount": ""}
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
    subtotal = 0
    notes = ''
    
    if bus_details:
        if bus_details.business_logo:
            logo = bus_details.business_logo.url
        billed_by =  { "name": bus_details.business_name, "address": bus_details.full_address,
                       "GSTIN": bus_details.gstin_no, "PAN": bus_details.pan_no,
                       "email": bus_details.business_email,
                       "website": bus_details.website_url, "hsn_sac_no": bus_details.hsn_sac_no}
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
                gst = float(booking.gst_percentage)
                gst_type = booking.gst_type
                subtotal = float(booking.subtotal)
                
                
        elif booking_type == 'HOLIDAYPACK':
            if booking.holiday_package_booking:
                item = invoice_json_holidaypack_booking(booking.holiday_package_booking)
                gst = float(booking.gst_percentage)
                gst_type = booking.gst_type
                subtotal = float(booking.subtotal)
            
        elif booking_type == 'VEHICLE':
            if booking.vehicle_booking:
                item = invoice_json_vehicle_booking(booking.vehicle_booking)
                gst = float(booking.gst_percentage)
                gst_type = booking.gst_type
                subtotal = float(booking.subtotal)
                
        elif booking_type == 'FLIGHT':
            if booking.flight_booking:
                item = invoice_json_flight_booking(booking.flight_booking)
                gst, gst_type  = "", ""
                subtotal = float(booking.subtotal)
                
            
        total = float(booking.final_amount)
        description = booking.description + item.get('description')
        
        item['price'] = subtotal
        item['amount'] = subtotal
        item['description'] = description
        
        notes = booking.additional_notes
        
##        booking.total_payment_made
    if invoice_action == 'create':
        invoice_date = get_current_date()
        last_day = last_calendar_month_day(invoice_date)
        if last_day:
            invoice_due_date = invoice_date.replace(day=last_day)
        else:
            invoice_due_date = invoice_date
        # invoice_due_date.isoformat()
        payload = json.dumps({
            "logo": logo, "header": "", "footer": "",
            "invoiceNumber": invoice_number,
            "invoiceDate": invoice_date.isoformat(), "dueDate": "",
            "notes": notes,
            "billedBy": billed_by, "billedTo": billed_to, "supplyDetails": supply_details,
            "items": [item],
            "GST": gst, "GSTType": gst_type, "total": total, "status": "Paid",
            "nextScheduleDate": "",
            "tags": [""] })
    elif invoice_action == 'update':
        payload = json.dumps({
            "logo": logo, 
            "notes": notes,
            "billedBy": billed_by, "billedTo": billed_to, "supplyDetails": supply_details,
            "items": [item],
            "GST": gst, "GSTType": gst_type, "total": total, "status": "Paid",
            "nextScheduleDate": "",
            "tags": [""] })
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
    return response
    

def update_invoice(invoice_id, payload):
    url = "{invoice_url}/api/invoices/{invoice_id}".format(
        invoice_url=invoice_url, invoice_id=invoice_id)

    headers = {
      'accept': 'application/json',
      'Content-Type': 'application/json'
    }

    response = requests.request("PATCH", url, headers=headers, data=payload)
    print("response status code", response.status_code)
    return response
    

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
