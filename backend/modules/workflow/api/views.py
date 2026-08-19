import uuid

from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Q
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.request import Request
from rest_framework.response import Response

from modules.platform.audit import request_metadata
from modules.tenant.api.base import TenantScopedAPIView
from modules.workflow.application.approval_center import approval_center_items
from modules.workflow.application.services import (
    decide_approval,
    publish_workflow_version,
    request_transition,
    start_workflow,
    validate_workflow,
)
from modules.workflow.models import (
    ApprovalTask,
    WorkflowDefinition,
    WorkflowInstance,
    WorkflowVersion,
)

from .serializers import (
    ApprovalDecisionSerializer,
    WorkflowDefinitionCreateSerializer,
    WorkflowStartSerializer,
    WorkflowTransitionSerializer,
    WorkflowVersionCreateSerializer,
)


def _instance_response(instance: WorkflowInstance) -> dict[str, object]:
    return {
        "public_id": str(instance.public_id),
        "definition_code": instance.definition.code,
        "workflow_version": instance.workflow_version.version,
        "subject_type": instance.subject_type,
        "subject_public_id": str(instance.subject_public_id),
        "current_state_code": instance.current_state_code,
        "lock_version": instance.lock_version,
        "status": instance.status,
        "started_at": instance.started_at.isoformat(),
        "completed_at": instance.completed_at.isoformat() if instance.completed_at else None,
    }


def _approval_response(approval: ApprovalTask) -> dict[str, object]:
    return {
        "public_id": str(approval.public_id),
        "workflow_instance_public_id": str(approval.workflow_instance.public_id),
        "transition_code": approval.transition_code,
        "from_state_code": approval.from_state_code,
        "to_state_code": approval.to_state_code,
        "status": approval.status,
        "due_at": approval.due_at.isoformat() if approval.due_at else None,
        "requested_by_public_id": str(approval.requested_by_public_id),
    }


class WorkflowStartView(TenantScopedAPIView):
    def post(self, request: Request, definition_code: str) -> Response:
        self.tenant_context.require("workflow.execute")
        serializer = WorkflowStartSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        definition = WorkflowDefinition.objects.filter(
            company=self.tenant_context.company,
            code=definition_code,
            is_active=True,
        ).first()
        if not definition:
            raise NotFound("Resource not found")
        request_id, _, _ = request_metadata(request._request)
        try:
            instance = start_workflow(
                definition=definition,
                subject_type=serializer.validated_data["subject_type"],
                subject_public_id=serializer.validated_data["subject_public_id"],
                actor_public_id=self.tenant_context.principal.user.public_id,
                correlation_id=request_id,
            )
        except DjangoValidationError as exc:
            raise ValidationError(exc.messages) from exc
        instance = WorkflowInstance.objects.select_related(
            "definition", "workflow_version"
        ).get(pk=instance.pk)
        return Response(_instance_response(instance), status=201)


class WorkflowTransitionView(TenantScopedAPIView):
    def post(self, request: Request, instance_id: uuid.UUID) -> Response:
        self.tenant_context.require("workflow.execute")
        serializer = WorkflowTransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        request_id, _, _ = request_metadata(request._request)
        try:
            result = request_transition(
                instance_public_id=instance_id,
                company_public_id=self.tenant_context.company.public_id,
                transition_code=serializer.validated_data["transition_code"],
                expected_version=serializer.validated_data["expected_version"],
                actor_public_id=self.tenant_context.principal.user.public_id,
                permission_codes=self.tenant_context.permission_codes(),
                correlation_id=request_id,
                comment=serializer.validated_data.get("comment", ""),
            )
        except DjangoPermissionDenied as exc:
            raise PermissionDenied("Permission denied") from exc
        except DjangoValidationError as exc:
            raise ValidationError(exc.messages) from exc
        instance = WorkflowInstance.objects.select_related(
            "definition", "workflow_version"
        ).get(pk=result.instance.pk)
        body: dict[str, object] = {"instance": _instance_response(instance)}
        if result.approval_task:
            body["approval"] = _approval_response(result.approval_task)
            return Response(body, status=202)
        return Response(body)


class UnifiedApprovalCenterView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        return Response(approval_center_items(tenant_context=self.tenant_context))


class ApprovalInboxView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        permission_codes = self.tenant_context.permission_codes()
        role_public_ids = self.tenant_context.role_public_ids()
        actor_public_id = self.tenant_context.principal.user.public_id
        role_scope = Q(assigned_role_public_id__isnull=True)
        if role_public_ids:
            role_scope |= Q(assigned_role_public_id__in=role_public_ids)
        approvals = (
            ApprovalTask.objects.filter(
                company=self.tenant_context.company,
                status=ApprovalTask.Status.PENDING,
                approval_permission_code__in=permission_codes,
            )
            .filter(
                Q(assigned_user_public_id__isnull=True)
                | Q(assigned_user_public_id=actor_public_id)
            )
            .filter(role_scope)
            .select_related("workflow_instance")
            .order_by("due_at", "created_at")[:100]
        )
        return Response({"items": [_approval_response(item) for item in approvals]})


class ApprovalDecisionView(TenantScopedAPIView):
    def post(self, request: Request, approval_id: uuid.UUID) -> Response:
        serializer = ApprovalDecisionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        request_id, _, _ = request_metadata(request._request)
        try:
            approval = decide_approval(
                approval_public_id=approval_id,
                company_public_id=self.tenant_context.company.public_id,
                approved=serializer.validated_data["approved"],
                actor_public_id=self.tenant_context.principal.user.public_id,
                permission_codes=self.tenant_context.permission_codes(),
                role_public_ids=self.tenant_context.role_public_ids(),
                correlation_id=request_id,
                comment=serializer.validated_data.get("comment", ""),
            )
        except DjangoPermissionDenied as exc:
            raise PermissionDenied("Permission denied") from exc
        except DjangoValidationError as exc:
            raise ValidationError(exc.messages) from exc
        return Response(_approval_response(approval))


class WorkflowDefinitionCreateView(TenantScopedAPIView):
    def post(self, request: Request) -> Response:
        self.tenant_context.require("workflow.manage")
        serializer = WorkflowDefinitionCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        definition = WorkflowDefinition.objects.create(
            company=self.tenant_context.company,
            code=serializer.validated_data["code"],
            name=serializer.validated_data["name"],
            description=serializer.validated_data.get("description", ""),
        )
        return Response(
            {
                "public_id": str(definition.public_id),
                "code": definition.code,
                "name": definition.name,
            },
            status=201,
        )


class WorkflowVersionCreateView(TenantScopedAPIView):
    def post(self, request: Request, definition_id: uuid.UUID) -> Response:
        self.tenant_context.require("workflow.manage")
        serializer = WorkflowVersionCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        definition = WorkflowDefinition.objects.filter(
            public_id=definition_id,
            company=self.tenant_context.company,
            is_active=True,
        ).first()
        if not definition:
            raise NotFound("Resource not found")
        current = definition.versions.order_by("-version").first()
        version = WorkflowVersion(
            definition=definition,
            version=1 if current is None else current.version + 1,
            initial_state_code=serializer.validated_data["initial_state_code"],
            states=serializer.validated_data["states"],
            transitions=serializer.validated_data["transitions"],
            created_by_public_id=self.tenant_context.principal.user.public_id,
        )
        try:
            validate_workflow(version)
            version.full_clean()
            version.save()
        except DjangoValidationError as exc:
            raise ValidationError(exc.messages) from exc
        return Response(
            {
                "public_id": str(version.public_id),
                "definition_code": definition.code,
                "version": version.version,
                "status": version.status,
            },
            status=201,
        )


class WorkflowVersionPublishView(TenantScopedAPIView):
    def post(self, request: Request, version_id: uuid.UUID) -> Response:
        self.tenant_context.require("workflow.publish")
        request_id, _, _ = request_metadata(request._request)
        try:
            version = publish_workflow_version(
                version_public_id=version_id,
                company_public_id=self.tenant_context.company.public_id,
                actor_public_id=self.tenant_context.principal.user.public_id,
                correlation_id=request_id,
            )
        except DjangoValidationError as exc:
            raise ValidationError(exc.messages) from exc
        return Response(
            {
                "public_id": str(version.public_id),
                "definition_code": version.definition.code,
                "version": version.version,
                "status": version.status,
                "checksum": version.checksum,
            }
        )
