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

from modules.equipmentops.models import (
    EquipmentApproval,
    EquipmentAsset,
    EquipmentDeployment,
    EquipmentInspection,
    EquipmentMeterReading,
    EquipmentPolicyVersion,
    EquipmentRisk,
    MaintenanceWorkOrder,
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


def _active_policy(
    *,
    company_id: int,
    public_id: uuid.UUID,
) -> EquipmentPolicyVersion | None:
    now = timezone.now()
    return (
        EquipmentPolicyVersion.objects.filter(
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


def _asset_is_immutable(asset: EquipmentAsset) -> bool:
    configured = asset.policy.configuration.get("immutable_asset_statuses", [])
    return asset.status_code in configured


def _work_order_transition(
    work_order: MaintenanceWorkOrder,
    target_status_code: str,
) -> dict[str, Any]:
    transitions = work_order.asset.policy.configuration.get(
        "work_order_transitions",
        [],
    )
    for transition in transitions:
        if (
            isinstance(transition, dict)
            and transition.get("from") == work_order.status_code
            and transition.get("to") == target_status_code
        ):
            return transition
    raise ValidationError(
        {
            "target_status_code": (
                f"Transition {work_order.status_code} to {target_status_code} "
                "is not configured"
            )
        }
    )


@transaction.atomic
def create_policy(
    *,
    context: TenantContext,
    evidence: RequestEvidence,
    attributes: dict[str, Any],
) -> EquipmentPolicyVersion:
    context.require("equipment.configure")
    policy = EquipmentPolicyVersion(company=context.company, **attributes)
    policy.full_clean()
    policy.save()
    _audit(
        context=context,
        evidence=evidence,
        action="equipment.policy.created",
        entity_type="equipment_policy",
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
        event_type="equipment.policy.created",
        aggregate_type="equipment_policy",
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
def create_asset(
    *,
    context: TenantContext,
    evidence: RequestEvidence,
    policy_public_id: uuid.UUID,
    attributes: dict[str, Any],
) -> EquipmentAsset:
    context.require("equipment.manage")
    policy = _active_policy(
        company_id=context.company.id,
        public_id=policy_public_id,
    )
    if not policy:
        raise ValidationError({"policy_public_id": "Published equipment policy not found"})
    initial_status = str(policy.configuration.get("initial_asset_status", "")).strip()
    if not initial_status:
        raise ValidationError({"policy_public_id": "Policy has no initial asset status"})
    payload = dict(attributes)
    payload.pop("status_code", None)
    payload["currency"] = str(payload.get("currency") or context.company.currency).upper()
    asset = EquipmentAsset(
        company=context.company,
        policy=policy,
        status_code=initial_status,
        **payload,
    )
    asset.full_clean()
    asset.save()
    _audit(
        context=context,
        evidence=evidence,
        action="equipment.asset.created",
        entity_type="equipment_asset",
        entity_public_id=asset.public_id,
        after={
            "asset_code": asset.asset_code,
            "category_code": asset.category_code,
            "status_code": asset.status_code,
            "ownership_code": asset.ownership_code,
        },
    )
    _event(
        context=context,
        evidence=evidence,
        event_type="equipment.asset.created",
        aggregate_type="equipment_asset",
        aggregate_public_id=asset.public_id,
        aggregate_version=asset.version,
        payload={
            "asset_code": asset.asset_code,
            "category_code": asset.category_code,
            "status_code": asset.status_code,
        },
    )
    return asset


@transaction.atomic
def create_deployment(
    *,
    context: TenantContext,
    evidence: RequestEvidence,
    asset_public_id: uuid.UUID,
    attributes: dict[str, Any],
) -> EquipmentDeployment:
    context.require("equipment.manage")
    asset = (
        EquipmentAsset.objects.select_for_update()
        .select_related("policy")
        .filter(company=context.company, public_id=asset_public_id)
        .first()
    )
    if not asset:
        raise ValidationError({"asset_public_id": "Equipment asset not found"})
    if _asset_is_immutable(asset):
        raise ValidationError({"asset_public_id": "Equipment asset is immutable"})
    status_code = str(
        asset.policy.configuration.get("initial_deployment_status", "")
    ).strip()
    if not status_code:
        raise ValidationError({"asset_public_id": "Policy has no deployment status"})
    deployment = EquipmentDeployment(
        company=context.company,
        asset=asset,
        status_code=status_code,
        **attributes,
    )
    deployment.full_clean()
    active_statuses = asset.policy.configuration.get("active_deployment_statuses", [])
    if deployment.status_code in active_statuses:
        overlapping_query = EquipmentDeployment.objects.filter(
            company=context.company,
            asset=asset,
            status_code__in=active_statuses,
        ).filter(Q(ends_at__isnull=True) | Q(ends_at__gt=deployment.starts_at))
        if deployment.ends_at is not None:
            overlapping_query = overlapping_query.filter(
                starts_at__lt=deployment.ends_at
            )
        if overlapping_query.exists():
            raise ValidationError({"starts_at": "Asset has an overlapping deployment"})
    deployment.save()
    deployed_asset_status = asset.policy.configuration.get("deployed_asset_status")
    if deployment.status_code in active_statuses and isinstance(deployed_asset_status, str):
        before_status = asset.status_code
        asset.status_code = deployed_asset_status
        asset.version += 1
        asset.full_clean()
        asset.save(update_fields=["status_code", "version", "updated_at"])
        _audit(
            context=context,
            evidence=evidence,
            action="equipment.asset.status_changed",
            entity_type="equipment_asset",
            entity_public_id=asset.public_id,
            before={"status_code": before_status},
            after={"status_code": asset.status_code},
            reason_code="DEPLOYMENT_CREATED",
        )
    _audit(
        context=context,
        evidence=evidence,
        action="equipment.deployment.created",
        entity_type="equipment_deployment",
        entity_public_id=deployment.public_id,
        after={
            "asset_public_id": str(asset.public_id),
            "deployment_code": deployment.deployment_code,
            "status_code": deployment.status_code,
            "project_public_id": (
                str(deployment.project_public_id) if deployment.project_public_id else None
            ),
        },
    )
    _event(
        context=context,
        evidence=evidence,
        event_type="equipment.deployment.created",
        aggregate_type="equipment_deployment",
        aggregate_public_id=deployment.public_id,
        aggregate_version=deployment.version,
        payload={
            "asset_public_id": str(asset.public_id),
            "deployment_code": deployment.deployment_code,
            "status_code": deployment.status_code,
        },
    )
    return deployment


@transaction.atomic
def record_meter_reading(
    *,
    context: TenantContext,
    evidence: RequestEvidence,
    asset_public_id: uuid.UUID,
    reading_at: Any,
    meter_type_code: str,
    reading_value: Any,
    source_code: str,
    deployment_public_id: uuid.UUID | None = None,
    evidence_object_key: str = "",
    metadata: dict[str, Any] | None = None,
    expected_asset_version: int | None = None,
) -> EquipmentMeterReading:
    context.require("equipment.manage")
    asset = (
        EquipmentAsset.objects.select_for_update()
        .select_related("policy")
        .filter(company=context.company, public_id=asset_public_id)
        .first()
    )
    if not asset:
        raise ValidationError({"asset_public_id": "Equipment asset not found"})
    if expected_asset_version is not None and asset.version != expected_asset_version:
        raise ValidationError(
            {"expected_asset_version": "Equipment asset was modified by another request"}
        )
    deployment = None
    if deployment_public_id:
        deployment = EquipmentDeployment.objects.filter(
            company=context.company,
            asset=asset,
            public_id=deployment_public_id,
        ).first()
        if not deployment:
            raise ValidationError({"deployment_public_id": "Deployment not found"})
    parsed = _decimal(reading_value, "reading_value")
    if parsed < 0:
        raise ValidationError({"reading_value": "Reading cannot be negative"})
    action = str(asset.policy.configuration.get("meter_regression_action", "BLOCK")).upper()
    regression = parsed < asset.current_meter_value
    if regression and action == "BLOCK":
        raise ValidationError(
            {"reading_value": "Reading cannot be lower than the current governed meter"}
        )
    reading = EquipmentMeterReading(
        company=context.company,
        asset=asset,
        deployment=deployment,
        reading_at=reading_at,
        meter_type_code=meter_type_code.strip(),
        reading_value=parsed,
        source_code=source_code.strip(),
        recorded_by_public_id=_actor(context),
        evidence_object_key=evidence_object_key.strip(),
        metadata=metadata or {},
    )
    reading.full_clean()
    reading.save()
    before_meter = str(asset.current_meter_value)
    asset.current_meter_value = parsed
    if not asset.meter_type_code:
        asset.meter_type_code = reading.meter_type_code
    asset.version += 1
    asset.full_clean()
    asset.save(update_fields=["current_meter_value", "meter_type_code", "version", "updated_at"])
    if regression and action == "RISK":
        risk = EquipmentRisk(
            company=context.company,
            asset=asset,
            risk_code=str(
                asset.policy.configuration.get(
                    "meter_regression_risk_code",
                    "METER_REGRESSION",
                )
            ),
            severity_code=str(
                asset.policy.configuration.get(
                    "meter_regression_severity",
                    "HIGH",
                )
            ),
            status_code=str(
                asset.policy.configuration.get("open_risk_status", "OPEN")
            ),
            message=(
                f"Meter reading regressed from {before_meter} to {parsed} "
                f"for asset {asset.asset_code}."
            ),
            metadata={"reading_public_id": str(reading.public_id)},
        )
        risk.full_clean()
        risk.save()
    _audit(
        context=context,
        evidence=evidence,
        action="equipment.meter.recorded",
        entity_type="equipment_asset",
        entity_public_id=asset.public_id,
        before={"current_meter_value": before_meter},
        after={
            "current_meter_value": str(asset.current_meter_value),
            "reading_public_id": str(reading.public_id),
            "meter_type_code": reading.meter_type_code,
        },
        reason_code="METER_REGRESSION" if regression else "",
    )
    _event(
        context=context,
        evidence=evidence,
        event_type="equipment.meter.recorded",
        aggregate_type="equipment_asset",
        aggregate_public_id=asset.public_id,
        aggregate_version=asset.version,
        payload={
            "reading_public_id": str(reading.public_id),
            "meter_type_code": reading.meter_type_code,
            "reading_value": str(reading.reading_value),
            "regression": regression,
        },
    )
    return reading


@transaction.atomic
def create_work_order(
    *,
    context: TenantContext,
    evidence: RequestEvidence,
    asset_public_id: uuid.UUID,
    attributes: dict[str, Any],
) -> MaintenanceWorkOrder:
    context.require("equipment.maintain")
    asset = (
        EquipmentAsset.objects.select_for_update()
        .select_related("policy")
        .filter(company=context.company, public_id=asset_public_id)
        .first()
    )
    if not asset:
        raise ValidationError({"asset_public_id": "Equipment asset not found"})
    initial_status = str(
        asset.policy.configuration.get("initial_work_order_status", "")
    ).strip()
    if not initial_status:
        raise ValidationError({"asset_public_id": "Policy has no work-order status"})
    payload = dict(attributes)
    payload.pop("status_code", None)
    payload["currency"] = str(payload.get("currency") or context.company.currency).upper()
    work_order = MaintenanceWorkOrder(
        company=context.company,
        asset=asset,
        status_code=initial_status,
        reported_at=payload.pop("reported_at", timezone.now()),
        **payload,
    )
    work_order.full_clean()
    work_order.save()
    hold_status = asset.policy.configuration.get("maintenance_hold_asset_status")
    hold_priorities = asset.policy.configuration.get("maintenance_hold_priorities", [])
    if (
        isinstance(hold_status, str)
        and work_order.priority_code in hold_priorities
        and not _asset_is_immutable(asset)
    ):
        asset.status_code = hold_status
        asset.version += 1
        asset.full_clean()
        asset.save(update_fields=["status_code", "version", "updated_at"])
    _audit(
        context=context,
        evidence=evidence,
        action="equipment.work_order.created",
        entity_type="equipment_work_order",
        entity_public_id=work_order.public_id,
        after={
            "asset_public_id": str(asset.public_id),
            "code": work_order.code,
            "status_code": work_order.status_code,
            "priority_code": work_order.priority_code,
            "estimated_cost": str(work_order.estimated_cost),
            "currency": work_order.currency,
        },
    )
    _event(
        context=context,
        evidence=evidence,
        event_type="equipment.work_order.created",
        aggregate_type="equipment_work_order",
        aggregate_public_id=work_order.public_id,
        aggregate_version=work_order.version,
        payload={
            "asset_public_id": str(asset.public_id),
            "code": work_order.code,
            "status_code": work_order.status_code,
            "priority_code": work_order.priority_code,
        },
    )
    return work_order


@transaction.atomic
def transition_work_order(
    *,
    context: TenantContext,
    evidence: RequestEvidence,
    work_order_public_id: uuid.UUID,
    target_status_code: str,
    expected_version: int,
    reason_code: str = "",
) -> MaintenanceWorkOrder:
    work_order = (
        MaintenanceWorkOrder.objects.select_for_update()
        .select_related("asset__policy")
        .filter(company=context.company, public_id=work_order_public_id)
        .first()
    )
    if not work_order:
        raise ValidationError({"work_order_public_id": "Work order not found"})
    if work_order.version != expected_version:
        raise ValidationError({"expected_version": "Work order was modified"})
    transition = _work_order_transition(work_order, target_status_code)
    permission = str(transition.get("permission", "")).strip()
    context.require(permission)
    required_approvals = transition.get("required_approvals", [])
    for requirement in required_approvals:
        accepted = requirement.get("accepted_statuses", [])
        if not EquipmentApproval.objects.filter(
            company=context.company,
            work_order=work_order,
            step_code=requirement.get("step_code"),
            status_code__in=accepted,
        ).exists():
            raise ValidationError(
                {
                    "target_status_code": (
                        f"Approval {requirement.get('step_code')} is required"
                    )
                }
            )
    before = {"status_code": work_order.status_code, "version": work_order.version}
    work_order.status_code = target_status_code
    work_order.version += 1
    now = timezone.now()
    milestone = transition.get("milestone")
    update_fields = ["status_code", "version", "updated_at"]
    if milestone == "approved":
        work_order.approved_at = now
        work_order.approved_by_public_id = _actor(context)
        update_fields.extend(["approved_at", "approved_by_public_id"])
    elif milestone == "completed":
        work_order.completed_at = now
        update_fields.append("completed_at")
    elif milestone == "closed":
        work_order.closed_at = now
        update_fields.append("closed_at")
    work_order.full_clean()
    work_order.save(update_fields=update_fields)
    asset_status_map = work_order.asset.policy.configuration.get(
        "asset_status_by_work_order_status",
        {},
    )
    mapped_status = asset_status_map.get(target_status_code) if isinstance(asset_status_map, dict) else None
    if isinstance(mapped_status, str) and not _asset_is_immutable(work_order.asset):
        work_order.asset.status_code = mapped_status
        work_order.asset.version += 1
        work_order.asset.full_clean()
        work_order.asset.save(update_fields=["status_code", "version", "updated_at"])
    _audit(
        context=context,
        evidence=evidence,
        action="equipment.work_order.transitioned",
        entity_type="equipment_work_order",
        entity_public_id=work_order.public_id,
        before=before,
        after={"status_code": work_order.status_code, "version": work_order.version},
        reason_code=reason_code,
    )
    _event(
        context=context,
        evidence=evidence,
        event_type="equipment.work_order.transitioned",
        aggregate_type="equipment_work_order",
        aggregate_public_id=work_order.public_id,
        aggregate_version=work_order.version,
        payload={
            "status_code": work_order.status_code,
            "asset_public_id": str(work_order.asset.public_id),
            "reason_code": reason_code,
        },
    )
    return work_order


@transaction.atomic
def record_inspection(
    *,
    context: TenantContext,
    evidence: RequestEvidence,
    asset_public_id: uuid.UUID,
    attributes: dict[str, Any],
) -> EquipmentInspection:
    context.require("equipment.maintain")
    asset = (
        EquipmentAsset.objects.select_for_update()
        .select_related("policy")
        .filter(company=context.company, public_id=asset_public_id)
        .first()
    )
    if not asset:
        raise ValidationError({"asset_public_id": "Equipment asset not found"})
    inspection = EquipmentInspection(
        company=context.company,
        asset=asset,
        **attributes,
    )
    inspection.full_clean()
    inspection.save()
    accepted = asset.policy.configuration.get("accepted_inspection_results", [])
    if inspection.result_code in accepted and inspection.valid_until:
        asset.compliance_due_on = inspection.valid_until
        asset.version += 1
        asset.save(update_fields=["compliance_due_on", "version", "updated_at"])
    elif inspection.result_code not in accepted:
        risk = EquipmentRisk(
            company=context.company,
            asset=asset,
            risk_code=str(
                asset.policy.configuration.get(
                    "inspection_failure_risk_code",
                    "INSPECTION_NOT_ACCEPTED",
                )
            ),
            severity_code=str(
                asset.policy.configuration.get(
                    "inspection_failure_severity",
                    "HIGH",
                )
            ),
            status_code=str(
                asset.policy.configuration.get("open_risk_status", "OPEN")
            ),
            message=(
                f"Inspection {inspection.inspection_code} returned "
                f"{inspection.result_code} for asset {asset.asset_code}."
            ),
            metadata={"inspection_public_id": str(inspection.public_id)},
        )
        risk.full_clean()
        risk.save()
    _audit(
        context=context,
        evidence=evidence,
        action="equipment.inspection.recorded",
        entity_type="equipment_inspection",
        entity_public_id=inspection.public_id,
        after={
            "asset_public_id": str(asset.public_id),
            "inspection_code": inspection.inspection_code,
            "result_code": inspection.result_code,
            "valid_until": (
                inspection.valid_until.isoformat() if inspection.valid_until else None
            ),
        },
    )
    _event(
        context=context,
        evidence=evidence,
        event_type="equipment.inspection.recorded",
        aggregate_type="equipment_inspection",
        aggregate_public_id=inspection.public_id,
        aggregate_version=1,
        payload={
            "asset_public_id": str(asset.public_id),
            "result_code": inspection.result_code,
            "valid_until": (
                inspection.valid_until.isoformat() if inspection.valid_until else None
            ),
        },
    )
    return inspection


@transaction.atomic
def request_approval(
    *,
    context: TenantContext,
    evidence: RequestEvidence,
    work_order_public_id: uuid.UUID,
    step_code: str,
    requested_from_membership_public_id: uuid.UUID,
    status_code: str,
    due_at: Any = None,
    metadata: dict[str, Any] | None = None,
) -> EquipmentApproval:
    context.require("equipment.maintain")
    work_order = MaintenanceWorkOrder.objects.filter(
        company=context.company,
        public_id=work_order_public_id,
    ).first()
    if not work_order:
        raise ValidationError({"work_order_public_id": "Work order not found"})
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
    approval = EquipmentApproval(
        company=context.company,
        work_order=work_order,
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
        action="equipment.approval.requested",
        entity_type="equipment_approval",
        entity_public_id=approval.public_id,
        after={
            "work_order_public_id": str(work_order.public_id),
            "step_code": approval.step_code,
            "status_code": approval.status_code,
            "requested_from_membership_public_id": str(target_membership.public_id),
        },
    )
    _event(
        context=context,
        evidence=evidence,
        event_type="equipment.approval.requested",
        aggregate_type="equipment_approval",
        aggregate_public_id=approval.public_id,
        aggregate_version=1,
        payload={
            "work_order_public_id": str(work_order.public_id),
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
    decision_reason: str = "",
) -> EquipmentApproval:
    context.require("equipment.approve")
    approval = (
        EquipmentApproval.objects.select_for_update()
        .select_related("work_order__asset__policy")
        .filter(company=context.company, public_id=approval_public_id)
        .first()
    )
    if not approval:
        raise ValidationError({"approval_public_id": "Approval not found"})
    if approval.decided_at:
        raise ValidationError({"approval_public_id": "Approval is already decided"})
    if approval.requested_from_membership_public_id != context.membership.public_id:
        raise PermissionDenied("Approval is assigned to another membership")
    maker_checker = bool(
        approval.work_order.asset.policy.configuration.get(
            "maker_checker_required",
            True,
        )
    )
    if maker_checker and approval.requested_by_public_id == _actor(context):
        raise ValidationError(
            {"approval_public_id": "Maker-checker separation is required"}
        )
    decisions = approval.work_order.asset.policy.configuration.get(
        "approval_decisions",
        {},
    )
    status_code = decisions.get(decision_code)
    if not isinstance(status_code, str) or not status_code:
        raise ValidationError({"decision_code": "Decision is not configured"})
    before = {"status_code": approval.status_code}
    approval.status_code = status_code
    approval.decision_code = decision_code
    approval.decision_reason = decision_reason.strip()
    approval.decided_at = timezone.now()
    approval.decided_by_public_id = _actor(context)
    approval.full_clean()
    approval.save(
        update_fields=[
            "status_code",
            "decision_code",
            "decision_reason",
            "decided_at",
            "decided_by_public_id",
            "updated_at",
        ]
    )
    _audit(
        context=context,
        evidence=evidence,
        action="equipment.approval.decided",
        entity_type="equipment_approval",
        entity_public_id=approval.public_id,
        before=before,
        after={
            "status_code": approval.status_code,
            "decision_code": approval.decision_code,
        },
        reason_code=decision_reason,
    )
    _event(
        context=context,
        evidence=evidence,
        event_type="equipment.approval.decided",
        aggregate_type="equipment_approval",
        aggregate_public_id=approval.public_id,
        aggregate_version=2,
        payload={
            "work_order_public_id": str(approval.work_order.public_id),
            "step_code": approval.step_code,
            "status_code": approval.status_code,
            "decision_code": approval.decision_code,
        },
    )
    return approval


@transaction.atomic
def create_risk(
    *,
    context: TenantContext,
    evidence: RequestEvidence,
    asset_public_id: uuid.UUID,
    attributes: dict[str, Any],
) -> EquipmentRisk:
    context.require("equipment.maintain")
    asset = EquipmentAsset.objects.filter(
        company=context.company,
        public_id=asset_public_id,
    ).first()
    if not asset:
        raise ValidationError({"asset_public_id": "Equipment asset not found"})
    payload = dict(attributes)
    work_order_public_id = payload.pop("work_order_public_id", None)
    work_order = None
    if work_order_public_id:
        work_order = MaintenanceWorkOrder.objects.filter(
            company=context.company,
            asset=asset,
            public_id=work_order_public_id,
        ).first()
        if not work_order:
            raise ValidationError({"work_order_public_id": "Work order not found"})
    risk = EquipmentRisk(
        company=context.company,
        asset=asset,
        work_order=work_order,
        **payload,
    )
    risk.full_clean()
    risk.save()
    _audit(
        context=context,
        evidence=evidence,
        action="equipment.risk.created",
        entity_type="equipment_risk",
        entity_public_id=risk.public_id,
        after={
            "asset_public_id": str(asset.public_id),
            "risk_code": risk.risk_code,
            "severity_code": risk.severity_code,
            "status_code": risk.status_code,
        },
    )
    _event(
        context=context,
        evidence=evidence,
        event_type="equipment.risk.created",
        aggregate_type="equipment_risk",
        aggregate_public_id=risk.public_id,
        aggregate_version=1,
        payload={
            "asset_public_id": str(asset.public_id),
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
    resolution_code: str,
    resolution_note: str = "",
    resolved_status_code: str = "RESOLVED",
) -> EquipmentRisk:
    context.require("equipment.maintain")
    risk = EquipmentRisk.objects.select_for_update().filter(
        company=context.company,
        public_id=risk_public_id,
    ).first()
    if not risk:
        raise ValidationError({"risk_public_id": "Equipment risk not found"})
    if risk.resolved_at:
        raise ValidationError({"risk_public_id": "Equipment risk is already resolved"})
    before = {"status_code": risk.status_code}
    risk.status_code = resolved_status_code.strip()
    risk.resolution_code = resolution_code.strip()
    risk.resolution_note = resolution_note.strip()
    risk.resolved_at = timezone.now()
    risk.resolved_by_public_id = _actor(context)
    risk.full_clean()
    risk.save(
        update_fields=[
            "status_code",
            "resolution_code",
            "resolution_note",
            "resolved_at",
            "resolved_by_public_id",
            "updated_at",
        ]
    )
    _audit(
        context=context,
        evidence=evidence,
        action="equipment.risk.resolved",
        entity_type="equipment_risk",
        entity_public_id=risk.public_id,
        before=before,
        after={
            "status_code": risk.status_code,
            "resolution_code": risk.resolution_code,
        },
        reason_code=resolution_note,
    )
    _event(
        context=context,
        evidence=evidence,
        event_type="equipment.risk.resolved",
        aggregate_type="equipment_risk",
        aggregate_public_id=risk.public_id,
        aggregate_version=2,
        payload={
            "asset_public_id": str(risk.asset.public_id),
            "status_code": risk.status_code,
            "resolution_code": risk.resolution_code,
        },
    )
    return risk
