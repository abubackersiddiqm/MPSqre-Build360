import uuid
from datetime import timedelta

import pytest
from django.utils import timezone

from modules.platform.events import EventRecord, append_event
from modules.platform.outbox import claim_due_events, mark_failed, mark_published


@pytest.mark.django_db
def test_outbox_claim_publish_and_dead_letter() -> None:
    first = append_event(
        EventRecord(
            event_type="test.first",
            aggregate_type="test",
            aggregate_public_id=uuid.uuid4(),
            aggregate_version=1,
            correlation_id=uuid.uuid4(),
        )
    )
    claimed = claim_due_events(batch_size=10)
    assert [event.public_id for event in claimed] == [first.public_id]
    first_lock_token = claimed[0].lock_token
    assert first_lock_token is not None

    mark_failed(
        event_public_id=first.public_id,
        lock_token=first_lock_token,
        error="provider unavailable",
        max_attempts=2,
    )
    first.refresh_from_db()
    assert first.attempts == 1
    assert first.next_attempt_at is not None
    first.next_attempt_at = timezone.now() - timedelta(seconds=1)
    first.save(update_fields=["next_attempt_at"])

    claimed = claim_due_events(batch_size=10)
    retry_lock_token = claimed[0].lock_token
    assert retry_lock_token is not None
    mark_failed(
        event_public_id=first.public_id,
        lock_token=retry_lock_token,
        error="provider unavailable",
        max_attempts=2,
    )
    first.refresh_from_db()
    assert first.dead_lettered_at is not None


@pytest.mark.django_db
def test_outbox_marks_published_only_with_claim_token() -> None:
    event = append_event(
        EventRecord(
            event_type="test.published",
            aggregate_type="test",
            aggregate_public_id=uuid.uuid4(),
            aggregate_version=1,
            correlation_id=uuid.uuid4(),
        )
    )
    claimed = claim_due_events(batch_size=1)[0]
    lock_token = claimed.lock_token
    assert lock_token is not None
    mark_published(event_public_id=event.public_id, lock_token=lock_token)
    event.refresh_from_db()
    assert event.published_at is not None
    assert event.lock_token is None
