from __future__ import annotations

import uuid

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.exceptions import ValidationError
from rest_framework.request import Request
from rest_framework.response import Response

from modules.pilotops.api.serializers import (
    AdoptionCollectSerializer,
    ChecklistTransitionSerializer,
    GoLiveTransitionSerializer,
    SignoffDecisionSerializer,
    TrainingCompletionSerializer,
)
from modules.pilotops.application.services import (
    assess_readiness,
    collect_adoption_snapshot,
    current_program,
    pilot_summary,
    readiness_metrics,
    signoff_go_live,
    transition_checklist_item,
    transition_go_live,
    update_training_completion,
    validate_master_data,
)
from modules.pilotops.models import (
    AdoptionSnapshot,
    GoLivePlan,
    GoLiveSignoff,
    MasterDataReadiness,
    PilotChecklistItem,
    PilotProgram,
    ReadinessAssessment,
    TrainingCompletion,
    TrainingModule,
)
from modules.platform.actors import request_actor
from modules.tenant.api.base import TenantScopedAPIView


def _validation(exc: DjangoValidationError) -> ValidationError:
    return ValidationError(exc.message_dict if hasattr(exc, "message_dict") else exc.messages)


def _program(item: PilotProgram) -> dict[str, object]:
    return {
        "public_id": str(item.public_id),
        "cohort_code": item.cohort_code,
        "name": item.name,
        "status": item.status,
        "owner": {
            "membership_public_id": str(item.owner_membership.public_id),
            "email": item.owner_membership.user.email,
            "display_name": item.owner_membership.user.display_name,
        },
        "target_start_date": item.target_start_date,
        "target_go_live_at": item.target_go_live_at,
        "actual_go_live_at": item.actual_go_live_at,
        "notes": item.notes,
        "version": item.version,
    }


def _checklist(item: PilotChecklistItem) -> dict[str, object]:
    return {
        "public_id": str(item.public_id),
        "code": item.code,
        "category": item.category,
        "title": item.title,
        "description": item.description,
        "is_required": item.is_required,
        "sequence": item.sequence,
        "status": item.status,
        "owner": (
            {
                "membership_public_id": str(item.owner_membership.public_id),
                "display_name": item.owner_membership.user.display_name,
            }
            if item.owner_membership_id
            else None
        ),
        "due_at": item.due_at,
        "completed_at": item.completed_at,
        "evidence": item.evidence,
        "waiver_reason": item.waiver_reason,
        "version": item.version,
    }


def _master(item: MasterDataReadiness) -> dict[str, object]:
    return {
        "public_id": str(item.public_id),
        "domain_code": item.domain_code,
        "domain_name": item.domain_name,
        "minimum_records": item.minimum_records,
        "current_records": item.current_records,
        "is_required": item.is_required,
        "status": item.status,
        "validation_summary": item.validation_summary,
        "last_validated_at": item.last_validated_at,
        "version": item.version,
    }


def _training_module(item: TrainingModule) -> dict[str, object]:
    return {
        "public_id": str(item.public_id),
        "code": item.code,
        "title": item.title,
        "description": item.description,
        "audience_codes": item.audience_codes,
        "is_required": item.is_required,
        "sequence": item.sequence,
        "status": item.status,
        "content_url": item.content_url,
        "version": item.version,
    }


def _completion(item: TrainingCompletion) -> dict[str, object]:
    return {
        "public_id": str(item.public_id),
        "module_public_id": str(item.module.public_id),
        "module_code": item.module.code,
        "module_title": item.module.title,
        "membership_public_id": str(item.membership.public_id),
        "user": {
            "email": item.membership.user.email,
            "display_name": item.membership.user.display_name,
        },
        "status": item.status,
        "score_percent": str(item.score_percent) if item.score_percent is not None else None,
        "assigned_at": item.assigned_at,
        "completed_at": item.completed_at,
        "evidence": item.evidence,
        "version": item.version,
    }


def _signoff(item: GoLiveSignoff) -> dict[str, object]:
    return {
        "public_id": str(item.public_id),
        "code": item.code,
        "area": item.area,
        "title": item.title,
        "is_required": item.is_required,
        "status": item.status,
        "signer": (
            {
                "membership_public_id": str(item.signer_membership.public_id),
                "display_name": item.signer_membership.user.display_name,
            }
            if item.signer_membership_id
            else None
        ),
        "signed_at": item.signed_at,
        "evidence": item.evidence,
        "reason": item.reason,
        "version": item.version,
    }


def _go_live(item: GoLivePlan) -> dict[str, object]:
    return {
        "public_id": str(item.public_id),
        "target_at": item.target_at,
        "cutover_window_minutes": item.cutover_window_minutes,
        "support_window_hours": item.support_window_hours,
        "rollback_reference": item.rollback_reference,
        "cutover_steps": item.cutover_steps,
        "status": item.status,
        "approved_at": item.approved_at,
        "started_at": item.started_at,
        "completed_at": item.completed_at,
        "version": item.version,
        "signoffs": [_signoff(signoff) for signoff in item.signoffs.all()],
    }


def _assessment(item: ReadinessAssessment) -> dict[str, object]:
    return {
        "public_id": str(item.public_id),
        "assessed_at": item.assessed_at,
        "score_percent": item.score_percent,
        "critical_blockers": item.critical_blockers,
        "warnings": item.warnings,
        "metrics": item.metrics,
        "checksum_sha256": item.checksum_sha256,
    }


def _adoption(item: AdoptionSnapshot) -> dict[str, object]:
    return {
        "public_id": str(item.public_id),
        "period_start": item.period_start,
        "period_end": item.period_end,
        "active_users": item.active_users,
        "total_users": item.total_users,
        "training_completion_percent": str(item.training_completion_percent),
        "completed_checklist_items": item.completed_checklist_items,
        "total_checklist_items": item.total_checklist_items,
        "key_activity_count": item.key_activity_count,
        "metrics": item.metrics,
        "generated_at": item.generated_at,
        "checksum_sha256": item.checksum_sha256,
    }


class PilotSummaryView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("pilot.dashboard.read")
        summary = pilot_summary(self.tenant_context.company)
        program = summary.pop("program")
        latest_adoption = summary.pop("latest_adoption")
        return Response(
            {
                **summary,
                "program": _program(program) if program else None,
                "latest_adoption": _adoption(latest_adoption) if latest_adoption else None,
            }
        )


class PilotPortfolioView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("pilot.dashboard.read")
        program = current_program(self.tenant_context.company)
        if program is None:
            return Response({"program": None})
        program = (
            PilotProgram.objects.select_related("owner_membership__user")
            .prefetch_related(
                "checklist_items__owner_membership__user",
                "master_data_domains",
                "training_modules",
                "training_modules__completions__membership__user",
                "readiness_assessments",
                "adoption_snapshots",
                "go_live_plan__signoffs__signer_membership__user",
            )
            .get(pk=program.pk)
        )
        try:
            plan = program.go_live_plan
        except GoLivePlan.DoesNotExist:
            plan = None
        return Response(
            {
                "program": _program(program),
                "readiness": readiness_metrics(program),
                "checklist": [_checklist(item) for item in program.checklist_items.all()],
                "master_data": [_master(item) for item in program.master_data_domains.all()],
                "training_modules": [
                    _training_module(item) for item in program.training_modules.all()
                ],
                "training_completions": [
                    _completion(item)
                    for module in program.training_modules.all()
                    for item in module.completions.all()
                ],
                "latest_assessment": (
                    _assessment(program.readiness_assessments.order_by("-assessed_at").first())
                    if program.readiness_assessments.exists()
                    else None
                ),
                "go_live_plan": _go_live(plan) if plan else None,
                "adoption": [
                    _adoption(item)
                    for item in program.adoption_snapshots.order_by("-period_end")[:12]
                ],
            }
        )


class ChecklistTransitionView(TenantScopedAPIView):
    def post(self, request: Request, public_id: uuid.UUID) -> Response:
        serializer = ChecklistTransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        status = serializer.validated_data["status"]
        permission = (
            "pilot.checklist.waive"
            if status == PilotChecklistItem.Status.WAIVED
            else "pilot.checklist.complete"
        )
        self.tenant_context.require(permission)
        try:
            item = transition_checklist_item(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                item_public_id=public_id,
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        return Response(_checklist(item))


class MasterDataValidateView(TenantScopedAPIView):
    def post(self, request: Request, program_public_id: uuid.UUID) -> Response:
        self.tenant_context.require("pilot.master_data.validate")
        try:
            items = validate_master_data(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                program_public_id=program_public_id,
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        return Response({"items": [_master(item) for item in items]})


class TrainingCompletionView(TenantScopedAPIView):
    def post(self, request: Request, public_id: uuid.UUID) -> Response:
        self.tenant_context.require("pilot.training.complete")
        serializer = TrainingCompletionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = update_training_completion(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                completion_public_id=public_id,
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        item = TrainingCompletion.objects.select_related("module", "membership__user").get(
            pk=item.pk
        )
        return Response(_completion(item))


class ReadinessAssessView(TenantScopedAPIView):
    def post(self, request: Request, program_public_id: uuid.UUID) -> Response:
        self.tenant_context.require("pilot.readiness.assess")
        try:
            item = assess_readiness(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                program_public_id=program_public_id,
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        return Response(_assessment(item), status=201)


class GoLiveSignoffView(TenantScopedAPIView):
    def post(self, request: Request, public_id: uuid.UUID) -> Response:
        serializer = SignoffDecisionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        permission = (
            "pilot.golive.waive"
            if serializer.validated_data["status"] == GoLiveSignoff.Status.WAIVED
            else "pilot.golive.signoff"
        )
        self.tenant_context.require(permission)
        try:
            item = signoff_go_live(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                signoff_public_id=public_id,
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        return Response(_signoff(item))


class GoLiveTransitionView(TenantScopedAPIView):
    def post(self, request: Request, public_id: uuid.UUID) -> Response:
        serializer = GoLiveTransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        target = serializer.validated_data["target_status"]
        permission = {
            GoLivePlan.Status.IN_REVIEW: "pilot.golive.manage",
            GoLivePlan.Status.DRAFT: "pilot.golive.manage",
            GoLivePlan.Status.APPROVED: "pilot.golive.approve",
            GoLivePlan.Status.IN_PROGRESS: "pilot.golive.execute",
            GoLivePlan.Status.LIVE: "pilot.golive.execute",
            GoLivePlan.Status.ROLLED_BACK: "pilot.golive.rollback",
            GoLivePlan.Status.CANCELLED: "pilot.golive.manage",
        }[target]
        self.tenant_context.require(permission)
        try:
            item = transition_go_live(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                plan_public_id=public_id,
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        item = GoLivePlan.objects.prefetch_related("signoffs__signer_membership__user").get(
            pk=item.pk
        )
        return Response(_go_live(item))


class AdoptionCollectView(TenantScopedAPIView):
    def post(self, request: Request, program_public_id: uuid.UUID) -> Response:
        self.tenant_context.require("pilot.adoption.collect")
        serializer = AdoptionCollectSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = collect_adoption_snapshot(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                program_public_id=program_public_id,
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        return Response(_adoption(item), status=201)
