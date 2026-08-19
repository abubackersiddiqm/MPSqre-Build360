from django.core.cache import cache
from django.db import connection
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView


class LiveView(APIView):
    permission_classes = [AllowAny]

    def get(self, request: Request) -> Response:
        return Response({"status": "ok"})


class ReadyView(APIView):
    permission_classes = [AllowAny]

    def get(self, request: Request) -> Response:
        dependencies: dict[str, str] = {}
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
            dependencies["database"] = "ok"
        except Exception:
            dependencies["database"] = "unavailable"

        try:
            cache.set("health:ready", "ok", timeout=5)
            dependencies["cache"] = "ok" if cache.get("health:ready") == "ok" else "unavailable"
        except Exception:
            dependencies["cache"] = "unavailable"

        ready = all(value == "ok" for value in dependencies.values())
        return Response(
            {"status": "ok" if ready else "unavailable", "dependencies": dependencies},
            status=200 if ready else 503,
        )
