from __future__ import annotations

import uuid
from datetime import timedelta
from typing import Any

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Case, F, IntegerField, Q, When
from django.utils import timezone

from modules.platform.audit import AuditRecord, append_audit
from modules.platform.events import EventRecord, append_event
from modules.supportops.models import (
    ChangeRequest,
    CustomerFeedback,
    ImprovementItem,
    KnowledgeArticle,
    ProblemRecord,
    ServiceCatalogItem,
    SupportPolicyVersion,
    SupportTicket,
    TicketInteraction,
)
from modules.tenant.models import Company

DEFAULT_CATALOG = [
    ("ACCESS_SUPPORT", "Access and authentication support", "ACCESS", 60, 480),
    ("APPLICATION_SUPPORT", "Application functionality support", "APPLICATION", 240, 2880),
    ("DATA_SUPPORT", "Data correction and migration support", "DATA", 480, 4320),
    ("INTEGRATION_SUPPORT", "Integration and connector support", "INTEGRATION", 240, 2880),
    ("PRODUCTION_INCIDENT", "Production service incident", "INCIDENT", 30, 240),
]


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


def seed_defaults(company: Company) -> dict[str, int]:
    policy, policy_created = SupportPolicyVersion.objects.get_or_create(
        company=company,
        version=1,
        defaults={
            "status_code": "DRAFT",
            "configuration": {"phase": 36, "release": "v1-service-desk-continuous-improvement"},
        },
    )
    created_count = 0
    for code, name, category, response, resolution in DEFAULT_CATALOG:
        _, created = ServiceCatalogItem.objects.get_or_create(
            company=company,
            code=code,
            defaults={
                "name": name,
                "category_code": category,
                "response_minutes": response,
                "resolution_minutes": resolution,
                "business_hours_only": True,
                "active": True,
            },
        )
        created_count += int(created)
    return {"policy": int(policy_created), "catalog_items": created_count, "policy_version": policy.version}


def _deadlines(company: Company, catalog_item: ServiceCatalogItem | None, created_at=None):
    policy = SupportPolicyVersion.objects.filter(company=company).order_by("-version").first()
    response_minutes = catalog_item.response_minutes if catalog_item else (policy.default_response_minutes if policy else 240)
    resolution_minutes = catalog_item.resolution_minutes if catalog_item else (policy.default_resolution_minutes if policy else 2880)
    base = created_at or timezone.now()
    return base + timedelta(minutes=response_minutes), base + timedelta(minutes=resolution_minutes)


@transaction.atomic
def create_ticket(
    *,
    company: Company,
    actor_public_id: uuid.UUID,
    correlation_id: uuid.UUID,
    catalog_item: ServiceCatalogItem | None = None,
    **data: Any,
) -> SupportTicket:
    response_due_at, resolution_due_at = _deadlines(company, catalog_item)
    ticket = SupportTicket(
        company=company,
        catalog_item=catalog_item,
        created_by_public_id=actor_public_id,
        response_due_at=response_due_at,
        resolution_due_at=resolution_due_at,
        **data,
    )
    ticket.full_clean()
    ticket.save()
    _record(
        company=company,
        action="CREATE",
        event_type="support.ticket.created",
        entity_type="SupportTicket",
        entity_public_id=ticket.public_id,
        actor_public_id=actor_public_id,
        correlation_id=correlation_id,
        version=ticket.version,
        after={"code": ticket.code, "priority": ticket.priority_code, "status": ticket.status_code},
    )
    return ticket


@transaction.atomic
def transition_ticket(
    *,
    ticket: SupportTicket,
    status_code: str,
    expected_version: int,
    actor_public_id: uuid.UUID,
    correlation_id: uuid.UUID,
    assigned_to_public_id: uuid.UUID | None = None,
    resolution_summary: str = "",
) -> SupportTicket:
    ticket = SupportTicket.objects.select_for_update().get(pk=ticket.pk)
    if ticket.version != expected_version:
        raise ValidationError("Support ticket changed. Refresh and retry.")
    allowed = {
        "NEW": {"TRIAGED", "IN_PROGRESS", "CANCELLED"},
        "TRIAGED": {"IN_PROGRESS", "WAITING_CUSTOMER", "WAITING_INTERNAL", "CANCELLED"},
        "IN_PROGRESS": {"WAITING_CUSTOMER", "WAITING_INTERNAL", "RESOLVED", "CANCELLED"},
        "WAITING_CUSTOMER": {"IN_PROGRESS", "RESOLVED", "CANCELLED"},
        "WAITING_INTERNAL": {"IN_PROGRESS", "RESOLVED", "CANCELLED"},
        "RESOLVED": {"CLOSED", "REOPENED"},
        "REOPENED": {"IN_PROGRESS", "WAITING_CUSTOMER", "WAITING_INTERNAL", "RESOLVED"},
        "CLOSED": {"REOPENED"},
        "CANCELLED": set(),
    }
    if status_code not in allowed.get(ticket.status_code, set()):
        raise ValidationError(f"Invalid ticket transition from {ticket.status_code} to {status_code}.")
    if status_code in {"RESOLVED", "CLOSED"} and not resolution_summary.strip() and not ticket.resolution_summary.strip():
        raise ValidationError("Resolution summary is required.")
    before = {"status": ticket.status_code, "version": ticket.version}
    now = timezone.now()
    if assigned_to_public_id is not None:
        ticket.assigned_to_public_id = assigned_to_public_id
    if resolution_summary.strip():
        ticket.resolution_summary = resolution_summary.strip()
    if status_code == "RESOLVED":
        ticket.resolved_at = now
    if status_code == "CLOSED":
        ticket.closed_at = now
    if status_code == "REOPENED":
        ticket.resolved_at = None
        ticket.closed_at = None
    ticket.status_code = status_code
    if ticket.resolution_due_at and ticket.resolution_due_at < now and status_code not in {"CLOSED", "CANCELLED"}:
        ticket.sla_breached = True
    ticket.version += 1
    ticket.full_clean()
    ticket.save()
    _record(
        company=ticket.company,
        action="TRANSITION",
        event_type="support.ticket.transitioned",
        entity_type="SupportTicket",
        entity_public_id=ticket.public_id,
        actor_public_id=actor_public_id,
        correlation_id=correlation_id,
        version=ticket.version,
        before=before,
        after={"code": ticket.code, "status": ticket.status_code, "sla_breached": ticket.sla_breached},
    )
    return ticket


@transaction.atomic
def add_interaction(
    *,
    company: Company,
    ticket: SupportTicket,
    actor_public_id: uuid.UUID,
    correlation_id: uuid.UUID,
    **data: Any,
) -> TicketInteraction:
    if ticket.company_id != company.id:
        raise ValidationError("Ticket interaction cannot cross companies.")
    occurred_at = data.pop("occurred_at", None) or timezone.now()
    interaction = TicketInteraction(
        company=company,
        ticket=ticket,
        actor_public_id=actor_public_id,
        occurred_at=occurred_at,
        **data,
    )
    interaction.full_clean()
    interaction.save()
    if ticket.first_responded_at is None and interaction.interaction_type_code in {"RESPONSE", "COMMENT", "CALL", "EMAIL"}:
        locked = SupportTicket.objects.select_for_update().get(pk=ticket.pk)
        locked.first_responded_at = occurred_at
        if locked.status_code == "NEW":
            locked.status_code = "TRIAGED"
        if locked.response_due_at and occurred_at > locked.response_due_at:
            locked.sla_breached = True
        locked.version += 1
        locked.save(update_fields=["first_responded_at", "status_code", "sla_breached", "version", "updated_at"])
    _record(
        company=company,
        action="CREATE",
        event_type="support.interaction.created",
        entity_type="TicketInteraction",
        entity_public_id=interaction.public_id,
        actor_public_id=actor_public_id,
        correlation_id=correlation_id,
        version=1,
        after={"ticket": ticket.code, "type": interaction.interaction_type_code, "customer_visible": interaction.customer_visible},
    )
    return interaction


@transaction.atomic
def create_problem(*, company: Company, actor_public_id: uuid.UUID, correlation_id: uuid.UUID, **data: Any) -> ProblemRecord:
    problem = ProblemRecord(company=company, created_by_public_id=actor_public_id, **data)
    problem.full_clean()
    problem.save()
    _record(
        company=company, action="CREATE", event_type="support.problem.created", entity_type="ProblemRecord",
        entity_public_id=problem.public_id, actor_public_id=actor_public_id, correlation_id=correlation_id,
        version=problem.version, after={"code": problem.code, "status": problem.status_code, "priority": problem.priority_code},
    )
    return problem


@transaction.atomic
def transition_problem(
    *, problem: ProblemRecord, status_code: str, expected_version: int, actor_public_id: uuid.UUID,
    correlation_id: uuid.UUID, root_cause: str = "", permanent_fix: str = ""
) -> ProblemRecord:
    problem = ProblemRecord.objects.select_for_update().get(pk=problem.pk)
    if problem.version != expected_version:
        raise ValidationError("Problem record changed. Refresh and retry.")
    allowed = {
        "OPEN": {"INVESTIGATING", "CANCELLED"},
        "INVESTIGATING": {"KNOWN_ERROR", "RESOLVED", "CANCELLED"},
        "KNOWN_ERROR": {"RESOLVED", "INVESTIGATING"},
        "RESOLVED": {"CLOSED", "INVESTIGATING"},
        "CLOSED": set(),
        "CANCELLED": set(),
    }
    if status_code not in allowed.get(problem.status_code, set()):
        raise ValidationError(f"Invalid problem transition from {problem.status_code} to {status_code}.")
    if status_code in {"RESOLVED", "CLOSED"} and not (root_cause.strip() or problem.root_cause.strip()):
        raise ValidationError("Root cause is required before resolving a problem.")
    before = {"status": problem.status_code, "version": problem.version}
    if root_cause.strip():
        problem.root_cause = root_cause.strip()
    if permanent_fix.strip():
        problem.permanent_fix = permanent_fix.strip()
    problem.status_code = status_code
    problem.resolved_at = timezone.now() if status_code in {"RESOLVED", "CLOSED"} else None
    problem.version += 1
    problem.full_clean()
    problem.save()
    _record(
        company=problem.company, action="TRANSITION", event_type="support.problem.transitioned", entity_type="ProblemRecord",
        entity_public_id=problem.public_id, actor_public_id=actor_public_id, correlation_id=correlation_id,
        version=problem.version, before=before, after={"code": problem.code, "status": problem.status_code},
    )
    return problem


@transaction.atomic
def create_change(*, company: Company, actor_public_id: uuid.UUID, correlation_id: uuid.UUID, **data: Any) -> ChangeRequest:
    change = ChangeRequest(company=company, created_by_public_id=actor_public_id, **data)
    change.full_clean()
    change.save()
    _record(
        company=company, action="CREATE", event_type="support.change.created", entity_type="ChangeRequest",
        entity_public_id=change.public_id, actor_public_id=actor_public_id, correlation_id=correlation_id,
        version=change.version, after={"code": change.code, "status": change.status_code, "risk": change.risk_code},
    )
    return change


@transaction.atomic
def transition_change(
    *, change: ChangeRequest, status_code: str, expected_version: int, actor_public_id: uuid.UUID,
    correlation_id: uuid.UUID, rollback_plan: str = "", test_evidence: dict[str, Any] | None = None
) -> ChangeRequest:
    change = ChangeRequest.objects.select_for_update().get(pk=change.pk)
    if change.version != expected_version:
        raise ValidationError("Change request changed. Refresh and retry.")
    allowed = {
        "DRAFT": {"ASSESSMENT", "CANCELLED"},
        "ASSESSMENT": {"PENDING_APPROVAL", "DRAFT", "CANCELLED"},
        "PENDING_APPROVAL": {"APPROVED", "REJECTED"},
        "APPROVED": {"SCHEDULED", "CANCELLED"},
        "SCHEDULED": {"IMPLEMENTING", "CANCELLED"},
        "IMPLEMENTING": {"IMPLEMENTED", "ROLLED_BACK"},
        "IMPLEMENTED": {"CLOSED", "ROLLED_BACK"},
        "REJECTED": {"DRAFT"},
        "ROLLED_BACK": {"CLOSED"},
        "CLOSED": set(),
        "CANCELLED": set(),
    }
    if status_code not in allowed.get(change.status_code, set()):
        raise ValidationError(f"Invalid change transition from {change.status_code} to {status_code}.")
    if status_code == "APPROVED" and change.created_by_public_id == actor_public_id:
        raise ValidationError("The change creator cannot approve the same change request.")
    if status_code in {"APPROVED", "SCHEDULED", "IMPLEMENTING", "IMPLEMENTED"} and not (
        rollback_plan.strip() or change.rollback_plan.strip()
    ):
        raise ValidationError("Rollback plan is required.")
    before = {"status": change.status_code, "version": change.version}
    if rollback_plan.strip():
        change.rollback_plan = rollback_plan.strip()
    if test_evidence is not None:
        change.test_evidence = test_evidence
    if status_code == "APPROVED":
        change.approved_by_public_id = actor_public_id
    if status_code == "IMPLEMENTED":
        change.implemented_at = timezone.now()
    change.status_code = status_code
    change.version += 1
    change.full_clean()
    change.save()
    _record(
        company=change.company, action="TRANSITION", event_type="support.change.transitioned", entity_type="ChangeRequest",
        entity_public_id=change.public_id, actor_public_id=actor_public_id, correlation_id=correlation_id,
        version=change.version, before=before, after={"code": change.code, "status": change.status_code},
    )
    return change


@transaction.atomic
def create_article(*, company: Company, actor_public_id: uuid.UUID, correlation_id: uuid.UUID, **data: Any) -> KnowledgeArticle:
    article = KnowledgeArticle(company=company, created_by_public_id=actor_public_id, **data)
    article.full_clean()
    article.save()
    _record(
        company=company, action="CREATE", event_type="support.knowledge.created", entity_type="KnowledgeArticle",
        entity_public_id=article.public_id, actor_public_id=actor_public_id, correlation_id=correlation_id,
        version=article.version, after={"code": article.code, "status": article.status_code},
    )
    return article


@transaction.atomic
def transition_article(
    *, article: KnowledgeArticle, status_code: str, expected_version: int, actor_public_id: uuid.UUID,
    correlation_id: uuid.UUID
) -> KnowledgeArticle:
    article = KnowledgeArticle.objects.select_for_update().get(pk=article.pk)
    if article.version != expected_version:
        raise ValidationError("Knowledge article changed. Refresh and retry.")
    allowed = {
        "DRAFT": {"IN_REVIEW", "ARCHIVED"},
        "IN_REVIEW": {"PUBLISHED", "DRAFT", "ARCHIVED"},
        "PUBLISHED": {"ARCHIVED", "DRAFT"},
        "ARCHIVED": {"DRAFT"},
    }
    if status_code not in allowed.get(article.status_code, set()):
        raise ValidationError(f"Invalid article transition from {article.status_code} to {status_code}.")
    if status_code == "PUBLISHED" and article.created_by_public_id == actor_public_id:
        raise ValidationError("The article author cannot publish the same article.")
    before = {"status": article.status_code, "version": article.version}
    if status_code == "PUBLISHED":
        article.published_by_public_id = actor_public_id
        article.published_at = timezone.now()
    if status_code == "DRAFT":
        article.published_by_public_id = None
        article.published_at = None
    article.status_code = status_code
    article.version += 1
    article.full_clean()
    article.save()
    _record(
        company=article.company, action="TRANSITION", event_type="support.knowledge.transitioned", entity_type="KnowledgeArticle",
        entity_public_id=article.public_id, actor_public_id=actor_public_id, correlation_id=correlation_id,
        version=article.version, before=before, after={"code": article.code, "status": article.status_code},
    )
    return article


@transaction.atomic
def create_feedback(
    *, company: Company, ticket: SupportTicket, actor_public_id: uuid.UUID, correlation_id: uuid.UUID, **data: Any
) -> CustomerFeedback:
    if ticket.company_id != company.id:
        raise ValidationError("Customer feedback cannot cross companies.")
    feedback = CustomerFeedback(company=company, ticket=ticket, **data)
    feedback.full_clean()
    feedback.save()
    _record(
        company=company, action="CREATE", event_type="support.feedback.created", entity_type="CustomerFeedback",
        entity_public_id=feedback.public_id, actor_public_id=actor_public_id, correlation_id=correlation_id,
        version=1, after={"ticket": ticket.code, "rating": feedback.rating, "follow_up_required": feedback.follow_up_required},
    )
    return feedback


@transaction.atomic
def create_improvement(*, company: Company, actor_public_id: uuid.UUID, correlation_id: uuid.UUID, **data: Any) -> ImprovementItem:
    item = ImprovementItem(company=company, created_by_public_id=actor_public_id, **data)
    item.full_clean()
    item.save()
    _record(
        company=company, action="CREATE", event_type="support.improvement.created", entity_type="ImprovementItem",
        entity_public_id=item.public_id, actor_public_id=actor_public_id, correlation_id=correlation_id,
        version=item.version, after={"code": item.code, "status": item.status_code, "theme": item.theme_code},
    )
    return item


@transaction.atomic
def transition_improvement(
    *, item: ImprovementItem, status_code: str, expected_version: int, actor_public_id: uuid.UUID,
    correlation_id: uuid.UUID, measured_benefit: str = ""
) -> ImprovementItem:
    item = ImprovementItem.objects.select_for_update().get(pk=item.pk)
    if item.version != expected_version:
        raise ValidationError("Improvement item changed. Refresh and retry.")
    allowed = {
        "BACKLOG": {"PLANNED", "CANCELLED"},
        "PLANNED": {"IN_PROGRESS", "BACKLOG", "CANCELLED"},
        "IN_PROGRESS": {"VALIDATING", "BLOCKED", "CANCELLED"},
        "BLOCKED": {"IN_PROGRESS", "CANCELLED"},
        "VALIDATING": {"COMPLETED", "IN_PROGRESS"},
        "COMPLETED": set(),
        "CANCELLED": set(),
    }
    if status_code not in allowed.get(item.status_code, set()):
        raise ValidationError(f"Invalid improvement transition from {item.status_code} to {status_code}.")
    if status_code == "COMPLETED" and not (measured_benefit.strip() or item.measured_benefit.strip()):
        raise ValidationError("Measured benefit is required before completion.")
    before = {"status": item.status_code, "version": item.version}
    if measured_benefit.strip():
        item.measured_benefit = measured_benefit.strip()
    item.status_code = status_code
    item.completed_at = timezone.now() if status_code == "COMPLETED" else None
    item.version += 1
    item.full_clean()
    item.save()
    _record(
        company=item.company, action="TRANSITION", event_type="support.improvement.transitioned", entity_type="ImprovementItem",
        entity_public_id=item.public_id, actor_public_id=actor_public_id, correlation_id=correlation_id,
        version=item.version, before=before, after={"code": item.code, "status": item.status_code},
    )
    return item


@transaction.atomic
def refresh_sla(company: Company) -> dict[str, int]:
    now = timezone.now()
    open_statuses = ["NEW", "TRIAGED", "IN_PROGRESS", "WAITING_CUSTOMER", "WAITING_INTERNAL", "REOPENED"]
    breach_condition = (
        Q(first_responded_at__isnull=True, response_due_at__lt=now)
        | Q(resolution_due_at__lt=now)
    )
    needs_update = Q(sla_breached=False) | Q(escalation_level=0)
    affected = SupportTicket.objects.filter(
        company=company,
        status_code__in=open_statuses,
    ).filter(breach_condition).filter(needs_update).update(
        sla_breached=True,
        escalation_level=Case(
            When(escalation_level=0, then=1),
            default=F("escalation_level"),
            output_field=IntegerField(),
        ),
        version=F("version") + 1,
        updated_at=now,
    )
    return {"breached": affected, "escalated": affected}
