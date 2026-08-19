from __future__ import annotations

import uuid
from datetime import datetime

from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.db import transaction
from django.utils import timezone
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode

from modules.identity.models import AuthSession, RefreshToken, User
from modules.platform.audit import AuditRecord, append_audit
from modules.platform.events import EventRecord, append_event


class LatestOnlyPasswordResetTokenGenerator(PasswordResetTokenGenerator):
    """A reset token invalidated by a newer reset request or password change."""

    def _make_hash_value(self, user: User, timestamp: int) -> str:
        login_timestamp = (
            "" if user.last_login is None else user.last_login.replace(microsecond=0, tzinfo=None)
        )
        security_timestamp = (
            ""
            if user.last_security_event_at is None
            else user.last_security_event_at.isoformat()
        )
        return (
            f"{user.pk}{user.password}{login_timestamp}{timestamp}"
            f"{user.email}{user.is_active}{security_timestamp}"
        )


password_reset_token_generator = LatestOnlyPasswordResetTokenGenerator()


def _security_event_aggregate_version(at: datetime) -> int:
    """Use the persisted security-event time as an ordered outbox aggregate version.

    Password-reset requests are repeatable commands. A hard-coded aggregate version
    makes the outbox unique-fact constraint reject the second request for the same user.
    The microsecond timestamp pattern is already used by Build360 access-control events
    for repeatable state transitions.
    """
    return max(1, int(at.timestamp() * 1_000_000))


@transaction.atomic
def issue_password_reset_token(*, user: User, correlation_id: uuid.UUID) -> tuple[str, str]:
    """Issue a latest-only password-reset token without storing the raw token."""
    locked = User.objects.select_for_update().get(pk=user.pk)
    security_event_at = timezone.now()
    locked.last_security_event_at = security_event_at
    locked.save(update_fields=["last_security_event_at", "updated_at"])
    uid = urlsafe_base64_encode(force_bytes(locked.pk))
    token = password_reset_token_generator.make_token(locked)
    append_audit(
        AuditRecord(
            action="identity.password_reset.requested",
            entity_type="user",
            entity_public_id=locked.public_id,
            actor_type="anonymous",
            request_id=correlation_id,
            correlation_id=correlation_id,
            after={"delivery": "self_service_reset", "latest_only": True},
        )
    )
    append_event(
        EventRecord(
            event_type="identity.password_reset_requested",
            aggregate_type="user",
            aggregate_public_id=locked.public_id,
            aggregate_version=_security_event_aggregate_version(security_event_at),
            correlation_id=correlation_id,
            payload={"delivery": "self_service_reset", "latest_only": True},
        )
    )
    return uid, token


def resolve_password_reset_user(*, uid: str, token: str) -> User | None:
    try:
        pk = force_str(urlsafe_base64_decode(uid))
    except (TypeError, ValueError, OverflowError, UnicodeDecodeError):
        return None
    user = User.objects.filter(pk=pk, is_active=True).first()
    if user is None or not password_reset_token_generator.check_token(user, token):
        return None
    return user


@transaction.atomic
def complete_password_reset(
    *,
    uid: str,
    token: str,
    new_password: str,
    correlation_id: uuid.UUID,
) -> User | None:
    user = resolve_password_reset_user(uid=uid, token=token)
    if user is None:
        return None
    locked = User.objects.select_for_update().filter(pk=user.pk, is_active=True).first()
    if locked is None or not password_reset_token_generator.check_token(locked, token):
        return None

    locked.set_password(new_password)
    security_event_at = timezone.now()
    locked.last_security_event_at = security_event_at
    locked.save(update_fields=["password", "last_security_event_at", "updated_at"])

    now = timezone.now()
    sessions = AuthSession.objects.filter(user=locked, revoked_at__isnull=True)
    session_ids = list(sessions.values_list("id", flat=True))
    sessions.update(revoked_at=now, revoke_reason="password_reset")
    RefreshToken.objects.filter(
        session_id__in=session_ids,
        revoked_at__isnull=True,
    ).update(revoked_at=now)

    append_audit(
        AuditRecord(
            action="identity.password_reset.completed",
            entity_type="user",
            entity_public_id=locked.public_id,
            actor_public_id=locked.public_id,
            actor_type="user",
            request_id=correlation_id,
            correlation_id=correlation_id,
            reason_code="self_service_password_reset",
            after={"active_sessions_revoked": len(session_ids)},
        )
    )
    append_event(
        EventRecord(
            event_type="identity.password_reset_completed",
            aggregate_type="user",
            aggregate_public_id=locked.public_id,
            aggregate_version=_security_event_aggregate_version(security_event_at),
            correlation_id=correlation_id,
            payload={"active_sessions_revoked": len(session_ids)},
        )
    )
    return locked
