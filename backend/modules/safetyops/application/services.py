from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied

from modules.platform.audit import AuditRecord, append_audit
from modules.platform.events import EventRecord, append_event
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


def _active_policy(company_id: int, public_id: uuid.UUID) -> SafetyPolicyVersion | None:
    now = timezone.now()
    return (
        SafetyPolicyVersion.objects.filter(
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


def _policy_for(context: TenantContext, public_id: uuid.UUID) -> SafetyPolicyVersion:
    policy = _active_policy(context.company.id, public_id)
    if not policy:
        raise ValidationError({"policy_public_id": "Published safety policy not found"})
    return policy


def _configured_code(policy: SafetyPolicyVersion, key: str) -> str:
    value = policy.configuration.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValidationError({"policy_public_id": f"Policy has no {key}"})
    return value.strip().upper()


def _transition(
    policy: SafetyPolicyVersion,
    key: str,
    current: str,
    target: str,
) -> dict[str, Any]:
    configured = policy.configuration.get(key, [])
    for item in configured:
        if (
            isinstance(item, dict)
            and str(item.get("from", "")).upper() == current.upper()
            and str(item.get("to", "")).upper() == target.upper()
        ):
            return item
    raise ValidationError(
        {"target_status_code": f"Transition {current} to {target} is not configured"}
    )


def _check_expected_version(instance: Any, expected_version: int | None) -> None:
    if expected_version is not None and instance.version != expected_version:
        raise ValidationError(
            {"expected_version": "Record was modified by another request"}
        )


def _require_membership(context: TenantContext, public_id: uuid.UUID, field: str) -> None:
    if not Membership.objects.filter(
        company=context.company,
        public_id=public_id,
        suspended_at__isnull=True,
        terminated_at__isnull=True,
    ).exists():
        raise ValidationError({field: "Active tenant membership not found"})


def _required_approvals_met(
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
        if not SafetyApproval.objects.filter(
            company_id=company_id,
            entity_type_code=entity_type_code,
            entity_public_id=entity_public_id,
            step_code=step_code,
            status_code__in=statuses,
        ).exists():
            return False
    return True


@transaction.atomic
def create_policy(
    *, context: TenantContext, evidence: RequestEvidence, attributes: dict[str, Any]
) -> SafetyPolicyVersion:
    context.require("safety.configure")
    policy = SafetyPolicyVersion(
        company=context.company,
        created_by_membership_public_id=context.membership.public_id,
        **attributes,
    )
    policy.full_clean()
    policy.save()
    _audit(
        context=context,
        evidence=evidence,
        action="safety.policy.created",
        entity_type="safety_policy",
        entity_public_id=policy.public_id,
        after={
            "code": policy.code,
            "version": policy.version,
            "status_code": policy.status_code,
            "published": policy.published_at is not None,
        },
    )
    _event(
        context=context,
        evidence=evidence,
        event_type="safety.policy.created",
        aggregate_type="safety_policy",
        aggregate_public_id=policy.public_id,
        aggregate_version=policy.version,
        payload={"code": policy.code, "status_code": policy.status_code},
    )
    return policy


@transaction.atomic
def create_observation(
    *,
    context: TenantContext,
    evidence: RequestEvidence,
    policy_public_id: uuid.UUID,
    attributes: dict[str, Any],
) -> SafetyObservation:
    context.require("safety.manage")
    policy = _policy_for(context, policy_public_id)
    payload = dict(attributes)
    payload.pop("status_code", None)
    observation = SafetyObservation(
        company=context.company,
        policy=policy,
        status_code=_configured_code(policy, "initial_observation_status"),
        observed_by_membership_public_id=context.membership.public_id,
        **payload,
    )
    observation.full_clean()
    observation.save()
    _audit(
        context=context,
        evidence=evidence,
        action="safety.observation.created",
        entity_type="safety_observation",
        entity_public_id=observation.public_id,
        after={
            "observation_code": observation.observation_code,
            "severity_code": observation.severity_code,
            "status_code": observation.status_code,
        },
    )
    _event(
        context=context,
        evidence=evidence,
        event_type="safety.observation.created",
        aggregate_type="safety_observation",
        aggregate_public_id=observation.public_id,
        aggregate_version=observation.version,
        payload={
            "observation_code": observation.observation_code,
            "severity_code": observation.severity_code,
            "status_code": observation.status_code,
        },
    )
    return observation


@transaction.atomic
def transition_observation(
    *,
    context: TenantContext,
    evidence: RequestEvidence,
    observation_public_id: uuid.UUID,
    target_status_code: str,
    expected_version: int | None = None,
    closure_note: str = "",
) -> SafetyObservation:
    observation = (
        SafetyObservation.objects.select_for_update()
        .select_related("policy")
        .filter(company=context.company, public_id=observation_public_id)
        .first()
    )
    if not observation:
        raise ValidationError({"observation_public_id": "Observation not found"})
    transition = _transition(
        observation.policy,
        "observation_transitions",
        observation.status_code,
        target_status_code,
    )
    context.require(str(transition.get("permission") or "safety.manage"))
    _check_expected_version(observation, expected_version)
    if not _required_approvals_met(
        company_id=context.company.id,
        entity_type_code="OBSERVATION",
        entity_public_id=observation.public_id,
        transition=transition,
    ):
        raise ValidationError({"target_status_code": "Required approval is not complete"})
    before = observation.status_code
    observation.status_code = target_status_code.strip().upper()
    observation.version += 1
    if transition.get("milestone") == "closed":
        observation.closed_at = timezone.now()
        observation.closure_note = closure_note.strip()
    observation.full_clean()
    observation.save()
    _audit(
        context=context,
        evidence=evidence,
        action="safety.observation.transitioned",
        entity_type="safety_observation",
        entity_public_id=observation.public_id,
        before={"status_code": before},
        after={"status_code": observation.status_code},
    )
    _event(
        context=context,
        evidence=evidence,
        event_type="safety.observation.transitioned",
        aggregate_type="safety_observation",
        aggregate_public_id=observation.public_id,
        aggregate_version=observation.version,
        payload={"status_code": observation.status_code},
    )
    return observation


@transaction.atomic
def report_incident(
    *,
    context: TenantContext,
    evidence: RequestEvidence,
    policy_public_id: uuid.UUID,
    attributes: dict[str, Any],
) -> SafetyIncident:
    context.require("safety.incident")
    policy = _policy_for(context, policy_public_id)
    payload = dict(attributes)
    payload.pop("status_code", None)
    incident = SafetyIncident(
        company=context.company,
        policy=policy,
        status_code=_configured_code(policy, "initial_incident_status"),
        reported_by_membership_public_id=context.membership.public_id,
        **payload,
    )
    incident.full_clean()
    incident.save()
    critical = {
        str(code).upper()
        for code in policy.configuration.get("critical_severity_codes", [])
    }
    if incident.severity_code in critical:
        risk = SafetyRisk(
            company=context.company,
            policy=policy,
            linked_entity_type_code="INCIDENT",
            linked_entity_public_id=incident.public_id,
            risk_code=str(
                policy.configuration.get("critical_incident_risk_code", "CRITICAL_INCIDENT")
            ),
            severity_code=incident.severity_code,
            status_code=_configured_code(policy, "initial_risk_status"),
            message=f"Critical incident {incident.incident_code} requires executive control",
            due_at=timezone.now(),
        )
        risk.full_clean()
        risk.save()
    _audit(
        context=context,
        evidence=evidence,
        action="safety.incident.reported",
        entity_type="safety_incident",
        entity_public_id=incident.public_id,
        after={
            "incident_code": incident.incident_code,
            "severity_code": incident.severity_code,
            "status_code": incident.status_code,
            "regulator_reportable": incident.regulator_reportable,
        },
    )
    _event(
        context=context,
        evidence=evidence,
        event_type="safety.incident.reported",
        aggregate_type="safety_incident",
        aggregate_public_id=incident.public_id,
        aggregate_version=incident.version,
        payload={
            "incident_code": incident.incident_code,
            "severity_code": incident.severity_code,
            "status_code": incident.status_code,
            "regulator_reportable": incident.regulator_reportable,
        },
    )
    return incident


@transaction.atomic
def transition_incident(
    *,
    context: TenantContext,
    evidence: RequestEvidence,
    incident_public_id: uuid.UUID,
    target_status_code: str,
    expected_version: int | None = None,
    root_cause: str = "",
) -> SafetyIncident:
    incident = (
        SafetyIncident.objects.select_for_update()
        .select_related("policy")
        .filter(company=context.company, public_id=incident_public_id)
        .first()
    )
    if not incident:
        raise ValidationError({"incident_public_id": "Incident not found"})
    transition = _transition(
        incident.policy, "incident_transitions", incident.status_code, target_status_code
    )
    context.require(str(transition.get("permission") or "safety.incident"))
    _check_expected_version(incident, expected_version)
    if not _required_approvals_met(
        company_id=context.company.id,
        entity_type_code="INCIDENT",
        entity_public_id=incident.public_id,
        transition=transition,
    ):
        raise ValidationError({"target_status_code": "Required approval is not complete"})
    before = incident.status_code
    incident.status_code = target_status_code.strip().upper()
    incident.version += 1
    if root_cause.strip():
        incident.root_cause = root_cause.strip()
    if transition.get("milestone") == "closed":
        incident.closed_at = timezone.now()
    incident.full_clean()
    incident.save()
    _audit(
        context=context,
        evidence=evidence,
        action="safety.incident.transitioned",
        entity_type="safety_incident",
        entity_public_id=incident.public_id,
        before={"status_code": before},
        after={"status_code": incident.status_code},
    )
    _event(
        context=context,
        evidence=evidence,
        event_type="safety.incident.transitioned",
        aggregate_type="safety_incident",
        aggregate_public_id=incident.public_id,
        aggregate_version=incident.version,
        payload={"status_code": incident.status_code},
    )
    return incident


@transaction.atomic
def create_permit(
    *,
    context: TenantContext,
    evidence: RequestEvidence,
    policy_public_id: uuid.UUID,
    attributes: dict[str, Any],
) -> PermitToWork:
    context.require("safety.permit")
    policy = _policy_for(context, policy_public_id)
    payload = dict(attributes)
    payload.pop("status_code", None)
    receiver_id = payload.get("receiver_membership_public_id")
    if receiver_id:
        _require_membership(context, receiver_id, "receiver_membership_public_id")
    permit = PermitToWork(
        company=context.company,
        policy=policy,
        status_code=_configured_code(policy, "initial_permit_status"),
        issuer_membership_public_id=context.membership.public_id,
        **payload,
    )
    permit.full_clean()
    permit.save()
    _audit(
        context=context,
        evidence=evidence,
        action="safety.permit.created",
        entity_type="safety_permit",
        entity_public_id=permit.public_id,
        after={
            "permit_code": permit.permit_code,
            "permit_type_code": permit.permit_type_code,
            "risk_level_code": permit.risk_level_code,
            "status_code": permit.status_code,
        },
    )
    _event(
        context=context,
        evidence=evidence,
        event_type="safety.permit.created",
        aggregate_type="safety_permit",
        aggregate_public_id=permit.public_id,
        aggregate_version=permit.version,
        payload={
            "permit_code": permit.permit_code,
            "permit_type_code": permit.permit_type_code,
            "status_code": permit.status_code,
            "valid_until": permit.valid_until.isoformat(),
        },
    )
    return permit


@transaction.atomic
def transition_permit(
    *,
    context: TenantContext,
    evidence: RequestEvidence,
    permit_public_id: uuid.UUID,
    target_status_code: str,
    expected_version: int | None = None,
) -> PermitToWork:
    permit = (
        PermitToWork.objects.select_for_update()
        .select_related("policy")
        .filter(company=context.company, public_id=permit_public_id)
        .first()
    )
    if not permit:
        raise ValidationError({"permit_public_id": "Permit not found"})
    transition = _transition(
        permit.policy, "permit_transitions", permit.status_code, target_status_code
    )
    context.require(str(transition.get("permission") or "safety.permit"))
    _check_expected_version(permit, expected_version)
    if not _required_approvals_met(
        company_id=context.company.id,
        entity_type_code="PERMIT",
        entity_public_id=permit.public_id,
        transition=transition,
    ):
        raise ValidationError({"target_status_code": "Required approval is not complete"})
    before = permit.status_code
    permit.status_code = target_status_code.strip().upper()
    permit.version += 1
    milestone = transition.get("milestone")
    now = timezone.now()
    if milestone == "approved":
        permit.approved_at = now
    elif milestone == "suspended":
        permit.suspended_at = now
    elif milestone == "closed":
        permit.closed_at = now
    permit.full_clean()
    permit.save()
    _audit(
        context=context,
        evidence=evidence,
        action="safety.permit.transitioned",
        entity_type="safety_permit",
        entity_public_id=permit.public_id,
        before={"status_code": before},
        after={"status_code": permit.status_code},
    )
    _event(
        context=context,
        evidence=evidence,
        event_type="safety.permit.transitioned",
        aggregate_type="safety_permit",
        aggregate_public_id=permit.public_id,
        aggregate_version=permit.version,
        payload={"status_code": permit.status_code},
    )
    return permit


@transaction.atomic
def record_inspection(
    *,
    context: TenantContext,
    evidence: RequestEvidence,
    policy_public_id: uuid.UUID,
    attributes: dict[str, Any],
) -> SafetyInspection:
    context.require("safety.manage")
    policy = _policy_for(context, policy_public_id)
    inspection = SafetyInspection(company=context.company, policy=policy, **attributes)
    inspection.full_clean()
    inspection.save()
    accepted = {
        str(code).upper()
        for code in policy.configuration.get("accepted_inspection_results", [])
    }
    if inspection.completed_at and inspection.result_code not in accepted:
        action = CorrectiveAction(
            company=context.company,
            policy=policy,
            action_code=f"AUTO-{inspection.inspection_code}",
            source_type_code="INSPECTION",
            source_public_id=inspection.public_id,
            project_public_id=inspection.project_public_id,
            location_public_id=inspection.location_public_id,
            category_code=str(
                policy.configuration.get("inspection_failure_action_category", "INSPECTION")
            ),
            priority_code=str(
                policy.configuration.get("inspection_failure_action_priority", "HIGH")
            ),
            status_code=_configured_code(policy, "initial_action_status"),
            title=f"Correct failed inspection {inspection.inspection_code}",
            description="Automatically created from a non-accepted inspection result.",
            due_at=timezone.now() + timedelta(
                days=max(
                    0,
                    int(policy.configuration.get("inspection_failure_due_days", 7)),
                )
            ),
        )
        action.full_clean()
        action.save()
    _audit(
        context=context,
        evidence=evidence,
        action="safety.inspection.recorded",
        entity_type="safety_inspection",
        entity_public_id=inspection.public_id,
        after={
            "inspection_code": inspection.inspection_code,
            "status_code": inspection.status_code,
            "result_code": inspection.result_code,
        },
    )
    _event(
        context=context,
        evidence=evidence,
        event_type="safety.inspection.recorded",
        aggregate_type="safety_inspection",
        aggregate_public_id=inspection.public_id,
        aggregate_version=inspection.version,
        payload={
            "inspection_code": inspection.inspection_code,
            "status_code": inspection.status_code,
            "result_code": inspection.result_code,
        },
    )
    return inspection


@transaction.atomic
def record_toolbox_talk(
    *,
    context: TenantContext,
    evidence: RequestEvidence,
    policy_public_id: uuid.UUID,
    attributes: dict[str, Any],
) -> ToolboxTalk:
    context.require("safety.manage")
    policy = _policy_for(context, policy_public_id)
    talk = ToolboxTalk(
        company=context.company,
        policy=policy,
        facilitator_membership_public_id=context.membership.public_id,
        **attributes,
    )
    talk.full_clean()
    talk.save()
    _audit(
        context=context,
        evidence=evidence,
        action="safety.toolbox_talk.recorded",
        entity_type="safety_toolbox_talk",
        entity_public_id=talk.public_id,
        after={
            "talk_code": talk.talk_code,
            "topic_code": talk.topic_code,
            "attendee_count": talk.attendee_count,
            "acknowledgement_count": talk.acknowledgement_count,
        },
    )
    _event(
        context=context,
        evidence=evidence,
        event_type="safety.toolbox_talk.recorded",
        aggregate_type="safety_toolbox_talk",
        aggregate_public_id=talk.public_id,
        aggregate_version=1,
        payload={
            "talk_code": talk.talk_code,
            "topic_code": talk.topic_code,
            "attendee_count": talk.attendee_count,
        },
    )
    return talk


@transaction.atomic
def create_action(
    *,
    context: TenantContext,
    evidence: RequestEvidence,
    policy_public_id: uuid.UUID,
    attributes: dict[str, Any],
) -> CorrectiveAction:
    context.require("safety.manage")
    policy = _policy_for(context, policy_public_id)
    payload = dict(attributes)
    payload.pop("status_code", None)
    owner_id = payload.get("owner_membership_public_id")
    if owner_id:
        _require_membership(context, owner_id, "owner_membership_public_id")
    action = CorrectiveAction(
        company=context.company,
        policy=policy,
        status_code=_configured_code(policy, "initial_action_status"),
        **payload,
    )
    action.full_clean()
    action.save()
    _audit(
        context=context,
        evidence=evidence,
        action="safety.corrective_action.created",
        entity_type="safety_corrective_action",
        entity_public_id=action.public_id,
        after={
            "action_code": action.action_code,
            "priority_code": action.priority_code,
            "status_code": action.status_code,
        },
    )
    _event(
        context=context,
        evidence=evidence,
        event_type="safety.corrective_action.created",
        aggregate_type="safety_corrective_action",
        aggregate_public_id=action.public_id,
        aggregate_version=action.version,
        payload={
            "action_code": action.action_code,
            "priority_code": action.priority_code,
            "status_code": action.status_code,
        },
    )
    return action


@transaction.atomic
def transition_action(
    *,
    context: TenantContext,
    evidence: RequestEvidence,
    action_public_id: uuid.UUID,
    target_status_code: str,
    expected_version: int | None = None,
    closure_note: str = "",
) -> CorrectiveAction:
    action = (
        CorrectiveAction.objects.select_for_update()
        .select_related("policy")
        .filter(company=context.company, public_id=action_public_id)
        .first()
    )
    if not action:
        raise ValidationError({"action_public_id": "Corrective action not found"})
    transition = _transition(
        action.policy, "action_transitions", action.status_code, target_status_code
    )
    context.require(str(transition.get("permission") or "safety.manage"))
    _check_expected_version(action, expected_version)
    if not _required_approvals_met(
        company_id=context.company.id,
        entity_type_code="ACTION",
        entity_public_id=action.public_id,
        transition=transition,
    ):
        raise ValidationError({"target_status_code": "Required approval is not complete"})
    before = action.status_code
    action.status_code = target_status_code.strip().upper()
    action.version += 1
    milestone = transition.get("milestone")
    now = timezone.now()
    if milestone == "completed":
        action.completed_at = now
        action.closure_note = closure_note.strip()
    elif milestone == "verified":
        action.verified_at = now
        action.verified_by_membership_public_id = context.membership.public_id
    action.full_clean()
    action.save()
    _audit(
        context=context,
        evidence=evidence,
        action="safety.corrective_action.transitioned",
        entity_type="safety_corrective_action",
        entity_public_id=action.public_id,
        before={"status_code": before},
        after={"status_code": action.status_code},
    )
    _event(
        context=context,
        evidence=evidence,
        event_type="safety.corrective_action.transitioned",
        aggregate_type="safety_corrective_action",
        aggregate_public_id=action.public_id,
        aggregate_version=action.version,
        payload={"status_code": action.status_code},
    )
    return action


@transaction.atomic
def request_approval(
    *,
    context: TenantContext,
    evidence: RequestEvidence,
    policy_public_id: uuid.UUID,
    attributes: dict[str, Any],
) -> SafetyApproval:
    context.require("safety.manage")
    policy = _policy_for(context, policy_public_id)
    requested_from = attributes.get("requested_from_membership_public_id")
    if not requested_from:
        raise ValidationError({"requested_from_membership_public_id": "Approver is required"})
    _require_membership(context, requested_from, "requested_from_membership_public_id")
    if requested_from == context.membership.public_id:
        raise ValidationError({"requested_from_membership_public_id": "Maker and checker must differ"})
    approval = SafetyApproval(
        company=context.company,
        policy=policy,
        requested_by_membership_public_id=context.membership.public_id,
        requested_at=timezone.now(),
        status_code=str(policy.configuration.get("initial_approval_status", "PENDING")),
        **attributes,
    )
    approval.full_clean()
    approval.save()
    _audit(
        context=context,
        evidence=evidence,
        action="safety.approval.requested",
        entity_type="safety_approval",
        entity_public_id=approval.public_id,
        after={
            "entity_type_code": approval.entity_type_code,
            "entity_public_id": str(approval.entity_public_id),
            "step_code": approval.step_code,
            "status_code": approval.status_code,
        },
    )
    _event(
        context=context,
        evidence=evidence,
        event_type="safety.approval.requested",
        aggregate_type="safety_approval",
        aggregate_public_id=approval.public_id,
        aggregate_version=approval.version,
        payload={
            "entity_type_code": approval.entity_type_code,
            "entity_public_id": str(approval.entity_public_id),
            "step_code": approval.step_code,
            "status_code": approval.status_code,
        },
    )
    return approval


@transaction.atomic
def decide_approval(
    *,
    context: TenantContext,
    evidence: RequestEvidence,
    approval_public_id: uuid.UUID,
    decision_code: str,
    decision_note: str = "",
    expected_version: int | None = None,
) -> SafetyApproval:
    context.require("safety.approve")
    approval = (
        SafetyApproval.objects.select_for_update()
        .select_related("policy")
        .filter(company=context.company, public_id=approval_public_id)
        .first()
    )
    if not approval:
        raise ValidationError({"approval_public_id": "Approval not found"})
    _check_expected_version(approval, expected_version)
    if approval.decided_at:
        raise ValidationError({"decision_code": "Approval is already decided"})
    if approval.requested_by_membership_public_id == context.membership.public_id:
        raise PermissionDenied("Maker cannot decide their own approval")
    mapping = approval.policy.configuration.get("approval_decisions", {})
    status_code = mapping.get(decision_code.strip().upper()) if isinstance(mapping, dict) else None
    if not isinstance(status_code, str) or not status_code.strip():
        raise ValidationError({"decision_code": "Decision is not configured"})
    before = approval.status_code
    approval.status_code = status_code.strip().upper()
    approval.decided_by_membership_public_id = context.membership.public_id
    approval.decided_at = timezone.now()
    approval.decision_note = decision_note.strip()
    approval.version += 1
    approval.full_clean()
    approval.save()
    _audit(
        context=context,
        evidence=evidence,
        action="safety.approval.decided",
        entity_type="safety_approval",
        entity_public_id=approval.public_id,
        before={"status_code": before},
        after={"status_code": approval.status_code},
        reason_code=decision_code.strip().upper(),
    )
    _event(
        context=context,
        evidence=evidence,
        event_type="safety.approval.decided",
        aggregate_type="safety_approval",
        aggregate_public_id=approval.public_id,
        aggregate_version=approval.version,
        payload={
            "entity_type_code": approval.entity_type_code,
            "entity_public_id": str(approval.entity_public_id),
            "step_code": approval.step_code,
            "status_code": approval.status_code,
        },
    )
    return approval


@transaction.atomic
def create_risk(
    *,
    context: TenantContext,
    evidence: RequestEvidence,
    policy_public_id: uuid.UUID,
    attributes: dict[str, Any],
) -> SafetyRisk:
    context.require("safety.manage")
    policy = _policy_for(context, policy_public_id)
    payload = dict(attributes)
    payload.pop("status_code", None)
    risk = SafetyRisk(
        company=context.company,
        policy=policy,
        status_code=_configured_code(policy, "initial_risk_status"),
        **payload,
    )
    risk.full_clean()
    risk.save()
    _audit(
        context=context,
        evidence=evidence,
        action="safety.risk.created",
        entity_type="safety_risk",
        entity_public_id=risk.public_id,
        after={
            "risk_code": risk.risk_code,
            "severity_code": risk.severity_code,
            "status_code": risk.status_code,
        },
    )
    _event(
        context=context,
        evidence=evidence,
        event_type="safety.risk.created",
        aggregate_type="safety_risk",
        aggregate_public_id=risk.public_id,
        aggregate_version=1,
        payload={
            "risk_code": risk.risk_code,
            "severity_code": risk.severity_code,
            "status_code": risk.status_code,
        },
    )
    return risk


@transaction.atomic
def resolve_risk(
    *,
    context: TenantContext,
    evidence: RequestEvidence,
    risk_public_id: uuid.UUID,
    resolution_note: str,
) -> SafetyRisk:
    context.require("safety.manage")
    risk = SafetyRisk.objects.select_for_update().filter(
        company=context.company, public_id=risk_public_id
    ).first()
    if not risk:
        raise ValidationError({"risk_public_id": "Safety risk not found"})
    if risk.resolved_at:
        raise ValidationError({"resolution_note": "Risk is already resolved"})
    before = risk.status_code
    risk.status_code = str(risk.policy.configuration.get("resolved_risk_status", "RESOLVED"))
    risk.resolved_at = timezone.now()
    risk.resolved_by_membership_public_id = context.membership.public_id
    risk.resolution_note = resolution_note.strip()
    risk.full_clean()
    risk.save()
    _audit(
        context=context,
        evidence=evidence,
        action="safety.risk.resolved",
        entity_type="safety_risk",
        entity_public_id=risk.public_id,
        before={"status_code": before},
        after={"status_code": risk.status_code},
    )
    _event(
        context=context,
        evidence=evidence,
        event_type="safety.risk.resolved",
        aggregate_type="safety_risk",
        aggregate_public_id=risk.public_id,
        aggregate_version=2,
        payload={"status_code": risk.status_code},
    )
    return risk
