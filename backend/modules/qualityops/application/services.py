from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied

from modules.platform.audit import AuditRecord, append_audit
from modules.platform.events import EventRecord, append_event
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
from modules.tenant.application.context import TenantContext
from modules.tenant.models import Membership


@dataclass(frozen=True, slots=True)
class RequestEvidence:
    request_id: uuid.UUID
    correlation_id: uuid.UUID
    ip_address: str | None = None
    user_agent: str = ""


def _actor(context: TenantContext) -> uuid.UUID:
    return context.principal.user.public_id


def _audit(
    *,
    context: TenantContext,
    evidence: RequestEvidence,
    action: str,
    entity_type: str,
    entity_public_id: uuid.UUID,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
    reason_code: str = "",
) -> None:
    append_audit(
        AuditRecord(
            action=action,
            entity_type=entity_type,
            entity_public_id=entity_public_id,
            actor_public_id=_actor(context),
            company_public_id=context.company.public_id,
            request_id=evidence.request_id,
            correlation_id=evidence.correlation_id,
            ip_address=evidence.ip_address,
            user_agent=evidence.user_agent,
            reason_code=reason_code,
            before=before or {},
            after=after or {},
        )
    )


def _event(
    *,
    context: TenantContext,
    evidence: RequestEvidence,
    event_type: str,
    aggregate_type: str,
    aggregate_public_id: uuid.UUID,
    aggregate_version: int,
    payload: dict[str, Any],
) -> None:
    append_event(
        EventRecord(
            event_type=event_type,
            aggregate_type=aggregate_type,
            aggregate_public_id=aggregate_public_id,
            aggregate_version=aggregate_version,
            company_public_id=context.company.public_id,
            correlation_id=evidence.correlation_id,
            payload=payload,
        )
    )


def _active_policy(company_id: int, public_id: uuid.UUID) -> QualityPolicyVersion | None:
    now = timezone.now()
    return (
        QualityPolicyVersion.objects.filter(
            company_id=company_id,
            public_id=public_id,
            published_at__isnull=False,
            published_at__lte=now,
            retired_at__isnull=True,
            effective_from__lte=now,
        )
        .filter(Q(effective_to__isnull=True) | Q(effective_to__gt=now))
        .first()
    )


def _policy_for(context: TenantContext, public_id: uuid.UUID) -> QualityPolicyVersion:
    policy = _active_policy(context.company.id, public_id)
    if not policy:
        raise ValidationError({"policy_public_id": "Published quality policy not found"})
    return policy


def _configured_code(policy: QualityPolicyVersion, key: str, fallback: str = "") -> str:
    value = policy.configuration.get(key, fallback)
    if not isinstance(value, str) or not value.strip():
        raise ValidationError({"policy_public_id": f"Policy has no {key}"})
    return value.strip().upper()


def _transition(
    policy: QualityPolicyVersion,
    key: str,
    current: str,
    target: str,
) -> dict[str, Any]:
    for item in policy.configuration.get(key, []):
        if (
            isinstance(item, dict)
            and str(item.get("from", "")).upper() == current.upper()
            and str(item.get("to", "")).upper() == target.upper()
        ):
            return item
    raise ValidationError(
        {"target_status_code": f"Transition {current} to {target} is not configured"}
    )


def _check_version(instance: Any, expected_version: int | None) -> None:
    if expected_version is not None and instance.version != expected_version:
        raise ValidationError({"expected_version": "Record was modified by another request"})


def _require_membership(context: TenantContext, public_id: uuid.UUID, field: str) -> None:
    now = timezone.now()
    membership_exists = (
        Membership.objects.filter(
            company=context.company,
            public_id=public_id,
            effective_from__lte=now,
            suspended_at__isnull=True,
            terminated_at__isnull=True,
        )
        .filter(Q(effective_to__isnull=True) | Q(effective_to__gt=now))
        .exists()
    )
    if not membership_exists:
        raise ValidationError({field: "Active tenant membership not found"})


def _approvals_met(
    *,
    company_id: int,
    entity_type_code: str,
    entity_public_id: uuid.UUID,
    transition: dict[str, Any],
) -> bool:
    requirements = transition.get("required_approvals", [])
    if not requirements:
        return True
    for requirement in requirements:
        if not isinstance(requirement, dict):
            return False
        step_code = str(requirement.get("step_code", "")).upper()
        statuses = [str(value).upper() for value in requirement.get("accepted_statuses", [])]
        if not step_code or not statuses:
            return False
        if not QualityApproval.objects.filter(
            company_id=company_id,
            entity_type_code=entity_type_code,
            entity_public_id=entity_public_id,
            step_code=step_code,
            status_code__in=statuses,
        ).exists():
            return False
    return True


def _publish_change(
    *,
    context: TenantContext,
    evidence: RequestEvidence,
    action: str,
    entity_type: str,
    instance: Any,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
    reason_code: str = "",
) -> None:
    _audit(
        context=context,
        evidence=evidence,
        action=action,
        entity_type=entity_type,
        entity_public_id=instance.public_id,
        before=before,
        after=after,
        reason_code=reason_code,
    )
    _event(
        context=context,
        evidence=evidence,
        event_type=action,
        aggregate_type=entity_type,
        aggregate_public_id=instance.public_id,
        aggregate_version=getattr(instance, "version", 1),
        payload=after or {},
    )


@transaction.atomic
def create_policy(
    *, context: TenantContext, evidence: RequestEvidence, attributes: dict[str, Any]
) -> QualityPolicyVersion:
    context.require("quality.configure")
    policy = QualityPolicyVersion(
        company=context.company,
        created_by_membership_public_id=context.membership.public_id,
        **attributes,
    )
    policy.full_clean()
    policy.save()
    _publish_change(
        context=context,
        evidence=evidence,
        action="quality.policy.created",
        entity_type="quality_policy",
        instance=policy,
        after={
            "code": policy.code,
            "version": policy.version,
            "status_code": policy.status_code,
            "published": policy.published_at is not None,
        },
    )
    return policy


@transaction.atomic
def create_itp(
    *,
    context: TenantContext,
    evidence: RequestEvidence,
    policy_public_id: uuid.UUID,
    attributes: dict[str, Any],
) -> InspectionTestPlan:
    context.require("quality.manage")
    policy = _policy_for(context, policy_public_id)
    item = InspectionTestPlan(
        company=context.company,
        policy=policy,
        status_code=_configured_code(policy, "initial_itp_status"),
        **attributes,
    )
    item.full_clean()
    item.save()
    _publish_change(
        context=context,
        evidence=evidence,
        action="quality.itp.created",
        entity_type="quality_itp",
        instance=item,
        after={
            "itp_code": item.itp_code,
            "revision": item.revision,
            "discipline_code": item.discipline_code,
            "status_code": item.status_code,
        },
    )
    return item


@transaction.atomic
def transition_itp(
    *,
    context: TenantContext,
    evidence: RequestEvidence,
    itp_public_id: uuid.UUID,
    target_status_code: str,
    expected_version: int | None = None,
) -> InspectionTestPlan:
    item = (
        InspectionTestPlan.objects.select_for_update()
        .select_related("policy")
        .filter(company=context.company, public_id=itp_public_id)
        .first()
    )
    if not item:
        raise ValidationError({"itp_public_id": "Inspection test plan not found"})
    transition = _transition(item.policy, "itp_transitions", item.status_code, target_status_code)
    context.require(str(transition.get("permission") or "quality.manage"))
    _check_version(item, expected_version)
    if not _approvals_met(
        company_id=context.company.id,
        entity_type_code="ITP",
        entity_public_id=item.public_id,
        transition=transition,
    ):
        raise ValidationError({"target_status_code": "Required approval is not complete"})
    before = item.status_code
    item.status_code = target_status_code.strip().upper()
    item.version += 1
    if transition.get("milestone") == "approved":
        item.approved_at = timezone.now()
        item.approved_by_membership_public_id = context.membership.public_id
    item.full_clean()
    item.save()
    _publish_change(
        context=context,
        evidence=evidence,
        action="quality.itp.transitioned",
        entity_type="quality_itp",
        instance=item,
        before={"status_code": before},
        after={"status_code": item.status_code},
    )
    return item


@transaction.atomic
def create_inspection_request(
    *,
    context: TenantContext,
    evidence: RequestEvidence,
    policy_public_id: uuid.UUID,
    itp_public_id: uuid.UUID | None,
    attributes: dict[str, Any],
) -> QualityInspectionRequest:
    context.require("quality.inspect")
    policy = _policy_for(context, policy_public_id)
    itp = None
    if itp_public_id:
        itp = InspectionTestPlan.objects.filter(
            company=context.company, policy=policy, public_id=itp_public_id
        ).first()
        if not itp:
            raise ValidationError({"itp_public_id": "Tenant inspection test plan not found"})
    assignee = attributes.get("assigned_inspector_membership_public_id")
    if assignee:
        _require_membership(context, assignee, "assigned_inspector_membership_public_id")
    item = QualityInspectionRequest(
        company=context.company,
        policy=policy,
        itp=itp,
        status_code=_configured_code(policy, "initial_request_status"),
        requested_by_membership_public_id=context.membership.public_id,
        **attributes,
    )
    item.full_clean()
    item.save()
    _publish_change(
        context=context,
        evidence=evidence,
        action="quality.inspection_request.created",
        entity_type="quality_inspection_request",
        instance=item,
        after={
            "request_code": item.request_code,
            "request_type_code": item.request_type_code,
            "activity_code": item.activity_code,
            "status_code": item.status_code,
        },
    )
    return item


@transaction.atomic
def transition_inspection_request(
    *,
    context: TenantContext,
    evidence: RequestEvidence,
    request_public_id: uuid.UUID,
    target_status_code: str,
    expected_version: int | None = None,
    closure_note: str = "",
) -> QualityInspectionRequest:
    item = (
        QualityInspectionRequest.objects.select_for_update()
        .select_related("policy")
        .filter(company=context.company, public_id=request_public_id)
        .first()
    )
    if not item:
        raise ValidationError({"request_public_id": "Inspection request not found"})
    transition = _transition(
        item.policy, "request_transitions", item.status_code, target_status_code
    )
    context.require(str(transition.get("permission") or "quality.inspect"))
    _check_version(item, expected_version)
    if not _approvals_met(
        company_id=context.company.id,
        entity_type_code="INSPECTION_REQUEST",
        entity_public_id=item.public_id,
        transition=transition,
    ):
        raise ValidationError({"target_status_code": "Required approval is not complete"})
    before = item.status_code
    item.status_code = target_status_code.strip().upper()
    item.version += 1
    if transition.get("milestone") == "closed":
        item.closed_at = timezone.now()
        if closure_note:
            item.notes = f"{item.notes}\n{closure_note}".strip()
    item.full_clean()
    item.save()
    _publish_change(
        context=context,
        evidence=evidence,
        action="quality.inspection_request.transitioned",
        entity_type="quality_inspection_request",
        instance=item,
        before={"status_code": before},
        after={"status_code": item.status_code},
    )
    return item


@transaction.atomic
def record_inspection(
    *,
    context: TenantContext,
    evidence: RequestEvidence,
    policy_public_id: uuid.UUID,
    request_public_id: uuid.UUID | None,
    attributes: dict[str, Any],
) -> QualityInspection:
    context.require("quality.inspect")
    policy = _policy_for(context, policy_public_id)
    request_item = None
    if request_public_id:
        request_item = QualityInspectionRequest.objects.filter(
            company=context.company, policy=policy, public_id=request_public_id
        ).first()
        if not request_item:
            raise ValidationError({"request_public_id": "Tenant inspection request not found"})
    inspector = attributes.get("inspector_membership_public_id")
    if inspector:
        _require_membership(context, inspector, "inspector_membership_public_id")
    payload = dict(attributes)
    completed_at = payload.get("completed_at")
    status_key = "completed_inspection_status" if completed_at else "initial_inspection_status"
    status_code = _configured_code(policy, status_key, "COMPLETED" if completed_at else "SCHEDULED")
    item = QualityInspection(
        company=context.company,
        policy=policy,
        request=request_item,
        status_code=status_code,
        **payload,
    )
    item.full_clean()
    item.save()
    _publish_change(
        context=context,
        evidence=evidence,
        action="quality.inspection.recorded",
        entity_type="quality_inspection",
        instance=item,
        after={
            "inspection_code": item.inspection_code,
            "inspection_type_code": item.inspection_type_code,
            "status_code": item.status_code,
            "result_code": item.result_code,
        },
    )
    return item


@transaction.atomic
def record_test_result(
    *,
    context: TenantContext,
    evidence: RequestEvidence,
    policy_public_id: uuid.UUID,
    inspection_public_id: uuid.UUID | None,
    attributes: dict[str, Any],
) -> QualityTestResult:
    context.require("quality.inspect")
    policy = _policy_for(context, policy_public_id)
    inspection = None
    if inspection_public_id:
        inspection = QualityInspection.objects.filter(
            company=context.company, policy=policy, public_id=inspection_public_id
        ).first()
        if not inspection:
            raise ValidationError({"inspection_public_id": "Tenant inspection not found"})
    tester = attributes.get("tested_by_membership_public_id")
    if tester:
        _require_membership(context, tester, "tested_by_membership_public_id")
    item = QualityTestResult(
        company=context.company, policy=policy, inspection=inspection, **attributes
    )
    item.full_clean()
    item.save()
    _publish_change(
        context=context,
        evidence=evidence,
        action="quality.test_result.recorded",
        entity_type="quality_test_result",
        instance=item,
        after={
            "test_code": item.test_code,
            "test_type_code": item.test_type_code,
            "result_code": item.result_code,
        },
    )
    return item


@transaction.atomic
def create_ncr(
    *,
    context: TenantContext,
    evidence: RequestEvidence,
    policy_public_id: uuid.UUID,
    attributes: dict[str, Any],
) -> NonConformanceReport:
    context.require("quality.ncr")
    policy = _policy_for(context, policy_public_id)
    responsible = attributes.get("responsible_membership_public_id")
    if responsible:
        _require_membership(context, responsible, "responsible_membership_public_id")
    item = NonConformanceReport(
        company=context.company,
        policy=policy,
        status_code=_configured_code(policy, "initial_ncr_status"),
        detected_by_membership_public_id=context.membership.public_id,
        **attributes,
    )
    item.full_clean()
    item.save()
    _publish_change(
        context=context,
        evidence=evidence,
        action="quality.ncr.created",
        entity_type="quality_ncr",
        instance=item,
        after={
            "ncr_code": item.ncr_code,
            "severity_code": item.severity_code,
            "category_code": item.category_code,
            "status_code": item.status_code,
        },
    )
    return item


@transaction.atomic
def transition_ncr(
    *,
    context: TenantContext,
    evidence: RequestEvidence,
    ncr_public_id: uuid.UUID,
    target_status_code: str,
    expected_version: int | None = None,
    root_cause: str = "",
    disposition_code: str = "",
    closure_note: str = "",
) -> NonConformanceReport:
    item = (
        NonConformanceReport.objects.select_for_update()
        .select_related("policy")
        .filter(company=context.company, public_id=ncr_public_id)
        .first()
    )
    if not item:
        raise ValidationError({"ncr_public_id": "Nonconformance report not found"})
    transition = _transition(item.policy, "ncr_transitions", item.status_code, target_status_code)
    context.require(str(transition.get("permission") or "quality.ncr"))
    _check_version(item, expected_version)
    if not _approvals_met(
        company_id=context.company.id,
        entity_type_code="NCR",
        entity_public_id=item.public_id,
        transition=transition,
    ):
        raise ValidationError({"target_status_code": "Required approval is not complete"})
    before = item.status_code
    item.status_code = target_status_code.strip().upper()
    item.version += 1
    if root_cause:
        item.root_cause = root_cause.strip()
    if disposition_code:
        item.disposition_code = disposition_code.strip().upper()
    if transition.get("milestone") == "closed":
        item.closed_at = timezone.now()
        item.closure_note = closure_note.strip()
    item.full_clean()
    item.save()
    _publish_change(
        context=context,
        evidence=evidence,
        action="quality.ncr.transitioned",
        entity_type="quality_ncr",
        instance=item,
        before={"status_code": before},
        after={"status_code": item.status_code, "disposition_code": item.disposition_code},
    )
    return item


@transaction.atomic
def create_action(
    *,
    context: TenantContext,
    evidence: RequestEvidence,
    policy_public_id: uuid.UUID,
    attributes: dict[str, Any],
) -> QualityCorrectiveAction:
    context.require("quality.manage")
    policy = _policy_for(context, policy_public_id)
    owner = attributes.get("owner_membership_public_id")
    if owner:
        _require_membership(context, owner, "owner_membership_public_id")
    item = QualityCorrectiveAction(
        company=context.company,
        policy=policy,
        status_code=_configured_code(policy, "initial_action_status"),
        **attributes,
    )
    item.full_clean()
    item.save()
    _publish_change(
        context=context,
        evidence=evidence,
        action="quality.corrective_action.created",
        entity_type="quality_corrective_action",
        instance=item,
        after={
            "action_code": item.action_code,
            "priority_code": item.priority_code,
            "status_code": item.status_code,
        },
    )
    return item


@transaction.atomic
def transition_action(
    *,
    context: TenantContext,
    evidence: RequestEvidence,
    action_public_id: uuid.UUID,
    target_status_code: str,
    expected_version: int | None = None,
    closure_note: str = "",
) -> QualityCorrectiveAction:
    item = (
        QualityCorrectiveAction.objects.select_for_update()
        .select_related("policy")
        .filter(company=context.company, public_id=action_public_id)
        .first()
    )
    if not item:
        raise ValidationError({"action_public_id": "Corrective action not found"})
    transition = _transition(
        item.policy, "action_transitions", item.status_code, target_status_code
    )
    context.require(str(transition.get("permission") or "quality.manage"))
    _check_version(item, expected_version)
    if not _approvals_met(
        company_id=context.company.id,
        entity_type_code="ACTION",
        entity_public_id=item.public_id,
        transition=transition,
    ):
        raise ValidationError({"target_status_code": "Required approval is not complete"})
    before = item.status_code
    item.status_code = target_status_code.strip().upper()
    item.version += 1
    milestone = transition.get("milestone")
    if milestone == "completed":
        item.completed_at = timezone.now()
        item.closure_note = closure_note.strip()
    elif milestone == "verified":
        if item.owner_membership_public_id == context.membership.public_id:
            raise PermissionDenied("Corrective-action owner cannot verify their own action")
        item.verified_at = timezone.now()
        item.verified_by_membership_public_id = context.membership.public_id
    item.full_clean()
    item.save()
    _publish_change(
        context=context,
        evidence=evidence,
        action="quality.corrective_action.transitioned",
        entity_type="quality_corrective_action",
        instance=item,
        before={"status_code": before},
        after={"status_code": item.status_code},
    )
    return item


@transaction.atomic
def request_approval(
    *,
    context: TenantContext,
    evidence: RequestEvidence,
    policy_public_id: uuid.UUID,
    attributes: dict[str, Any],
) -> QualityApproval:
    context.require("quality.manage")
    policy = _policy_for(context, policy_public_id)
    requested_from = attributes.get("requested_from_membership_public_id")
    if not requested_from:
        raise ValidationError({"requested_from_membership_public_id": "Approver is required"})
    _require_membership(context, requested_from, "requested_from_membership_public_id")
    if requested_from == context.membership.public_id:
        raise ValidationError(
            {"requested_from_membership_public_id": "Maker and checker must differ"}
        )
    item = QualityApproval(
        company=context.company,
        policy=policy,
        requested_by_membership_public_id=context.membership.public_id,
        requested_at=timezone.now(),
        status_code=_configured_code(policy, "initial_approval_status", "PENDING"),
        **attributes,
    )
    item.full_clean()
    item.save()
    _publish_change(
        context=context,
        evidence=evidence,
        action="quality.approval.requested",
        entity_type="quality_approval",
        instance=item,
        after={
            "entity_type_code": item.entity_type_code,
            "entity_public_id": str(item.entity_public_id),
            "step_code": item.step_code,
            "status_code": item.status_code,
        },
    )
    return item


@transaction.atomic
def decide_approval(
    *,
    context: TenantContext,
    evidence: RequestEvidence,
    approval_public_id: uuid.UUID,
    decision_code: str,
    decision_note: str = "",
    expected_version: int | None = None,
) -> QualityApproval:
    context.require("quality.approve")
    item = (
        QualityApproval.objects.select_for_update()
        .select_related("policy")
        .filter(company=context.company, public_id=approval_public_id)
        .first()
    )
    if not item:
        raise ValidationError({"approval_public_id": "Approval not found"})
    _check_version(item, expected_version)
    if item.decided_at:
        raise ValidationError({"decision_code": "Approval is already decided"})
    if item.requested_by_membership_public_id == context.membership.public_id:
        raise PermissionDenied("Maker cannot decide their own approval")
    if item.requested_from_membership_public_id != context.membership.public_id:
        raise PermissionDenied("Only the assigned checker can decide this approval")
    mapping = item.policy.configuration.get("approval_decisions", {})
    status_code = mapping.get(decision_code.strip().upper()) if isinstance(mapping, dict) else None
    if not isinstance(status_code, str) or not status_code.strip():
        raise ValidationError({"decision_code": "Decision is not configured"})
    before = item.status_code
    item.status_code = status_code.strip().upper()
    item.decided_by_membership_public_id = context.membership.public_id
    item.decided_at = timezone.now()
    item.decision_note = decision_note.strip()
    item.version += 1
    item.full_clean()
    item.save()
    _publish_change(
        context=context,
        evidence=evidence,
        action="quality.approval.decided",
        entity_type="quality_approval",
        instance=item,
        before={"status_code": before},
        after={"status_code": item.status_code},
        reason_code=decision_code.strip().upper(),
    )
    return item


@transaction.atomic
def create_risk(
    *,
    context: TenantContext,
    evidence: RequestEvidence,
    policy_public_id: uuid.UUID,
    attributes: dict[str, Any],
) -> QualityRisk:
    context.require("quality.manage")
    policy = _policy_for(context, policy_public_id)
    item = QualityRisk(
        company=context.company,
        policy=policy,
        status_code=_configured_code(policy, "initial_risk_status"),
        **attributes,
    )
    item.full_clean()
    item.save()
    _publish_change(
        context=context,
        evidence=evidence,
        action="quality.risk.created",
        entity_type="quality_risk",
        instance=item,
        after={
            "risk_code": item.risk_code,
            "severity_code": item.severity_code,
            "status_code": item.status_code,
        },
    )
    return item


@transaction.atomic
def resolve_risk(
    *,
    context: TenantContext,
    evidence: RequestEvidence,
    risk_public_id: uuid.UUID,
    resolution_note: str,
    expected_version: int | None = None,
) -> QualityRisk:
    context.require("quality.manage")
    item = (
        QualityRisk.objects.select_for_update()
        .select_related("policy")
        .filter(company=context.company, public_id=risk_public_id)
        .first()
    )
    if not item:
        raise ValidationError({"risk_public_id": "Quality risk not found"})
    _check_version(item, expected_version)
    if item.resolved_at:
        raise ValidationError({"resolution_note": "Risk is already resolved"})
    before = item.status_code
    item.status_code = _configured_code(item.policy, "resolved_risk_status", "RESOLVED")
    item.resolved_at = timezone.now()
    item.resolved_by_membership_public_id = context.membership.public_id
    item.resolution_note = resolution_note.strip()
    item.version += 1
    item.full_clean()
    item.save()
    _publish_change(
        context=context,
        evidence=evidence,
        action="quality.risk.resolved",
        entity_type="quality_risk",
        instance=item,
        before={"status_code": before},
        after={"status_code": item.status_code},
    )
    return item
