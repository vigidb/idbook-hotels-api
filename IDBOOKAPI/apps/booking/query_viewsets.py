"""
Unified Query ViewSet for all service types
Standard REST API with minimal custom actions
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from decimal import Decimal
from datetime import date

from IDBOOKAPI.mixins import StandardResponseMixin, LoggingMixin
from apps.authentication.constants import UserGroups, CORPORATE_GROUPS, B2C_GROUPS
from apps.authentication.utils.token_utils import get_user_active_group
from .models import Query, QueryCommunication, Booking, VisaBooking, EventBooking, Invoice
from .serializers import (
    QuerySerializer, 
    QueryCommunicationSerializer, 
    BookingSerializer,
    VisaBookingSerializer,
    EventBookingSerializer,
    InvoiceSerializer,
)


def is_admin_user(user, request):
    """Check if user is admin"""
    if not user.is_authenticated:
        return False
    active_group = get_user_active_group(user, request)
    default_group = active_group or user.default_group
    return default_group in [UserGroups.BUSINESS_GRP, UserGroups.BUS_ADMIN]


class QueryViewSet(viewsets.ModelViewSet, StandardResponseMixin, LoggingMixin):
    """
    Unified ViewSet for all query types
    Standard REST API - minimal custom actions
    """
    queryset = Query.objects.all()
    serializer_class = QuerySerializer
    permission_classes = [AllowAny]  # Public creation
    
    def get_queryset(self):
        """Filter based on user type and query params"""
        queryset = Query.objects.filter(active=True)
        user = self.request.user
        
        # Filter by query type
        query_type = self.request.query_params.get("query_type")
        if query_type:
            queryset = queryset.filter(query_type=query_type)
        
        # Filter by company
        company_id = self.request.query_params.get("company_id")
        if company_id:
            queryset = queryset.filter(company_id=company_id)
        
        # Filter by status
        status_filter = self.request.query_params.get("status")
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        # Filter by booking_for
        booking_for = self.request.query_params.get("booking_for")
        if booking_for:
            queryset = queryset.filter(booking_for=booking_for)
        
        # Filter by raised_by
        raised_by = self.request.query_params.get("raised_by")
        if raised_by:
            queryset = queryset.filter(raised_by_id=raised_by)
        
        # Filter by referred_by
        referred_by = self.request.query_params.get("referred_by")
        if referred_by:
            queryset = queryset.filter(referred_by_id=referred_by)
        
        # User-specific filtering
        if user.is_authenticated:
            active_group = get_user_active_group(user, self.request)
            default_group = active_group or user.default_group
            
            # Admin sees all
            if is_admin_user(user, self.request):
                return queryset.order_by("-created")
            
            # Corporate users see company queries and their own
            if default_group in CORPORATE_GROUPS:
                queryset = queryset.filter(
                    Q(raised_by=user) | Q(company_id=user.company_id)
                )
            else:
                # B2C users see only their own
                queryset = queryset.filter(raised_by=user)
        
        return queryset.order_by("-created")
    
    def create(self, request, *args, **kwargs):
        """Create a new query"""
        self.log_request(request)
        
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            query = serializer.save()
            custom_response = self.get_response(
                data=QuerySerializer(query).data,
                message="Query created successfully",
                status_code=status.HTTP_201_CREATED,
            )
        else:
            custom_response = self.get_error_response(
                message="Validation Error",
                status="error",
                errors=serializer.errors,
                error_code="VALIDATION_ERROR",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        
        self.log_response(custom_response)
        return custom_response
    
    @action(detail=True, methods=["post"], url_path="add-communication")
    def add_communication(self, request, pk=None):
        """Add communication note/history"""
        self.log_request(request)
        
        query = self.get_object()
        serializer = QueryCommunicationSerializer(
            data=request.data,
            context={"request": request}
        )
        
        if serializer.is_valid():
            comm = serializer.save(query=query, user=request.user if request.user.is_authenticated else None)
            custom_response = self.get_response(
                data=QueryCommunicationSerializer(comm).data,
                message="Communication added successfully",
                status_code=status.HTTP_201_CREATED,
            )
        else:
            custom_response = self.get_error_response(
                message="Validation Error",
                status="error",
                errors=serializer.errors,
                error_code="VALIDATION_ERROR",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        
        self.log_response(custom_response)
        return custom_response
    
    @action(detail=True, methods=["post"], url_path="create-proforma-invoice")
    def create_proforma_invoice(self, request, pk=None):
        """Create or update proforma invoice for query (admin only)"""
        self.log_request(request)
        
        if not is_admin_user(request.user, request):
            return self.get_error_response(
                message="Admin access required",
                status="error",
                error_code="PERMISSION_DENIED",
                status_code=status.HTTP_403_FORBIDDEN,
            )
        
        query = self.get_object()
        
        if not query.quote_amount or query.quote_amount <= 0:
            return self.get_error_response(
                message="Quote amount must be set before creating proforma invoice",
                status="error",
                error_code="QUOTE_REQUIRED",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        
        try:
            with transaction.atomic():
                # Get or create proforma invoice
                if query.invoice:
                    # Update existing proforma
                    invoice = query.invoice
                    invoice.total_amount = int(query.quote_amount)
                    invoice.total = int(query.quote_amount)
                    invoice.updated_by = request.user.email if request.user.is_authenticated else ""
                    invoice.save()
                    message = "Proforma invoice updated successfully"
                else:
                    # Create new proforma invoice
                    from apps.org_managements.models import BusinessDetail
                    business = BusinessDetail.objects.first()  # Get default business
                    
                    # Generate proforma invoice number
                    last_proforma = Invoice.objects.filter(
                        invoice_type="PROFORMA"
                    ).order_by("-id").first()
                    
                    if last_proforma and last_proforma.invoice_number.startswith("PI-"):
                        try:
                            last_num = int(last_proforma.invoice_number.split("-")[1])
                            proforma_number = f"PI-{last_num + 1:06d}"
                        except (ValueError, IndexError):
                            proforma_number = f"PI-{query.id:06d}"
                    else:
                        proforma_number = f"PI-{query.id:06d}"
                    
                    invoice = Invoice.objects.create(
                        invoice_number=proforma_number,
                        invoice_type="PROFORMA",
                        invoice_date=date.today(),
                        due_date=query.expires_at.date() if query.expires_at else None,
                        billed_by=business,
                        billed_to=query.raised_by,
                        billed_to_details={
                            "name": query.raised_by.name if query.raised_by else "",
                            "email": query.raised_by.email if query.raised_by else "",
                            "company": query.company.company_name if query.company else "",
                        },
                        items=[{
                            "description": f"{query.query_type} - {query.query_reference}",
                            "quantity": 1,
                            "unit_price": float(query.quote_amount),
                            "total": float(query.quote_amount),
                        }],
                        total_amount=int(query.quote_amount),
                        total=int(query.quote_amount),
                        status="Pending",
                        source_query=query,
                        created_by=request.user.email if request.user.is_authenticated else "",
                    )
                    
                    # Link invoice to query
                    query.invoice = invoice
                    query.save()
                    message = "Proforma invoice created successfully"
                
                custom_response = self.get_response(
                    data={
                        "query": QuerySerializer(query).data,
                        "invoice": InvoiceSerializer(invoice).data,
                    },
                    message=message,
                    status_code=status.HTTP_201_CREATED,
                )
        except Exception as e:
            custom_response = self.get_error_response(
                message=f"Error creating proforma invoice: {str(e)}",
                status="error",
                error_code="INVOICE_ERROR",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        
        self.log_response(custom_response)
        return custom_response
    
    @action(detail=True, methods=["post"], url_path="upload-document")
    def upload_document(self, request, pk=None):
        """
        Upload document to query's invoice (admin only)
        
        Request body:
        - document_type: proforma_pdf, invoice_pdf, receipt_pdf, credit_note_pdf, voucher_pdf, other
        - file: The file to upload (multipart form data)
        - name: (optional) Document name for 'other' type
        """
        self.log_request(request)
        
        if not is_admin_user(request.user, request):
            return self.get_error_response(
                message="Admin access required",
                status="error",
                error_code="PERMISSION_DENIED",
                status_code=status.HTTP_403_FORBIDDEN,
            )
        
        query = self.get_object()
        
        if not query.invoice:
            return self.get_error_response(
                message="No invoice exists for this query. Create proforma invoice first.",
                status="error",
                error_code="NO_INVOICE",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        
        document_type = request.data.get("document_type")
        file = request.FILES.get("file")
        
        if not document_type:
            return self.get_error_response(
                message="document_type is required (proforma_pdf, invoice_pdf, receipt_pdf, credit_note_pdf, voucher_pdf, other)",
                status="error",
                error_code="MISSING_DOCUMENT_TYPE",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        
        if not file:
            return self.get_error_response(
                message="file is required",
                status="error",
                error_code="MISSING_FILE",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        
        valid_types = ["proforma_pdf", "invoice_pdf", "receipt_pdf", "credit_note_pdf", "voucher_pdf", "other"]
        if document_type not in valid_types:
            return self.get_error_response(
                message=f"Invalid document_type. Must be one of: {', '.join(valid_types)}",
                status="error",
                error_code="INVALID_DOCUMENT_TYPE",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        
        try:
            invoice = query.invoice
            
            if document_type == "other":
                # Add to other_documents list
                doc_name = request.data.get("name", file.name)
                
                # Save file manually
                from django.core.files.storage import default_storage
                from django.utils import timezone
                
                file_path = f"booking/invoices/other/{invoice.id}/{file.name}"
                saved_path = default_storage.save(file_path, file)
                file_url = default_storage.url(saved_path)
                
                other_docs = invoice.other_documents or []
                other_docs.append({
                    "name": doc_name,
                    "url": file_url,
                    "type": file.content_type,
                    "uploaded_at": timezone.now().isoformat(),
                    "uploaded_by": request.user.email if request.user.is_authenticated else "",
                })
                invoice.other_documents = other_docs
                invoice.save()
                message = f"Document '{doc_name}' uploaded successfully"
            else:
                # Set the appropriate file field
                setattr(invoice, document_type, file)
                invoice.save()
                message = f"{document_type.replace('_', ' ').title()} uploaded successfully"
            
            custom_response = self.get_response(
                data={
                    "query": QuerySerializer(query).data,
                    "invoice": InvoiceSerializer(invoice).data,
                },
                message=message,
                status_code=status.HTTP_200_OK,
            )
        except Exception as e:
            custom_response = self.get_error_response(
                message=f"Error uploading document: {str(e)}",
                status="error",
                error_code="UPLOAD_ERROR",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        
        self.log_response(custom_response)
        return custom_response
    
    @action(detail=True, methods=["post"], url_path="convert-to-booking")
    def convert_to_booking(self, request, pk=None):
        """Convert query to booking (admin only)"""
        self.log_request(request)
        
        if not is_admin_user(request.user, request):
            return self.get_error_response(
                message="Admin access required",
                status="error",
                error_code="PERMISSION_DENIED",
                status_code=status.HTTP_403_FORBIDDEN,
            )
        
        query = self.get_object()
        
        if query.booking:
            return self.get_error_response(
                message="Query already converted to booking",
                status="error",
                error_code="ALREADY_CONVERTED",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        
        if not query.quote_amount or query.quote_amount <= 0:
            return self.get_error_response(
                message="Quote amount must be set before converting to booking",
                status="error",
                error_code="QUOTE_REQUIRED",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        
        if not query.raised_by:
            return self.get_error_response(
                message="Query must have a user (raised_by) to convert to booking",
                status="error",
                error_code="USER_REQUIRED",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        
        try:
            with transaction.atomic():
                # Create booking from query
                booking_data = {
                    "booking_type": query.query_type,
                    "user": query.raised_by.id,
                    "company": query.company.id if query.company else None,
                    "subtotal": float(query.quote_amount),
                    "final_amount": float(query.quote_amount),
                    "status": "pending",
                    "source_query": query.id,
                    "adult_count": query.query_data.get("adult_count", 1),
                    "child_count": query.query_data.get("child_count", 0),
                    "infant_count": query.query_data.get("infant_count", 0),
                }
                
                # Add service-specific data based on query_type
                # Merge query_data into booking_data for serializer
                if query.query_type == "VISA":
                    booking_data.update({
                        "destination_country": query.query_data.get("destination_country", ""),
                        "travel_date": query.query_data.get("travel_date"),
                        "visa_type": query.query_data.get("visa_type", "tourist"),
                        "passport_number": query.query_data.get("passport_number", ""),
                        "travel_purpose": query.query_data.get("travel_purpose", ""),
                    })
                
                elif query.query_type == "EVENT":
                    booking_data.update({
                        "event_name": query.query_data.get("event_name", ""),
                        "event_type": query.query_data.get("event_type", "other"),
                        "event_date": query.query_data.get("event_date"),
                        "location": query.query_data.get("location", ""),
                        "attendee_count": query.query_data.get("attendee_count", 1),
                    })
                
                # Create a mutable copy of request.data with merged booking_data
                from django.http import QueryDict
                merged_data = QueryDict(mutable=True)
                merged_data.update(booking_data)
                
                # Temporarily set request.user to query.raised_by and update request.data
                original_user = request.user
                original_data = request._full_data if hasattr(request, '_full_data') else request.data
                request.user = query.raised_by
                request.data = merged_data
                
                try:
                    booking_serializer = BookingSerializer(
                        data=merged_data,
                        context={"request": request}
                    )
                    
                    if booking_serializer.is_valid():
                        booking = booking_serializer.save()
                        
                        # Link query to booking
                        query.booking = booking
                        query.status = "confirmed"
                        query.save()
                        
                        # Convert proforma invoice to final invoice if exists
                        if query.invoice and query.invoice.invoice_type == "PROFORMA":
                            proforma = query.invoice
                            
                            # Generate final invoice number
                            last_invoice = Invoice.objects.filter(
                                invoice_type="INVOICE"
                            ).order_by("-id").first()
                            
                            if last_invoice and last_invoice.invoice_number.startswith("INV-"):
                                try:
                                    last_num = int(last_invoice.invoice_number.split("-")[1])
                                    invoice_number = f"INV-{last_num + 1:06d}"
                                except (ValueError, IndexError):
                                    invoice_number = f"INV-{booking.id:06d}"
                            else:
                                invoice_number = f"INV-{booking.id:06d}"
                            
                            # Update proforma to final invoice
                            proforma.invoice_number = invoice_number
                            proforma.invoice_type = "INVOICE"
                            proforma.invoice_date = date.today()
                            proforma.status = "Pending"  # Pending payment
                            proforma.updated_by = request.user.email if request.user.is_authenticated else ""
                            proforma.save()
                            
                            # Link invoice to booking
                            booking.invoice_id = invoice_number
                            booking.save()
                        
                        custom_response = self.get_response(
                            data={
                                "query": QuerySerializer(query).data,
                                "booking": BookingSerializer(booking).data,
                            },
                            message="Query converted to booking successfully",
                            status_code=status.HTTP_201_CREATED,
                        )
                    else:
                        custom_response = self.get_error_response(
                            message="Error creating booking",
                            status="error",
                            errors=booking_serializer.errors,
                            error_code="BOOKING_CREATION_ERROR",
                            status_code=status.HTTP_400_BAD_REQUEST,
                        )
                finally:
                    # Restore original user and data
                    request.user = original_user
                    if hasattr(request, '_full_data'):
                        request._full_data = original_data
                    else:
                        request.data = original_data
                    
        except Exception as e:
            custom_response = self.get_error_response(
                message=f"Error converting query to booking: {str(e)}",
                status="error",
                error_code="CONVERSION_ERROR",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        
        self.log_response(custom_response)
        return custom_response


# Keep VisaBookingViewSet and EventBookingViewSet for admin management
class VisaBookingViewSet(viewsets.ModelViewSet, StandardResponseMixin, LoggingMixin):
    """Admin ViewSet for VisaBooking management"""
    queryset = VisaBooking.objects.all()
    serializer_class = VisaBookingSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Filter by company if provided"""
        queryset = VisaBooking.objects.all()
        company_id = self.request.query_params.get("company_id")
        if company_id:
            queryset = queryset.filter(booking__company_id=company_id)
        return queryset.order_by("-created")
    
    def list(self, request, *args, **kwargs):
        if not is_admin_user(request.user, request):
            return self.get_error_response(
                message="Admin access required",
                error_code="PERMISSION_DENIED",
                status_code=status.HTTP_403_FORBIDDEN,
            )
        return super().list(request, *args, **kwargs)


class EventBookingViewSet(viewsets.ModelViewSet, StandardResponseMixin, LoggingMixin):
    """Admin ViewSet for EventBooking management"""
    queryset = EventBooking.objects.all()
    serializer_class = EventBookingSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Filter by company if provided"""
        queryset = EventBooking.objects.all()
        company_id = self.request.query_params.get("company_id")
        if company_id:
            queryset = queryset.filter(booking__company_id=company_id)
        return queryset.order_by("-created")
    
    def list(self, request, *args, **kwargs):
        if not is_admin_user(request.user, request):
            return self.get_error_response(
                message="Admin access required",
                error_code="PERMISSION_DENIED",
                status_code=status.HTTP_403_FORBIDDEN,
            )
        return super().list(request, *args, **kwargs)
