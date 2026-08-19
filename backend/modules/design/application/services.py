from __future__ import annotations

import uuid
from typing import Any

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from modules.design.models import (
    DesignDocument,
    DesignIssue,
    DesignReview,
    DesignTransmittal,
    DesignVersion,
    TransmittalItem,
)
from modules.platform.actors import RequestActor
from modules.platform.audit import AuditRecord, append_audit
from modules.platform.events import EventRecord, append_event
from modules.projects.application.services import (
    initial_stage,
    resolve_stage,
)
from modules.projects.models import DeliveryStage, Project
from modules.tenant.models import Company, Membership


def _audit(
    *,
    actor: RequestActor,
    company: Company,
    action: str,
    entity_type: str,
    entity_public_id: uuid.UUID,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
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
            before=before or {},
            after=after or {},
            reason_code=reason_code,
        )
    )


def _event(
    *,
    actor: RequestActor,
    company: Company,
    event_type: str,
    aggregate_type: str,
    aggregate_public_id: uuid.UUID,
    aggregate_version: int,
    payload: dict[str, Any],
) -> None:
    append_event(
        EventRecord(
            event_type=event_type,
            aggregate_type=aggregate_type,
            aggregate_public_id=aggregate_public_id,
            aggregate_version=aggregate_version,
            company_public_id=company.public_id,
            correlation_id=actor.request_id,
            payload=payload,
        )
    )


def _project(company: Company, public_id: uuid.UUID) -> Project:
    project = Project.objects.filter(company=company, public_id=public_id).first()
    if project is None:
        raise ValidationError("Project was not found")
    return project


def _membership(company: Company, public_id: uuid.UUID) -> None:
    if not Membership.objects.filter(
        company=company,
        public_id=public_id,
        suspended_at__isnull=True,
        terminated_at__isnull=True,
    ).exists():
        raise ValidationError("Reviewer membership was not found")


@transaction.atomic
def create_document(
    *,
    company: Company,
    actor: RequestActor,
    project_public_id: uuid.UUID,
    document_number: str,
    title: str,
    discipline_code: str,
    document_type_code: str,
    description: str = "",
) -> DesignDocument:
    project = _project(company, project_public_id)
    document = DesignDocument(
        company=company,
        project=project,
        document_number=document_number.strip().upper(),
        title=title.strip(),
        discipline_code=discipline_code.strip().upper(),
        document_type_code=document_type_code.strip().upper(),
        description=description.strip(),
        created_by_public_id=actor.user_public_id,
    )
    document.full_clean()
    document.save()
    _audit(
        actor=actor,
        company=company,
        action="design.document.created",
        entity_type="design_document",
        entity_public_id=document.public_id,
        after={
            "project_public_id": str(project.public_id),
            "document_number": document.document_number,
        },
    )
    _event(
        actor=actor,
        company=company,
        event_type="design.document_created",
        aggregate_type="design_document",
        aggregate_public_id=document.public_id,
        aggregate_version=document.version,
        payload={"project_public_id": str(project.public_id)},
    )
    return document


@transaction.atomic
def create_version(
    *,
    company: Company,
    actor: RequestActor,
    document_public_id: uuid.UUID,
    revision_code: str,
    description: str = "",
    file_object_public_id: uuid.UUID | None = None,
    checksum_sha256: str = "",
) -> DesignVersion:
    document = DesignDocument.objects.select_for_update().filter(
        company=company,
        public_id=document_public_id,
    ).first()
    if document is None:
        raise ValidationError("Design document was not found")
    latest = (
        DesignVersion.objects.filter(company=company, document=document)
        .order_by("-version_number")
        .first()
    )
    version_number = 1 if latest is None else latest.version_number + 1
    version = DesignVersion(
        company=company,
        document=document,
        version_number=version_number,
        revision_code=revision_code.strip().upper(),
        stage=initial_stage(company, DeliveryStage.EntityType.DESIGN_VERSION),
        description=description.strip(),
        file_object_public_id=file_object_public_id,
        checksum_sha256=checksum_sha256.strip().lower(),
        created_by_public_id=actor.user_public_id,
    )
    version.full_clean()
    version.save()
    _audit(
        actor=actor,
        company=company,
        action="design.version.created",
        entity_type="design_version",
        entity_public_id=version.public_id,
        after={
            "document_public_id": str(document.public_id),
            "version_number": version_number,
            "stage": version.stage.code,
        },
    )
    _event(
        actor=actor,
        company=company,
        event_type="design.version_created",
        aggregate_type="design_version",
        aggregate_public_id=version.public_id,
        aggregate_version=version.version,
        payload={
            "document_public_id": str(document.public_id),
            "version_number": version_number,
        },
    )
    return version


@transaction.atomic
def transition_version(
    *,
    company: Company,
    actor: RequestActor,
    version_public_id: uuid.UUID,
    target_stage_public_id: uuid.UUID,
    expected_version: int,
    reason_code: str = "",
) -> DesignVersion:
    version = (
        DesignVersion.objects.select_for_update()
        .select_related("stage", "document")
        .filter(company=company, public_id=version_public_id)
        .first()
    )
    if version is None:
        raise ValidationError("Design version was not found")
    if version.version != expected_version:
        raise ValidationError("Design version has changed; refresh before retrying")
    target = resolve_stage(
        company,
        target_stage_public_id,
        DeliveryStage.EntityType.DESIGN_VERSION,
    )
    if target.code not in version.stage.allowed_next_codes:
        raise ValidationError("The requested design transition is not permitted")
    old_code = version.stage.code
    now = timezone.now()
    version.stage = target
    version.version += 1
    if target.outcome == DeliveryStage.Outcome.REVIEW:
        version.submitted_at = now
    elif target.outcome == DeliveryStage.Outcome.APPROVED:
        version.approved_at = now
    elif target.outcome == DeliveryStage.Outcome.ISSUED:
        version.issued_at = now
        DesignVersion.objects.filter(
            company=company,
            document=version.document,
            issued_at__isnull=False,
            superseded_at__isnull=True,
        ).exclude(pk=version.pk).update(superseded_at=now)
    elif target.outcome == DeliveryStage.Outcome.SUPERSEDED:
        version.superseded_at = now
    version.full_clean()
    version.save()
    _audit(
        actor=actor,
        company=company,
        action="design.version.transitioned",
        entity_type="design_version",
        entity_public_id=version.public_id,
        before={"stage": old_code, "version": expected_version},
        after={"stage": target.code, "version": version.version},
        reason_code=reason_code.strip(),
    )
    _event(
        actor=actor,
        company=company,
        event_type="design.version_transitioned",
        aggregate_type="design_version",
        aggregate_public_id=version.public_id,
        aggregate_version=version.version,
        payload={"from": old_code, "to": target.code},
    )
    return version


@transaction.atomic
def request_review(
    *,
    company: Company,
    actor: RequestActor,
    version_public_id: uuid.UUID,
    reviewer_membership_public_id: uuid.UUID,
) -> DesignReview:
    version = DesignVersion.objects.select_related("stage").filter(
        company=company,
        public_id=version_public_id,
    ).first()
    if version is None:
        raise ValidationError("Design version was not found")
    if version.stage.outcome != DeliveryStage.Outcome.REVIEW:
        raise ValidationError("Design version must be under review before assigning reviewers")
    _membership(company, reviewer_membership_public_id)
    review, _ = DesignReview.objects.get_or_create(
        company=company,
        design_version=version,
        reviewer_membership_public_id=reviewer_membership_public_id,
        defaults={
            "requested_by_public_id": actor.user_public_id,
            "requested_at": timezone.now(),
        },
    )
    _audit(
        actor=actor,
        company=company,
        action="design.review.requested",
        entity_type="design_review",
        entity_public_id=review.public_id,
        after={"design_version_public_id": str(version.public_id)},
    )
    return review


@transaction.atomic
def decide_review(
    *,
    company: Company,
    actor: RequestActor,
    review_public_id: uuid.UUID,
    decision: str,
    comments: str,
    expected_version: int,
) -> DesignReview:
    review = DesignReview.objects.select_for_update().filter(
        company=company,
        public_id=review_public_id,
    ).first()
    if review is None:
        raise ValidationError("Design review was not found")
    if review.version != expected_version:
        raise ValidationError("Design review has changed; refresh before retrying")
    if review.decision != DesignReview.Decision.PENDING:
        raise ValidationError("Design review has already been decided")
    review.decision = decision
    review.comments = comments.strip()
    review.decided_by_public_id = actor.user_public_id
    review.decided_at = timezone.now()
    review.version += 1
    review.full_clean()
    review.save()
    _audit(
        actor=actor,
        company=company,
        action="design.review.decided",
        entity_type="design_review",
        entity_public_id=review.public_id,
        after={"decision": decision, "version": review.version},
    )
    _event(
        actor=actor,
        company=company,
        event_type="design.review_decided",
        aggregate_type="design_review",
        aggregate_public_id=review.public_id,
        aggregate_version=review.version,
        payload={"decision": decision},
    )
    return review


@transaction.atomic
def create_issue(
    *,
    company: Company,
    actor: RequestActor,
    project_public_id: uuid.UUID,
    title: str,
    severity: str,
    description: str = "",
    design_version_public_id: uuid.UUID | None = None,
    assigned_membership_public_id: uuid.UUID | None = None,
    due_at: Any = None,
) -> DesignIssue:
    project = _project(company, project_public_id)
    design_version = None
    if design_version_public_id:
        design_version = DesignVersion.objects.filter(
            company=company,
            public_id=design_version_public_id,
            document__project=project,
        ).first()
        if design_version is None:
            raise ValidationError("Design version was not found for the project")
    if assigned_membership_public_id:
        _membership(company, assigned_membership_public_id)
    issue = DesignIssue(
        company=company,
        project=project,
        design_version=design_version,
        title=title.strip(),
        description=description.strip(),
        severity=severity,
        raised_by_public_id=actor.user_public_id,
        assigned_membership_public_id=assigned_membership_public_id,
        due_at=due_at,
    )
    issue.full_clean()
    issue.save()
    _audit(
        actor=actor,
        company=company,
        action="design.issue.created",
        entity_type="design_issue",
        entity_public_id=issue.public_id,
        after={"project_public_id": str(project.public_id), "severity": issue.severity},
    )
    _event(
        actor=actor,
        company=company,
        event_type="design.issue_created",
        aggregate_type="design_issue",
        aggregate_public_id=issue.public_id,
        aggregate_version=issue.version,
        payload={"project_public_id": str(project.public_id), "severity": issue.severity},
    )
    return issue


@transaction.atomic
def close_issue(
    *,
    company: Company,
    actor: RequestActor,
    issue_public_id: uuid.UUID,
    expected_version: int,
    resolution: str,
) -> DesignIssue:
    issue = DesignIssue.objects.select_for_update().filter(
        company=company,
        public_id=issue_public_id,
    ).first()
    if issue is None:
        raise ValidationError("Design issue was not found")
    if issue.version != expected_version:
        raise ValidationError("Design issue has changed; refresh before retrying")
    if issue.closed_at:
        raise ValidationError("Design issue is already closed")
    issue.closed_at = timezone.now()
    issue.closed_by_public_id = actor.user_public_id
    issue.resolution = resolution.strip()
    issue.version += 1
    issue.full_clean()
    issue.save()
    _audit(
        actor=actor,
        company=company,
        action="design.issue.closed",
        entity_type="design_issue",
        entity_public_id=issue.public_id,
        after={"version": issue.version},
    )
    _event(
        actor=actor,
        company=company,
        event_type="design.issue_closed",
        aggregate_type="design_issue",
        aggregate_public_id=issue.public_id,
        aggregate_version=issue.version,
        payload={"project_public_id": str(issue.project.public_id)},
    )
    return issue


@transaction.atomic
def create_transmittal(
    *,
    company: Company,
    actor: RequestActor,
    project_public_id: uuid.UUID,
    reference: str,
    purpose_code: str,
    recipient: str,
    design_version_public_ids: list[uuid.UUID],
    notes: str = "",
) -> DesignTransmittal:
    project = _project(company, project_public_id)
    versions = list(
        DesignVersion.objects.filter(
            company=company,
            public_id__in=design_version_public_ids,
            document__project=project,
            issued_at__isnull=False,
            superseded_at__isnull=True,
        )
    )
    if len(versions) != len(set(design_version_public_ids)):
        raise ValidationError("All transmittal documents must be current issued versions")
    transmittal = DesignTransmittal(
        company=company,
        project=project,
        reference=reference.strip().upper(),
        purpose_code=purpose_code.strip().upper(),
        recipient=recipient.strip(),
        notes=notes.strip(),
        issued_by_public_id=actor.user_public_id,
        issued_at=timezone.now(),
    )
    transmittal.full_clean()
    transmittal.save()
    TransmittalItem.objects.bulk_create(
        [
            TransmittalItem(
                company=company,
                transmittal=transmittal,
                design_version=version,
            )
            for version in versions
        ]
    )
    _audit(
        actor=actor,
        company=company,
        action="design.transmittal.issued",
        entity_type="design_transmittal",
        entity_public_id=transmittal.public_id,
        after={
            "project_public_id": str(project.public_id),
            "document_count": len(versions),
        },
    )
    _event(
        actor=actor,
        company=company,
        event_type="design.transmittal_issued",
        aggregate_type="design_transmittal",
        aggregate_public_id=transmittal.public_id,
        aggregate_version=1,
        payload={"project_public_id": str(project.public_id), "document_count": len(versions)},
    )
    return transmittal

