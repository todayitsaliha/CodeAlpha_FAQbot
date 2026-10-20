"""Global error handling: one consistent {status, message, requestId} shape."""

import logging
import uuid

from flask import Flask, g, jsonify
from werkzeug.exceptions import HTTPException

from app.services.chatbot_service import InvalidMessageError

logger = logging.getLogger(__name__)

UNEXPECTED_ERROR = "An unexpected error occurred. Please try again later."
NOT_READY = "The chatbot is not ready yet. Please try again later."
_HTTP_MESSAGES = {
    404: "Resource not found.",
    405: "Method not allowed.",
    413: "Request body is too large.",
}


class ApiError(Exception):
    """An error the API deliberately reports to the client."""

    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


def error_response(status: int, message: str):
    request_id = getattr(g, "request_id", None) or str(uuid.uuid4())
    return jsonify(status=status, message=message, requestId=request_id), status


def register_error_handlers(app: Flask) -> None:
    @app.errorhandler(ApiError)
    def handle_api_error(error: ApiError):
        return error_response(error.status, error.message)

    @app.errorhandler(InvalidMessageError)
    def handle_invalid_message(error: InvalidMessageError):
        return error_response(400, str(error))

    @app.errorhandler(HTTPException)
    def handle_http_error(error: HTTPException):
        status = error.code or 500
        response, _ = error_response(
            status, _HTTP_MESSAGES.get(status, error.name or "Request failed.")
        )
        response.headers.extend(
            (k, v) for k, v in error.get_headers() if k.lower() == "allow"
        )
        return response, status

    @app.errorhandler(Exception)
    def handle_unexpected_error(error: Exception):
        # Full stack trace goes to the log; the client only sees a generic message.
        logger.exception("Unhandled error while processing request")
        return error_response(500, UNEXPECTED_ERROR)
