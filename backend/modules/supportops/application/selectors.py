from __future__ import annotations

from decimal import Decimal

from django.db.models import Avg
from django.utils import timezone

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

OPEN_TICKET_STATUSES = ["NEW", "TRIAGED", "IN_PROGRESS", "WAITING_CUSTOMER", "WAITING_INTERNAL", "REOPENED"]


def _company_payload(company: Company) -> dict[str, str]:
    return {
        "name": getattr(company, "display_name", "") or getattr(company, "legal_name", ""),
        "code": company.code,
        "timezone": company.timezone,
        "currency": company.currency,
    }


def support_overview(company: Company) -> dict[str, object]:
    policy = SupportPolicyVersion.objects.filter(company=company).order_by("-version").first()
    catalog = ServiceCatalogItem.objects.filter(company=company)
    tickets = SupportTicket.objects.filter(company=company)
    interactions = TicketInteraction.objects.filter(company=company)
    problems = ProblemRecord.objects.filter(company=company)
    changes = ChangeRequest.objects.filter(company=company)
    articles = KnowledgeArticle.objects.filter(company=company)
    feedback = CustomerFeedback.objects.filter(company=company)
    improvements = ImprovementItem.objects.filter(company=company)

    now = timezone.now()
    open_tickets = tickets.filter(status_code__in=OPEN_TICKET_STATUSES)
    response_breaches = open_tickets.filter(first_responded_at__isnull=True, response_due_at__lt=now).count()
    resolution_breaches = open_tickets.filter(resolution_due_at__lt=now).count()
    average_rating = feedback.aggregate(value=Avg("rating"))["value"]

    latest_tickets = list(
        tickets.select_related("catalog_item").order_by(
            "status_code", "priority_code", "-created_at"
        ).values(
            "public_id", "catalog_item__code", "code", "title", "category_code", "priority_code",
            "channel_code", "status_code", "requester_name", "requester_email",
            "assigned_to_public_id", "response_due_at", "resolution_due_at", "first_responded_at",
            "resolved_at", "sla_breached", "escalation_level", "version", "created_at",
        )[:50]
    )
    latest_interactions = list(
        interactions.select_related("ticket").order_by("-occurred_at").values(
            "public_id", "ticket__code", "interaction_type_code", "visibility_code", "body",
            "actor_public_id", "customer_visible", "occurred_at",
        )[:50]
    )
    latest_problems = list(
        problems.select_related("source_ticket").order_by("status_code", "priority_code", "-created_at").values(
            "public_id", "source_ticket__code", "code", "title", "impact_summary", "root_cause",
            "workaround", "permanent_fix", "priority_code", "status_code", "owner_public_id",
            "resolved_at", "version",
        )[:30]
    )
    latest_changes = list(
        changes.select_related("source_ticket", "problem").order_by("status_code", "risk_code", "-created_at").values(
            "public_id", "source_ticket__code", "problem__code", "code", "title", "change_type_code",
            "risk_code", "status_code", "planned_start_at", "planned_end_at", "rollback_plan",
            "approved_by_public_id", "implemented_at", "version",
        )[:30]
    )
    latest_articles = list(
        articles.order_by("status_code", "-updated_at").values(
            "public_id", "code", "title", "summary", "category_code", "audience_code",
            "status_code", "published_at", "version",
        )[:40]
    )
    latest_feedback = list(
        feedback.select_related("ticket").order_by("-submitted_at").values(
            "public_id", "ticket__code", "rating", "comments", "submitted_by_name",
            "follow_up_required", "follow_up_notes", "submitted_at",
        )[:40]
    )
    latest_improvements = list(
        improvements.order_by("status_code", "priority_code", "due_at").values(
            "public_id", "code", "title", "theme_code", "priority_code", "status_code",
            "expected_benefit", "measured_benefit", "owner_public_id", "due_at",
            "completed_at", "version",
        )[:40]
    )
    catalog_payload = list(
        catalog.order_by("category_code", "code").values(
            "public_id", "code", "name", "category_code", "description", "response_minutes",
            "resolution_minutes", "business_hours_only", "active", "version",
        )
    )

    return {
        "company": _company_payload(company),
        "policy": {
            "status": policy.status_code if policy else "MISSING",
            "version": policy.version if policy else 0,
            "default_response_minutes": policy.default_response_minutes if policy else 240,
            "default_resolution_minutes": policy.default_resolution_minutes if policy else 2880,
            "escalation_warning_percent": str(policy.escalation_warning_percent if policy else Decimal("80.00")),
            "customer_feedback_required": policy.customer_feedback_required if policy else True,
        },
        "metrics": {
            "open_tickets": open_tickets.count(),
            "critical_tickets": open_tickets.filter(priority_code__in=["P0", "P1"]).count(),
            "unassigned_tickets": open_tickets.filter(assigned_to_public_id__isnull=True).count(),
            "response_breaches": response_breaches,
            "resolution_breaches": resolution_breaches,
            "sla_breaches": open_tickets.filter(sla_breached=True).count(),
            "open_problems": problems.exclude(status_code__in=["RESOLVED", "CLOSED", "CANCELLED"]).count(),
            "pending_changes": changes.filter(status_code__in=["DRAFT", "ASSESSMENT", "PENDING_APPROVAL", "APPROVED", "SCHEDULED"]).count(),
            "published_articles": articles.filter(status_code="PUBLISHED").count(),
            "average_feedback_rating": round(float(average_rating or 0), 2),
            "feedback_responses": feedback.count(),
            "open_improvements": improvements.exclude(status_code__in=["COMPLETED", "CANCELLED"]).count(),
            "overdue_improvements": improvements.exclude(status_code__in=["COMPLETED", "CANCELLED"]).filter(due_at__lt=now).count(),
        },
        "catalog_items": catalog_payload,
        "tickets": latest_tickets,
        "interactions": latest_interactions,
        "problems": latest_problems,
        "changes": latest_changes,
        "knowledge_articles": latest_articles,
        "feedback": latest_feedback,
        "improvements": latest_improvements,
    }
