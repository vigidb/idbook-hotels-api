import requests
from datetime import datetime
from django.db import models
from django.db.models import Q
from apps.authentication.models import User
from apps.booking.utils.invoice_utils import number_to_words
from .models import Invoice
from apps.org_managements.models import BusinessDetail
from django.template.loader import render_to_string
from django.core.files.base import ContentFile
import pdfkit
import io
import json


invoice_url = "https://invoice-api.idbookhotels.com"

def migrated_invoice_pdf_generation(payload, invoice_obj=None, booking_id=None):
    """
    Generate a PDF invoice from the new payload format.
    """
    try:
        if isinstance(payload, str):
            invoice_data = json.loads(payload)
        else:
            invoice_data = payload

        # print("invoice_data", invoice_data)

        if invoice_obj is not None:
            if invoice_data.get('logo') and len(invoice_data.get('logo', '')) > 250:
                invoice_data['logo'] = None
                print("Logo URL too long, skipping storage in database")

        # Standardize keys for template rendering
        invoice_data['invoiceNumber'] = invoice_data.get('invoiceNumber', 'unknown')
        invoice_data['invoiceDate'] = invoice_data.get("invoiceDate")
        invoice_data['dueDate'] = invoice_data.get("dueDate")
        invoice_data['billedBy'] = dict(invoice_data.get('billedBy') or {})
        invoice_data['billedTo'] = dict(invoice_data.get('billedTo') or {})
        invoice_data['supplyDetails'] = dict(invoice_data.get('supplyDetails') or {})
        invoice_data['billed_mob_num'] = '+91 98765 43210'
        invoice_data['GSTType'] = invoice_data.get('GSTType')
        invoice_data['status'] = invoice_data.get('status', 'Pending')
        invoice_data['total'] = invoice_data.get('total', 0)
        invoice_data['totalAmount'] = invoice_data.get('totalAmount', 0)
        invoice_data['totalTax'] = invoice_data.get('totalTax', 0)

        discount = float(invoice_data.get('discount') or 0)
        invoice_data['discount'] = discount

        # Amount and tax calculation
        amount = 0
        tax_amount = 0
        for item in invoice_data.get('items', []):
            # if invoice_obj is not None and item.get('description') and len(item.get('description', '')) > 250:
            #     # Keep full description for PDF rendering but mark for database handling
            #     item['description'] = 'length Exceeded' 
            #     print("Item description too long, using placeholder for database")
            # Use price if available, fall back to rate if not
            price = float(item.get('price') or item.get('rate') or 0)
            quantity = int(item.get('quantity') or 0)
            
            # Use existing amount if available, otherwise calculate it
            if item.get('amount') is not None and item['amount'] != 0:
                item_amount = float(item['amount'])
            else:
                item_amount = price * quantity
                item['amount'] = item_amount
                
            item['price'] = price
            
            item_tax = 0
            if item.get('tax') is not None:
                gst = float(item.get('tax') or 0)
                # item_tax = (gst / 100) * item_amount
            
            amount += item_amount
            tax_amount += gst

        if amount > 0:
            invoice_data['amount'] = amount
        else:
            invoice_data['amount'] = invoice_data.get('totalAmount', 0)
            
        invoice_data['tax_amount'] = tax_amount

        total_after_discount = invoice_data['amount'] + tax_amount - discount
        if total_after_discount > 0:
            invoice_data['total'] = total_after_discount
        
        invoice_data['total_in_words'] = number_to_words(invoice_data['total'])

        # print("Data passed to render template:\n", json.dumps(invoice_data, indent=4, default=str))
        html_content = render_to_string('invoice_template/manual_invoice.html', invoice_data)

        # PDF options
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
            'enable-smart-shrinking': True
        }

        pdf_bytes = pdfkit.from_string(html_content, False, options=options)
        pdf_file = io.BytesIO(pdf_bytes)

        file_name = f"migrated_invoice_{invoice_data['invoiceNumber']}_{datetime.now().strftime('%Y_%m_%d_%H%M%S')}.pdf"
        #Get the invoice object - either use the provided one or try to fetch it
        if invoice_obj is None:
            try:
                invoice = Invoice.objects.get(invoice_number=invoice_data['invoiceNumber'])
            except Invoice.DoesNotExist:
                print(f"Error: Invoice with number {invoice_data['invoiceNumber']} not found in database")
                return None
        else:
            invoice = invoice_obj

        # Save the generated PDF to the invoice_pdf field
        invoice.invoice_pdf.save(file_name, ContentFile(pdf_file.getvalue()))

        if invoice.invoice_pdf:
            pdf_url = invoice.invoice_pdf.url

            print(f"Invoice PDF saved successfully. File URL: {pdf_url}")
            return pdf_url
        else:
            print("Failed to save the invoice PDF.")
            return None

    except Exception as e:
        print(f"Error generating invoice PDF: {str(e)}")
        raise

def validate_invoices():
    """
    Fetch invoices from API and validate them without saving to database.
    Return counts of what would be created, failed, or skipped.
    """
    print("Starting invoice validation process...")
    
    # Fetch invoices from API
    url = f"{invoice_url}/api/invoices/"
    try:
        response = requests.get(url)
    except Exception as e:
        print(f"Failed to connect to the API: {str(e)}")
        return {
            'total': 0,
            'would_create': 0,
            'would_fail': 0,
            'would_skip': 0,
            'error': str(e)
        }
    
    if response.status_code != 200:
        print(f"Failed to fetch invoices. Status code: {response.status_code}")
        return {
            'total': 0,
            'would_create': 0,
            'would_fail': 0,
            'would_skip': 0,
            'error': f"API returned status code {response.status_code}"
        }
    
    try:
        response_json = response.json()
    except Exception as e:
        print(f"Failed to parse API response as JSON: {str(e)}")
        return {
            'total': 0,
            'would_create': 0,
            'would_fail': 0,
            'would_skip': 0,
            'error': f"Invalid JSON response: {str(e)}"
        }
    
    if not response_json.get("success") or not isinstance(response_json.get("data"), list):
        print("Invalid or unexpected data format in API response")
        return {
            'total': 0,
            'would_create': 0,
            'would_fail': 0,
            'would_skip': 0,
            'error': "Invalid API response format"
        }
    
    invoices_data = response_json["data"]
    total_invoices = len(invoices_data)
    print(f"Total invoices to process: {total_invoices}")
    
    # Get the business detail for "Idbook hospitality private limited"
    try:
        billed_by = BusinessDetail.objects.get(business_name="Idbook hospitality private limited")
        print(f"Found business details with ID: {billed_by.id}")
    except BusinessDetail.DoesNotExist:
        print("Business 'Idbook hospitality private limited' not found in database")
        return {
            'total': total_invoices,
            'would_create': 0,
            'would_fail': total_invoices,
            'would_skip': 0,
            'error': "Business 'Idbook hospitality private limited' not found"
        }
    except BusinessDetail.MultipleObjectsReturned:
        print("Multiple businesses with name 'Idbook hospitality private limited' found")
        billed_by = BusinessDetail.objects.filter(business_name="Idbook hospitality private limited").first()
        print(f"Using the first one with ID: {billed_by.id}")
    except Exception as e:
        print(f"Error looking up business details: {str(e)}")
        return {
            'total': total_invoices,
            'would_create': 0,
            'would_fail': total_invoices,
            'would_skip': 0,
            'error': f"Error looking up business details: {str(e)}"
        }
    
    created_count = 0
    failed_count = 0
    skipped_count = 0
    
    # Process each invoice
    for invoice_data in invoices_data:
        try:
            # Check if invoice already exists (just the check, no actual DB query)
            invoice_number = invoice_data.get("invoiceNumber")
            if not invoice_number:
                print(f"Missing invoice number in data, would fail...")
                failed_count += 1
                continue
                
            existing_count = Invoice.objects.filter(invoice_number=invoice_number).count()
            
            if existing_count > 0:
                print(f"Invoice {invoice_number} already exists, would skip...")
                skipped_count += 1
                continue
            
            # Validate dates - try to parse them
            try:
                if invoice_data.get("invoiceDate"):
                    invoice_date = datetime.strptime(invoice_data.get("invoiceDate"), "%Y-%m-%dT%H:%M:%S.%fZ").date()
                
                if invoice_data.get("dueDate"):
                    due_date = datetime.strptime(invoice_data.get("dueDate"), "%Y-%m-%dT%H:%M:%S.%fZ").date()
            except ValueError as e:
                print(f"Date parsing error for invoice {invoice_number}: {str(e)}")
                failed_count += 1
                continue
                
            # If we get here, the invoice is valid and could be created
            # print(f"Invoice {invoice_number} is valid and would be created")
            created_count += 1
            
        except Exception as e:
            print(f"Validation failed for invoice {invoice_data.get('invoiceNumber', 'unknown')}: {str(e)}")
            failed_count += 1
    
    # Print summary
    print("\n===== VALIDATION SUMMARY =====")
    print(f"Total invoices from API: {total_invoices}")
    print(f"Would be created: {created_count}")
    print(f"Would fail to create: {failed_count}")
    print(f"Would be skipped (already exist): {skipped_count}")
    print("==============================")
    
    return {
        'total': total_invoices,
        'would_create': created_count,
        'would_fail': failed_count,
        'would_skip': skipped_count
    }

def sync_invoices(limit=None):
    """
    Fetch invoices from API and save to the Invoice table.
    Track count of created and failed invoices.
    """
    print("Starting invoice sync process...")
    if limit is not None:
        print(f"Will process up to {limit} invoices")
    
    # Fetch invoices from API
    url = f"{invoice_url}/api/invoices/"
    try:
        response = requests.get(url)
    except Exception as e:
        print(f"Failed to connect to the API: {str(e)}")
        return {
            'total': 0,
            'created': 0,
            'failed': 0,
            'skipped': 0,
            'error': str(e)
        }
    
    if response.status_code != 200:
        print(f"Failed to fetch invoices. Status code: {response.status_code}")
        return {
            'total': 0,
            'created': 0,
            'failed': 0,
            'skipped': 0,
            'error': f"API returned status code {response.status_code}"
        }
    
    try:
        response_json = response.json()
    except Exception as e:
        print(f"Failed to parse API response as JSON: {str(e)}")
        return {
            'total': 0,
            'created': 0,
            'failed': 0,
            'skipped': 0,
            'error': f"Invalid JSON response: {str(e)}"
        }
    
    if not response_json.get("success") or not isinstance(response_json.get("data"), list):
        print("Invalid or unexpected data format in API response")
        return {
            'total': 0,
            'created': 0,
            'failed': 0,
            'skipped': 0,
            'error': "Invalid API response format"
        }
    
    invoices_data = response_json["data"]
    total_invoices = len(invoices_data)
    print(f"Total invoices to process: {total_invoices}")
    
    # Get the business detail for "Idbook hospitality private limited"
    try:
        billed_by = BusinessDetail.objects.get(business_name="Idbook hospitality private limited")
        print(f"Found business details with ID: {billed_by.id}")
    except BusinessDetail.DoesNotExist:
        print("Business 'Idbook hospitality private limited' not found in database")
        return {
            'total': total_invoices,
            'created': 0,
            'failed': total_invoices,
            'skipped': 0,
            'error': "Business 'Idbook hospitality private limited' not found"
        }
    except BusinessDetail.MultipleObjectsReturned:
        print("Multiple businesses with name 'Idbook hospitality private limited' found")
        billed_by = BusinessDetail.objects.filter(business_name="Idbook hospitality private limited").first()
        print(f"Using the first one with ID: {billed_by.id}")
    except Exception as e:
        print(f"Error looking up business details: {str(e)}")
        return {
            'total': total_invoices,
            'created': 0,
            'failed': total_invoices,
            'skipped': 0,
            'error': f"Error looking up business details: {str(e)}"
        }
    
    created_count = 0
    failed_count = 0
    skipped_count = 0
    processed_count = 0
    
    # Process each invoice
    for invoice_data in invoices_data:
        if limit is not None and (created_count + failed_count) >= limit:
            print(f"Reached the limit of {limit} invoices processed. Stopping sync.")
            break
        try:
            # Check if invoice already exists
            invoice_number = invoice_data.get("invoiceNumber")
            if not invoice_number:
                print(f"Missing invoice number in data, skipping...")
                failed_count += 1
                continue
                
            existing_invoice = Invoice.objects.filter(invoice_number=invoice_number).first()
            
            if existing_invoice:
                print(f"Invoice {invoice_number} already exists, skipping...")
                skipped_count += 1
                continue
            
            # Format dates
            try:
                invoice_date = None
                due_date = None
                
                if invoice_data.get("invoiceDate"):
                    invoice_date = datetime.strptime(invoice_data.get("invoiceDate"), "%Y-%m-%dT%H:%M:%S.%fZ").date()
                
                if invoice_data.get("dueDate"):
                    due_date = datetime.strptime(invoice_data.get("dueDate"), "%Y-%m-%dT%H:%M:%S.%fZ").date()
            except ValueError as e:
                print(f"Date parsing error for invoice {invoice_number}: {str(e)}")
                failed_count += 1
                continue

            if invoice_data.get('logo') and len(invoice_data.get('logo', '')) > 250:
                logo = ''
                print("Logo URL too long, skipping storage in database")
            else:
                logo = invoice_data.get("logo", "")
            
            # Create new invoice
            invoice = Invoice(
                logo=logo,
                header=invoice_data.get("header", ""),
                footer=invoice_data.get("footer", ""),
                invoice_number=invoice_number,
                invoice_date=invoice_date,
                due_date=due_date,
                notes=invoice_data.get("notes", ""),
                
                billed_by=billed_by,
                billed_by_details=invoice_data.get("billedBy", {}),
                billed_to_details=invoice_data.get("billedTo", {}),
                supply_details=invoice_data.get("supplyDetails", {}),
                items=invoice_data.get("items", []),
                
                GST=invoice_data.get("GST", 0) or 0,  # Handle None values
                GST_type=invoice_data.get("GSTType", "CGST/SGST"),
                total=invoice_data.get("totalAmount", 0) or 0,
                total_amount=invoice_data.get("total", 0) or 0,
                total_tax=invoice_data.get("totalTax", 0) or 0,
                
                status=invoice_data.get("status", "Pending"),
                tags=",".join(invoice_data.get("tags", [])) if isinstance(invoice_data.get("tags"), list) else "",
                
                discount=0,
                reference="Other"
            )
            
            # Save the invoice to database
            invoice.save()
            print(f"Successfully created invoice: {invoice_number}")
            created_count += 1

            try:
                pdf_url = migrated_invoice_pdf_generation(invoice_data, invoice_obj=invoice, booking_id=None)
                if pdf_url:
                    print(f"Successfully generated PDF for invoice: {invoice_number}")
                else:
                    print(f"Failed to generate PDF for invoice: {invoice_number}")
            except Exception as pdf_error:
                print(f"Error generating PDF for invoice {invoice_number}: {str(pdf_error)}")
            
        except Exception as e:
            print(f"Failed to create invoice {invoice_data.get('invoiceNumber', 'unknown')}: {str(e)}")
            failed_count += 1

        processed_count += 1
    
    # Print summary
    print("\n===== SYNC SUMMARY =====")
    print(f"Total invoices processed: {processed_count} out of {total_invoices}")
    print(f"Total invoices from API: {total_invoices}")
    print(f"Successfully created: {created_count}")
    print(f"Failed to create: {failed_count}")
    print(f"Skipped (already exist): {skipped_count}")
    print("========================")
    
    return {
        'total': total_invoices,
        'processed': processed_count,
        'created': created_count,
        'failed': failed_count,
        'skipped': skipped_count
    }

def run_validation():
    return validate_invoices()

def run_sync(limit=None):
    return sync_invoices(limit=limit)

# Example usage in Django shell:
# from apps.booking.invoice_migration import run_validation, run_sync
# run_validation()
# run_sync()
# run_sync(limit=3)
