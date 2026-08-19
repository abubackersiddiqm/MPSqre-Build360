from __future__ import annotations

from collections import Counter, defaultdict
from datetime import timedelta
from decimal import Decimal
from typing import Any

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
from modules.tenant.models import Company

ZERO = Decimal("0")


def _iso(value: Any) -> str | None:
    return value.isoformat() if value is not None else None


def _money(value: Decimal | None) -> str:
    return str(value if value is not None else ZERO)


def _company_value(company: Company, *names: str, default: str = "") -> str:
    for name in names:
        value = getattr(company, name, None)
        if value is not None:
            return str(value)
    return default


def _policy_codes(company: Company, key: str) -> list[str]:
    now = timezone.now()
    configurations = (
        CommercialPolicyVersion.objects.filter(
            company=company,
            published_at__isnull=False,
            published_at__lte=now,
            retired_at__isnull=True,
            effective_from__lte=now,
        )
        .filter(Q(effective_to__isnull=True) | Q(effective_to__gt=now))
        .values_list("configuration", flat=True)
    )
    values: set[str] = set()
    for configuration in configurations:
        configured = configuration.get(key, []) if isinstance(configuration, dict) else []
        if isinstance(configured, list):
            values.update(
                str(item).strip().upper()
                for item in configured
                if isinstance(item, str) and item.strip()
            )
    return sorted(values)


def commercial_overview(company: Company) -> dict[str, Any]:
    now = timezone.now()
    date_today = timezone.localdate()
    decision_horizon = now + timedelta(days=7)
    completion_horizon = date_today + timedelta(days=45)

    policies = CommercialPolicyVersion.objects.filter(company=company)
    contracts = CommercialContract.objects.filter(company=company).select_related("policy")
    milestones = ContractMilestone.objects.filter(company=company).select_related(
        "policy", "contract"
    )
    variations = VariationOrder.objects.filter(company=company).select_related(
        "policy", "contract"
    )
    payments = PaymentApplication.objects.filter(company=company).select_related(
        "policy", "contract"
    )
    claims = CommercialClaim.objects.filter(company=company).select_related(
        "policy", "contract"
    )
    eot_requests = ExtensionOfTime.objects.filter(company=company).select_related(
        "policy", "contract", "claim"
    )
    approvals = CommercialApproval.objects.filter(company=company).select_related("policy")
    risks = CommercialRisk.objects.filter(company=company).select_related(
        "policy", "contract"
    )

    active_contract_statuses = _policy_codes(company, "active_contract_statuses")
    open_milestone_statuses = _policy_codes(company, "open_milestone_statuses")
    open_variation_statuses = _policy_codes(company, "open_variation_statuses")
    open_payment_statuses = _policy_codes(company, "open_payment_statuses")
    open_claim_statuses = _policy_codes(company, "open_claim_statuses")
    open_eot_statuses = _policy_codes(company, "open_eot_statuses")
    critical_claim_priorities = _policy_codes(company, "critical_claim_priority_codes")
    critical_risk_severities = _policy_codes(company, "critical_risk_severity_codes")

    active_contracts = contracts.filter(status_code__in=active_contract_statuses)
    upcoming_contracts = active_contracts.filter(
        planned_completion_date__lte=completion_horizon,
        actual_completion_date__isnull=True,
    )
    open_milestones = milestones.filter(status_code__in=open_milestone_statuses)
    overdue_milestones = open_milestones.filter(due_date__lt=date_today)
    open_variations = variations.filter(status_code__in=open_variation_statuses)
    variation_due = open_variations.filter(decision_due_at__lte=decision_horizon)
    overdue_variations = open_variations.filter(decision_due_at__lt=now)
    open_payments = payments.filter(status_code__in=open_payment_statuses)
    payment_due = open_payments.filter(certification_due_at__lte=decision_horizon)
    overdue_payments = open_payments.filter(certification_due_at__lt=now)
    open_claims = claims.filter(status_code__in=open_claim_statuses)
    overdue_claims = open_claims.filter(response_due_at__lt=now)
    critical_claims = open_claims.filter(priority_code__in=critical_claim_priorities)
    open_eots = eot_requests.filter(status_code__in=open_eot_statuses)
    overdue_eots = open_eots.filter(decision_due_at__lt=now)
    pending_approvals = approvals.filter(decided_at__isnull=True)
    overdue_approvals = pending_approvals.filter(due_at__lt=now)
    open_risks = risks.filter(resolved_at__isnull=True)
    critical_risks = open_risks.filter(severity_code__in=critical_risk_severities)

    exposure: dict[str, dict[str, Decimal]] = defaultdict(
        lambda: {
            "contract_value": ZERO,
            "pending_variations": ZERO,
            "uncertified_payments": ZERO,
            "open_claims": ZERO,
        }
    )
    # These querysets inherit select_related() from the overview register queries.
    # Using only() here would defer the selected relation fields and Django raises:
    # "Field ... cannot be both deferred and traversed using select_related".
    # values_list() keeps the exposure aggregation projection-only and avoids that
    # runtime failure even when the tenant has no commercial records.
    for currency_code, current_contract_value in active_contracts.values_list(
        "currency_code", "current_contract_value"
    ):
        exposure[currency_code]["contract_value"] += current_contract_value
    for currency_code, submitted_value in open_variations.values_list(
        "currency_code", "submitted_value"
    ):
        exposure[currency_code]["pending_variations"] += submitted_value
    for currency_code, gross_claimed, certified_amount in open_payments.values_list(
        "currency_code", "gross_claimed", "certified_amount"
    ):
        exposure[currency_code]["uncertified_payments"] += (
            gross_claimed - (certified_amount or ZERO)
        )
    for currency_code, claimed_amount, assessed_amount in open_claims.values_list(
        "currency_code", "claimed_amount", "assessed_amount"
    ):
        exposure[currency_code]["open_claims"] += (
            claimed_amount - (assessed_amount or ZERO)
        )

    contract_items = [
        {
            "public_id": str(item.public_id),
            "contract_number": item.contract_number,
            "title": item.title,
            "counterparty_name": item.counterparty_name,
            "contract_type_code": item.contract_type_code,
            "status_code": item.status_code,
            "currency_code": item.currency_code,
            "current_contract_value": _money(item.current_contract_value),
            "planned_completion_date": item.planned_completion_date.isoformat(),
            "completion_due": item.planned_completion_date <= completion_horizon,
            "version": item.version,
        }
        for item in active_contracts.order_by(
            "planned_completion_date", "contract_number"
        )[:12]
    ]

    milestone_items = [
        {
            "public_id": str(item.public_id),
            "contract_number": item.contract.contract_number,
            "milestone_number": item.milestone_number,
            "title": item.title,
            "status_code": item.status_code,
            "due_date": item.due_date.isoformat(),
            "currency_code": item.currency_code,
            "milestone_value": _money(item.milestone_value),
            "overdue": item.due_date < date_today,
            "version": item.version,
        }
        for item in open_milestones.order_by("due_date", "milestone_number")[:12]
    ]

    variation_items = [
        {
            "public_id": str(item.public_id),
            "contract_number": item.contract.contract_number,
            "variation_number": item.variation_number,
            "title": item.title,
            "reason_code": item.reason_code,
            "status_code": item.status_code,
            "currency_code": item.currency_code,
            "submitted_value": _money(item.submitted_value),
            "approved_value": _money(item.approved_value),
            "time_impact_days": item.time_impact_days,
            "decision_due_at": _iso(item.decision_due_at),
            "overdue": bool(item.decision_due_at and item.decision_due_at < now),
            "version": item.version,
        }
        for item in variation_due.order_by("decision_due_at", "variation_number")[:12]
    ]

    payment_items = [
        {
            "public_id": str(item.public_id),
            "contract_number": item.contract.contract_number,
            "application_number": item.application_number,
            "status_code": item.status_code,
            "currency_code": item.currency_code,
            "gross_claimed": _money(item.gross_claimed),
            "certified_amount": _money(item.certified_amount),
            "net_payable": _money(item.net_payable),
            "certification_due_at": _iso(item.certification_due_at),
            "overdue": bool(
                item.certification_due_at and item.certification_due_at < now
            ),
            "version": item.version,
        }
        for item in payment_due.order_by(
            "certification_due_at", "application_number"
        )[:12]
    ]

    claim_items = [
        {
            "public_id": str(item.public_id),
            "contract_number": item.contract.contract_number,
            "claim_number": item.claim_number,
            "claim_type_code": item.claim_type_code,
            "priority_code": item.priority_code,
            "title": item.title,
            "status_code": item.status_code,
            "currency_code": item.currency_code,
            "claimed_amount": _money(item.claimed_amount),
            "assessed_amount": _money(item.assessed_amount),
            "response_due_at": _iso(item.response_due_at),
            "overdue": bool(item.response_due_at and item.response_due_at < now),
            "version": item.version,
        }
        for item in open_claims.order_by("response_due_at", "claim_number")[:12]
    ]

    eot_items = [
        {
            "public_id": str(item.public_id),
            "contract_number": item.contract.contract_number,
            "claim_number": item.claim.claim_number if item.claim else "",
            "eot_number": item.eot_number,
            "reason_code": item.reason_code,
            "status_code": item.status_code,
            "requested_days": item.requested_days,
            "assessed_days": item.assessed_days,
            "approved_days": item.approved_days,
            "decision_due_at": _iso(item.decision_due_at),
            "overdue": bool(item.decision_due_at and item.decision_due_at < now),
            "version": item.version,
        }
        for item in open_eots.order_by("decision_due_at", "eot_number")[:12]
    ]

    approval_items = [
        {
            "public_id": str(item.public_id),
            "entity_type_code": item.entity_type_code,
            "entity_public_id": str(item.entity_public_id),
            "step_code": item.step_code,
            "status_code": item.status_code,
            "requested_at": _iso(item.requested_at),
            "due_at": _iso(item.due_at),
            "overdue": bool(item.due_at and item.due_at < now),
            "version": item.version,
        }
        for item in pending_approvals.order_by("due_at", "requested_at")[:12]
    ]

    risk_items = [
        {
            "public_id": str(item.public_id),
            "contract_number": item.contract.contract_number if item.contract else "",
            "linked_entity_type_code": item.linked_entity_type_code,
            "risk_code": item.risk_code,
            "severity_code": item.severity_code,
            "status_code": item.status_code,
            "message": item.message,
            "due_at": _iso(item.due_at),
            "overdue": bool(item.due_at and item.due_at < now),
            "version": item.version,
        }
        for item in open_risks.order_by("due_at", "-created_at")[:12]
    ]

    return {
        "generated_at": now.isoformat(),
        "company": {
            "public_id": str(company.public_id),
            "display_name": company.display_name,
            "locale": _company_value(company, "default_locale", "locale", default="en-IN"),
            "timezone": _company_value(company, "default_timezone", "timezone", default="UTC"),
            "currency": _company_value(company, "default_currency", "currency", default="USD"),
            "unit_system_code": _company_value(company, "unit_system_code", default="metric"),
        },
        "summary": {
            "published_policy_count": policies.filter(
                published_at__isnull=False, retired_at__isnull=True
            ).count(),
            "active_contract_count": active_contracts.count(),
            "completion_due_count": upcoming_contracts.count(),
            "open_milestone_count": open_milestones.count(),
            "overdue_milestone_count": overdue_milestones.count(),
            "open_variation_count": open_variations.count(),
            "overdue_variation_count": overdue_variations.count(),
            "open_payment_count": open_payments.count(),
            "overdue_payment_count": overdue_payments.count(),
            "open_claim_count": open_claims.count(),
            "overdue_claim_count": overdue_claims.count(),
            "critical_claim_count": critical_claims.count(),
            "open_eot_count": open_eots.count(),
            "overdue_eot_count": overdue_eots.count(),
            "pending_approval_count": pending_approvals.count(),
            "overdue_approval_count": overdue_approvals.count(),
            "open_risk_count": open_risks.count(),
            "critical_risk_count": critical_risks.count(),
        },
        "active_contracts": contract_items,
        "milestone_queue": milestone_items,
        "variation_queue": variation_items,
        "payment_queue": payment_items,
        "open_claims": claim_items,
        "eot_queue": eot_items,
        "pending_approvals": approval_items,
        "open_risks": risk_items,
        "financial_exposure": [
            {
                "currency_code": currency,
                "contract_value": _money(values["contract_value"]),
                "pending_variations": _money(values["pending_variations"]),
                "uncertified_payments": _money(values["uncertified_payments"]),
                "open_claims": _money(values["open_claims"]),
            }
            for currency, values in sorted(exposure.items())
        ],
        "contract_types": [
            {"contract_type_code": code, "count": count}
            for code, count in Counter(
                active_contracts.values_list("contract_type_code", flat=True)
            ).most_common()
        ],
        "claim_priorities": [
            {"priority_code": code, "count": count}
            for code, count in Counter(
                open_claims.values_list("priority_code", flat=True)
            ).most_common()
        ],
        "risk_severity": [
            {"severity_code": code, "count": count}
            for code, count in Counter(
                open_risks.values_list("severity_code", flat=True)
            ).most_common()
        ],
        "governance": {
            "workflow_source": "tenant_commercial_policy",
            "contract_types_hardcoded": False,
            "variation_reasons_hardcoded": False,
            "claim_types_hardcoded": False,
            "payment_certification_hardcoded": False,
            "currencies_aggregated_together": False,
            "cross_tenant_records_allowed": False,
            "maker_checker_supported": True,
            "project_adapter_boundary": "project_public_id",
            "party_adapter_boundary": "counterparty_public_id",
            "accounting_adapter_boundary": "payment_application_public_id",
            "snapshot_date": date_today.isoformat(),
        },
    }
