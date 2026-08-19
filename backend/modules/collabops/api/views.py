from __future__ import annotations

import uuid

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.request import Request
from rest_framework.response import Response

from modules.collabops.application.selectors import internal_overview, partner_overview
from modules.collabops.application.services import (
    active_grant,
    create_collaboration_item,
    create_partner,
    decide_collaboration_item,
    grant_project_access,
    invite_partner_contact,
    post_collaboration_message,
    resolve_partner_contact,
    submit_partner_response,
)
from modules.collabops.models import (
    CollaborationItem,
    CollaborationSubmission,
    PartnerContact,
    PartnerOrganization,
    ProjectAccessGrant,
)
from modules.tenant.api.base import TenantScopedAPIView
from modules.workops.models import Project, ProjectSite

from .serializers import (
    CollaborationItemSerializer,
    DecisionSerializer,
    MessageSerializer,
    PartnerContactInviteSerializer,
    PartnerOrganizationSerializer,
    ProjectGrantSerializer,
    SubmissionSerializer,
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


class InternalCollaborationAPIView(TenantScopedAPIView):
    required_permission = "collaboration.view"

    def initial(self, request: Request, *args: object, **kwargs: object) -> None:
        super().initial(request, *args, **kwargs)
        self.tenant_context.require(self.required_permission)

    @property
    def actor(self) -> uuid.UUID:
        return self.tenant_context.principal.user.public_id


class OverviewView(InternalCollaborationAPIView):
    def get(self, request: Request) -> Response:
        payload = internal_overview(self.tenant_context.company)
        payload["capabilities"] = {
            "can_manage": self.tenant_context.can("collaboration.manage"),
            "can_invite": self.tenant_context.can("collaboration.invite"),
            "can_grant": self.tenant_context.can("collaboration.grant"),
            "can_request": self.tenant_context.can("collaboration.request"),
            "can_approve": self.tenant_context.can("collaboration.approve"),
            "can_message": self.tenant_context.can("collaboration.message"),
            "can_export": self.tenant_context.can("collaboration.export"),
        }
        return Response(payload)


class PartnerCreateView(InternalCollaborationAPIView):
    required_permission = "collaboration.manage"

    def post(self, request: Request) -> Response:
        serializer = PartnerOrganizationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            partner = create_partner(
                company=self.tenant_context.company,
                actor_public_id=self.actor,
                correlation_id=correlation_id(request),
                **serializer.validated_data,
            )
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(partner.public_id), "code": partner.code, "status": partner.status_code}, status=201)


class ContactInviteView(InternalCollaborationAPIView):
    required_permission = "collaboration.invite"

    def post(self, request: Request, partner_id: uuid.UUID) -> Response:
        partner = find(PartnerOrganization, company=self.tenant_context.company, public_id=partner_id, message="Partner not found")
        serializer = PartnerContactInviteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            contact, raw_token = invite_partner_contact(
                company=self.tenant_context.company,
                organization=partner,
                actor_public_id=self.actor,
                correlation_id=correlation_id(request),
                **serializer.validated_data,
            )
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response(
            {
                "public_id": str(contact.public_id),
                "status": contact.status_code,
                "invitation_url": f"/accept-invitation?token={raw_token}",
                "token_returned_once": True,
            },
            status=201,
        )


class GrantCreateView(InternalCollaborationAPIView):
    required_permission = "collaboration.grant"

    def post(self, request: Request) -> Response:
        serializer = ProjectGrantSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        contact = find(PartnerContact, company=self.tenant_context.company, public_id=data.pop("contact_public_id"), message="Partner contact not found")
        project = find(Project, company=self.tenant_context.company, public_id=data.pop("project_public_id"), message="Project not found")
        site_id = data.pop("site_public_id", None)
        site = find(ProjectSite, company=self.tenant_context.company, public_id=site_id, message="Project site not found") if site_id else None
        try:
            grant = grant_project_access(
                company=self.tenant_context.company,
                contact=contact,
                project=project,
                site=site,
                actor_public_id=self.actor,
                correlation_id=correlation_id(request),
                **data,
            )
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(grant.public_id), "status": grant.status_code, "scopes": grant.scopes}, status=201)


class ItemCreateView(InternalCollaborationAPIView):
    required_permission = "collaboration.request"

    def post(self, request: Request) -> Response:
        serializer = CollaborationItemSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        partner = find(PartnerOrganization, company=self.tenant_context.company, public_id=data.pop("organization_public_id"), message="Partner not found")
        project = find(Project, company=self.tenant_context.company, public_id=data.pop("project_public_id"), message="Project not found")
        site_id = data.pop("site_public_id", None)
        contact_id = data.pop("assigned_contact_public_id", None)
        site = find(ProjectSite, company=self.tenant_context.company, public_id=site_id, message="Project site not found") if site_id else None
        contact = find(PartnerContact, company=self.tenant_context.company, public_id=contact_id, message="Partner contact not found") if contact_id else None
        try:
            item = create_collaboration_item(
                company=self.tenant_context.company,
                organization=partner,
                project=project,
                site=site,
                assigned_contact=contact,
                actor_public_id=self.actor,
                correlation_id=correlation_id(request),
                **data,
            )
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(item.public_id), "reference": item.reference, "status": item.status_code}, status=201)


class InternalDecisionView(InternalCollaborationAPIView):
    required_permission = "collaboration.approve"

    def post(self, request: Request, item_id: uuid.UUID) -> Response:
        item = find(CollaborationItem, company=self.tenant_context.company, public_id=item_id, message="Collaboration item not found")
        serializer = DecisionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        submission_id = data.pop("submission_public_id", None)
        submission = find(CollaborationSubmission, company=self.tenant_context.company, public_id=submission_id, message="Submission not found") if submission_id else None
        try:
            decision = decide_collaboration_item(
                company=self.tenant_context.company,
                item=item,
                submission=submission,
                actor_public_id=self.actor,
                correlation_id=correlation_id(request),
                **data,
            )
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(decision.public_id), "decision": decision.decision_code, "item_status": item.status_code})


class InternalMessageView(InternalCollaborationAPIView):
    required_permission = "collaboration.message"

    def post(self, request: Request, item_id: uuid.UUID) -> Response:
        item = find(CollaborationItem, company=self.tenant_context.company, public_id=item_id, message="Collaboration item not found")
        serializer = MessageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            message = post_collaboration_message(
                company=self.tenant_context.company,
                item=item,
                contact=None,
                sender_type_code="INTERNAL",
                sender_public_id=self.actor,
                correlation_id=correlation_id(request),
                **serializer.validated_data,
            )
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(message.public_id), "sent_at": message.sent_at}, status=201)


class PartnerAPIView(TenantScopedAPIView):
    required_permission = "collaboration.portal"

    def initial(self, request: Request, *args: object, **kwargs: object) -> None:
        super().initial(request, *args, **kwargs)
        self.tenant_context.require(self.required_permission)
        try:
            self.partner_contact = resolve_partner_contact(self.tenant_context.company, self.tenant_context.membership)
        except DjangoValidationError as error:
            raise translate(error) from error

    @property
    def actor(self) -> uuid.UUID:
        return self.tenant_context.principal.user.public_id

    def partner_item(self, public_id: uuid.UUID) -> CollaborationItem:
        item = CollaborationItem.objects.filter(
            company=self.tenant_context.company,
            public_id=public_id,
            organization=self.partner_contact.organization,
        ).filter(Q(assigned_contact__isnull=True) | Q(assigned_contact=self.partner_contact)).first()
        if item is None:
            raise NotFound("Collaboration item not found")
        now = timezone.now()
        grants = ProjectAccessGrant.objects.filter(
            company=self.tenant_context.company,
            contact=self.partner_contact,
            project=item.project,
            status_code="ACTIVE",
            revoked_at__isnull=True,
            effective_from__lte=now,
        ).filter(Q(effective_to__isnull=True) | Q(effective_to__gt=now))
        if item.site_id:
            grants = grants.filter(Q(site__isnull=True) | Q(site=item.site))
        if not grants.exists():
            raise NotFound("Collaboration item not found")
        return item


class PartnerOverviewView(PartnerAPIView):
    def get(self, request: Request) -> Response:
        return Response(partner_overview(self.partner_contact))


class PartnerSubmissionView(PartnerAPIView):
    required_permission = "collaboration.submit"

    def post(self, request: Request, item_id: uuid.UUID) -> Response:
        item = self.partner_item(item_id)
        serializer = SubmissionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            submission = submit_partner_response(
                company=self.tenant_context.company,
                contact=self.partner_contact,
                item=item,
                actor_public_id=self.actor,
                correlation_id=correlation_id(request),
                **serializer.validated_data,
            )
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(submission.public_id), "revision": submission.revision, "status": submission.status_code}, status=201)


class PartnerDecisionView(PartnerAPIView):
    required_permission = "collaboration.approve"

    def post(self, request: Request, item_id: uuid.UUID) -> Response:
        if not self.partner_contact.can_approve:
            raise ValidationError("This partner contact is not authorized to decide collaboration items")
        item = self.partner_item(item_id)
        if active_grant(self.partner_contact, item, "APPROVE") is None:
            raise ValidationError("No active project access grant permits external approval")
        serializer = DecisionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        submission_id = data.pop("submission_public_id", None)
        submission = find(CollaborationSubmission, company=self.tenant_context.company, public_id=submission_id, message="Submission not found") if submission_id else None
        try:
            decision = decide_collaboration_item(
                company=self.tenant_context.company,
                item=item,
                submission=submission,
                actor_public_id=self.actor,
                correlation_id=correlation_id(request),
                decided_by_type="EXTERNAL",
                **data,
            )
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(decision.public_id), "decision": decision.decision_code})


class PartnerMessageView(PartnerAPIView):
    required_permission = "collaboration.message"

    def post(self, request: Request, item_id: uuid.UUID) -> Response:
        item = self.partner_item(item_id)
        serializer = MessageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        data.pop("is_internal", None)
        try:
            message = post_collaboration_message(
                company=self.tenant_context.company,
                item=item,
                contact=self.partner_contact,
                sender_type_code="EXTERNAL",
                sender_public_id=self.actor,
                is_internal=False,
                correlation_id=correlation_id(request),
                **data,
            )
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(message.public_id), "sent_at": message.sent_at}, status=201)
