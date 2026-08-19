import uuid
from datetime import datetime

from django.db import transaction
from django.utils import timezone

from modules.identity.models import AuthSession, RefreshToken, User
from modules.platform.audit import AuditRecord, append_audit
from modules.platform.events import EventRecord, append_event


@transaction.atomic
def suspend_user(
    *,
    user: User,
    actor_public_id: uuid.UUID,
    correlation_id: uuid.UUID,
    reason_code: str,
    company_public_id: uuid.UUID | None = None,
) -> User:
    locked = User.objects.select_for_update().get(pk=user.pk)
    before = {"is_active": locked.is_active}
    now = timezone.now()
    locked.is_active = False
    locked.suspended_at = now
    locked.save(update_fields=["is_active", "suspended_at", "updated_at"])
    _revoke_all_sessions(locked, now, "user_suspended")
    _record_user_change(
        user=locked,
        actor_public_id=actor_public_id,
        company_public_id=company_public_id,
        correlation_id=correlation_id,
        action="identity.user.suspended",
        event_type="identity.user_suspended",
        reason_code=reason_code,
        before=before,
        after={"is_active": False},
    )
    return locked


@transaction.atomic
def reactivate_user(
    *,
    user: User,
    actor_public_id: uuid.UUID,
    correlation_id: uuid.UUID,
    reason_code: str,
    company_public_id: uuid.UUID | None = None,
) -> User:
    locked = User.objects.select_for_update().get(pk=user.pk)
    if locked.terminated_at:
        raise ValueError("Terminated users cannot be reactivated")
    before = {"is_active": locked.is_active}
    locked.is_active = True
    locked.suspended_at = None
    locked.save(update_fields=["is_active", "suspended_at", "updated_at"])
    _record_user_change(
        user=locked,
        actor_public_id=actor_public_id,
        company_public_id=company_public_id,
        correlation_id=correlation_id,
        action="identity.user.reactivated",
        event_type="identity.user_reactivated",
        reason_code=reason_code,
        before=before,
        after={"is_active": True},
    )
    return locked


@transaction.atomic
def terminate_user(
    *,
    user: User,
    actor_public_id: uuid.UUID,
    correlation_id: uuid.UUID,
    reason_code: str,
    company_public_id: uuid.UUID | None = None,
) -> User:
    locked = User.objects.select_for_update().get(pk=user.pk)
    before = {"is_active": locked.is_active}
    now = timezone.now()
    locked.is_active = False
    locked.terminated_at = now
    locked.save(update_fields=["is_active", "terminated_at", "updated_at"])
    _revoke_all_sessions(locked, now, "user_terminated")
    _record_user_change(
        user=locked,
        actor_public_id=actor_public_id,
        company_public_id=company_public_id,
        correlation_id=correlation_id,
        action="identity.user.terminated",
        event_type="identity.user_terminated",
        reason_code=reason_code,
        before=before,
        after={"is_active": False},
    )
    return locked


def _revoke_all_sessions(user: User, now: datetime, reason: str) -> None:
    sessions = AuthSession.objects.filter(user=user, revoked_at__isnull=True)
    session_ids = list(sessions.values_list("id", flat=True))
    sessions.update(revoked_at=now, revoke_reason=reason)
    RefreshToken.objects.filter(
        session_id__in=session_ids,
        revoked_at__isnull=True,
    ).update(revoked_at=now)


def _record_user_change(
    *,
    user: User,
    actor_public_id: uuid.UUID,
    company_public_id: uuid.UUID | None,
    correlation_id: uuid.UUID,
    action: str,
    event_type: str,
    reason_code: str,
    before: dict[str, bool],
    after: dict[str, bool],
) -> None:
    append_audit(
        AuditRecord(
            action=action,
            entity_type="user",
            entity_public_id=user.public_id,
            actor_public_id=actor_public_id,
            company_public_id=company_public_id,
            request_id=correlation_id,
            correlation_id=correlation_id,
            reason_code=reason_code,
            before=before,
            after=after,
        )
    )
    append_event(
        EventRecord(
            event_type=event_type,
            aggregate_type="user",
            aggregate_public_id=user.public_id,
            aggregate_version=1,
            company_public_id=company_public_id,
            correlation_id=correlation_id,
            payload={"reason_code": reason_code},
        )
    )
