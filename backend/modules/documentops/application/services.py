from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied

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


def _policy_for(
    context: TenantContext, public_id: uuid.UUID
) -> DocumentControlPolicyVersion:
    now = timezone.now()
    policy = (
        DocumentControlPolicyVersion.objects.filter(
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
            {"policy_public_id": "Published document-control policy not found"}
        )
    return policy


def _configured_code(
    policy: DocumentControlPolicyVersion, key: str, fallback: str = ""
) -> str:
    value = policy.configuration.get(key, fallback)
    if not isinstance(value, str) or not value.strip():
        raise ValidationError({"policy_public_id": f"Policy has no {key}"})
    return value.strip().upper()


def _transition(
    policy: DocumentControlPolicyVersion,
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
        if not DocumentApproval.objects.filter(
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
) -> DocumentControlPolicyVersion:
    context.require("document.configure")
    item = DocumentControlPolicyVersion(
        company=context.company,
        created_by_membership_public_id=context.membership.public_id,
        **attributes,
    )
    item.full_clean()
    item.save()
    _publish_change(
        context=context,
        evidence=evidence,
        action="document.policy.created",
        entity_type="document_control_policy",
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
def create_document(
    *,
    context: TenantContext,
    evidence: RequestEvidence,
    policy_public_id: uuid.UUID,
    attributes: dict[str, Any],
) -> ControlledDocument:
    context.require("document.manage")
    policy = _policy_for(context, policy_public_id)
    for field in ("originator_membership_public_id", "owner_membership_public_id"):
        if value := attributes.get(field):
            _require_membership(context, value, field)
    item = ControlledDocument(
        company=context.company,
        policy=policy,
        status_code=_configured_code(policy, "initial_document_status"),
        **attributes,
    )
    item.full_clean()
    item.save()
    _publish_change(
        context=context,
        evidence=evidence,
        action="document.record.created",
        entity_type="controlled_document",
        instance=item,
        after={
            "document_number": item.document_number,
            "discipline_code": item.discipline_code,
            "document_type_code": item.document_type_code,
            "status_code": item.status_code,
        },
    )
    return item


@transaction.atomic
def transition_document(
    *,
    context: TenantContext,
    evidence: RequestEvidence,
    document_public_id: uuid.UUID,
    target_status_code: str,
    expected_version: int | None = None,
) -> ControlledDocument:
    item = (
        ControlledDocument.objects.select_for_update()
        .select_related("policy")
        .filter(company=context.company, public_id=document_public_id)
        .first()
    )
    if not item:
        raise ValidationError({"document_public_id": "Controlled document not found"})
    transition = _transition(
        item.policy, "document_transitions", item.status_code, target_status_code
    )
    context.require(str(transition.get("permission") or "document.manage"))
    _check_version(item, expected_version)
    if not _approvals_met(
        company_id=context.company.id,
        entity_type_code="DOCUMENT",
        entity_public_id=item.public_id,
        transition=transition,
    ):
        raise ValidationError({"target_status_code": "Required approval is not complete"})
    before = item.status_code
    item.status_code = target_status_code.strip().upper()
    item.version += 1
    item.full_clean()
    item.save()
    _publish_change(
        context=context,
        evidence=evidence,
        action="document.record.transitioned",
        entity_type="controlled_document",
        instance=item,
        before={"status_code": before},
        after={"status_code": item.status_code},
    )
    return item


@transaction.atomic
def create_revision(
    *,
    context: TenantContext,
    evidence: RequestEvidence,
    policy_public_id: uuid.UUID,
    document_public_id: uuid.UUID,
    attributes: dict[str, Any],
) -> DocumentRevision:
    context.require("document.manage")
    policy = _policy_for(context, policy_public_id)
    document = ControlledDocument.objects.filter(
        company=context.company, public_id=document_public_id, policy=policy
    ).first()
    if not document:
        raise ValidationError({"document_public_id": "Controlled document not found"})
    item = DocumentRevision(
        company=context.company,
        policy=policy,
        document=document,
        created_by_membership_public_id=context.membership.public_id,
        status_code=_configured_code(policy, "initial_revision_status"),
        **attributes,
    )
    item.full_clean()
    item.save()
    _publish_change(
        context=context,
        evidence=evidence,
        action="document.revision.created",
        entity_type="document_revision",
        instance=item,
        after={
            "document_number": document.document_number,
            "revision_code": item.revision_code,
            "sequence_number": item.sequence_number,
            "status_code": item.status_code,
        },
    )
    return item


@transaction.atomic
def transition_revision(
    *,
    context: TenantContext,
    evidence: RequestEvidence,
    revision_public_id: uuid.UUID,
    target_status_code: str,
    expected_version: int | None = None,
) -> DocumentRevision:
    item = (
        DocumentRevision.objects.select_for_update()
        .select_related("policy", "document")
        .filter(company=context.company, public_id=revision_public_id)
        .first()
    )
    if not item:
        raise ValidationError({"revision_public_id": "Document revision not found"})
    transition = _transition(
        item.policy, "revision_transitions", item.status_code, target_status_code
    )
    context.require(str(transition.get("permission") or "document.issue"))
    _check_version(item, expected_version)
    if not _approvals_met(
        company_id=context.company.id,
        entity_type_code="REVISION",
        entity_public_id=item.public_id,
        transition=transition,
    ):
        raise ValidationError({"target_status_code": "Required approval is not complete"})
    before = item.status_code
    item.status_code = target_status_code.strip().upper()
    item.version += 1
    milestone = str(transition.get("milestone") or "").lower()
    if milestone == "submitted":
        item.submitted_at = timezone.now()
    elif milestone == "reviewed":
        item.reviewed_by_membership_public_id = context.membership.public_id
    elif milestone == "issued":
        now = timezone.now()
        item.issued_at = now
        item.approved_by_membership_public_id = context.membership.public_id
        previous_document_state = {
            "current_revision_code": item.document.current_revision_code,
            "version": item.document.version,
        }
        item.document.current_revision_code = item.revision_code
        item.document.version += 1
        item.document.full_clean()
        item.document.save()
        _publish_change(
            context=context,
            evidence=evidence,
            action="document.current_revision.updated",
            entity_type="controlled_document",
            instance=item.document,
            before=previous_document_state,
            after={
                "current_revision_code": item.document.current_revision_code,
                "version": item.document.version,
            },
        )
    elif milestone == "superseded":
        item.superseded_at = timezone.now()
    item.full_clean()
    item.save()
    _publish_change(
        context=context,
        evidence=evidence,
        action="document.revision.transitioned",
        entity_type="document_revision",
        instance=item,
        before={"status_code": before},
        after={
            "status_code": item.status_code,
            "revision_code": item.revision_code,
        },
    )
    return item


@transaction.atomic
def create_transmittal(
    *,
    context: TenantContext,
    evidence: RequestEvidence,
    policy_public_id: uuid.UUID,
    attributes: dict[str, Any],
) -> DocumentTransmittal:
    context.require("document.issue")
    policy = _policy_for(context, policy_public_id)
    item = DocumentTransmittal(
        company=context.company,
        policy=policy,
        created_by_membership_public_id=context.membership.public_id,
        status_code=_configured_code(policy, "initial_transmittal_status"),
        **attributes,
    )
    item.full_clean()
    item.save()
    _publish_change(
        context=context,
        evidence=evidence,
        action="document.transmittal.created",
        entity_type="document_transmittal",
        instance=item,
        after={
            "transmittal_number": item.transmittal_number,
            "direction_code": item.direction_code,
            "status_code": item.status_code,
            "document_count": len(item.document_manifest),
        },
    )
    return item


@transaction.atomic
def transition_transmittal(
    *,
    context: TenantContext,
    evidence: RequestEvidence,
    transmittal_public_id: uuid.UUID,
    target_status_code: str,
    expected_version: int | None = None,
) -> DocumentTransmittal:
    item = (
        DocumentTransmittal.objects.select_for_update()
        .select_related("policy")
        .filter(company=context.company, public_id=transmittal_public_id)
        .first()
    )
    if not item:
        raise ValidationError({"transmittal_public_id": "Transmittal not found"})
    transition = _transition(
        item.policy, "transmittal_transitions", item.status_code, target_status_code
    )
    context.require(str(transition.get("permission") or "document.issue"))
    _check_version(item, expected_version)
    if not _approvals_met(
        company_id=context.company.id,
        entity_type_code="TRANSMITTAL",
        entity_public_id=item.public_id,
        transition=transition,
    ):
        raise ValidationError({"target_status_code": "Required approval is not complete"})
    before = item.status_code
    item.status_code = target_status_code.strip().upper()
    item.version += 1
    milestone = str(transition.get("milestone") or "").lower()
    if milestone == "issued":
        item.issued_at = timezone.now()
    elif milestone == "acknowledged":
        item.acknowledged_at = timezone.now()
    elif milestone == "closed":
        if not item.acknowledged_at:
            item.acknowledged_at = timezone.now()
        item.closed_at = timezone.now()
    item.full_clean()
    item.save()
    _publish_change(
        context=context,
        evidence=evidence,
        action="document.transmittal.transitioned",
        entity_type="document_transmittal",
        instance=item,
        before={"status_code": before},
        after={"status_code": item.status_code},
    )
    return item


@transaction.atomic
def create_rfi(
    *,
    context: TenantContext,
    evidence: RequestEvidence,
    policy_public_id: uuid.UUID,
    attributes: dict[str, Any],
) -> RequestForInformation:
    context.require("document.rfi")
    policy = _policy_for(context, policy_public_id)
    if assignee := attributes.get("assigned_to_membership_public_id"):
        _require_membership(context, assignee, "assigned_to_membership_public_id")
    item = RequestForInformation(
        company=context.company,
        policy=policy,
        raised_by_membership_public_id=context.membership.public_id,
        status_code=_configured_code(policy, "initial_rfi_status"),
        **attributes,
    )
    item.full_clean()
    item.save()
    _publish_change(
        context=context,
        evidence=evidence,
        action="document.rfi.created",
        entity_type="request_for_information",
        instance=item,
        after={
            "rfi_number": item.rfi_number,
            "priority_code": item.priority_code,
            "status_code": item.status_code,
            "response_due_at": item.response_due_at.isoformat()
            if item.response_due_at
            else None,
        },
    )
    return item


@transaction.atomic
def transition_rfi(
    *,
    context: TenantContext,
    evidence: RequestEvidence,
    rfi_public_id: uuid.UUID,
    target_status_code: str,
    expected_version: int | None = None,
    response_text: str = "",
) -> RequestForInformation:
    item = (
        RequestForInformation.objects.select_for_update()
        .select_related("policy")
        .filter(company=context.company, public_id=rfi_public_id)
        .first()
    )
    if not item:
        raise ValidationError({"rfi_public_id": "RFI not found"})
    transition = _transition(item.policy, "rfi_transitions", item.status_code, target_status_code)
    context.require(str(transition.get("permission") or "document.rfi"))
    _check_version(item, expected_version)
    if not _approvals_met(
        company_id=context.company.id,
        entity_type_code="RFI",
        entity_public_id=item.public_id,
        transition=transition,
    ):
        raise ValidationError({"target_status_code": "Required approval is not complete"})
    before = item.status_code
    item.status_code = target_status_code.strip().upper()
    item.version += 1
    milestone = str(transition.get("milestone") or "").lower()
    if milestone in {"responded", "closed"}:
        if not response_text.strip() and not item.response_text:
            raise ValidationError({"response_text": "A governed response is required"})
        item.response_text = response_text.strip() or item.response_text
        item.responded_at = item.responded_at or timezone.now()
        item.responded_by_membership_public_id = context.membership.public_id
    if milestone == "closed":
        item.closed_at = timezone.now()
    item.full_clean()
    item.save()
    _publish_change(
        context=context,
        evidence=evidence,
        action="document.rfi.transitioned",
        entity_type="request_for_information",
        instance=item,
        before={"status_code": before},
        after={"status_code": item.status_code, "responded": item.responded_at is not None},
    )
    return item


@transaction.atomic
def create_submittal(
    *,
    context: TenantContext,
    evidence: RequestEvidence,
    policy_public_id: uuid.UUID,
    attributes: dict[str, Any],
) -> TechnicalSubmittal:
    context.require("document.submittal")
    policy = _policy_for(context, policy_public_id)
    if reviewer := attributes.get("reviewer_membership_public_id"):
        _require_membership(context, reviewer, "reviewer_membership_public_id")
    item = TechnicalSubmittal(
        company=context.company,
        policy=policy,
        submitted_by_membership_public_id=context.membership.public_id,
        status_code=_configured_code(policy, "initial_submittal_status"),
        **attributes,
    )
    item.full_clean()
    item.save()
    _publish_change(
        context=context,
        evidence=evidence,
        action="document.submittal.created",
        entity_type="technical_submittal",
        instance=item,
        after={
            "submittal_number": item.submittal_number,
            "revision_number": item.revision_number,
            "category_code": item.category_code,
            "status_code": item.status_code,
        },
    )
    return item


@transaction.atomic
def transition_submittal(
    *,
    context: TenantContext,
    evidence: RequestEvidence,
    submittal_public_id: uuid.UUID,
    target_status_code: str,
    expected_version: int | None = None,
    decision_code: str = "",
    decision_note: str = "",
) -> TechnicalSubmittal:
    item = (
        TechnicalSubmittal.objects.select_for_update()
        .select_related("policy")
        .filter(company=context.company, public_id=submittal_public_id)
        .first()
    )
    if not item:
        raise ValidationError({"submittal_public_id": "Technical submittal not found"})
    transition = _transition(
        item.policy, "submittal_transitions", item.status_code, target_status_code
    )
    context.require(str(transition.get("permission") or "document.submittal"))
    _check_version(item, expected_version)
    if not _approvals_met(
        company_id=context.company.id,
        entity_type_code="SUBMITTAL",
        entity_public_id=item.public_id,
        transition=transition,
    ):
        raise ValidationError({"target_status_code": "Required approval is not complete"})
    before = item.status_code
    item.status_code = target_status_code.strip().upper()
    item.version += 1
    milestone = str(transition.get("milestone") or "").lower()
    if milestone == "submitted":
        item.submitted_at = timezone.now()
    elif milestone in {"reviewed", "closed"}:
        if not decision_code.strip():
            raise ValidationError({"decision_code": "A review decision is required"})
        item.reviewed_at = timezone.now()
        item.reviewer_membership_public_id = context.membership.public_id
        item.decision_code = decision_code.strip().upper()
        item.decision_note = decision_note.strip()
    item.full_clean()
    item.save()
    _publish_change(
        context=context,
        evidence=evidence,
        action="document.submittal.transitioned",
        entity_type="technical_submittal",
        instance=item,
        before={"status_code": before},
        after={"status_code": item.status_code, "decision_code": item.decision_code},
    )
    return item


@transaction.atomic
def request_approval(
    *,
    context: TenantContext,
    evidence: RequestEvidence,
    policy_public_id: uuid.UUID,
    attributes: dict[str, Any],
) -> DocumentApproval:
    context.require("document.manage")
    policy = _policy_for(context, policy_public_id)
    checker = attributes.get("requested_from_membership_public_id")
    if not checker:
        raise ValidationError({"requested_from_membership_public_id": "Approver is required"})
    _require_membership(context, checker, "requested_from_membership_public_id")
    if checker == context.membership.public_id:
        raise ValidationError(
            {"requested_from_membership_public_id": "Maker and checker must differ"}
        )
    item = DocumentApproval(
        company=context.company,
        policy=policy,
        requested_by_membership_public_id=context.membership.public_id,
        requested_at=timezone.now(),
        status_code=_configured_code(policy, "initial_approval_status"),
        **attributes,
    )
    item.full_clean()
    item.save()
    _publish_change(
        context=context,
        evidence=evidence,
        action="document.approval.requested",
        entity_type="document_approval",
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
) -> DocumentApproval:
    context.require("document.approve")
    item = (
        DocumentApproval.objects.select_for_update()
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
        action="document.approval.decided",
        entity_type="document_approval",
        instance=item,
        before={"status_code": before},
        after={"status_code": item.status_code},
        reason_code=decision_code.strip().upper(),
    )
    return item


@transaction.atomic
def record_distribution(
    *,
    context: TenantContext,
    evidence: RequestEvidence,
    policy_public_id: uuid.UUID,
    revision_public_id: uuid.UUID,
    attributes: dict[str, Any],
) -> DocumentDistribution:
    context.require("document.issue")
    policy = _policy_for(context, policy_public_id)
    revision = DocumentRevision.objects.select_related("document").filter(
        company=context.company,
        public_id=revision_public_id,
        policy=policy,
        issued_at__isnull=False,
        superseded_at__isnull=True,
    ).first()
    if not revision:
        raise ValidationError(
            {"revision_public_id": "Current issued document revision not found"}
        )
    status_code = str(
        policy.configuration.get("initial_distribution_status", "DISTRIBUTED")
    ).strip().upper()
    item = DocumentDistribution(
        company=context.company,
        policy=policy,
        revision=revision,
        distributed_by_membership_public_id=context.membership.public_id,
        distributed_at=timezone.now(),
        status_code=status_code,
        **attributes,
    )
    item.full_clean()
    item.save()
    _publish_change(
        context=context,
        evidence=evidence,
        action="document.distribution.recorded",
        entity_type="document_distribution",
        instance=item,
        after={
            "document_number": revision.document.document_number,
            "revision_code": revision.revision_code,
            "recipient_type_code": item.recipient_type_code,
            "purpose_code": item.purpose_code,
            "status_code": item.status_code,
        },
    )
    return item


@transaction.atomic
def acknowledge_distribution(
    *,
    context: TenantContext,
    evidence: RequestEvidence,
    distribution_public_id: uuid.UUID,
    expected_version: int | None = None,
) -> DocumentDistribution:
    context.require("document.issue")
    item = (
        DocumentDistribution.objects.select_for_update()
        .select_related("policy", "revision", "revision__document")
        .filter(company=context.company, public_id=distribution_public_id)
        .first()
    )
    if not item:
        raise ValidationError({"distribution_public_id": "Distribution not found"})
    _check_version(item, expected_version)
    if item.revoked_at:
        raise ValidationError({"distribution_public_id": "Distribution was revoked"})
    if item.acknowledged_at:
        raise ValidationError({"distribution_public_id": "Distribution is already acknowledged"})
    before = item.status_code
    item.acknowledged_at = timezone.now()
    item.status_code = str(
        item.policy.configuration.get("acknowledged_distribution_status", "ACKNOWLEDGED")
    ).strip().upper()
    item.version += 1
    item.full_clean()
    item.save()
    _publish_change(
        context=context,
        evidence=evidence,
        action="document.distribution.acknowledged",
        entity_type="document_distribution",
        instance=item,
        before={"status_code": before},
        after={"status_code": item.status_code},
    )
    return item


@transaction.atomic
def create_risk(
    *,
    context: TenantContext,
    evidence: RequestEvidence,
    policy_public_id: uuid.UUID,
    attributes: dict[str, Any],
) -> DocumentRisk:
    context.require("document.manage")
    policy = _policy_for(context, policy_public_id)
    item = DocumentRisk(
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
        action="document.risk.created",
        entity_type="document_risk",
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
) -> DocumentRisk:
    context.require("document.manage")
    item = (
        DocumentRisk.objects.select_for_update()
        .select_related("policy")
        .filter(company=context.company, public_id=risk_public_id)
        .first()
    )
    if not item:
        raise ValidationError({"risk_public_id": "Document-control risk not found"})
    _check_version(item, expected_version)
    if item.resolved_at:
        raise ValidationError({"resolution_note": "Risk is already resolved"})
    if not resolution_note.strip():
        raise ValidationError({"resolution_note": "Resolution note is required"})
    before = item.status_code
    item.status_code = _configured_code(item.policy, "resolved_risk_status")
    item.resolved_at = timezone.now()
    item.resolved_by_membership_public_id = context.membership.public_id
    item.resolution_note = resolution_note.strip()
    item.version += 1
    item.full_clean()
    item.save()
    _publish_change(
        context=context,
        evidence=evidence,
        action="document.risk.resolved",
        entity_type="document_risk",
        instance=item,
        before={"status_code": before},
        after={"status_code": item.status_code},
    )
    return item
