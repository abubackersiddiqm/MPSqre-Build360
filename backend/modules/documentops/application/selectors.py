from __future__ import annotations

from collections import Counter
from datetime import timedelta
from typing import Any

from django.db.models import Q
from django.utils import timezone

from modules.documentops.models import (
    ControlledDocument,
    DocumentApproval,
    DocumentControlPolicyVersion,
    DocumentDistribution,
    DocumentRevision,
    DocumentRisk,
    DocumentTransmittal,
    RequestForInformation,
    TechnicalSubmittal,
)
from modules.tenant.models import Company


def _iso(value: Any) -> str | None:
    return value.isoformat() if value is not None else None


def _company_value(company: Company, *names: str, default: str = "") -> str:
    for name in names:
        value = getattr(company, name, None)
        if value is not None:
            return str(value)
    return default


def _policy_codes(company: Company, key: str) -> list[str]:
    now = timezone.now()
    configurations = (
        DocumentControlPolicyVersion.objects.filter(
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


def document_control_overview(company: Company) -> dict[str, Any]:
    now = timezone.now()
    review_horizon = now + timedelta(days=7)
    recent_window = now - timedelta(days=30)

    policies = DocumentControlPolicyVersion.objects.filter(company=company)
    documents = ControlledDocument.objects.filter(company=company).select_related("policy")
    revisions = DocumentRevision.objects.filter(company=company).select_related(
        "policy", "document"
    )
    transmittals = DocumentTransmittal.objects.filter(company=company).select_related(
        "policy"
    )
    rfis = RequestForInformation.objects.filter(company=company).select_related("policy")
    submittals = TechnicalSubmittal.objects.filter(company=company).select_related("policy")
    approvals = DocumentApproval.objects.filter(company=company).select_related("policy")
    distributions = DocumentDistribution.objects.filter(company=company).select_related(
        "policy", "revision", "revision__document"
    )
    risks = DocumentRisk.objects.filter(company=company).select_related("policy")

    active_document_statuses = _policy_codes(company, "active_document_statuses")
    review_revision_statuses = _policy_codes(company, "review_revision_statuses")
    open_transmittal_statuses = _policy_codes(company, "open_transmittal_statuses")
    open_rfi_statuses = _policy_codes(company, "open_rfi_statuses")
    open_submittal_statuses = _policy_codes(company, "open_submittal_statuses")
    critical_priority_codes = _policy_codes(company, "critical_priority_codes")
    approved_decisions = _policy_codes(company, "approved_submittal_decisions")

    active_documents = documents.filter(status_code__in=active_document_statuses)
    revision_queue = revisions.filter(status_code__in=review_revision_statuses)
    revision_due = revision_queue.filter(submitted_at__isnull=False, submitted_at__lte=now)
    open_transmittals = transmittals.filter(status_code__in=open_transmittal_statuses)
    overdue_transmittals = open_transmittals.filter(due_at__lt=now)
    open_rfis = rfis.filter(status_code__in=open_rfi_statuses)
    overdue_rfis = open_rfis.filter(response_due_at__lt=now)
    critical_rfis = open_rfis.filter(priority_code__in=critical_priority_codes)
    open_submittals = submittals.filter(status_code__in=open_submittal_statuses)
    due_submittals = open_submittals.filter(review_due_at__lte=review_horizon)
    overdue_submittals = open_submittals.filter(review_due_at__lt=now)
    reviewed_recent = submittals.filter(reviewed_at__gte=recent_window)
    approved_recent = reviewed_recent.filter(decision_code__in=approved_decisions)
    pending_approvals = approvals.filter(decided_at__isnull=True)
    overdue_approvals = pending_approvals.filter(due_at__lt=now)
    open_risks = risks.filter(resolved_at__isnull=True)
    recent_distributions = distributions.filter(distributed_at__gte=recent_window)
    unacknowledged_distributions = distributions.filter(
        acknowledged_at__isnull=True, revoked_at__isnull=True
    )

    reviewed_count = reviewed_recent.count()
    approved_count = approved_recent.count()
    approval_rate = (
        round((approved_count / reviewed_count) * 100, 1) if reviewed_count else 0.0
    )

    document_items = [
        {
            "public_id": str(item.public_id),
            "document_number": item.document_number,
            "discipline_code": item.discipline_code,
            "document_type_code": item.document_type_code,
            "title": item.title,
            "status_code": item.status_code,
            "current_revision_code": item.current_revision_code,
            "confidentiality_code": item.confidentiality_code,
            "version": item.version,
        }
        for item in active_documents.order_by("discipline_code", "document_number")[:12]
    ]

    revision_items = [
        {
            "public_id": str(item.public_id),
            "document_number": item.document.document_number,
            "revision_code": item.revision_code,
            "purpose_code": item.purpose_code,
            "status_code": item.status_code,
            "submitted_at": _iso(item.submitted_at),
            "issued_at": _iso(item.issued_at),
            "version": item.version,
        }
        for item in revision_queue.order_by("submitted_at", "document__document_number")[:12]
    ]

    transmittal_items = [
        {
            "public_id": str(item.public_id),
            "transmittal_number": item.transmittal_number,
            "direction_code": item.direction_code,
            "status_code": item.status_code,
            "subject": item.subject,
            "issued_at": _iso(item.issued_at),
            "due_at": _iso(item.due_at),
            "document_count": len(item.document_manifest)
            if isinstance(item.document_manifest, list)
            else 0,
            "overdue": bool(item.due_at and item.due_at < now),
            "version": item.version,
        }
        for item in open_transmittals.order_by("due_at", "transmittal_number")[:12]
    ]

    rfi_items = [
        {
            "public_id": str(item.public_id),
            "rfi_number": item.rfi_number,
            "discipline_code": item.discipline_code,
            "priority_code": item.priority_code,
            "status_code": item.status_code,
            "subject": item.subject,
            "raised_at": _iso(item.raised_at),
            "response_due_at": _iso(item.response_due_at),
            "overdue": bool(item.response_due_at and item.response_due_at < now),
            "version": item.version,
        }
        for item in open_rfis.order_by("response_due_at", "rfi_number")[:12]
    ]

    submittal_items = [
        {
            "public_id": str(item.public_id),
            "submittal_number": item.submittal_number,
            "revision_number": item.revision_number,
            "category_code": item.category_code,
            "package_code": item.package_code,
            "status_code": item.status_code,
            "title": item.title,
            "submitted_at": _iso(item.submitted_at),
            "review_due_at": _iso(item.review_due_at),
            "decision_code": item.decision_code,
            "overdue": bool(item.review_due_at and item.review_due_at < now),
            "version": item.version,
        }
        for item in due_submittals.order_by("review_due_at", "submittal_number")[:12]
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
            "overdue": bool(item.due_at and item.due_at < now),
            "version": item.version,
        }
        for item in pending_approvals.order_by("due_at", "requested_at")[:12]
    ]

    distribution_items = [
        {
            "public_id": str(item.public_id),
            "document_number": item.revision.document.document_number,
            "revision_code": item.revision.revision_code,
            "recipient_type_code": item.recipient_type_code,
            "purpose_code": item.purpose_code,
            "status_code": item.status_code,
            "distributed_at": _iso(item.distributed_at),
            "acknowledged_at": _iso(item.acknowledged_at),
            "version": item.version,
        }
        for item in recent_distributions.order_by("-distributed_at")[:12]
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

    discipline_counts = Counter(
        active_documents.values_list("discipline_code", flat=True)
    )
    rfi_priority_counts = Counter(open_rfis.values_list("priority_code", flat=True))
    risk_severity_counts = Counter(open_risks.values_list("severity_code", flat=True))

    return {
        "generated_at": now.isoformat(),
        "company": {
            "public_id": str(company.public_id),
            "display_name": company.display_name,
            "locale": _company_value(company, "default_locale", "locale", default="en-IN"),
            "timezone": _company_value(company, "default_timezone", "timezone", default="UTC"),
            "currency": _company_value(company, "default_currency", "currency", default="USD"),
            "unit_system_code": _company_value(company, "unit_system_code", default="metric"),
        },
        "summary": {
            "published_policy_count": policies.filter(
                published_at__isnull=False, retired_at__isnull=True
            ).count(),
            "active_document_count": active_documents.count(),
            "revision_review_count": revision_queue.count(),
            "revision_due_count": revision_due.count(),
            "open_transmittal_count": open_transmittals.count(),
            "overdue_transmittal_count": overdue_transmittals.count(),
            "open_rfi_count": open_rfis.count(),
            "overdue_rfi_count": overdue_rfis.count(),
            "critical_rfi_count": critical_rfis.count(),
            "open_submittal_count": open_submittals.count(),
            "submittal_due_count": due_submittals.count(),
            "overdue_submittal_count": overdue_submittals.count(),
            "reviewed_submittal_30d_count": reviewed_count,
            "submittal_approval_percent": approval_rate,
            "pending_approval_count": pending_approvals.count(),
            "overdue_approval_count": overdue_approvals.count(),
            "unacknowledged_distribution_count": unacknowledged_distributions.count(),
            "open_risk_count": open_risks.count(),
        },
        "active_documents": document_items,
        "revision_queue": revision_items,
        "open_transmittals": transmittal_items,
        "open_rfis": rfi_items,
        "submittal_queue": submittal_items,
        "pending_approvals": approval_items,
        "recent_distributions": distribution_items,
        "open_risks": risk_items,
        "document_disciplines": [
            {"discipline_code": code, "count": count}
            for code, count in discipline_counts.most_common()
        ],
        "rfi_priorities": [
            {"priority_code": code, "count": count}
            for code, count in rfi_priority_counts.most_common()
        ],
        "risk_severity": [
            {"severity_code": code, "count": count}
            for code, count in risk_severity_counts.most_common()
        ],
        "governance": {
            "workflow_source": "tenant_document_control_policy",
            "document_types_hardcoded": False,
            "discipline_codes_hardcoded": False,
            "revision_schemes_hardcoded": False,
            "submittal_decisions_hardcoded": False,
            "cross_tenant_records_allowed": False,
            "file_references_exposed": False,
            "checksums_exposed": False,
            "maker_checker_supported": True,
            "project_adapter_boundary": "project_public_id",
            "party_adapter_boundary": "party_public_id",
            "storage_adapter_boundary": "file_reference",
            "snapshot_date": timezone.localdate().isoformat(),
        },
    }
