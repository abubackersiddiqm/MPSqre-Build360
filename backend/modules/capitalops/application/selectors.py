from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.db.models import Count, DecimalField, Sum
from django.db.models.functions import Coalesce
from django.utils import timezone

from modules.capitalops.models import (
    CapitalCommitment,
    CapitalEvent,
    CapitalPolicyVersion,
    CovenantTest,
    DebtFacility,
    DrawdownRequest,
    FundingProgram,
    InvestorDistribution,
    InvestorProfile,
    JointVentureArrangement,
)
from modules.tenant.models import Company

MONEY = DecimalField(max_digits=24, decimal_places=2)
ZERO = Decimal("0.00")


def _money_by_currency(queryset, amount_fields: dict[str, str]):
    annotations = {
        alias: Coalesce(Sum(field), ZERO, output_field=MONEY)
        for alias, field in amount_fields.items()
    }
    return list(queryset.values("currency_code").annotate(**annotations).order_by("currency_code"))


def capital_overview(company: Company) -> dict:
    today = timezone.localdate()
    policy = CapitalPolicyVersion.objects.filter(company=company).order_by("-version").first()
    commitment_alert_days = policy.commitment_expiry_alert_days if policy else 45
    commitment_alert_on = today + timedelta(days=commitment_alert_days)

    programs_qs = FundingProgram.objects.filter(company=company)
    investors_qs = InvestorProfile.objects.filter(company=company)
    jvs_qs = JointVentureArrangement.objects.filter(company=company)
    commitments_qs = CapitalCommitment.objects.filter(company=company)
    facilities_qs = DebtFacility.objects.filter(company=company)
    drawdowns_qs = DrawdownRequest.objects.filter(company=company)
    covenants_qs = CovenantTest.objects.filter(company=company)
    distributions_qs = InvestorDistribution.objects.filter(company=company)
    events_qs = CapitalEvent.objects.filter(company=company)

    program_rows = list(
        programs_qs.order_by("-updated_at").values(
            "public_id", "program_code", "name", "program_type_code", "project_public_id",
            "land_opportunity_public_id", "status_code", "currency_code", "target_capital",
            "target_equity", "target_debt", "sponsor_public_id", "start_on", "target_close_on", "version",
        )[:100]
    )
    investor_rows = list(
        investors_qs.order_by("legal_name").values(
            "public_id", "investor_code", "legal_name", "investor_type_code", "jurisdiction_code",
            "kyc_status_code", "risk_rating_code", "accredited_flag", "version",
        )[:150]
    )
    jv_rows = list(
        jvs_qs.select_related("program").order_by("-updated_at").values(
            "public_id", "program__program_code", "venture_code", "partner_name", "ownership_percent",
            "profit_share_percent", "status_code", "version",
        )[:150]
    )
    commitment_rows = list(
        commitments_qs.select_related("program", "investor", "joint_venture").order_by("-committed_on").values(
            "public_id", "program__program_code", "investor__legal_name", "joint_venture__partner_name",
            "commitment_number", "commitment_type_code", "committed_amount", "called_amount", "funded_amount",
            "currency_code", "committed_on", "expiry_on", "status_code", "version",
        )[:200]
    )
    facility_rows = list(
        facilities_qs.select_related("program").order_by("-updated_at").values(
            "public_id", "program__program_code", "facility_code", "lender_name", "facility_type_code",
            "principal_limit", "currency_code", "interest_rate_percent", "tenor_months", "maturity_on",
            "status_code", "version",
        )[:150]
    )
    drawdown_rows = list(
        drawdowns_qs.select_related("program", "debt_facility", "commitment").order_by("-requested_on").values(
            "public_id", "program__program_code", "debt_facility__facility_code", "commitment__commitment_number",
            "request_number", "request_type_code", "amount", "currency_code", "requested_on", "required_by",
            "status_code", "disbursed_on", "disbursement_reference", "version",
        )[:200]
    )
    covenant_rows = list(
        covenants_qs.select_related("debt_facility").order_by("-tested_on").values(
            "public_id", "debt_facility__facility_code", "test_number", "covenant_code", "tested_on",
            "metric_value", "threshold_operator", "threshold_value", "compliant", "status_code", "version",
        )[:200]
    )
    distribution_rows = list(
        distributions_qs.select_related("program", "investor", "joint_venture").order_by("-declared_on").values(
            "public_id", "program__program_code", "investor__legal_name", "joint_venture__partner_name",
            "distribution_number", "distribution_type_code", "amount", "currency_code", "declared_on",
            "payable_on", "paid_on", "payment_reference", "status_code", "version",
        )[:200]
    )
    event_rows = list(
        events_qs.select_related("program").order_by("-event_on").values(
            "public_id", "program__program_code", "event_type_code", "event_on", "summary", "evidence",
        )[:200]
    )

    return {
        "company": {
            "name": company.display_name,
            "code": company.code,
            "timezone": company.timezone,
            "currency": company.currency,
        },
        "policy": {
            "status": policy.status_code if policy else "DRAFT",
            "version": policy.version if policy else 1,
            "covenant_alert_days": policy.covenant_alert_days if policy else 30,
            "commitment_expiry_alert_days": policy.commitment_expiry_alert_days if policy else 45,
            "maximum_leverage_percent": str(policy.maximum_leverage_percent if policy else Decimal("70.0000")),
        },
        "metrics": {
            "active_programs": programs_qs.filter(status_code__in=["APPROVED", "ACTIVE", "SUSPENDED"]).count(),
            "verified_investors": investors_qs.filter(kyc_status_code="VERIFIED").count(),
            "active_joint_ventures": jvs_qs.filter(status_code__in=["APPROVED", "ACTIVE"]).count(),
            "pending_commitments": commitments_qs.filter(status_code__in=["DRAFT", "SUBMITTED", "APPROVED"]).count(),
            "pending_drawdowns": drawdowns_qs.filter(status_code__in=["DRAFT", "SUBMITTED", "APPROVED"]).count(),
            "covenant_breaches": covenants_qs.filter(compliant=False).exclude(status_code="CLOSED").count(),
            "pending_distributions": distributions_qs.filter(status_code__in=["DRAFT", "SUBMITTED", "APPROVED"]).count(),
            "expiring_commitments": commitments_qs.filter(expiry_on__isnull=False, expiry_on__gte=today, expiry_on__lte=commitment_alert_on).exclude(status_code__in=["CLOSED", "CANCELLED"]).count(),
        },
        "programs": program_rows,
        "investors": investor_rows,
        "joint_ventures": jv_rows,
        "commitments": commitment_rows,
        "facilities": facility_rows,
        "drawdowns": drawdown_rows,
        "covenants": covenant_rows,
        "distributions": distribution_rows,
        "events": event_rows,
        "portfolio": {
            "program_status": list(programs_qs.values("status_code").annotate(count=Count("id")).order_by("status_code")),
            "investor_kyc": list(investors_qs.values("kyc_status_code").annotate(count=Count("id")).order_by("kyc_status_code")),
            "capital_by_currency": _money_by_currency(
                programs_qs,
                {"target_capital": "target_capital", "target_equity": "target_equity", "target_debt": "target_debt"},
            ),
            "commitments_by_currency": _money_by_currency(
                commitments_qs.exclude(status_code__in=["REJECTED", "CANCELLED"]),
                {"committed_amount": "committed_amount", "called_amount": "called_amount", "funded_amount": "funded_amount"},
            ),
            "debt_by_currency": _money_by_currency(
                facilities_qs.exclude(status_code__in=["REJECTED", "CANCELLED"]),
                {"principal_limit": "principal_limit"},
            ),
            "drawdowns_by_currency": _money_by_currency(
                drawdowns_qs.filter(status_code__in=["APPROVED", "DISBURSED", "SETTLED"]),
                {"drawn_amount": "amount"},
            ),
            "distributions_by_currency": _money_by_currency(
                distributions_qs.filter(status_code__in=["APPROVED", "PAID", "CLOSED"]),
                {"distribution_amount": "amount"},
            ),
        },
    }
