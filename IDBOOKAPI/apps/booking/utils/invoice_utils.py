# invoice
import requests
import json
from apps.booking.models import Invoice, BookingPaymentDetail
from datetime import datetime
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

def create_invoice_number():
    current_year = datetime.now().year
    current_month = str(datetime.now().month).zfill(2)

    initial_invoice_number = 50239

    last_invoice = Invoice.objects.filter(invoice_number__startswith=f"Idb-{current_year}-{current_month}-") \
                                  .order_by('-invoice_number') \
                                  .first()

    if not last_invoice or not last_invoice.invoice_number:
        return f"Idb-{current_year}-{current_month}-{initial_invoice_number}"

    try:
        last_number = int(last_invoice.invoice_number.split('-')[-1])
    except ValueError:
        return f"Idb-{current_year}-{current_month}-{initial_invoice_number}"

    new_invoice_number = last_number + 1

    invoice_number = f"Idb-{current_year}-{current_month}-{new_invoice_number}"
    return invoice_number

def invoice_json_hotel_booking(hotel_booking):
    property_name, room_type = '', ''
    room_subtotal, service_tax = 0.0, 0.0
    items = []
    
    # property details
    if hotel_booking.confirmed_property:
        confirmed_property = hotel_booking.confirmed_property
        property_name = confirmed_property.name

    confirmed_checkin_time = hotel_booking.confirmed_checkin_time
    confirmed_checkout_time = hotel_booking.confirmed_checkout_time

    confirmed_room_details = hotel_booking.confirmed_room_details

    for confirmed_room in confirmed_room_details:
        room_id = confirmed_room.get('room_id', None)
        room_type = confirmed_room.get('room_type', '')
        price = confirmed_room.get('price', None)
        no_of_rooms = confirmed_room.get('no_of_rooms', 0)
        tax_in_percent = confirmed_room.get("tax_in_percent", None)
        total_room_amount = confirmed_room.get("total_room_amount", None)
        total_tax_amount = confirmed_room.get("total_tax_amount", None)
        no_of_days = confirmed_room.get("no_of_days", None)

        name = f"{room_type}, {property_name}"
        description = f" Check In:: {confirmed_checkin_time}, Check Out:: {confirmed_checkout_time}, \
No of Days:: {no_of_days} "
    
        item = { "name": name, "description": description, "quantity": no_of_rooms,
                 "price": price, "amount": total_room_amount, "gst":tax_in_percent,
                 "tax":total_tax_amount}
        items.append(item)
        

    
##    # room details    
##    if hotel_booking.room:
##        room = hotel_booking.room
##        room_type = room.room_type
    
    return items

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

def invoice_json_data(booking, bus_details, company_details, customer_details,
                      invoice_number, invoice_action='create'):
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
    is_same_state = False
    business_state = None

    
    if bus_details:
        if bus_details.business_logo:
            logo = bus_details.business_logo.url
        billed_by =  { "name": bus_details.business_name, "address": bus_details.full_address,
                       "GSTIN": bus_details.gstin_no, "PAN": bus_details.pan_no,
                       "email": bus_details.business_email,
                       "website": bus_details.website_url, "hsn_sac_no": bus_details.hsn_sac_no}
        
        business_state = bus_details.state
        if business_state:
            business_state = business_state.lower()
            
    if company_details:
        billed_to = { "name": company_details.company_name, "address": company_details.registered_address,
                      "GSTIN": company_details.gstin_no, "PAN": company_details.pan_no}
        supply_details = { "countryOfSupply": company_details.country,
                           "placeOfSupply": company_details.state}

        # for gst type
        if company_details.state:
            if business_state == company_details.state.lower():
                is_same_state = True
            
        
    elif customer_details:
        address = customer_details.address if customer_details.address else ''
        country = customer_details.country if customer_details.country else ''
        state = customer_details.state if customer_details.state else ''
        pan = customer_details.pan_card_number if customer_details.pan_card_number else ''
        
        billed_to = { "name": customer_details.user.name, "address": address,
                      "GSTIN": "", "PAN": customer_details.pan_card_number}
        supply_details = { "countryOfSupply": country,
                           "placeOfSupply": state}

        if customer_details.state:
            if business_state == customer_details.state.lower():
                is_same_state = True
        

    if booking:
        booking_type = booking.booking_type
        if booking_type == 'HOTEL':
            if booking.hotel_booking:
                item = invoice_json_hotel_booking(booking.hotel_booking)
                if item and item[0]:
                    gst = item[0].get('gst',0)
                else:
                    gst = 0
                # below code need to change
                #gst =  18 #float(booking.gst_percentage)
                # set gst type
                if is_same_state:
                    gst_type = "CGST/SGST"
                else:
                    gst_type = "IGST"
                # subtotal = float(booking.subtotal)
                
                
        elif booking_type == 'HOLIDAYPACK':
            if booking.holiday_package_booking:
                item = invoice_json_holidaypack_booking(booking.holiday_package_booking)
                item = [item] # temp need to change
                gst = float(booking.gst_percentage)
                gst_type = booking.gst_type
                subtotal = float(booking.subtotal)
            
        elif booking_type == 'VEHICLE':
            if booking.vehicle_booking:
                item = invoice_json_vehicle_booking(booking.vehicle_booking)
                item = [item] # temp need to change
                
                gst = float(booking.gst_percentage)
                gst_type = booking.gst_type
                subtotal = float(booking.subtotal)
                
        elif booking_type == 'FLIGHT':
            if booking.flight_booking:
                item = invoice_json_flight_booking(booking.flight_booking)
                item = [item] # temp need to change
                gst, gst_type  = "", ""
                subtotal = float(booking.subtotal)
                
            
        total = float(booking.final_amount)
##        description = booking.description + item.get('description')
##        
##        item['price'] = subtotal
##        item['amount'] = subtotal
##        item['description'] = description
        
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
            "items": item,
            "GST": gst, "GSTType": gst_type, "total": total, "status": "Paid",
            "nextScheduleDate": "",
            "tags": [""] })
    elif invoice_action == 'update':
        payload = json.dumps({
            "logo": logo, 
            "notes": notes,
            "billedBy": billed_by, "billedTo": billed_to, "supplyDetails": supply_details,
            "items": item,
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

def create_invoice_response_data(invoice, payload_json):
    """
    Create a response object similar to the external API format.
    """
    try:
        if not invoice:
            return {"success": False, "error": "No invoice found"}

        payload = json.loads(payload_json)

        # Get payment history
        payment_history = []
        payments = BookingPaymentDetail.objects.filter(invoice=invoice)
        for payment in payments:
            payment_history.append({
                "_id": str(payment.id),
                "amount": float(payment.amount) if payment.amount else 0,
                "paymentMode": payment.payment_mode or "",
                "reference": payment.reference or "",
                "transactionId": payment.transaction_id or "",
                "date": payment.created.isoformat() if payment.created else None
            })

        # Calculate total amount (excluding tax)
        total_amount = 0
        items = invoice.items or []
        for item in items:
            try:
                total_amount += float(item.get("amount", 0))
            except (ValueError, TypeError):
                continue

        response = {
            "success": True,
            "data": {
                "_id": str(invoice.id),
                "invoiceNumber": invoice.invoice_number,
                "invoiceDate": invoice.invoice_date.isoformat() if invoice.invoice_date else None,
                "dueDate": invoice.due_date.isoformat() if invoice.due_date else None,
                "logo": invoice.logo or "",
                "header": invoice.header or "",
                "footer": invoice.footer or "",
                "notes": invoice.notes or "",
                "billedBy": invoice.billed_by_details or {},
                "billedTo": invoice.billed_to_details or {},
                "supplyDetails": invoice.supply_details or {},
                "items": items,
                "GST": float(invoice.GST or 0),
                "GSTType": invoice.GST_type or "",
                "total": float(invoice.total or 0),
                "totalAmount": float(invoice.total_amount or (invoice.total + invoice.total_tax)),
                "status": invoice.status or "Pending",
                "nextScheduleDate": invoice.next_schedule_date.isoformat() if invoice.next_schedule_date else None,
                "tags": invoice.tags.split(',') if invoice.tags else [],
                "paymentHistory": payment_history,
                "createdAt": invoice.created_at.isoformat() if invoice.created_at else None,
                "updatedAt": invoice.updated_at.isoformat() if invoice.updated_at else None,
                "__v": 0
            }
        }

        return response
    except Exception as e:
        print(f"Error creating invoice response data: {e}")
        return {"success": False, "error": str(e)}
