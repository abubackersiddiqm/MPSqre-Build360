from __future__ import annotations

import hashlib
import re
import uuid
from datetime import timedelta
from decimal import Decimal
from typing import Any

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from modules.ai.models import (
    AICitation,
    AIEvaluationRun,
    AIExtractionJob,
    AIInteraction,
    AIModelPolicy,
    AIProviderProfile,
    AIRiskSignal,
    AIToolAction,
)
from modules.platform.actors import RequestActor
from modules.platform.audit import AuditRecord, append_audit
from modules.platform.events import EventRecord, append_event
from modules.reporting.application.services import calculate_metric
from modules.reporting.models import MetricDefinition
from modules.tenant.models import Company

_SOURCE_PERMISSION = {
    "crm": "crm.dashboard.read",
    "projects": "project.dashboard.read",
    "supply": "vendor.dashboard.read",
    "procurement": "procurement.dashboard.read",
    "inventory": "inventory.dashboard.read",
    "safety": "safety.dashboard.read",
    "finance": "finance.dashboard.read",
    "notifications": "notification.inbox.read",
}


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _record(
    *,
    company: Company,
    actor: RequestActor,
    action: str,
    entity_type: str,
    entity_public_id: uuid.UUID,
    version: int,
    payload: dict[str, Any],
    reason_code: str = "",
) -> None:
    append_audit(
        AuditRecord(
            action=action,
            entity_type=entity_type,
            entity_public_id=entity_public_id,
            actor_public_id=actor.user_public_id,
            company_public_id=company.public_id,
            request_id=actor.request_id,
            correlation_id=actor.request_id,
            ip_address=actor.ip_address,
            user_agent=actor.user_agent,
            reason_code=reason_code,
            after=payload,
        )
    )
    append_event(
        EventRecord(
            event_type=action,
            aggregate_type=entity_type,
            aggregate_public_id=entity_public_id,
            aggregate_version=version,
            company_public_id=company.public_id,
            correlation_id=actor.request_id,
            payload=payload,
        )
    )


def active_policy(*, company: Company, code: str, purpose: str | None = None) -> AIModelPolicy:
    now = timezone.now()
    query = AIModelPolicy.objects.select_related("provider").filter(
        company=company,
        code=code.strip().upper(),
        is_active=True,
        effective_from__lte=now,
    ).filter(models_q_effective(now))
    if purpose:
        query = query.filter(purpose=purpose)
    policy = query.order_by("-version").first()
    if policy is None:
        raise ValidationError("No active AI policy matches this request")
    if not policy.provider.is_active:
        raise ValidationError("The AI provider configured by this policy is inactive")
    return policy


def models_q_effective(now: Any):
    from django.db.models import Q

    return Q(effective_to__isnull=True) | Q(effective_to__gt=now)


def _require_local_provider(policy: AIModelPolicy) -> None:
    if policy.provider.adapter_code != "local_grounded":
        raise ValidationError(
            "External AI execution is disabled until an approved provider adapter is configured"
        )
    if not settings.AI_LOCAL_ADAPTER_ENABLED:
        raise ValidationError("The local governed AI adapter is disabled")


def _authorized_metrics(
    *,
    company: Company,
    metric_codes: list[str],
    permission_codes: set[str],
    policy: AIModelPolicy,
) -> list[MetricDefinition]:
    normalized = [item.strip().upper() for item in metric_codes if item.strip()]
    if not normalized:
        raise ValidationError("At least one governed metric is required")
    if len(normalized) > policy.max_context_records:
        raise ValidationError("The requested context exceeds the active AI policy")
    metrics = list(
        MetricDefinition.objects.filter(
            company=company,
            code__in=normalized,
            is_active=True,
        ).order_by("domain_code", "code")
    )
    found = {item.code for item in metrics}
    missing = sorted(set(normalized) - found)
    if missing:
        raise ValidationError(
            {"metric_codes": [f"Unknown metrics: {', '.join(missing)}"]}
        )
    allowed_sources = set(policy.allowed_source_types)
    for metric in metrics:
        source_type = f"reporting.metric.{metric.domain_code}"
        if (
            allowed_sources
            and source_type not in allowed_sources
            and "reporting.metric" not in allowed_sources
        ):
            raise ValidationError(f"The AI policy does not allow source type {source_type}")
        required_permission = _SOURCE_PERMISSION.get(
            metric.domain_code,
            "reporting.metric.read",
        )
        if (
            required_permission not in permission_codes
            and "reporting.dashboard.read" not in permission_codes
        ):
            raise ValidationError(
                f"Permission {required_permission} is required for metric {metric.code}"
            )
        if (
            metric.data_classification == "restricted"
            and "ai.source.restricted" not in permission_codes
        ):
            raise ValidationError(f"Restricted metric {metric.code} requires ai.source.restricted")
        if metric.data_classification not in set(policy.allowed_data_classifications):
            raise ValidationError(
                f"Metric {metric.code} classification is not allowed by the active AI policy"
            )
    return metrics


def ai_summary(company: Company) -> dict[str, int]:
    return {
        "active_providers": AIProviderProfile.objects.filter(
            company=company,
            is_active=True,
        ).count(),
        "active_policies": AIModelPolicy.objects.filter(
            company=company,
            is_active=True,
        ).count(),
        "completed_interactions": AIInteraction.objects.filter(
            company=company,
            status=AIInteraction.Status.COMPLETED,
        ).count(),
        "pending_reviews": AIInteraction.objects.filter(
            company=company,
            review_status=AIInteraction.ReviewStatus.PENDING,
        ).count()
        + AIExtractionJob.objects.filter(
            company=company,
            status=AIExtractionJob.Status.COMPLETED,
        ).count(),
        "open_risks": AIRiskSignal.objects.filter(
            company=company,
            status__in=[AIRiskSignal.Status.OPEN, AIRiskSignal.Status.ACKNOWLEDGED],
        ).count(),
        "proposed_actions": AIToolAction.objects.filter(
            company=company,
            status=AIToolAction.Status.PROPOSED,
        ).count(),
    }


@transaction.atomic
def create_grounded_interaction(
    *,
    company: Company,
    actor: RequestActor,
    permission_codes: set[str],
    policy_code: str,
    prompt: str,
    metric_codes: list[str],
    idempotency_key: str,
) -> AIInteraction:
    normalized_prompt = prompt.strip()
    if not normalized_prompt:
        raise ValidationError("Prompt is required")
    if len(normalized_prompt) > settings.AI_MAX_PROMPT_CHARACTERS:
        raise ValidationError("Prompt exceeds the configured AI input limit")
    existing = AIInteraction.objects.filter(
        company=company,
        idempotency_key=idempotency_key.strip(),
    ).first()
    if existing:
        return existing
    policy = active_policy(
        company=company,
        code=policy_code,
        purpose=AIModelPolicy.Purpose.ASSISTANT,
    )
    _require_local_provider(policy)
    metrics = _authorized_metrics(
        company=company,
        metric_codes=metric_codes,
        permission_codes=permission_codes,
        policy=policy,
    )
    interaction = AIInteraction(
        company=company,
        policy=policy,
        requested_by_public_id=actor.user_public_id,
        membership_public_id=actor.membership_public_id,
        idempotency_key=idempotency_key.strip(),
        purpose=AIModelPolicy.Purpose.ASSISTANT,
        prompt_digest=_digest(normalized_prompt),
        prompt_excerpt=normalized_prompt[:500],
        status=AIInteraction.Status.RUNNING,
        citations_required=policy.citations_required,
        review_status=(
            AIInteraction.ReviewStatus.PENDING
            if policy.human_review_required
            else AIInteraction.ReviewStatus.NOT_REQUIRED
        ),
        provider_code_snapshot=policy.provider.code,
        model_name_snapshot=policy.model_name,
        input_metadata={"metric_codes": [item.code for item in metrics]},
        started_at=timezone.now(),
    )
    interaction.full_clean()
    interaction.save()

    rows: list[tuple[MetricDefinition, object]] = []
    for metric in metrics:
        rows.append(
            (
                metric,
                calculate_metric(
                    company=company,
                    metric=metric,
                    user_public_id=actor.user_public_id,
                ),
            )
        )
    lines = ["Grounded Build360 summary:"]
    for index, (metric, value) in enumerate(rows, start=1):
        lines.append(f"[{index}] {metric.name}: {value} {metric.unit_code}".rstrip())
    lines.append(
        "This output is decision support only. Validate source records before "
        "approvals, postings, safety actions, or external communications."
    )
    response = "\n".join(lines)[: policy.max_output_characters]
    interaction.response_text = response
    interaction.confidence = Decimal("0.9000") if rows else Decimal("0.0000")
    interaction.status = AIInteraction.Status.COMPLETED
    interaction.completed_at = timezone.now()
    interaction.output_metadata = {
        "citation_count": len(rows),
        "adapter": "local_grounded",
        "human_review_required": policy.human_review_required,
    }
    interaction.version += 1
    interaction.full_clean()
    interaction.save()
    for index, (metric, value) in enumerate(rows, start=1):
        citation = AICitation(
            company=company,
            interaction=interaction,
            rank=index,
            source_type="reporting.metric",
            source_public_id=metric.public_id,
            source_label=metric.name,
            source_version=str(metric.version),
            excerpt=f"{metric.code}={value} {metric.unit_code}"[:600],
            authorization_basis=_SOURCE_PERMISSION.get(metric.domain_code, "reporting.metric.read"),
            data_classification=metric.data_classification,
        )
        citation.full_clean()
        citation.save()
    _record(
        company=company,
        actor=actor,
        action="ai.interaction.completed",
        entity_type="ai_interaction",
        entity_public_id=interaction.public_id,
        version=interaction.version,
        payload={
            "policy_code": policy.code,
            "provider_code": policy.provider.code,
            "citation_count": len(rows),
            "review_status": interaction.review_status,
        },
    )
    return interaction


@transaction.atomic
def review_interaction(
    *,
    company: Company,
    actor: RequestActor,
    interaction_public_id: uuid.UUID,
    decision: str,
    reason: str,
    corrected_response: str = "",
) -> AIInteraction:
    interaction = AIInteraction.objects.select_for_update().get(
        company=company,
        public_id=interaction_public_id,
    )
    normalized = decision.strip().lower()
    if normalized not in {"approve", "reject", "correct"}:
        raise ValidationError("Decision must be approve, reject, or correct")
    if (
        actor.user_public_id == interaction.requested_by_public_id
        and interaction.policy.human_review_required
    ):
        raise ValidationError("A distinct reviewer is required by the active AI policy")
    if normalized == "correct":
        corrected = corrected_response.strip()
        if not corrected:
            raise ValidationError("Corrected response is required")
        if len(corrected) > interaction.policy.max_output_characters:
            raise ValidationError("Corrected response exceeds the policy limit")
        interaction.response_text = corrected
        interaction.review_status = AIInteraction.ReviewStatus.CORRECTED
    elif normalized == "approve":
        interaction.review_status = AIInteraction.ReviewStatus.APPROVED
    else:
        interaction.review_status = AIInteraction.ReviewStatus.REJECTED
    interaction.reviewed_by_public_id = actor.user_public_id
    interaction.reviewed_at = timezone.now()
    interaction.review_reason = reason.strip()[:500]
    interaction.version += 1
    interaction.save()
    _record(
        company=company,
        actor=actor,
        action="ai.interaction.reviewed",
        entity_type="ai_interaction",
        entity_public_id=interaction.public_id,
        version=interaction.version,
        payload={"decision": normalized, "review_status": interaction.review_status},
        reason_code=reason.strip()[:100],
    )
    return interaction


def _extract_value(source_text: str, field_name: str) -> str:
    pattern = re.compile(
        rf"(?im)^\s*{re.escape(field_name)}\s*[:=-]\s*(.+?)\s*$"
    )
    match = pattern.search(source_text)
    return match.group(1).strip()[:500] if match else ""


@transaction.atomic
def create_extraction_job(
    *,
    company: Company,
    actor: RequestActor,
    policy_code: str,
    source_type: str,
    source_public_id: uuid.UUID | None,
    source_text: str,
    schema_code: str,
    requested_fields: list[str],
    idempotency_key: str,
) -> AIExtractionJob:
    existing = AIExtractionJob.objects.filter(
        company=company,
        idempotency_key=idempotency_key.strip(),
    ).first()
    if existing:
        return existing
    if not source_text.strip():
        raise ValidationError("Source text is required for local extraction")
    if len(source_text) > settings.AI_EXTRACTION_MAX_CHARACTERS:
        raise ValidationError("Extraction source exceeds the configured limit")
    policy = active_policy(
        company=company,
        code=policy_code,
        purpose=AIModelPolicy.Purpose.EXTRACTION,
    )
    _require_local_provider(policy)
    fields = [item.strip() for item in requested_fields if item.strip()]
    payload = {field: _extract_value(source_text, field) for field in fields}
    confidence = {field: ("0.9000" if payload[field] else "0.0000") for field in fields}
    job = AIExtractionJob(
        company=company,
        policy=policy,
        requested_by_public_id=actor.user_public_id,
        idempotency_key=idempotency_key.strip(),
        source_type=source_type.strip().lower(),
        source_public_id=source_public_id,
        source_digest=_digest(source_text),
        schema_code=schema_code.strip().upper(),
        requested_fields=fields,
        extracted_payload=payload,
        confidence_by_field=confidence,
        status=AIExtractionJob.Status.COMPLETED,
    )
    job.full_clean()
    job.save()
    _record(
        company=company,
        actor=actor,
        action="ai.extraction.completed",
        entity_type="ai_extraction_job",
        entity_public_id=job.public_id,
        version=job.version,
        payload={
            "schema_code": job.schema_code,
            "field_count": len(fields),
            "source_type": job.source_type,
        },
    )
    return job


@transaction.atomic
def review_extraction(
    *,
    company: Company,
    actor: RequestActor,
    job_public_id: uuid.UUID,
    decision: str,
    corrections: dict[str, Any],
    reason: str,
) -> AIExtractionJob:
    job = AIExtractionJob.objects.select_for_update().get(
        company=company,
        public_id=job_public_id,
    )
    if actor.user_public_id == job.requested_by_public_id and job.policy.human_review_required:
        raise ValidationError("A distinct reviewer is required by the active AI policy")
    normalized = decision.strip().lower()
    if normalized not in {"approve", "reject", "correct"}:
        raise ValidationError("Decision must be approve, reject, or correct")
    if normalized == "correct":
        unknown = set(corrections) - set(job.requested_fields)
        if unknown:
            raise ValidationError(f"Unknown extraction fields: {', '.join(sorted(unknown))}")
        job.corrections = corrections
        job.extracted_payload = {**job.extracted_payload, **corrections}
        job.status = AIExtractionJob.Status.REVIEWED
    elif normalized == "approve":
        job.status = AIExtractionJob.Status.REVIEWED
    else:
        job.status = AIExtractionJob.Status.REJECTED
    job.reviewed_by_public_id = actor.user_public_id
    job.reviewed_at = timezone.now()
    job.review_reason = reason.strip()[:500]
    job.version += 1
    job.save()
    _record(
        company=company,
        actor=actor,
        action="ai.extraction.reviewed",
        entity_type="ai_extraction_job",
        entity_public_id=job.public_id,
        version=job.version,
        payload={"decision": normalized, "status": job.status},
        reason_code=reason.strip()[:100],
    )
    return job


@transaction.atomic
def scan_risks(
    *,
    company: Company,
    actor: RequestActor,
    permission_codes: set[str],
    policy_code: str,
) -> list[AIRiskSignal]:
    policy = active_policy(
        company=company,
        code=policy_code,
        purpose=AIModelPolicy.Purpose.RISK,
    )
    _require_local_provider(policy)
    metric_codes = [
        "PROJECT_TASKS_OVERDUE",
        "SAFETY_INCIDENTS_OPEN",
        "FINANCE_OUTSTANDING",
    ]
    metrics = _authorized_metrics(
        company=company,
        metric_codes=metric_codes,
        permission_codes=permission_codes,
        policy=policy,
    )
    signals: list[AIRiskSignal] = []
    for metric in metrics:
        value = calculate_metric(
            company=company,
            metric=metric,
            user_public_id=actor.user_public_id,
        )
        numeric = Decimal(str(value or 0))
        if numeric <= 0:
            continue
        severity = AIRiskSignal.Severity.MEDIUM
        if metric.code == "SAFETY_INCIDENTS_OPEN":
            severity = AIRiskSignal.Severity.HIGH
        elif metric.code == "FINANCE_OUTSTANDING" and numeric > Decimal("1000000"):
            severity = AIRiskSignal.Severity.HIGH
        fingerprint = _digest(f"{company.public_id}:{metric.code}:{metric.public_id}")
        signal, _ = AIRiskSignal.objects.get_or_create(
            company=company,
            fingerprint=fingerprint,
            status__in=[AIRiskSignal.Status.OPEN, AIRiskSignal.Status.ACKNOWLEDGED],
            defaults={
                "signal_code": f"AI_{metric.code}",
                "severity": severity,
                "title": metric.name,
                "description": f"Governed metric {metric.code} currently reports {value}.",
                "source_type": "reporting.metric",
                "source_public_id": metric.public_id,
                "evidence": {
                    "metric_code": metric.code,
                    "value": str(value),
                    "unit": metric.unit_code,
                },
            },
        )
        signals.append(signal)
    for signal in signals:
        _record(
            company=company,
            actor=actor,
            action="ai.risk.detected",
            entity_type="ai_risk_signal",
            entity_public_id=signal.public_id,
            version=signal.version,
            payload={
                "signal_code": signal.signal_code,
                "severity": signal.severity,
                "status": signal.status,
            },
        )
    return signals


@transaction.atomic
def decide_risk(
    *,
    company: Company,
    actor: RequestActor,
    signal_public_id: uuid.UUID,
    decision: str,
    reason: str,
) -> AIRiskSignal:
    signal = AIRiskSignal.objects.select_for_update().get(
        company=company,
        public_id=signal_public_id,
    )
    normalized = decision.strip().lower()
    if normalized not in {
        AIRiskSignal.Status.ACKNOWLEDGED,
        AIRiskSignal.Status.RESOLVED,
        AIRiskSignal.Status.DISMISSED,
    }:
        raise ValidationError("Risk decision must be acknowledged, resolved, or dismissed")
    signal.status = normalized
    signal.disposition_reason = reason.strip()[:500]
    if normalized in {AIRiskSignal.Status.RESOLVED, AIRiskSignal.Status.DISMISSED}:
        signal.resolved_by_public_id = actor.user_public_id
        signal.resolved_at = timezone.now()
    signal.version += 1
    signal.save()
    _record(
        company=company,
        actor=actor,
        action="ai.risk.decided",
        entity_type="ai_risk_signal",
        entity_public_id=signal.public_id,
        version=signal.version,
        payload={"status": signal.status, "signal_code": signal.signal_code},
        reason_code=reason.strip()[:100],
    )
    return signal


@transaction.atomic
def propose_tool_action(
    *,
    company: Company,
    actor: RequestActor,
    interaction_public_id: uuid.UUID,
    action_code: str,
    target_type: str,
    target_public_id: uuid.UUID | None,
    proposed_payload: dict[str, Any],
    idempotency_key: str,
) -> AIToolAction:
    existing = AIToolAction.objects.filter(
        company=company,
        idempotency_key=idempotency_key.strip(),
    ).first()
    if existing:
        return existing
    interaction = AIInteraction.objects.select_related("policy").get(
        company=company,
        public_id=interaction_public_id,
    )
    normalized_action = action_code.strip().lower()
    if normalized_action not in set(interaction.policy.allowed_tool_codes):
        raise ValidationError("The requested tool action is not allowed by the AI policy")
    action = AIToolAction(
        company=company,
        interaction=interaction,
        action_code=normalized_action,
        target_type=target_type.strip().lower(),
        target_public_id=target_public_id,
        proposed_payload=proposed_payload,
        proposed_by_public_id=actor.user_public_id,
        expires_at=timezone.now() + timedelta(hours=24),
        idempotency_key=idempotency_key.strip(),
    )
    action.full_clean()
    action.save()
    _record(
        company=company,
        actor=actor,
        action="ai.tool_action.proposed",
        entity_type="ai_tool_action",
        entity_public_id=action.public_id,
        version=action.version,
        payload={"action_code": action.action_code, "status": action.status},
    )
    return action


@transaction.atomic
def decide_tool_action(
    *,
    company: Company,
    actor: RequestActor,
    action_public_id: uuid.UUID,
    decision: str,
    reason: str,
) -> AIToolAction:
    action = AIToolAction.objects.select_for_update().get(
        company=company,
        public_id=action_public_id,
    )
    if action.status != AIToolAction.Status.PROPOSED:
        raise ValidationError("Only proposed AI tool actions can be decided")
    if action.expires_at <= timezone.now():
        action.status = AIToolAction.Status.EXPIRED
        action.version += 1
        action.save()
        raise ValidationError("The AI tool proposal has expired")
    if actor.user_public_id == action.proposed_by_public_id:
        raise ValidationError("AI tool actions require independent human confirmation")
    normalized = decision.strip().lower()
    if normalized not in {"confirm", "reject"}:
        raise ValidationError("Decision must be confirm or reject")
    action.status = (
        AIToolAction.Status.CONFIRMED
        if normalized == "confirm"
        else AIToolAction.Status.REJECTED
    )
    action.decided_by_public_id = actor.user_public_id
    action.decided_at = timezone.now()
    action.decision_reason = reason.strip()[:500]
    action.version += 1
    action.save()
    _record(
        company=company,
        actor=actor,
        action="ai.tool_action.decided",
        entity_type="ai_tool_action",
        entity_public_id=action.public_id,
        version=action.version,
        payload={"action_code": action.action_code, "status": action.status},
        reason_code=reason.strip()[:100],
    )
    return action


@transaction.atomic
def run_evaluation(
    *,
    company: Company,
    actor: RequestActor,
    policy_code: str,
    suite_code: str = "FOUNDATION_GUARDRAILS",
) -> AIEvaluationRun:
    policy = active_policy(company=company, code=policy_code)
    scenarios = {
        "citation_control_appropriate": (
            policy.citations_required
            or policy.purpose == AIModelPolicy.Purpose.EXTRACTION
        ),
        "human_review_required": policy.human_review_required,
        "provider_active": policy.provider.is_active,
        "context_bounded": policy.max_context_records <= 100,
        "output_bounded": policy.max_output_characters <= 20000,
        "no_external_execution": policy.provider.adapter_code == "local_grounded",
    }
    failures = [name for name, passed in scenarios.items() if not passed]
    run = AIEvaluationRun(
        company=company,
        policy=policy,
        requested_by_public_id=actor.user_public_id,
        suite_code=suite_code.strip().upper(),
        status=(
            AIEvaluationRun.Status.COMPLETED
            if not failures
            else AIEvaluationRun.Status.FAILED
        ),
        scenario_count=len(scenarios),
        passed_count=len(scenarios) - len(failures),
        scores={
            "guardrail_pass_rate": str(
                (len(scenarios) - len(failures)) / len(scenarios)
            )
        },
        failures=failures,
        provider_code_snapshot=policy.provider.code,
        model_name_snapshot=policy.model_name,
        completed_at=timezone.now(),
    )
    run.full_clean()
    run.save()
    _record(
        company=company,
        actor=actor,
        action="ai.evaluation.completed",
        entity_type="ai_evaluation_run",
        entity_public_id=run.public_id,
        version=1,
        payload={
            "suite_code": run.suite_code,
            "passed": run.passed_count,
            "total": run.scenario_count,
            "status": run.status,
        },
    )
    return run
