from __future__ import annotations

from decimal import Decimal

from django.db.models import Sum

from modules.goliveops.models import (
    CutoverPlan,
    CutoverTask,
    GoLiveGate,
    GoLivePolicyVersion,
    GoLiveWave,
    HypercareIssue,
    MigrationBatch,
    MigrationIssue,
    TrainingCohort,
    TrainingEnrollment,
)
from modules.tenant.models import Company


def _percent(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round((numerator / denominator) * 100, 1)


def _company_payload(company: Company) -> dict[str, str]:
    return {
        "name": getattr(company, "display_name", "") or getattr(company, "legal_name", ""),
        "code": company.code,
        "timezone": company.timezone,
        "currency": company.currency,
    }


def go_live_overview(company: Company) -> dict[str, object]:
    policy = GoLivePolicyVersion.objects.filter(company=company).order_by("-version").first()

    batches = MigrationBatch.objects.filter(company=company)
    issues = MigrationIssue.objects.filter(company=company)
    cohorts = TrainingCohort.objects.filter(company=company)
    enrollments = TrainingEnrollment.objects.filter(company=company)
    plans = CutoverPlan.objects.filter(company=company)
    tasks = CutoverTask.objects.filter(company=company)
    waves = GoLiveWave.objects.filter(company=company)
    hypercare = HypercareIssue.objects.filter(company=company)
    gates = GoLiveGate.objects.filter(company=company)

    row_totals = batches.aggregate(total=Sum("total_rows"), valid=Sum("valid_rows"), invalid=Sum("invalid_rows"))
    total_rows = int(row_totals["total"] or 0)
    valid_rows = int(row_totals["valid"] or 0)
    invalid_rows = int(row_totals["invalid"] or 0)
    training_total = enrollments.count()
    training_completed = enrollments.filter(status_code__in=["COMPLETED", "WAIVED"]).count()
    required_gates = gates.filter(is_required=True)
    passed_gates = required_gates.filter(status_code="PASSED").count()
    required_gate_count = required_gates.count()

    latest_batches = list(
        batches.order_by("-created_at")[:20].values(
            "public_id", "code", "entity_code", "source_file_name", "status_code", "dry_run",
            "total_rows", "valid_rows", "invalid_rows", "warning_rows", "created_at", "completed_at", "version",
        )
    )
    latest_issues = list(
        issues.select_related("batch").order_by("resolved", "-severity_code", "-created_at")[:30].values(
            "public_id", "batch__code", "row_number", "field_name", "severity_code", "issue_code",
            "message", "resolved", "resolution_notes", "version",
        )
    )
    latest_cohorts = list(
        cohorts.order_by("-starts_at")[:20].values(
            "public_id", "code", "title", "audience_code", "delivery_mode_code", "required",
            "starts_at", "ends_at", "minimum_score_percent", "status_code", "facilitator_name", "version",
        )
    )
    latest_enrollments = list(
        enrollments.select_related("cohort").order_by("status_code", "participant_name")[:40].values(
            "public_id", "cohort__code", "participant_public_id", "participant_name", "participant_email",
            "status_code", "score_percent", "completed_at", "version",
        )
    )
    latest_plans = list(
        plans.order_by("-planned_go_live_at")[:20].values(
            "public_id", "code", "name", "environment_code", "status_code", "planned_start_at",
            "planned_go_live_at", "actual_go_live_at", "rollback_deadline_at", "version",
        )
    )
    latest_tasks = list(
        tasks.select_related("plan").order_by("plan__planned_go_live_at", "sequence")[:50].values(
            "public_id", "plan__code", "code", "title", "category_code", "sequence", "critical",
            "status_code", "due_at", "completed_at", "notes", "version",
        )
    )
    latest_waves = list(
        waves.select_related("plan").order_by("-planned_at")[:20].values(
            "public_id", "plan__code", "code", "name", "scope", "status_code", "planned_at",
            "activated_at", "closed_at", "version",
        )
    )
    latest_hypercare = list(
        hypercare.select_related("wave").order_by("status_code", "severity_code", "-reported_at")[:30].values(
            "public_id", "wave__code", "code", "title", "severity_code", "status_code", "area_code",
            "impact_summary", "resolution_summary", "reported_at", "resolved_at", "version",
        )
    )
    gate_payload = list(
        gates.order_by("category_code", "code").values(
            "public_id", "code", "name", "category_code", "description", "is_required", "status_code",
            "evidence", "notes", "decided_at", "version",
        )
    )

    policy_payload = {
        "status": policy.status_code if policy else "MISSING",
        "version": policy.version if policy else 0,
        "migration_error_tolerance_percent": str(policy.migration_error_tolerance_percent if policy else Decimal("0.00")),
        "minimum_training_completion_percent": str(policy.minimum_training_completion_percent if policy else Decimal("100.00")),
        "cutover_freeze_hours": policy.cutover_freeze_hours if policy else 24,
        "hypercare_days": policy.hypercare_days if policy else 14,
    }
    metrics = {
        "migration_batches": batches.count(),
        "migration_rows": total_rows,
        "migration_valid_rows": valid_rows,
        "migration_invalid_rows": invalid_rows,
        "migration_pass_percent": _percent(valid_rows, total_rows),
        "open_migration_issues": issues.filter(resolved=False).count(),
        "blocking_migration_issues": issues.filter(resolved=False, severity_code="BLOCKER").count(),
        "training_cohorts": cohorts.count(),
        "training_enrollments": training_total,
        "training_completed": training_completed,
        "training_completion_percent": _percent(training_completed, training_total),
        "open_cutover_tasks": tasks.exclude(status_code__in=["DONE", "SKIPPED"]).count(),
        "blocked_critical_tasks": tasks.filter(critical=True, status_code="BLOCKED").count(),
        "active_go_live_waves": waves.filter(status_code__in=["READY", "APPROVED", "LIVE", "HYPERCARE"]).count(),
        "open_hypercare_issues": hypercare.exclude(status_code="CLOSED").count(),
        "critical_hypercare_issues": hypercare.filter(status_code__in=["OPEN", "ACKNOWLEDGED", "MITIGATING"], severity_code__in=["P0", "P1"]).count(),
        "go_live_gates_passed": passed_gates,
        "go_live_gates_total": required_gate_count,
        "go_live_readiness_percent": _percent(passed_gates, required_gate_count),
    }
    return {
        "company": _company_payload(company),
        "policy": policy_payload,
        "metrics": metrics,
        "migration_batches": latest_batches,
        "migration_issues": latest_issues,
        "training_cohorts": latest_cohorts,
        "training_enrollments": latest_enrollments,
        "cutover_plans": latest_plans,
        "cutover_tasks": latest_tasks,
        "go_live_waves": latest_waves,
        "hypercare_issues": latest_hypercare,
        "gates": gate_payload,
    }
