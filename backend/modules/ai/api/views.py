from __future__ import annotations

import uuid

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from rest_framework.request import Request
from rest_framework.response import Response

from modules.ai.api.serializers import (
    EvaluationRunSerializer,
    ExtractionCreateSerializer,
    ExtractionReviewSerializer,
    InteractionCreateSerializer,
    InteractionReviewSerializer,
    PolicyCreateSerializer,
    RiskDecisionSerializer,
    RiskScanSerializer,
    ToolActionCreateSerializer,
    ToolActionDecisionSerializer,
)
from modules.ai.application.services import (
    ai_summary,
    create_extraction_job,
    create_grounded_interaction,
    decide_risk,
    decide_tool_action,
    propose_tool_action,
    review_extraction,
    review_interaction,
    run_evaluation,
    scan_risks,
)
from modules.ai.models import (
    AIEvaluationRun,
    AIExtractionJob,
    AIInteraction,
    AIModelPolicy,
    AIProviderProfile,
    AIRiskSignal,
    AIToolAction,
)
from modules.platform.actors import request_actor
from modules.platform.audit import AuditRecord, append_audit
from modules.platform.events import EventRecord, append_event
from modules.tenant.api.base import TenantScopedAPIView


def _validation(exc: DjangoValidationError) -> ValidationError:
    return ValidationError(exc.message_dict if hasattr(exc, "message_dict") else exc.messages)


def _provider(item: AIProviderProfile) -> dict[str, object]:
    return {
        "public_id": str(item.public_id),
        "code": item.code,
        "display_name": item.display_name,
        "adapter_code": item.adapter_code,
        "data_residency": item.data_residency,
        "supports_citations": item.supports_citations,
        "supports_extraction": item.supports_extraction,
        "supports_tools": item.supports_tools,
        "is_active": item.is_active,
        "version": item.version,
    }


def _policy(item: AIModelPolicy) -> dict[str, object]:
    return {
        "public_id": str(item.public_id),
        "code": item.code,
        "name": item.name,
        "provider": _provider(item.provider),
        "model_name": item.model_name,
        "purpose": item.purpose,
        "allowed_source_types": item.allowed_source_types,
        "allowed_data_classifications": item.allowed_data_classifications,
        "allowed_tool_codes": item.allowed_tool_codes,
        "max_context_records": item.max_context_records,
        "max_output_characters": item.max_output_characters,
        "human_review_required": item.human_review_required,
        "citations_required": item.citations_required,
        "retention_days": item.retention_days,
        "effective_from": item.effective_from,
        "effective_to": item.effective_to,
        "is_active": item.is_active,
        "version": item.version,
    }


def _interaction(item: AIInteraction) -> dict[str, object]:
    return {
        "public_id": str(item.public_id),
        "policy": {"code": item.policy.code, "name": item.policy.name},
        "purpose": item.purpose,
        "prompt_excerpt": item.prompt_excerpt,
        "status": item.status,
        "response_text": item.response_text,
        "confidence": str(item.confidence) if item.confidence is not None else None,
        "review_status": item.review_status,
        "review_reason": item.review_reason,
        "provider_code": item.provider_code_snapshot,
        "model_name": item.model_name_snapshot,
        "input_metadata": item.input_metadata,
        "output_metadata": item.output_metadata,
        "citations": [
            {
                "public_id": str(citation.public_id),
                "rank": citation.rank,
                "source_type": citation.source_type,
                "source_public_id": str(citation.source_public_id),
                "source_label": citation.source_label,
                "source_version": citation.source_version,
                "excerpt": citation.excerpt,
                "authorization_basis": citation.authorization_basis,
                "data_classification": citation.data_classification,
            }
            for citation in item.citations.all()
        ],
        "created_at": item.created_at,
        "completed_at": item.completed_at,
        "version": item.version,
    }


def _extraction(item: AIExtractionJob) -> dict[str, object]:
    return {
        "public_id": str(item.public_id),
        "policy_code": item.policy.code,
        "source_type": item.source_type,
        "source_public_id": str(item.source_public_id) if item.source_public_id else None,
        "source_digest": item.source_digest,
        "schema_code": item.schema_code,
        "requested_fields": item.requested_fields,
        "extracted_payload": item.extracted_payload,
        "confidence_by_field": item.confidence_by_field,
        "status": item.status,
        "corrections": item.corrections,
        "review_reason": item.review_reason,
        "created_at": item.created_at,
        "version": item.version,
    }


def _risk(item: AIRiskSignal) -> dict[str, object]:
    return {
        "public_id": str(item.public_id),
        "signal_code": item.signal_code,
        "severity": item.severity,
        "title": item.title,
        "description": item.description,
        "source_type": item.source_type,
        "source_public_id": str(item.source_public_id) if item.source_public_id else None,
        "evidence": item.evidence,
        "status": item.status,
        "disposition_reason": item.disposition_reason,
        "created_at": item.created_at,
        "version": item.version,
    }


def _action(item: AIToolAction) -> dict[str, object]:
    return {
        "public_id": str(item.public_id),
        "interaction_public_id": str(item.interaction.public_id),
        "action_code": item.action_code,
        "target_type": item.target_type,
        "target_public_id": str(item.target_public_id) if item.target_public_id else None,
        "proposed_payload": item.proposed_payload,
        "status": item.status,
        "decision_reason": item.decision_reason,
        "expires_at": item.expires_at,
        "created_at": item.created_at,
        "version": item.version,
    }


def _evaluation(item: AIEvaluationRun) -> dict[str, object]:
    return {
        "public_id": str(item.public_id),
        "policy_code": item.policy.code,
        "suite_code": item.suite_code,
        "status": item.status,
        "scenario_count": item.scenario_count,
        "passed_count": item.passed_count,
        "scores": item.scores,
        "failures": item.failures,
        "provider_code": item.provider_code_snapshot,
        "model_name": item.model_name_snapshot,
        "completed_at": item.completed_at,
    }


class AISummaryView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("ai.dashboard.read")
        return Response(ai_summary(self.tenant_context.company))


class ProviderListView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("ai.provider.read")
        items = AIProviderProfile.objects.filter(company=self.tenant_context.company)[:100]
        return Response({"items": [_provider(item) for item in items]})


class PolicyListCreateView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("ai.policy.read")
        items = AIModelPolicy.objects.select_related("provider").filter(
            company=self.tenant_context.company,
        )[:200]
        return Response({"items": [_policy(item) for item in items]})

    @transaction.atomic
    def post(self, request: Request) -> Response:
        self.tenant_context.require("ai.policy.manage")
        serializer = PolicyCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        provider = AIProviderProfile.objects.filter(
            company=self.tenant_context.company,
            public_id=data.pop("provider_public_id"),
        ).first()
        if provider is None:
            raise ValidationError({"provider_public_id": ["Provider not found"]})
        latest = AIModelPolicy.objects.filter(
            company=self.tenant_context.company,
            code=data["code"].strip().upper(),
        ).order_by("-version").first()
        if latest:
            AIModelPolicy.objects.filter(pk=latest.pk).update(is_active=False)
        item = AIModelPolicy(
            company=self.tenant_context.company,
            provider=provider,
            code=data.pop("code").strip().upper(),
            version=(latest.version + 1) if latest else 1,
            effective_from=timezone.now(),
            **data,
        )
        try:
            item.full_clean()
            item.save()
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        actor = request_actor(request, self.tenant_context)
        append_audit(
            AuditRecord(
                action="ai.policy.created",
                entity_type="ai_model_policy",
                entity_public_id=item.public_id,
                actor_public_id=actor.user_public_id,
                company_public_id=self.tenant_context.company.public_id,
                request_id=actor.request_id,
                correlation_id=actor.request_id,
                ip_address=actor.ip_address,
                user_agent=actor.user_agent,
                after={"code": item.code, "purpose": item.purpose, "version": item.version},
            )
        )
        append_event(
            EventRecord(
                event_type="ai.policy.created",
                aggregate_type="ai_model_policy",
                aggregate_public_id=item.public_id,
                aggregate_version=item.version,
                company_public_id=self.tenant_context.company.public_id,
                correlation_id=actor.request_id,
                payload={"code": item.code, "purpose": item.purpose, "version": item.version},
            )
        )
        return Response(_policy(item), status=201)


class InteractionListCreateView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("ai.interaction.read")
        items = AIInteraction.objects.select_related("policy").prefetch_related("citations").filter(
            company=self.tenant_context.company,
        )[:200]
        return Response({"items": [_interaction(item) for item in items]})

    def post(self, request: Request) -> Response:
        self.tenant_context.require("ai.interaction.create")
        serializer = InteractionCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = create_grounded_interaction(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                permission_codes=set(self.tenant_context.permission_codes()),
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        item = (
            AIInteraction.objects.select_related("policy")
            .prefetch_related("citations")
            .get(pk=item.pk)
        )
        return Response(_interaction(item), status=201)


class InteractionReviewView(TenantScopedAPIView):
    def post(self, request: Request, public_id: uuid.UUID) -> Response:
        self.tenant_context.require("ai.interaction.review")
        serializer = InteractionReviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = review_interaction(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                interaction_public_id=public_id,
                **serializer.validated_data,
            )
        except (DjangoValidationError, AIInteraction.DoesNotExist) as exc:
            if isinstance(exc, AIInteraction.DoesNotExist):
                return Response({"detail": "Not found"}, status=404)
            raise _validation(exc) from exc
        item = (
            AIInteraction.objects.select_related("policy")
            .prefetch_related("citations")
            .get(pk=item.pk)
        )
        return Response(_interaction(item))


class ExtractionListCreateView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("ai.extraction.read")
        items = AIExtractionJob.objects.select_related("policy").filter(
            company=self.tenant_context.company,
        )[:200]
        return Response({"items": [_extraction(item) for item in items]})

    def post(self, request: Request) -> Response:
        self.tenant_context.require("ai.extraction.create")
        serializer = ExtractionCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = create_extraction_job(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        return Response(_extraction(item), status=201)


class ExtractionReviewView(TenantScopedAPIView):
    def post(self, request: Request, public_id: uuid.UUID) -> Response:
        self.tenant_context.require("ai.extraction.review")
        serializer = ExtractionReviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = review_extraction(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                job_public_id=public_id,
                **serializer.validated_data,
            )
        except (DjangoValidationError, AIExtractionJob.DoesNotExist) as exc:
            if isinstance(exc, AIExtractionJob.DoesNotExist):
                return Response({"detail": "Not found"}, status=404)
            raise _validation(exc) from exc
        return Response(_extraction(item))


class RiskListScanView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("ai.risk.read")
        items = AIRiskSignal.objects.filter(company=self.tenant_context.company)[:300]
        return Response({"items": [_risk(item) for item in items]})

    def post(self, request: Request) -> Response:
        self.tenant_context.require("ai.risk.scan")
        serializer = RiskScanSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            items = scan_risks(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                permission_codes=set(self.tenant_context.permission_codes()),
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        return Response({"items": [_risk(item) for item in items]}, status=201)


class RiskDecisionView(TenantScopedAPIView):
    def post(self, request: Request, public_id: uuid.UUID) -> Response:
        self.tenant_context.require("ai.risk.manage")
        serializer = RiskDecisionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = decide_risk(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                signal_public_id=public_id,
                **serializer.validated_data,
            )
        except (DjangoValidationError, AIRiskSignal.DoesNotExist) as exc:
            if isinstance(exc, AIRiskSignal.DoesNotExist):
                return Response({"detail": "Not found"}, status=404)
            raise _validation(exc) from exc
        return Response(_risk(item))


class ToolActionListCreateView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("ai.action.read")
        items = AIToolAction.objects.select_related("interaction").filter(
            company=self.tenant_context.company,
        )[:200]
        return Response({"items": [_action(item) for item in items]})

    def post(self, request: Request) -> Response:
        self.tenant_context.require("ai.action.propose")
        serializer = ToolActionCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = propose_tool_action(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                **serializer.validated_data,
            )
        except (DjangoValidationError, AIInteraction.DoesNotExist) as exc:
            if isinstance(exc, AIInteraction.DoesNotExist):
                return Response({"detail": "Interaction not found"}, status=404)
            raise _validation(exc) from exc
        return Response(_action(item), status=201)


class ToolActionDecisionView(TenantScopedAPIView):
    def post(self, request: Request, public_id: uuid.UUID) -> Response:
        self.tenant_context.require("ai.action.confirm")
        serializer = ToolActionDecisionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = decide_tool_action(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                action_public_id=public_id,
                **serializer.validated_data,
            )
        except (DjangoValidationError, AIToolAction.DoesNotExist) as exc:
            if isinstance(exc, AIToolAction.DoesNotExist):
                return Response({"detail": "Not found"}, status=404)
            raise _validation(exc) from exc
        return Response(_action(item))


class EvaluationListCreateView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("ai.evaluation.read")
        items = AIEvaluationRun.objects.select_related("policy").filter(
            company=self.tenant_context.company,
        )[:200]
        return Response({"items": [_evaluation(item) for item in items]})

    def post(self, request: Request) -> Response:
        self.tenant_context.require("ai.evaluation.run")
        serializer = EvaluationRunSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = run_evaluation(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        return Response(_evaluation(item), status=201)
