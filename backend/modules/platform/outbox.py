from __future__ import annotations

import uuid
from datetime import timedelta
from typing import Protocol

from django.db import connection, transaction
from django.db.models import Q
from django.utils import timezone

from modules.platform.models import BusinessEventOutbox


class EventPublisher(Protocol):
    def publish(self, event: BusinessEventOutbox) -> None: ...


@transaction.atomic
def claim_due_events(*, batch_size: int = 100) -> list[BusinessEventOutbox]:
    if batch_size < 1 or batch_size > 500:
        raise ValueError("batch_size must be between 1 and 500")
    now = timezone.now()
    stale_before = now - timedelta(minutes=5)
    queryset = BusinessEventOutbox.objects.filter(
        published_at__isnull=True,
        dead_lettered_at__isnull=True,
    ).filter(
        Q(next_attempt_at__isnull=True) | Q(next_attempt_at__lte=now)
    ).filter(
        Q(locked_at__isnull=True) | Q(locked_at__lt=stale_before)
    ).order_by("occurred_at", "pk")
    queryset = (
        queryset.select_for_update(skip_locked=True)
        if connection.features.has_select_for_update_skip_locked
        else queryset.select_for_update()
    )
    events = list(queryset[:batch_size])
    token = uuid.uuid4()
    for event in events:
        event.locked_at = now
        event.lock_token = token
    if events:
        BusinessEventOutbox.objects.bulk_update(events, ["locked_at", "lock_token"])
    return events


@transaction.atomic
def mark_published(*, event_public_id: uuid.UUID, lock_token: uuid.UUID) -> None:
    event = BusinessEventOutbox.objects.select_for_update().get(
        public_id=event_public_id,
        lock_token=lock_token,
        published_at__isnull=True,
        dead_lettered_at__isnull=True,
    )
    event.published_at = timezone.now()
    event.locked_at = None
    event.lock_token = None
    event.last_error = ""
    event.save(
        update_fields=["published_at", "locked_at", "lock_token", "last_error"]
    )


@transaction.atomic
def mark_failed(
    *,
    event_public_id: uuid.UUID,
    lock_token: uuid.UUID,
    error: str,
    max_attempts: int = 8,
) -> BusinessEventOutbox:
    event = BusinessEventOutbox.objects.select_for_update().get(
        public_id=event_public_id,
        lock_token=lock_token,
        published_at__isnull=True,
        dead_lettered_at__isnull=True,
    )
    event.attempts += 1
    event.last_error = error[:1000]
    event.locked_at = None
    event.lock_token = None
    if event.attempts >= max_attempts:
        event.dead_lettered_at = timezone.now()
        event.next_attempt_at = None
    else:
        delay_seconds = min(3600, 2 ** min(event.attempts, 12) * 15)
        event.next_attempt_at = timezone.now() + timedelta(seconds=delay_seconds)
    event.save(
        update_fields=[
            "attempts",
            "last_error",
            "locked_at",
            "lock_token",
            "dead_lettered_at",
            "next_attempt_at",
        ]
    )
    return event


def publish_claimed_batch(*, publisher: EventPublisher, batch_size: int = 100) -> int:
    published = 0
    for event in claim_due_events(batch_size=batch_size):
        assert event.lock_token is not None
        try:
            publisher.publish(event)
        except Exception as exc:  # noqa: BLE001 - boundary records and retries provider errors
            mark_failed(
                event_public_id=event.public_id,
                lock_token=event.lock_token,
                error=f"{type(exc).__name__}: {exc}",
            )
        else:
            mark_published(event_public_id=event.public_id, lock_token=event.lock_token)
            published += 1
    return published
