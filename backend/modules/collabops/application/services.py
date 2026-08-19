from __future__ import annotations

import uuid
from typing import Any

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from modules.accessops.application.services import create_invitation
from modules.collabops.models import (
    CollaborationDecision,
    CollaborationItem,
    CollaborationMessage,
    CollaborationSubmission,
    PartnerContact,
    PartnerOrganization,
    ProjectAccessGrant,
)
from modules.identity.models import Permission, Role, RolePermission
from modules.platform.audit import AuditRecord, append_audit
from modules.platform.events import EventRecord, append_event
from modules.tenant.models import Company, Membership
from modules.workops.models import Project, ProjectSite

EXTERNAL_ROLE_PERMISSIONS = {
    "EXTERNAL_COLLABORATOR": [
        "collaboration.portal",
        "collaboration.submit",
        "collaboration.message",
    ],
    "EXTERNAL_APPROVER": [
        "collaboration.portal",
        "collaboration.submit",
        "collaboration.message",
        "collaboration.approve",
    ],
}


def _code(value: str) -> str:
    return value.strip().upper().replace(" ", "_")


def _record(
    *,
    company: Company,
    action: str,
    event_type: str,
    entity_type: str,
    entity_public_id: uuid.UUID,
    actor_public_id: uuid.UUID,
    correlation_id: uuid.UUID,
    version: int,
    after: dict[str, Any],
    before: dict[str, Any] | None = None,
) -> None:
    append_audit(
        AuditRecord(
            action=action,
            entity_type=entity_type,
            entity_public_id=entity_public_id,
            actor_public_id=actor_public_id,
            company_public_id=company.public_id,
            request_id=correlation_id,
            correlation_id=correlation_id,
            before=before or {},
            after=after,
        )
    )
    append_event(
        EventRecord(
            event_type=event_type,
            aggregate_type=entity_type,
            aggregate_public_id=entity_public_id,
            aggregate_version=version,
            company_public_id=company.public_id,
            correlation_id=correlation_id,
            payload=after,
        )
    )


def ensure_external_role(company: Company, *, can_approve: bool) -> Role:
    code = "EXTERNAL_APPROVER" if can_approve else "EXTERNAL_COLLABORATOR"
    role = (
        Role.objects.filter(company_public_id=company.public_id, code=code, retired_at__isnull=True)
        .order_by("-version")
        .first()
    )
    if role is not None:
        return role
    latest = Role.objects.filter(company_public_id=company.public_id, code=code).order_by("-version").first()
    role = Role.objects.create(
        company_public_id=company.public_id,
        code=code,
        name="External Approver" if can_approve else "External Collaborator",
        version=(latest.version + 1) if latest else 1,
        effective_from=timezone.now(),
    )
    permissions = Permission.objects.filter(code__in=EXTERNAL_ROLE_PERMISSIONS[code])
    RolePermission.objects.bulk_create(
        [RolePermission(role=role, permission=permission) for permission in permissions],
        ignore_conflicts=True,
    )
    return role


@transaction.atomic
def create_partner(
    *,
    company: Company,
    actor_public_id: uuid.UUID,
    correlation_id: uuid.UUID,
    **data: Any,
) -> PartnerOrganization:
    data["code"] = _code(data["code"])
    data["organization_type_code"] = _code(data.get("organization_type_code", "VENDOR"))
    partner = PartnerOrganization(company=company, **data)
    partner.full_clean()
    partner.save()
    _record(
        company=company,
        action="collaboration.partner.created",
        event_type="collaboration.partner_created",
        entity_type="partner_organization",
        entity_public_id=partner.public_id,
        actor_public_id=actor_public_id,
        correlation_id=correlation_id,
        version=partner.version,
        after={"code": partner.code, "type": partner.organization_type_code},
    )
    return partner


@transaction.atomic
def invite_partner_contact(
    *,
    company: Company,
    organization: PartnerOrganization,
    actor_public_id: uuid.UUID,
    correlation_id: uuid.UUID,
    full_name: str,
    email: str,
    mobile: str = "",
    job_title: str = "",
    can_approve: bool = False,
    is_primary: bool = False,
) -> tuple[PartnerContact, str]:
    if organization.company_id != company.id:
        raise ValidationError("Partner organization cannot cross companies")
    normalized_email = email.strip().lower()
    if PartnerContact.objects.filter(company=company, email__iexact=normalized_email).exists():
        raise ValidationError({"email": "This partner contact already exists"})
    role = ensure_external_role(company, can_approve=can_approve)
    invitation, raw_token = create_invitation(
        company=company,
        email=normalized_email,
        display_name=full_name,
        invitation_type_code="EXTERNAL_PARTNER",
        role_public_ids=[role.public_id],
        employee_number="",
        job_title=job_title,
        invited_by_public_id=actor_public_id,
        correlation_id=correlation_id,
        ttl_hours=72,
    )
    contact = PartnerContact(
        company=company,
        organization=organization,
        full_name=full_name.strip(),
        email=normalized_email,
        mobile=mobile.strip(),
        job_title=job_title.strip(),
        can_approve=can_approve,
        is_primary=is_primary,
        invitation_public_id=invitation.public_id,
        invited_at=timezone.now(),
    )
    contact.full_clean()
    contact.save()
    _record(
        company=company,
        action="collaboration.contact.invited",
        event_type="collaboration.contact_invited",
        entity_type="partner_contact",
        entity_public_id=contact.public_id,
        actor_public_id=actor_public_id,
        correlation_id=correlation_id,
        version=contact.version,
        after={"organization": str(organization.public_id), "email": normalized_email, "can_approve": can_approve},
    )
    return contact, raw_token


def resolve_partner_contact(company: Company, membership: Membership) -> PartnerContact:
    contact = PartnerContact.objects.filter(company=company, membership=membership, suspended_at__isnull=True).first()
    if contact is None:
        contact = PartnerContact.objects.filter(
            company=company,
            email__iexact=membership.user.email,
            suspended_at__isnull=True,
        ).first()
        if contact is not None and contact.membership_id is None:
            contact.membership = membership
            contact.status_code = "ACTIVE"
            contact.activated_at = timezone.now()
            contact.version += 1
            contact.save(update_fields=["membership", "status_code", "activated_at", "version", "updated_at"])
    if contact is None:
        raise ValidationError({"partner_profile": "This login is not linked to an external partner contact."})
    return contact


@transaction.atomic
def grant_project_access(
    *,
    company: Company,
    contact: PartnerContact,
    project: Project,
    site: ProjectSite | None,
    scopes: list[str],
    effective_from,
    effective_to,
    actor_public_id: uuid.UUID,
    correlation_id: uuid.UUID,
) -> ProjectAccessGrant:
    grant = ProjectAccessGrant(
        company=company,
        contact=contact,
        project=project,
        site=site,
        scopes=sorted({_code(scope) for scope in scopes if scope.strip()}),
        effective_from=effective_from,
        effective_to=effective_to,
        granted_by_public_id=actor_public_id,
    )
    grant.full_clean()
    grant.save()
    _record(
        company=company,
        action="collaboration.project_access.granted",
        event_type="collaboration.project_access_granted",
        entity_type="project_access_grant",
        entity_public_id=grant.public_id,
        actor_public_id=actor_public_id,
        correlation_id=correlation_id,
        version=grant.version,
        after={"contact": str(contact.public_id), "project": str(project.public_id), "scopes": grant.scopes},
    )
    return grant


@transaction.atomic
def create_collaboration_item(
    *,
    company: Company,
    organization: PartnerOrganization,
    project: Project,
    site: ProjectSite | None,
    assigned_contact: PartnerContact | None,
    actor_public_id: uuid.UUID,
    correlation_id: uuid.UUID,
    **data: Any,
) -> CollaborationItem:
    item = CollaborationItem(
        company=company,
        organization=organization,
        project=project,
        site=site,
        assigned_contact=assigned_contact,
        created_by_public_id=actor_public_id,
        item_type_code=_code(data.pop("item_type_code", "GENERAL")),
        priority_code=_code(data.pop("priority_code", "NORMAL")),
        **data,
    )
    item.full_clean()
    item.save()
    _record(
        company=company,
        action="collaboration.item.created",
        event_type="collaboration.item_created",
        entity_type="collaboration_item",
        entity_public_id=item.public_id,
        actor_public_id=actor_public_id,
        correlation_id=correlation_id,
        version=item.version,
        after={"reference": item.reference, "type": item.item_type_code, "project": str(project.public_id)},
    )
    return item


def active_grant(contact: PartnerContact, item: CollaborationItem, scope: str) -> ProjectAccessGrant | None:
    now = timezone.now()
    grants = ProjectAccessGrant.objects.filter(
        company=item.company,
        contact=contact,
        project=item.project,
        status_code="ACTIVE",
        revoked_at__isnull=True,
        effective_from__lte=now,
    ).filter(models.Q(effective_to__isnull=True) | models.Q(effective_to__gt=now))
    if item.site_id:
        grants = grants.filter(models.Q(site__isnull=True) | models.Q(site=item.site))
    requested = _code(scope)
    for grant in grants:
        normalized = {_code(value) for value in grant.scopes}
        if "ALL" in normalized or requested in normalized or item.item_type_code in normalized:
            return grant
    return None


@transaction.atomic
def submit_partner_response(
    *,
    company: Company,
    contact: PartnerContact,
    item: CollaborationItem,
    actor_public_id: uuid.UUID,
    correlation_id: uuid.UUID,
    summary: str,
    data: dict[str, Any],
    attachment_references: list[dict[str, Any]],
) -> CollaborationSubmission:
    if item.organization_id != contact.organization_id:
        raise ValidationError("The collaboration item is not assigned to this partner")
    if active_grant(contact, item, "SUBMIT") is None:
        raise ValidationError("No active project access grant permits this submission")
    revision = (item.submissions.order_by("-revision").values_list("revision", flat=True).first() or 0) + 1
    submission = CollaborationSubmission(
        company=company,
        item=item,
        contact=contact,
        revision=revision,
        summary=summary.strip(),
        data=data,
        attachment_references=attachment_references,
        submitted_at=timezone.now(),
    )
    submission.full_clean()
    submission.save()
    item.status_code = "SUBMITTED"
    item.version += 1
    item.save(update_fields=["status_code", "version", "updated_at"])
    _record(
        company=company,
        action="collaboration.submission.created",
        event_type="collaboration.submission_created",
        entity_type="collaboration_submission",
        entity_public_id=submission.public_id,
        actor_public_id=actor_public_id,
        correlation_id=correlation_id,
        version=submission.version,
        after={"item": str(item.public_id), "revision": revision},
    )
    return submission


@transaction.atomic
def decide_collaboration_item(
    *,
    company: Company,
    item: CollaborationItem,
    submission: CollaborationSubmission | None,
    decision_code: str,
    notes: str,
    actor_public_id: uuid.UUID,
    correlation_id: uuid.UUID,
    decided_by_type: str = "INTERNAL",
) -> CollaborationDecision:
    code = _code(decision_code)
    allowed = {"APPROVED", "REJECTED", "REVISION_REQUIRED", "ACKNOWLEDGED"}
    if code not in allowed:
        raise ValidationError({"decision_code": "Unsupported decision"})
    decision = CollaborationDecision(
        company=company,
        item=item,
        submission=submission,
        decision_code=code,
        notes=notes.strip(),
        decided_by_public_id=actor_public_id,
        decided_by_type=_code(decided_by_type),
        decided_at=timezone.now(),
    )
    decision.full_clean()
    decision.save()
    item.status_code = code
    if code in {"APPROVED", "REJECTED", "ACKNOWLEDGED"}:
        item.closed_at = timezone.now()
    item.version += 1
    item.save(update_fields=["status_code", "closed_at", "version", "updated_at"])
    if submission:
        submission.status_code = code
        submission.reviewed_at = timezone.now()
        submission.reviewed_by_public_id = actor_public_id
        submission.version += 1
        submission.save(update_fields=["status_code", "reviewed_at", "reviewed_by_public_id", "version", "updated_at"])
    _record(
        company=company,
        action="collaboration.item.decided",
        event_type="collaboration.item_decided",
        entity_type="collaboration_decision",
        entity_public_id=decision.public_id,
        actor_public_id=actor_public_id,
        correlation_id=correlation_id,
        version=decision.version,
        after={"item": str(item.public_id), "decision": code, "actor_type": decision.decided_by_type},
    )
    return decision


@transaction.atomic
def post_collaboration_message(
    *,
    company: Company,
    item: CollaborationItem,
    contact: PartnerContact | None,
    sender_type_code: str,
    sender_public_id: uuid.UUID,
    body: str,
    attachment_references: list[dict[str, Any]],
    is_internal: bool,
    correlation_id: uuid.UUID,
) -> CollaborationMessage:
    if not body.strip():
        raise ValidationError({"body": "Message body is required"})
    if contact is not None:
        if item.organization_id != contact.organization_id:
            raise ValidationError("Message partner does not match the item")
        if active_grant(contact, item, "MESSAGE") is None:
            raise ValidationError("No active project access grant permits messaging")
        is_internal = False
    message = CollaborationMessage(
        company=company,
        item=item,
        contact=contact,
        sender_type_code=_code(sender_type_code),
        sender_public_id=sender_public_id,
        body=body.strip(),
        attachment_references=attachment_references,
        is_internal=is_internal,
        sent_at=timezone.now(),
    )
    message.full_clean()
    message.save()
    _record(
        company=company,
        action="collaboration.message.posted",
        event_type="collaboration.message_posted",
        entity_type="collaboration_message",
        entity_public_id=message.public_id,
        actor_public_id=sender_public_id,
        correlation_id=correlation_id,
        version=1,
        after={"item": str(item.public_id), "sender_type": message.sender_type_code, "internal": is_internal},
    )
    return message


# Avoid a module-level import cycle while keeping query construction explicit.
from django.db import models  # noqa: E402
