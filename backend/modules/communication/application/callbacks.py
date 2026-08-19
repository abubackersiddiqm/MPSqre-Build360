from __future__ import annotations

import hashlib
import hmac
import json

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from modules.communication.models import (
    CallbackReceipt,
    CommunicationAttempt,
    CommunicationRequest,
    InboundCommunication,
    ProviderConfiguration,
)
from modules.crm.application.protection import blind_index


def verify_signature(*, provider: ProviderConfiguration, raw_body: bytes, signature: str) -> bool:
    key_id = provider.callback_key_id
    secret = settings.COMMUNICATION_CALLBACK_KEYS.get(key_id)
    if not key_id or not secret or not signature:
        return False
    expected = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    supplied = signature.removeprefix("sha256=").strip().lower()
    return hmac.compare_digest(expected, supplied)


def _normalized_status(value: str) -> str | None:
    mapping = {
        "accepted": CommunicationRequest.Status.SENT,
        "sent": CommunicationRequest.Status.SENT,
        "delivered": CommunicationRequest.Status.DELIVERED,
        "failed": CommunicationRequest.Status.FAILED,
        "rejected": CommunicationRequest.Status.FAILED,
    }
    return mapping.get(value.strip().lower())


@transaction.atomic
def process_callback(
    *,
    provider_public_id,
    raw_body: bytes,
    signature: str,
) -> CallbackReceipt:
    provider = ProviderConfiguration.objects.select_related("company").filter(
        public_id=provider_public_id,
        is_active=True,
    ).first()
    if provider is None:
        raise ValidationError("Communication provider was not found")
    payload_digest = hashlib.sha256(raw_body).hexdigest()
    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValidationError("Communication callback payload is invalid") from exc
    if not isinstance(payload, dict):
        raise ValidationError("Communication callback payload must be an object")
    event_id = str(payload.get("event_id", "")).strip()
    event_type = str(payload.get("event_type", "")).strip().lower()
    provider_message_id = str(payload.get("provider_message_id", "")).strip()
    if not event_id or not event_type:
        raise ValidationError("Communication callback event_id and event_type are required")
    valid = verify_signature(provider=provider, raw_body=raw_body, signature=signature)
    existing = CallbackReceipt.objects.filter(
        company=provider.company,
        provider=provider,
        provider_event_id=event_id,
    ).first()
    if existing is not None:
        return existing
    request = None
    if provider_message_id:
        request = CommunicationRequest.objects.select_for_update().filter(
            company=provider.company,
            provider=provider,
            provider_message_id=provider_message_id,
        ).first()
    receipt = CallbackReceipt(
        company=provider.company,
        provider=provider,
        request=request,
        provider_event_id=event_id,
        event_type=event_type,
        provider_message_id=provider_message_id,
        payload_digest=payload_digest,
        signature_valid=valid,
        received_at=timezone.now(),
        rejection_reason="" if valid else "invalid_signature",
    )
    receipt.full_clean()
    try:
        receipt.save()
    except IntegrityError:
        return CallbackReceipt.objects.get(
            company=provider.company,
            provider=provider,
            provider_event_id=event_id,
        )
    if not valid:
        return receipt
    if event_type == "inbound.message":
        sender_reference = str(payload.get("sender_reference", ""))
        summary = str(payload.get("summary", "")).strip()[:500]
        inbound = InboundCommunication(
            company=provider.company,
            provider=provider,
            channel=provider.channel,
            provider_message_id=provider_message_id or event_id,
            sender_reference_hash=(
                blind_index(sender_reference, purpose="communication.inbound.sender")
                if sender_reference
                else ""
            ),
            subject_reference_type=str(payload.get("subject_reference_type", "")).strip(),
            subject_reference_public_id=payload.get("subject_reference_public_id") or None,
            summary=summary or "Inbound communication received",
            status=InboundCommunication.Status.REVIEW_REQUIRED,
            received_at=timezone.now(),
        )
        inbound.full_clean()
        try:
            inbound.save()
        except IntegrityError:
            pass
    elif request is not None:
        normalized = _normalized_status(str(payload.get("status", event_type)))
        if normalized:
            request.status = normalized
            if normalized == CommunicationRequest.Status.DELIVERED:
                request.delivered_at = timezone.now()
            if normalized == CommunicationRequest.Status.FAILED:
                request.failed_at = timezone.now()
            request.version += 1
            request.save()
            last_attempt = request.attempts.order_by("-attempt_number").first()
            if last_attempt is not None:
                if normalized == CommunicationRequest.Status.DELIVERED:
                    last_attempt.status = CommunicationAttempt.Status.DELIVERED
                elif normalized == CommunicationRequest.Status.FAILED:
                    last_attempt.status = CommunicationAttempt.Status.FAILED
                    last_attempt.error_code = str(payload.get("error_code", "provider_failed"))[:100]
                last_attempt.finished_at = timezone.now()
                last_attempt.save()
    receipt.processed_at = timezone.now()
    receipt.save(update_fields=["processed_at"])
    return receipt
