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
from apps.authentication.models import User
from .models import Query, QueryCommunication, Booking, VisaBooking, EventBooking, Invoice, FlightBooking
from apps.booking.utils.coupon_booking_helpers import apply_coupon_to_booking
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from apps.customer.models import Customer
from apps.authentication.utils.authentication_utils import add_group_for_guest_user
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


def _billed_by_details_from_business(business):
    """
    Build billed_by_details dict from BusinessDetail (same shape as invoice_utils / API response).
    """
    if not business:
        return {}
    return {
        "name": getattr(business, "business_name", "") or "",
        "address": getattr(business, "full_address", "") or "",
        "GSTIN": getattr(business, "gstin_no", "") or "",
        "PAN": getattr(business, "pan_no", "") or "",
        "email": getattr(business, "business_email", "") or "",
        "website": getattr(business, "website_url", "") or "",
        "mobile_number": getattr(business, "business_phone", "") or "",
        "hsn_sac_no": getattr(business, "hsn_sac_no", "") or "",
    }


def _build_proforma_payload_from_query(query, business=None):
    """
    Build billed_to_details, supply_details, and invoice items from query (quotation, user,
    query_data) for all query types. Matches structure expected by Invoice model and API
    (same as invoice_utils / booking invoice generation).
    """
    qd = query.query_data or {}
    user = query.raised_by
    company = query.company
    quote = float(query.quote_amount)
    ref = getattr(query, "query_reference", "") or f"Q{query.id}"
    # Billed-to: same keys as invoice_utils (name, address, GSTIN, PAN) for PDF/API
    display_name = ""
    if user:
        display_name = (getattr(user, "name", None) or getattr(user, "get_full_name", lambda: "")() or "").strip()
        if not display_name:
            display_name = (
                (getattr(user, "first_name", "") or "").strip() + " " + (getattr(user, "last_name", "") or "").strip()
            ).strip() or getattr(user, "email", "") or ""
    if company:
        display_name = display_name or (getattr(company, "company_name", "") or "")
    billed_to_details = {
        "name": display_name or "Customer",
        "address": getattr(company, "registered_address", "") or "" if company else "",
        "GSTIN": getattr(company, "gstin_no", "") or "" if company else "",
        "PAN": getattr(company, "pan_no", "") or "" if company else "",
    }
    # Supply details (place/country of supply) from company or default
    supply_details = {"placeOfSupply": "", "countryOfSupply": "INDIA"}
    if company:
        supply_details["placeOfSupply"] = getattr(company, "state", "") or ""
        supply_details["countryOfSupply"] = getattr(company, "country", "") or "INDIA"
    # Type-specific line item: name (title), description, rate, amount, quantity, gst
    qtype = (query.query_type or "").upper()
    if qtype == "HOTEL":
        item_name = f"Hotel - {qd.get('enquired_property', 'Enquiry')}"
        desc = f"Check-in: {qd.get('checkin_time', '-')} | Check-out: {qd.get('checkout_time', '-')} | Ref: {ref}"
    elif qtype == "VISA":
        item_name = f"Visa - {qd.get('destination_country', '')} ({qd.get('visa_type', 'tourist')})"
        desc = f"Travel date: {qd.get('travel_date', '-')} | Ref: {ref}"
    elif qtype == "EVENT":
        item_name = f"Event - {qd.get('event_name', '')}"
        desc = f"{qd.get('event_type', '')} | Date: {qd.get('event_date', '-')} | {qd.get('location', '')} | Ref: {ref}"
    elif qtype == "VEHICLE":
        item_name = f"Vehicle - {qd.get('vehicle_type', 'CAR')}"
        desc = f"{qd.get('pickup_addr', '')} to {qd.get('dropoff_addr', '')} | Ref: {ref}"
    elif qtype == "HOLIDAYPACK":
        item_name = f"Holiday package - {qd.get('enquired_holidaypack', 'Package')}"
        desc = f"{qd.get('no_days', '')} days | From {qd.get('available_start_date', '')} | Ref: {ref}"
    elif qtype == "FLIGHT":
        origin = qd.get("base_origin") or qd.get("flying_from") or qd.get("origin", "")
        dest = qd.get("base_destination") or qd.get("flying_to") or qd.get("destination", "")
        item_name = f"Flight - {origin} to {dest}"
        desc = f"Depart: {qd.get('departure_date') or qd.get('departure', '-')} | Ref: {ref}"
    else:
        item_name = f"{query.query_type or 'Service'} - {ref}"
        desc = f"Ref: {ref}"
    # Items: name, description, quantity, rate, amount, gst (match invoice_utils / API)
    rate_amount = round(quote, 2)
    items = [{
        "name": item_name,
        "description": desc,
        "quantity": 1,
        "rate": rate_amount,
        "price": rate_amount,
        "amount": rate_amount,
        "gst": 0,
    }]
    total_int = int(round(quote))
    total_tax = 0
    return {
        "billed_to_details": billed_to_details,
        "supply_details": supply_details,
        "items": items,
        "total_amount": total_int,
        "total": total_int,
        "total_tax": total_tax,
    }


def _normalize_guest_phone(raw_phone: str) -> str:
    digits = "".join(ch for ch in str(raw_phone or "") if ch.isdigit())
    if len(digits) >= 10:
        return digits[-10:]
    return ""


def _resolve_or_create_guest_user_for_query(query: Query) -> User | None:
    """
    Resolve a user for anonymous query conversion:
    - Try existing user by email (preferred), then by mobile.
    - Else create a lightweight guest/B2C user from query contact.
    """
    qd = query.query_data or {}
    contact = qd.get("contact") or qd.get("contact_person") or {}
    if not isinstance(contact, dict):
        contact = {}

    email = str(contact.get("email") or qd.get("email") or "").strip().lower()
    phone = _normalize_guest_phone(contact.get("phone") or qd.get("phone") or qd.get("mobile_number"))
    name = str(contact.get("name") or qd.get("name") or "Guest User").strip() or "Guest User"

    user = None
    if email:
        user = User.objects.filter(email__iexact=email).first()
    if not user and phone:
        user = User.objects.filter(mobile_number=phone).first()

    if user:
        updates = []
        if not user.name and name:
            user.name = name
            updates.append("name")
        if not user.email and email:
            user.email = email
            updates.append("email")
        if not user.mobile_number and phone:
            user.mobile_number = phone
            updates.append("mobile_number")
        if not user.is_active:
            user.is_active = True
            updates.append("is_active")
        if updates:
            user.save(update_fields=updates + ["updated"])
    else:
        # Fallback for missing email/phone on anonymous query
        if not email:
            email = f"guest.query.{query.id}@idbookhotels.local"
        if not phone:
            phone = f"{(9000000000 + (query.id % 999999999)):010d}"
        user = User.objects.create(
            name=name,
            email=email,
            mobile_number=phone,
            category="B-CUST",
            default_group="B2C-GRP",
            is_active=True,
        )
        add_group_for_guest_user(user)

    if user and not Customer.objects.filter(user=user).exists():
        Customer.objects.create(user=user, active=True)

    return user


class QueryViewSet(viewsets.ModelViewSet, StandardResponseMixin, LoggingMixin):
    """
    Unified ViewSet for all query types
    Standard REST API - minimal custom actions
    """
    queryset = Query.objects.all()
    serializer_class = QuerySerializer
    permission_classes = [AllowAny]  # Public creation
    
    def list(self, request, *args, **kwargs):
        """
        Standard response for query list with pagination support.
        """
        self.log_request(request)
        queryset = self.filter_queryset(self.get_queryset())

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            # Get total count from paginator when paginated
            total_count = 0
            paginator = getattr(self, "paginator", None)
            if paginator is not None:
                # PageNumberPagination exposes .page.paginator.count
                page_obj = getattr(paginator, "page", None)
                if page_obj is not None and hasattr(page_obj, "paginator"):
                    total_count = page_obj.paginator.count
                else:
                    total_count = getattr(paginator, "count", len(serializer.data))
            else:
                total_count = len(serializer.data)

            response = self.get_response(
                data=serializer.data,
                message="Queries fetched successfully",
                status_code=status.HTTP_200_OK,
                status="success",
                count=total_count,
            )
            self.log_response(response)
            return response

        serializer = self.get_serializer(queryset, many=True)
        response = self.get_response(
            data=serializer.data,
            message="Queries fetched successfully",
            status_code=status.HTTP_200_OK,
            status="success",
            count=len(serializer.data),
        )
        self.log_response(response)
        return response
    
    def retrieve(self, request, *args, **kwargs):
        """
        Standard response for single query detail.
        """
        self.log_request(request)
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        response = self.get_response(
            data=serializer.data,
            message="Query retrieved successfully",
            status_code=status.HTTP_200_OK,
            status="success",
            count=1,
        )
        self.log_response(response)
        return response
    
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
        
        # User/role-specific filtering
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
            # Agent users: see queries they raised OR where they are marked as referrer
            elif default_group in (UserGroups.AGENT_GRP, UserGroups.AGENT_ADMIN):
                queryset = queryset.filter(
                    Q(raised_by=user) | Q(referred_by=user)
                )
            else:
                # B2C / other users see only their own
                queryset = queryset.filter(raised_by=user)
        else:
            # Anonymous users can only access their own queries via guest token.
            guest_token = self.request.query_params.get("guest_token")
            if guest_token:
                queryset = queryset.filter(guest_access_token=guest_token)
            else:
                queryset = queryset.none()

        return queryset.order_by("-created")
    
    def create(self, request, *args, **kwargs):
        """Create a new query"""
        self.log_request(request)
        
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            query = serializer.save()

            # For anonymous queries: create/find guest user and issue a token so
            # the guest can view the query without authentication.
            if not request.user.is_authenticated and not query.raised_by:
                guest_user = _resolve_or_create_guest_user_for_query(query)
                if guest_user:
                    query.raised_by = guest_user
                    query.booking_for = query.booking_for or "B2C"
                    if not query.guest_access_token:
                        from apps.booking.utils.booking_utils import (
                            generate_guest_access_token,
                        )

                        query.guest_access_token = generate_guest_access_token(
                            query.id, user=guest_user
                        )
                    query.save(
                        update_fields=[
                            "raised_by",
                            "booking_for",
                            "guest_access_token",
                            "updated",
                        ]
                    )

            # Fire lifecycle notifications for query creation (best-effort)
            try:
                from apps.booking.tasks import (
                    send_query_email_task,
                    send_query_sms_task,
                )

                send_query_email_task.delay(query.id, "QUERY_CREATED")
                send_query_sms_task.delay(query.id, "QUERY_CREATED")
            except Exception:
                pass

            custom_response = self.get_response(
                data=QuerySerializer(query).data,
                message="Query created successfully",
                status_code=status.HTTP_201_CREATED,
                status="success",
                count=1,
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

    def update(self, request, *args, **kwargs):
        """Update a query – return standard response structure."""
        self.log_request(request)
        partial = kwargs.get("partial", False)
        instance = self.get_object()
        old_status = getattr(instance, "status", None)
        requested_status = request.data.get("status")
        if str(requested_status).lower() == "cancelled" and getattr(instance, "booking", None):
            return self.get_error_response(
                message="Booking already created. Query cannot be cancelled.",
                status="error",
                errors=[],
                error_code="QUERY_BOOKING_EXISTS",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        if serializer.is_valid():
            query = serializer.save()

            # Fire lifecycle notifications for query status changes (best-effort).
            # Quote/accept/assign flows update `status` from "pending" -> "quoted" -> "confirmed".
            try:
                new_status = getattr(query, "status", None)
                if old_status and new_status and old_status != new_status:
                    status_to_event = {
                        "quoted": "QUERY_QUOTED",
                        "confirmed": "QUERY_ACCEPTED",
                        "assigned": "QUERY_ASSIGNED",
                        "cancelled": "QUERY_CANCELLED",
                        "completed": "QUERY_COMPLETED",
                    }
                    event_type = status_to_event.get(new_status)
                    if event_type:
                        from apps.booking.tasks import (
                            send_query_email_task,
                            send_query_sms_task,
                        )

                        send_query_email_task.delay(query.id, event_type)
                        send_query_sms_task.delay(query.id, event_type)
            except Exception:
                pass

            custom_response = self.get_response(
                data=QuerySerializer(query).data,
                message="Query updated successfully",
                status_code=status.HTTP_200_OK,
                status="success",
                count=1,
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

    def destroy(self, request, *args, **kwargs):
        """Delete a query – return standard response structure."""
        self.log_request(request)
        instance = self.get_object()
        instance.delete()
        custom_response = self.get_response(
            data=None,
            message="Query deleted successfully",
            status_code=status.HTTP_200_OK,
            status="success",
            count=0,
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
        """
        Create or update proforma invoice for query (admin only).
        Requires quotation (quote_amount) to be set. Uses quotation, user info, and
        query data to generate a proper invoice for all query types (HOTEL, VISA, EVENT,
        VEHICLE, HOLIDAYPACK, FLIGHT).
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
        
        # Quotation is required: proforma is generated from the quote
        if not query.quote_amount or query.quote_amount <= 0:
            return self.get_error_response(
                message="Quotation required. Set quote amount on the query before creating proforma invoice.",
                status="error",
                error_code="QUOTE_REQUIRED",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        
        try:
            with transaction.atomic():
                from apps.org_managements.utils import get_active_business
                business = get_active_business()
                if not business:
                    custom_response = self.get_error_response(
                        message="No active business configured. Set an active BusinessDetail to create proforma invoices.",
                        status="error",
                        error_code="BUSINESS_REQUIRED",
                        status_code=status.HTTP_400_BAD_REQUEST,
                    )
                    self.log_response(custom_response)
                    return custom_response
                payload = _build_proforma_payload_from_query(query)
                billed_to_details = payload["billed_to_details"]
                supply_details = payload["supply_details"]
                items = payload["items"]
                total_amount = payload["total_amount"]
                total = payload["total"]
                total_tax = payload.get("total_tax", 0)
                billed_by_details = _billed_by_details_from_business(business)
                logo = ""
                if getattr(business, "business_logo", None) and business.business_logo:
                    try:
                        logo = business.business_logo.url
                    except Exception:
                        pass
                if query.invoice:
                    # Update existing proforma with current quotation and query data
                    invoice = query.invoice
                    invoice.billed_by = business
                    invoice.billed_by_details = billed_by_details
                    invoice.billed_to_details = billed_to_details
                    invoice.supply_details = supply_details
                    invoice.items = items
                    invoice.total_amount = total_amount
                    invoice.total = total
                    invoice.total_tax = total_tax
                    invoice.GST = 0
                    invoice.GST_type = "IGST"
                    invoice.updated_by = request.user.email if request.user.is_authenticated else ""
                    if query.expires_at:
                        invoice.due_date = query.expires_at.date()
                    invoice.save()
                    message = "Proforma invoice updated successfully"
                else:
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
                        billed_by_details=billed_by_details,
                        billed_to=query.raised_by,
                        billed_to_details=billed_to_details,
                        supply_details=supply_details,
                        items=items,
                        total_amount=total_amount,
                        total=total,
                        total_tax=total_tax,
                        GST=0,
                        GST_type="IGST",
                        status="Pending",
                        source_query=query,
                        created_by=request.user.email if request.user.is_authenticated else "",
                        logo=logo,
                    )
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
        
        query = self.get_object()

        guest_token = request.query_params.get("guest_token")
        is_owner = False
        if request.user and getattr(request.user, "is_authenticated", False):
            is_owner = (
                getattr(query, "raised_by_id", None) is not None
                and int(query.raised_by_id) == int(request.user.id)
            )
        if guest_token and getattr(query, "guest_access_token", None):
            is_owner = str(query.guest_access_token) == str(guest_token)

        if not (is_admin_user(request.user, request) or is_owner):
            return self.get_error_response(
                message="Permission denied",
                status="error",
                error_code="PERMISSION_DENIED",
                status_code=status.HTTP_403_FORBIDDEN,
            )
        
        if str(getattr(query, "status", "")).lower() in ("cancelled", "completed"):
            return self.get_error_response(
                message="Cancelled/completed query cannot be converted to booking",
                status="error",
                error_code="QUERY_NOT_CONVERTIBLE",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        if query.booking:
            # Idempotent conversion: allow updating the already-created booking
            # (mainly for quote changes before payment is made / hold expiry).
            booking = query.booking

            booking_status = str(getattr(booking, "status", "") or "").lower()
            if booking_status in ("confirmed", "completed", "canceled", "no_show"):
                return self.get_error_response(
                    message="Booking already confirmed/completed. Cannot update from query.",
                    status="error",
                    error_code="BOOKING_FINALIZED",
                    status_code=status.HTTP_400_BAD_REQUEST,
                )

            try:
                paid = Decimal(str(getattr(booking, "total_payment_made", 0) or 0))
            except Exception:
                paid = Decimal("0")

            if paid > 0:
                return self.get_error_response(
                    message="Payment already started. Cannot update booking amounts from query.",
                    status="error",
                    error_code="BOOKING_PAYMENT_STARTED",
                    status_code=status.HTTP_400_BAD_REQUEST,
                )

            hold_end_time = getattr(booking, "on_hold_end_time", None)
            if hold_end_time and timezone.now() > hold_end_time:
                return self.get_error_response(
                    message="Hold expired. Cannot update booking from query.",
                    status="error",
                    error_code="HOLD_EXPIRED",
                    status_code=status.HTTP_400_BAD_REQUEST,
                )

            try:
                with transaction.atomic():
                    quote = Decimal(str(query.quote_amount))
                    qd = query.query_data or {}

                    # Update hold/status from quote validity
                    booking.status = "on_hold" if query.expires_at else "pending"
                    booking.on_hold_end_time = (
                        query.expires_at if query.expires_at else None
                    )

                    applied_coupon = False
                    coupon_code = (
                        request.data.get("coupon_code")
                        or getattr(query, "coupon_code", "")
                        or (qd.get("coupon_code") or "")
                    )
                    coupon_code = str(coupon_code).strip() if coupon_code else ""

                    checkin_date = None
                    booking_date = None
                    qtype = str(query.query_type or "")
                    if qtype == "HOLIDAYPACK":
                        asd = qd.get("available_start_date")
                        if asd:
                            from datetime import datetime as dt

                            if isinstance(asd, str):
                                try:
                                    checkin_date = (
                                        dt.strptime(str(asd)[:10], "%Y-%m-%d")
                                    ).date()
                                except ValueError:
                                    pass
                            elif isinstance(asd, dt):
                                checkin_date = asd.date()
                            else:
                                checkin_date = asd
                        booking_date = date.today()

                    if coupon_code:
                        apply_coupon_to_booking(
                            booking,
                            coupon_code,
                            quote,
                            user_id=query.raised_by_id,
                            booking_type=qtype or "HOTEL",
                            checkin_date=checkin_date,
                            booking_date=booking_date,
                        )
                        applied_coupon = True
                    if not applied_coupon:
                        booking.subtotal = quote
                        booking.final_amount = quote

                    # Update min-first-payment (HOLIDAYPACK)
                    q_itinerary = getattr(query, "itinerary_details", None) or {}
                    mp = request.data.get("min_payment_percent")
                    ma = request.data.get("min_payment_amount")
                    if (mp is None or mp == "") and isinstance(q_itinerary, dict):
                        mp = q_itinerary.get("min_payment_percent")
                    if (ma is None or ma == "") and isinstance(q_itinerary, dict):
                        ma = q_itinerary.get("min_payment_amount")

                    update_fields = [
                        "status",
                        "on_hold_end_time",
                        "subtotal",
                        "final_amount",
                        "updated",
                    ]

                    if mp is not None and str(mp).strip() != "":
                        booking.min_payment_percent = Decimal(str(mp))
                        update_fields.append("min_payment_percent")
                    if ma is not None and str(ma).strip() != "":
                        booking.min_payment_amount = Decimal(str(ma))
                        update_fields.append("min_payment_amount")

                    booking.source_query = query
                    update_fields.append("source_query")
                    if getattr(query, "agent_id", None):
                        booking.agent_id = query.agent_id
                        update_fields.append("agent_id")

                    if getattr(query, "guest_access_token", None):
                        booking.guest_access_token = query.guest_access_token
                        update_fields.append("guest_access_token")

                    booking.save(update_fields=list(set(update_fields)))

                    custom_response = self.get_response(
                        data={
                            "query": QuerySerializer(query).data,
                            "booking": BookingSerializer(booking).data,
                        },
                        message="Booking updated from query.",
                        status_code=status.HTTP_200_OK,
                    )
                    self.log_response(custom_response)
                    return custom_response
            except Exception as e:
                return self.get_error_response(
                    message=f"Error updating booking from query: {str(e)}",
                    status="error",
                    error_code="BOOKING_UPDATE_ERROR",
                    status_code=status.HTTP_400_BAD_REQUEST,
                )
        
        if not query.quote_amount or query.quote_amount <= 0:
            return self.get_error_response(
                message="Quote amount must be set before converting to booking",
                status="error",
                error_code="QUOTE_REQUIRED",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        
        try:
            with transaction.atomic():
                if not query.raised_by:
                    guest_user = _resolve_or_create_guest_user_for_query(query)
                    if not guest_user:
                        return self.get_error_response(
                            message="Could not resolve guest user from query contact details",
                            status="error",
                            error_code="USER_REQUIRED",
                            status_code=status.HTTP_400_BAD_REQUEST,
                        )
                    query.raised_by = guest_user
                    query.booking_for = query.booking_for or "B2C"
                    if not query.guest_access_token:
                        from apps.booking.utils.booking_utils import (
                            generate_guest_access_token,
                        )

                        query.guest_access_token = generate_guest_access_token(
                            query.id, user=guest_user
                        )
                    query.save(
                        update_fields=[
                            "raised_by",
                            "booking_for",
                            "guest_access_token",
                            "updated",
                        ]
                    )

                qd = query.query_data or {}
                if query.query_type == "FLIGHT":
                    # Tracking-only flight: create Booking + FlightBooking from query for manual tracking.
                    # No AirIQ call; PNR/confirmation done manually.
                    from apps.booking.utils.booking_source_utils import determine_booking_source
                    from django.utils.dateparse import parse_datetime
                    dep = qd.get("departure_date") or qd.get("departure")
                    ret = qd.get("return_date") or qd.get("return")
                    departure_dt = parse_datetime(str(dep)) if dep else None
                    return_dt = parse_datetime(str(ret)) if ret else None
                    raw_trip = (qd.get("trip_type") or qd.get("flight_trip") or "O")
                    raw_trip = str(raw_trip).upper().strip()
                    if raw_trip in ("R", "ROUND"):
                        flight_trip = "ROUND"
                    else:
                        flight_trip = "ONE-WAY"
                    flight_booking_data = {
                        "flight_no": qd.get("flight_no", "") or "",
                        "airline_code": (qd.get("airline_code") or "")[:3] or "",
                        "flying_from": qd.get("base_origin") or qd.get("flying_from") or qd.get("origin", ""),
                        "flying_to": qd.get("base_destination") or qd.get("flying_to") or qd.get("destination", ""),
                        "flight_trip": flight_trip,
                        "flight_class": qd.get("flight_class", "ECONOMY"),
                        "departure_date": departure_dt,
                        "return_date": return_dt,
                        "status": "INITIATED",
                        "booking_mode": "REALTIME",
                        "booking_reference": "",
                        "selected_flight_data": qd.get("selected_flight_data", {}),
                        "search_session_data": {
                            "from_query": True,
                            "query_id": query.id,
                            "passenger_counts": {
                                "adults": qd.get("adult_count", 1),
                                "children": qd.get("child_count", 0),
                                "infants": qd.get("infant_count", 0),
                            },
                        },
                    }
                    flight_booking = FlightBooking.objects.create(**flight_booking_data)
                    booking_source = getattr(query, "booking_for", None) or determine_booking_source(
                        user=query.raised_by,
                        agent=getattr(query, "agent", None),
                        company_id=query.company_id,
                        request=None,
                    )
                    if booking_source not in ("AGENT", "CORPORATE", "B2C", "GUEST", "DIRECT"):
                        booking_source = "DIRECT"
                    quote = Decimal(str(query.quote_amount))
                    booking = Booking.objects.create(
                        user=query.raised_by,
                        company=query.company,
                        booking_type="FLIGHT",
                        flight_booking=flight_booking,
                        adult_count=qd.get("adult_count", 1),
                        child_count=qd.get("child_count", 0),
                        infant_count=qd.get("infant_count", 0),
                        subtotal=quote,
                        final_amount=quote,
                        status="on_hold" if query.expires_at else "pending",
                        on_hold_end_time=query.expires_at if query.expires_at else None,
                        booking_source=booking_source,
                        source_query=query,
                        agent=query.agent if getattr(query, "agent", None) else None,
                    )
                    if getattr(query, "guest_access_token", None):
                        booking.guest_access_token = query.guest_access_token
                        booking.save(update_fields=["guest_access_token"])
                    query.booking = booking
                    query.status = "completed"
                    query.save()
                    # Notify guest/customer about conversion into booking (best-effort)
                    try:
                        from apps.booking.tasks import (
                            send_query_email_task,
                            send_query_sms_task,
                        )

                        transaction.on_commit(
                            lambda: send_query_email_task.delay(
                                query.id, "QUERY_CONVERTED_TO_BOOKING"
                            )
                        )
                        transaction.on_commit(
                            lambda: send_query_sms_task.delay(
                                query.id, "QUERY_CONVERTED_TO_BOOKING"
                            )
                        )
                        transaction.on_commit(
                            lambda: send_query_email_task.delay(
                                query.id, "QUERY_COMPLETED"
                            )
                        )
                    except Exception:
                        pass
                    if query.invoice and query.invoice.invoice_type == "PROFORMA":
                        proforma = query.invoice
                        last_invoice = Invoice.objects.filter(invoice_type="INVOICE").order_by("-id").first()
                        if last_invoice and last_invoice.invoice_number.startswith("INV-"):
                            try:
                                last_num = int(last_invoice.invoice_number.split("-")[1])
                                invoice_number = f"INV-{last_num + 1:06d}"
                            except (ValueError, IndexError):
                                invoice_number = f"INV-{booking.id:06d}"
                        else:
                            invoice_number = f"INV-{booking.id:06d}"
                        proforma.invoice_number = invoice_number
                        proforma.invoice_type = "INVOICE"
                        proforma.invoice_date = date.today()
                        proforma.status = "Pending"
                        proforma.updated_by = getattr(query.raised_by, "email", "") or ""
                        proforma.save()
                        booking.invoice_id = invoice_number
                        booking.save(update_fields=["invoice_id"])
                    custom_response = self.get_response(
                        data={
                            "query": QuerySerializer(query).data,
                            "booking": BookingSerializer(booking).data,
                        },
                        message="Query converted to booking successfully (manual tracking)",
                        status_code=status.HTTP_201_CREATED,
                    )
                    self.log_response(custom_response)
                    return custom_response
                # Non-flight: use serializer
                # Base booking payload (dict so serializer's request.data.get works)
                # Note: serializer.create() does not set subtotal/final_amount for non-FLIGHT;
                # we set them after save from query.quote_amount.
                booking_data = {
                    "booking_type": query.query_type,
                    "user": query.raised_by.id,
                    "company": query.company_id,
                    "subtotal": float(query.quote_amount),
                    "final_amount": float(query.quote_amount),
                    "status": "on_hold" if query.expires_at else "pending",
                    "on_hold_end_time": query.expires_at if query.expires_at else None,
                    "adult_count": qd.get("adult_count", 1),
                    "child_count": qd.get("child_count", 0),
                    "infant_count": qd.get("infant_count", 0),
                    "child_age_list": qd.get("child_age_list", []),
                }
                
                if query.query_type == "HOTEL":
                    booking_data.update({
                        "room_type": qd.get("room_type", "DELUXE"),
                        "checkin_time": qd.get("checkin_time"),
                        "checkout_time": qd.get("checkout_time"),
                        "bed_count": qd.get("bed_count", 1),
                        "enquired_property": qd.get("enquired_property", ""),
                        "booking_slot": qd.get("booking_slot", "24 HOURS"),
                        "requested_room_no": qd.get("requested_room_no", 1),
                    })
                elif query.query_type == "HOLIDAYPACK":
                    booking_data.update({
                        "enquired_holidaypack": qd.get("enquired_holidaypack", ""),
                        "no_days": qd.get("no_days", 0),
                        "available_start_date": qd.get("available_start_date"),
                    })
                elif query.query_type == "VEHICLE":
                    booking_data.update({
                        "pickup_addr": qd.get("pickup_addr", ""),
                        "dropoff_addr": qd.get("dropoff_addr", ""),
                        "pickup_time": qd.get("pickup_time"),
                        "vehicle_type": qd.get("vehicle_type", "CAR"),
                    })
                elif query.query_type == "VISA":
                    booking_data.update({
                        "destination_country": qd.get("destination_country", ""),
                        "travel_date": qd.get("travel_date"),
                        "visa_type": qd.get("visa_type", "tourist"),
                        "passport_number": qd.get("passport_number", ""),
                        "passport_expiry": qd.get("passport_expiry"),
                        "travel_purpose": qd.get("travel_purpose", ""),
                        "documents_uploaded": qd.get("documents_uploaded", {}),
                        "special_requirements": qd.get("special_requirements", ""),
                        "itinerary_details": qd.get("itinerary_details") or getattr(query, "itinerary_details", None) or {},
                        "admin_notes": (getattr(query, "admin_notes", None) or "") or qd.get("admin_notes", ""),
                        "status": "pending",
                    })
                elif query.query_type == "EVENT":
                    booking_data.update({
                        "event_name": qd.get("event_name", ""),
                        "event_type": qd.get("event_type", "other"),
                        "event_date": qd.get("event_date"),
                        "event_end_date": qd.get("event_end_date"),
                        "location": qd.get("location", ""),
                        "attendee_count": qd.get("attendee_count", 1),
                        "budget_range": qd.get("budget_range"),
                        "special_requirements": qd.get("special_requirements", ""),
                        "itinerary_details": qd.get("itinerary_details") or getattr(query, "itinerary_details", None) or {},
                        "admin_notes": (getattr(query, "admin_notes", None) or "") or qd.get("admin_notes", ""),
                        "status": "pending",
                    })
                
                # Request adapter: BookingSerializer.create() uses context["request"].user, .data, and .META
                # (e.g. get_user_active_group reads request.META). Override user and data; delegate rest to real request.
                class _RequestAdapter:
                    def __init__(self, real_request, user_override, data_override):
                        self._request = real_request
                        self.user = user_override
                        self._data = data_override
                    @property
                    def data(self):
                        return self._data
                    def __getattr__(self, name):
                        return getattr(self._request, name)
                context_request = _RequestAdapter(request, query.raised_by, booking_data)
                
                booking_serializer = BookingSerializer(
                    data=booking_data,
                    context={"request": context_request},
                )
                
                if booking_serializer.is_valid():
                    booking = booking_serializer.save()
                    quote = Decimal(str(query.quote_amount))
                    coupon_code = (
                        request.data.get("coupon_code")
                        or getattr(query, "coupon_code", "")
                        or (qd.get("coupon_code") or "")
                    )
                    coupon_code = str(coupon_code).strip() if coupon_code else ""
                    checkin_date = None
                    booking_date = None
                    qtype = str(query.query_type or "")
                    if qtype == "HOLIDAYPACK":
                        asd = qd.get("available_start_date")
                        if asd:
                            from datetime import datetime as dt

                            if isinstance(asd, str):
                                try:
                                    checkin_date = dt.strptime(str(asd)[:10], "%Y-%m-%d").date()
                                except ValueError:
                                    pass
                            elif isinstance(asd, dt):
                                checkin_date = asd.date()
                            else:
                                checkin_date = asd
                        booking_date = date.today()
                    applied_coupon = False
                    if coupon_code:
                        try:
                            apply_coupon_to_booking(
                                booking,
                                coupon_code,
                                quote,
                                user_id=query.raised_by_id,
                                booking_type=qtype or "HOTEL",
                                checkin_date=checkin_date,
                                booking_date=booking_date,
                            )
                            applied_coupon = True
                        except ValueError as exc:
                            custom_response = self.get_error_response(
                                message=str(exc),
                                status="error",
                                errors=[],
                                error_code="COUPON_ERROR",
                                status_code=status.HTTP_400_BAD_REQUEST,
                            )
                            self.log_response(custom_response)
                            return custom_response
                    if not applied_coupon:
                        booking.subtotal = quote
                        booking.final_amount = quote
                    # Minimum-first-payment settings can come from:
                    # 1) convert-to-booking request payload, or
                    # 2) stored holiday quote details (query.itinerary_details)
                    q_itinerary = getattr(query, "itinerary_details", None) or {}
                    mp = request.data.get("min_payment_percent")
                    ma = request.data.get("min_payment_amount")

                    if (mp is None or mp == "") and isinstance(q_itinerary, dict):
                        mp = q_itinerary.get("min_payment_percent")
                    if (ma is None or ma == "") and isinstance(q_itinerary, dict):
                        ma = q_itinerary.get("min_payment_amount")

                    if mp is not None and str(mp).strip() != "":
                        booking.min_payment_percent = Decimal(str(mp))
                    if ma is not None and str(ma).strip() != "":
                        booking.min_payment_amount = Decimal(str(ma))
                    # Link query <-> booking and preserve query context
                    booking.source_query = query
                    if getattr(query, "agent_id", None):
                        booking.agent_id = query.agent_id
                    booking_for = getattr(query, "booking_for", None)
                    if booking_for and str(booking_for).upper() in (
                        "AGENT",
                        "CORPORATE",
                        "B2C",
                        "GUEST",
                    ):
                        booking.booking_source = str(booking_for).upper()
                    update_fields = ["source_query", "subtotal", "final_amount", "updated"]
                    if applied_coupon:
                        update_fields.extend(
                            [
                                "discount",
                                "total_discount",
                                "coupon",
                                "coupon_code",
                            ]
                        )
                    if getattr(query, "agent_id", None):
                        update_fields.append("agent_id")
                    if booking_for and str(booking_for).upper() in (
                        "AGENT",
                        "CORPORATE",
                        "B2C",
                        "GUEST",
                    ):
                        update_fields.append("booking_source")
                    if mp is not None and str(mp).strip() != "":
                        update_fields.append("min_payment_percent")
                    if ma is not None and str(ma).strip() != "":
                        update_fields.append("min_payment_amount")
                    booking.save(update_fields=update_fields)
                    if getattr(query, "guest_access_token", None):
                        booking.guest_access_token = query.guest_access_token
                        booking.save(update_fields=["guest_access_token"])
                    query.booking = booking
                    query.status = "completed"
                    query.save()
                    # Notify guest/customer about conversion into booking (best-effort)
                    try:
                        from apps.booking.tasks import (
                            send_query_email_task,
                            send_query_sms_task,
                        )

                        transaction.on_commit(
                            lambda: send_query_email_task.delay(
                                query.id, "QUERY_CONVERTED_TO_BOOKING"
                            )
                        )
                        transaction.on_commit(
                            lambda: send_query_sms_task.delay(
                                query.id, "QUERY_CONVERTED_TO_BOOKING"
                            )
                        )
                        transaction.on_commit(
                            lambda: send_query_email_task.delay(
                                query.id, "QUERY_COMPLETED"
                            )
                        )
                    except Exception:
                        pass
                    
                    # Convert proforma invoice to final invoice if exists
                    if query.invoice and query.invoice.invoice_type == "PROFORMA":
                        proforma = query.invoice
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
                        proforma.invoice_number = invoice_number
                        proforma.invoice_type = "INVOICE"
                        proforma.invoice_date = date.today()
                        proforma.status = "Pending"
                        proforma.updated_by = getattr(query.raised_by, "email", "") or ""
                        proforma.save()
                        booking.invoice_id = invoice_number
                        booking.save(update_fields=["invoice_id"])
                    
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
                    
        except Exception as e:
            custom_response = self.get_error_response(
                message=f"Error converting query to booking: {str(e)}",
                status="error",
                error_code="CONVERSION_ERROR",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        
        self.log_response(custom_response)
        return custom_response

    @action(
        detail=True,
        methods=["patch"],
        url_path="assign-business-user",
        permission_classes=[IsAuthenticated],
    )
    @swagger_auto_schema(
        operation_summary="Assign query to BUSINESS-GRP user",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=["assigned_to_user_id"],
            properties={
                "assigned_to_user_id": openapi.Schema(type=openapi.TYPE_INTEGER),
            },
        ),
        responses={200: "Query assigned", 400: "Validation error", 403: "Permission denied", 404: "User not found"},
    )
    def assign_business_user(self, request, pk=None):
        """Manual assignment of query to a BUSINESS-GRP user."""
        self.log_request(request)

        if not is_admin_user(request.user, request):
            custom_response = self.get_error_response(
                message="Admin access required",
                status="error",
                error_code="PERMISSION_DENIED",
                status_code=status.HTTP_403_FORBIDDEN,
            )
            self.log_response(custom_response)
            return custom_response

        query = self.get_object()
        assigned_to_user_id = request.data.get("assigned_to_user_id")
        if not assigned_to_user_id:
            custom_response = self.get_error_response(
                message="assigned_to_user_id is required",
                status="error",
                error_code="VALIDATION_ERROR",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
            self.log_response(custom_response)
            return custom_response

        try:
            assigned_user = User.objects.get(
                id=int(assigned_to_user_id), is_active=True
            )
        except (ValueError, TypeError, User.DoesNotExist):
            custom_response = self.get_error_response(
                message="Assigned user not found",
                status="error",
                error_code="NOT_FOUND",
                status_code=status.HTTP_404_NOT_FOUND,
            )
            self.log_response(custom_response)
            return custom_response

        if assigned_user.default_group != UserGroups.BUSINESS_GRP:
            custom_response = self.get_error_response(
                message="Assigned user must belong to BUSINESS-GRP",
                status="error",
                error_code="VALIDATION_ERROR",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
            self.log_response(custom_response)
            return custom_response

        query.referred_by = assigned_user
        query.referral_type = "EMPLOYEE"
        query.status = "assigned"
        query.save(update_fields=["referred_by", "referral_type", "status", "updated"])

        # Best-effort notifications for assignment
        try:
            from apps.booking.tasks import send_query_email_task, send_query_sms_task

            send_query_email_task.delay(query.id, "QUERY_ASSIGNED")
            send_query_sms_task.delay(query.id, "QUERY_ASSIGNED")
        except Exception:
            pass

        custom_response = self.get_response(
            data={
                "query": QuerySerializer(query).data,
                "assigned_to": {
                    "id": assigned_user.id,
                    "name": assigned_user.name,
                    "email": assigned_user.email,
                },
            },
            message="Query assigned successfully",
            status_code=status.HTTP_200_OK,
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
