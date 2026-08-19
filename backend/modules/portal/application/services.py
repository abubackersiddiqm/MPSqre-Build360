
from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import timedelta
from typing import Any

from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.utils import timezone

from modules.communication.application.services import create_request, dispatch_request
from modules.communication.models import CommunicationChannel, CommunicationRequest, MessageTemplate
from modules.crm.models import Customer
from modules.design.models import DesignDocument
from modules.estimation.models import EstimateVersion
from modules.finance.models import Invoice
from modules.identity.models import User
from modules.platform.actors import RequestActor
from modules.platform.audit import AuditRecord, append_audit
from modules.platform.events import EventRecord, append_event
from modules.portal.models import (
    PortalAccessGrant,
    PortalInvitation,
    PortalScopeType,
    PortalShare,
    PortalType,
)
from modules.procurement.models import PurchaseOrder, RequestForQuotation
from modules.projects.models import Project
from modules.tenant.models import Company, CompanyBrandProfile, Membership, TenantDomain
from modules.vendor.models import VendorProfile

PORTAL_PERMISSION_CODES = {
    PortalType.CLIENT: {
        "portal.dashboard.view",
        "portal.project.view",
        "portal.document.view",
        "portal.invoice.view",
        "portal.estimate.view",
        "portal.comment.create",
    },
    PortalType.VENDOR: {
        "portal.dashboard.view",
        "portal.rfq.view",
        "portal.quotation.submit",
        "portal.purchase_order.view",
        "portal.invoice.view",
    },
}


def validate_permission_codes(portal_type: str, permission_codes: list[str]) -> list[str]:
    normalized = sorted({str(code).strip().lower() for code in permission_codes if str(code).strip()})
    allowed = PORTAL_PERMISSION_CODES.get(portal_type)
    if allowed is None:
        raise ValidationError("Portal type is invalid")
    if not normalized:
        raise ValidationError("At least one portal permission is required")
    unsupported = sorted(set(normalized) - allowed)
    if unsupported:
        raise ValidationError({"permission_codes": [f"Unsupported portal permissions: {', '.join(unsupported)}"]})
    return normalized


def _shared_entity(company: Company, entity_type: str, entity_public_id: uuid.UUID) -> tuple[object, uuid.UUID | None]:
    normalized_type = entity_type.strip().lower()
    if normalized_type == "project":
        item = Project.objects.filter(company=company, public_id=entity_public_id).first()
        return item, item.public_id if item else None
    if normalized_type == "customer":
        item = Customer.objects.filter(company=company, public_id=entity_public_id).first()
        return item, None
    if normalized_type == "vendor":
        item = VendorProfile.objects.filter(company=company, public_id=entity_public_id).first()
        return item, None
    if normalized_type == "design.document":
        item = DesignDocument.objects.select_related("project").filter(
            company=company, public_id=entity_public_id
        ).first()
        return item, item.project.public_id if item else None
    if normalized_type == "estimation.version":
        item = EstimateVersion.objects.select_related("estimate__project").filter(
            company=company, public_id=entity_public_id, baselined_at__isnull=False
        ).first()
        return item, item.estimate.project.public_id if item else None
    if normalized_type == "finance.invoice":
        item = Invoice.objects.select_related("project").filter(
            company=company, public_id=entity_public_id
        ).first()
        return item, item.project.public_id if item else None
    if normalized_type == "procurement.rfq":
        item = RequestForQuotation.objects.select_related("purchase_request__project").filter(
            company=company, public_id=entity_public_id
        ).first()
        project_id = item.purchase_request.project.public_id if item and item.purchase_request.project else None
        return item, project_id
    if normalized_type == "procurement.purchase_order":
        item = PurchaseOrder.objects.select_related("purchase_request__project").filter(
            company=company, public_id=entity_public_id
        ).first()
        project_id = item.purchase_request.project.public_id if item and item.purchase_request.project else None
        return item, project_id
    raise ValidationError("Portal share entity type is not supported")


def validate_share_scope(
    *,
    company: Company,
    grant: PortalAccessGrant,
    entity_type: str,
    entity_public_id: uuid.UUID,
) -> None:
    item, project_public_id = _shared_entity(company, entity_type, entity_public_id)
    if item is None:
        raise ValidationError("Portal share entity was not found")
    normalized_type = entity_type.strip().lower()
    if normalized_type == "estimation.version" and "portal.estimate.view" not in grant.permission_codes:
        raise ValidationError("This client grant does not permit estimate viewing")
    if normalized_type == "design.document" and "portal.document.view" not in grant.permission_codes:
        raise ValidationError("This portal grant does not permit document viewing")
    if normalized_type == "finance.invoice":
        if "portal.invoice.view" not in grant.permission_codes:
            raise ValidationError("This portal grant does not permit invoice viewing")
        invoice = item
        if grant.portal_type == PortalType.CLIENT and invoice.invoice_type != Invoice.InvoiceType.CLIENT:
            raise ValidationError("Client portals can only receive client invoices")
    if normalized_type == "procurement.purchase_order":
        if grant.portal_type != PortalType.VENDOR:
            raise ValidationError("Purchase orders can only be shared to vendor portals")
        if "portal.purchase_order.view" not in grant.permission_codes:
            raise ValidationError("This vendor grant does not permit purchase-order viewing")
        order = item
        if grant.scope_type == PortalScopeType.VENDOR and order.vendor.public_id != grant.scope_public_id:
            raise ValidationError("Purchase order is outside the granted vendor scope")
    if grant.scope_type == PortalScopeType.PROJECT and project_public_id != grant.scope_public_id:
        raise ValidationError("Portal share is outside the granted project scope")
    if grant.scope_type == PortalScopeType.CUSTOMER:
        if entity_type.strip().lower() != "customer" or entity_public_id != grant.scope_public_id:
            raise ValidationError("Portal share is outside the granted customer scope")
    if grant.scope_type == PortalScopeType.VENDOR:
        if normalized_type == "procurement.purchase_order":
            return
        if normalized_type != "vendor" or entity_public_id != grant.scope_public_id:
            raise ValidationError("Portal share is outside the granted vendor scope")


def _record(
    *,
    company: Company,
    actor: RequestActor,
    action: str,
    entity_type: str,
    entity_public_id: uuid.UUID,
    version: int,
    payload: dict[str, Any],
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


def validate_scope(company: Company, scope_type: str, scope_public_id: uuid.UUID | None) -> None:
    if scope_type == PortalScopeType.COMPANY:
        if scope_public_id is not None:
            raise ValidationError("Company scope cannot include a scope ID")
        return
    model_map = {
        PortalScopeType.PROJECT: Project,
        PortalScopeType.CUSTOMER: Customer,
        PortalScopeType.VENDOR: VendorProfile,
    }
    model = model_map.get(scope_type)
    if model is None or scope_public_id is None:
        raise ValidationError("Portal scope is invalid")
    if not model.objects.filter(company=company, public_id=scope_public_id).exists():
        raise ValidationError("Portal scope was not found")


def portal_summary(company: Company) -> dict[str, int]:
    now = timezone.now()
    return {
        "pending_invitations": PortalInvitation.objects.filter(
            company=company,
            status=PortalInvitation.Status.PENDING,
            expires_at__gt=now,
        ).count(),
        "active_grants": PortalAccessGrant.objects.filter(
            company=company,
            revoked_at__isnull=True,
            effective_from__lte=now,
        ).filter(effective_to__isnull=True).count()
        + PortalAccessGrant.objects.filter(
            company=company,
            revoked_at__isnull=True,
            effective_from__lte=now,
            effective_to__gt=now,
        ).count(),
        "active_shares": PortalShare.objects.filter(
            company=company,
            revoked_at__isnull=True,
        ).count(),
    }


@transaction.atomic
def create_invitation(
    *,
    company: Company,
    actor: RequestActor,
    email: str,
    portal_type: str,
    scope_type: str,
    scope_public_id: uuid.UUID | None,
    permission_codes: list[str],
    expires_in_days: int = 7,
) -> tuple[PortalInvitation, str]:
    validate_scope(company, scope_type, scope_public_id)
    normalized_permissions = validate_permission_codes(portal_type, permission_codes)
    if PortalInvitation.objects.filter(
        company=company,
        email=email.strip().lower(),
        portal_type=portal_type,
        scope_type=scope_type,
        scope_public_id=scope_public_id,
        status=PortalInvitation.Status.PENDING,
        expires_at__gt=timezone.now(),
    ).exists():
        raise ValidationError("An active invitation already exists for this portal scope")
    if expires_in_days < 1 or expires_in_days > 30:
        raise ValidationError("Portal invitations must expire within 1 to 30 days")
    token = secrets.token_urlsafe(32)
    invitation = PortalInvitation(
        company=company,
        email=email.strip().lower(),
        portal_type=portal_type,
        scope_type=scope_type,
        scope_public_id=scope_public_id,
        permission_codes=normalized_permissions,
        token_digest=hashlib.sha256(token.encode()).hexdigest(),
        invited_by_public_id=actor.user_public_id,
        expires_at=timezone.now() + timedelta(days=expires_in_days),
    )
    invitation.full_clean()
    invitation.save()
    _record(
        company=company,
        actor=actor,
        action="portal.invitation.created",
        entity_type="portal_invitation",
        entity_public_id=invitation.public_id,
        version=invitation.version,
        payload={
            "portal_type": invitation.portal_type,
            "scope_type": invitation.scope_type,
            "expires_at": invitation.expires_at.isoformat(),
        },
    )
    return invitation, token


def _validate_pending_invitation_for_user(*, invitation: PortalInvitation, user: User) -> None:
    if invitation.status != PortalInvitation.Status.PENDING:
        raise ValidationError("Portal invitation is invalid")
    if invitation.expires_at <= timezone.now():
        invitation.status = PortalInvitation.Status.EXPIRED
        invitation.version += 1
        invitation.save(update_fields=["status", "version", "updated_at"])
        raise ValidationError("Portal invitation has expired")
    if user.email.lower() != invitation.email.lower():
        raise ValidationError("Invitation email does not match the authenticated user")


def _accept_invitation_record(
    *,
    invitation: PortalInvitation,
    user: User,
    actor: RequestActor,
) -> PortalAccessGrant:
    _validate_pending_invitation_for_user(invitation=invitation, user=user)
    validate_scope(invitation.company, invitation.scope_type, invitation.scope_public_id)
    grant = PortalAccessGrant.objects.filter(
        company=invitation.company,
        user_public_id=user.public_id,
        portal_type=invitation.portal_type,
        scope_type=invitation.scope_type,
        scope_public_id=invitation.scope_public_id,
        revoked_at__isnull=True,
    ).first()
    if grant is None:
        grant = PortalAccessGrant.objects.create(
            company=invitation.company,
            user_public_id=user.public_id,
            portal_type=invitation.portal_type,
            scope_type=invitation.scope_type,
            scope_public_id=invitation.scope_public_id,
            permission_codes=invitation.permission_codes,
            effective_from=timezone.now(),
            granted_by_public_id=invitation.invited_by_public_id,
        )
    invitation.status = PortalInvitation.Status.ACCEPTED
    invitation.accepted_by_public_id = user.public_id
    invitation.accepted_at = timezone.now()
    invitation.version += 1
    invitation.save()
    _record(
        company=invitation.company,
        actor=actor,
        action="portal.invitation.accepted",
        entity_type="portal_access_grant",
        entity_public_id=grant.public_id,
        version=grant.version,
        payload={"portal_type": grant.portal_type, "scope_type": grant.scope_type},
    )
    return grant


@transaction.atomic
def accept_invitation(
    *,
    company: Company,
    actor: RequestActor,
    token: str,
) -> PortalAccessGrant:
    digest = hashlib.sha256(token.encode()).hexdigest()
    invitation = (
        PortalInvitation.objects.select_for_update()
        .filter(company=company, token_digest=digest)
        .first()
    )
    if invitation is None:
        raise ValidationError("Portal invitation is invalid")
    user = User.objects.filter(public_id=actor.user_public_id, is_active=True).first()
    if user is None:
        raise ValidationError("Portal user was not found")
    return _accept_invitation_record(invitation=invitation, user=user, actor=actor)


@transaction.atomic
def accept_invitation_by_id_for_user(
    *,
    user: User,
    invitation_public_id: uuid.UUID,
    request_id: uuid.UUID,
    ip_address: str | None,
    user_agent: str,
) -> tuple[Company, PortalAccessGrant]:
    invitation = (
        PortalInvitation.objects.select_for_update()
        .select_related("company")
        .filter(public_id=invitation_public_id)
        .first()
    )
    if invitation is None:
        raise ValidationError("Portal invitation is invalid")
    # Validate identity before creating a company membership.
    _validate_pending_invitation_for_user(invitation=invitation, user=user)
    membership, _ = Membership.objects.get_or_create(
        company=invitation.company,
        user=user,
        defaults={"effective_from": timezone.now()},
    )
    if membership.suspended_at or membership.terminated_at:
        raise ValidationError("Portal membership is inactive")
    actor = RequestActor(
        user_public_id=user.public_id,
        membership_public_id=membership.public_id,
        request_id=request_id,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    grant = _accept_invitation_record(invitation=invitation, user=user, actor=actor)
    return invitation.company, grant


def _portal_invitation_url(invitation: PortalInvitation) -> str:
    domain = (
        TenantDomain.objects.filter(
            company=invitation.company,
            status=TenantDomain.Status.ACTIVE,
            is_primary=True,
        ).first()
        or TenantDomain.objects.filter(
            company=invitation.company,
            status=TenantDomain.Status.ACTIVE,
        ).order_by("-is_primary", "domain").first()
    )
    path = f"/portal/accept?invitation={invitation.public_id}"
    return f"https://{domain.domain}{path}" if domain else path


def _portal_invitation_template(company: Company) -> MessageTemplate:
    locale = (company.locale or "en").strip()
    template = (
        MessageTemplate.objects.filter(
            company=company,
            channel=CommunicationChannel.EMAIL,
            purpose_code="portal_invitation",
            status=MessageTemplate.Status.PUBLISHED,
            locale=locale,
        ).order_by("-version").first()
        or MessageTemplate.objects.filter(
            company=company,
            channel=CommunicationChannel.EMAIL,
            purpose_code="portal_invitation",
            status=MessageTemplate.Status.PUBLISHED,
        ).order_by("-version").first()
    )
    if template is None:
        raise ValidationError(
            "Publish an email template with purpose_code portal_invitation before delivery."
        )
    return template


@transaction.atomic
def queue_invitation_communication(
    *,
    company: Company,
    actor: RequestActor,
    invitation_public_id: uuid.UUID,
    dispatch_now: bool = False,
) -> CommunicationRequest:
    invitation = PortalInvitation.objects.select_for_update().filter(
        company=company,
        public_id=invitation_public_id,
    ).first()
    if invitation is None:
        raise ValidationError("Portal invitation was not found")
    if invitation.status != PortalInvitation.Status.PENDING:
        raise ValidationError("Only pending portal invitations can be delivered")
    if invitation.expires_at <= timezone.now():
        invitation.status = PortalInvitation.Status.EXPIRED
        invitation.version += 1
        invitation.save(update_fields=["status", "version", "updated_at"])
        raise ValidationError("Portal invitation has expired")

    template = _portal_invitation_template(company)
    brand = CompanyBrandProfile.objects.filter(company=company).first()
    variables = {
        "company_name": company.display_name,
        "product_name": brand.product_name if brand and brand.product_name else company.display_name,
        "invited_email": invitation.email,
        "portal_type": invitation.portal_type,
        "scope_type": invitation.scope_type,
        "accept_url": _portal_invitation_url(invitation),
        "expires_at": invitation.expires_at.isoformat(),
        "support_email": brand.support_email if brand else "",
    }
    unsupported = sorted(set(template.variable_names) - set(variables))
    if unsupported:
        raise ValidationError(
            f"Portal invitation template declares unsupported variables: {', '.join(unsupported)}"
        )

    communication = create_request(
        company=company,
        actor=actor,
        template_public_id=template.public_id,
        subject_type="portal_invitation",
        subject_public_id=invitation.public_id,
        recipient_reference_type="portal_invitation",
        recipient_reference_public_id=invitation.public_id,
        template_variables=variables,
        idempotency_key=f"portal-invite:{invitation.public_id}:{template.public_id}:v{template.version}",
    )
    if dispatch_now:
        communication = dispatch_request(
            company=company,
            actor=actor,
            request_public_id=communication.public_id,
        )
    _record(
        company=company,
        actor=actor,
        action="portal.invitation.communication.queued",
        entity_type="portal_invitation",
        entity_public_id=invitation.public_id,
        version=invitation.version,
        payload={
            "communication_request_public_id": str(communication.public_id),
            "status": communication.status,
            "channel": communication.channel,
            "token_embedded": False,
        },
    )
    return communication


@transaction.atomic
def create_direct_grant(
    *,
    company: Company,
    actor: RequestActor,
    user_public_id: uuid.UUID,
    portal_type: str,
    scope_type: str,
    scope_public_id: uuid.UUID | None,
    permission_codes: list[str],
    effective_to: Any = None,
) -> PortalAccessGrant:
    validate_scope(company, scope_type, scope_public_id)
    normalized_permissions = validate_permission_codes(portal_type, permission_codes)
    if not User.objects.filter(public_id=user_public_id, is_active=True).exists():
        raise ValidationError("Portal user was not found")
    grant = PortalAccessGrant(
        company=company,
        user_public_id=user_public_id,
        portal_type=portal_type,
        scope_type=scope_type,
        scope_public_id=scope_public_id,
        permission_codes=normalized_permissions,
        effective_from=timezone.now(),
        effective_to=effective_to,
        granted_by_public_id=actor.user_public_id,
    )
    grant.full_clean()
    grant.save()
    _record(
        company=company,
        actor=actor,
        action="portal.grant.created",
        entity_type="portal_access_grant",
        entity_public_id=grant.public_id,
        version=grant.version,
        payload={"portal_type": grant.portal_type, "scope_type": grant.scope_type},
    )
    return grant


@transaction.atomic
def revoke_grant(
    *,
    company: Company,
    actor: RequestActor,
    grant_public_id: uuid.UUID,
    expected_version: int,
    reason: str,
) -> PortalAccessGrant:
    grant = PortalAccessGrant.objects.select_for_update().filter(
        company=company,
        public_id=grant_public_id,
    ).first()
    if grant is None:
        raise ValidationError("Portal grant was not found")
    if grant.version != expected_version:
        raise ValidationError("Portal grant changed; refresh before retrying")
    if grant.revoked_at is None:
        grant.revoked_at = timezone.now()
        grant.revoked_by_public_id = actor.user_public_id
        grant.revoke_reason = reason.strip()
        grant.version += 1
        grant.save()
        PortalShare.objects.filter(company=company, grant=grant, revoked_at__isnull=True).update(
            revoked_at=timezone.now(),
            revoked_by_public_id=actor.user_public_id,
            version=models.F("version") + 1,
        )
    _record(
        company=company,
        actor=actor,
        action="portal.grant.revoked",
        entity_type="portal_access_grant",
        entity_public_id=grant.public_id,
        version=grant.version,
        payload={"reason": grant.revoke_reason},
    )
    return grant


@transaction.atomic
def create_share(
    *,
    company: Company,
    actor: RequestActor,
    grant_public_id: uuid.UUID,
    entity_type: str,
    entity_public_id: uuid.UUID,
    access_level: str,
    expires_at: Any = None,
) -> PortalShare:
    grant = PortalAccessGrant.objects.filter(
        company=company,
        public_id=grant_public_id,
        revoked_at__isnull=True,
    ).first()
    if grant is None:
        raise ValidationError("Active portal grant was not found")
    now = timezone.now()
    if grant.effective_from > now or (grant.effective_to and grant.effective_to <= now):
        raise ValidationError("Portal grant is not currently effective")
    if expires_at and expires_at <= now:
        raise ValidationError("Portal share expiry must be in the future")
    validate_share_scope(
        company=company,
        grant=grant,
        entity_type=entity_type,
        entity_public_id=entity_public_id,
    )
    share = PortalShare(
        company=company,
        grant=grant,
        entity_type=entity_type.strip().lower(),
        entity_public_id=entity_public_id,
        access_level=access_level,
        created_by_public_id=actor.user_public_id,
        expires_at=expires_at,
    )
    share.full_clean()
    share.save()
    _record(
        company=company,
        actor=actor,
        action="portal.share.created",
        entity_type="portal_share",
        entity_public_id=share.public_id,
        version=share.version,
        payload={"entity_type": share.entity_type, "access_level": share.access_level},
    )
    return share


def grants_for_user(company: Company, user_public_id: uuid.UUID) -> list[PortalAccessGrant]:
    now = timezone.now()
    return list(
        PortalAccessGrant.objects.filter(
            company=company,
            user_public_id=user_public_id,
            revoked_at__isnull=True,
            effective_from__lte=now,
        )
        .filter(models.Q(effective_to__isnull=True) | models.Q(effective_to__gt=now))
        .order_by("portal_type", "scope_type")
    )


def shares_for_user(company: Company, user_public_id: uuid.UUID) -> list[PortalShare]:
    now = timezone.now()
    return list(
        PortalShare.objects.select_related("grant")
        .filter(
            company=company,
            grant__user_public_id=user_public_id,
            grant__revoked_at__isnull=True,
            grant__effective_from__lte=now,
            revoked_at__isnull=True,
        )
        .filter(models.Q(grant__effective_to__isnull=True) | models.Q(grant__effective_to__gt=now))
        .filter(models.Q(expires_at__isnull=True) | models.Q(expires_at__gt=now))
        .order_by("-created_at")
    )


@transaction.atomic
def accept_invitation_for_user(
    *,
    user: User,
    token: str,
    request_id: uuid.UUID,
    ip_address: str | None,
    user_agent: str,
) -> tuple[Company, PortalAccessGrant]:
    digest = hashlib.sha256(token.encode()).hexdigest()
    invitation = (
        PortalInvitation.objects.select_for_update()
        .select_related("company")
        .filter(token_digest=digest)
        .first()
    )
    if invitation is None:
        raise ValidationError("Portal invitation is invalid")
    _validate_pending_invitation_for_user(invitation=invitation, user=user)
    membership, _ = Membership.objects.get_or_create(
        company=invitation.company,
        user=user,
        defaults={"effective_from": timezone.now()},
    )
    if membership.suspended_at or membership.terminated_at:
        raise ValidationError("Portal membership is inactive")
    actor = RequestActor(
        user_public_id=user.public_id,
        membership_public_id=membership.public_id,
        request_id=request_id,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    grant = accept_invitation(
        company=invitation.company,
        actor=actor,
        token=token,
    )
    return invitation.company, grant
