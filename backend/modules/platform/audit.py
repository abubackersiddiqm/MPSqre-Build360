import uuid
from dataclasses import dataclass, field
from typing import Any

from django.http import HttpRequest
from django.utils import timezone

from .models import AuditEvent


@dataclass(frozen=True, slots=True)
class AuditRecord:
    action: str
    entity_type: str
    request_id: uuid.UUID
    correlation_id: uuid.UUID
    actor_public_id: uuid.UUID | None = None
    company_public_id: uuid.UUID | None = None
    entity_public_id: uuid.UUID | None = None
    actor_type: str = "user"
    ip_address: str | None = None
    user_agent: str = ""
    reason_code: str = ""
    before: dict[str, Any] = field(default_factory=dict)
    after: dict[str, Any] = field(default_factory=dict)


def request_metadata(request: HttpRequest) -> tuple[uuid.UUID, str | None, str]:
    request_id = getattr(request, "request_id", uuid.uuid4())
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    ip_address = forwarded.split(",", 1)[0].strip() or request.META.get("REMOTE_ADDR")
    user_agent = request.META.get("HTTP_USER_AGENT", "")[:500]
    return request_id, ip_address, user_agent


def append_audit(record: AuditRecord) -> AuditEvent:
    return AuditEvent.objects.create(
        company_public_id=record.company_public_id,
        actor_type=record.actor_type,
        actor_public_id=record.actor_public_id,
        action=record.action,
        entity_type=record.entity_type,
        entity_public_id=record.entity_public_id,
        occurred_at=timezone.now(),
        request_id=record.request_id,
        correlation_id=record.correlation_id,
        ip_address=record.ip_address,
        user_agent=record.user_agent,
        reason_code=record.reason_code,
        before=record.before,
        after=record.after,
    )

