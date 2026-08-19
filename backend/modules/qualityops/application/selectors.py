from __future__ import annotations

from collections import Counter
from datetime import timedelta
from typing import Any

from django.db.models import Q
from django.utils import timezone

from modules.qualityops.models import (
    InspectionTestPlan,
    NonConformanceReport,
    QualityApproval,
    QualityCorrectiveAction,
    QualityInspection,
    QualityInspectionRequest,
    QualityPolicyVersion,
    QualityRisk,
    QualityTestResult,
)
from modules.tenant.models import Company


def _iso(value: Any) -> str | None:
    return value.isoformat() if value is not None else None


def _policy_codes(company: Company, key: str) -> list[str]:
    now = timezone.now()
    configurations = (
        QualityPolicyVersion.objects.filter(
            company=company,
            published_at__isnull=False,
            published_at__lte=now,
            retired_at__isnull=True,
            effective_from__lte=now,
        )
        .filter(Q(effective_to__isnull=True) | Q(effective_to__gt=now))
        .values_list("configuration", flat=True)
    )
    values: set[str] = set()
    for configuration in configurations:
        configured = configuration.get(key, []) if isinstance(configuration, dict) else []
        if isinstance(configured, list):
            values.update(
                str(item).strip().upper()
                for item in configured
                if isinstance(item, str) and item.strip()
            )
    return sorted(values)


def quality_overview(company: Company) -> dict[str, Any]:
    now = timezone.now()
    today = timezone.localdate()
    inspection_horizon = now + timedelta(days=7)
    recent_window = now - timedelta(days=30)

    policies = QualityPolicyVersion.objects.filter(company=company)
    itps = InspectionTestPlan.objects.filter(company=company).select_related("policy")
    requests = QualityInspectionRequest.objects.filter(company=company).select_related(
        "policy", "itp"
    )
    inspections = QualityInspection.objects.filter(company=company).select_related(
        "policy", "request"
    )
    tests = QualityTestResult.objects.filter(company=company).select_related(
        "policy", "inspection"
    )
    ncrs = NonConformanceReport.objects.filter(company=company).select_related("policy")
    actions = QualityCorrectiveAction.objects.filter(company=company).select_related("policy")
    approvals = QualityApproval.objects.filter(company=company).select_related("policy")
    risks = QualityRisk.objects.filter(company=company).select_related("policy")

    active_itp_statuses = _policy_codes(company, "active_itp_statuses")
    open_request_statuses = _policy_codes(company, "open_request_statuses")
    open_ncr_statuses = _policy_codes(company, "open_ncr_statuses")
    open_action_statuses = _policy_codes(company, "open_action_statuses")
    critical_severity_codes = _policy_codes(company, "critical_severity_codes")
    accepted_inspection_results = _policy_codes(company, "accepted_inspection_results")
    accepted_test_results = _policy_codes(company, "accepted_test_results")

    active_itps = itps.filter(status_code__in=active_itp_statuses)
    open_requests = requests.filter(status_code__in=open_request_statuses)
    request_watch = open_requests.filter(requested_for__lte=inspection_horizon)
    completed_recent = inspections.filter(completed_at__gte=recent_window)
    accepted_recent = completed_recent.filter(result_code__in=accepted_inspection_results)
    inspection_watch = inspections.filter(
        completed_at__isnull=True, scheduled_at__lte=inspection_horizon
    )
    failed_inspections = inspections.filter(completed_at__isnull=False).exclude(
        result_code__in=accepted_inspection_results
    )
    failed_tests = tests.exclude(result_code__in=accepted_test_results)
    open_ncrs = ncrs.filter(status_code__in=open_ncr_statuses)
    critical_ncrs = open_ncrs.filter(severity_code__in=critical_severity_codes)
    overdue_ncrs = open_ncrs.filter(due_at__lt=now)
    open_actions = actions.filter(status_code__in=open_action_statuses)
    overdue_actions = open_actions.filter(due_at__lt=now)
    pending_approvals = approvals.filter(decided_at__isnull=True)
    open_risks = risks.filter(resolved_at__isnull=True)

    completed_count = completed_recent.count()
    accepted_count = accepted_recent.count()
    first_pass_rate = round((accepted_count / completed_count) * 100, 1) if completed_count else 0.0

    itp_items = [
        {
            "public_id": str(item.public_id),
            "itp_code": item.itp_code,
            "discipline_code": item.discipline_code,
            "work_package_code": item.work_package_code,
            "revision": item.revision,
            "status_code": item.status_code,
            "title": item.title,
            "hold_point_count": (
                len(item.hold_points) if isinstance(item.hold_points, list) else 0
            ),
            "witness_point_count": (
                len(item.witness_points) if isinstance(item.witness_points, list) else 0
            ),
            "version": item.version,
        }
        for item in active_itps.order_by("discipline_code", "itp_code")[:12]
    ]

    request_items = [
        {
            "public_id": str(item.public_id),
            "request_code": item.request_code,
            "request_type_code": item.request_type_code,
            "activity_code": item.activity_code,
            "lot_or_batch_code": item.lot_or_batch_code,
            "status_code": item.status_code,
            "requested_for": _iso(item.requested_for),
            "overdue": item.requested_for < now,
            "itp_code": item.itp.itp_code if item.itp else None,
            "version": item.version,
        }
        for item in request_watch.order_by("requested_for")[:12]
    ]

    inspection_items = [
        {
            "public_id": str(item.public_id),
            "inspection_code": item.inspection_code,
            "inspection_type_code": item.inspection_type_code,
            "status_code": item.status_code,
            "result_code": item.result_code,
            "scheduled_at": _iso(item.scheduled_at),
            "completed_at": _iso(item.completed_at),
            "score_percent": str(item.score_percent) if item.score_percent is not None else None,
            "sample_size": item.sample_size,
            "accepted_quantity": item.accepted_quantity,
            "rejected_quantity": item.rejected_quantity,
            "overdue": item.completed_at is None and item.scheduled_at < now,
        }
        for item in inspection_watch.order_by("scheduled_at")[:12]
    ]

    ncr_items = [
        {
            "public_id": str(item.public_id),
            "ncr_code": item.ncr_code,
            "category_code": item.category_code,
            "severity_code": item.severity_code,
            "status_code": item.status_code,
            "title": item.title,
            "detected_at": _iso(item.detected_at),
            "due_at": _iso(item.due_at),
            "overdue": bool(item.due_at and item.due_at < now),
            "version": item.version,
        }
        for item in open_ncrs.order_by("due_at", "-detected_at")[:12]
    ]

    action_items = [
        {
            "public_id": str(item.public_id),
            "action_code": item.action_code,
            "source_type_code": item.source_type_code,
            "priority_code": item.priority_code,
            "status_code": item.status_code,
            "title": item.title,
            "due_at": _iso(item.due_at),
            "overdue": bool(item.due_at and item.due_at < now),
            "version": item.version,
        }
        for item in open_actions.order_by("due_at", "-created_at")[:12]
    ]

    test_items = [
        {
            "public_id": str(item.public_id),
            "test_code": item.test_code,
            "test_type_code": item.test_type_code,
            "specimen_code": item.specimen_code,
            "result_code": item.result_code,
            "measured_value": str(item.measured_value) if item.measured_value is not None else None,
            "unit_code": item.unit_code,
            "tested_at": _iso(item.tested_at),
            "inspection_code": item.inspection.inspection_code if item.inspection else None,
        }
        for item in failed_tests.order_by("-tested_at")[:12]
    ]

    approval_items = [
        {
            "public_id": str(item.public_id),
            "entity_type_code": item.entity_type_code,
            "entity_public_id": str(item.entity_public_id),
            "step_code": item.step_code,
            "status_code": item.status_code,
            "requested_at": _iso(item.requested_at),
            "due_at": _iso(item.due_at),
            "version": item.version,
        }
        for item in pending_approvals.order_by("due_at", "requested_at")[:12]
    ]

    risk_items = [
        {
            "public_id": str(item.public_id),
            "linked_entity_type_code": item.linked_entity_type_code,
            "risk_code": item.risk_code,
            "severity_code": item.severity_code,
            "status_code": item.status_code,
            "message": item.message,
            "due_at": _iso(item.due_at),
            "overdue": bool(item.due_at and item.due_at < now),
            "version": item.version,
        }
        for item in open_risks.order_by("due_at", "-created_at")[:12]
    ]

    ncr_severity = Counter(open_ncrs.values_list("severity_code", flat=True))
    risk_severity = Counter(open_risks.values_list("severity_code", flat=True))

    return {
        "generated_at": now.isoformat(),
        "company": {
            "public_id": str(company.public_id),
            "code": company.code,
            "display_name": company.display_name,
            "locale": company.locale,
            "timezone": company.timezone,
            "currency": company.currency,
            "unit_system_code": company.unit_system_code,
        },
        "summary": {
            "published_policy_count": policies.filter(
                published_at__isnull=False, retired_at__isnull=True
            ).count(),
            "active_itp_count": active_itps.count(),
            "open_request_count": open_requests.count(),
            "request_due_count": request_watch.count(),
            "inspection_due_count": inspection_watch.count(),
            "failed_inspection_count": failed_inspections.count(),
            "completed_inspection_30d_count": completed_count,
            "first_pass_acceptance_percent": first_pass_rate,
            "failed_test_count": failed_tests.count(),
            "open_ncr_count": open_ncrs.count(),
            "critical_ncr_count": critical_ncrs.count(),
            "overdue_ncr_count": overdue_ncrs.count(),
            "open_action_count": open_actions.count(),
            "overdue_action_count": overdue_actions.count(),
            "pending_approval_count": pending_approvals.count(),
            "open_risk_count": open_risks.count(),
        },
        "active_itps": itp_items,
        "inspection_queue": request_items,
        "inspection_watch": inspection_items,
        "open_ncrs": ncr_items,
        "open_actions": action_items,
        "failed_tests": test_items,
        "pending_approvals": approval_items,
        "open_risks": risk_items,
        "ncr_severity": [
            {"severity_code": code, "count": count}
            for code, count in sorted(ncr_severity.items())
        ],
        "risk_severity": [
            {"severity_code": code, "count": count}
            for code, count in sorted(risk_severity.items())
        ],
        "governance": {
            "workflow_source": "versioned_tenant_policy",
            "inspection_types_hardcoded": False,
            "test_types_hardcoded": False,
            "acceptance_criteria_hardcoded": False,
            "disposition_codes_hardcoded": False,
            "cross_tenant_records_allowed": False,
            "evidence_references_exposed": False,
            "maker_checker_supported": True,
            "project_adapter_boundary": "project_public_id",
            "location_adapter_boundary": "location_public_id",
            "supplier_adapter_boundary": "supplier_public_id",
            "laboratory_adapter_boundary": "provider_neutral",
            "snapshot_date": today.isoformat(),
        },
    }
