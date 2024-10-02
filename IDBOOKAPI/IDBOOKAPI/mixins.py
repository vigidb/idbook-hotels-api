from rest_framework.response import Response
from rest_framework import status
import logging


def generate_response(data=None, message="", status_code='', is_error=False, status=''):
    if data is None:
        data = []
    response = {
        'status': status,
        # 'code': status_code,
        'message': message,
        'data': data
    }
    return Response(response, status=status_code)

def generate_error_response(errors, message, error_code, status, status_code):
    response = {
        'status': status,
        'message': message,
        'errors': errors,
        'errorCode':error_code
    }
    return Response(response, status=status_code)



class StandardResponseMixin:
    def get_response(self, data=None, message="", status_code=status.HTTP_200_OK, is_error=False, status=''):
        return generate_response(data, message, status_code, is_error, status)

    def get_error_response(self, message="", status='', errors=[],
                           error_code="", status_code=status.HTTP_401_UNAUTHORIZED):
        return generate_error_response(errors, message, error_code, status, status_code)


class LoggingMixin:
    logger = logging.getLogger(__name__)

    def log_request(self, request):
        user_info = f"User: {request.user}" if request.user.is_authenticated else "Anonymous User"
        self.logger.info(
            f"Request: {request.method} {request.get_full_path()} | {user_info}"
        )

    def log_response(self, response):
        self.logger.info(
            f"Response: {response.status_code}"
        )

    # def log_request(self, request):
    #     self.logger.info(
    #         f"Request: {request.method} {request.get_full_path()} | "
    #         f"Data: {request.data} | "
    #         f"User: {request.user}"
    #     )
    #
    # def log_response(self, response):
    #     self.logger.info(
    #         f"Response: {response.status_code} | "
    #         f"Data: {response.data}"
    #     )
