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
        """
        Pure proxy endpoint - passes request to AirIQ API and returns raw response.
        Only injects AgentInfo if missing in the payload.
        """
        try:
            payload = request.data if isinstance(request.data, dict) else {}
            resp, ok = airiq_service.proxy_call(endpoint, payload)
            # Return raw AirIQ response - don't wrap it
            http_status = status.HTTP_200_OK if ok else status.HTTP_400_BAD_REQUEST
            return Response(resp, status=http_status)
        except AirIQException as e:
            # Log the actual error for debugging
            self.log_error(f"AirIQ proxy error for endpoint {endpoint}: {str(e)}")
            # Return error in AirIQ format if possible
            error_response = {
                "Status": {
                    "ResultCode": "0",
                    "Error": str(e),
                    "SequenceID": ""
                }
            }
            return Response(error_response, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            # Log the actual error for debugging
            self.log_error(f"AirIQ proxy unexpected error for endpoint {endpoint}: {str(e)}", exc_info=True)
            # Return error in AirIQ format
            error_response = {
                "Status": {
                    "ResultCode": "-1",
                    "Error": f"EX-{str(e)}",
                    "SequenceID": ""
                }
            }
            return Response(error_response, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
