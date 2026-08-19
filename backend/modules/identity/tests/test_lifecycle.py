import uuid
from collections.abc import Callable

import pytest

from modules.identity.application.lifecycle import (
    reactivate_user,
    suspend_user,
    terminate_user,
)
from modules.identity.application.tokens import TokenPair
from modules.identity.models import AuthSession, User
from modules.platform.models import AuditEvent, BusinessEventOutbox


@pytest.mark.django_db
def test_suspend_and_reactivate_preserve_user_and_revoke_sessions(
    user_factory: Callable[..., User],
    token_pair_factory: Callable[[User], TokenPair],
) -> None:
    user = user_factory()
    token_pair_factory(user)
    correlation_id = uuid.uuid4()

    suspended = suspend_user(
        user=user,
        actor_public_id=uuid.uuid4(),
        correlation_id=correlation_id,
        reason_code="security_review",
    )

    assert not suspended.is_active
    assert AuthSession.objects.filter(user=user, revoked_at__isnull=False).exists()
    assert AuditEvent.objects.filter(action="identity.user.suspended").exists()
    assert BusinessEventOutbox.objects.filter(event_type="identity.user_suspended").exists()

    reactivated = reactivate_user(
        user=user,
        actor_public_id=uuid.uuid4(),
        correlation_id=uuid.uuid4(),
        reason_code="review_completed",
    )
    assert reactivated.is_active


@pytest.mark.django_db
def test_terminated_user_cannot_be_reactivated(
    user_factory: Callable[..., User],
) -> None:
    user = user_factory()
    terminate_user(
        user=user,
        actor_public_id=uuid.uuid4(),
        correlation_id=uuid.uuid4(),
        reason_code="employment_ended",
    )

    with pytest.raises(ValueError, match="cannot be reactivated"):
        reactivate_user(
            user=user,
            actor_public_id=uuid.uuid4(),
            correlation_id=uuid.uuid4(),
            reason_code="invalid",
        )

