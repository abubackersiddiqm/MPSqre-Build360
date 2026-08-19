from __future__ import annotations

import uuid
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied

from modules.employee.models import Employee
from modules.platform.audit import AuditRecord, append_audit
from modules.platform.events import EventRecord, append_event
from modules.tenant.application.context import TenantContext
from modules.tenant.models import Membership
from modules.workforceops.models import (
    EmployeeSkillCredential,
    SkillDefinition,
    WorkforceApproval,
    WorkforceAssignment,
    WorkforceDemand,
    WorkforcePlan,
    WorkforcePolicyVersion,
    WorkforceRisk,
)


@dataclass(frozen=True, slots=True)
class RequestEvidence:
    request_id: uuid.UUID
    correlation_id: uuid.UUID
    ip_address: str | None = None
    user_agent: str = ""


def _actor(context: TenantContext) -> uuid.UUID:
    return context.principal.user.public_id


def _decimal(value: Any, field_name: str) -> Decimal:
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValidationError({field_name: "Enter a valid decimal value"}) from exc
    return parsed


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


def _active_published_policy(
    *,
    company_id: int,
    public_id: uuid.UUID,
) -> WorkforcePolicyVersion | None:
    now = timezone.now()
    return (
        WorkforcePolicyVersion.objects.filter(
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


def _plan_is_immutable(plan: WorkforcePlan) -> bool:
    configured = plan.policy.configuration.get("immutable_statuses", [])
    return plan.status_code in configured


@transaction.atomic
def create_policy(
    *,
    context: TenantContext,
    evidence: RequestEvidence,
    attributes: dict[str, Any],
) -> WorkforcePolicyVersion:
    context.require("workforce.configure")
    policy = WorkforcePolicyVersion(company=context.company, **attributes)
    policy.full_clean()
    policy.save()
    _audit(
        context=context,
        evidence=evidence,
        action="workforce.policy.created",
        entity_type="workforce_policy",
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
        event_type="workforce.policy.created",
        aggregate_type="workforce_policy",
        aggregate_public_id=policy.public_id,
        aggregate_version=policy.version,
        payload={
            "code": policy.code,
            "status_code": policy.status_code,
            "published": policy.published_at is not None,
        },
    )
    return policy


@transaction.atomic
def create_skill(
    *,
    context: TenantContext,
    evidence: RequestEvidence,
    attributes: dict[str, Any],
) -> SkillDefinition:
    context.require("workforce.configure")
    skill = SkillDefinition(company=context.company, **attributes)
    skill.full_clean()
    skill.save()
    _audit(
        context=context,
        evidence=evidence,
        action="workforce.skill.created",
        entity_type="workforce_skill",
        entity_public_id=skill.public_id,
        after={
            "code": skill.code,
            "version": skill.version,
            "category_code": skill.category_code,
            "is_certification": skill.is_certification,
        },
    )
    _event(
        context=context,
        evidence=evidence,
        event_type="workforce.skill.created",
        aggregate_type="workforce_skill",
        aggregate_public_id=skill.public_id,
        aggregate_version=skill.version,
        payload={
            "code": skill.code,
            "category_code": skill.category_code,
            "is_certification": skill.is_certification,
        },
    )
    return skill


@transaction.atomic
def create_plan(
    *,
    context: TenantContext,
    evidence: RequestEvidence,
    policy_public_id: uuid.UUID,
    code: str,
    name: str,
    starts_on: Any,
    ends_on: Any,
    notes: str = "",
    metadata: dict[str, Any] | None = None,
) -> WorkforcePlan:
    context.require("workforce.manage")
    policy = _active_published_policy(
        company_id=context.company.id,
        public_id=policy_public_id,
    )
    if not policy:
        raise ValidationError({"policy_public_id": "Published workforce policy not found"})
    initial_status = str(policy.configuration.get("initial_plan_status", "")).strip()
    if not initial_status:
        raise ValidationError({"policy_public_id": "Policy has no initial plan status"})
    plan = WorkforcePlan(
        company=context.company,
        policy=policy,
        code=code.strip(),
        name=name.strip(),
        starts_on=starts_on,
        ends_on=ends_on,
        status_code=initial_status,
        owner_membership_public_id=context.membership.public_id,
        notes=notes.strip(),
        metadata=metadata or {},
    )
    plan.full_clean()
    plan.save()
    _audit(
        context=context,
        evidence=evidence,
        action="workforce.plan.created",
        entity_type="workforce_plan",
        entity_public_id=plan.public_id,
        after={
            "code": plan.code,
            "status_code": plan.status_code,
            "starts_on": plan.starts_on.isoformat(),
            "ends_on": plan.ends_on.isoformat(),
            "policy_code": policy.code,
            "policy_version": policy.version,
        },
    )
    _event(
        context=context,
        evidence=evidence,
        event_type="workforce.plan.created",
        aggregate_type="workforce_plan",
        aggregate_public_id=plan.public_id,
        aggregate_version=plan.version,
        payload={
            "code": plan.code,
            "status_code": plan.status_code,
            "starts_on": plan.starts_on.isoformat(),
            "ends_on": plan.ends_on.isoformat(),
        },
    )
    return plan


@transaction.atomic
def create_demand(
    *,
    context: TenantContext,
    evidence: RequestEvidence,
    plan_public_id: uuid.UUID,
    attributes: dict[str, Any],
) -> WorkforceDemand:
    context.require("workforce.manage")
    plan = (
        WorkforcePlan.objects.select_for_update()
        .select_related("policy")
        .filter(company=context.company, public_id=plan_public_id)
        .first()
    )
    if not plan:
        raise ValidationError({"plan_public_id": "Workforce plan not found"})
    if _plan_is_immutable(plan):
        raise ValidationError({"plan_public_id": "The workforce plan is locked"})
    demand = WorkforceDemand(company=context.company, plan=plan, **attributes)
    if demand.starts_on < plan.starts_on or demand.ends_on > plan.ends_on:
        raise ValidationError(
            {"date_range": "Demand dates must fall inside the workforce plan"}
        )
    demand.full_clean()
    demand.save()
    plan.version += 1
    plan.save(update_fields=["version", "updated_at"])
    _audit(
        context=context,
        evidence=evidence,
        action="workforce.demand.created",
        entity_type="workforce_demand",
        entity_public_id=demand.public_id,
        after={
            "plan_public_id": str(plan.public_id),
            "demand_code": demand.demand_code,
            "role_code": demand.role_code,
            "quantity_required": demand.quantity_required,
            "priority_code": demand.priority_code,
        },
    )
    _event(
        context=context,
        evidence=evidence,
        event_type="workforce.demand.created",
        aggregate_type="workforce_plan",
        aggregate_public_id=plan.public_id,
        aggregate_version=plan.version,
        payload={
            "demand_public_id": str(demand.public_id),
            "demand_code": demand.demand_code,
            "role_code": demand.role_code,
            "quantity_required": demand.quantity_required,
        },
    )
    return demand


def _transition_definition(
    plan: WorkforcePlan,
    target_status_code: str,
) -> dict[str, Any]:
    for transition in plan.policy.configuration.get("transitions", []):
        if (
            isinstance(transition, dict)
            and transition.get("from") == plan.status_code
            and transition.get("to") == target_status_code
        ):
            return transition
    raise ValidationError(
        {"target_status_code": "Transition is not allowed by the retained policy"}
    )


@transaction.atomic
def transition_plan(
    *,
    context: TenantContext,
    evidence: RequestEvidence,
    plan_public_id: uuid.UUID,
    expected_version: int,
    target_status_code: str,
    reason: str = "",
) -> WorkforcePlan:
    plan = (
        WorkforcePlan.objects.select_for_update()
        .select_related("policy")
        .filter(company=context.company, public_id=plan_public_id)
        .first()
    )
    if not plan:
        raise ValidationError({"plan_public_id": "Workforce plan not found"})
    if plan.version != expected_version:
        raise ValidationError(
            {"expected_version": "Workforce plan changed; refresh before retrying"}
        )
    if _plan_is_immutable(plan):
        raise ValidationError({"status_code": "The workforce plan is immutable"})
    transition = _transition_definition(plan, target_status_code)
    context.require(str(transition["permission"]))
    for requirement in transition.get("required_approvals", []):
        accepted = requirement.get("accepted_statuses", [])
        approved = WorkforceApproval.objects.filter(
            company=context.company,
            plan=plan,
            step_code=requirement.get("step_code"),
            status_code__in=accepted,
            decided_at__isnull=False,
        ).exists()
        if not approved:
            raise ValidationError(
                {
                    "target_status_code": (
                        f"Approval step {requirement.get('step_code')} is incomplete"
                    )
                }
            )
    before = {"status_code": plan.status_code, "version": plan.version}
    plan.status_code = target_status_code.strip()
    plan.version += 1
    milestone = transition.get("milestone")
    now = timezone.now()
    if milestone == "approved":
        plan.approved_at = now
        plan.approved_by_public_id = _actor(context)
    elif milestone == "locked":
        plan.locked_at = now
    plan.full_clean()
    plan.save()
    _audit(
        context=context,
        evidence=evidence,
        action="workforce.plan.transitioned",
        entity_type="workforce_plan",
        entity_public_id=plan.public_id,
        before=before,
        after={"status_code": plan.status_code, "version": plan.version},
        reason_code=reason.strip()[:100],
    )
    _event(
        context=context,
        evidence=evidence,
        event_type="workforce.plan.transitioned",
        aggregate_type="workforce_plan",
        aggregate_public_id=plan.public_id,
        aggregate_version=plan.version,
        payload={
            "status_code": plan.status_code,
            "previous_status_code": before["status_code"],
        },
    )
    return plan


def _credential_gaps(
    *,
    company_id: int,
    employee_public_id: uuid.UUID,
    demand: WorkforceDemand,
) -> list[str]:
    mandatory_codes = [
        str(item.get("skill_code", "")).strip()
        for item in demand.skill_requirements
        if isinstance(item, dict) and bool(item.get("mandatory", False))
    ]
    mandatory_codes = [code for code in mandatory_codes if code]
    if not mandatory_codes:
        return []
    now = timezone.localdate()
    available = set(
        EmployeeSkillCredential.objects.filter(
            company_id=company_id,
            employee_public_id=employee_public_id,
            skill__code__in=mandatory_codes,
            skill__is_active=True,
            verification_status_code__in=demand.plan.policy.configuration[
                "accepted_verification_statuses"
            ],
        )
        .filter(Q(expires_on__isnull=True) | Q(expires_on__gte=now))
        .values_list("skill__code", flat=True)
    )
    return [code for code in mandatory_codes if code not in available]


@transaction.atomic
def assign_worker(
    *,
    context: TenantContext,
    evidence: RequestEvidence,
    demand_public_id: uuid.UUID,
    employee_public_id: uuid.UUID,
    assignment_status_code: str,
    allocation_percent: Any,
    starts_on: Any,
    ends_on: Any = None,
    source_reference: str = "",
    metadata: dict[str, Any] | None = None,
) -> WorkforceAssignment:
    context.require("workforce.manage")
    demand = (
        WorkforceDemand.objects.select_for_update()
        .select_related("plan", "plan__policy")
        .filter(company=context.company, public_id=demand_public_id)
        .first()
    )
    if not demand:
        raise ValidationError({"demand_public_id": "Workforce demand not found"})
    if _plan_is_immutable(demand.plan):
        raise ValidationError({"demand_public_id": "The workforce plan is locked"})
    if demand.quantity_filled >= demand.quantity_required:
        raise ValidationError({"demand_public_id": "The demand is already fully staffed"})
    employee = Employee.objects.filter(
        company=context.company,
        public_id=employee_public_id,
    ).first()
    if not employee:
        raise ValidationError({"employee_public_id": "Employee not found"})
    gaps = _credential_gaps(
        company_id=context.company.id,
        employee_public_id=employee_public_id,
        demand=demand,
    )
    enforcement = str(
        demand.plan.policy.configuration.get("credential_enforcement", "")
    ).strip().upper()
    if enforcement not in {"BLOCK", "RISK", "OFF"}:
        raise ValidationError(
            {"demand_public_id": "The retained policy has invalid credential enforcement"}
        )
    if gaps and enforcement == "BLOCK":
        raise ValidationError(
            {"employee_public_id": f"Missing required skills: {', '.join(gaps)}"}
        )
    assignment = WorkforceAssignment(
        company=context.company,
        demand=demand,
        employee_public_id=employee_public_id,
        assignment_status_code=assignment_status_code.strip(),
        allocation_percent=_decimal(allocation_percent, "allocation_percent"),
        starts_on=starts_on,
        ends_on=ends_on,
        source_reference=source_reference.strip(),
        metadata=metadata or {},
    )
    assignment.full_clean()
    assignment.save()
    demand.quantity_filled += 1
    demand.version += 1
    if demand.quantity_filled == demand.quantity_required:
        configured_status = str(
            demand.plan.policy.configuration.get("filled_demand_status", "")
        ).strip()
        if configured_status:
            demand.status_code = configured_status
    demand.full_clean()
    demand.save()
    automatic_risk = None
    if gaps and enforcement == "RISK":
        automatic_risk = WorkforceRisk(
            company=context.company,
            plan=demand.plan,
            demand=demand,
            employee_public_id=employee_public_id,
            risk_code=str(
                demand.plan.policy.configuration["credential_gap_risk_code"]
            ).strip(),
            severity_code=str(
                demand.plan.policy.configuration["credential_gap_severity"]
            ).strip(),
            status_code=str(
                demand.plan.policy.configuration["open_risk_status"]
            ).strip(),
            message=f"Missing configured workforce skills: {', '.join(gaps)}",
            metadata={"skill_codes": gaps, "source": "assignment_control"},
        )
        automatic_risk.full_clean()
        automatic_risk.save()
    _audit(
        context=context,
        evidence=evidence,
        action="workforce.assignment.created",
        entity_type="workforce_assignment",
        entity_public_id=assignment.public_id,
        after={
            "demand_public_id": str(demand.public_id),
            "employee_public_id": str(employee_public_id),
            "allocation_percent": str(assignment.allocation_percent),
            "credential_gap_count": len(gaps),
        },
    )
    _event(
        context=context,
        evidence=evidence,
        event_type="workforce.assignment.created",
        aggregate_type="workforce_demand",
        aggregate_public_id=demand.public_id,
        aggregate_version=demand.version,
        payload={
            "assignment_public_id": str(assignment.public_id),
            "employee_public_id": str(employee_public_id),
            "quantity_filled": demand.quantity_filled,
            "quantity_required": demand.quantity_required,
            "credential_gap_count": len(gaps),
        },
    )
    if automatic_risk is not None:
        _audit(
            context=context,
            evidence=evidence,
            action="workforce.risk.created",
            entity_type="workforce_risk",
            entity_public_id=automatic_risk.public_id,
            after={
                "risk_code": automatic_risk.risk_code,
                "severity_code": automatic_risk.severity_code,
                "status_code": automatic_risk.status_code,
                "source": "assignment_control",
            },
        )
        _event(
            context=context,
            evidence=evidence,
            event_type="workforce.risk.created",
            aggregate_type="workforce_risk",
            aggregate_public_id=automatic_risk.public_id,
            aggregate_version=1,
            payload={
                "risk_code": automatic_risk.risk_code,
                "severity_code": automatic_risk.severity_code,
                "status_code": automatic_risk.status_code,
                "demand_public_id": str(demand.public_id),
                "employee_public_id": str(employee_public_id),
            },
        )
    return assignment


@transaction.atomic
def upsert_credential(
    *,
    context: TenantContext,
    evidence: RequestEvidence,
    employee_public_id: uuid.UUID,
    skill_public_id: uuid.UUID,
    attributes: dict[str, Any],
) -> EmployeeSkillCredential:
    context.require("workforce.manage")
    if not Employee.objects.filter(
        company=context.company,
        public_id=employee_public_id,
    ).exists():
        raise ValidationError({"employee_public_id": "Employee not found"})
    skill = SkillDefinition.objects.filter(
        company=context.company,
        public_id=skill_public_id,
        is_active=True,
    ).first()
    if not skill:
        raise ValidationError({"skill_public_id": "Active skill definition not found"})
    issued_on = attributes.get("issued_on")
    credential = EmployeeSkillCredential.objects.filter(
        company=context.company,
        employee_public_id=employee_public_id,
        skill=skill,
        issued_on=issued_on,
    ).first()
    created = credential is None
    if credential is None:
        credential = EmployeeSkillCredential(
            company=context.company,
            employee_public_id=employee_public_id,
            skill=skill,
        )
    else:
        credential.version += 1
    for field, value in attributes.items():
        setattr(credential, field, value)
    credential.full_clean()
    credential.save()
    _audit(
        context=context,
        evidence=evidence,
        action=(
            "workforce.credential.created"
            if created
            else "workforce.credential.updated"
        ),
        entity_type="workforce_credential",
        entity_public_id=credential.public_id,
        after={
            "employee_public_id": str(employee_public_id),
            "skill_code": skill.code,
            "verification_status_code": credential.verification_status_code,
            "expires_on": (
                credential.expires_on.isoformat() if credential.expires_on else None
            ),
        },
    )
    _event(
        context=context,
        evidence=evidence,
        event_type="workforce.credential.changed",
        aggregate_type="workforce_credential",
        aggregate_public_id=credential.public_id,
        aggregate_version=credential.version,
        payload={
            "employee_public_id": str(employee_public_id),
            "skill_code": skill.code,
            "verification_status_code": credential.verification_status_code,
            "created": created,
        },
    )
    return credential


@transaction.atomic
def request_approval(
    *,
    context: TenantContext,
    evidence: RequestEvidence,
    plan_public_id: uuid.UUID,
    step_code: str,
    requested_from_membership_public_id: uuid.UUID,
    status_code: str,
    due_at: Any = None,
    metadata: dict[str, Any] | None = None,
) -> WorkforceApproval:
    context.require("workforce.manage")
    plan = WorkforcePlan.objects.filter(
        company=context.company,
        public_id=plan_public_id,
    ).first()
    if not plan:
        raise ValidationError({"plan_public_id": "Workforce plan not found"})
    target_membership = Membership.objects.filter(
        company=context.company,
        public_id=requested_from_membership_public_id,
        suspended_at__isnull=True,
        terminated_at__isnull=True,
    ).first()
    if not target_membership:
        raise ValidationError(
            {"requested_from_membership_public_id": "Active membership not found"}
        )
    approval = WorkforceApproval(
        company=context.company,
        plan=plan,
        step_code=step_code.strip(),
        status_code=status_code.strip(),
        requested_from_membership_public_id=target_membership.public_id,
        requested_by_public_id=_actor(context),
        requested_at=timezone.now(),
        due_at=due_at,
        metadata=metadata or {},
    )
    approval.full_clean()
    approval.save()
    _audit(
        context=context,
        evidence=evidence,
        action="workforce.approval.requested",
        entity_type="workforce_approval",
        entity_public_id=approval.public_id,
        after={
            "plan_public_id": str(plan.public_id),
            "step_code": approval.step_code,
            "status_code": approval.status_code,
            "requested_from_membership_public_id": str(target_membership.public_id),
        },
    )
    _event(
        context=context,
        evidence=evidence,
        event_type="workforce.approval.requested",
        aggregate_type="workforce_approval",
        aggregate_public_id=approval.public_id,
        aggregate_version=1,
        payload={
            "plan_public_id": str(plan.public_id),
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
    reason: str = "",
) -> WorkforceApproval:
    context.require("workforce.approve")
    approval = (
        WorkforceApproval.objects.select_for_update()
        .select_related("plan", "plan__policy")
        .filter(company=context.company, public_id=approval_public_id)
        .first()
    )
    if not approval:
        raise ValidationError({"approval_public_id": "Workforce approval not found"})
    if approval.decided_at:
        raise ValidationError({"approval_public_id": "Approval is already decided"})
    if approval.requested_from_membership_public_id != context.membership.public_id:
        raise PermissionDenied("This approval is assigned to another membership")
    maker_checker = bool(
        approval.plan.policy.configuration.get("maker_checker_required", True)
    )
    if maker_checker and approval.requested_by_public_id == _actor(context):
        raise ValidationError("Maker-checker policy prevents self-approval")
    decisions = approval.plan.policy.configuration.get("approval_decisions", {})
    status_code = decisions.get(decision_code)
    if not isinstance(status_code, str) or not status_code.strip():
        raise ValidationError({"decision_code": "Decision is not configured"})
    approval.status_code = status_code.strip()
    approval.decision_code = decision_code.strip()
    approval.decision_reason = reason.strip()
    approval.decided_by_public_id = _actor(context)
    approval.decided_at = timezone.now()
    approval.full_clean()
    approval.save()
    _audit(
        context=context,
        evidence=evidence,
        action="workforce.approval.decided",
        entity_type="workforce_approval",
        entity_public_id=approval.public_id,
        after={
            "decision_code": approval.decision_code,
            "status_code": approval.status_code,
            "plan_public_id": str(approval.plan.public_id),
        },
        reason_code=reason.strip()[:100],
    )
    _event(
        context=context,
        evidence=evidence,
        event_type="workforce.approval.decided",
        aggregate_type="workforce_approval",
        aggregate_public_id=approval.public_id,
        aggregate_version=2,
        payload={
            "plan_public_id": str(approval.plan.public_id),
            "step_code": approval.step_code,
            "decision_code": approval.decision_code,
            "status_code": approval.status_code,
        },
    )
    return approval


@transaction.atomic
def create_risk(
    *,
    context: TenantContext,
    evidence: RequestEvidence,
    attributes: dict[str, Any],
) -> WorkforceRisk:
    context.require("workforce.manage")
    plan = None
    demand = None
    plan_public_id = attributes.pop("plan_public_id", None)
    demand_public_id = attributes.pop("demand_public_id", None)
    if plan_public_id:
        plan = WorkforcePlan.objects.filter(
            company=context.company,
            public_id=plan_public_id,
        ).first()
        if not plan:
            raise ValidationError({"plan_public_id": "Workforce plan not found"})
    if demand_public_id:
        demand = WorkforceDemand.objects.filter(
            company=context.company,
            public_id=demand_public_id,
        ).first()
        if not demand:
            raise ValidationError({"demand_public_id": "Workforce demand not found"})
        if plan and demand.plan_id != plan.id:
            raise ValidationError({"demand_public_id": "Demand does not belong to plan"})
        plan = plan or demand.plan
    risk = WorkforceRisk(
        company=context.company,
        plan=plan,
        demand=demand,
        **attributes,
    )
    risk.full_clean()
    risk.save()
    _audit(
        context=context,
        evidence=evidence,
        action="workforce.risk.created",
        entity_type="workforce_risk",
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
        event_type="workforce.risk.created",
        aggregate_type="workforce_risk",
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
    status_code: str,
    resolution_note: str,
) -> WorkforceRisk:
    context.require("workforce.manage")
    risk = WorkforceRisk.objects.select_for_update().filter(
        company=context.company,
        public_id=risk_public_id,
    ).first()
    if not risk:
        raise ValidationError({"risk_public_id": "Workforce risk not found"})
    if risk.resolved_at:
        raise ValidationError({"risk_public_id": "Workforce risk is already resolved"})
    before = {"status_code": risk.status_code, "severity_code": risk.severity_code}
    risk.status_code = status_code.strip()
    risk.resolution_note = resolution_note.strip()
    risk.resolved_at = timezone.now()
    risk.resolved_by_public_id = _actor(context)
    risk.full_clean()
    risk.save()
    _audit(
        context=context,
        evidence=evidence,
        action="workforce.risk.resolved",
        entity_type="workforce_risk",
        entity_public_id=risk.public_id,
        before=before,
        after={"status_code": risk.status_code, "resolved": True},
        reason_code=resolution_note.strip()[:100],
    )
    _event(
        context=context,
        evidence=evidence,
        event_type="workforce.risk.resolved",
        aggregate_type="workforce_risk",
        aggregate_public_id=risk.public_id,
        aggregate_version=2,
        payload={"status_code": risk.status_code, "resolved": True},
    )
    return risk
