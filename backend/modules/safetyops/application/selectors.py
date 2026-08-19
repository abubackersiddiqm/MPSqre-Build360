from __future__ import annotations

from collections import Counter
from datetime import timedelta
from typing import Any

from django.db.models import Q
from django.utils import timezone

from modules.safetyops.models import (
    CorrectiveAction,
    PermitToWork,
    SafetyApproval,
    SafetyIncident,
    SafetyInspection,
    SafetyObservation,
    SafetyPolicyVersion,
    SafetyRisk,
    ToolboxTalk,
)
from modules.tenant.models import Company


def _iso(value: Any) -> str | None:
    return value.isoformat() if value is not None else None


def _policy_codes(company: Company, key: str) -> list[str]:
    now = timezone.now()
    configurations = (
        SafetyPolicyVersion.objects.filter(
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


def safety_overview(company: Company) -> dict[str, Any]:
    now = timezone.now()
    today = timezone.localdate()
    permit_horizon = now + timedelta(hours=48)
    inspection_horizon = now + timedelta(days=7)
    training_window = now - timedelta(days=30)

    policies = SafetyPolicyVersion.objects.filter(company=company)
    observations = SafetyObservation.objects.filter(company=company).select_related("policy")
    incidents = SafetyIncident.objects.filter(company=company).select_related("policy")
    permits = PermitToWork.objects.filter(company=company).select_related("policy")
    inspections = SafetyInspection.objects.filter(company=company).select_related("policy")
    talks = ToolboxTalk.objects.filter(company=company).select_related("policy")
    actions = CorrectiveAction.objects.filter(company=company).select_related("policy")
    approvals = SafetyApproval.objects.filter(company=company).select_related("policy")
    risks = SafetyRisk.objects.filter(company=company).select_related("policy")

    open_observation_statuses = _policy_codes(company, "open_observation_statuses")
    open_incident_statuses = _policy_codes(company, "open_incident_statuses")
    active_permit_statuses = _policy_codes(company, "active_permit_statuses")
    open_action_statuses = _policy_codes(company, "open_action_statuses")
    critical_severity_codes = _policy_codes(company, "critical_severity_codes")
    accepted_results = _policy_codes(company, "accepted_inspection_results")

    open_observations = observations.filter(status_code__in=open_observation_statuses)
    open_incidents = incidents.filter(status_code__in=open_incident_statuses)
    critical_incidents = open_incidents.filter(severity_code__in=critical_severity_codes)
    active_permits = permits.filter(status_code__in=active_permit_statuses)
    permit_watch = active_permits.filter(valid_until__lte=permit_horizon)
    inspection_watch = inspections.filter(completed_at__isnull=True, scheduled_at__lte=inspection_horizon)
    failed_inspections = inspections.filter(completed_at__isnull=False).exclude(result_code__in=accepted_results)
    open_actions = actions.filter(status_code__in=open_action_statuses)
    overdue_actions = open_actions.filter(due_at__lt=now)
    recent_talks = talks.filter(delivered_at__gte=training_window)
    pending_approvals = approvals.filter(decided_at__isnull=True)
    open_risks = risks.filter(resolved_at__isnull=True)

    incident_items = [
        {
            "public_id": str(item.public_id),
            "incident_code": item.incident_code,
            "incident_type_code": item.incident_type_code,
            "severity_code": item.severity_code,
            "status_code": item.status_code,
            "title": item.title,
            "occurred_at": _iso(item.occurred_at),
            "reported_at": _iso(item.reported_at),
            "affected_people_count": item.affected_people_count,
            "lost_time": item.lost_time,
            "regulator_reportable": item.regulator_reportable,
            "project_public_id": str(item.project_public_id) if item.project_public_id else None,
            "location_public_id": str(item.location_public_id) if item.location_public_id else None,
            "version": item.version,
        }
        for item in open_incidents.order_by("-reported_at")[:12]
    ]

    permit_items = [
        {
            "public_id": str(item.public_id),
            "permit_code": item.permit_code,
            "permit_type_code": item.permit_type_code,
            "risk_level_code": item.risk_level_code,
            "status_code": item.status_code,
            "work_summary": item.work_summary,
            "valid_from": _iso(item.valid_from),
            "valid_until": _iso(item.valid_until),
            "expires_soon": item.valid_until <= permit_horizon,
            "expired": item.valid_until < now,
            "version": item.version,
        }
        for item in active_permits.order_by("valid_until")[:12]
    ]

    observation_items = [
        {
            "public_id": str(item.public_id),
            "observation_code": item.observation_code,
            "category_code": item.category_code,
            "severity_code": item.severity_code,
            "status_code": item.status_code,
            "title": item.title,
            "observed_at": _iso(item.observed_at),
            "due_at": _iso(item.due_at),
            "overdue": bool(item.due_at and item.due_at < now),
            "version": item.version,
        }
        for item in open_observations.order_by("due_at", "-observed_at")[:12]
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
            "overdue": item.scheduled_at < now and item.completed_at is None,
        }
        for item in inspection_watch.order_by("scheduled_at")[:12]
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

    approval_items = [
        {
            "public_id": str(item.public_id),
            "entity_type_code": item.entity_type_code,
            "entity_public_id": str(item.entity_public_id),
            "step_code": item.step_code,
            "status_code": item.status_code,
            "requested_at": _iso(item.requested_at),
            "due_at": _iso(item.due_at),
            "requested_from_membership_public_id": str(item.requested_from_membership_public_id),
            "version": item.version,
        }
        for item in pending_approvals.order_by("due_at", "requested_at")[:12]
    ]

    risk_items = [
        {
            "public_id": str(item.public_id),
            "linked_entity_type_code": item.linked_entity_type_code,
            "linked_entity_public_id": str(item.linked_entity_public_id) if item.linked_entity_public_id else None,
            "risk_code": item.risk_code,
            "severity_code": item.severity_code,
            "status_code": item.status_code,
            "message": item.message,
            "due_at": _iso(item.due_at),
            "overdue": bool(item.due_at and item.due_at < now),
        }
        for item in open_risks.order_by("due_at", "-created_at")[:12]
    ]

    talk_items = [
        {
            "public_id": str(item.public_id),
            "talk_code": item.talk_code,
            "topic_code": item.topic_code,
            "status_code": item.status_code,
            "title": item.title,
            "delivered_at": _iso(item.delivered_at),
            "attendee_count": item.attendee_count,
            "acknowledgement_count": item.acknowledgement_count,
            "acknowledgement_percent": (
                round((item.acknowledgement_count / item.attendee_count) * 100, 1)
                if item.attendee_count
                else 0.0
            ),
        }
        for item in recent_talks.order_by("-delivered_at")[:12]
    ]

    severity_counts = Counter(open_incidents.values_list("severity_code", flat=True))
    risk_counts = Counter(open_risks.values_list("severity_code", flat=True))

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
            "published_policy_count": policies.filter(published_at__isnull=False, retired_at__isnull=True).count(),
            "open_observation_count": open_observations.count(),
            "overdue_observation_count": open_observations.filter(due_at__lt=now).count(),
            "open_incident_count": open_incidents.count(),
            "critical_incident_count": critical_incidents.count(),
            "active_permit_count": active_permits.count(),
            "permit_expiry_watch_count": permit_watch.count(),
            "inspection_due_count": inspection_watch.count(),
            "failed_inspection_count": failed_inspections.count(),
            "open_action_count": open_actions.count(),
            "overdue_action_count": overdue_actions.count(),
            "toolbox_talk_30d_count": recent_talks.count(),
            "pending_approval_count": pending_approvals.count(),
            "open_risk_count": open_risks.count(),
        },
        "open_incidents": incident_items,
        "active_permits": permit_items,
        "open_observations": observation_items,
        "inspection_watch": inspection_items,
        "open_actions": action_items,
        "pending_approvals": approval_items,
        "open_risks": risk_items,
        "recent_toolbox_talks": talk_items,
        "incident_severity": [
            {"severity_code": code, "count": count}
            for code, count in sorted(severity_counts.items())
        ],
        "risk_severity": [
            {"severity_code": code, "count": count}
            for code, count in sorted(risk_counts.items())
        ],
        "governance": {
            "workflow_source": "versioned_tenant_policy",
            "incident_types_hardcoded": False,
            "permit_types_hardcoded": False,
            "severity_matrix_hardcoded": False,
            "cross_tenant_records_allowed": False,
            "evidence_references_exposed": False,
            "maker_checker_supported": True,
            "project_adapter_boundary": "project_public_id",
            "location_adapter_boundary": "location_public_id",
            "regulatory_adapter_boundary": "provider_neutral",
            "snapshot_date": today.isoformat(),
        },
    }
