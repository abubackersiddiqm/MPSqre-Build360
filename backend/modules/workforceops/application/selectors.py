from __future__ import annotations

from collections import Counter
from datetime import timedelta
from typing import Any

from django.db.models import F, Q, Sum
from django.utils import timezone

from modules.tenant.models import Company
from modules.workforceops.models import (
    EmployeeSkillCredential,
    WorkforceApproval,
    WorkforceDemand,
    WorkforcePlan,
    WorkforcePolicyVersion,
    WorkforceRisk,
)


def _plan_payload(plan: WorkforcePlan) -> dict[str, Any]:
    demands = list(plan.demands.all())
    required = sum(item.quantity_required for item in demands)
    filled = sum(item.quantity_filled for item in demands)
    return {
        "public_id": str(plan.public_id),
        "code": plan.code,
        "name": plan.name,
        "policy_code": plan.policy.code,
        "policy_version": plan.policy.version,
        "starts_on": plan.starts_on.isoformat(),
        "ends_on": plan.ends_on.isoformat(),
        "status_code": plan.status_code,
        "version": plan.version,
        "required_headcount": required,
        "filled_headcount": filled,
        "open_gap": max(required - filled, 0),
        "approved_at": plan.approved_at.isoformat() if plan.approved_at else None,
        "locked_at": plan.locked_at.isoformat() if plan.locked_at else None,
        "created_at": plan.created_at.isoformat(),
        "updated_at": plan.updated_at.isoformat(),
    }


def workforce_overview(company: Company) -> dict[str, Any]:
    now = timezone.now()
    today = timezone.localdate()
    credential_horizon = today + timedelta(days=60)
    policies = list(
        WorkforcePolicyVersion.objects.filter(
            company=company,
            published_at__isnull=False,
            published_at__lte=now,
            retired_at__isnull=True,
            effective_from__lte=now,
        )
        .filter(Q(effective_to__isnull=True) | Q(effective_to__gt=now))
        .order_by("code", "-version")
    )
    plans = list(
        WorkforcePlan.objects.filter(company=company)
        .select_related("policy")
        .prefetch_related("demands")
        .order_by("-created_at")[:12]
    )
    demands = WorkforceDemand.objects.filter(company=company)
    aggregate = demands.aggregate(
        required=Sum("quantity_required"),
        filled=Sum("quantity_filled"),
    )
    required = int(aggregate["required"] or 0)
    filled = int(aggregate["filled"] or 0)
    company_currency_cost = demands.filter(currency=company.currency).aggregate(
        total=Sum("estimated_cost")
    )["total"]
    cost_by_currency = list(
        demands.values("currency")
        .annotate(total=Sum("estimated_cost"))
        .order_by("currency")
    )
    gap_demands = list(
        demands.filter(quantity_filled__lt=F("quantity_required"))
        .select_related("plan")
        .order_by("priority_code", "starts_on", "created_at")[:12]
    )
    expiring_credentials = list(
        EmployeeSkillCredential.objects.filter(
            company=company,
            expires_on__isnull=False,
            expires_on__gte=today,
            expires_on__lte=credential_horizon,
        )
        .select_related("skill")
        .order_by("expires_on", "employee_public_id")[:12]
    )
    expired_credential_count = EmployeeSkillCredential.objects.filter(
        company=company,
        expires_on__lt=today,
    ).count()
    pending_approvals = list(
        WorkforceApproval.objects.filter(
            company=company,
            decided_at__isnull=True,
        )
        .select_related("plan")
        .order_by("due_at", "requested_at")[:10]
    )
    open_risks = list(
        WorkforceRisk.objects.filter(
            company=company,
            resolved_at__isnull=True,
        )
        .select_related("plan", "demand")
        .order_by("due_at", "-created_at")[:12]
    )
    severity_counts = Counter(item.severity_code for item in open_risks)
    return {
        "generated_at": now.isoformat(),
        "company": {
            "public_id": str(company.public_id),
            "code": company.code,
            "display_name": company.display_name,
            "locale": company.locale,
            "timezone": company.timezone,
            "currency": company.currency,
        },
        "summary": {
            "published_policy_count": len(policies),
            "plan_count": WorkforcePlan.objects.filter(company=company).count(),
            "active_plan_count": WorkforcePlan.objects.filter(
                company=company,
                locked_at__isnull=True,
                ends_on__gte=today,
            ).count(),
            "demand_count": demands.count(),
            "required_headcount": required,
            "filled_headcount": filled,
            "open_gap": max(required - filled, 0),
            "coverage_percent": (
                round((filled / required) * 100, 1) if required else 0.0
            ),
            "estimated_cost": str(company_currency_cost or "0.00"),
            "currency": company.currency,
            "estimated_cost_by_currency": [
                {"currency": item["currency"], "amount": str(item["total"] or "0.00")}
                for item in cost_by_currency
            ],
            "expiring_credential_count": EmployeeSkillCredential.objects.filter(
                company=company,
                expires_on__isnull=False,
                expires_on__gte=today,
                expires_on__lte=credential_horizon,
            ).count(),
            "expired_credential_count": expired_credential_count,
            "pending_approval_count": WorkforceApproval.objects.filter(
                company=company,
                decided_at__isnull=True,
            ).count(),
            "open_risk_count": WorkforceRisk.objects.filter(
                company=company,
                resolved_at__isnull=True,
            ).count(),
        },
        "policies": [
            {
                "public_id": str(policy.public_id),
                "code": policy.code,
                "name": policy.name,
                "version": policy.version,
                "status_code": policy.status_code,
                "effective_from": policy.effective_from.isoformat(),
                "effective_to": (
                    policy.effective_to.isoformat() if policy.effective_to else None
                ),
                "published_at": policy.published_at.isoformat(),
            }
            for policy in policies
        ],
        "recent_plans": [_plan_payload(plan) for plan in plans],
        "critical_gaps": [
            {
                "public_id": str(demand.public_id),
                "plan_public_id": str(demand.plan.public_id),
                "plan_code": demand.plan.code,
                "demand_code": demand.demand_code,
                "role_code": demand.role_code,
                "priority_code": demand.priority_code,
                "status_code": demand.status_code,
                "quantity_required": demand.quantity_required,
                "quantity_filled": demand.quantity_filled,
                "open_quantity": demand.open_quantity,
                "starts_on": demand.starts_on.isoformat(),
                "ends_on": demand.ends_on.isoformat(),
                "project_public_id": (
                    str(demand.project_public_id) if demand.project_public_id else None
                ),
                "location_public_id": (
                    str(demand.location_public_id) if demand.location_public_id else None
                ),
            }
            for demand in gap_demands
        ],
        "expiring_credentials": [
            {
                "public_id": str(credential.public_id),
                "employee_public_id": str(credential.employee_public_id),
                "skill_code": credential.skill.code,
                "skill_name": credential.skill.name,
                "proficiency_code": credential.proficiency_code,
                "verification_status_code": credential.verification_status_code,
                "expires_on": credential.expires_on.isoformat(),
            }
            for credential in expiring_credentials
        ],
        "pending_approvals": [
            {
                "public_id": str(approval.public_id),
                "plan_public_id": str(approval.plan.public_id),
                "plan_code": approval.plan.code,
                "step_code": approval.step_code,
                "status_code": approval.status_code,
                "requested_from_membership_public_id": str(
                    approval.requested_from_membership_public_id
                ),
                "requested_at": approval.requested_at.isoformat(),
                "due_at": approval.due_at.isoformat() if approval.due_at else None,
            }
            for approval in pending_approvals
        ],
        "open_risks": [
            {
                "public_id": str(risk.public_id),
                "plan_public_id": str(risk.plan.public_id) if risk.plan else None,
                "plan_code": risk.plan.code if risk.plan else None,
                "demand_public_id": (
                    str(risk.demand.public_id) if risk.demand else None
                ),
                "employee_public_id": (
                    str(risk.employee_public_id) if risk.employee_public_id else None
                ),
                "risk_code": risk.risk_code,
                "severity_code": risk.severity_code,
                "status_code": risk.status_code,
                "message": risk.message,
                "due_at": risk.due_at.isoformat() if risk.due_at else None,
                "created_at": risk.created_at.isoformat(),
            }
            for risk in open_risks
        ],
        "risk_severity": [
            {"severity_code": code, "count": count}
            for code, count in sorted(severity_counts.items())
        ],
        "governance": {
            "workflow_source": "versioned_policy_configuration",
            "role_codes_hardcoded": False,
            "skill_catalog_hardcoded": False,
            "cross_tenant_assignments_allowed": False,
            "credential_evidence_exposed": False,
            "maker_checker_supported": True,
            "project_adapter_boundary": "public_id_reference",
        },
    }
