from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from IDBOOKAPI.mixins import StandardResponseMixin, LoggingMixin
from .services.airiq_service import airiq_service, AirIQException


class AirIQProxyViewSet(viewsets.ViewSet, StandardResponseMixin, LoggingMixin):
    """
    Generic proxy for AirIQ API endpoints.
    - No auth required: handles AirIQ login/token internally
    - Injects AgentInfo automatically if missing
    - Call with: POST /api/v1/flights/airiq-proxy/<EndpointName>/
      Example: POST /api/v1/flights/airiq-proxy/Availability/
    """

    permission_classes = [AllowAny]

    @action(detail=False, methods=["get"], url_path="endpoints")
    def list_endpoints(self, request):
        mapping = airiq_service.get_supported_endpoints()
        return self.get_response(
            data={"endpoints": list(mapping.keys())},
            message="Supported AirIQ endpoints",
            status="success",
            status_code=status.HTTP_200_OK,
        )

    @action(detail=False, methods=["post"], url_path=r"(?P<endpoint>[^/]+)")
    def proxy(self, request, endpoint=None):
        try:
            payload = request.data if isinstance(request.data, dict) else {}
            resp, ok = airiq_service.proxy_call(endpoint, payload)
            http_status = status.HTTP_200_OK if ok else status.HTTP_400_BAD_REQUEST
            return Response(resp, status=http_status)
        except AirIQException as e:
            return self.get_error_response(
                message=str(e),
                status="error",
                error_code="AIRIQ_PROXY_ERROR",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            return self.get_error_response(
                message="Unexpected error",
                status="error",
                error_code="AIRIQ_PROXY_UNEXPECTED",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
