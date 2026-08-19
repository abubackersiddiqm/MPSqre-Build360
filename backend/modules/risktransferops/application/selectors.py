from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.db.models import Count, DecimalField, Sum
from django.db.models.functions import Coalesce
from django.utils import timezone

from modules.risktransferops.models import (
    GuaranteeInstrument,
    InstrumentCall,
    InsuranceClaim,
    InsuranceCoverage,
    InsuranceProgram,
    LossEvent,
    PremiumSchedule,
    RiskCounterparty,
    RiskTransferEvent,
    RiskTransferPolicyVersion,
)
from modules.tenant.models import Company

MONEY = DecimalField(max_digits=24, decimal_places=2)
ZERO = Decimal("0.00")


def _money_by_currency(queryset, fields: dict[str, str]):
    annotations = {alias: Coalesce(Sum(field), ZERO, output_field=MONEY) for alias, field in fields.items()}
    return list(queryset.values("currency_code").annotate(**annotations).order_by("currency_code"))


def risk_transfer_overview(company: Company) -> dict:
    today = timezone.localdate()
    policy = RiskTransferPolicyVersion.objects.filter(company=company).order_by("-version").first()
    alert_days = policy.expiry_alert_days if policy else 45
    alert_on = today + timedelta(days=alert_days)

    programs = InsuranceProgram.objects.filter(company=company)
    parties = RiskCounterparty.objects.filter(company=company)
    coverages = InsuranceCoverage.objects.filter(company=company)
    premiums = PremiumSchedule.objects.filter(company=company)
    losses = LossEvent.objects.filter(company=company)
    claims = InsuranceClaim.objects.filter(company=company)
    instruments = GuaranteeInstrument.objects.filter(company=company)
    calls = InstrumentCall.objects.filter(company=company)
    events = RiskTransferEvent.objects.filter(company=company)

    program_rows = list(programs.order_by("-updated_at").values("public_id", "program_code", "name", "program_type_code", "project_public_id", "contract_public_id", "status_code", "currency_code", "aggregate_exposure", "starts_on", "ends_on", "version")[:100])
    party_rows = list(parties.order_by("legal_name").values("public_id", "counterparty_code", "legal_name", "counterparty_type_code", "jurisdiction_code", "financial_rating_code", "status_code", "version")[:150])
    coverage_rows = list(coverages.select_related("program", "counterparty").order_by("-ends_on").values("public_id", "program__program_code", "counterparty__legal_name", "policy_number", "coverage_type_code", "coverage_limit", "deductible_amount", "annual_premium", "currency_code", "starts_on", "ends_on", "status_code", "version")[:200])
    premium_rows = list(premiums.select_related("coverage").order_by("due_on").values("public_id", "coverage__policy_number", "installment_number", "due_on", "amount", "paid_amount", "currency_code", "status_code", "payment_reference", "version")[:200])
    loss_rows = list(losses.select_related("program").order_by("-reported_on").values("public_id", "program__program_code", "loss_number", "occurrence_on", "reported_on", "loss_type_code", "description", "estimated_loss", "currency_code", "severity_code", "status_code", "version")[:200])
    claim_rows = list(claims.select_related("loss_event", "coverage").order_by("-notified_on").values("public_id", "loss_event__loss_number", "coverage__policy_number", "claim_number", "notified_on", "claimed_amount", "reserved_amount", "recovered_amount", "currency_code", "status_code", "adjuster_reference", "settlement_reference", "version")[:200])
    instrument_rows = list(instruments.select_related("program", "counterparty").order_by("expiry_on").values("public_id", "program__program_code", "counterparty__legal_name", "instrument_number", "instrument_type_code", "beneficiary_name", "applicant_name", "amount", "currency_code", "issued_on", "expiry_on", "auto_renew_flag", "status_code", "version")[:200])
    call_rows = list(calls.select_related("instrument").order_by("-called_on").values("public_id", "instrument__instrument_number", "call_number", "called_on", "amount", "currency_code", "reason", "status_code", "settlement_reference", "version")[:200])
    event_rows = list(events.select_related("program").order_by("-event_on").values("public_id", "program__program_code", "event_type_code", "event_on", "summary", "evidence")[:200])

    active_coverage = coverages.filter(status_code__in=["APPROVED", "ACTIVE", "SUSPENDED"])
    coverage_by_program = {
        row["program_id"]: row["total"]
        for row in active_coverage.values("program_id").annotate(
            total=Coalesce(Sum("coverage_limit"), ZERO, output_field=MONEY)
        )
    }
    minimum_percent = policy.minimum_coverage_percent if policy else Decimal("100.0000")
    underinsured_program_ids = [
        program_id
        for program_id, aggregate_exposure in programs.filter(
            status_code__in=["APPROVED", "ACTIVE", "SUSPENDED"],
            aggregate_exposure__gt=0,
        ).values_list("id", "aggregate_exposure")
        if coverage_by_program.get(program_id, ZERO) * Decimal("100")
        < aggregate_exposure * minimum_percent
    ]

    return {
        "company": {"name": company.display_name, "code": company.code, "timezone": company.timezone, "currency": company.currency},
        "policy": {
            "status": policy.status_code if policy else "DRAFT",
            "version": policy.version if policy else 1,
            "expiry_alert_days": alert_days,
            "claim_notification_sla_days": policy.claim_notification_sla_days if policy else 7,
            "minimum_coverage_percent": str(minimum_percent),
        },
        "metrics": {
            "active_programs": programs.filter(status_code__in=["APPROVED", "ACTIVE", "SUSPENDED"]).count(),
            "verified_counterparties": parties.filter(status_code="VERIFIED").count(),
            "active_coverages": active_coverage.count(),
            "expiring_coverages": active_coverage.filter(ends_on__gte=today, ends_on__lte=alert_on).count(),
            "unpaid_premiums": premiums.filter(status_code__in=["DUE", "PARTIALLY_PAID"]).count(),
            "open_losses": losses.exclude(status_code="CLOSED").count(),
            "open_claims": claims.exclude(status_code__in=["CLOSED", "CANCELLED", "REJECTED"]).count(),
            "expiring_instruments": instruments.filter(expiry_on__gte=today, expiry_on__lte=alert_on).exclude(status_code__in=["CLOSED", "CANCELLED", "RENEWED"]).count(),
            "open_calls": calls.exclude(status_code__in=["CLOSED", "CANCELLED", "REJECTED"]).count(),
            "coverage_gaps": len(underinsured_program_ids),
        },
        "programs": program_rows,
        "counterparties": party_rows,
        "coverages": coverage_rows,
        "premiums": premium_rows,
        "losses": loss_rows,
        "claims": claim_rows,
        "instruments": instrument_rows,
        "calls": call_rows,
        "events": event_rows,
        "portfolio": {
            "program_status": list(programs.values("status_code").annotate(count=Count("id")).order_by("status_code")),
            "counterparty_status": list(parties.values("status_code").annotate(count=Count("id")).order_by("status_code")),
            "coverage_by_currency": _money_by_currency(active_coverage, {"coverage_limit": "coverage_limit", "annual_premium": "annual_premium"}),
            "losses_by_currency": _money_by_currency(losses, {"estimated_loss": "estimated_loss"}),
            "claims_by_currency": _money_by_currency(claims, {"claimed_amount": "claimed_amount", "reserved_amount": "reserved_amount", "recovered_amount": "recovered_amount"}),
            "instruments_by_currency": _money_by_currency(instruments.exclude(status_code__in=["CLOSED", "CANCELLED"]), {"instrument_amount": "amount"}),
            "calls_by_currency": _money_by_currency(calls.exclude(status_code__in=["REJECTED", "CANCELLED"]), {"called_amount": "amount"}),
        },
    }
