# invoice
import requests
import json
import re
from decimal import Decimal, InvalidOperation

from apps.booking.models import Invoice, BookingPaymentDetail
from apps.org_managements.models import BusinessDetail
from datetime import datetime
from IDBOOKAPI.utils import (
    get_current_date, last_calendar_month_day)
from django.template.loader import render_to_string
from django.template import Context, Template
import pdfkit
import os, io
from django.core.files.base import ContentFile
from django.db.models import Sum
from django.conf import settings

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

def generate_business_code(business_detail):
    """
    Generate a consistent, unique code for a business.
    Uses state code (or country code as fallback) + business ID for guaranteed uniqueness.
    
    Priority:
    1. State code (first 2-3 chars)
    2. Country code (first 2-3 chars) 
    3. Default 'XX' if neither exists
    Then append business ID
    
    Args:
        business_detail: BusinessDetail object
        
    Returns:
        str: A unique business code (e.g., 'MH5', 'IND12', 'XX3', etc.)
    """
    if not business_detail:
        return "GLB0"  # Global fallback
    
    location_code = ""
    
    # Priority 1: Try to get state code
    if business_detail.state:
        # Remove special characters and spaces, get alphanumeric only
        clean_state = re.sub(r'[^A-Z0-9]', '', business_detail.state.upper())
        location_code = clean_state[:3] if len(clean_state) >= 3 else clean_state[:2]
    
    # Priority 2: If no state, try country code
    if not location_code and business_detail.country:
        clean_country = re.sub(r'[^A-Z0-9]', '', business_detail.country.upper())
        location_code = clean_country[:3] if len(clean_country) >= 3 else clean_country[:2]
    
    # Priority 3: Default if neither state nor country exists
    if not location_code:
        location_code = "XX"
    
    # Always append business ID for guaranteed uniqueness
    business_code = location_code + str(business_detail.id)
    
    return business_code.upper()


def create_invoice_number(billed_by_id=None, gstin=None):
    """
    Generate an invoice number scoped per billed_by with unique business code.
    Format: Idb-<BUSINESS_CODE><BUS_ID>-YYYY-MM-<running_sequence>
    
    Examples:
        - ABC Company (ID=5): Idb-ABC5-2025-01-50239, Idb-ABC5-2025-01-50240, ...
        - XYZ Hotel (ID=12): Idb-XYZ12-2025-01-50239, Idb-XYZ12-2025-01-50240, ...
        - Without billed_by: Idb-GLB0-2025-01-50239, Idb-GLB0-2025-01-50240, ...

    - Business code + ID ensures complete uniqueness across all businesses
    - Sequence number increments per billed_by and month
    - Each business has its own sequence starting from 50239
    
    Args:
        billed_by_id: ID of the BusinessDetail object
        gstin: GSTIN number (optional, not used currently)
        
    Returns:
        str: Generated invoice number
    """
    print(f"DEBUG create_invoice_number called with billed_by_id={billed_by_id}, gstin={gstin}")
    
    current_year = datetime.now().year
    current_month = str(datetime.now().month).zfill(2)
    initial_invoice_number = 50239

    # Get business code (includes ID for uniqueness)
    business_code = "GLB0"  # Default for global scope
    if billed_by_id:
        try:
            business_detail = BusinessDetail.objects.get(id=billed_by_id)
            business_code = generate_business_code(business_detail)
            print(f"DEBUG: Found BusinessDetail, generated code={business_code}")
        except BusinessDetail.DoesNotExist:
            print(f"BusinessDetail with id {billed_by_id} not found, using global code")
            business_code = "GLB0"
    else:
        print(f"DEBUG: No billed_by_id provided, using global code={business_code}")

    prefix = f"Idb-{business_code}-{current_year}-{current_month}-"
    print(f"DEBUG: Generated prefix={prefix}")

    # Filter invoices for this specific business and month
    if billed_by_id:
        qs = Invoice.objects.filter(
            billed_by_id=billed_by_id,
            invoice_number__startswith=prefix
        )
    else:
        qs = Invoice.objects.filter(invoice_number__startswith=prefix)

    last_invoice = qs.order_by('-invoice_number').first()

    if not last_invoice or not last_invoice.invoice_number:
        # First invoice for this business/month combination
        return f"{prefix}{initial_invoice_number}"

    try:
        # Extract the last sequence number and increment it
        last_number = int(last_invoice.invoice_number.split('-')[-1])
        new_invoice_number = last_number + 1
    except ValueError:
        # If parsing fails, start from initial number
        new_invoice_number = initial_invoice_number

    invoice_number = f"{prefix}{new_invoice_number}"
    print(f"DEBUG: Final invoice_number={invoice_number}")
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
        room_discount_value = confirmed_room.get("room_discount_value", None)
        final_room_total = confirmed_room.get("final_room_total", None)
        room_amount_with_discount = confirmed_room.get("room_amount_with_discount", None)

        name = f"{room_type}, {property_name}"
        description = f" Check In:: {confirmed_checkin_time}, Check Out:: {confirmed_checkout_time}, \
No of Days:: {no_of_days} "
    
        item = { "name": name, "description": description, "quantity": no_of_rooms,
                 "price": price, "amount": total_room_amount, "gst":tax_in_percent,
                 "tax":total_tax_amount, "room_discount": room_discount_value,
                 "final_room_total": final_room_total, "room_amount_with_discount": room_amount_with_discount}
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

def _to_decimal(value) -> Decimal:
    """Safely convert value to Decimal."""
    if value in (None, '', 'N/A'):
        return Decimal('0')
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal('0')


def invoice_json_flight_booking(booking):
    """Generate flight booking invoice items derived from AirIQ itinerary data with IDBook adjustments."""
    flight_booking = booking.flight_booking
    items = []
    airiq_data = flight_booking.airiq_response_data or {}

    def _format_segment(segment):
        origin = segment.get('Origin')
        destination = segment.get('Destination')
        flight_number = segment.get('FlightNumber')
        carrier = segment.get('CarrierCode')
        dep_time = segment.get('DepartureDateTime')
        arr_time = segment.get('ArrivalDateTime')
        extras = []
        if segment.get('MealsPreference'):
            extras.append(f"Meal: {segment.get('MealsPreference')} ({segment.get('MealsAmount', '0')})")
        if segment.get('BaggagePreference'):
            extras.append(f"Baggage: {segment.get('BaggagePreference')} ({segment.get('BaggageAmount', '0')})")
        if segment.get('SeatPreference'):
            extras.append(f"Seat: {segment.get('SeatPreference')} ({segment.get('SeatAmount', '0')})")
        extra_info = f"\n    " + "\n    ".join(extras) if extras else ""
        return f"{origin} → {destination} | {carrier}{flight_number} | {dep_time} → {arr_time}{extra_info}"

    itinerary_details = (
        airiq_data.get('Bookingresponse', {}).get('ItinearyDetails')
        or airiq_data.get('Bookingresponse', {}).get('ItineraryDetails')
        or []
    )

    if itinerary_details:
        for itinerary in itinerary_details:
            passengers_info = []
            line_total = Decimal('0')

            for leg in itinerary.get('Item', []):
                route_name = f"{leg.get('BaseOrigin')} → {leg.get('BaseDestination')}"
                payment_details = leg.get('PaymentDetails', {}).get('Item', [])
                if payment_details:
                    for payment_detail in payment_details:
                        line_total += _to_decimal(payment_detail.get('Amount'))

                traveller_info = leg.get('TravellerInfo', {}).get('Item', [])
                segment_rows = []
                for traveller in traveller_info:
                    pax_name = f"{traveller.get('Title', '').title()} {traveller.get('FirstName', '')} {traveller.get('LastName', '')}".strip()
                    pax_type = traveller.get('PaxType', '').upper()
                    ticket_number = traveller.get('TicketNumber', '')
                    passengers_info.append(f"{pax_name} ({pax_type}) - Ticket {ticket_number}")

                    segment_information = traveller.get('SegmentInformation', {}).get('Item', [])
                    for segment in segment_information:
                        segment_rows.append(_format_segment(segment))

                description_parts = [
                    f"Route: {route_name}",
                    f"Segments:\n    " + "\n    ".join(segment_rows) if segment_rows else "",
                    "Travellers:\n    " + "\n    ".join(passengers_info) if passengers_info else "",
                ]

                item = {
                    "name": f"Flight Itinerary - {route_name}",
                    "description": "\n".join(filter(None, description_parts)),
                    "quantity": 1,
                    "price": float(line_total) if line_total else float(_to_decimal(itinerary.get('TotalAmount'))),
                    "amount": float(line_total) if line_total else float(_to_decimal(itinerary.get('TotalAmount'))),
                    "gst": float(booking.gst_percentage or 0),
                    "tax": float(booking.gst_amount or 0),
                    "discount": 0,
                    "final_total": float(line_total) if line_total else float(_to_decimal(itinerary.get('TotalAmount'))),
                }
                items.append(item)

        # Distribute discounts, if any, across itinerary items
        total_discount = float(booking.discount or 0) + float(booking.pro_member_discount_value or 0)
        if total_discount > 0 and items:
            per_item_discount = total_discount / len(items)
            for item in items:
                item['discount'] = per_item_discount
                item['final_total'] = max(item['amount'] - per_item_discount, 0)
    else:
        # Fallback to legacy behaviour when AirIQ data is missing
        flight_no = flight_booking.flight_no or 'TBD'
        flight_trip = flight_booking.flight_trip
        flying_from = flight_booking.flying_from
        flying_to = flight_booking.flying_to
        flight_class = flight_booking.flight_class

        departure_date = flight_booking.departure_date
        arrival_date = flight_booking.arrival_date
        departure_time = departure_date.strftime('%d-%m-%Y %H:%M') if departure_date else 'TBD'
        arrival_time = arrival_date.strftime('%d-%m-%Y %H:%M') if arrival_date else 'TBD'

        if flight_trip == 'ONE-WAY':
            description = f"Flight Class: {flight_class}, Trip: {flight_trip}\nRoute: {flying_from} → {flying_to}\nFlight Number: {flight_no}\nDeparture: {departure_time}\nArrival: {arrival_time}"
        elif flight_trip == 'ROUND':
            return_date = flight_booking.return_date
            return_arrival_date = flight_booking.return_arrival_date
            return_from = flight_booking.return_from or flying_to
            return_to = flight_booking.return_to or flying_from

            return_dep_time = return_date.strftime('%d-%m-%Y %H:%M') if return_date else 'TBD'
            return_arr_time = return_arrival_date.strftime('%d-%m-%Y %H:%M') if return_arrival_date else 'TBD'

            description = f"Flight Class: {flight_class}, Trip: {flight_trip}\nOutbound: {flying_from} → {flying_to} on {departure_time}\nReturn: {return_from} → {return_to} on {return_dep_time}\nFlight Number: {flight_no}"
        else:
            description = f"Flight Class: {flight_class}, Route: {flying_from} → {flying_to}"

        passengers = flight_booking.passengers.all()
        passenger_count = {
            'adult': passengers.filter(passenger_type='ADULT').count(),
            'child': passengers.filter(passenger_type='CHILD').count(),
            'infant': passengers.filter(passenger_type='INFANT').count()
        }

        passenger_info = []
        if passenger_count['adult'] > 0:
            passenger_info.append(f"{passenger_count['adult']} Adult(s)")
        if passenger_count['child'] > 0:
            passenger_info.append(f"{passenger_count['child']} Child(ren)")
        if passenger_count['infant'] > 0:
            passenger_info.append(f"{passenger_count['infant']} Infant(s)")

        if passenger_info:
            description += f"\nPassengers: {', '.join(passenger_info)}"

        flight_name = f"Flight Booking - {flying_from} to {flying_to}"
        if flight_no != 'TBD':
            flight_name += f" ({flight_no})"

        main_item = {
            "name": flight_name,
            "description": description,
            "quantity": 1,
            "price": float(flight_booking.base_fare or 0),
            "amount": float(flight_booking.base_fare or 0),
            "gst": float(booking.gst_percentage or 0),
            "tax": float(booking.gst_amount or 0),
            "discount": float(booking.discount or 0),
            "final_total": max(float(flight_booking.base_fare or 0) - float(booking.discount or 0), 0)
        }
        items.append(main_item)

        ancillary_services = flight_booking.ancillary_services.all()
        if ancillary_services.exists():
            service_groups = {}
            for service in ancillary_services:
                service_type = service.service_type
                if service_type not in service_groups:
                    service_groups[service_type] = []
                service_groups[service_type].append(service)

            for service_type, services in service_groups.items():
                total_price = sum(float(s.service_price or 0) for s in services)
                service_count = len(services)

                service_descriptions = []
                for service in services:
                    passenger_name = f"{service.passenger.first_name} {service.passenger.last_name}" if service.passenger else 'Unknown'
                    service_desc = f"{passenger_name}: {service.service_description or service_type}"
                    service_descriptions.append(service_desc)

                service_item = {
                    "name": f"{service_type.title()} Services",
                    "description": "\n".join(service_descriptions),
                    "quantity": service_count,
                    "price": total_price / service_count if service_count > 0 else 0,
                    "amount": total_price,
                    "gst": 0,
                    "tax": 0,
                    "discount": 0,
                    "final_total": total_price
                }
                items.append(service_item)

    return items


def _is_booking_payment_completed(booking) -> bool:
    """Determine whether a booking has been fully paid."""
    if not booking:
        return False

    try:
        final_amount = Decimal(booking.final_amount or 0)
    except (InvalidOperation, TypeError, ValueError):
        final_amount = Decimal('0')

    if final_amount <= 0:
        return False

    try:
        total_paid = Decimal(booking.total_payment_made or 0)
        if total_paid >= final_amount:
            return True
    except (InvalidOperation, TypeError, ValueError):
        total_paid = Decimal('0')

    aggregate_total = booking.booking_payment.filter(
        is_transaction_success=True
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0')

    try:
        aggregate_total = Decimal(aggregate_total)
    except (InvalidOperation, TypeError, ValueError):
        aggregate_total = Decimal('0')

    return aggregate_total >= final_amount

def invoice_json_data(booking, bus_details, company_details, customer_details,
                      invoice_number, invoice_action='create', pay_at_hotel=False):
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
    discount = 0
    notes = ''
    is_same_state = False
    business_state = None
    status = "Pending"
    
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
                item = invoice_json_flight_booking(booking)
                # item is already a list from the enhanced function
                
                # Extract GST information from booking
                gst = float(booking.gst_percentage) if booking.gst_percentage else 0
                gst_type = booking.gst_type if booking.gst_type else (
                    "CGST/SGST" if is_same_state else "IGST"
                )
                subtotal = float(booking.subtotal)
                
            
        total = float(booking.final_amount)
##        description = booking.description + item.get('description')
##        
##        item['price'] = subtotal
##        item['amount'] = subtotal
##        item['description'] = description
        
        notes = booking.additional_notes
        if booking.discount and float(booking.discount) > 0:
            discount = float(booking.discount)
        else:
            discount = 0

        if booking.pro_member_discount_value and float(booking.pro_member_discount_value) > 0:
            pro_member_discount = float(booking.pro_member_discount_value)
        else:
            pro_member_discount = 0

        if pay_at_hotel:
            status = "Pending"
        else:
            status = "Paid" if _is_booking_payment_completed(booking) else "Pending"

    if bus_details:
        billed_mob_num = bus_details.business_phone
        
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
            "invoiceDate": invoice_date.isoformat(), "dueDate": invoice_due_date.isoformat(),
            "notes": notes,
            "billedBy": billed_by, "billedTo": billed_to, "supplyDetails": supply_details,
            "billed_mob_num": billed_mob_num,
            "items": item,
            "GST": gst, "GSTType": gst_type, "total": total, "status": status,
            "discount": discount,
            "pro_member_discount": pro_member_discount,
            "nextScheduleDate": "",
            "tags": [""] })
    elif invoice_action == 'update':
        payload = json.dumps({
            "logo": logo, 
            "notes": notes,
            "billedBy": billed_by, "billedTo": billed_to, "supplyDetails": supply_details,
            "items": item,
            "GST": gst, "GSTType": gst_type, "total": total, "status": status,
            "discount": discount,
            "pro_member_discount": pro_member_discount,
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

def calculate_flight_gst(booking, business_state=None):
    """
    Calculate GST for flight bookings based on business rules
    
    Args:
        booking: Flight booking object
        business_state: State of the business issuing invoice
        
    Returns:
        dict: GST calculation details
    """
    # Flight booking GST is typically 5% for domestic flights
    base_amount = float(booking.subtotal or 0)
    
    if not base_amount or base_amount <= 0:
        return {
            'gst_percentage': 0,
            'gst_amount': 0,
            'gst_type': 'NO_GST'
        }
    
    # Check if GST is applicable based on booking details
    gst_info = getattr(booking, 'gst_info', {}) or {}
    if isinstance(gst_info, str):
        import json
        try:
            gst_info = json.loads(gst_info)
        except json.JSONDecodeError:
            gst_info = {}
    
    # If GST number is provided, it's a business booking - apply GST
    is_business_booking = bool(gst_info.get('gst_number'))
    
    if not is_business_booking:
        return {
            'gst_percentage': 0,
            'gst_amount': 0,
            'gst_type': 'NO_GST'
        }
    
    # 5% GST for domestic flights (business bookings)
    gst_percentage = 5.0
    gst_amount = (base_amount * gst_percentage) / 100
    
    # Determine GST type based on states
    customer_state = gst_info.get('state', '').lower()
    business_state_lower = business_state.lower() if business_state else ''
    
    if customer_state and business_state_lower and customer_state == business_state_lower:
        gst_type = "CGST/SGST"
    else:
        gst_type = "IGST"
    
    return {
        'gst_percentage': gst_percentage,
        'gst_amount': gst_amount,
        'gst_type': gst_type
    }

def manual_generate_invoice_pdf(payload, booking_id=None):
    """
    Backward-compatible wrapper for viewsets that expect manual_generate_invoice_pdf.
    Delegates to generate_invoice_pdf which already normalizes and falls back to
    the manual template when needed. Returns the PDF URL or None.
    """
    return generate_invoice_pdf(payload, booking_id)

def generate_invoice_pdf(payload, booking_id=None):
    """
    Generate a PDF invoice from payload and save to Invoice.invoice_pdf.
    Returns the file URL or None on failure.
    """
    try:
        # Parse payload if string
        if isinstance(payload, str):
            invoice_data = json.loads(payload)
        else:
            invoice_data = payload

        # Normalize keys for templates
        invoice_number = (
            invoice_data.get('invoiceNumber')
            or invoice_data.get('invoice_number')
            or 'unknown'
        )
        invoice_data['invoiceNumber'] = invoice_number
        invoice_data['invoiceDate'] = invoice_data.get('invoiceDate') or invoice_data.get('invoice_date')
        invoice_data['dueDate'] = invoice_data.get('dueDate') or invoice_data.get('due_date')
        invoice_data['billedBy'] = dict(invoice_data.get('billedBy') or invoice_data.get('billed_by_details') or {})
        invoice_data['billedTo'] = dict(invoice_data.get('billedTo') or invoice_data.get('billed_to_details') or {})
        invoice_data['supplyDetails'] = dict(invoice_data.get('supplyDetails') or invoice_data.get('supply_details') or {})
        invoice_data['GSTType'] = invoice_data.get('GSTType') or invoice_data.get('GST_type')
        billed_by_details = invoice_data.get('billedBy', {})
        invoice_data['billed_mob_num'] = billed_by_details.get('mobile_number', '')
        discount = float(invoice_data.get('discount', 0) or 0)
        invoice_data['discount'] = discount

        # Parse dates if present
        for key in ['invoiceDate', 'dueDate']:
            if invoice_data.get(key):
                try:
                    invoice_data[key] = datetime.fromisoformat(str(invoice_data[key]).replace('Z', '+00:00'))
                except Exception:
                    pass

        # Compute amount and tax across items
        amount = 0.0
        tax_amount = 0.0
        for item in invoice_data.get('items', []):
            # rate/price and quantity
            rate = float(item.get('rate', item.get('price', 0) or 0))
            qty = int(item.get('quantity', item.get('qty', 0) or 0))
            # explicit amount fallback
            item_amount = float(item.get('amount', rate * qty))
            # gst/tax
            gst_percent = float(item.get('gst', 0) or 0)
            item_tax = float(item.get('tax', (gst_percent / 100.0) * item_amount))

            amount += item_amount
            tax_amount += item_tax

            # fill back item entries for template
            item.setdefault('price', rate)
            item.setdefault('amount', item_amount)
            item.setdefault('tax', item_tax)

        total_after_discount = amount + tax_amount - discount
        invoice_data['amount'] = amount
        invoice_data['tax_amount'] = tax_amount
        invoice_data['total'] = total_after_discount
        invoice_data['total_in_words'] = number_to_words(total_after_discount)

        # Try primary template; fallback to manual
        try:
            html_content = render_to_string('invoice_template/invoice.html', invoice_data)
        except Exception:
            html_content = render_to_string('invoice_template/manual_invoice.html', invoice_data)

        # wkhtmltopdf options
        options = {
            'page-size': 'A4',
            'margin-top': '5mm',
            'margin-right': '5mm',
            'margin-bottom': '5mm',
            'margin-left': '5mm',
            'encoding': 'UTF-8',
            'no-outline': None,
            'dpi': 300,
            'zoom': 1.0,
            'enable-smart-shrinking': True,
        }

        # Path to wkhtmltopdf from settings, if provided
        config = None
        try:
            wk_cmd = getattr(settings, 'WKHTMLTOPDF_CMD', None)
            if wk_cmd:
                config = pdfkit.configuration(wkhtmltopdf=wk_cmd)
        except Exception:
            config = None

        # Generate PDF
        if config:
            pdf_bytes = pdfkit.from_string(html_content, False, options=options, configuration=config)
        else:
            pdf_bytes = pdfkit.from_string(html_content, False, options=options)
        pdf_file = io.BytesIO(pdf_bytes)

        # Save to Invoice model FileField
        file_name = f"invoice_{invoice_number}.pdf"
        invoice = Invoice.objects.filter(invoice_number=invoice_number).first()
        if not invoice:
            print(f"Invoice not found for number: {invoice_number}")
            return None

        invoice.invoice_pdf.save(file_name, ContentFile(pdf_file.getvalue()))
        invoice.refresh_from_db()

        if invoice.invoice_pdf:
            pdf_url = invoice.invoice_pdf.url
            print(f"Invoice PDF saved successfully. File URL: {pdf_url}")
            return pdf_url
        else:
            print("Failed to save the invoice PDF.")
            return None

    except OSError as e:
        print(f"wkhtmltopdf error: {str(e)}")
        raise
    except Exception as e:
        print(f"Error generating invoice PDF: {str(e)}")
        raise


def number_to_words(n):
    ones = ["", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine"]
    twos = ["Ten", "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen",
            "Sixteen", "Seventeen", "Eighteen", "Nineteen"]
    tens = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"]
    places = ["", "Thousand", "Lakh", "Crore"]

    def two_digit_word(n):
        if n < 10:
            return ones[n]
        elif n < 20:
            return twos[n - 10]
        else:
            return tens[n // 10] + (" " + ones[n % 10] if n % 10 else "")

    def get_words(n):
        if n == 0:
            return "Zero"

        result = ""
        parts = []

        parts.append(n % 1000)  # hundreds
        n //= 1000

        while n > 0:
            parts.append(n % 100)
            n //= 100

        for i in range(len(parts) - 1, -1, -1):
            part = parts[i]
            if part:
                if i == 0:
                    result += (two_digit_word(part % 100) if part < 100 else
                               ones[part // 100] + " Hundred " + two_digit_word(part % 100)) + " "
                else:
                    result += two_digit_word(part) + " " + places[i] + " "

        return result.strip()

    return get_words(int(n)) + " Rupees Only"
