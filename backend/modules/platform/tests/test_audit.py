import uuid

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from modules.platform.models import AuditEvent


@pytest.mark.django_db
def test_audit_event_cannot_be_updated_or_deleted() -> None:
    event = AuditEvent.objects.create(
        actor_type="system",
        action="test.created",
        entity_type="test",
        occurred_at=timezone.now(),
        request_id=uuid.uuid4(),
        correlation_id=uuid.uuid4(),
    )
    event.reason_code = "changed"

    with pytest.raises(ValidationError, match="append-only"):
        event.save()
    with pytest.raises(ValidationError, match="append-only"):
        event.delete()

