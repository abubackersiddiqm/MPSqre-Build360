import uuid
from collections.abc import Callable

from django.http import HttpRequest, HttpResponse

REQUEST_ID_HEADER = "HTTP_X_REQUEST_ID"


class CorrelationIdMiddleware:
    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        raw_request_id = request.META.get(REQUEST_ID_HEADER)
        try:
            request_id = uuid.UUID(raw_request_id) if raw_request_id else uuid.uuid4()
        except (TypeError, ValueError, AttributeError):
            request_id = uuid.uuid4()
        request.request_id = request_id  # type: ignore[attr-defined]
        response = self.get_response(request)
        response["X-Request-Id"] = str(request_id)
        return response
