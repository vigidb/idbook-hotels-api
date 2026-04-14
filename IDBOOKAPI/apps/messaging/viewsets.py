import re
from typing import Any, Dict, Optional
from django.conf import settings
from django.core import signing
from django.core.validators import EmailValidator
from django.db import transaction
from django.db.models import Count, Prefetch, Q
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
from apps.org_resources.models import MessageTemplate
from apps.messaging.models import (
    Contact,
    ContactUploadSession,
    Campaign,
    CampaignStep,
    CampaignContact,
    MessageLog,
    EmailTemplate,
    MessagingProviderConfig,
)
from apps.messaging.serializers import (
    ContactSerializer,
    ContactUploadSessionSerializer,
    CampaignSerializer,
    CampaignListSerializer,
    CampaignCreateUpdateSerializer,
    CampaignAudiencePreviewSerializer,
    CampaignStepSerializer,
    CampaignContactSerializer,
    MessageLogSerializer,
    SmsTemplateSerializer,
    EmailTemplateSerializer,
    MessagingProviderConfigSerializer,
)
from apps.messaging.provider_runtime import (
    credential_guidance,
    resolve_email_provider_for_test,
    resolve_sms_config_for_test,
)
from apps.messaging.services import (
    MissingTemplateVariableError,
    apply_template_variable_defaults,
    build_template_variables,
    campaign_has_active_steps,
    count_campaign_audience,
    get_default_provider_for_channel,
    get_template_variable_definitions,
    normalize_phone,
    normalize_segment_tags,
    resolve_campaign_contacts,
    upsert_contact_from_row,
    render_template_string,
)
from apps.messaging.tasks import enqueue_campaign_contacts_task, send_campaign_batch_task
from apps.sms_gateway.mixins.fastwosms_mixins import send_template_sms
from IDBOOKAPI.email_utils import send_email_with_smtp_config


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
            "duplicate_in_file_count = rows skipped as duplicates within this CSV.\n\n"
            "Optional form fields:\n"
            "- **group_type** — default when a row omits `group_type` (same values as column).\n"
            "- **default_tags** — comma-separated labels applied to every row, **union** with per-row "
            "`tags` / `segment_tags` column (all normalized lowercase); then merged with existing "
            "contact tags on update."
        ),
        manual_parameters=[
            openapi.Parameter(
                name="file",
                in_=openapi.IN_FORM,
                type=openapi.TYPE_FILE,
                required=True,
                description="CSV file with contacts exported from Excel.",
            ),
            openapi.Parameter(
                name="group_type",
                in_=openapi.IN_FORM,
                type=openapi.TYPE_STRING,
                required=False,
                description="Default group_type for rows that omit the column (e.g. B2C-GRP).",
            ),
            openapi.Parameter(
                name="default_tags",
                in_=openapi.IN_FORM,
                type=openapi.TYPE_STRING,
                required=False,
                description="Comma-separated tags applied to every row in addition to per-row tags.",
            ),
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
        CSV header row may include:
        name, phone, email, city, country, group_type, remarks, department, tags
        (tags = comma-separated labels, merged with existing tags on update).

        Optional multipart fields: group_type (default for rows without column),
        default_tags (comma-separated; union with each row's tags before upsert).
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

        default_group_type = (request.POST.get("group_type") or "").strip()
        if default_group_type and default_group_type not in dict(ALL_GROUP_CHOICES):
            return self.get_error_response(
                message=f"Invalid default group_type '{default_group_type}'",
                status="error",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        default_tags_raw = (request.POST.get("default_tags") or "").strip()
        default_tag_list = (
            normalize_segment_tags(default_tags_raw) if default_tags_raw else []
        )

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
                "labels": "tags",
                "segment tags": "tags",
                "segment_tags": "tags",
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
                    group_type = (row.get("group_type") or "").strip() or (
                        default_group_type or UserGroups.B2C_GRP
                    )
                    remarks = (row.get("remarks") or "").strip()
                    department = (row.get("department") or "").strip()
                    row_tag_list: list = []
                    if "tags" in row or "segment_tags" in row:
                        tag_cell = (row.get("tags") or row.get("segment_tags") or "").strip()
                        row_tag_list = (
                            normalize_segment_tags(tag_cell) if tag_cell else []
                        )
                    segment_tags_arg = sorted(set(default_tag_list) | set(row_tag_list))

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
                        segment_tags=segment_tags_arg,
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

    queryset = EmailTemplate.objects.all().select_related("provider").order_by(
        "-created_at"
    )
    serializer_class = EmailTemplateSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "post", "put", "patch", "delete"]
    swagger_tags = ["2. Templates & Variables"]

    def _build_test_system_variables(self, contact_id: Optional[int] = None) -> Dict[str, Any]:
        frontend_base = (getattr(settings, "FRONTEND_URL", "") or "").rstrip("/")
        if not frontend_base:
            frontend_base = (getattr(settings, "BASE_URL", "") or "").rstrip("/")
        payload = {"contact_id": contact_id, "channel": "email", "purpose": "test"}
        token = signing.dumps(payload, salt="messaging-unsubscribe")
        unsubscribe_url = f"{frontend_base}/unsubscribe?token={token}" if frontend_base else ""
        return {"unsubscribe_token": token, "unsubscribe_url": unsubscribe_url}

    @swagger_auto_schema(
        method="post",
        operation_summary="Preview an email template with variables",
        operation_description=(
            "Renders subject/body using a selected contact (optional) and variable overrides.\n\n"
            "Defaults are applied from EmailTemplate.variables_schema and inline |default: syntax."
        ),
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "contact_id": openapi.Schema(type=openapi.TYPE_INTEGER, description="Contact id to use as context."),
                "variables": openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    description="Override variables (e.g. {\"name\": \"Vignesh\"}).",
                    additional_properties=openapi.Schema(type=openapi.TYPE_STRING),
                ),
            },
        ),
        responses={200: "Standard response: rendered subject/body"},
    )
    @action(detail=True, methods=["post"], url_path="preview")
    def preview(self, request, pk=None):
        self.log_request(request)
        template = self.get_object()
        contact_id = request.data.get("contact_id")
        overrides = request.data.get("variables") or {}
        if overrides is not None and not isinstance(overrides, dict):
            return self.get_error_response(
                message="variables must be an object",
                status="error",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        contact = None
        if contact_id is not None:
            try:
                contact = Contact.objects.get(pk=int(contact_id))
            except Exception:
                return self.get_error_response(
                    message="Invalid contact_id",
                    status="error",
                    status_code=status.HTTP_400_BAD_REQUEST,
                )

        variables = build_template_variables(contact) if contact else {}
        variables.update(self._build_test_system_variables(contact_id=contact.id if contact else None))
        variables.update(overrides)
        variables = apply_template_variable_defaults(getattr(template, "variables_schema", None), variables)

        try:
            rendered = {
                "subject": render_template_string(template.subject, variables),
                "body_html": render_template_string(template.body_html, variables),
                "body_text": template.body_text
                and render_template_string(template.body_text, variables)
                or render_template_string(template.body_html, variables),
            }
        except MissingTemplateVariableError as exc:
            return self.get_error_response(
                message=str(exc),
                status="error",
                errors={"missing_variables": exc.missing},
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        return self.get_response(
            data=rendered,
            message="Preview generated",
            status="success",
            status_code=status.HTTP_200_OK,
        )

    @swagger_auto_schema(
        method="post",
        operation_summary="Send a test email for this template",
        operation_description=(
            "Sends a test email using this template. Provide either to_email, or contact_id (uses contact.email).\n"
            "You can pass variable overrides via `variables`."
        ),
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "to_email": openapi.Schema(type=openapi.TYPE_STRING, description="Recipient email for the test."),
                "contact_id": openapi.Schema(type=openapi.TYPE_INTEGER, description="Contact id to use as context."),
                "variables": openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    description="Override variables (e.g. {\"name\": \"Vignesh\"}).",
                    additional_properties=openapi.Schema(type=openapi.TYPE_STRING),
                ),
                "messaging_provider_id": openapi.Schema(
                    type=openapi.TYPE_INTEGER,
                    description=(
                        "Optional. Use this email MessagingProviderConfig for SMTP. "
                        "Omit to follow template → default provider → server env."
                    ),
                ),
            },
            required=[],
        ),
        responses={200: "Standard response: send result"},
    )
    @action(detail=True, methods=["post"], url_path="send-test")
    def send_test(self, request, pk=None):
        self.log_request(request)
        template = self.get_object()
        to_email = (request.data.get("to_email") or "").strip()
        contact_id = request.data.get("contact_id")
        overrides = request.data.get("variables") or {}
        if overrides is not None and not isinstance(overrides, dict):
            return self.get_error_response(
                message="variables must be an object",
                status="error",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        contact = None
        if contact_id is not None:
            try:
                contact = Contact.objects.get(pk=int(contact_id))
            except Exception:
                return self.get_error_response(
                    message="Invalid contact_id",
                    status="error",
                    status_code=status.HTTP_400_BAD_REQUEST,
                )

        if not to_email and contact and contact.email:
            to_email = contact.email
        if not to_email:
            return self.get_error_response(
                message="to_email is required (or provide contact_id with email)",
                status="error",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        # Validate email format early
        try:
            EmailValidator()(to_email)
        except Exception:
            return self.get_error_response(
                message="Invalid to_email",
                status="error",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        variables = build_template_variables(contact) if contact else {}
        variables.update(self._build_test_system_variables(contact_id=contact.id if contact else None))
        variables.update(overrides)
        variables = apply_template_variable_defaults(getattr(template, "variables_schema", None), variables)

        try:
            subject = render_template_string(template.subject, variables)
            body_html = render_template_string(template.body_html, variables)
            body_text = template.body_text and render_template_string(template.body_text, variables) or render_template_string(template.body_html, variables)
        except MissingTemplateVariableError as exc:
            return self.get_error_response(
                message=str(exc),
                status="error",
                errors={"missing_variables": exc.missing},
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        from IDBOOKAPI.email_utils import send_email as core_send_email

        raw_pid = request.data.get("messaging_provider_id")
        override_provider_id = None
        if raw_pid is not None and raw_pid != "":
            try:
                override_provider_id = int(raw_pid)
            except (TypeError, ValueError):
                return self.get_error_response(
                    message="messaging_provider_id must be an integer",
                    status="error",
                    status_code=status.HTTP_400_BAD_REQUEST,
                )

        try:
            prov_used, smtp_cfg = resolve_email_provider_for_test(
                template_provider=template.provider,
                override_provider_id=override_provider_id,
                default_resolver=get_default_provider_for_channel,
            )
        except ValueError as exc:
            return self.get_error_response(
                message=str(exc),
                status="error",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        if prov_used and not smtp_cfg:
            return self.get_error_response(
                message=(
                    "Selected email provider is missing required SMTP settings "
                    "(smtp_host, smtp_username, smtp_password, from_email)."
                ),
                status="error",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        try:
            if smtp_cfg:
                send_email_with_smtp_config(
                    subject=subject,
                    message=body_text,
                    html_message=body_html,
                    to_emails=[to_email],
                    smtp=smtp_cfg,
                )
            else:
                core_send_email(
                    subject=subject,
                    message=body_text,
                    html_message=body_html,
                    to_emails=[to_email],
                    from_email=settings.EMAIL_HOST_USER,
                )
        except Exception as exc:
            return self.get_error_response(
                message=f"Failed to send test email: {exc}",
                status="error",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        return self.get_response(
            data={
                "to_email": to_email,
                "template_id": template.id,
                "messaging_provider_id": prov_used.id if prov_used else None,
                "used_custom_smtp": bool(smtp_cfg),
            },
            message="Test email sent",
            status="success",
            status_code=status.HTTP_200_OK,
        )

    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["is_active", "is_marketing", "provider", "created_by", "slug", "name"]
    search_fields = ["name", "slug", "subject", "body_html", "body_text"]
    ordering_fields = ["created_at", "updated_at", "name", "slug", "is_active", "is_marketing"]
    ordering = ["-created_at"]

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
            description="Search in name, slug, subject, body_html, body_text (partial match).",
            type=openapi.TYPE_STRING,
        ),
        openapi.Parameter(
            "ordering",
            openapi.IN_QUERY,
            description="Sort by: created_at, updated_at, name, slug, is_active, is_marketing. Prefix with '-' for descending (e.g. -created_at).",
            type=openapi.TYPE_STRING,
        ),
        openapi.Parameter("is_active", openapi.IN_QUERY, type=openapi.TYPE_BOOLEAN),
        openapi.Parameter("is_marketing", openapi.IN_QUERY, type=openapi.TYPE_BOOLEAN),
        openapi.Parameter(
            "provider",
            openapi.IN_QUERY,
            description="Filter by provider id.",
            type=openapi.TYPE_INTEGER,
        ),
        openapi.Parameter(
            "created_by",
            openapi.IN_QUERY,
            description="Filter by creator user id.",
            type=openapi.TYPE_INTEGER,
        ),
        openapi.Parameter("slug", openapi.IN_QUERY, type=openapi.TYPE_STRING),
        openapi.Parameter("name", openapi.IN_QUERY, type=openapi.TYPE_STRING),
    ]

    @swagger_auto_schema(
        operation_summary="List email templates (with filters, search, sort, pagination)",
        operation_description=(
            "Returns email templates in standard envelope.\n\n"
            "Pagination: offset, limit (default limit=10).\n"
            "Search: search by name, slug, subject, body_html, body_text.\n"
            "Ordering: ordering by created_at, updated_at, name, slug, is_active, is_marketing.\n"
            "Filters: is_active, is_marketing, provider, created_by, slug, name."
        ),
        manual_parameters=_LIST_PARAMS,
        responses={200: "Standard response: { status, message, count, data: [EmailTemplate...] }"},
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
            message="Email template created",
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
            message="Email template updated",
            status="success",
            status_code=status.HTTP_200_OK,
        )
        self.log_response(custom)
        return custom

    def partial_update(self, request, *args, **kwargs):
        kwargs["partial"] = True
        return self.update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        self.log_request(request)
        instance = self.get_object()
        instance.delete()
        custom = self.get_response(
            data=None,
            message="Email template deleted successfully",
            status="success",
            status_code=status.HTTP_200_OK,
        )
        self.log_response(custom)
        return custom

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class CampaignViewSet(viewsets.ModelViewSet, StandardResponseMixin, LoggingMixin):
    """
    Campaigns: audience (target group + JSON filters), multi-step flows, scheduling.
    """

    queryset = Campaign.objects.all()
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "post", "put", "patch", "delete"]
    swagger_tags = ["3. Campaigns & Steps"]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["status", "target_group_type"]
    search_fields = ["name", "description"]
    ordering_fields = ["created_at", "updated_at", "name", "schedule_time", "status"]
    ordering = ["-created_at"]

    def get_queryset(self):
        return (
            Campaign.objects.annotate(step_count=Count("steps", distinct=True))
            .select_related("created_by")
            .prefetch_related(
                Prefetch(
                    "steps",
                    queryset=CampaignStep.objects.select_related("messaging_provider").order_by(
                        "order_index"
                    ),
                )
            )
            .order_by("-created_at")
        )

    def get_serializer_class(self):
        if self.action == "list":
            return CampaignListSerializer
        if self.action in ("create", "update", "partial_update"):
            return CampaignCreateUpdateSerializer
        return CampaignSerializer

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    def _dispatch_prereq_error(self, campaign):
        if not campaign_has_active_steps(campaign):
            return self.get_error_response(
                message=(
                    "Add at least one active step with a template (email slug or SMS template_code). "
                    "Manage steps via /api/v1/messaging/campaign-steps/?campaign=<id>."
                ),
                status="error",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        if count_campaign_audience(campaign) == 0:
            return self.get_error_response(
                message="No contacts match this audience. Adjust target_group_type or target_filters.",
                status="error",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        return None

    def _rebuild_pipeline_and_enqueue(self, campaign, *, eta=None):
        """
        Keep campaign_contact rows aligned with latest audience + steps.
        Re-scheduling should not retain stale rows from previous targeting.
        """
        CampaignContact.objects.filter(campaign=campaign).delete()
        if eta is not None:
            enqueue_campaign_contacts_task.apply_async(args=[campaign.id], eta=eta)
        else:
            enqueue_campaign_contacts_task.delay(campaign.id)

    @swagger_auto_schema(
        operation_summary="List campaigns (filters, search, pagination)",
        manual_parameters=[
            openapi.Parameter("offset", openapi.IN_QUERY, type=openapi.TYPE_INTEGER),
            openapi.Parameter("limit", openapi.IN_QUERY, type=openapi.TYPE_INTEGER),
            openapi.Parameter("search", openapi.IN_QUERY, type=openapi.TYPE_STRING),
            openapi.Parameter("ordering", openapi.IN_QUERY, type=openapi.TYPE_STRING),
            openapi.Parameter("status", openapi.IN_QUERY, type=openapi.TYPE_STRING),
            openapi.Parameter("target_group_type", openapi.IN_QUERY, type=openapi.TYPE_STRING),
        ],
        responses={200: "Standard envelope: count, data"},
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
            message="Campaign created",
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
            message="Campaign updated",
            status="success",
            status_code=status.HTTP_200_OK,
        )
        self.log_response(custom)
        return custom

    def partial_update(self, request, *args, **kwargs):
        kwargs["partial"] = True
        return self.update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        self.log_request(request)
        instance = self.get_object()
        if instance.status in (Campaign.Status.SCHEDULED, Campaign.Status.RUNNING):
            custom = self.get_error_response(
                message="Pause the campaign before deleting.",
                status="error",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
            self.log_response(custom)
            return custom
        instance.delete()
        custom = self.get_response(
            data=None,
            message="Campaign deleted successfully",
            status="success",
            status_code=status.HTTP_200_OK,
        )
        self.log_response(custom)
        return custom

    @swagger_auto_schema(
        method="post",
        tags=["3. Campaigns & Steps"],
        operation_summary="Preview audience size without saving a campaign",
        request_body=CampaignAudiencePreviewSerializer,
        responses={200: "count and targeting echo"},
    )
    @action(detail=False, methods=["post"], url_path="audience-preview")
    def audience_preview(self, request):
        self.log_request(request)
        ser = CampaignAudiencePreviewSerializer(data=request.data)
        if not ser.is_valid():
            return self.get_error_response(
                message="Validation error",
                status="error",
                errors=self.custom_serializer_error(ser.errors),
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        c = Campaign(
            target_group_type=ser.validated_data.get("target_group_type") or "",
            target_filters=ser.validated_data.get("target_filters") or {},
        )
        n = count_campaign_audience(c)
        return self.get_response(
            data={
                "count": n,
                "target_group_type": c.target_group_type,
                "target_filters": c.target_filters,
            },
            message="Audience preview",
            status="success",
        )

    @swagger_auto_schema(
        method="post",
        tags=["3. Campaigns & Steps"],
        operation_summary="Sample contacts matching audience filters (paginated)",
        request_body=CampaignAudiencePreviewSerializer,
        responses={200: "Standard envelope: total count + Contact[] slice"},
    )
    @action(detail=False, methods=["post"], url_path="audience-sample")
    def audience_sample(self, request):
        self.log_request(request)
        ser = CampaignAudiencePreviewSerializer(data=request.data)
        if not ser.is_valid():
            return self.get_error_response(
                message="Validation error",
                status="error",
                errors=self.custom_serializer_error(ser.errors),
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        try:
            limit = int(request.data.get("limit", 25))
        except (TypeError, ValueError):
            limit = 25
        try:
            offset = int(request.data.get("offset", 0))
        except (TypeError, ValueError):
            offset = 0
        limit = max(1, min(limit, 100))
        offset = max(0, offset)

        c = Campaign(
            target_group_type=ser.validated_data.get("target_group_type") or "",
            target_filters=ser.validated_data.get("target_filters") or {},
        )
        qs = resolve_campaign_contacts(c).order_by("-id")
        total = qs.count()
        slice_qs = qs[offset : offset + limit]
        data = ContactSerializer(slice_qs, many=True).data
        return self.get_response(
            data=data,
            count=total,
            message="Audience sample",
            status="success",
        )

    @swagger_auto_schema(
        method="get",
        tags=["3. Campaigns & Steps"],
        operation_summary="Saved campaign: audience count and targeting",
    )
    @action(detail=True, methods=["get"], url_path="audience")
    def audience(self, request, pk=None):
        self.log_request(request)
        campaign = self.get_object()
        n = count_campaign_audience(campaign)
        return self.get_response(
            data={
                "count": n,
                "target_group_type": campaign.target_group_type,
                "target_filters": campaign.target_filters or {},
            },
            status="success",
        )

    @swagger_auto_schema(
        method="get",
        tags=["5. Monitoring & Analytics"],
        operation_summary="Paginated campaign_contact rows (per-recipient pipeline)",
        manual_parameters=[
            openapi.Parameter("offset", openapi.IN_QUERY, type=openapi.TYPE_INTEGER),
            openapi.Parameter("limit", openapi.IN_QUERY, type=openapi.TYPE_INTEGER),
            openapi.Parameter(
                "status",
                openapi.IN_QUERY,
                type=openapi.TYPE_STRING,
                description="Filter by CampaignContact status",
            ),
        ],
    )
    @action(detail=True, methods=["get"], url_path="contacts")
    def contacts(self, request, pk=None):
        self.log_request(request)
        campaign = self.get_object()
        qs = CampaignContact.objects.filter(campaign=campaign).select_related(
            "contact", "step"
        )
        st = (request.query_params.get("status") or "").strip()
        if st:
            qs = qs.filter(status=st)
        qs = qs.order_by("-id")
        count, page = paginate_queryset(request, qs)
        ser = CampaignContactSerializer(page, many=True)
        return self.get_response(
            data=ser.data,
            count=count,
            message="Campaign contacts",
            status="success",
        )

    @swagger_auto_schema(
        method="post",
        tags=["3. Campaigns & Steps"],
        operation_summary="Delete queued rows for draft/paused campaigns (re-build audience)",
    )
    @action(detail=True, methods=["post"], url_path="reset-contacts")
    def reset_contacts(self, request, pk=None):
        self.log_request(request)
        campaign = self.get_object()
        if campaign.status not in (Campaign.Status.DRAFT, Campaign.Status.PAUSED):
            return self.get_error_response(
                message="Only draft or paused campaigns can reset contacts.",
                status="error",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        deleted, _ = CampaignContact.objects.filter(campaign=campaign).delete()
        return self.get_response(
            data={"deleted": deleted},
            message="Campaign contacts cleared",
            status="success",
        )

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
        if campaign.status == Campaign.Status.RUNNING:
            return self.get_error_response(
                message="Cannot schedule while campaign is running. Pause it first.",
                status="error",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        err = self._dispatch_prereq_error(campaign)
        if err:
            return err
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

        now = timezone.now()

        campaign.schedule_time = schedule_time
        campaign.status = Campaign.Status.SCHEDULED
        campaign.save(update_fields=["schedule_time", "status", "updated_at"])

        # If scheduling in the future, enqueue build exactly at schedule_time.
        # Always rebuild pipeline rows first to avoid stale audience data.
        if schedule_time > now:
            self._rebuild_pipeline_and_enqueue(campaign, eta=schedule_time)
        else:
            self._rebuild_pipeline_and_enqueue(campaign)

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
        err = self._dispatch_prereq_error(campaign)
        if err:
            return err
        campaign.schedule_time = timezone.now()
        campaign.status = Campaign.Status.RUNNING
        campaign.save(update_fields=["schedule_time", "status", "updated_at"])

        # Rebuild from latest audience/steps before immediate dispatch.
        self._rebuild_pipeline_and_enqueue(campaign)
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
        operation_summary="Campaign status, aggregate counters, and per-step breakdown",
        responses={
            200: openapi.Response(
                description="Campaign status with counters",
                examples={
                    "application/json": {
                        "status": "success",
                        "data": {
                            "campaign_id": 1,
                            "status": "running",
                            "counters": {},
                            "steps": [],
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
        agg_rows = (
            CampaignContact.objects.filter(campaign=campaign)
            .values("step_id")
            .annotate(
                total=Count("id"),
                pending=Count("id", filter=Q(status=CampaignContact.Status.PENDING)),
                queued=Count("id", filter=Q(status=CampaignContact.Status.QUEUED)),
                sent=Count("id", filter=Q(status=CampaignContact.Status.SENT)),
                failed=Count("id", filter=Q(status=CampaignContact.Status.FAILED)),
                skipped_opt_out=Count(
                    "id", filter=Q(status=CampaignContact.Status.SKIPPED_OPT_OUT)
                ),
                blacklisted=Count(
                    "id", filter=Q(status=CampaignContact.Status.BLACKLISTED)
                ),
            )
        )
        by_step = {r["step_id"]: r for r in agg_rows}
        steps_out = []
        for step in campaign.steps.all().order_by("order_index"):
            row = by_step.get(step.id, {})
            steps_out.append(
                {
                    "step_id": step.id,
                    "order_index": step.order_index,
                    "channel": step.channel,
                    "template_code": step.template_code,
                    "delay_amount": step.delay_amount,
                    "delay_unit": step.delay_unit,
                    "active": step.active,
                    "messaging_provider_id": step.messaging_provider_id,
                    "counters": {
                        "total": row.get("total") or 0,
                        "pending": row.get("pending") or 0,
                        "queued": row.get("queued") or 0,
                        "sent": row.get("sent") or 0,
                        "failed": row.get("failed") or 0,
                        "skipped_opt_out": row.get("skipped_opt_out") or 0,
                        "blacklisted": row.get("blacklisted") or 0,
                    },
                }
            )
        audience_count = count_campaign_audience(campaign)
        return self.get_response(
            data={
                "campaign_id": campaign.id,
                "status": campaign.status,
                "audience_count": audience_count,
                "counters": counters,
                "steps": steps_out,
            },
            status="success",
        )


class CampaignStepViewSet(viewsets.ModelViewSet, StandardResponseMixin, LoggingMixin):
    """
    Step 4: Campaign Steps

    Attach one or more steps (Email/SMS, templates, delays) to a campaign.
    """

    queryset = CampaignStep.objects.all().select_related("campaign", "messaging_provider")
    serializer_class = CampaignStepSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "post", "put", "patch", "delete"]
    swagger_tags = ["3. Campaigns & Steps"]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["campaign", "channel", "active"]
    search_fields = ["template_code"]
    ordering_fields = ["order_index", "created_at", "campaign"]
    ordering = ["campaign_id", "order_index"]

    @swagger_auto_schema(
        operation_summary="List campaign steps",
        manual_parameters=[
            openapi.Parameter("offset", openapi.IN_QUERY, type=openapi.TYPE_INTEGER),
            openapi.Parameter("limit", openapi.IN_QUERY, type=openapi.TYPE_INTEGER),
            openapi.Parameter("campaign", openapi.IN_QUERY, type=openapi.TYPE_INTEGER),
            openapi.Parameter("channel", openapi.IN_QUERY, type=openapi.TYPE_STRING),
            openapi.Parameter("active", openapi.IN_QUERY, type=openapi.TYPE_BOOLEAN),
        ],
        responses={200: "Standard envelope"},
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

    def retrieve(self, request, *args, **kwargs):
        self.log_request(request)
        response = super().retrieve(request, *args, **kwargs)
        if response.status_code != status.HTTP_200_OK:
            return self.get_response(
                data=None,
                message="Error occurred",
                status_code=response.status_code,
                is_error=True,
                status="error",
            )
        return self.get_response(
            data=response.data,
            message="Item Retrieved",
            status="success",
            status_code=status.HTTP_200_OK,
        )

    def create(self, request, *args, **kwargs):
        self.log_request(request)
        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            return self.get_error_response(
                message="Validation error",
                status="error",
                errors=self.custom_serializer_error(serializer.errors),
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        self.perform_create(serializer)
        return self.get_response(
            data=serializer.data,
            message="Campaign step created",
            status="success",
            status_code=status.HTTP_201_CREATED,
        )

    def update(self, request, *args, **kwargs):
        self.log_request(request)
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        if not serializer.is_valid():
            return self.get_error_response(
                message="Validation error",
                status="error",
                errors=self.custom_serializer_error(serializer.errors),
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        self.perform_update(serializer)
        return self.get_response(
            data=serializer.data,
            message="Campaign step updated",
            status="success",
            status_code=status.HTTP_200_OK,
        )

    def partial_update(self, request, *args, **kwargs):
        kwargs["partial"] = True
        return self.update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        self.log_request(request)
        instance = self.get_object()
        instance.delete()
        return self.get_response(
            data=None,
            message="Campaign step deleted",
            status="success",
            status_code=status.HTTP_200_OK,
        )


class MessageLogViewSet(viewsets.ReadOnlyModelViewSet, StandardResponseMixin, LoggingMixin):
    """
    Step 6: Monitoring & Analytics

    Inspect individual message logs for debugging and analytics.
    """

    queryset = MessageLog.objects.all().select_related("contact", "campaign", "step")
    serializer_class = MessageLogSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ["get"]
    swagger_tags = ["5. Monitoring & Analytics"]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["campaign", "step", "contact", "channel", "status"]
    ordering_fields = ["created_at", "sent_at", "status", "channel"]
    ordering = ["-created_at"]

    @swagger_auto_schema(
        operation_summary="List message logs (filters, pagination)",
        manual_parameters=[
            openapi.Parameter("offset", openapi.IN_QUERY, type=openapi.TYPE_INTEGER),
            openapi.Parameter("limit", openapi.IN_QUERY, type=openapi.TYPE_INTEGER),
            openapi.Parameter("campaign", openapi.IN_QUERY, type=openapi.TYPE_INTEGER),
            openapi.Parameter("step", openapi.IN_QUERY, type=openapi.TYPE_INTEGER),
            openapi.Parameter("contact", openapi.IN_QUERY, type=openapi.TYPE_INTEGER),
            openapi.Parameter("channel", openapi.IN_QUERY, type=openapi.TYPE_STRING),
            openapi.Parameter("status", openapi.IN_QUERY, type=openapi.TYPE_STRING),
        ],
        responses={200: "Standard envelope"},
    )
    def list(self, request, *args, **kwargs):
        self.log_request(request)
        queryset = self.filter_queryset(self.get_queryset())
        count, paginated_queryset = paginate_queryset(request, queryset)
        serializer = self.get_serializer(paginated_queryset, many=True)
        return self.get_response(
            data=serializer.data,
            message="List Retrieved",
            count=count,
            status="success",
            status_code=status.HTTP_200_OK,
        )

    def retrieve(self, request, *args, **kwargs):
        self.log_request(request)
        response = super().retrieve(request, *args, **kwargs)
        if response.status_code != status.HTTP_200_OK:
            return self.get_response(
                data=None,
                message="Error occurred",
                status_code=response.status_code,
                is_error=True,
                status="error",
            )
        return self.get_response(
            data=response.data,
            message="Item Retrieved",
            status="success",
            status_code=status.HTTP_200_OK,
        )


class SmsTemplateViewSet(viewsets.ModelViewSet, StandardResponseMixin, LoggingMixin):
    """
    SMS / DLT templates (MessageTemplate): CRUD, filters, and catalog for campaign steps.

    Query **for_campaigns=true** to list only **active** templates with types allowed on
    campaign SMS steps (**service_explicit**, **promotional**).
    """

    queryset = MessageTemplate.objects.all().order_by("-updated_at")
    serializer_class = SmsTemplateSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "post", "put", "patch", "delete"]
    swagger_tags = ["2. Templates & Variables"]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["template_code", "template_type", "is_active", "message_id"]
    search_fields = ["name", "template_code", "message_id", "template_message"]
    ordering_fields = [
        "id",
        "template_code",
        "message_id",
        "name",
        "template_type",
        "is_active",
        "created_at",
        "updated_at",
    ]
    ordering = ["-updated_at"]

    _SMS_LIST_PARAMS = [
        openapi.Parameter("offset", openapi.IN_QUERY, type=openapi.TYPE_INTEGER),
        openapi.Parameter("limit", openapi.IN_QUERY, type=openapi.TYPE_INTEGER),
        openapi.Parameter("search", openapi.IN_QUERY, type=openapi.TYPE_STRING),
        openapi.Parameter("ordering", openapi.IN_QUERY, type=openapi.TYPE_STRING),
        openapi.Parameter("template_code", openapi.IN_QUERY, type=openapi.TYPE_STRING),
        openapi.Parameter("message_id", openapi.IN_QUERY, type=openapi.TYPE_STRING),
        openapi.Parameter(
            "template_type",
            openapi.IN_QUERY,
            type=openapi.TYPE_STRING,
            description="transactional | service_implicit | service_explicit | promotional",
        ),
        openapi.Parameter("is_active", openapi.IN_QUERY, type=openapi.TYPE_BOOLEAN),
        openapi.Parameter(
            "for_campaigns",
            openapi.IN_QUERY,
            type=openapi.TYPE_BOOLEAN,
            description="If true, only active service_explicit + promotional (campaign picker).",
        ),
    ]

    def get_queryset(self):
        qs = super().get_queryset()
        raw = (self.request.query_params.get("for_campaigns") or "").lower()
        if raw in ("1", "true", "yes"):
            return qs.filter(
                is_active=True,
                template_type__in=MessageTemplate.CAMPAIGN_ALLOWED_TYPES,
            )
        return qs

    @swagger_auto_schema(
        operation_summary="List SMS templates (filters, search, sort, pagination)",
        operation_description=(
            "Pagination: offset, limit.\n"
            "Search: name, template_code, message_id, template_message.\n"
            "Filters: template_code, message_id, template_type, is_active.\n"
            "**for_campaigns=true**: only templates eligible for messaging campaign SMS steps."
        ),
        manual_parameters=_SMS_LIST_PARAMS,
        responses={200: "Standard envelope"},
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
            message="SMS template created",
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
            message="SMS template updated",
            status="success",
            status_code=status.HTTP_200_OK,
        )
        self.log_response(custom)
        return custom

    def partial_update(self, request, *args, **kwargs):
        kwargs["partial"] = True
        return self.update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        self.log_request(request)
        instance = self.get_object()
        instance.delete()
        custom = self.get_response(
            data=None,
            message="SMS template deleted successfully",
            status="success",
            status_code=status.HTTP_200_OK,
        )
        self.log_response(custom)
        return custom


class MessagingProviderConfigViewSet(
    viewsets.ModelViewSet, StandardResponseMixin, LoggingMixin
):
    """
    Custom email (SMTP) and SMS (Fast2SMS) provider rows used by campaign steps,
    email templates, and test sends. When unset, the API falls back to the default
    row for that channel (if any), then to server environment variables.
    """

    queryset = MessagingProviderConfig.objects.all().order_by("channel", "name")
    serializer_class = MessagingProviderConfigSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "post", "put", "patch", "delete"]
    swagger_tags = ["2. Templates & Variables"]

    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["channel", "active", "is_default"]
    search_fields = ["name"]
    ordering_fields = ["created_at", "updated_at", "name", "channel"]
    ordering = ["channel", "name"]

    @swagger_auto_schema(
        method="get",
        operation_summary="How to obtain SMTP and Fast2SMS credentials",
        operation_description=(
            "Short admin copy: `general` and per-field `hint` only (no long prose)."
        ),
        responses={200: "Standard response: { general, email, sms }"},
    )
    @action(detail=False, methods=["get"], url_path="credential-guidance")
    def credential_guidance_action(self, request):
        return self.get_response(data=credential_guidance(), status="success")

    @swagger_auto_schema(
        operation_summary="List messaging provider configs",
        manual_parameters=[
            openapi.Parameter("offset", openapi.IN_QUERY, type=openapi.TYPE_INTEGER),
            openapi.Parameter("limit", openapi.IN_QUERY, type=openapi.TYPE_INTEGER),
            openapi.Parameter("channel", openapi.IN_QUERY, type=openapi.TYPE_STRING),
            openapi.Parameter("active", openapi.IN_QUERY, type=openapi.TYPE_BOOLEAN),
            openapi.Parameter("is_default", openapi.IN_QUERY, type=openapi.TYPE_BOOLEAN),
            openapi.Parameter("search", openapi.IN_QUERY, type=openapi.TYPE_STRING),
        ],
        responses={200: "Standard response envelope with list"},
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

    def retrieve(self, request, *args, **kwargs):
        self.log_request(request)
        response = super().retrieve(request, *args, **kwargs)
        if response.status_code != status.HTTP_200_OK:
            return self.get_response(
                data=None,
                message="Error occurred",
                status_code=response.status_code,
                is_error=True,
                status="error",
            )
        return self.get_response(
            data=response.data,
            message="Item Retrieved",
            status="success",
            status_code=status.HTTP_200_OK,
        )

    def create(self, request, *args, **kwargs):
        self.log_request(request)
        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            return self.get_error_response(
                message="Validation error",
                status="error",
                errors=self.custom_serializer_error(serializer.errors),
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        self.perform_create(serializer)
        return self.get_response(
            data=serializer.data,
            message="Provider config created",
            status="success",
            status_code=status.HTTP_201_CREATED,
        )

    def update(self, request, *args, **kwargs):
        self.log_request(request)
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        if not serializer.is_valid():
            return self.get_error_response(
                message="Validation error",
                status="error",
                errors=self.custom_serializer_error(serializer.errors),
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        self.perform_update(serializer)
        return self.get_response(
            data=serializer.data,
            message="Provider config updated",
            status="success",
            status_code=status.HTTP_200_OK,
        )

    def partial_update(self, request, *args, **kwargs):
        kwargs["partial"] = True
        return self.update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        self.log_request(request)
        instance = self.get_object()
        instance.delete()
        return self.get_response(
            data=None,
            message="Provider config deleted",
            status="success",
            status_code=status.HTTP_200_OK,
        )


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


class MessagingTestViewSet(viewsets.ViewSet, StandardResponseMixin, LoggingMixin):
    """
    Utilities: send test messages without campaigns.
    """

    permission_classes = [IsAuthenticated]
    swagger_tags = ["4. Execution (Send & Schedule)"]

    @swagger_auto_schema(
        method="post",
        operation_summary="Send a test SMS (Fast2SMS template)",
        operation_description=(
            "Send a test SMS using a provider template_code.\n\n"
            "Provide either phone, or contact_id (uses contact.phone). "
            "You can send `variables_values` directly (recommended), or pass `variables` to build a pipe string."
        ),
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=["template_code"],
            properties={
                "template_code": openapi.Schema(type=openapi.TYPE_STRING, description="Fast2SMS template code."),
                "phone": openapi.Schema(type=openapi.TYPE_STRING, description="Recipient phone (digits/+)."),
                "contact_id": openapi.Schema(type=openapi.TYPE_INTEGER, description="Contact id to use as context."),
                "variables_values": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description="Pipe-separated values in provider-expected order.",
                ),
                "variables": openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    description="Override variables to build variables_values if variables_values is not provided.",
                    additional_properties=openapi.Schema(type=openapi.TYPE_STRING),
                ),
                "messaging_provider_id": openapi.Schema(
                    type=openapi.TYPE_INTEGER,
                    description="Optional. SMS MessagingProviderConfig (Fast2SMS) to use instead of environment defaults.",
                ),
            },
        ),
        responses={200: "Standard response: provider response"},
    )
    @action(detail=False, methods=["post"], url_path="sms/send-test")
    def send_test_sms(self, request):
        self.log_request(request)
        template_code = (request.data.get("template_code") or "").strip()
        phone = (request.data.get("phone") or "").strip()
        contact_id = request.data.get("contact_id")
        variables_values = (request.data.get("variables_values") or "").strip()
        overrides = request.data.get("variables") or {}

        if not template_code:
            return self.get_error_response(
                message="template_code is required",
                status="error",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        if overrides is not None and not isinstance(overrides, dict):
            return self.get_error_response(
                message="variables must be an object",
                status="error",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        contact = None
        if contact_id is not None:
            try:
                contact = Contact.objects.get(pk=int(contact_id))
            except Exception:
                return self.get_error_response(
                    message="Invalid contact_id",
                    status="error",
                    status_code=status.HTTP_400_BAD_REQUEST,
                )

        if not phone and contact and contact.phone:
            phone = contact.phone
        phone_norm = normalize_phone(phone)
        if not phone_norm:
            return self.get_error_response(
                message="phone is required (or provide contact_id with phone)",
                status="error",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        if not variables_values:
            variables = build_template_variables(contact) if contact else {}
            variables.update(overrides)
            # remove nested objects and non-primitive keys
            for k in ("contact", "user", "company", "agent"):
                variables.pop(k, None)
            # deterministic but may not match provider expected order; prefer variables_values input
            variables_values = "|".join(str(variables[k]) for k in sorted(variables.keys()) if variables.get(k) not in (None, ""))

        raw_pid = request.data.get("messaging_provider_id")
        override_provider_id = None
        if raw_pid is not None and raw_pid != "":
            try:
                override_provider_id = int(raw_pid)
            except (TypeError, ValueError):
                return self.get_error_response(
                    message="messaging_provider_id must be an integer",
                    status="error",
                    status_code=status.HTTP_400_BAD_REQUEST,
                )

        try:
            sms_cfg = resolve_sms_config_for_test(override_provider_id)
        except ValueError as exc:
            return self.get_error_response(
                message=str(exc),
                status="error",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        try:
            resp = send_template_sms(
                mobile_number=phone_norm,
                template_code=template_code,
                variables_values=variables_values,
                sms_config=sms_cfg,
            )
            data: Dict[str, Any] = {
                "phone": phone_norm,
                "template_code": template_code,
                "variables_values": variables_values,
                "provider_status_code": getattr(resp, "status_code", None),
            }
            try:
                data["provider_response"] = resp.json() if resp is not None else None
            except Exception:
                data["provider_response"] = None
        except Exception as exc:
            return self.get_error_response(
                message=f"Failed to send test SMS: {exc}",
                status="error",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        return self.get_response(
            data=data,
            message="Test SMS sent",
            status="success",
            status_code=status.HTTP_200_OK,
        )

