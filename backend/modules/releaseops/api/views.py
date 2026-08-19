from __future__ import annotations

import uuid

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.request import Request
from rest_framework.response import Response

from modules.releaseops.application.selectors import release_overview
from modules.releaseops.application.services import (
    approve_release,
    attach_gate_evidence_file,
    attach_uat_evidence_file,
    create_release,
    create_target,
    decide_gate,
    execute_uat,
    publish_release,
    register_backup,
    run_readiness,
)
from modules.releaseops.models import (
    DeploymentTarget,
    ReleaseCandidate,
    ReleaseGate,
    UATExecution,
)
from modules.tenant.api.base import TenantScopedAPIView

from .serializers import (
    BackupSerializer,
    DeploymentTargetSerializer,
    EvidenceAttachmentSerializer,
    GateDecisionSerializer,
    ReadinessRunSerializer,
    ReleaseCandidateSerializer,
    UATExecutionSerializer,
    VersionActionSerializer,
)


def correlation_id(request: Request) -> uuid.UUID:
    return getattr(request, "request_id", uuid.uuid4())


def translate(error: DjangoValidationError) -> ValidationError:
    if hasattr(error, "message_dict"):
        return ValidationError(error.message_dict)
    return ValidationError(getattr(error, "messages", [str(error)]))


def find(model, *, company, public_id, message):
    item = model.objects.filter(company=company, public_id=public_id).first()
    if item is None:
        raise NotFound(message)
    return item


class ReleaseAPIView(TenantScopedAPIView):
    required_permission = "release.view"

    def initial(self, request: Request, *args: object, **kwargs: object) -> None:
        super().initial(request, *args, **kwargs)
        self.tenant_context.require(self.required_permission)

    @property
    def actor(self) -> uuid.UUID:
        return self.tenant_context.principal.user.public_id


class OverviewView(ReleaseAPIView):
    def get(self, request: Request) -> Response:
        payload = release_overview(self.tenant_context.company)
        payload["capabilities"] = {
            "can_manage": self.tenant_context.can("release.manage"),
            "can_target": self.tenant_context.can("release.target"),
            "can_gate": self.tenant_context.can("release.gate"),
            "can_uat": self.tenant_context.can("release.uat"),
            "can_backup": self.tenant_context.can("release.backup"),
            "can_approve": self.tenant_context.can("release.approve"),
            "can_publish": self.tenant_context.can("release.publish"),
            "can_export": self.tenant_context.can("release.export"),
        }
        return Response(payload)


class TargetCreateView(ReleaseAPIView):
    required_permission = "release.target"

    def post(self, request: Request) -> Response:
        serializer = DeploymentTargetSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            target = create_target(
                company=self.tenant_context.company,
                actor_public_id=self.actor,
                correlation_id=correlation_id(request),
                **serializer.validated_data,
            )
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(target.public_id), "code": target.code, "status": target.status_code}, status=201)


class ReleaseCreateView(ReleaseAPIView):
    required_permission = "release.manage"

    def post(self, request: Request) -> Response:
        serializer = ReleaseCandidateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        target_id = data.pop("target_public_id", None)
        target = find(DeploymentTarget, company=self.tenant_context.company, public_id=target_id, message="Deployment target not found") if target_id else None
        try:
            release = create_release(
                company=self.tenant_context.company,
                target=target,
                actor_public_id=self.actor,
                correlation_id=correlation_id(request),
                **data,
            )
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(release.public_id), "release_code": release.release_code, "status": release.status_code}, status=201)


class GateDecisionView(ReleaseAPIView):
    required_permission = "release.gate"

    def post(self, request: Request, gate_id: uuid.UUID) -> Response:
        gate = find(ReleaseGate, company=self.tenant_context.company, public_id=gate_id, message="Release gate not found")
        serializer = GateDecisionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            gate = decide_gate(
                gate=gate,
                actor_public_id=self.actor,
                correlation_id=correlation_id(request),
                **serializer.validated_data,
            )
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(gate.public_id), "status": gate.status_code, "version": gate.version})


class UATExecutionView(ReleaseAPIView):
    required_permission = "release.uat"

    def post(self, request: Request, execution_id: uuid.UUID) -> Response:
        execution = find(UATExecution, company=self.tenant_context.company, public_id=execution_id, message="UAT execution not found")
        serializer = UATExecutionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            execution = execute_uat(
                execution=execution,
                actor_public_id=self.actor,
                correlation_id=correlation_id(request),
                **serializer.validated_data,
            )
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(execution.public_id), "status": execution.status_code, "version": execution.version})


class BackupCreateView(ReleaseAPIView):
    required_permission = "release.backup"

    def post(self, request: Request) -> Response:
        serializer = BackupSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        release_id = data.pop("release_public_id", None)
        target_id = data.pop("target_public_id", None)
        release = find(ReleaseCandidate, company=self.tenant_context.company, public_id=release_id, message="Release candidate not found") if release_id else None
        target = find(DeploymentTarget, company=self.tenant_context.company, public_id=target_id, message="Deployment target not found") if target_id else None
        try:
            backup = register_backup(
                company=self.tenant_context.company,
                release=release,
                target=target,
                actor_public_id=self.actor,
                correlation_id=correlation_id(request),
                **data,
            )
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(backup.public_id), "reference": backup.reference, "status": backup.status_code}, status=201)


class ReadinessRunView(ReleaseAPIView):
    required_permission = "release.manage"

    def post(self, request: Request) -> Response:
        serializer = ReadinessRunSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        release_id = serializer.validated_data.get("release_public_id")
        release = find(ReleaseCandidate, company=self.tenant_context.company, public_id=release_id, message="Release candidate not found") if release_id else None
        run = run_readiness(
            company=self.tenant_context.company,
            release=release,
            actor_public_id=self.actor,
            correlation_id=correlation_id(request),
        )
        return Response({
            "public_id": str(run.public_id),
            "status": run.status_code,
            "checks_total": run.checks_total,
            "checks_passed": run.checks_passed,
            "checks_failed": run.checks_failed,
            "results": run.results,
        }, status=201)


class ApproveReleaseView(ReleaseAPIView):
    required_permission = "release.approve"

    def post(self, request: Request, release_id: uuid.UUID) -> Response:
        release = find(ReleaseCandidate, company=self.tenant_context.company, public_id=release_id, message="Release candidate not found")
        serializer = VersionActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            release = approve_release(
                release=release,
                actor_public_id=self.actor,
                correlation_id=correlation_id(request),
                **serializer.validated_data,
            )
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(release.public_id), "status": release.status_code, "version": release.version})


class PublishReleaseView(ReleaseAPIView):
    required_permission = "release.publish"

    def post(self, request: Request, release_id: uuid.UUID) -> Response:
        release = find(ReleaseCandidate, company=self.tenant_context.company, public_id=release_id, message="Release candidate not found")
        serializer = VersionActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            release = publish_release(
                release=release,
                actor_public_id=self.actor,
                correlation_id=correlation_id(request),
                **serializer.validated_data,
            )
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(release.public_id), "status": release.status_code, "version": release.version})



class GateEvidenceAttachmentView(ReleaseAPIView):
    required_permission = "release.gate"

    def post(self, request: Request, gate_id: uuid.UUID) -> Response:
        self.tenant_context.require("files.read")
        gate = find(ReleaseGate, company=self.tenant_context.company, public_id=gate_id, message="Release gate not found")
        serializer = EvidenceAttachmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            gate = attach_gate_evidence_file(
                gate=gate,
                actor_public_id=self.actor,
                correlation_id=correlation_id(request),
                **serializer.validated_data,
            )
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(gate.public_id), "version": gate.version, "evidence": gate.evidence})


class UATEvidenceAttachmentView(ReleaseAPIView):
    required_permission = "release.uat"

    def post(self, request: Request, execution_id: uuid.UUID) -> Response:
        self.tenant_context.require("files.read")
        execution = find(UATExecution, company=self.tenant_context.company, public_id=execution_id, message="UAT execution not found")
        serializer = EvidenceAttachmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            execution = attach_uat_evidence_file(
                execution=execution,
                actor_public_id=self.actor,
                correlation_id=correlation_id(request),
                **serializer.validated_data,
            )
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(execution.public_id), "version": execution.version, "evidence": execution.evidence})
