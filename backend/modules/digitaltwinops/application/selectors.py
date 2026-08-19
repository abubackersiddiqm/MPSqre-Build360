from __future__ import annotations

from datetime import timedelta

from django.db.models import Q
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
from modules.tenant.models import Company


def _company_payload(company: Company) -> dict[str, str]:
    return {
        "name": company.display_name,
        "code": company.code,
        "timezone": company.timezone,
        "currency": company.currency,
    }


def _rows(queryset, *fields: str, limit: int = 50) -> list[dict]:
    return list(queryset.values(*fields)[:limit])


def digital_twin_overview(company: Company) -> dict:
    now = timezone.now()
    stale_cutoff = now - timedelta(hours=24)
    policy = DigitalTwinPolicyVersion.objects.filter(company=company).order_by("-version").first()

    model_qs = BIMModel.objects.filter(company=company)
    revision_qs = BIMRevision.objects.filter(company=company)
    federation_qs = ModelFederation.objects.filter(company=company)
    clash_qs = ClashRecord.objects.filter(company=company)
    issue_qs = BIMIssue.objects.filter(company=company)
    device_qs = IoTDevice.objects.filter(company=company)
    telemetry_qs = TelemetryReading.objects.filter(company=company)
    alert_qs = SmartAlert.objects.filter(company=company)
    asset_qs = HandoverAssetRecord.objects.filter(company=company)

    metrics = {
        "published_models": model_qs.filter(status_code="PUBLISHED").count(),
        "pending_model_reviews": revision_qs.filter(status_code="SUBMITTED").count(),
        "open_clashes": clash_qs.exclude(status_code__in=["CLOSED", "CANCELLED"]).count(),
        "critical_clashes": clash_qs.filter(severity_code="CRITICAL").exclude(status_code__in=["CLOSED", "CANCELLED"]).count(),
        "open_issues": issue_qs.exclude(status_code__in=["CLOSED", "CANCELLED"]).count(),
        "online_devices": device_qs.filter(status_code="ONLINE").count(),
        "stale_devices": device_qs.filter(Q(last_seen_at__lt=stale_cutoff) | Q(last_seen_at__isnull=True)).exclude(status_code="RETIRED").count(),
        "open_alerts": alert_qs.exclude(status_code__in=["CLOSED", "SUPPRESSED"]).count(),
        "critical_alerts": alert_qs.filter(severity_code="CRITICAL").exclude(status_code__in=["CLOSED", "SUPPRESSED"]).count(),
        "handover_assets": asset_qs.count(),
        "handed_over_assets": asset_qs.filter(operation_status_code__in=["HANDED_OVER", "IN_SERVICE", "OUT_OF_SERVICE", "RETIRED"]).count(),
        "telemetry_readings_24h": telemetry_qs.filter(observed_at__gte=now - timedelta(hours=24)).count(),
    }

    policy_payload = {
        "status": policy.status_code if policy else "MISSING",
        "version": policy.version if policy else 0,
        "coordinate_system": policy.coordinate_system_code if policy else "PROJECT_LOCAL",
        "retention_days": policy.telemetry_retention_days if policy else 0,
    }

    models = _rows(
        model_qs.order_by("-updated_at"),
        "public_id",
        "code",
        "name",
        "project_public_id",
        "site_reference",
        "discipline_code",
        "model_type_code",
        "file_format_code",
        "status_code",
        "current_revision_code",
        "last_published_at",
        "version",
    )
    revisions = _rows(
        revision_qs.select_related("model").order_by("-created_at"),
        "public_id",
        "model__public_id",
        "model__code",
        "revision_code",
        "issue_purpose_code",
        "status_code",
        "submitted_at",
        "approved_at",
        "version",
    )
    federations = _rows(
        federation_qs.order_by("-updated_at"),
        "public_id",
        "code",
        "name",
        "project_public_id",
        "status_code",
        "model_count",
        "coordination_date",
        "version",
    )
    clashes = _rows(
        clash_qs.select_related("federation").order_by("status_code", "-severity_code", "due_date"),
        "public_id",
        "federation__code",
        "clash_number",
        "clash_type_code",
        "severity_code",
        "discipline_a_code",
        "discipline_b_code",
        "title",
        "status_code",
        "due_date",
        "resolution_note",
        "version",
    )
    issues = _rows(
        issue_qs.order_by("status_code", "-priority_code", "due_date"),
        "public_id",
        "issue_code",
        "category_code",
        "priority_code",
        "title",
        "status_code",
        "site_reference",
        "due_date",
        "version",
    )
    devices = _rows(
        device_qs.order_by("status_code", "code"),
        "public_id",
        "code",
        "name",
        "device_type_code",
        "metric_code",
        "unit_code",
        "status_code",
        "site_reference",
        "last_seen_at",
        "threshold_configuration",
        "version",
    )
    telemetry = _rows(
        telemetry_qs.select_related("device").order_by("-observed_at"),
        "public_id",
        "device__public_id",
        "device__code",
        "observed_at",
        "metric_code",
        "numeric_value",
        "text_value",
        "unit_code",
        "quality_code",
        limit=100,
    )
    alerts = _rows(
        alert_qs.select_related("device").order_by("status_code", "-triggered_at"),
        "public_id",
        "alert_code",
        "device__code",
        "alert_type_code",
        "severity_code",
        "status_code",
        "message",
        "triggered_at",
        "acknowledged_at",
        "resolved_at",
        "version",
    )
    assets = _rows(
        asset_qs.order_by("operation_status_code", "asset_tag"),
        "public_id",
        "asset_tag",
        "asset_name",
        "classification_code",
        "site_reference",
        "model_element_reference",
        "manufacturer",
        "serial_number",
        "commissioned_on",
        "warranty_end_on",
        "operation_status_code",
        "maintainable",
        "version",
    )

    return {
        "company": _company_payload(company),
        "policy": policy_payload,
        "metrics": metrics,
        "models": models,
        "revisions": revisions,
        "federations": federations,
        "clashes": clashes,
        "issues": issues,
        "devices": devices,
        "telemetry": telemetry,
        "alerts": alerts,
        "assets": assets,
    }
