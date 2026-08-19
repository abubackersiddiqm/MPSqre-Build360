
from __future__ import annotations

import uuid

from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils import timezone
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from modules.communication.models import CommunicationRequest
from modules.design.models import DesignDocument, DesignVersion
from modules.estimation.models import BoqItem, EstimateVersion
from modules.files.application.services import governed_download_url
from modules.files.models import FileObject, FileVersion
from modules.finance.models import Invoice
from modules.identity.application.tokens import AccessPrincipal
from modules.platform.actors import request_actor
from modules.platform.audit import request_metadata
from modules.portal.api.serializers import (
    DirectGrantSerializer,
    GrantRevokeSerializer,
    InvitationAcceptSerializer,
    InvitationCreateSerializer,
    InvitationDeliverySerializer,
    ShareCreateSerializer,
)
from modules.portal.application.services import (
    accept_invitation_by_id_for_user,
    accept_invitation_for_user,
    create_direct_grant,
    create_invitation,
    create_share,
    grants_for_user,
    portal_summary,
    queue_invitation_communication,
    revoke_grant,
    shares_for_user,
)
from modules.portal.models import PortalAccessGrant, PortalInvitation, PortalShare
from modules.procurement.models import PurchaseOrder, PurchaseOrderLine
from modules.projects.models import DeliveryStage, Project, ProjectTask
from modules.tenant.api.base import TenantScopedAPIView


def _validation(exc: DjangoValidationError) -> ValidationError:
    return ValidationError(exc.message_dict if hasattr(exc, "message_dict") else exc.messages)


def _invite(item: PortalInvitation, token: str | None = None) -> dict[str, object]:
    delivery = (
        CommunicationRequest.objects.filter(
            company=item.company,
            subject_type="portal_invitation",
            subject_public_id=item.public_id,
        )
        .order_by("-created_at")
        .first()
    )
    result: dict[str, object] = {
        "public_id": str(item.public_id),
        "email": item.email,
        "portal_type": item.portal_type,
        "scope_type": item.scope_type,
        "scope_public_id": str(item.scope_public_id) if item.scope_public_id else None,
        "permission_codes": item.permission_codes,
        "status": item.status,
        "expires_at": item.expires_at,
        "accepted_at": item.accepted_at,
        "version": item.version,
        "delivery": (
            {
                "public_id": str(delivery.public_id),
                "channel": delivery.channel,
                "status": delivery.status,
                "sent_at": delivery.sent_at,
                "delivered_at": delivery.delivered_at,
                "suppression_reason": delivery.suppression_reason,
                "created_at": delivery.created_at,
            }
            if delivery
            else None
        ),
    }
    if token:
        result["acceptance_token"] = token
    return result


def _grant(item: PortalAccessGrant) -> dict[str, object]:
    return {
        "public_id": str(item.public_id),
        "user_public_id": str(item.user_public_id),
        "portal_type": item.portal_type,
        "scope_type": item.scope_type,
        "scope_public_id": str(item.scope_public_id) if item.scope_public_id else None,
        "permission_codes": item.permission_codes,
        "effective_from": item.effective_from,
        "effective_to": item.effective_to,
        "revoked_at": item.revoked_at,
        "revoke_reason": item.revoke_reason,
        "version": item.version,
    }


def _share(item: PortalShare) -> dict[str, object]:
    return {
        "public_id": str(item.public_id),
        "grant_public_id": str(item.grant.public_id),
        "entity_type": item.entity_type,
        "entity_public_id": str(item.entity_public_id),
        "access_level": item.access_level,
        "expires_at": item.expires_at,
        "revoked_at": item.revoked_at,
        "version": item.version,
    }


def _recipient_share(item: PortalShare) -> dict[str, object]:
    result = _share(item)
    result["entity"] = None
    if item.entity_type == "estimation.version" and "portal.estimate.view" in item.grant.permission_codes:
        version = (
            EstimateVersion.objects.select_related("estimate__project", "stage")
            .filter(
                company=item.company,
                public_id=item.entity_public_id,
                baselined_at__isnull=False,
            )
            .first()
        )
        if version is not None:
            boq = BoqItem.objects.filter(
                company=item.company,
                estimate_version=version,
            ).order_by("sort_order", "item_code")
            result["entity"] = {
                "type": "estimation.version",
                "estimate_code": version.estimate.code,
                "estimate_name": version.estimate.name,
                "project_code": version.estimate.project.code,
                "project_name": version.estimate.project.name,
                "currency": version.estimate.currency,
                "version_number": version.version_number,
                "stage_name": version.stage.name,
                "subtotal": str(version.subtotal),
                "tax_total": str(version.tax_total),
                "grand_total": str(version.grand_total),
                "notes": version.notes,
                "baselined_at": version.baselined_at,
                "boq_items": [
                    {
                        "item_code": row.item_code,
                        "description": row.description,
                        "unit_code": row.unit_code,
                        "quantity": str(row.quantity),
                        "rate": str(row.rate),
                        "amount": str(row.amount),
                        "tax_amount": str(row.tax_amount),
                        "total_amount": str(row.total_amount),
                    }
                    for row in boq
                ],
            }

    if item.entity_type == "project" and "portal.project.view" in item.grant.permission_codes:
        project = (
            Project.objects.select_related("stage")
            .filter(
                company=item.company,
                public_id=item.entity_public_id,
                archived_at__isnull=True,
            )
            .first()
        )
        if project is not None:
            tasks = ProjectTask.objects.select_related("stage").filter(
                company=item.company,
                project=project,
            )
            task_count = tasks.count()
            completed_tasks = tasks.filter(
                stage__outcome__in=[
                    DeliveryStage.Outcome.COMPLETE,
                    DeliveryStage.Outcome.CANCELLED,
                ]
            ).count()
            overdue_tasks = (
                tasks.filter(planned_end_date__lt=timezone.localdate())
                .exclude(
                    stage__outcome__in=[
                        DeliveryStage.Outcome.COMPLETE,
                        DeliveryStage.Outcome.CANCELLED,
                    ]
                )
                .count()
            )
            progress_values = list(tasks.values_list("progress_percent", flat=True))
            progress_percent = (
                int(sum(progress_values) / len(progress_values))
                if progress_values
                else 0
            )
            issued_design_versions = None
            if "portal.document.view" in item.grant.permission_codes:
                issued_design_versions = DesignVersion.objects.filter(
                    company=item.company,
                    document__project=project,
                    issued_at__isnull=False,
                ).count()
            result["entity"] = {
                "type": "project",
                "project_code": project.code,
                "project_name": project.name,
                "stage_name": project.stage.name,
                "planned_start_date": project.planned_start_date,
                "planned_end_date": project.planned_end_date,
                "actual_start_date": project.actual_start_date,
                "actual_end_date": project.actual_end_date,
                "progress_percent": progress_percent,
                "task_count": task_count,
                "completed_tasks": completed_tasks,
                "overdue_tasks": overdue_tasks,
                "issued_design_versions": issued_design_versions,
                "updated_at": project.updated_at,
            }

    if item.entity_type == "design.document" and "portal.document.view" in item.grant.permission_codes:
        document = (
            DesignDocument.objects.select_related("project")
            .filter(
                company=item.company,
                public_id=item.entity_public_id,
                archived_at__isnull=True,
            )
            .first()
        )
        if document is not None:
            version = (
                DesignVersion.objects.select_related("stage")
                .filter(
                    company=item.company,
                    document=document,
                    issued_at__isnull=False,
                    superseded_at__isnull=True,
                )
                .order_by("-version_number")
                .first()
            )
            file_meta = None
            if version and version.file_object_public_id:
                file_object = FileObject.objects.filter(
                    company=item.company,
                    public_id=version.file_object_public_id,
                    status=FileObject.Status.ACTIVE,
                ).first()
                clean_version = (
                    FileVersion.objects.filter(
                        file_object=file_object,
                        upload_status=FileVersion.UploadStatus.FINALIZED,
                        scan_status=FileVersion.ScanStatus.CLEAN,
                    ).order_by("-version").first()
                    if file_object
                    else None
                )
                if file_object and clean_version:
                    file_meta = {
                        "file_public_id": str(file_object.public_id),
                        "original_name": clean_version.original_name,
                        "content_type": clean_version.content_type,
                        "size_bytes": clean_version.actual_size_bytes or clean_version.expected_size_bytes,
                    }
            result["entity"] = {
                "type": "design.document",
                "project_code": document.project.code,
                "project_name": document.project.name,
                "document_number": document.document_number,
                "title": document.title,
                "discipline_code": document.discipline_code,
                "document_type_code": document.document_type_code,
                "description": document.description,
                "revision_code": version.revision_code if version else None,
                "version_number": version.version_number if version else None,
                "stage_name": version.stage.name if version else None,
                "issued_at": version.issued_at if version else None,
                "file": file_meta,
            }

    if item.entity_type == "finance.invoice" and "portal.invoice.view" in item.grant.permission_codes:
        invoice = (
            Invoice.objects.select_related("project", "stage")
            .filter(
                company=item.company,
                public_id=item.entity_public_id,
                reversed_at__isnull=True,
            )
            .first()
        )
        if invoice is not None:
            if item.grant.portal_type == "client" and invoice.invoice_type != Invoice.InvoiceType.CLIENT:
                invoice = None
        if invoice is not None:
            result["entity"] = {
                "type": "finance.invoice",
                "project_code": invoice.project.code,
                "project_name": invoice.project.name,
                "invoice_number": invoice.invoice_number,
                "invoice_type": invoice.invoice_type,
                "counterparty_name": invoice.counterparty_name,
                "stage_name": invoice.stage.name,
                "currency": invoice.currency,
                "invoice_date": invoice.invoice_date,
                "due_date": invoice.due_date,
                "net_amount": str(invoice.net_amount),
                "tax_amount": str(invoice.tax_amount),
                "gross_amount": str(invoice.gross_amount),
                "outstanding_amount": str(invoice.outstanding_amount),
                "posted_at": invoice.posted_at,
            }

    if (
        item.entity_type == "procurement.purchase_order"
        and item.grant.portal_type == "vendor"
        and "portal.purchase_order.view" in item.grant.permission_codes
    ):
        order = (
            PurchaseOrder.objects.select_related("purchase_request__project", "vendor", "stage")
            .filter(company=item.company, public_id=item.entity_public_id)
            .first()
        )
        if order is not None and item.grant.scope_type == "vendor":
            if order.vendor.public_id != item.grant.scope_public_id:
                order = None
        if order is not None:
            lines = PurchaseOrderLine.objects.filter(
                company=item.company,
                purchase_order=order,
            ).order_by("line_number")
            result["entity"] = {
                "type": "procurement.purchase_order",
                "project_code": order.purchase_request.project.code if order.purchase_request.project else None,
                "project_name": order.purchase_request.project.name if order.purchase_request.project else None,
                "po_number": order.po_number,
                "vendor_name": order.vendor.display_name,
                "stage_name": order.stage.name,
                "currency": order.currency,
                "total_amount": str(order.total_amount),
                "issued_at": order.issued_at,
                "lines": [
                    {
                        "line_number": row.line_number,
                        "description": row.description,
                        "quantity_ordered": str(row.quantity_ordered),
                        "quantity_received": str(row.quantity_received),
                        "unit_code": row.unit_code,
                        "unit_rate": str(row.unit_rate),
                    }
                    for row in lines
                ],
            }

    return result


class PortalSummaryView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("portal.dashboard.read")
        return Response(portal_summary(self.tenant_context.company))


class InvitationListCreateView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("portal.invitation.read")
        items = PortalInvitation.objects.filter(
            company=self.tenant_context.company,
        ).order_by("-created_at")[:300]
        return Response({"items": [_invite(item) for item in items]})

    def post(self, request: Request) -> Response:
        self.tenant_context.require("portal.invitation.manage")
        serializer = InvitationCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item, token = create_invitation(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        return Response(_invite(item, token), status=201)


class InvitationAcceptView(APIView):
    def post(self, request: Request) -> Response:
        serializer = InvitationAcceptSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if not isinstance(request.auth, AccessPrincipal):
            raise ValidationError("An authenticated session is required")
        request_id, ip_address, user_agent = request_metadata(request)
        try:
            values = dict(serializer.validated_data)
            invitation_public_id = values.get("invitation_public_id")
            if invitation_public_id:
                company, grant = accept_invitation_by_id_for_user(
                    user=request.auth.user,
                    invitation_public_id=invitation_public_id,
                    request_id=request_id,
                    ip_address=ip_address,
                    user_agent=user_agent,
                )
            else:
                company, grant = accept_invitation_for_user(
                    user=request.auth.user,
                    token=(values.get("token") or "").strip(),
                    request_id=request_id,
                    ip_address=ip_address,
                    user_agent=user_agent,
                )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        return Response({
            "company": {
                "public_id": str(company.public_id),
                "code": company.code,
                "display_name": company.display_name,
            },
            "grant": _grant(grant),
        })


class InvitationDeliveryView(TenantScopedAPIView):
    def post(self, request: Request, public_id: uuid.UUID) -> Response:
        self.tenant_context.require("portal.invitation.manage")
        self.tenant_context.require("communication.request.create")
        serializer = InvitationDeliverySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        dispatch_now = serializer.validated_data["dispatch_now"]
        if dispatch_now:
            self.tenant_context.require("communication.request.dispatch")
        try:
            communication = queue_invitation_communication(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                invitation_public_id=public_id,
                dispatch_now=dispatch_now,
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        return Response(
            {
                "public_id": str(communication.public_id),
                "channel": communication.channel,
                "status": communication.status,
                "sent_at": communication.sent_at,
                "delivered_at": communication.delivered_at,
                "suppression_reason": communication.suppression_reason,
                "token_embedded": False,
            }
        )


class GrantListCreateView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("portal.grant.read")
        items = PortalAccessGrant.objects.filter(
            company=self.tenant_context.company,
        ).order_by("-created_at")[:300]
        return Response({"items": [_grant(item) for item in items]})

    def post(self, request: Request) -> Response:
        self.tenant_context.require("portal.grant.manage")
        serializer = DirectGrantSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = create_direct_grant(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        return Response(_grant(item), status=201)


class GrantRevokeView(TenantScopedAPIView):
    def post(self, request: Request, public_id: uuid.UUID) -> Response:
        self.tenant_context.require("portal.grant.revoke")
        serializer = GrantRevokeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = revoke_grant(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                grant_public_id=public_id,
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        return Response(_grant(item))


class ShareListCreateView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("portal.share.read")
        items = PortalShare.objects.select_related("grant").filter(
            company=self.tenant_context.company,
        ).order_by("-created_at")[:300]
        return Response({"items": [_share(item) for item in items]})

    def post(self, request: Request) -> Response:
        self.tenant_context.require("portal.share.manage")
        serializer = ShareCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = create_share(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        return Response(_share(item), status=201)


class MyPortalGrantsView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        items = grants_for_user(
            self.tenant_context.company,
            self.tenant_context.principal.user.public_id,
        )
        return Response({"items": [_grant(item) for item in items]})


class MyPortalSharesView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        items = shares_for_user(
            self.tenant_context.company,
            self.tenant_context.principal.user.public_id,
        )
        return Response({"items": [_recipient_share(item) for item in items]})



class PortalSharedFileDownloadView(TenantScopedAPIView):
    def get(self, request: Request, share_public_id: uuid.UUID) -> Response:
        allowed_shares = shares_for_user(
            self.tenant_context.company,
            self.tenant_context.principal.user.public_id,
        )
        share = next((item for item in allowed_shares if item.public_id == share_public_id), None)
        if share is None or share.entity_type != "design.document":
            raise NotFound("Shared file was not found")
        if "portal.document.view" not in share.grant.permission_codes:
            raise NotFound("Shared file was not found")
        document = DesignDocument.objects.filter(
            company=self.tenant_context.company,
            public_id=share.entity_public_id,
            archived_at__isnull=True,
        ).first()
        if document is None:
            raise NotFound("Shared file was not found")
        version = (
            DesignVersion.objects.filter(
                company=self.tenant_context.company,
                document=document,
                issued_at__isnull=False,
                superseded_at__isnull=True,
                file_object_public_id__isnull=False,
            )
            .order_by("-version_number")
            .first()
        )
        if version is None:
            raise NotFound("Shared file was not found")
        file_object = FileObject.objects.filter(
            company=self.tenant_context.company,
            public_id=version.file_object_public_id,
            status=FileObject.Status.ACTIVE,
        ).first()
        if file_object is None:
            raise NotFound("Shared file was not found")
        try:
            _, url = governed_download_url(file_object=file_object)
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        return Response({"download_url": url})
