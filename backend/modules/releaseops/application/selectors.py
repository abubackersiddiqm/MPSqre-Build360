from __future__ import annotations

from modules.releaseops.models import (
    BackupSnapshot,
    DeploymentTarget,
    ReadinessRun,
    ReleaseCandidate,
    UATScenario,
)
from modules.tenant.models import Company

RECENT_BACKUP_LIMIT = 50
RECENT_READINESS_RUN_LIMIT = 25
TARGET_LIMIT = 100


def release_overview(company: Company) -> dict[str, object]:
    """Build the Phase 33 overview without re-filtering sliced querysets.

    Querysets used for totals remain unsliced. Separate bounded querysets are
    materialized only for the recent-record collections returned to the UI.
    """

    release_queryset = ReleaseCandidate.objects.filter(company=company)
    current = (
        release_queryset.select_related("target")
        .prefetch_related("gates", "uat_executions__scenario")
        .order_by("-created_at")
        .first()
    )

    target_queryset = DeploymentTarget.objects.filter(company=company)
    targets = list(target_queryset.order_by("environment_code", "code")[:TARGET_LIMIT])

    scenarios = list(
        UATScenario.objects.filter(company=company, status_code="ACTIVE").order_by("code")
    )

    backup_queryset = BackupSnapshot.objects.filter(company=company)
    backups = list(
        backup_queryset.select_related("release", "target")
        .order_by("-captured_at")[:RECENT_BACKUP_LIMIT]
    )

    readiness_queryset = ReadinessRun.objects.filter(company=company)
    readiness_runs = list(
        readiness_queryset.select_related("release")
        .order_by("-started_at")[:RECENT_READINESS_RUN_LIMIT]
    )

    gate_rows: list[dict[str, object]] = []
    execution_by_scenario: dict[int, object] = {}
    if current is not None:
        gate_rows = [
            {
                "public_id": str(gate.public_id),
                "code": gate.code,
                "name": gate.name,
                "category": gate.category_code,
                "required": gate.is_required,
                "status": gate.status_code,
                "notes": gate.notes,
                "evidence": gate.evidence,
                "version": gate.version,
            }
            for gate in current.gates.all().order_by("category_code", "code")
        ]
        execution_by_scenario = {
            execution.scenario_id: execution for execution in current.uat_executions.all()
        }

    scenario_rows: list[dict[str, object]] = []
    for scenario in scenarios:
        execution = execution_by_scenario.get(scenario.id)
        scenario_rows.append(
            {
                "public_id": str(scenario.public_id),
                "code": scenario.code,
                "title": scenario.title,
                "module": scenario.module_code,
                "persona": scenario.persona_code,
                "required": scenario.is_required,
                "steps": scenario.steps,
                "expected_result": scenario.expected_result,
                "execution": (
                    {
                        "public_id": str(execution.public_id),
                        "status": execution.status_code,
                        "notes": execution.notes,
                        "defect_reference": execution.defect_reference,
                        "evidence": execution.evidence,
                        "version": execution.version,
                    }
                    if execution
                    else None
                ),
            }
        )

    required_gates = current.gates.filter(is_required=True) if current else None
    required_uat = current.uat_executions.filter(scenario__is_required=True) if current else None

    return {
        "company": {
            "public_id": str(company.public_id),
            "name": company.display_name,
            "currency": company.currency,
            "timezone": company.timezone,
        },
        "metrics": {
            "targets": target_queryset.filter(status_code="ACTIVE").count(),
            "release_candidates": release_queryset.count(),
            "required_gates_passed": (
                required_gates.filter(status_code="PASSED").count()
                if required_gates is not None
                else 0
            ),
            "required_gates_total": required_gates.count() if required_gates is not None else 0,
            "uat_passed": (
                required_uat.filter(status_code="PASSED").count()
                if required_uat is not None
                else 0
            ),
            "uat_total": required_uat.count() if required_uat is not None else 0,
            "available_backups": backup_queryset.filter(status_code="AVAILABLE").count(),
            "failed_readiness_checks": readiness_queryset.filter(checks_failed__gt=0).count(),
        },
        "current_release": (
            {
                "public_id": str(current.public_id),
                "release_code": current.release_code,
                "version_label": current.version_label,
                "title": current.title,
                "summary": current.summary,
                "status": current.status_code,
                "source_reference": current.source_reference,
                "artifact_reference": current.artifact_reference,
                "artifact_sha256": current.artifact_sha256,
                "planned_at": current.planned_at,
                "approved_at": current.approved_at,
                "published_at": current.published_at,
                "target": (
                    {
                        "public_id": str(current.target.public_id),
                        "code": current.target.code,
                        "name": current.target.name,
                    }
                    if current.target
                    else None
                ),
                "version": current.version,
            }
            if current
            else None
        ),
        "targets": [
            {
                "public_id": str(target.public_id),
                "code": target.code,
                "name": target.name,
                "environment": target.environment_code,
                "frontend_url": target.frontend_url,
                "backend_url": target.backend_url,
                "health_url": target.health_url,
                "provider": target.hosting_provider_code,
                "region": target.region_code,
                "status": target.status_code,
                "version": target.version,
            }
            for target in targets
        ],
        "gates": gate_rows,
        "scenarios": scenario_rows,
        "backups": [
            {
                "public_id": str(backup.public_id),
                "reference": backup.reference,
                "type": backup.backup_type_code,
                "status": backup.status_code,
                "storage_reference": backup.storage_reference,
                "restore_tested": backup.restore_tested,
                "captured_at": backup.captured_at,
                "retention_until": backup.retention_until,
                "release_code": backup.release.release_code if backup.release else None,
                "target_code": backup.target.code if backup.target else None,
            }
            for backup in backups
        ],
        "readiness_runs": [
            {
                "public_id": str(run.public_id),
                "status": run.status_code,
                "checks_total": run.checks_total,
                "checks_passed": run.checks_passed,
                "checks_failed": run.checks_failed,
                "results": run.results,
                "started_at": run.started_at,
                "completed_at": run.completed_at,
                "release_code": run.release.release_code if run.release else None,
            }
            for run in readiness_runs
        ],
    }
