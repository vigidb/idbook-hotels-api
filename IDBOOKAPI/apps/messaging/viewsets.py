import re
from django.core.validators import EmailValidator
from django.db import transaction
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from IDBOOKAPI.mixins import StandardResponseMixin, LoggingMixin
from IDBOOKAPI.utils import paginate_queryset
from apps.authentication.constants import ALL_GROUP_CHOICES, UserGroups
from apps.messaging.models import (
    Contact,
    ContactUploadSession,
    Campaign,
    CampaignStep,
    CampaignContact,
    MessageLog,
    EmailTemplate,
)
from apps.messaging.serializers import (
    ContactSerializer,
    ContactUploadSessionSerializer,
    CampaignSerializer,
    CampaignCreateUpdateSerializer,
    CampaignStepSerializer,
    CampaignContactSerializer,
    MessageLogSerializer,
    EmailTemplateSerializer,
)
from apps.messaging.services import (
    get_template_variable_definitions,
    normalize_phone,
    upsert_contact_from_row,
)
from apps.messaging.tasks import enqueue_campaign_contacts_task, send_campaign_batch_task


class ContactViewSet(viewsets.ModelViewSet, StandardResponseMixin, LoggingMixin):
    """
    Step 1: Contacts & Segmentation

    Use these endpoints to create, list, and bulk upload contacts which will be
    targeted by campaigns.
    """

    queryset = Contact.objects.all().order_by("-created_at")
    serializer_class = ContactSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "post", "put", "patch", "delete"]
    swagger_tags = ["1. Contacts & Segmentation"]

    # Pagination uses query params: offset, limit (see IDBOOKAPI.utils.paginate_queryset)
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = [
        "group_type",
        "city",
        "country",
        "department",
        "is_blacklisted",
        "opt_out_sms",
        "opt_out_email",
        "opt_out_whatsapp",
    ]
    search_fields = ["name", "phone", "email", "city", "country"]
    ordering_fields = [
        "created_at",
        "updated_at",
        "name",
        "email",
        "phone",
        "city",
        "country",
    ]
    ordering = ["-created_at"]

    def create(self, request, *args, **kwargs):
        self.log_request(request)
        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            custom = self.get_error_response(
                message="Validation error",
                status="error",
                errors=self.custom_serializer_error(serializer.errors),
                status_code=status.HTTP_400_BAD_REQUEST,
            )
            self.log_response(custom)
            return custom
        self.perform_create(serializer)
        custom = self.get_response(
            data=serializer.data,
            message="Contact created",
            status="success",
            status_code=status.HTTP_201_CREATED,
        )
        self.log_response(custom)
        return custom

    def update(self, request, *args, **kwargs):
        self.log_request(request)
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        if not serializer.is_valid():
            custom = self.get_error_response(
                message="Validation error",
                status="error",
                errors=self.custom_serializer_error(serializer.errors),
                status_code=status.HTTP_400_BAD_REQUEST,
            )
            self.log_response(custom)
            return custom
        self.perform_update(serializer)
        custom = self.get_response(
            data=serializer.data,
            message="Contact updated",
            status="success",
            status_code=status.HTTP_200_OK,
        )
        self.log_response(custom)
        return custom

    def partial_update(self, request, *args, **kwargs):
        kwargs["partial"] = True
        return self.update(request, *args, **kwargs)

    # Query params for list (filters, search, ordering, pagination) — documented for Swagger
    _LIST_PARAMS = [
        openapi.Parameter(
            "offset",
            openapi.IN_QUERY,
            description="Pagination: skip this many records (default 0).",
            type=openapi.TYPE_INTEGER,
        ),
        openapi.Parameter(
            "limit",
            openapi.IN_QUERY,
            description="Pagination: max records per page (default 10).",
            type=openapi.TYPE_INTEGER,
        ),
        openapi.Parameter(
            "search",
            openapi.IN_QUERY,
            description="Search in name, phone, email, city, country (partial match).",
            type=openapi.TYPE_STRING,
        ),
        openapi.Parameter(
            "ordering",
            openapi.IN_QUERY,
            description="Sort by: created_at, updated_at, name, email, phone, city, country. Prefix with '-' for descending (e.g. -created_at).",
            type=openapi.TYPE_STRING,
        ),
        openapi.Parameter("group_type", openapi.IN_QUERY, type=openapi.TYPE_STRING),
        openapi.Parameter("city", openapi.IN_QUERY, type=openapi.TYPE_STRING),
        openapi.Parameter("country", openapi.IN_QUERY, type=openapi.TYPE_STRING),
        openapi.Parameter("department", openapi.IN_QUERY, type=openapi.TYPE_STRING),
        openapi.Parameter(
            "is_blacklisted",
            openapi.IN_QUERY,
            type=openapi.TYPE_BOOLEAN,
            description="Filter by blacklist status.",
        ),
        openapi.Parameter(
            "opt_out_sms",
            openapi.IN_QUERY,
            type=openapi.TYPE_BOOLEAN,
            description="Filter by SMS opt-out.",
        ),
        openapi.Parameter(
            "opt_out_email",
            openapi.IN_QUERY,
            type=openapi.TYPE_BOOLEAN,
            description="Filter by email opt-out.",
        ),
        openapi.Parameter(
            "opt_out_whatsapp",
            openapi.IN_QUERY,
            type=openapi.TYPE_BOOLEAN,
            description="Filter by WhatsApp opt-out.",
        ),
    ]

    @swagger_auto_schema(
        operation_summary="List contacts (with filters, search, sort, pagination)",
        operation_description=(
            "Returns contacts in standard envelope. Use query params to filter, search, sort, and paginate.\n\n"
            "**Pagination:** offset, limit (default limit=10).\n"
            "**Search:** search (partial match on name, phone, email, city, country).\n"
            "**Ordering:** ordering (e.g. -created_at, name).\n"
            "**Filters:** group_type, city, country, department, is_blacklisted, opt_out_sms, opt_out_email, opt_out_whatsapp."
        ),
        manual_parameters=_LIST_PARAMS,
        responses={200: "Standard response: { status, message, count, data: [Contact...] }"},
    )
    def list(self, request, *args, **kwargs):
        self.log_request(request)
        # Apply filter/search/order first, then paginate. Do not call super().list()
        # after slicing, or DRF would try to reorder the slice and raise.
        queryset = self.filter_queryset(self.get_queryset())
        count, paginated_queryset = paginate_queryset(request, queryset)
        serializer = self.get_serializer(paginated_queryset, many=True)
        custom = self.get_response(
            data=serializer.data,
            message="List Retrieved",
            count=count,
            status="success",
            status_code=status.HTTP_200_OK,
        )
        self.log_response(custom)
        return custom

    def retrieve(self, request, *args, **kwargs):
        self.log_request(request)
        response = super().retrieve(request, *args, **kwargs)
        if response.status_code != status.HTTP_200_OK:
            custom = self.get_response(
                data=None,
                message="Error occurred",
                status_code=response.status_code,
                is_error=True,
                status="error",
            )
            self.log_response(custom)
            return custom
        custom = self.get_response(
            data=response.data,
            message="Item Retrieved",
            status="success",
            status_code=status.HTTP_200_OK,
        )
        self.log_response(custom)
        return custom

    def destroy(self, request, *args, **kwargs):
        """Delete a single contact. Returns standard response."""
        self.log_request(request)
        instance = self.get_object()
        instance.delete()
        custom = self.get_response(
            data=None,
            message="Contact deleted successfully",
            status="success",
            status_code=status.HTTP_200_OK,
        )
        self.log_response(custom)
        return custom

    @swagger_auto_schema(
        method="post",
        tags=["1. Contacts & Segmentation"],
        operation_summary="Bulk delete contacts",
        operation_description="Delete multiple contacts by ID. Request body: { \"ids\": [1, 2, 3] }. Only existing contact IDs are deleted; invalid IDs are skipped.",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=["ids"],
            properties={
                "ids": openapi.Schema(
                    type=openapi.TYPE_ARRAY,
                    items=openapi.Items(type=openapi.TYPE_INTEGER),
                    description="List of contact IDs to delete.",
                ),
            },
        ),
        responses={
            200: openapi.Response(
                description="Bulk delete result",
                examples={
                    "application/json": {
                        "status": "success",
                        "message": "Contacts deleted",
                        "count": 0,
                        "data": {"deleted_count": 3, "ids": [1, 2, 3]},
                    }
                },
            ),
            400: "Invalid request (e.g. ids missing or not a list).",
        },
    )
    @action(detail=False, methods=["post"], url_path="bulk-delete")
    def bulk_delete(self, request):
        """Delete multiple contacts by ID. Body: { \"ids\": [1, 2, 3] }."""
        self.log_request(request)
        ids = request.data.get("ids")
        if ids is None:
            return self.get_error_response(
                message="ids is required (list of contact IDs)",
                status="error",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        if not isinstance(ids, list):
            return self.get_error_response(
                message="ids must be a list of integers",
                status="error",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        try:
            id_list = [int(x) for x in ids if x is not None]
        except (TypeError, ValueError):
            return self.get_error_response(
                message="ids must contain only integers",
                status="error",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        if not id_list:
            return self.get_response(
                data={"deleted_count": 0, "ids": []},
                message="No valid IDs provided",
                count=0,
                status="success",
                status_code=status.HTTP_200_OK,
            )
        deleted_count, _ = Contact.objects.filter(id__in=id_list).delete()
        custom = self.get_response(
            data={"deleted_count": deleted_count, "ids": id_list},
            message="Contacts deleted",
            count=deleted_count,
            status="success",
            status_code=status.HTTP_200_OK,
        )
        self.log_response(custom)
        return custom

    @swagger_auto_schema(
        method="post",
        tags=["1. Contacts & Segmentation"],
        operation_summary="Bulk upload contacts via CSV",
        operation_description=(
            "Upload a CSV file exported from Excel to create or update contacts.\n\n"
            "Required header columns:\n"
            "- name\n"
            "- phone\n"
            "- email\n"
            "- city\n"
            "- country\n"
            "- group_type (e.g. B2C-GRP, B2C-GUEST, CORPORATE-GRP, HOTELIER-GRP, AGENT-GRP, BUSINESS-GRP; see auth constants)\n\n"
            "Either phone or email must be present per row. "
            "Existing contacts are matched by (group_type + phone) or (group_type + email). "
            "Duplicate rows in the file (same group_type + phone/email as an earlier row) are ignored and not upserted.\n\n"
            "Counts: success_count = created_count + updated_count (first occurrence per identity only). "
            "duplicate_in_file_count = rows skipped as duplicates within this CSV."
        ),
        manual_parameters=[
            openapi.Parameter(
                name="file",
                in_=openapi.IN_FORM,
                type=openapi.TYPE_FILE,
                required=True,
                description="CSV file with contacts exported from Excel.",
            )
        ],
        responses={
            201: openapi.Response(
                description="Upload processed successfully",
                examples={
                    "application/json": {
                        "status": "success",
                        "data": {
                            "id": 5,
                            "uploaded_by": 1,
                            "file_name": "b2c_contacts.csv",
                            "status": "completed",
                            "total_rows": 120,
                            "success_count": 115,
                            "failure_count": 5,
                            "created_count": 80,
                            "updated_count": 23,
                            "duplicate_in_file_count": 12,
                            "errors": [
                                {"row": 4, "error": "Either phone or email is required"}
                            ],
                        },
                    }
                },
            ),
            400: "Invalid file or parsing error",
        },
    )
    @action(detail=False, methods=["post"], url_path="upload", parser_classes=[MultiPartParser])
    def upload(self, request):
        """
        Upload contacts via CSV/Excel-like file.
        For MVP we support a simple CSV where the header row contains:
        name,phone,email,city,country,group_type
        """
        upload_file = request.FILES.get("file")
        if not upload_file:
            return self.get_error_response(
                message="file is required",
                status="error",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        # Only CSV is supported. .numbers and .xlsx are binary; ask user to export as CSV.
        name_lower = (upload_file.name or "").lower()
        if name_lower.endswith(".numbers") or name_lower.endswith(".xlsx") or name_lower.endswith(".xls"):
            return self.get_error_response(
                message=(
                    "Only CSV files are supported. Please export your sheet as CSV "
                    "(e.g. in Numbers: File → Export To → CSV; in Excel: Save As → CSV UTF-8) and upload the .csv file."
                ),
                status="error",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        session = ContactUploadSession.objects.create(
            uploaded_by=request.user,
            file_name=upload_file.name,
        )

        import csv
        import io

        total_rows = 0
        success_count = 0
        failure_count = 0
        created_count = 0
        updated_count = 0
        duplicate_in_file_count = 0
        seen_in_file = set()  # (group_type, phone_norm or email_norm) for duplicate detection
        error_rows = []

        def decode_file_content(raw_bytes):
            """Try UTF-8, then Windows-1252, then latin-1 (accepts any byte)."""
            for encoding in ("utf-8", "cp1252", "latin-1"):
                try:
                    return raw_bytes.decode(encoding)
                except UnicodeDecodeError:
                    continue
            raise UnicodeDecodeError(
                "unknown", raw_bytes, 0, len(raw_bytes), "Could not decode with utf-8, cp1252, or latin-1"
            )

        def normalize_csv_newlines(text):
            """
            Make CSV parseable when cells contain embedded newlines (e.g. Excel).
            If file uses \\r\\n (Windows), treat only \\r\\n as row breaks and replace
            standalone \\n/\\r inside lines with space so csv module does not break.
            """
            if "\r\n" in text:
                lines = text.split("\r\n")
                return "\n".join(
                    line.replace("\n", " ").replace("\r", " ") for line in lines
                )
            return text

        try:
            raw_bytes = upload_file.read()
            data = decode_file_content(raw_bytes)
            data = normalize_csv_newlines(data)
            reader = csv.DictReader(io.StringIO(data))

            # Map common CSV header aliases to our canonical keys (after lowercasing)
            HEADER_ALIASES = {
                "mobile": "phone",
                "phone number": "phone",
                "contact number": "phone",
                "telephone": "phone",
                "e-mail": "email",
                "email address": "email",
                "mail": "email",
                "group": "group_type",
                "group type": "group_type",
            }

            for idx, row in enumerate(reader, start=2):  # 1-based + header row
                total_rows += 1
                # Normalize keys to lowercase for case-insensitive header matching
                row = {k.strip().lower(): v for k, v in row.items() if k}
                # Apply aliases so "Mobile", "E-mail", etc. map to phone/email
                for alias, canonical in HEADER_ALIASES.items():
                    if alias in row and canonical not in row:
                        row[canonical] = row[alias]
                try:
                    name = (row.get("name") or "").strip()
                    phone = (row.get("phone") or "").strip()
                    email = (row.get("email") or "").strip()
                    city = (row.get("city") or "").strip()
                    country = (row.get("country") or "").strip()
                    group_type = (row.get("group_type") or "").strip() or UserGroups.B2C_GRP
                    remarks = (row.get("remarks") or "").strip()
                    department = (row.get("department") or "").strip()

                    if not phone and not email:
                        raise ValueError("Either phone or email is required")
                    if group_type not in dict(ALL_GROUP_CHOICES):
                        raise ValueError(f"Invalid group_type '{group_type}'")
                    # Validate phone format when provided (digits only, 10–15 chars)
                    if phone:
                        phone_digits = re.sub(r"\D", "", phone)
                        if len(phone_digits) < 10 or len(phone_digits) > 15:
                            raise ValueError(
                                "Invalid phone: must be 10–15 digits (with optional + or spaces)"
                            )
                    # Validate email format when provided
                    if email:
                        EmailValidator()(email)

                    # Ignore duplicates within this CSV (same group_type + phone/email as earlier row)
                    phone_norm = normalize_phone(phone) if phone else ""
                    email_norm = email.strip().lower() if email else ""
                    row_key = (group_type, phone_norm or email_norm)
                    if row_key in seen_in_file:
                        duplicate_in_file_count += 1
                        continue
                    seen_in_file.add(row_key)

                    _contact, created = upsert_contact_from_row(
                        name=name,
                        phone=phone,
                        email=email,
                        city=city,
                        country=country,
                        group_type=group_type,
                        remarks=remarks,
                        department=department,
                    )
                    success_count += 1
                    if created:
                        created_count += 1
                    else:
                        updated_count += 1
                except Exception as exc:
                    failure_count += 1
                    error_rows.append({"row": idx, "error": str(exc)})

            session.total_rows = total_rows
            session.success_count = success_count
            session.failure_count = failure_count
            session.created_count = created_count
            session.updated_count = updated_count
            session.duplicate_in_file_count = duplicate_in_file_count
            # Mark as COMPLETED if we successfully processed the file, even if some rows failed.
            # Use FAILED only when nothing succeeded.
            session.status = (
                ContactUploadSession.Status.COMPLETED
                if success_count > 0 or failure_count == 0
                else ContactUploadSession.Status.FAILED
            )
            session.finished_at = timezone.now()
            # For MVP we store errors inline in session.error_report_path as JSON string
            if error_rows:
                import json

                session.error_report_path = json.dumps(error_rows)
            session.save(
                update_fields=[
                    "total_rows",
                    "success_count",
                    "failure_count",
                    "created_count",
                    "updated_count",
                    "duplicate_in_file_count",
                    "status",
                    "finished_at",
                    "error_report_path",
                ]
            )
        except Exception as exc:
            session.status = ContactUploadSession.Status.FAILED
            session.finished_at = timezone.now()
            session.error_report_path = str(exc)
            session.save(update_fields=["status", "finished_at", "error_report_path"])
            return self.get_error_response(
                message=f"Failed to process file: {exc}",
                status="error",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        payload = ContactUploadSessionSerializer(session).data
        payload["errors"] = error_rows
        return self.get_response(
            data=payload, status="success", status_code=status.HTTP_201_CREATED
        )


class ContactUploadSessionViewSet(viewsets.ReadOnlyModelViewSet, StandardResponseMixin, LoggingMixin):
    """
    Monitoring: Contact upload sessions
    """

    queryset = ContactUploadSession.objects.all().order_by("-created_at")
    serializer_class = ContactUploadSessionSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ["get"]
    swagger_tags = ["1. Contacts & Segmentation"]

    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["status", "uploaded_by", "file_name"]
    search_fields = ["file_name"]
    ordering_fields = ["created_at", "finished_at", "total_rows", "success_count", "failure_count"]
    ordering = ["-created_at"]

    def retrieve(self, request, *args, **kwargs):
        self.log_request(request)
        response = super().retrieve(request, *args, **kwargs)
        if response.status_code != status.HTTP_200_OK:
            custom = self.get_response(
                data=None,
                message="Error occurred",
                status_code=response.status_code,
                is_error=True,
                status="error",
            )
            self.log_response(custom)
            return custom
        custom = self.get_response(
            data=response.data,
            message="Item Retrieved",
            status="success",
            status_code=status.HTTP_200_OK,
        )
        self.log_response(custom)
        return custom

    @swagger_auto_schema(
        operation_summary="List contact uploads (with filters, search, sort, pagination)",
        operation_description=(
            "Returns recent contact uploads in standard envelope.\n\n"
            "Pagination: offset, limit (default limit=10).\n"
            "Search: search by file_name.\n"
            "Ordering: ordering by created_at, finished_at, total_rows, success_count, failure_count.\n"
            "Filters: status, uploaded_by, file_name."
        ),
        manual_parameters=[
            openapi.Parameter(
                "offset",
                openapi.IN_QUERY,
                description="Pagination offset (default 0).",
                type=openapi.TYPE_INTEGER,
            ),
            openapi.Parameter(
                "limit",
                openapi.IN_QUERY,
                description="Pagination limit (default 10).",
                type=openapi.TYPE_INTEGER,
            ),
            openapi.Parameter(
                "search",
                openapi.IN_QUERY,
                description="Search by file_name (partial match).",
                type=openapi.TYPE_STRING,
            ),
            openapi.Parameter(
                "ordering",
                openapi.IN_QUERY,
                description="Sort by created_at, finished_at, total_rows, success_count, failure_count. Prefix '-' for desc.",
                type=openapi.TYPE_STRING,
            ),
            openapi.Parameter(
                "status",
                openapi.IN_QUERY,
                description="Filter by status: processing/completed/failed.",
                type=openapi.TYPE_STRING,
            ),
            openapi.Parameter(
                "uploaded_by",
                openapi.IN_QUERY,
                description="Filter by uploader user id.",
                type=openapi.TYPE_INTEGER,
            ),
            openapi.Parameter(
                "file_name",
                openapi.IN_QUERY,
                description="Exact match filter by file name.",
                type=openapi.TYPE_STRING,
            ),
        ],
        responses={200: "Standard response: { status, message, count, data: [ContactUploadSession...] }"},
    )
    def list(self, request, *args, **kwargs):
        self.log_request(request)
        queryset = self.filter_queryset(self.get_queryset())
        count, paginated_queryset = paginate_queryset(request, queryset)
        serializer = self.get_serializer(paginated_queryset, many=True)
        custom = self.get_response(
            data=serializer.data,
            message="List Retrieved",
            count=count,
            status="success",
            status_code=status.HTTP_200_OK,
        )
        self.log_response(custom)
        return custom


class EmailTemplateViewSet(viewsets.ModelViewSet, StandardResponseMixin, LoggingMixin):
    """
    Step 2: Email Templates

    Define marketing email templates used by campaign steps (channel=email).
    """

    queryset = EmailTemplate.objects.all().order_by("-created_at")
    serializer_class = EmailTemplateSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "post", "put", "patch", "delete"]
    swagger_tags = ["2. Templates & Variables"]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class CampaignViewSet(viewsets.ModelViewSet, StandardResponseMixin, LoggingMixin):
    """
    Step 3: Campaigns

    Create and manage high-level campaigns (audience + filters).
    """

    queryset = Campaign.objects.all().order_by("-created_at")
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "post", "put", "patch", "delete"]
    swagger_tags = ["3. Campaigns & Steps"]

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return CampaignCreateUpdateSerializer
        return CampaignSerializer

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @swagger_auto_schema(
        method="post",
        tags=["4. Execution (Send & Schedule)"],
        operation_summary="Schedule campaign for a future time",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=["schedule_time"],
            properties={
                "schedule_time": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    format="date-time",
                    description="ISO 8601 datetime when the first step should start.",
                    example="2026-03-17T10:00:00+05:30",
                )
            },
        ),
        responses={
            200: openapi.Response(
                description="Campaign scheduled",
                examples={
                    "application/json": {
                        "status": "success",
                        "data": {
                            "status": "scheduled",
                            "schedule_time": "2026-03-17T04:30:00Z",
                        },
                    }
                },
            ),
            400: "Invalid schedule_time",
        },
    )
    @action(detail=True, methods=["post"])
    def schedule(self, request, pk=None):
        campaign = self.get_object()
        schedule_time_str = request.data.get("schedule_time")
        if not schedule_time_str:
            return self.get_error_response(
                message="schedule_time is required",
                status="error",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        try:
            schedule_time = timezone.datetime.fromisoformat(schedule_time_str)
            if timezone.is_naive(schedule_time):
                schedule_time = timezone.make_aware(schedule_time, timezone.get_current_timezone())
        except Exception:
            return self.get_error_response(
                message="Invalid schedule_time format, expected ISO 8601",
                status="error",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        campaign.schedule_time = schedule_time
        campaign.status = Campaign.Status.SCHEDULED
        campaign.save(update_fields=["schedule_time", "status", "updated_at"])

        enqueue_campaign_contacts_task.delay(campaign.id)

        return self.get_response(
            data={"status": "scheduled", "schedule_time": schedule_time},
            status="success",
        )

    @swagger_auto_schema(
        method="post",
        tags=["4. Execution (Send & Schedule)"],
        operation_summary="Trigger campaign to send immediately",
        responses={
            200: openapi.Response(
                description="Campaign started",
                examples={
                    "application/json": {
                        "status": "success",
                        "data": {"status": "running"},
                    }
                },
            )
        },
    )
    @action(detail=True, methods=["post"])
    def send_now(self, request, pk=None):
        campaign = self.get_object()
        campaign.schedule_time = timezone.now()
        campaign.status = Campaign.Status.RUNNING
        campaign.save(update_fields=["schedule_time", "status", "updated_at"])

        enqueue_campaign_contacts_task.delay(campaign.id)
        return self.get_response(data={"status": "running"}, status="success")

    @swagger_auto_schema(
        method="post",
        tags=["4. Execution (Send & Schedule)"],
        operation_summary="Pause an active or scheduled campaign",
        responses={
            200: openapi.Response(
                description="Campaign paused",
                examples={
                    "application/json": {
                        "status": "success",
                        "data": {"status": "paused"},
                    }
                },
            )
        },
    )
    @action(detail=True, methods=["post"])
    def pause(self, request, pk=None):
        campaign = self.get_object()
        campaign.status = Campaign.Status.PAUSED
        campaign.save(update_fields=["status", "updated_at"])
        return self.get_response(data={"status": "paused"}, status="success")

    @swagger_auto_schema(
        method="get",
        tags=["5. Monitoring & Analytics"],
        operation_summary="Get campaign status and counters",
        responses={
            200: openapi.Response(
                description="Campaign status with counters",
                examples={
                    "application/json": {
                        "status": "success",
                        "data": {
                            "campaign_id": 1,
                            "status": "running",
                            "counters": {
                                "total": 1000,
                                "pending": 200,
                                "queued": 0,
                                "sent": 780,
                                "failed": 10,
                                "skipped_opt_out": 5,
                                "blacklisted": 5,
                            },
                        },
                    }
                },
            )
        },
    )
    @action(detail=True, methods=["get"])
    def status(self, request, pk=None):
        campaign = self.get_object()
        qs = CampaignContact.objects.filter(campaign=campaign)
        counters = {
            "total": qs.count(),
            "pending": qs.filter(status=CampaignContact.Status.PENDING).count(),
            "queued": qs.filter(status=CampaignContact.Status.QUEUED).count(),
            "sent": qs.filter(status=CampaignContact.Status.SENT).count(),
            "failed": qs.filter(status=CampaignContact.Status.FAILED).count(),
            "skipped_opt_out": qs.filter(
                status=CampaignContact.Status.SKIPPED_OPT_OUT
            ).count(),
            "blacklisted": qs.filter(
                status=CampaignContact.Status.BLACKLISTED
            ).count(),
        }
        return self.get_response(
            data={"campaign_id": campaign.id, "status": campaign.status, "counters": counters},
            status="success",
        )


class CampaignStepViewSet(viewsets.ModelViewSet, StandardResponseMixin, LoggingMixin):
    """
    Step 4: Campaign Steps

    Attach one or more steps (Email/SMS, templates, delays) to a campaign.
    """

    queryset = CampaignStep.objects.all().order_by("campaign_id", "order_index")
    serializer_class = CampaignStepSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "post", "put", "patch", "delete"]
    swagger_tags = ["3. Campaigns & Steps"]


class MessageLogViewSet(viewsets.ReadOnlyModelViewSet, StandardResponseMixin, LoggingMixin):
    """
    Step 6: Monitoring & Analytics

    Inspect individual message logs for debugging and analytics.
    """

    queryset = MessageLog.objects.all().order_by("-created_at")
    serializer_class = MessageLogSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ["get"]
    swagger_tags = ["5. Monitoring & Analytics"]


class TemplateVariablesViewSet(viewsets.ViewSet, StandardResponseMixin, LoggingMixin):
    permission_classes = [IsAuthenticated]
    swagger_tags = ["2. Templates & Variables"]

    @swagger_auto_schema(
        operation_summary="List available template variables",
        operation_description=(
            "Returns all supported template variables that can be used in SMS and email templates, "
            "grouped by categories like 'contact' and 'user'."
        ),
        responses={
            200: openapi.Response(
                description="List of variables",
                examples={
                    "application/json": {
                        "status": "success",
                        "data": [
                            {
                                "name": "name",
                                "label": "Contact name",
                                "category": "contact",
                            },
                            {
                                "name": "city",
                                "label": "City",
                                "category": "contact",
                            },
                            {
                                "name": "user_id",
                                "label": "User ID",
                                "category": "user",
                            },
                        ],
                    }
                },
            )
        },
    )
    def list(self, request):
        definitions = get_template_variable_definitions()
        return self.get_response(data=definitions, status="success")

