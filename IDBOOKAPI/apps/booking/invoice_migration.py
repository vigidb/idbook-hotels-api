import requests
from datetime import datetime
from django.db import models
from django.db.models import Q
from apps.authentication.models import User

# Assume the models are already imported in your project
from .models import Invoice
from apps.org_managements.models import BusinessDetail

invoice_url = "https://invoice-api.idbookhotels.com"

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
                
                if invoice_data.get("dueDate") and invoice_data.get("dueDate") != "1970-01-01T00:00:00.000Z":
                    due_date = datetime.strptime(invoice_data.get("dueDate"), "%Y-%m-%dT%H:%M:%S.%fZ").date()
            except ValueError as e:
                print(f"Date parsing error for invoice {invoice_number}: {str(e)}")
                failed_count += 1
                continue
                
            # If we get here, the invoice is valid and could be created
            print(f"Invoice {invoice_number} is valid and would be created")
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

def sync_invoices():
    """
    Fetch invoices from API and save to the Invoice table.
    Track count of created and failed invoices.
    """
    print("Starting invoice sync process...")
    
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
    
    # Process each invoice
    for invoice_data in invoices_data:
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
                
                if invoice_data.get("dueDate") and invoice_data.get("dueDate") != "1970-01-01T00:00:00.000Z":
                    due_date = datetime.strptime(invoice_data.get("dueDate"), "%Y-%m-%dT%H:%M:%S.%fZ").date()
            except ValueError as e:
                print(f"Date parsing error for invoice {invoice_number}: {str(e)}")
                failed_count += 1
                continue
            
            # Create new invoice
            invoice = Invoice(
                logo=invoice_data.get("logo", ""),
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
                total=invoice_data.get("total", 0) or 0,
                total_amount=invoice_data.get("totalAmount", 0) or 0,
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
            
        except Exception as e:
            print(f"Failed to create invoice {invoice_data.get('invoiceNumber', 'unknown')}: {str(e)}")
            failed_count += 1
    
    # Print summary
    print("\n===== SYNC SUMMARY =====")
    print(f"Total invoices from API: {total_invoices}")
    print(f"Successfully created: {created_count}")
    print(f"Failed to create: {failed_count}")
    print(f"Skipped (already exist): {skipped_count}")
    print("========================")
    
    return {
        'total': total_invoices,
        'created': created_count,
        'failed': failed_count,
        'skipped': skipped_count
    }

def run_validation():
    """
    Helper function to run validation from the Django shell
    """
    return validate_invoices()

def run_sync():
    """
    Helper function to run actual sync from the Django shell
    """
    return sync_invoices()

# Example usage in Django shell:
# from apps.booking.invoice_migrations import run_validation, run_sync
# run_validation()
# run_sync()