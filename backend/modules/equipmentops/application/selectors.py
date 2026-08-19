from __future__ import annotations

from collections import defaultdict
from datetime import timedelta
from decimal import Decimal
from typing import Any

from django.db.models import Count, F, Q, Sum
from django.utils import timezone

from modules.equipmentops.models import (
    EquipmentApproval,
    EquipmentAsset,
    EquipmentDeployment,
    EquipmentPolicyVersion,
    EquipmentRisk,
    MaintenanceWorkOrder,
)
from modules.tenant.models import Company


def _iso(value: Any) -> str | None:
    return value.isoformat() if value is not None else None


def _money(value: Decimal | None) -> str:
    return str(value or Decimal("0.00"))


def _policy_codes(company: Company, key: str, fallback: list[str]) -> list[str]:
    now = timezone.now()
    policies = (
        EquipmentPolicyVersion.objects.filter(
            company=company,
            published_at__isnull=False,
            published_at__lte=now,
            retired_at__isnull=True,
            effective_from__lte=now,
        )
        .filter(Q(effective_to__isnull=True) | Q(effective_to__gt=now))
        .values_list("configuration", flat=True)
    )
    codes: set[str] = set()
    for configuration in policies:
        configured = configuration.get(key, []) if isinstance(configuration, dict) else []
        if isinstance(configured, list):
            codes.update(
                item.strip()
                for item in configured
                if isinstance(item, str) and item.strip()
            )
    return sorted(codes) or fallback


def equipment_overview(company: Company) -> dict[str, Any]:
    now = timezone.now()
    today = timezone.localdate()
    service_horizon = today + timedelta(days=30)
    compliance_horizon = today + timedelta(days=60)

    active_deployment_statuses = _policy_codes(
        company,
        "active_deployment_statuses",
        [],
    )
    open_work_order_statuses = _policy_codes(
        company,
        "open_work_order_statuses",
        [],
    )

    assets = EquipmentAsset.objects.filter(company=company).select_related("policy")
    deployments = EquipmentDeployment.objects.filter(company=company).select_related("asset")
    work_orders = MaintenanceWorkOrder.objects.filter(company=company).select_related("asset")
    approvals = EquipmentApproval.objects.filter(company=company).select_related(
        "work_order",
        "work_order__asset",
    )
    risks = EquipmentRisk.objects.filter(company=company).select_related(
        "asset",
        "work_order",
    )

    inactive_asset_statuses = _policy_codes(
        company,
        "immutable_asset_statuses",
        [],
    )
    active_assets = (
        assets.exclude(status_code__in=inactive_asset_statuses)
        if inactive_asset_statuses
        else assets
    )
    active_asset_count = active_assets.count()
    active_deployments = deployments.filter(status_code__in=active_deployment_statuses)
    deployed_asset_count = active_deployments.values("asset_id").distinct().count()
    utilization_percent = (
        round((deployed_asset_count / active_asset_count) * 100, 1)
        if active_asset_count
        else 0.0
    )

    due_service_filter = (
        Q(next_service_on__isnull=False, next_service_on__lte=service_horizon)
        | Q(
            next_service_meter__isnull=False,
            next_service_meter__lte=F("current_meter_value"),
        )
    )
    service_due = active_assets.filter(due_service_filter)
    compliance_watch = active_assets.filter(
        compliance_due_on__isnull=False,
        compliance_due_on__lte=compliance_horizon,
    )
    open_orders = work_orders.filter(status_code__in=open_work_order_statuses)
    pending_approvals = approvals.filter(decided_at__isnull=True)
    open_risks = risks.filter(resolved_at__isnull=True)

    costs: dict[str, Decimal] = defaultdict(lambda: Decimal("0.00"))
    cost_rows = open_orders.values("currency").annotate(total=Sum("estimated_cost"))
    for row in cost_rows:
        costs[row["currency"]] += row["total"] or Decimal("0.00")
    cost_by_currency = [
        {"currency": currency, "amount": _money(amount)}
        for currency, amount in sorted(costs.items())
    ]
    company_cost = costs.get(company.currency, Decimal("0.00"))

    recent_assets = []
    for asset in assets.order_by("-created_at")[:12]:
        recent_assets.append(
            {
                "public_id": str(asset.public_id),
                "asset_code": asset.asset_code,
                "name": asset.name,
                "category_code": asset.category_code,
                "asset_type_code": asset.asset_type_code,
                "ownership_code": asset.ownership_code,
                "status_code": asset.status_code,
                "current_meter_value": str(asset.current_meter_value),
                "meter_type_code": asset.meter_type_code,
                "next_service_on": _iso(asset.next_service_on),
                "next_service_meter": (
                    str(asset.next_service_meter)
                    if asset.next_service_meter is not None
                    else None
                ),
                "compliance_due_on": _iso(asset.compliance_due_on),
                "policy_code": asset.policy.code,
                "policy_version": asset.policy.version,
                "version": asset.version,
                "created_at": _iso(asset.created_at),
                "updated_at": _iso(asset.updated_at),
            }
        )

    deployment_items = []
    for deployment in active_deployments.order_by("starts_at")[:12]:
        deployment_items.append(
            {
                "public_id": str(deployment.public_id),
                "asset_public_id": str(deployment.asset.public_id),
                "asset_code": deployment.asset.asset_code,
                "asset_name": deployment.asset.name,
                "deployment_code": deployment.deployment_code,
                "project_public_id": (
                    str(deployment.project_public_id)
                    if deployment.project_public_id
                    else None
                ),
                "location_public_id": (
                    str(deployment.location_public_id)
                    if deployment.location_public_id
                    else None
                ),
                "status_code": deployment.status_code,
                "starts_at": _iso(deployment.starts_at),
                "ends_at": _iso(deployment.ends_at),
                "operator_employee_public_id": (
                    str(deployment.operator_employee_public_id)
                    if deployment.operator_employee_public_id
                    else None
                ),
            }
        )

    service_items = []
    for asset in service_due.order_by("next_service_on", "next_service_meter")[:12]:
        due_by_date = bool(asset.next_service_on and asset.next_service_on <= today)
        due_by_meter = bool(
            asset.next_service_meter is not None
            and asset.next_service_meter <= asset.current_meter_value
        )
        service_items.append(
            {
                "public_id": str(asset.public_id),
                "asset_code": asset.asset_code,
                "asset_name": asset.name,
                "status_code": asset.status_code,
                "next_service_on": _iso(asset.next_service_on),
                "next_service_meter": (
                    str(asset.next_service_meter)
                    if asset.next_service_meter is not None
                    else None
                ),
                "current_meter_value": str(asset.current_meter_value),
                "meter_type_code": asset.meter_type_code,
                "overdue": due_by_date or due_by_meter,
            }
        )

    compliance_items = []
    for asset in compliance_watch.order_by("compliance_due_on")[:12]:
        compliance_items.append(
            {
                "public_id": str(asset.public_id),
                "asset_code": asset.asset_code,
                "asset_name": asset.name,
                "category_code": asset.category_code,
                "status_code": asset.status_code,
                "compliance_due_on": _iso(asset.compliance_due_on),
                "expired": bool(
                    asset.compliance_due_on and asset.compliance_due_on < today
                ),
            }
        )

    work_order_items = []
    for order in open_orders.order_by("priority_code", "scheduled_start", "-reported_at")[:12]:
        work_order_items.append(
            {
                "public_id": str(order.public_id),
                "asset_public_id": str(order.asset.public_id),
                "asset_code": order.asset.asset_code,
                "asset_name": order.asset.name,
                "code": order.code,
                "maintenance_type_code": order.maintenance_type_code,
                "priority_code": order.priority_code,
                "status_code": order.status_code,
                "summary": order.summary,
                "reported_at": _iso(order.reported_at),
                "scheduled_start": _iso(order.scheduled_start),
                "estimated_cost": str(order.estimated_cost),
                "currency": order.currency,
                "requires_approval": order.requires_approval,
                "version": order.version,
            }
        )

    approval_items = []
    for approval in pending_approvals.order_by("due_at", "requested_at")[:12]:
        approval_items.append(
            {
                "public_id": str(approval.public_id),
                "work_order_public_id": str(approval.work_order.public_id),
                "work_order_code": approval.work_order.code,
                "asset_code": approval.work_order.asset.asset_code,
                "step_code": approval.step_code,
                "status_code": approval.status_code,
                "requested_from_membership_public_id": str(
                    approval.requested_from_membership_public_id
                ),
                "requested_at": _iso(approval.requested_at),
                "due_at": _iso(approval.due_at),
            }
        )

    risk_items = []
    for risk in open_risks.order_by("severity_code", "due_at", "-created_at")[:12]:
        risk_items.append(
            {
                "public_id": str(risk.public_id),
                "asset_public_id": str(risk.asset.public_id),
                "asset_code": risk.asset.asset_code,
                "work_order_public_id": (
                    str(risk.work_order.public_id) if risk.work_order else None
                ),
                "risk_code": risk.risk_code,
                "severity_code": risk.severity_code,
                "status_code": risk.status_code,
                "message": risk.message,
                "due_at": _iso(risk.due_at),
                "created_at": _iso(risk.created_at),
            }
        )

    risk_severity = list(
        open_risks.values("severity_code")
        .annotate(count=Count("id"))
        .order_by("severity_code")
    )

    policy_count = EquipmentPolicyVersion.objects.filter(
        company=company,
        published_at__isnull=False,
        retired_at__isnull=True,
    ).count()

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
            "published_policy_count": policy_count,
            "asset_count": assets.count(),
            "active_asset_count": active_asset_count,
            "deployed_asset_count": deployed_asset_count,
            "utilization_percent": utilization_percent,
            "service_due_count": service_due.count(),
            "service_overdue_count": service_due.filter(
                Q(next_service_on__lt=today)
                | Q(next_service_meter__lte=F("current_meter_value"))
            ).count(),
            "compliance_watch_count": compliance_watch.count(),
            "compliance_expired_count": compliance_watch.filter(
                compliance_due_on__lt=today
            ).count(),
            "open_work_order_count": open_orders.count(),
            "pending_approval_count": pending_approvals.count(),
            "open_risk_count": open_risks.count(),
            "estimated_maintenance_cost": _money(company_cost),
            "currency": company.currency,
            "estimated_cost_by_currency": cost_by_currency,
        },
        "recent_assets": recent_assets,
        "active_deployments": deployment_items,
        "service_due": service_items,
        "compliance_watch": compliance_items,
        "open_work_orders": work_order_items,
        "pending_approvals": approval_items,
        "open_risks": risk_items,
        "risk_severity": risk_severity,
        "governance": {
            "workflow_source": "versioned_policy",
            "asset_categories_hardcoded": False,
            "ownership_models_hardcoded": False,
            "cross_tenant_deployments_allowed": False,
            "inspection_evidence_exposed": False,
            "meter_evidence_exposed": False,
            "maker_checker_supported": True,
            "project_adapter_boundary": "public_id_reference",
            "maintenance_provider_boundary": "provider_neutral",
        },
    }

