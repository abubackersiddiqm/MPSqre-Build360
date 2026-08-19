from __future__ import annotations

import logging
import os
import time
import uuid
from collections.abc import Callable

from django.http import HttpRequest, HttpResponse

logger = logging.getLogger("build360.performance")


class RequestTimingMiddleware:
    """Adds response timing evidence and emits structured slow-request warnings."""

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response
        self.slow_threshold_ms = max(1, int(os.getenv("BUILD360_SLOW_REQUEST_MS", "1000")))

    def __call__(self, request: HttpRequest) -> HttpResponse:
        started = time.perf_counter()
        response = self.get_response(request)
        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        request_id = getattr(request, "request_id", None) or uuid.uuid4()

        response["X-Request-ID"] = str(request_id)
        response["X-Response-Time-Ms"] = f"{duration_ms:.2f}"
        existing = response.get("Server-Timing")
        timing = f"app;dur={duration_ms:.2f}"
        response["Server-Timing"] = f"{existing}, {timing}" if existing else timing

        if duration_ms >= self.slow_threshold_ms and not request.path.startswith("/static/"):
            logger.warning(
                "slow_request",
                extra={
                    "request_id": str(request_id),
                    "method": request.method,
                    "path": request.path,
                    "status_code": response.status_code,
                    "duration_ms": duration_ms,
                    "threshold_ms": self.slow_threshold_ms,
                },
            )
        return response
