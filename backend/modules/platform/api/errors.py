from typing import Any

from rest_framework.response import Response
from rest_framework.views import exception_handler


def api_exception_handler(exc: Exception, context: dict[str, Any]) -> Response | None:
    response = exception_handler(exc, context)
    if response is None:
        return None
    request = context.get("request")
    request_id = str(getattr(request, "request_id", ""))
    detail = response.data
    response.data = {
        "code": f"API-{response.status_code}",
        "message": "The request could not be completed.",
        "field_errors": detail if isinstance(detail, dict) else {},
        "details": [] if isinstance(detail, dict) else detail,
        "request_id": request_id,
        "retryable": response.status_code in {429, 502, 503, 504},
    }
    return response

