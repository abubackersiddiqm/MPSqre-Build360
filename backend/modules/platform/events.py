import uuid
from dataclasses import dataclass, field
from typing import Any

from django.utils import timezone

from .models import BusinessEventOutbox


@dataclass(frozen=True, slots=True)
class EventRecord:
    event_type: str
    aggregate_type: str
    aggregate_public_id: uuid.UUID
    aggregate_version: int
    correlation_id: uuid.UUID
    company_public_id: uuid.UUID | None = None
    causation_id: uuid.UUID | None = None
    event_version: int = 1
    payload: dict[str, Any] = field(default_factory=dict)


def append_event(record: EventRecord) -> BusinessEventOutbox:
    return BusinessEventOutbox.objects.create(
        company_public_id=record.company_public_id,
        aggregate_type=record.aggregate_type,
        aggregate_public_id=record.aggregate_public_id,
        aggregate_version=record.aggregate_version,
        event_type=record.event_type,
        event_version=record.event_version,
        payload=record.payload,
        occurred_at=timezone.now(),
        correlation_id=record.correlation_id,
        causation_id=record.causation_id,
    )

