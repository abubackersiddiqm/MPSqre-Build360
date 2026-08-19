from __future__ import annotations

import uuid
from decimal import Decimal, InvalidOperation
from typing import Any

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from modules.digitaltwinops.models import (
    BIMIssue,
    BIMModel,
    BIMRevision,
    ClashRecord,
    DigitalTwinPolicyVersion,
    HandoverAssetRecord,
    IoTDevice,
    ModelFederation,
    SmartAlert,
    TelemetryReading,
)
from modules.platform.audit import AuditRecord, append_audit
from modules.platform.events import EventRecord, append_event
from modules.tenant.models import Company


def _record(
    *,
    company: Company,
    action: str,
    event_type: str,
    entity_type: str,
    entity_public_id: uuid.UUID,
    actor_public_id: uuid.UUID,
    correlation_id: uuid.UUID,
    version: int,
    after: dict[str, Any],
    before: dict[str, Any] | None = None,
) -> None:
    append_audit(
        AuditRecord(
            action=action,
            entity_type=entity_type,
            entity_public_id=entity_public_id,
            actor_public_id=actor_public_id,
            company_public_id=company.public_id,
            request_id=correlation_id,
            correlation_id=correlation_id,
            before=before or {},
            after=after,
        )
    )
    append_event(
        EventRecord(
            event_type=event_type,
            aggregate_type=entity_type,
            aggregate_public_id=entity_public_id,
            aggregate_version=version,
            company_public_id=company.public_id,
            correlation_id=correlation_id,
            payload=after,
        )
    )


def seed_defaults(company: Company) -> dict[str, int]:
    _, created = DigitalTwinPolicyVersion.objects.get_or_create(
        company=company,
        version=1,
        defaults={
            "status_code": "DRAFT",
            "coordinate_system_code": "PROJECT_LOCAL",
            "model_review_frequency_code": "WEEKLY",
            "telemetry_retention_days": 365,
            "alert_acknowledgement_minutes": 30,
            "configuration": {
                "phase": 39,
                "release": "bim-digital-twin-smart-site",
                "model_storage": "REFERENCE_ONLY",
                "iot_provider": "PROVIDER_NEUTRAL",
                "ifc_processing": "EXTERNAL_CONNECTOR",
            },
        },
    )
    return {"policy": int(created)}


def _create(
    model,
    *,
    company: Company,
    actor_public_id: uuid.UUID,
    correlation_id: uuid.UUID,
    event: str,
    **data: Any,
):
    item = model(company=company, **data)
    item.full_clean()
    item.save()
    version = getattr(item, "version", 1)
    code = (
        getattr(item, "code", None)
        or getattr(item, "issue_code", None)
        or getattr(item, "alert_code", None)
        or getattr(item, "asset_tag", None)
        or getattr(item, "clash_number", None)
        or str(item.public_id)
    )
    _record(
        company=company,
        action="CREATE",
        event_type=event,
        entity_type=model.__name__,
        entity_public_id=item.public_id,
        actor_public_id=actor_public_id,
        correlation_id=correlation_id,
        version=version,
        after={"code": code, "status": getattr(item, "status_code", getattr(item, "operation_status_code", "RECORDED"))},
    )
    return item


@transaction.atomic
def create_model(*, company: Company, actor_public_id: uuid.UUID, correlation_id: uuid.UUID, **data: Any) -> BIMModel:
    data.setdefault("owner_public_id", actor_public_id)
    return _create(
        BIMModel,
        company=company,
        actor_public_id=actor_public_id,
        correlation_id=correlation_id,
        event="digitaltwin.model.created",
        **data,
    )


@transaction.atomic
def create_revision(
    *, company: Company, model: BIMModel, actor_public_id: uuid.UUID, correlation_id: uuid.UUID, **data: Any
) -> BIMRevision:
    data.setdefault("authored_by_public_id", actor_public_id)
    return _create(
        BIMRevision,
        company=company,
        model=model,
        actor_public_id=actor_public_id,
        correlation_id=correlation_id,
        event="digitaltwin.revision.created",
        **data,
    )


@transaction.atomic
def transition_revision(
    *, revision: BIMRevision, status_code: str, expected_version: int, actor_public_id: uuid.UUID, correlation_id: uuid.UUID
) -> BIMRevision:
    revision = BIMRevision.objects.select_for_update().select_related("model").get(pk=revision.pk)
    status_code = status_code.strip().upper()
    if revision.version != expected_version:
        raise ValidationError("BIM revision changed. Refresh and retry.")
    allowed = {
        "DRAFT": {"SUBMITTED", "CANCELLED"},
        "SUBMITTED": {"APPROVED", "REJECTED", "DRAFT"},
        "REJECTED": {"DRAFT", "CANCELLED"},
        "APPROVED": {"PUBLISHED", "REJECTED"},
        "PUBLISHED": set(),
        "CANCELLED": set(),
    }
    if status_code not in allowed.get(revision.status_code, set()):
        raise ValidationError(f"Invalid revision transition from {revision.status_code} to {status_code}.")
    if status_code == "APPROVED" and revision.authored_by_public_id == actor_public_id:
        raise ValidationError("The revision author cannot approve the same revision.")
    before = {"status": revision.status_code, "version": revision.version}
    revision.status_code = status_code
    if status_code == "SUBMITTED":
        revision.submitted_at = timezone.now()
    if status_code == "APPROVED":
        revision.approved_by_public_id = actor_public_id
        revision.approved_at = timezone.now()
    revision.version += 1
    revision.full_clean()
    revision.save()
    if status_code == "PUBLISHED":
        model = BIMModel.objects.select_for_update().get(pk=revision.model_id)
        model.current_revision_code = revision.revision_code
        model.status_code = "PUBLISHED"
        model.last_published_at = timezone.now()
        model.version += 1
        model.save(update_fields=["current_revision_code", "status_code", "last_published_at", "version", "updated_at"])
    _record(
        company=revision.company,
        action="TRANSITION",
        event_type="digitaltwin.revision.transitioned",
        entity_type="BIMRevision",
        entity_public_id=revision.public_id,
        actor_public_id=actor_public_id,
        correlation_id=correlation_id,
        version=revision.version,
        before=before,
        after={"status": status_code, "revision": revision.revision_code, "model": revision.model.code},
    )
    return revision


@transaction.atomic
def create_federation(
    *, company: Company, actor_public_id: uuid.UUID, correlation_id: uuid.UUID, **data: Any
) -> ModelFederation:
    model_refs = data.get("model_public_ids") or []
    existing = BIMModel.objects.filter(company=company, public_id__in=model_refs).count()
    if existing != len(set(str(item) for item in model_refs)):
        raise ValidationError("One or more BIM model references are invalid for this company.")
    data["model_count"] = existing
    data.setdefault("prepared_by_public_id", actor_public_id)
    return _create(
        ModelFederation,
        company=company,
        actor_public_id=actor_public_id,
        correlation_id=correlation_id,
        event="digitaltwin.federation.created",
        **data,
    )


@transaction.atomic
def create_clash(
    *, company: Company, federation: ModelFederation, actor_public_id: uuid.UUID, correlation_id: uuid.UUID, **data: Any
) -> ClashRecord:
    return _create(
        ClashRecord,
        company=company,
        federation=federation,
        actor_public_id=actor_public_id,
        correlation_id=correlation_id,
        event="digitaltwin.clash.created",
        **data,
    )


@transaction.atomic
def transition_clash(
    *, clash: ClashRecord, status_code: str, expected_version: int, actor_public_id: uuid.UUID, correlation_id: uuid.UUID, resolution_note: str = ""
) -> ClashRecord:
    clash = ClashRecord.objects.select_for_update().get(pk=clash.pk)
    status_code = status_code.strip().upper()
    if clash.version != expected_version:
        raise ValidationError("Clash record changed. Refresh and retry.")
    allowed = {
        "OPEN": {"IN_PROGRESS", "BLOCKED", "CANCELLED"},
        "IN_PROGRESS": {"RESOLVED", "BLOCKED", "OPEN"},
        "BLOCKED": {"IN_PROGRESS", "CANCELLED"},
        "RESOLVED": {"VERIFIED", "IN_PROGRESS"},
        "VERIFIED": {"CLOSED", "IN_PROGRESS"},
        "CLOSED": set(),
        "CANCELLED": set(),
    }
    if status_code not in allowed.get(clash.status_code, set()):
        raise ValidationError(f"Invalid clash transition from {clash.status_code} to {status_code}.")
    before = {"status": clash.status_code, "version": clash.version}
    clash.status_code = status_code
    if resolution_note:
        clash.resolution_note = resolution_note
    if status_code in {"RESOLVED", "VERIFIED", "CLOSED"}:
        clash.resolved_at = clash.resolved_at or timezone.now()
    elif status_code == "IN_PROGRESS":
        clash.resolved_at = None
    clash.version += 1
    clash.full_clean()
    clash.save()
    _record(
        company=clash.company,
        action="TRANSITION",
        event_type="digitaltwin.clash.transitioned",
        entity_type="ClashRecord",
        entity_public_id=clash.public_id,
        actor_public_id=actor_public_id,
        correlation_id=correlation_id,
        version=clash.version,
        before=before,
        after={"status": status_code, "clash_number": clash.clash_number, "severity": clash.severity_code},
    )
    return clash


@transaction.atomic
def create_issue(*, company: Company, actor_public_id: uuid.UUID, correlation_id: uuid.UUID, **data: Any) -> BIMIssue:
    data.setdefault("raised_by_public_id", actor_public_id)
    return _create(
        BIMIssue,
        company=company,
        actor_public_id=actor_public_id,
        correlation_id=correlation_id,
        event="digitaltwin.issue.created",
        **data,
    )


@transaction.atomic
def transition_issue(
    *, issue: BIMIssue, status_code: str, expected_version: int, actor_public_id: uuid.UUID, correlation_id: uuid.UUID
) -> BIMIssue:
    issue = BIMIssue.objects.select_for_update().get(pk=issue.pk)
    status_code = status_code.strip().upper()
    if issue.version != expected_version:
        raise ValidationError("BIM issue changed. Refresh and retry.")
    allowed = {
        "OPEN": {"IN_PROGRESS", "BLOCKED", "CANCELLED"},
        "IN_PROGRESS": {"RESOLVED", "BLOCKED", "OPEN"},
        "BLOCKED": {"IN_PROGRESS", "CANCELLED"},
        "RESOLVED": {"CLOSED", "IN_PROGRESS"},
        "CLOSED": set(),
        "CANCELLED": set(),
    }
    if status_code not in allowed.get(issue.status_code, set()):
        raise ValidationError(f"Invalid issue transition from {issue.status_code} to {status_code}.")
    before = {"status": issue.status_code, "version": issue.version}
    issue.status_code = status_code
    issue.closed_at = timezone.now() if status_code == "CLOSED" else None
    issue.version += 1
    issue.full_clean()
    issue.save()
    _record(
        company=issue.company,
        action="TRANSITION",
        event_type="digitaltwin.issue.transitioned",
        entity_type="BIMIssue",
        entity_public_id=issue.public_id,
        actor_public_id=actor_public_id,
        correlation_id=correlation_id,
        version=issue.version,
        before=before,
        after={"status": status_code, "issue_code": issue.issue_code},
    )
    return issue


@transaction.atomic
def create_device(*, company: Company, actor_public_id: uuid.UUID, correlation_id: uuid.UUID, **data: Any) -> IoTDevice:
    return _create(
        IoTDevice,
        company=company,
        actor_public_id=actor_public_id,
        correlation_id=correlation_id,
        event="digitaltwin.device.created",
        **data,
    )


def _threshold_alert(device: IoTDevice, reading: TelemetryReading) -> tuple[bool, str, str]:
    if reading.numeric_value is None:
        return False, "", ""
    config = device.threshold_configuration or {}
    try:
        minimum = Decimal(str(config["min"])) if config.get("min") not in (None, "") else None
        maximum = Decimal(str(config["max"])) if config.get("max") not in (None, "") else None
    except (InvalidOperation, ValueError, TypeError):
        return False, "", ""
    if minimum is not None and reading.numeric_value < minimum:
        return True, str(config.get("severity", "HIGH")).upper(), f"{device.metric_code} below minimum threshold {minimum}."
    if maximum is not None and reading.numeric_value > maximum:
        return True, str(config.get("severity", "HIGH")).upper(), f"{device.metric_code} above maximum threshold {maximum}."
    return False, "", ""


@transaction.atomic
def record_telemetry(
    *, company: Company, device: IoTDevice, actor_public_id: uuid.UUID, correlation_id: uuid.UUID, **data: Any
) -> tuple[TelemetryReading, SmartAlert | None]:
    data.setdefault("metric_code", device.metric_code)
    data.setdefault("unit_code", device.unit_code)
    reading = _create(
        TelemetryReading,
        company=company,
        device=device,
        actor_public_id=actor_public_id,
        correlation_id=correlation_id,
        event="digitaltwin.telemetry.recorded",
        **data,
    )
    device = IoTDevice.objects.select_for_update().get(pk=device.pk)
    device.last_seen_at = reading.observed_at
    device.status_code = "ONLINE"
    device.version += 1
    device.save(update_fields=["last_seen_at", "status_code", "version", "updated_at"])
    breached, severity, message = _threshold_alert(device, reading)
    alert = None
    if breached:
        alert = _create(
            SmartAlert,
            company=company,
            device=device,
            actor_public_id=actor_public_id,
            correlation_id=correlation_id,
            event="digitaltwin.alert.triggered",
            project_public_id=device.project_public_id,
            alert_code=f"ALERT_{reading.public_id.hex[:12].upper()}",
            alert_type_code="THRESHOLD_BREACH",
            severity_code=severity,
            status_code="OPEN",
            message=message,
            triggered_at=reading.observed_at,
            source_reading_public_id=reading.public_id,
        )
    return reading, alert


@transaction.atomic
def transition_alert(
    *, alert: SmartAlert, status_code: str, expected_version: int, actor_public_id: uuid.UUID, correlation_id: uuid.UUID
) -> SmartAlert:
    alert = SmartAlert.objects.select_for_update().get(pk=alert.pk)
    status_code = status_code.strip().upper()
    if alert.version != expected_version:
        raise ValidationError("Smart alert changed. Refresh and retry.")
    allowed = {
        "OPEN": {"ACKNOWLEDGED", "RESOLVED", "SUPPRESSED"},
        "ACKNOWLEDGED": {"RESOLVED", "OPEN", "SUPPRESSED"},
        "RESOLVED": {"CLOSED", "OPEN"},
        "SUPPRESSED": {"OPEN", "CLOSED"},
        "CLOSED": set(),
    }
    if status_code not in allowed.get(alert.status_code, set()):
        raise ValidationError(f"Invalid alert transition from {alert.status_code} to {status_code}.")
    before = {"status": alert.status_code, "version": alert.version}
    alert.status_code = status_code
    if status_code == "ACKNOWLEDGED":
        alert.acknowledged_by_public_id = actor_public_id
        alert.acknowledged_at = timezone.now()
    if status_code == "RESOLVED":
        alert.resolved_by_public_id = actor_public_id
        alert.resolved_at = timezone.now()
    if status_code == "OPEN":
        alert.resolved_by_public_id = None
        alert.resolved_at = None
    alert.version += 1
    alert.full_clean()
    alert.save()
    _record(
        company=alert.company,
        action="TRANSITION",
        event_type="digitaltwin.alert.transitioned",
        entity_type="SmartAlert",
        entity_public_id=alert.public_id,
        actor_public_id=actor_public_id,
        correlation_id=correlation_id,
        version=alert.version,
        before=before,
        after={"status": status_code, "alert_code": alert.alert_code, "severity": alert.severity_code},
    )
    return alert


@transaction.atomic
def create_asset(
    *, company: Company, actor_public_id: uuid.UUID, correlation_id: uuid.UUID, **data: Any
) -> HandoverAssetRecord:
    data.setdefault("captured_by_public_id", actor_public_id)
    return _create(
        HandoverAssetRecord,
        company=company,
        actor_public_id=actor_public_id,
        correlation_id=correlation_id,
        event="digitaltwin.handover_asset.created",
        **data,
    )


@transaction.atomic
def transition_asset(
    *, asset: HandoverAssetRecord, status_code: str, expected_version: int, actor_public_id: uuid.UUID, correlation_id: uuid.UUID
) -> HandoverAssetRecord:
    asset = HandoverAssetRecord.objects.select_for_update().get(pk=asset.pk)
    status_code = status_code.strip().upper()
    if asset.version != expected_version:
        raise ValidationError("Handover asset changed. Refresh and retry.")
    allowed = {
        "DRAFT": {"VERIFIED", "CANCELLED"},
        "VERIFIED": {"HANDED_OVER", "DRAFT"},
        "HANDED_OVER": {"IN_SERVICE", "VERIFIED"},
        "IN_SERVICE": {"OUT_OF_SERVICE", "RETIRED"},
        "OUT_OF_SERVICE": {"IN_SERVICE", "RETIRED"},
        "RETIRED": set(),
        "CANCELLED": set(),
    }
    if status_code not in allowed.get(asset.operation_status_code, set()):
        raise ValidationError(f"Invalid asset transition from {asset.operation_status_code} to {status_code}.")
    if status_code == "VERIFIED" and asset.captured_by_public_id == actor_public_id:
        raise ValidationError("The asset recorder cannot verify the same handover asset.")
    before = {"status": asset.operation_status_code, "version": asset.version}
    asset.operation_status_code = status_code
    if status_code == "VERIFIED":
        asset.verified_by_public_id = actor_public_id
    asset.version += 1
    asset.full_clean()
    asset.save()
    _record(
        company=asset.company,
        action="TRANSITION",
        event_type="digitaltwin.handover_asset.transitioned",
        entity_type="HandoverAssetRecord",
        entity_public_id=asset.public_id,
        actor_public_id=actor_public_id,
        correlation_id=correlation_id,
        version=asset.version,
        before=before,
        after={"status": status_code, "asset_tag": asset.asset_tag},
    )
    return asset
