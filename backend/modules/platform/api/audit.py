from django.utils.dateparse import parse_datetime
from rest_framework.exceptions import ValidationError
from rest_framework.request import Request
from rest_framework.response import Response

from modules.platform.models import AuditEvent
from modules.tenant.api.base import TenantScopedAPIView


class AuditEventListView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("audit.read")
        try:
            limit = min(100, max(1, int(request.query_params.get("limit", "50"))))
        except ValueError as exc:
            raise ValidationError("limit must be an integer") from exc
        queryset = AuditEvent.objects.filter(
            company_public_id=self.tenant_context.company.public_id
        ).order_by("-occurred_at", "-pk")
        action = request.query_params.get("action")
        entity_type = request.query_params.get("entity_type")
        before = request.query_params.get("before")
        if action:
            queryset = queryset.filter(action=action[:200])
        if entity_type:
            queryset = queryset.filter(entity_type=entity_type[:100])
        if before:
            parsed = parse_datetime(before)
            if parsed is None:
                raise ValidationError("before must be an ISO-8601 datetime")
            queryset = queryset.filter(occurred_at__lt=parsed)
        events = list(queryset[:limit])
        return Response(
            {
                "items": [
                    {
                        "public_id": str(event.public_id),
                        "action": event.action,
                        "entity_type": event.entity_type,
                        "entity_public_id": (
                            str(event.entity_public_id) if event.entity_public_id else None
                        ),
                        "actor_type": event.actor_type,
                        "actor_public_id": (
                            str(event.actor_public_id) if event.actor_public_id else None
                        ),
                        "occurred_at": event.occurred_at.isoformat(),
                        "correlation_id": str(event.correlation_id),
                        "reason_code": event.reason_code,
                    }
                    for event in events
                ],
                "next_before": events[-1].occurred_at.isoformat() if len(events) == limit else None,
            }
        )
