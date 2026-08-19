from __future__ import annotations

import uuid
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q, Sum
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied

from modules.employee.models import Employee
from modules.payrollops.models import (
    PayrollApproval,
    PayrollException,
    PayrollPeriod,
    PayrollPolicyVersion,
    PayrollRun,
    PayrollRunLine,
)
from modules.platform.audit import AuditRecord, append_audit
from modules.platform.events import EventRecord, append_event
from modules.tenant.application.context import TenantContext
from modules.tenant.models import Membership


@dataclass(frozen=True, slots=True)
class RequestEvidence:
    request_id: uuid.UUID
    correlation_id: uuid.UUID
    ip_address: str | None = None
    user_agent: str = ""


MILESTONE_FIELDS = {
    "calculated": "calculated_at",
    "approved": "approved_at",
    "locked": "locked_at",
}


def _actor(context: TenantContext) -> uuid.UUID:
    return context.principal.user.public_id


def _money(value: Any, field_name: str) -> Decimal:
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValidationError({field_name: "Enter a valid decimal amount"}) from exc
    if parsed < 0:
        raise ValidationError({field_name: "Amount cannot be negative"})
    return parsed.quantize(Decimal("0.01"))


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
    aggregate_public_id: uuid.UUID,
    aggregate_version: int,
    payload: dict[str, Any],
    aggregate_type: str = "payroll_run",
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


@transaction.atomic
def create_policy(
    *,
    context: TenantContext,
    evidence: RequestEvidence,
    attributes: dict[str, Any],
) -> PayrollPolicyVersion:
    context.require("payroll.configure")
    policy = PayrollPolicyVersion(company=context.company, **attributes)
    policy.full_clean()
    policy.save()
    _audit(
        context=context,
        evidence=evidence,
        action="payroll.policy.created",
        entity_type="payroll_policy",
        entity_public_id=policy.public_id,
        after={
            "code": policy.code,
            "version": policy.version,
            "status_code": policy.status_code,
            "currency": policy.currency,
            "published": policy.published_at is not None,
        },
    )
    _event(
        context=context,
        evidence=evidence,
        event_type="payroll.policy.created",
        aggregate_type="payroll_policy",
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
def create_period(
    *,
    context: TenantContext,
    evidence: RequestEvidence,
    code: str,
    starts_on: Any,
    ends_on: Any,
    payment_due_on: Any,
    status_code: str,
    configuration: dict[str, Any] | None = None,
) -> PayrollPeriod:
    context.require("payroll.manage")
    period = PayrollPeriod(
        company=context.company,
        code=code.strip(),
        starts_on=starts_on,
        ends_on=ends_on,
        payment_due_on=payment_due_on,
        status_code=status_code.strip(),
        configuration=configuration or {},
    )
    period.full_clean()
    period.save()
    _audit(
        context=context,
        evidence=evidence,
        action="payroll.period.created",
        entity_type="payroll_period",
        entity_public_id=period.public_id,
        after={
            "code": period.code,
            "starts_on": period.starts_on.isoformat(),
            "ends_on": period.ends_on.isoformat(),
            "payment_due_on": period.payment_due_on.isoformat(),
            "status_code": period.status_code,
        },
    )
    _event(
        context=context,
        evidence=evidence,
        event_type="payroll.period.created",
        aggregate_type="payroll_period",
        aggregate_public_id=period.public_id,
        aggregate_version=period.lock_version,
        payload={
            "code": period.code,
            "status_code": period.status_code,
            "payment_due_on": period.payment_due_on.isoformat(),
        },
    )
    return period


@transaction.atomic
def create_run(
    *,
    context: TenantContext,
    evidence: RequestEvidence,
    period_public_id: uuid.UUID,
    policy_public_id: uuid.UUID,
    run_number: int,
    run_type_code: str,
    metadata: dict[str, Any] | None = None,
) -> PayrollRun:
    context.require("payroll.manage")
    period = PayrollPeriod.objects.select_for_update().filter(
        company=context.company,
        public_id=period_public_id,
    ).first()
    if not period:
        raise ValidationError({"period_public_id": "Payroll period was not found"})
    now = timezone.now()
    policy = (
        PayrollPolicyVersion.objects.filter(
            company=context.company,
            public_id=policy_public_id,
            published_at__isnull=False,
            published_at__lte=now,
            retired_at__isnull=True,
            effective_from__lte=now,
        )
        .filter(Q(effective_to__isnull=True) | Q(effective_to__gt=now))
        .first()
    )
    if not policy:
        raise ValidationError({"policy_public_id": "Published payroll policy was not found"})
    allowed_period_statuses = policy.configuration.get(
        "run_creation_period_statuses"
    )
    if (
        isinstance(allowed_period_statuses, list)
        and allowed_period_statuses
        and period.status_code not in allowed_period_statuses
    ):
        raise ValidationError(
            {"period_public_id": "The period status does not allow run creation"}
        )
    allowed_run_types = policy.configuration.get("run_types")
    requested_run_type = run_type_code.strip()
    if (
        isinstance(allowed_run_types, list)
        and allowed_run_types
        and requested_run_type not in allowed_run_types
    ):
        raise ValidationError(
            {"run_type_code": "The run type is not allowed by the payroll policy"}
        )
    initial_status = str(policy.configuration.get("initial_run_status", "")).strip()
    if not initial_status:
        raise ValidationError("The payroll policy does not define initial_run_status")
    run = PayrollRun(
        company=context.company,
        period=period,
        policy=policy,
        run_number=run_number,
        run_type_code=requested_run_type,
        status_code=initial_status,
        currency=policy.currency,
        initiated_by_public_id=_actor(context),
        metadata=metadata or {},
    )
    run.full_clean()
    run.save()
    _audit(
        context=context,
        evidence=evidence,
        action="payroll.run.created",
        entity_type="payroll_run",
        entity_public_id=run.public_id,
        after={
            "period_public_id": str(period.public_id),
            "policy_public_id": str(policy.public_id),
            "run_number": run.run_number,
            "run_type_code": run.run_type_code,
            "status_code": run.status_code,
            "currency": run.currency,
        },
    )
    _event(
        context=context,
        evidence=evidence,
        event_type="payroll.run.created",
        aggregate_public_id=run.public_id,
        aggregate_version=run.version,
        payload={
            "period_public_id": str(period.public_id),
            "run_type_code": run.run_type_code,
            "status_code": run.status_code,
        },
    )
    return run


def _transition_definition(run: PayrollRun, target_status: str) -> dict[str, Any]:
    transitions = run.policy.configuration.get("transitions", [])
    if not isinstance(transitions, list):
        raise ValidationError("Payroll policy transitions are invalid")
    for transition in transitions:
        if not isinstance(transition, dict):
            continue
        if transition.get("from") == run.status_code and transition.get("to") == target_status:
            return transition
    raise ValidationError(
        {
            "target_status_code": (
                f"Transition from {run.status_code} to {target_status} is not configured"
            )
        }
    )


@transaction.atomic
def transition_run(
    *,
    context: TenantContext,
    evidence: RequestEvidence,
    run_public_id: uuid.UUID,
    expected_version: int,
    target_status_code: str,
    reason: str,
) -> PayrollRun:
    run = PayrollRun.objects.select_for_update().select_related("policy", "period").filter(
        company=context.company,
        public_id=run_public_id,
    ).first()
    if not run:
        raise ValidationError({"run_public_id": "Payroll run was not found"})
    if run.version != expected_version:
        raise ValidationError(
            {
                "expected_version": (
                    f"Version conflict. Current version is {run.version}"
                )
            }
        )
    target_status = target_status_code.strip()
    transition = _transition_definition(run, target_status)
    permission_code = str(transition.get("permission", "")).strip()
    if not permission_code:
        raise ValidationError("Configured transition permission is missing")
    context.require(permission_code)
    if bool(transition.get("require_reason")) and not reason.strip():
        raise ValidationError({"reason": "A reason is required for this transition"})
    if (
        bool(transition.get("segregation_of_duties"))
        and run.initiated_by_public_id == _actor(context)
    ):
        raise PermissionDenied("Segregation of duties prevents self-approval")
    required_approvals = transition.get("required_approvals", [])
    if not isinstance(required_approvals, list):
        raise ValidationError("Configured required_approvals must be a list")
    for requirement in required_approvals:
        if not isinstance(requirement, dict):
            raise ValidationError("Configured approval requirement must be an object")
        step_code = str(requirement.get("step_code", "")).strip()
        accepted_statuses = requirement.get("accepted_statuses", [])
        if (
            not step_code
            or not isinstance(accepted_statuses, list)
            or not accepted_statuses
        ):
            raise ValidationError("Configured approval requirement is incomplete")
        approved = run.approvals.filter(
            step_code=step_code,
            status_code__in=accepted_statuses,
            decided_at__isnull=False,
        ).exists()
        if not approved:
            raise ValidationError(
                {
                    "target_status_code": (
                        f"Approval step {step_code} has not reached an accepted status"
                    )
                }
            )

    before = {"status_code": run.status_code, "version": run.version}
    run.status_code = target_status
    run.version += 1
    milestone = str(transition.get("milestone", "")).strip().lower()
    field_name = MILESTONE_FIELDS.get(milestone)
    now = timezone.now()
    update_fields = ["status_code", "version", "updated_at"]
    if field_name:
        setattr(run, field_name, now)
        update_fields.append(field_name)
        if milestone == "approved":
            run.approved_by_public_id = _actor(context)
            update_fields.append("approved_by_public_id")
    run.full_clean()
    run.save(update_fields=update_fields)

    event_type = str(transition.get("event_type", "payroll.run.transitioned")).strip()
    _audit(
        context=context,
        evidence=evidence,
        action="payroll.run.transitioned",
        entity_type="payroll_run",
        entity_public_id=run.public_id,
        before=before,
        after={"status_code": run.status_code, "version": run.version},
        reason_code=reason.strip()[:100],
    )
    _event(
        context=context,
        evidence=evidence,
        event_type=event_type or "payroll.run.transitioned",
        aggregate_public_id=run.public_id,
        aggregate_version=run.version,
        payload={
            "from_status_code": before["status_code"],
            "to_status_code": run.status_code,
            "reason": reason.strip()[:500],
        },
    )
    return run


@transaction.atomic
def upsert_run_lines(
    *,
    context: TenantContext,
    evidence: RequestEvidence,
    run_public_id: uuid.UUID,
    expected_version: int,
    lines: list[dict[str, Any]],
) -> PayrollRun:
    context.require("payroll.manage")
    run = PayrollRun.objects.select_for_update().select_related("policy").filter(
        company=context.company,
        public_id=run_public_id,
    ).first()
    if not run:
        raise ValidationError({"run_public_id": "Payroll run was not found"})
    if run.version != expected_version:
        raise ValidationError(
            {"expected_version": f"Version conflict. Current version is {run.version}"}
        )
    immutable_statuses = run.policy.configuration.get("immutable_statuses", [])
    if isinstance(immutable_statuses, list) and run.status_code in immutable_statuses:
        raise ValidationError("This payroll run is immutable under the active policy")
    if not lines:
        raise ValidationError({"lines": "At least one payroll line is required"})
    seen: set[uuid.UUID] = set()
    normalized_lines: list[dict[str, Any]] = []
    for index, item in enumerate(lines):
        try:
            employee_public_id = uuid.UUID(str(item.get("employee_public_id")))
        except (ValueError, TypeError, AttributeError) as exc:
            raise ValidationError(
                {"lines": f"Line {index + 1} has an invalid employee_public_id"}
            ) from exc
        if employee_public_id in seen:
            raise ValidationError(
                {"lines": f"Employee {employee_public_id} appears more than once"}
            )
        seen.add(employee_public_id)
        gross = _money(item.get("gross_amount"), "gross_amount")
        deductions = _money(item.get("deduction_amount"), "deduction_amount")
        employer_cost = _money(
            item.get("employer_cost_amount"),
            "employer_cost_amount",
        )
        if deductions > gross:
            raise ValidationError(
                {"lines": f"Line {index + 1} deductions exceed gross amount"}
            )
        status_code = str(item.get("status_code", "")).strip()
        if not status_code:
            raise ValidationError(
                {"lines": f"Line {index + 1} requires status_code"}
            )
        normalized_lines.append(
            {
                "employee_public_id": employee_public_id,
                "company": context.company,
                "employment_public_id": item.get("employment_public_id") or None,
                "currency": run.currency,
                "gross_amount": gross,
                "deduction_amount": deductions,
                "employer_cost_amount": employer_cost,
                "net_amount": gross - deductions,
                "status_code": status_code,
                "exception_codes": item.get("exception_codes") or [],
                "component_breakdown": item.get("component_breakdown") or [],
                "calculation_trace": item.get("calculation_trace") or {},
                "source_reference": str(
                    item.get("source_reference", "")
                ).strip(),
            }
        )

    tenant_employee_ids = set(
        Employee.objects.filter(
            company=context.company,
            public_id__in=seen,
        ).values_list("public_id", flat=True)
    )
    missing_employee_ids = seen - tenant_employee_ids
    if missing_employee_ids:
        raise ValidationError(
            {
                "lines": (
                    "One or more employees are absent from the active tenant: "
                    + ", ".join(sorted(str(item) for item in missing_employee_ids))
                )
            }
        )

    for normalized in normalized_lines:
        employee_public_id = normalized.pop("employee_public_id")
        line = PayrollRunLine.objects.filter(
            run=run,
            employee_public_id=employee_public_id,
        ).first()
        if line:
            for key, value in normalized.items():
                setattr(line, key, value)
            line.version += 1
        else:
            line = PayrollRunLine(
                run=run,
                employee_public_id=employee_public_id,
                **normalized,
            )
        line.full_clean()
        line.save()

    totals = run.lines.aggregate(
        gross=Sum("gross_amount"),
        deductions=Sum("deduction_amount"),
        employer_cost=Sum("employer_cost_amount"),
        net=Sum("net_amount"),
    )
    run.gross_amount = totals["gross"] or Decimal("0.00")
    run.deduction_amount = totals["deductions"] or Decimal("0.00")
    run.employer_cost_amount = totals["employer_cost"] or Decimal("0.00")
    run.net_amount = totals["net"] or Decimal("0.00")
    run.employee_count = run.lines.count()
    run.exception_count = run.exceptions.filter(resolved_at__isnull=True).count()
    run.version += 1
    run.full_clean()
    run.save(
        update_fields=[
            "gross_amount",
            "deduction_amount",
            "employer_cost_amount",
            "net_amount",
            "employee_count",
            "exception_count",
            "version",
            "updated_at",
        ]
    )
    _audit(
        context=context,
        evidence=evidence,
        action="payroll.run.lines_upserted",
        entity_type="payroll_run",
        entity_public_id=run.public_id,
        after={
            "employee_count": run.employee_count,
            "gross_amount": str(run.gross_amount),
            "deduction_amount": str(run.deduction_amount),
            "net_amount": str(run.net_amount),
            "version": run.version,
        },
    )
    _event(
        context=context,
        evidence=evidence,
        event_type="payroll.run.lines_updated",
        aggregate_public_id=run.public_id,
        aggregate_version=run.version,
        payload={
            "employee_count": run.employee_count,
            "exception_count": run.exception_count,
        },
    )
    return run


@transaction.atomic
def request_approval(
    *,
    context: TenantContext,
    evidence: RequestEvidence,
    run_public_id: uuid.UUID,
    step_code: str,
    status_code: str,
    requested_from_membership_public_id: uuid.UUID,
    due_at: Any = None,
    metadata: dict[str, Any] | None = None,
) -> PayrollApproval:
    context.require("payroll.manage")
    run = PayrollRun.objects.select_for_update().filter(
        company=context.company,
        public_id=run_public_id,
    ).first()
    if not run:
        raise ValidationError({"run_public_id": "Payroll run was not found"})
    requested_membership_exists = Membership.objects.filter(
        company=context.company,
        public_id=requested_from_membership_public_id,
    ).exists()
    if not requested_membership_exists:
        raise ValidationError(
            {
                "requested_from_membership_public_id": (
                    "The requested approver is not a member of this company"
                )
            }
        )
    approval = PayrollApproval(
        company=context.company,
        run=run,
        step_code=step_code.strip(),
        status_code=status_code.strip(),
        requested_from_membership_public_id=requested_from_membership_public_id,
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
        action="payroll.approval.requested",
        entity_type="payroll_approval",
        entity_public_id=approval.public_id,
        after={
            "run_public_id": str(run.public_id),
            "step_code": approval.step_code,
            "status_code": approval.status_code,
        },
    )
    _event(
        context=context,
        evidence=evidence,
        event_type="payroll.approval.requested",
        aggregate_type="payroll_approval",
        aggregate_public_id=approval.public_id,
        aggregate_version=1,
        payload={
            "run_public_id": str(run.public_id),
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
    status_code: str,
    reason: str,
) -> PayrollApproval:
    context.require("payroll.approve")
    approval = PayrollApproval.objects.select_for_update().select_related("run__policy").filter(
        company=context.company,
        public_id=approval_public_id,
        decided_at__isnull=True,
    ).first()
    if not approval:
        raise ValidationError({"approval_public_id": "Pending approval was not found"})
    policy_config = approval.run.policy.configuration
    if bool(policy_config.get("approval_assignment_required", True)):
        if approval.requested_from_membership_public_id != context.membership.public_id:
            raise PermissionDenied("This payroll approval is assigned to another member")
    if bool(policy_config.get("approval_segregation_of_duties", True)):
        if approval.requested_by_public_id == _actor(context):
            raise PermissionDenied("Segregation of duties prevents self-approval")
    if bool(policy_config.get("approval_reason_required", False)) and not reason.strip():
        raise ValidationError({"reason": "A decision reason is required"})
    decision_rules = policy_config.get("approval_decisions")
    normalized_decision = decision_code.strip()
    normalized_status = status_code.strip()
    if isinstance(decision_rules, dict) and decision_rules:
        configured_status = decision_rules.get(normalized_decision)
        if not isinstance(configured_status, str):
            raise ValidationError({"decision_code": "Decision is not configured"})
        if configured_status != normalized_status:
            raise ValidationError(
                {"status_code": "Status does not match the configured decision"}
            )
    before = {"status_code": approval.status_code}
    approval.decision_code = normalized_decision
    approval.status_code = normalized_status
    approval.decision_reason = reason.strip()[:500]
    approval.decided_by_public_id = _actor(context)
    approval.decided_at = timezone.now()
    approval.full_clean()
    approval.save(
        update_fields=[
            "decision_code",
            "status_code",
            "decision_reason",
            "decided_by_public_id",
            "decided_at",
            "updated_at",
        ]
    )
    _audit(
        context=context,
        evidence=evidence,
        action="payroll.approval.decided",
        entity_type="payroll_approval",
        entity_public_id=approval.public_id,
        before=before,
        after={
            "status_code": approval.status_code,
            "decision_code": approval.decision_code,
        },
        reason_code=reason.strip()[:100],
    )
    _event(
        context=context,
        evidence=evidence,
        event_type="payroll.approval.decided",
        aggregate_type="payroll_approval",
        aggregate_public_id=approval.public_id,
        aggregate_version=1,
        payload={
            "run_public_id": str(approval.run.public_id),
            "status_code": approval.status_code,
            "decision_code": approval.decision_code,
        },
    )
    return approval


@transaction.atomic
def resolve_exception(
    *,
    context: TenantContext,
    evidence: RequestEvidence,
    exception_public_id: uuid.UUID,
    status_code: str,
    resolution_note: str,
) -> PayrollException:
    context.require("payroll.manage")
    exception = PayrollException.objects.select_for_update().select_related("run").filter(
        company=context.company,
        public_id=exception_public_id,
        resolved_at__isnull=True,
    ).first()
    if not exception:
        raise ValidationError({"exception_public_id": "Open exception was not found"})
    exception.status_code = status_code.strip()
    exception.resolution_note = resolution_note.strip()[:500]
    exception.resolved_by_public_id = _actor(context)
    exception.resolved_at = timezone.now()
    exception.full_clean()
    exception.save(
        update_fields=[
            "status_code",
            "resolution_note",
            "resolved_by_public_id",
            "resolved_at",
            "updated_at",
        ]
    )
    run = PayrollRun.objects.select_for_update().get(pk=exception.run_id)
    run.exception_count = run.exceptions.filter(resolved_at__isnull=True).count()
    run.version += 1
    run.save(update_fields=["exception_count", "version", "updated_at"])
    _audit(
        context=context,
        evidence=evidence,
        action="payroll.exception.resolved",
        entity_type="payroll_exception",
        entity_public_id=exception.public_id,
        after={
            "status_code": exception.status_code,
            "run_public_id": str(run.public_id),
        },
    )
    _event(
        context=context,
        evidence=evidence,
        event_type="payroll.exception.resolved",
        aggregate_type="payroll_exception",
        aggregate_public_id=exception.public_id,
        aggregate_version=1,
        payload={
            "run_public_id": str(run.public_id),
            "status_code": exception.status_code,
        },
    )
    return exception
