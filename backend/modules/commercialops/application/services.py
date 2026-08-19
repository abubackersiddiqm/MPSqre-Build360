from __future__ import annotations

import uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models import Q
from django.utils import timezone

from modules.commercialops.models import (
    CommercialApproval,
    CommercialClaim,
    CommercialContract,
    CommercialPolicyVersion,
    CommercialRisk,
    ContractMilestone,
    ExtensionOfTime,
    PaymentApplication,
    VariationOrder,
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


def _actor(context: TenantContext) -> uuid.UUID:
    return context.principal.user.public_id


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
    append_audit(
        AuditRecord(
            action=action,
            entity_type=entity_type,
            entity_public_id=instance.public_id,
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
    append_event(
        EventRecord(
            event_type=action,
            aggregate_type=entity_type,
            aggregate_public_id=instance.public_id,
            aggregate_version=getattr(instance, "version", 1),
            company_public_id=context.company.public_id,
            correlation_id=evidence.correlation_id,
            payload=after or {},
        )
    )


def _policy_for(context: TenantContext, public_id: uuid.UUID) -> CommercialPolicyVersion:
    now = timezone.now()
    policy = (
        CommercialPolicyVersion.objects.filter(
            company=context.company,
            public_id=public_id,
            published_at__isnull=False,
            published_at__lte=now,
            retired_at__isnull=True,
            effective_from__lte=now,
        )
        .filter(Q(effective_to__isnull=True) | Q(effective_to__gt=now))
        .first()
    )
    if not policy:
        raise ValidationError(
            {"policy_public_id": "Published commercial policy not found"}
        )
    return policy


def _configured_code(
    policy: CommercialPolicyVersion, key: str, fallback: str = ""
) -> str:
    value = policy.configuration.get(key, fallback)
    if not isinstance(value, str) or not value.strip():
        raise ValidationError({"policy_public_id": f"Policy has no {key}"})
    return value.strip().upper()


def _transition(
    policy: CommercialPolicyVersion,
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
        raise ValidationError(
            {"expected_version": "Record was modified by another request"}
        )


def _require_membership(
    context: TenantContext, public_id: uuid.UUID, field: str
) -> None:
    now = timezone.now()
    exists = (
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
    if not exists:
        raise ValidationError({field: "Active tenant membership not found"})


def _contract_for(
    context: TenantContext,
    policy: CommercialPolicyVersion,
    public_id: uuid.UUID,
) -> CommercialContract:
    item = CommercialContract.objects.filter(
        company=context.company, policy=policy, public_id=public_id
    ).first()
    if not item:
        raise ValidationError({"contract_public_id": "Commercial contract not found"})
    return item


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
        statuses = [
            str(value).upper()
            for value in requirement.get("accepted_statuses", [])
            if str(value).strip()
        ]
        if not step_code or not statuses:
            return False
        if not CommercialApproval.objects.filter(
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
) -> CommercialPolicyVersion:
    context.require("commercial.configure")
    item = CommercialPolicyVersion(
        company=context.company,
        created_by_membership_public_id=context.membership.public_id,
        **attributes,
    )
    item.full_clean()
    item.save()
    _publish_change(
        context=context,
        evidence=evidence,
        action="commercial.policy.created",
        entity_type="commercial_policy",
        instance=item,
        after={
            "code": item.code,
            "version": item.version,
            "status_code": item.status_code,
            "published": item.published_at is not None,
        },
    )
    return item


@transaction.atomic
def create_contract(
    *,
    context: TenantContext,
    evidence: RequestEvidence,
    policy_public_id: uuid.UUID,
    attributes: dict[str, Any],
) -> CommercialContract:
    context.require("commercial.contract")
    policy = _policy_for(context, policy_public_id)
    if owner := attributes.get("owner_membership_public_id"):
        _require_membership(context, owner, "owner_membership_public_id")
    original = Decimal(attributes.get("original_value", 0))
    item = CommercialContract(
        company=context.company,
        policy=policy,
        status_code=_configured_code(policy, "initial_contract_status"),
        approved_variation_value=Decimal("0"),
        current_contract_value=original,
        **attributes,
    )
    item.full_clean()
    item.save()
    _publish_change(
        context=context,
        evidence=evidence,
        action="commercial.contract.created",
        entity_type="commercial_contract",
        instance=item,
        after={
            "contract_number": item.contract_number,
            "status_code": item.status_code,
            "currency_code": item.currency_code,
            "current_contract_value": str(item.current_contract_value),
        },
    )
    return item


@transaction.atomic
def create_milestone(
    *,
    context: TenantContext,
    evidence: RequestEvidence,
    policy_public_id: uuid.UUID,
    contract_public_id: uuid.UUID,
    attributes: dict[str, Any],
) -> ContractMilestone:
    context.require("commercial.contract")
    policy = _policy_for(context, policy_public_id)
    contract = _contract_for(context, policy, contract_public_id)
    item = ContractMilestone(
        company=context.company,
        policy=policy,
        contract=contract,
        status_code=_configured_code(policy, "initial_milestone_status"),
        **attributes,
    )
    item.full_clean()
    item.save()
    _publish_change(
        context=context,
        evidence=evidence,
        action="commercial.milestone.created",
        entity_type="contract_milestone",
        instance=item,
        after={
            "contract_number": contract.contract_number,
            "milestone_number": item.milestone_number,
            "status_code": item.status_code,
            "due_date": item.due_date.isoformat(),
        },
    )
    return item


@transaction.atomic
def create_variation(
    *,
    context: TenantContext,
    evidence: RequestEvidence,
    policy_public_id: uuid.UUID,
    contract_public_id: uuid.UUID,
    attributes: dict[str, Any],
) -> VariationOrder:
    context.require("commercial.change")
    policy = _policy_for(context, policy_public_id)
    contract = _contract_for(context, policy, contract_public_id)
    item = VariationOrder(
        company=context.company,
        policy=policy,
        contract=contract,
        status_code=_configured_code(policy, "initial_variation_status"),
        requested_by_membership_public_id=context.membership.public_id,
        **attributes,
    )
    item.full_clean()
    item.save()
    _publish_change(
        context=context,
        evidence=evidence,
        action="commercial.variation.created",
        entity_type="variation_order",
        instance=item,
        after={
            "contract_number": contract.contract_number,
            "variation_number": item.variation_number,
            "status_code": item.status_code,
            "submitted_value": str(item.submitted_value),
        },
    )
    return item


@transaction.atomic
def create_payment(
    *,
    context: TenantContext,
    evidence: RequestEvidence,
    policy_public_id: uuid.UUID,
    contract_public_id: uuid.UUID,
    attributes: dict[str, Any],
) -> PaymentApplication:
    context.require("commercial.payment")
    policy = _policy_for(context, policy_public_id)
    contract = _contract_for(context, policy, contract_public_id)
    certified = attributes.get("certified_amount")
    if certified is not None and attributes.get("net_payable") is None:
        attributes["net_payable"] = (
            Decimal(certified)
            - Decimal(attributes.get("retention_amount", 0))
            - Decimal(attributes.get("deduction_amount", 0))
        )
    item = PaymentApplication(
        company=context.company,
        policy=policy,
        contract=contract,
        status_code=_configured_code(policy, "initial_payment_status"),
        applicant_membership_public_id=context.membership.public_id,
        **attributes,
    )
    item.full_clean()
    item.save()
    _publish_change(
        context=context,
        evidence=evidence,
        action="commercial.payment.created",
        entity_type="payment_application",
        instance=item,
        after={
            "contract_number": contract.contract_number,
            "application_number": item.application_number,
            "status_code": item.status_code,
            "gross_claimed": str(item.gross_claimed),
        },
    )
    return item


@transaction.atomic
def create_claim(
    *,
    context: TenantContext,
    evidence: RequestEvidence,
    policy_public_id: uuid.UUID,
    contract_public_id: uuid.UUID,
    attributes: dict[str, Any],
) -> CommercialClaim:
    context.require("commercial.claim")
    policy = _policy_for(context, policy_public_id)
    contract = _contract_for(context, policy, contract_public_id)
    if owner := attributes.get("owner_membership_public_id"):
        _require_membership(context, owner, "owner_membership_public_id")
    item = CommercialClaim(
        company=context.company,
        policy=policy,
        contract=contract,
        status_code=_configured_code(policy, "initial_claim_status"),
        **attributes,
    )
    item.full_clean()
    item.save()
    _publish_change(
        context=context,
        evidence=evidence,
        action="commercial.claim.created",
        entity_type="commercial_claim",
        instance=item,
        after={
            "contract_number": contract.contract_number,
            "claim_number": item.claim_number,
            "priority_code": item.priority_code,
            "status_code": item.status_code,
            "claimed_amount": str(item.claimed_amount),
        },
    )
    return item


@transaction.atomic
def create_eot(
    *,
    context: TenantContext,
    evidence: RequestEvidence,
    policy_public_id: uuid.UUID,
    contract_public_id: uuid.UUID,
    claim_public_id: uuid.UUID | None,
    attributes: dict[str, Any],
) -> ExtensionOfTime:
    context.require("commercial.claim")
    policy = _policy_for(context, policy_public_id)
    contract = _contract_for(context, policy, contract_public_id)
    claim = None
    if claim_public_id:
        claim = CommercialClaim.objects.filter(
            company=context.company,
            contract=contract,
            policy=policy,
            public_id=claim_public_id,
        ).first()
        if not claim:
            raise ValidationError({"claim_public_id": "Commercial claim not found"})
    item = ExtensionOfTime(
        company=context.company,
        policy=policy,
        contract=contract,
        claim=claim,
        status_code=_configured_code(policy, "initial_eot_status"),
        requested_by_membership_public_id=context.membership.public_id,
        **attributes,
    )
    item.full_clean()
    item.save()
    _publish_change(
        context=context,
        evidence=evidence,
        action="commercial.eot.created",
        entity_type="extension_of_time",
        instance=item,
        after={
            "contract_number": contract.contract_number,
            "eot_number": item.eot_number,
            "requested_days": item.requested_days,
            "status_code": item.status_code,
        },
    )
    return item


def _record_for_transition[RecordT: models.Model](
    *,
    context: TenantContext,
    model: type[RecordT],
    public_id: uuid.UUID,
    label: str,
) -> RecordT:
    item = (
        model.objects.select_for_update()
        .select_related("policy")
        .filter(company=context.company, public_id=public_id)
        .first()
    )
    if not item:
        raise ValidationError({f"{label}_public_id": f"{label.replace('_', ' ').title()} not found"})
    return item


@transaction.atomic
def transition_record(
    *,
    context: TenantContext,
    evidence: RequestEvidence,
    entity_type_code: str,
    record_public_id: uuid.UUID,
    target_status_code: str,
    expected_version: int | None,
) -> models.Model:
    definitions: dict[str, tuple[type[models.Model], str, str, str]] = {
        "CONTRACT": (CommercialContract, "contract_transitions", "commercial.contract", "commercial_contract"),
        "MILESTONE": (ContractMilestone, "milestone_transitions", "commercial.contract", "contract_milestone"),
        "VARIATION": (VariationOrder, "variation_transitions", "commercial.change", "variation_order"),
        "PAYMENT": (PaymentApplication, "payment_transitions", "commercial.payment", "payment_application"),
        "CLAIM": (CommercialClaim, "claim_transitions", "commercial.claim", "commercial_claim"),
        "EOT": (ExtensionOfTime, "eot_transitions", "commercial.claim", "extension_of_time"),
    }
    normalized = entity_type_code.strip().upper()
    definition = definitions.get(normalized)
    if not definition:
        raise ValidationError({"entity_type_code": "Unsupported commercial entity type"})
    model, transition_key, default_permission, event_entity = definition
    item = _record_for_transition(
        context=context,
        model=model,
        public_id=record_public_id,
        label=normalized.lower(),
    )
    transition = _transition(
        item.policy, transition_key, item.status_code, target_status_code
    )
    context.require(str(transition.get("permission") or default_permission))
    _check_version(item, expected_version)
    if not _approvals_met(
        company_id=context.company.id,
        entity_type_code=normalized,
        entity_public_id=item.public_id,
        transition=transition,
    ):
        raise ValidationError({"target_status_code": "Required approval is not complete"})

    before = {"status_code": item.status_code, "version": item.version}
    item.status_code = target_status_code.strip().upper()
    item.version += 1
    milestone = str(transition.get("milestone") or "").lower()
    now = timezone.now()

    if isinstance(item, ContractMilestone) and milestone == "achieved":
        item.achieved_at = now
    elif isinstance(item, VariationOrder):
        if milestone == "submitted":
            item.submitted_at = now
        elif milestone == "approved":
            if item.approved_value is None:
                raise ValidationError({"approved_value": "Approved value is required"})
            item.decided_at = now
            item.decided_by_membership_public_id = context.membership.public_id
            contract = CommercialContract.objects.select_for_update().get(pk=item.contract_id)
            contract.approved_variation_value += item.approved_value
            contract.current_contract_value = (
                contract.original_value + contract.approved_variation_value
            )
            contract.version += 1
            contract.full_clean()
            contract.save()
            _publish_change(
                context=context,
                evidence=evidence,
                action="commercial.contract.value_updated",
                entity_type="commercial_contract",
                instance=contract,
                after={
                    "approved_variation_value": str(contract.approved_variation_value),
                    "current_contract_value": str(contract.current_contract_value),
                },
            )
        elif milestone in {"rejected", "closed"}:
            item.decided_at = now
            item.decided_by_membership_public_id = context.membership.public_id
    elif isinstance(item, PaymentApplication):
        if milestone == "submitted":
            item.submitted_at = now
        elif milestone == "certified":
            if item.certified_amount is None:
                raise ValidationError({"certified_amount": "Certified amount is required"})
            item.net_payable = (
                item.certified_amount - item.retention_amount - item.deduction_amount
            )
            item.certified_at = now
            item.certifier_membership_public_id = context.membership.public_id
    elif isinstance(item, CommercialClaim) and milestone in {"resolved", "closed"}:
        item.resolved_at = now
    elif isinstance(item, ExtensionOfTime) and milestone in {"approved", "rejected", "closed"}:
        item.decided_at = now
        item.decided_by_membership_public_id = context.membership.public_id

    item.full_clean()
    item.save()
    _publish_change(
        context=context,
        evidence=evidence,
        action=f"commercial.{normalized.lower()}.transitioned",
        entity_type=event_entity,
        instance=item,
        before=before,
        after={"status_code": item.status_code, "version": item.version},
    )
    return item


@transaction.atomic
def request_approval(
    *,
    context: TenantContext,
    evidence: RequestEvidence,
    policy_public_id: uuid.UUID,
    attributes: dict[str, Any],
) -> CommercialApproval:
    context.require("commercial.manage")
    policy = _policy_for(context, policy_public_id)
    approver = attributes.get("approver_membership_public_id")
    if approver:
        _require_membership(context, approver, "approver_membership_public_id")
    item = CommercialApproval(
        company=context.company,
        policy=policy,
        status_code=_configured_code(policy, "initial_approval_status"),
        requested_by_membership_public_id=context.membership.public_id,
        requested_at=timezone.now(),
        **attributes,
    )
    item.full_clean()
    item.save()
    _publish_change(
        context=context,
        evidence=evidence,
        action="commercial.approval.requested",
        entity_type="commercial_approval",
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
    reason: str,
    expected_version: int | None,
) -> CommercialApproval:
    context.require("commercial.approve")
    item = (
        CommercialApproval.objects.select_for_update()
        .select_related("policy")
        .filter(company=context.company, public_id=approval_public_id)
        .first()
    )
    if not item:
        raise ValidationError({"approval_public_id": "Commercial approval not found"})
    _check_version(item, expected_version)
    if item.decided_at:
        raise ValidationError({"decision_code": "Approval is already decided"})
    if item.requested_by_membership_public_id == context.membership.public_id:
        raise ValidationError("Requester cannot approve their own commercial action")
    configured = item.policy.configuration.get("approval_decisions", {})
    normalized = decision_code.strip().upper()
    target = configured.get(normalized) if isinstance(configured, dict) else None
    if not isinstance(target, str) or not target.strip():
        raise ValidationError({"decision_code": "Decision is not configured"})
    before = {"status_code": item.status_code, "version": item.version}
    item.status_code = target.strip().upper()
    item.decision_code = normalized
    item.reason = reason
    item.decided_at = timezone.now()
    item.approver_membership_public_id = context.membership.public_id
    item.version += 1
    item.full_clean()
    item.save()
    _publish_change(
        context=context,
        evidence=evidence,
        action="commercial.approval.decided",
        entity_type="commercial_approval",
        instance=item,
        before=before,
        after={
            "status_code": item.status_code,
            "decision_code": item.decision_code,
            "version": item.version,
        },
        reason_code=normalized,
    )
    return item


@transaction.atomic
def create_risk(
    *,
    context: TenantContext,
    evidence: RequestEvidence,
    policy_public_id: uuid.UUID,
    contract_public_id: uuid.UUID | None,
    attributes: dict[str, Any],
) -> CommercialRisk:
    context.require("commercial.manage")
    policy = _policy_for(context, policy_public_id)
    contract = None
    if contract_public_id:
        contract = _contract_for(context, policy, contract_public_id)
    if assignee := attributes.get("assigned_membership_public_id"):
        _require_membership(context, assignee, "assigned_membership_public_id")
    item = CommercialRisk(
        company=context.company,
        policy=policy,
        contract=contract,
        status_code=_configured_code(policy, "initial_risk_status"),
        **attributes,
    )
    item.full_clean()
    item.save()
    _publish_change(
        context=context,
        evidence=evidence,
        action="commercial.risk.created",
        entity_type="commercial_risk",
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
    expected_version: int | None,
) -> CommercialRisk:
    context.require("commercial.manage")
    item = (
        CommercialRisk.objects.select_for_update()
        .select_related("policy")
        .filter(company=context.company, public_id=risk_public_id)
        .first()
    )
    if not item:
        raise ValidationError({"risk_public_id": "Commercial risk not found"})
    _check_version(item, expected_version)
    if item.resolved_at:
        raise ValidationError({"resolution_note": "Risk is already resolved"})
    before = {"status_code": item.status_code, "version": item.version}
    item.status_code = _configured_code(item.policy, "resolved_risk_status")
    item.resolved_at = timezone.now()
    item.resolved_by_membership_public_id = context.membership.public_id
    item.resolution_note = resolution_note
    item.version += 1
    item.full_clean()
    item.save()
    _publish_change(
        context=context,
        evidence=evidence,
        action="commercial.risk.resolved",
        entity_type="commercial_risk",
        instance=item,
        before=before,
        after={"status_code": item.status_code, "version": item.version},
    )
    return item
