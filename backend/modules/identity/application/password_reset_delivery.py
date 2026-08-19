from __future__ import annotations

import logging
import uuid
from html import escape
from urllib.parse import urlencode

from modules.identity.models import User
from modules.platform.audit import AuditRecord, append_audit
from modules.platform.events import EventRecord, append_event
from modules.tenant.application.email_delivery import (
    PasswordResetScope,
    resolve_transactional_brand,
    send_transactional_email,
)

logger = logging.getLogger(__name__)


def password_reset_url(*, uid: str, token: str, scope: PasswordResetScope) -> str:
    brand = resolve_transactional_brand(scope.company)
    query = urlencode({"uid": uid, "token": token})
    return f"{brand.public_web_url.rstrip('/')}/reset-password?{query}"


def _password_reset_copy(
    *,
    user: User,
    reset_url: str,
    scope: PasswordResetScope,
) -> tuple[str, str, str]:
    from django.conf import settings

    brand = resolve_transactional_brand(scope.company)
    display_name = str(getattr(user, "display_name", "") or "").strip()
    greeting = display_name or "there"
    timeout_seconds = int(getattr(settings, "PASSWORD_RESET_TIMEOUT", 3600))
    timeout_minutes = max(1, timeout_seconds // 60)
    subject = f"Reset your {brand.product_name} password"
    text = (
        f"Hi {greeting},\n\n"
        f"We received a request to reset the password for your {brand.product_name} account.\n\n"
        f"Reset password: {reset_url}\n\n"
        f"This link expires in {timeout_minutes} minutes and only the latest reset link will work.\n"
        "If you did not request this change, you can ignore this email.\n\n"
        f"{brand.product_name}\n"
    )
    powered = (
        '<p style="line-height:1.6;color:#98a2b3;font-size:11px">Powered by MPSqre Build360</p>'
        if brand.powered_by_build360 and brand.white_label_enabled
        else ""
    )
    html = f"""
<!doctype html>
<html>
  <body style="margin:0;background:#f5f7f6;font-family:Arial,sans-serif;color:#17202a">
    <div style="max-width:620px;margin:0 auto;padding:32px 18px">
      <div style="background:#ffffff;border:1px solid #e4e7ec;border-radius:18px;padding:32px">
        <div style="font-size:13px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:{escape(brand.primary_color)}">{escape(brand.product_name)}</div>
        <h1 style="font-size:24px;line-height:1.3;margin:12px 0 10px">Reset your password</h1>
        <p style="line-height:1.65;color:#475467">Hi {escape(greeting)}, we received a request to reset the password for your account.</p>
        <p style="margin:28px 0"><a href="{escape(reset_url, quote=True)}" style="background:{escape(brand.primary_color)};color:#ffffff;text-decoration:none;font-weight:700;padding:13px 20px;border-radius:10px;display:inline-block">Reset password</a></p>
        <p style="line-height:1.6;color:#667085;font-size:13px">This one-time link expires in {timeout_minutes} minutes. If you request another reset link, this link becomes invalid.</p>
        <p style="line-height:1.6;color:#667085;font-size:13px">If you did not request this change, you can safely ignore this email.</p>
        {powered}
      </div>
    </div>
  </body>
</html>
""".strip()
    return subject, text, html


def _record_delivery(
    *,
    user: User,
    correlation_id: uuid.UUID,
    status: str,
    route: str,
    scope_source: str,
    error_code: str = "",
) -> None:
    try:
        append_audit(
            AuditRecord(
                action="identity.password_reset.delivery",
                entity_type="user",
                entity_public_id=user.public_id,
                actor_type="system",
                request_id=correlation_id,
                correlation_id=correlation_id,
                reason_code=error_code,
                after={
                    "channel": "email",
                    "status": status,
                    "route": route,
                    "tenant_resolution": scope_source,
                },
            )
        )
        append_event(
            EventRecord(
                event_type="identity.password_reset_delivery",
                aggregate_type="user",
                aggregate_public_id=user.public_id,
                aggregate_version=1,
                correlation_id=correlation_id,
                payload={"channel": "email", "status": status, "route": route},
            )
        )
    except Exception:
        logger.exception("Password reset delivery telemetry failed")


def deliver_password_reset_email(
    *,
    user: User,
    uid: str,
    token: str,
    correlation_id: uuid.UUID,
    scope: PasswordResetScope,
) -> dict[str, str]:
    reset_url = password_reset_url(uid=uid, token=token, scope=scope)
    brand = resolve_transactional_brand(scope.company)
    subject, text, html = _password_reset_copy(
        user=user,
        reset_url=reset_url,
        scope=scope,
    )
    delivery = send_transactional_email(
        company=scope.company,
        subject=subject,
        text=text,
        html=html,
        to=[user.email],
        sender_name=brand.sender_name,
        reply_to=[brand.support_email] if brand.support_email else None,
    )
    _record_delivery(
        user=user,
        correlation_id=correlation_id,
        status=delivery.status,
        route=delivery.route,
        scope_source=scope.source,
        error_code=delivery.error_code,
    )
    return {
        "status": delivery.status,
        "route": delivery.route,
        "error_code": delivery.error_code,
    }
