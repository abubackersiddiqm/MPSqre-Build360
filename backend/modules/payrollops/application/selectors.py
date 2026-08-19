from __future__ import annotations

from collections import Counter
from typing import Any

from django.db.models import Q
from django.utils import timezone

from modules.payrollops.models import (
    PayrollApproval,
    PayrollException,
    PayrollPeriod,
    PayrollPolicyVersion,
    PayrollRun,
)
from modules.tenant.models import Company


def _run_payload(run: PayrollRun) -> dict[str, Any]:
    return {
        "public_id": str(run.public_id),
        "period_public_id": str(run.period.public_id),
        "period_code": run.period.code,
        "policy_public_id": str(run.policy.public_id),
        "policy_code": run.policy.code,
        "policy_version": run.policy.version,
        "run_number": run.run_number,
        "run_type_code": run.run_type_code,
        "status_code": run.status_code,
        "currency": run.currency,
        "version": run.version,
        "gross_amount": str(run.gross_amount),
        "deduction_amount": str(run.deduction_amount),
        "employer_cost_amount": str(run.employer_cost_amount),
        "net_amount": str(run.net_amount),
        "employee_count": run.employee_count,
        "exception_count": run.exception_count,
        "calculated_at": run.calculated_at.isoformat() if run.calculated_at else None,
        "approved_at": run.approved_at.isoformat() if run.approved_at else None,
        "locked_at": run.locked_at.isoformat() if run.locked_at else None,
        "created_at": run.created_at.isoformat(),
        "updated_at": run.updated_at.isoformat(),
    }


def payroll_overview(company: Company) -> dict[str, Any]:
    now = timezone.now()
    policies = list(
        PayrollPolicyVersion.objects.filter(
            company=company,
            published_at__isnull=False,
            published_at__lte=now,
            retired_at__isnull=True,
            effective_from__lte=now,
        )
        .filter(Q(effective_to__isnull=True) | Q(effective_to__gt=now))
        .order_by("code", "-version")
    )
    periods = list(
        PayrollPeriod.objects.filter(company=company)
        .order_by("-ends_on", "-created_at")[:12]
    )
    runs = list(
        PayrollRun.objects.filter(company=company)
        .select_related("period", "policy")
        .order_by("-created_at")[:12]
    )
    latest_run = runs[0] if runs else None
    open_exceptions = list(
        PayrollException.objects.filter(
            company=company,
            resolved_at__isnull=True,
        )
        .select_related("run", "run__period")
        .order_by("due_at", "-created_at")[:10]
    )
    pending_approvals = list(
        PayrollApproval.objects.filter(
            company=company,
            decided_at__isnull=True,
        )
        .select_related("run", "run__period")
        .order_by("due_at", "requested_at")[:10]
    )
    severity_counts = Counter(item.severity_code for item in open_exceptions)
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
            "period_count": PayrollPeriod.objects.filter(company=company).count(),
            "run_count": PayrollRun.objects.filter(company=company).count(),
            "open_exception_count": PayrollException.objects.filter(
                company=company,
                resolved_at__isnull=True,
            ).count(),
            "pending_approval_count": PayrollApproval.objects.filter(
                company=company,
                decided_at__isnull=True,
            ).count(),
            "latest_employee_count": latest_run.employee_count if latest_run else 0,
            "latest_net_amount": str(latest_run.net_amount) if latest_run else "0.00",
            "latest_currency": latest_run.currency if latest_run else company.currency,
        },
        "policies": [
            {
                "public_id": str(policy.public_id),
                "code": policy.code,
                "name": policy.name,
                "version": policy.version,
                "status_code": policy.status_code,
                "locale_code": policy.locale_code,
                "currency": policy.currency,
                "effective_from": policy.effective_from.isoformat(),
                "effective_to": (
                    policy.effective_to.isoformat() if policy.effective_to else None
                ),
                "published_at": policy.published_at.isoformat(),
            }
            for policy in policies
        ],
        "periods": [
            {
                "public_id": str(period.public_id),
                "code": period.code,
                "starts_on": period.starts_on.isoformat(),
                "ends_on": period.ends_on.isoformat(),
                "payment_due_on": period.payment_due_on.isoformat(),
                "status_code": period.status_code,
                "lock_version": period.lock_version,
            }
            for period in periods
        ],
        "latest_run": _run_payload(latest_run) if latest_run else None,
        "recent_runs": [_run_payload(run) for run in runs],
        "open_exceptions": [
            {
                "public_id": str(item.public_id),
                "run_public_id": str(item.run.public_id),
                "period_code": item.run.period.code,
                "employee_public_id": (
                    str(item.employee_public_id) if item.employee_public_id else None
                ),
                "exception_code": item.exception_code,
                "severity_code": item.severity_code,
                "status_code": item.status_code,
                "message": item.message,
                "due_at": item.due_at.isoformat() if item.due_at else None,
                "created_at": item.created_at.isoformat(),
            }
            for item in open_exceptions
        ],
        "pending_approvals": [
            {
                "public_id": str(item.public_id),
                "run_public_id": str(item.run.public_id),
                "period_code": item.run.period.code,
                "step_code": item.step_code,
                "status_code": item.status_code,
                "requested_from_membership_public_id": str(
                    item.requested_from_membership_public_id
                ),
                "requested_at": item.requested_at.isoformat(),
                "due_at": item.due_at.isoformat() if item.due_at else None,
            }
            for item in pending_approvals
        ],
        "exception_severity": [
            {"severity_code": code, "count": count}
            for code, count in sorted(severity_counts.items())
        ],
        "governance": {
            "workflow_source": "versioned_policy_configuration",
            "statutory_formulae_hardcoded": False,
            "locked_runs_mutable": False,
            "raw_bank_data_exposed": False,
            "maker_checker_supported": True,
        },
    }
