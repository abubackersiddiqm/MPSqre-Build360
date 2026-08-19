import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import AuthenticationFailed

from modules.identity.models import AuthSession, RefreshToken, User, hash_jti
from modules.platform.audit import AuditRecord, append_audit
from modules.platform.events import EventRecord, append_event

ALGORITHM = "HS256"


@dataclass(frozen=True, slots=True)
class TokenPair:
    access_token: str
    refresh_token: str
    access_expires_at: datetime
    refresh_expires_at: datetime
    session_public_id: uuid.UUID


@dataclass(frozen=True, slots=True)
class AccessPrincipal:
    user: User
    session: AuthSession
    assurance_at: datetime | None


def _encode(
    *,
    user: User,
    session: AuthSession,
    credential_kind: str,
    jti: uuid.UUID,
    issued_at: datetime,
    expires_at: datetime,
    family_id: uuid.UUID | None = None,
) -> str:
    claims: dict[str, Any] = {
        "iss": settings.JWT_ISSUER,
        "aud": settings.JWT_AUDIENCE,
        "sub": str(user.public_id),
        "sid": str(session.public_id),
        "jti": str(jti),
        "type": credential_kind,
        "iat": int(issued_at.timestamp()),
        "nbf": int(issued_at.timestamp()),
        "exp": int(expires_at.timestamp()),
    }
    if family_id:
        claims["family"] = str(family_id)
    return jwt.encode(claims, settings.JWT_SIGNING_KEY, algorithm=ALGORITHM)


def decode_token(token: str, expected_type: str) -> dict[str, Any]:
    try:
        claims = jwt.decode(
            token,
            settings.JWT_SIGNING_KEY,
            algorithms=[ALGORITHM],
            audience=settings.JWT_AUDIENCE,
            issuer=settings.JWT_ISSUER,
            options={"require": ["exp", "iat", "jti", "sid", "sub", "type"]},
        )
    except jwt.PyJWTError as exc:
        raise AuthenticationFailed("Invalid or expired credential") from exc
    if claims.get("type") != expected_type:
        raise AuthenticationFailed("Credential type is invalid")
    return claims


def issue_session(
    *,
    user: User,
    device_id: uuid.UUID,
    device_name: str,
    ip_address: str | None,
    user_agent: str,
    correlation_id: uuid.UUID,
) -> TokenPair:
    now = timezone.now()
    refresh_expires_at = now + timedelta(seconds=settings.JWT_REFRESH_TTL_SECONDS)
    session = AuthSession.objects.create(
        user=user,
        device_id=device_id,
        device_name=device_name[:200],
        ip_address=ip_address,
        user_agent=user_agent[:500],
        assurance_at=now,
        expires_at=refresh_expires_at,
    )
    pair = _issue_pair(session=session, family_id=uuid.uuid4(), now=now)
    append_audit(
        AuditRecord(
            action="identity.session.created",
            entity_type="auth_session",
            entity_public_id=session.public_id,
            actor_public_id=user.public_id,
            request_id=correlation_id,
            correlation_id=correlation_id,
            ip_address=ip_address,
            user_agent=user_agent[:500],
            after={"device_id": str(device_id)},
        )
    )
    append_event(
        EventRecord(
            event_type="identity.session_created",
            aggregate_type="auth_session",
            aggregate_public_id=session.public_id,
            aggregate_version=1,
            correlation_id=correlation_id,
            payload={"user_public_id": str(user.public_id)},
        )
    )
    return pair


def _issue_pair(
    *,
    session: AuthSession,
    family_id: uuid.UUID,
    now: datetime,
) -> TokenPair:
    access_jti = uuid.uuid4()
    refresh_jti = uuid.uuid4()
    access_expires_at = now + timedelta(seconds=settings.JWT_ACCESS_TTL_SECONDS)
    refresh_expires_at = min(
        session.expires_at,
        now + timedelta(seconds=settings.JWT_REFRESH_TTL_SECONDS),
    )
    RefreshToken.objects.create(
        session=session,
        jti_hash=hash_jti(refresh_jti),
        family_id=family_id,
        issued_at=now,
        expires_at=refresh_expires_at,
    )
    return TokenPair(
        access_token=_encode(
            user=session.user,
            session=session,
            credential_kind="access",
            jti=access_jti,
            issued_at=now,
            expires_at=access_expires_at,
        ),
        refresh_token=_encode(
            user=session.user,
            session=session,
            credential_kind="refresh",
            jti=refresh_jti,
            family_id=family_id,
            issued_at=now,
            expires_at=refresh_expires_at,
        ),
        access_expires_at=access_expires_at,
        refresh_expires_at=refresh_expires_at,
        session_public_id=session.public_id,
    )


def rotate_refresh_token(
    *,
    encoded_token: str,
    correlation_id: uuid.UUID,
    ip_address: str | None,
    user_agent: str,
) -> TokenPair:
    claims = decode_token(encoded_token, "refresh")
    try:
        jti = uuid.UUID(str(claims["jti"]))
        session_public_id = uuid.UUID(str(claims["sid"]))
        family_id = uuid.UUID(str(claims["family"]))
    except (KeyError, TypeError, ValueError) as exc:
        raise AuthenticationFailed("Refresh credential claims are invalid") from exc

    reuse_detected = False
    pair: TokenPair | None = None
    with transaction.atomic():
        session = (
            AuthSession.objects.select_for_update()
            .select_related("user")
            .filter(public_id=session_public_id)
            .first()
        )
        if not session or session.revoked_at or session.expires_at <= timezone.now():
            raise AuthenticationFailed("Session is revoked or expired")
        if not session.user.is_active:
            raise AuthenticationFailed("User is inactive")

        token = (
            RefreshToken.objects.select_for_update()
            .filter(session=session, jti_hash=hash_jti(jti), family_id=family_id)
            .first()
        )
        now = timezone.now()
        if not token or token.expires_at <= now:
            raise AuthenticationFailed("Refresh credential is invalid or expired")
        if token.used_at or token.revoked_at:
            _revoke_session_locked(
                session=session,
                reason="refresh_token_reuse",
                now=now,
            )
            append_audit(
                AuditRecord(
                    action="identity.refresh_token.reuse_detected",
                    entity_type="auth_session",
                    entity_public_id=session.public_id,
                    actor_public_id=session.user.public_id,
                    request_id=correlation_id,
                    correlation_id=correlation_id,
                    ip_address=ip_address,
                    user_agent=user_agent[:500],
                )
            )
            append_event(
                EventRecord(
                    event_type="identity.refresh_token_reuse_detected",
                    aggregate_type="auth_session",
                    aggregate_public_id=session.public_id,
                    aggregate_version=1,
                    correlation_id=correlation_id,
                    payload={"user_public_id": str(session.user.public_id)},
                )
            )
            reuse_detected = True
        else:
            token.used_at = now
            pair = _issue_pair(session=session, family_id=family_id, now=now)
            replacement_claims = decode_token(pair.refresh_token, "refresh")
            replacement_jti = uuid.UUID(str(replacement_claims["jti"]))
            token.replaced_by_jti_hash = hash_jti(replacement_jti)
            token.save(update_fields=["used_at", "replaced_by_jti_hash"])
    if reuse_detected:
        raise AuthenticationFailed("Session revoked after credential reuse")
    if pair is None:
        raise AuthenticationFailed("Refresh credential could not be rotated")
    return pair


def authenticate_access_token(encoded_token: str) -> AccessPrincipal:
    claims = decode_token(encoded_token, "access")
    try:
        user_public_id = uuid.UUID(str(claims["sub"]))
        session_public_id = uuid.UUID(str(claims["sid"]))
    except (KeyError, TypeError, ValueError) as exc:
        raise AuthenticationFailed("Access credential claims are invalid") from exc
    session = (
        AuthSession.objects.select_related("user")
        .filter(public_id=session_public_id, user__public_id=user_public_id)
        .first()
    )
    now = timezone.now()
    if (
        not session
        or session.revoked_at
        or session.expires_at <= now
        or not session.user.is_active
    ):
        raise AuthenticationFailed("Session is revoked or expired")
    return AccessPrincipal(
        user=session.user,
        session=session,
        assurance_at=session.assurance_at,
    )


def _revoke_session_locked(
    *,
    session: AuthSession,
    reason: str,
    now: datetime,
) -> None:
    if not session.revoked_at:
        session.revoked_at = now
        session.revoke_reason = reason
        session.save(update_fields=["revoked_at", "revoke_reason"])
    RefreshToken.objects.filter(session=session, revoked_at__isnull=True).update(revoked_at=now)


@transaction.atomic
def revoke_session(
    *,
    session: AuthSession,
    actor_public_id: uuid.UUID,
    reason: str,
    correlation_id: uuid.UUID,
    company_public_id: uuid.UUID | None = None,
) -> None:
    locked = AuthSession.objects.select_for_update().get(pk=session.pk)
    now = timezone.now()
    _revoke_session_locked(session=locked, reason=reason, now=now)
    append_audit(
        AuditRecord(
            action="identity.session.revoked",
            entity_type="auth_session",
            entity_public_id=session.public_id,
            actor_public_id=actor_public_id,
            company_public_id=company_public_id,
            request_id=correlation_id,
            correlation_id=correlation_id,
            reason_code=reason,
        )
    )
    append_event(
        EventRecord(
            event_type="identity.session_revoked",
            aggregate_type="auth_session",
            aggregate_public_id=session.public_id,
            aggregate_version=1,
            correlation_id=correlation_id,
            company_public_id=company_public_id,
            payload={
                "user_public_id": str(actor_public_id),
                "reason_code": reason,
            },
        )
    )


def has_recent_assurance(principal: AccessPrincipal) -> bool:
    if not principal.assurance_at:
        return False
    minimum = datetime.now(UTC) - timedelta(seconds=settings.JWT_STEP_UP_TTL_SECONDS)
    return principal.assurance_at >= minimum
