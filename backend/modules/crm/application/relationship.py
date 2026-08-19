from __future__ import annotations

import uuid
from datetime import timedelta
from decimal import Decimal
from typing import Any

from django.db.models import (
    Case,
    Count,
    DateTimeField,
    Exists,
    F,
    OuterRef,
    Q,
    Subquery,
    Sum,
    When,
)
from django.db.models.functions import Coalesce
from django.utils import timezone

from modules.crm.application.logbook import (
    attachment_payloads,
    creator_display_names,
    membership_display_names,
)
from modules.crm.application.protection import (
    blind_index,
    masked_email,
    masked_phone,
    normalize_email,
    normalize_phone,
)
from modules.crm.models import (
    Activity,
    Contact,
    Customer,
    Lead,
    Opportunity,
    PipelineStage,
    StageHistory,
)
from modules.tenant.models import Company

PEOPLE_VIEWS = {
    "all",
    "overdue",
    "today",
    "tomorrow",
    "active_leads",
    "converted",
    "contact_only",
    "no_next_action",
}
PEOPLE_SORTS = {"next_action", "recent", "name", "newest"}


def _safe_int(value: str | None, *, default: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value or default)
    except (TypeError, ValueError):
        parsed = default
    return min(max(parsed, minimum), maximum)


def _person_name(contact: Contact) -> str:
    return " ".join(part for part in (contact.first_name, contact.last_name) if part).strip()


def _contact_payload(contact: Contact, *, include_customer_reference: bool = True) -> dict[str, Any]:
    return {
        "public_id": str(contact.public_id),
        "customer_public_id": (
            str(contact.customer.public_id)
            if include_customer_reference and contact.customer
            else None
        ),
        "display_name": _person_name(contact),
        "first_name": contact.first_name,
        "last_name": contact.last_name,
        "job_title": contact.job_title,
        "email_masked": masked_email(contact.email_last_four),
        "phone_masked": masked_phone(contact.phone_last_four),
        "alternate_phone_masked": masked_phone(contact.alternate_phone_last_four),
        "communication_actions": {
            "email": bool(contact.email_ciphertext),
            "phone": bool(contact.phone_ciphertext),
            "alternate_phone": bool(contact.alternate_phone_ciphertext),
        },
        "consent_status": contact.consent_status,
        "preferred_channel_code": contact.preferred_channel_code,
        "address": contact.address,
        "source_code": contact.source_code,
        "tags": contact.tags,
        "notes": contact.notes,
        "custom_fields": contact.custom_fields,
        "owner_membership_public_id": (
            str(contact.owner_membership_public_id)
            if contact.owner_membership_public_id
            else None
        ),
        "is_primary": contact.is_primary,
        "is_active": contact.is_active,
        "version": contact.version,
        "created_at": contact.created_at.isoformat(),
        "updated_at": contact.updated_at.isoformat(),
    }


def _customer_payload(customer: Customer | None) -> dict[str, Any] | None:
    if customer is None:
        return None
    return {
        "public_id": str(customer.public_id),
        "kind": customer.kind,
        "display_name": customer.display_name,
        "legal_name": customer.legal_name,
        "external_reference": customer.external_reference,
        "source_code": customer.source_code,
        "status": customer.status,
        "owner_membership_public_id": (
            str(customer.owner_membership_public_id)
            if customer.owner_membership_public_id
            else None
        ),
        "custom_fields": customer.custom_fields,
        "notes": customer.notes,
        "version": customer.version,
        "created_at": customer.created_at.isoformat(),
    }


def _active_lead_subquery(company: Company):
    return Lead.objects.filter(
        company=company,
        primary_contact=OuterRef("pk"),
        converted_at__isnull=True,
        disqualified_at__isnull=True,
    ).order_by(F("next_follow_up_at").asc(nulls_last=True), "-created_at")


def _open_opportunity_subquery(company: Company):
    return Opportunity.objects.filter(
        company=company,
        primary_contact=OuterRef("pk"),
        won_at__isnull=True,
        lost_at__isnull=True,
    ).order_by(F("expected_close_date").asc(nulls_last=True), "-created_at")


def _next_activity_subquery(company: Company):
    return (
        Activity.objects.filter(company=company, status=Activity.Status.PLANNED)
        .filter(
            Q(contact=OuterRef("pk"))
            | Q(lead__primary_contact=OuterRef("pk"))
            | Q(opportunity__primary_contact=OuterRef("pk"))
        )
        .annotate(action_at=Coalesce("scheduled_for", "follow_up_at"))
        .filter(action_at__isnull=False)
        .order_by("action_at", "created_at")
    )


def people_page(
    *,
    company: Company,
    membership_public_id: uuid.UUID,
    search: str = "",
    view: str = "all",
    stage: str = "",
    source: str = "",
    owner: str = "",
    customer_public_id: str = "",
    sort: str = "next_action",
    page: int = 1,
    page_size: int = 50,
    include_leads: bool = True,
    include_opportunities: bool = True,
    include_activities: bool = True,
    include_customers: bool = True,
) -> dict[str, Any]:
    """Return a server-filtered person master list without duplicating CRM source records."""

    now = timezone.now()
    today = timezone.localdate()
    tomorrow = today + timedelta(days=1)
    page = max(page, 1)
    page_size = min(max(page_size, 10), 100)
    view = view if view in PEOPLE_VIEWS else "all"
    sort = sort if sort in PEOPLE_SORTS else "next_action"

    queryset = Contact.objects.select_related("customer").filter(company=company, is_active=True)

    if include_leads:
        active_leads = _active_lead_subquery(company)
        converted_leads = Lead.objects.filter(
            company=company,
            primary_contact=OuterRef("pk"),
            converted_at__isnull=False,
        )
        any_leads = Lead.objects.filter(company=company, primary_contact=OuterRef("pk"))
        queryset = queryset.annotate(
            has_any_lead=Exists(any_leads),
            has_active_lead=Exists(active_leads),
            has_converted_lead=Exists(converted_leads),
            active_lead_public_id=Subquery(active_leads.values("public_id")[:1]),
            active_lead_title=Subquery(active_leads.values("title")[:1]),
            active_lead_stage_code=Subquery(active_leads.values("stage__code")[:1]),
            active_lead_stage_name=Subquery(active_leads.values("stage__name")[:1]),
            active_lead_source_code=Subquery(active_leads.values("source_code")[:1]),
            active_lead_owner_public_id=Subquery(active_leads.values("owner_membership_public_id")[:1]),
            next_follow_up_at_value=Subquery(active_leads.values("next_follow_up_at")[:1]),
        )

    if include_opportunities:
        open_opportunities = _open_opportunity_subquery(company)
        won_opportunities = Opportunity.objects.filter(
            company=company,
            primary_contact=OuterRef("pk"),
            won_at__isnull=False,
        )
        queryset = queryset.annotate(
            has_open_opportunity=Exists(open_opportunities),
            has_won_opportunity=Exists(won_opportunities),
            open_opportunity_public_id=Subquery(open_opportunities.values("public_id")[:1]),
            open_opportunity_name=Subquery(open_opportunities.values("name")[:1]),
            open_opportunity_amount=Subquery(open_opportunities.values("amount")[:1]),
            open_opportunity_currency=Subquery(open_opportunities.values("currency")[:1]),
        )

    if include_activities:
        recent_activity = Activity.objects.filter(
            company=company,
        ).filter(
            Q(contact=OuterRef("pk"))
            | Q(lead__primary_contact=OuterRef("pk"))
            | Q(opportunity__primary_contact=OuterRef("pk"))
        ).order_by("-created_at")
        next_activity = _next_activity_subquery(company)
        queryset = queryset.annotate(
            last_activity_at_value=Subquery(recent_activity.values("created_at")[:1]),
            next_activity_at_value=Subquery(next_activity.values("action_at")[:1]),
            next_activity_subject=Subquery(next_activity.values("subject")[:1]),
        )

    if include_leads and include_activities:
        queryset = queryset.annotate(
            next_action_at_value=Case(
                When(next_follow_up_at_value__isnull=True, then=F("next_activity_at_value")),
                When(next_activity_at_value__isnull=True, then=F("next_follow_up_at_value")),
                When(next_follow_up_at_value__lte=F("next_activity_at_value"), then=F("next_follow_up_at_value")),
                default=F("next_activity_at_value"),
                output_field=DateTimeField(),
            )
        )
    elif include_leads:
        queryset = queryset.annotate(next_action_at_value=F("next_follow_up_at_value"))
    elif include_activities:
        queryset = queryset.annotate(next_action_at_value=F("next_activity_at_value"))

    search = search.strip()
    if search:
        search_q = (
            Q(first_name__icontains=search)
            | Q(last_name__icontains=search)
            | Q(job_title__icontains=search)
            | Q(source_code__icontains=search)
        )
        if include_customers:
            search_q |= Q(customer__display_name__icontains=search) | Q(customer__legal_name__icontains=search)
        if include_leads:
            search_q |= Q(active_lead_title__icontains=search)
        if "@" in search:
            normalized = normalize_email(search)
            search_q |= Q(email_blind_index=blind_index(normalized, purpose="email"))
        normalized_phone = normalize_phone(search)
        if len(normalized_phone.lstrip("+")) >= 7:
            search_q |= Q(phone_blind_index=blind_index(normalized_phone, purpose="phone"))
        queryset = queryset.filter(search_q)

    if customer_public_id and include_customers:
        try:
            customer_uuid = uuid.UUID(customer_public_id)
        except (ValueError, TypeError):
            customer_uuid = None
        if customer_uuid:
            queryset = queryset.filter(customer__public_id=customer_uuid)

    has_next_action_context = include_leads or include_activities
    if view in {"overdue", "today", "tomorrow"} and not has_next_action_context:
        queryset = queryset.none()
    elif view in {"active_leads", "contact_only"} and not include_leads:
        queryset = queryset.none()
    elif view == "no_next_action" and not (
        (include_leads or include_opportunities) and (include_leads or include_activities)
    ):
        queryset = queryset.none()
    elif view == "overdue":
        queryset = queryset.filter(next_action_at_value__lt=now)
    elif view == "today":
        queryset = queryset.filter(next_action_at_value__date=today)
    elif view == "tomorrow":
        queryset = queryset.filter(next_action_at_value__date=tomorrow)
    elif view == "active_leads":
        queryset = queryset.filter(has_active_lead=True)
    elif view == "converted":
        converted_q = Q()
        if include_leads:
            converted_q |= Q(has_converted_lead=True)
        if include_opportunities:
            converted_q |= Q(has_won_opportunity=True)
        queryset = queryset.filter(converted_q) if (include_leads or include_opportunities) else queryset.none()
    elif view == "contact_only":
        queryset = queryset.filter(has_any_lead=False)
    elif view == "no_next_action":
        active_relationship_q = Q()
        if include_leads:
            active_relationship_q |= Q(has_active_lead=True)
        if include_opportunities:
            active_relationship_q |= Q(has_open_opportunity=True)
        queryset = queryset.filter(active_relationship_q, next_action_at_value__isnull=True)

    if stage:
        queryset = queryset.filter(active_lead_stage_code=stage) if include_leads else queryset.none()
    if source:
        source_q = Q(source_code=source)
        if include_leads:
            source_q |= Q(active_lead_source_code=source)
        queryset = queryset.filter(source_q)
    if owner:
        owner_uuid: uuid.UUID | None = None
        if owner == "me":
            owner_uuid = membership_public_id
        else:
            try:
                owner_uuid = uuid.UUID(owner)
            except (ValueError, TypeError):
                owner_uuid = None
        if owner_uuid:
            owner_q = Q(owner_membership_public_id=owner_uuid)
            if include_leads:
                owner_q |= Q(active_lead_owner_public_id=owner_uuid)
            queryset = queryset.filter(owner_q)

    if sort == "name":
        queryset = queryset.order_by("first_name", "last_name", "id")
    elif sort == "recent" and include_activities:
        queryset = queryset.order_by(F("last_activity_at_value").desc(nulls_last=True), "first_name", "id")
    elif sort == "newest":
        queryset = queryset.order_by("-created_at", "id")
    elif include_leads or include_activities:
        queryset = queryset.order_by(F("next_action_at_value").asc(nulls_last=True), "first_name", "id")
    else:
        queryset = queryset.order_by("first_name", "last_name", "id")

    total = queryset.count()
    offset = (page - 1) * page_size
    rows = list(queryset[offset : offset + page_size])

    owner_ids: set[uuid.UUID] = set()
    for row in rows:
        if row.owner_membership_public_id:
            owner_ids.add(row.owner_membership_public_id)
        active_owner = getattr(row, "active_lead_owner_public_id", None)
        if active_owner:
            owner_ids.add(active_owner)
    owner_names = membership_display_names(company=company, public_ids=owner_ids)

    items: list[dict[str, Any]] = []
    for contact in rows:
        next_follow_up = getattr(contact, "next_action_at_value", None)
        active_owner = getattr(contact, "active_lead_owner_public_id", None)
        contact_owner = contact.owner_membership_public_id
        owner_id = active_owner or contact_owner
        relationship = "contact"
        if getattr(contact, "has_active_lead", False):
            relationship = "lead"
        elif getattr(contact, "has_converted_lead", False) or getattr(contact, "has_won_opportunity", False):
            relationship = "converted"
        items.append(
            {
                "person": {
                    "public_id": str(contact.public_id),
                    "display_name": _person_name(contact),
                    "job_title": contact.job_title,
                    "email_masked": masked_email(contact.email_last_four),
                    "phone_masked": masked_phone(contact.phone_last_four),
                    "alternate_phone_masked": masked_phone(contact.alternate_phone_last_four),
                    "source_code": contact.source_code,
                    "tags": contact.tags,
                    "created_at": contact.created_at.isoformat(),
                },
                "company": _customer_payload(contact.customer) if include_customers else None,
                "relationship": relationship,
                "has_active_lead": bool(getattr(contact, "has_active_lead", False)),
                "has_converted_lead": bool(getattr(contact, "has_converted_lead", False)),
                "has_open_opportunity": bool(getattr(contact, "has_open_opportunity", False)),
                "has_won_opportunity": bool(getattr(contact, "has_won_opportunity", False)),
                "active_lead": (
                    {
                        "public_id": str(contact.active_lead_public_id),
                        "title": getattr(contact, "active_lead_title", ""),
                        "stage_code": getattr(contact, "active_lead_stage_code", ""),
                        "stage_name": getattr(contact, "active_lead_stage_name", ""),
                        "source_code": getattr(contact, "active_lead_source_code", ""),
                    }
                    if getattr(contact, "active_lead_public_id", None)
                    else None
                ),
                "open_opportunity": (
                    {
                        "public_id": str(contact.open_opportunity_public_id),
                        "name": getattr(contact, "open_opportunity_name", ""),
                        "amount": str(getattr(contact, "open_opportunity_amount", Decimal("0")) or Decimal("0")),
                        "currency": getattr(contact, "open_opportunity_currency", company.currency),
                    }
                    if getattr(contact, "open_opportunity_public_id", None)
                    else None
                ),
                "next_follow_up_at": next_follow_up.isoformat() if next_follow_up else None,
                "next_action_kind": (
                    "lead_follow_up"
                    if next_follow_up and getattr(contact, "next_follow_up_at_value", None) == next_follow_up
                    else "activity" if next_follow_up else None
                ),
                "next_action_label": (
                    f"Follow up · {getattr(contact, 'active_lead_title', '')}"
                    if next_follow_up and getattr(contact, "next_follow_up_at_value", None) == next_follow_up
                    else getattr(contact, "next_activity_subject", "") if next_follow_up else ""
                ),
                "is_overdue": bool(next_follow_up and next_follow_up < now),
                "last_activity_at": (
                    contact.last_activity_at_value.isoformat()
                    if getattr(contact, "last_activity_at_value", None)
                    else None
                ),
                "owner": {
                    "public_id": str(owner_id) if owner_id else None,
                    "display_name": owner_names.get(owner_id, "") if owner_id else "",
                },
            }
        )

    return {
        "items": items,
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total": total,
            "has_next": offset + page_size < total,
            "has_previous": page > 1,
        },
        "filters": {
            "search": search,
            "view": view,
            "stage": stage,
            "source": source,
            "owner": owner,
            "sort": sort,
        },
    }


def _lead_payload(lead: Lead, owner_names: dict[uuid.UUID, str]) -> dict[str, Any]:
    return {
        "public_id": str(lead.public_id),
        "title": lead.title,
        "description": lead.description,
        "source_code": lead.source_code,
        "stage": {
            "public_id": str(lead.stage.public_id),
            "code": lead.stage.code,
            "name": lead.stage.name,
            "outcome": lead.stage.outcome,
            "pipeline_public_id": str(lead.stage.pipeline.public_id) if lead.stage.pipeline else None,
            "pipeline_name": lead.stage.pipeline.name if lead.stage.pipeline else "",
        },
        "estimated_value": str(lead.estimated_value) if lead.estimated_value is not None else None,
        "currency": lead.currency,
        "next_follow_up_at": lead.next_follow_up_at.isoformat() if lead.next_follow_up_at else None,
        "owner_membership_public_id": str(lead.owner_membership_public_id),
        "owner_display_name": owner_names.get(lead.owner_membership_public_id, ""),
        "custom_fields": lead.custom_fields,
        "converted_at": lead.converted_at.isoformat() if lead.converted_at else None,
        "disqualified_at": lead.disqualified_at.isoformat() if lead.disqualified_at else None,
        "created_at": lead.created_at.isoformat(),
        "version": lead.version,
    }


def _opportunity_payload(opportunity: Opportunity, owner_names: dict[uuid.UUID, str]) -> dict[str, Any]:
    return {
        "public_id": str(opportunity.public_id),
        "name": opportunity.name,
        "source_lead_public_id": str(opportunity.source_lead.public_id) if opportunity.source_lead else None,
        "stage": {
            "public_id": str(opportunity.stage.public_id),
            "code": opportunity.stage.code,
            "name": opportunity.stage.name,
            "outcome": opportunity.stage.outcome,
            "pipeline_public_id": str(opportunity.stage.pipeline.public_id) if opportunity.stage.pipeline else None,
            "pipeline_name": opportunity.stage.pipeline.name if opportunity.stage.pipeline else "",
        },
        "amount": str(opportunity.amount),
        "currency": opportunity.currency,
        "probability_percent": opportunity.probability_percent,
        "expected_close_date": opportunity.expected_close_date.isoformat() if opportunity.expected_close_date else None,
        "owner_membership_public_id": str(opportunity.owner_membership_public_id),
        "owner_display_name": owner_names.get(opportunity.owner_membership_public_id, ""),
        "custom_fields": opportunity.custom_fields,
        "won_at": opportunity.won_at.isoformat() if opportunity.won_at else None,
        "lost_at": opportunity.lost_at.isoformat() if opportunity.lost_at else None,
        "created_at": opportunity.created_at.isoformat(),
        "version": opportunity.version,
    }


def relationship_workspace(
    *,
    company: Company,
    contact_public_id: uuid.UUID,
    limit: int = 250,
    include_leads: bool = True,
    include_opportunities: bool = True,
    include_activities: bool = True,
    include_customers: bool = True,
) -> dict[str, Any]:
    contact = (
        Contact.objects.select_related("customer")
        .filter(company=company, public_id=contact_public_id, is_active=True)
        .first()
    )
    if contact is None:
        raise Contact.DoesNotExist

    limit = min(max(limit, 50), 500)
    leads = (
        list(
            Lead.objects.select_related("stage", "stage__pipeline", "customer")
            .filter(company=company, primary_contact=contact)
            .order_by("-created_at")
        )
        if include_leads
        else []
    )
    opportunities = (
        list(
            Opportunity.objects.select_related("stage", "stage__pipeline", "source_lead", "customer")
            .filter(company=company, primary_contact=contact)
            .order_by("-created_at")
        )
        if include_opportunities
        else []
    )
    lead_ids = [row.public_id for row in leads]
    opportunity_ids = [row.public_id for row in opportunities]

    activity_filter = Q(contact=contact)
    if lead_ids:
        activity_filter |= Q(lead__public_id__in=lead_ids)
    if opportunity_ids:
        activity_filter |= Q(opportunity__public_id__in=opportunity_ids)
    activities = (
        list(
            Activity.objects.select_related("lead", "opportunity", "customer")
            .prefetch_related("attachments")
            .filter(company=company)
            .filter(activity_filter)
            .distinct()
            .order_by("-created_at")[:limit]
        )
        if include_activities
        else []
    )

    attachments = [item for activity in activities for item in activity.attachments.all()]
    attachment_map = attachment_payloads(company=company, attachments=attachments)

    history_filter = Q()
    if lead_ids:
        history_filter |= Q(
            entity_type=PipelineStage.EntityType.LEAD,
            entity_public_id__in=lead_ids,
        )
    if opportunity_ids:
        history_filter |= Q(
            entity_type=PipelineStage.EntityType.OPPORTUNITY,
            entity_public_id__in=opportunity_ids,
        )
    histories = list(
        StageHistory.objects.filter(company=company)
        .filter(history_filter)
        .order_by("-changed_at")[:limit]
    ) if (lead_ids or opportunity_ids) else []

    owner_ids = {
        *(row.owner_membership_public_id for row in leads),
        *(row.owner_membership_public_id for row in opportunities),
    }
    if contact.owner_membership_public_id:
        owner_ids.add(contact.owner_membership_public_id)
    if contact.customer and contact.customer.owner_membership_public_id:
        owner_ids.add(contact.customer.owner_membership_public_id)
    owner_names = membership_display_names(company=company, public_ids=owner_ids)

    creator_ids = {activity.created_by_public_id for activity in activities}
    creator_ids.update(history.changed_by_public_id for history in histories)
    creator_names = creator_display_names(creator_ids)

    timeline: list[dict[str, Any]] = []
    for activity in activities:
        event_at = activity.occurred_at or activity.completed_at or activity.created_at
        timeline.append(
            {
                "kind": "activity",
                "public_id": str(activity.public_id),
                "occurred_at": event_at.isoformat(),
                "activity_type": activity.activity_type,
                "status": activity.status,
                "direction": activity.direction,
                "outcome_code": activity.outcome_code,
                "duration_seconds": activity.duration_seconds,
                "channel_metadata": activity.channel_metadata or {},
                "priority": activity.priority,
                "subject": activity.subject,
                "description": activity.notes,
                "scheduled_for": activity.scheduled_for.isoformat() if activity.scheduled_for else None,
                "follow_up_at": activity.follow_up_at.isoformat() if activity.follow_up_at else None,
                "lead_public_id": str(activity.lead.public_id) if activity.lead else None,
                "opportunity_public_id": str(activity.opportunity.public_id) if activity.opportunity else None,
                "created_by_name": creator_names.get(activity.created_by_public_id, "Build360 user"),
                "attachments": [
                    attachment_map[item.pk]
                    for item in activity.attachments.all()
                    if item.pk in attachment_map
                ],
                "version": activity.version,
            }
        )
    for history in histories:
        timeline.append(
            {
                "kind": "stage_change",
                "public_id": str(history.public_id),
                "occurred_at": history.changed_at.isoformat(),
                "activity_type": "status_change",
                "status": "completed",
                "direction": "internal",
                "outcome_code": "",
                "duration_seconds": None,
                "channel_metadata": {},
                "priority": "normal",
                "subject": f"{history.entity_type.title()} moved to {history.to_stage_code}",
                "description": f"{history.from_stage_code or 'Created'} → {history.to_stage_code}",
                "scheduled_for": None,
                "follow_up_at": None,
                "lead_public_id": str(history.entity_public_id) if history.entity_type == PipelineStage.EntityType.LEAD else None,
                "opportunity_public_id": str(history.entity_public_id) if history.entity_type == PipelineStage.EntityType.OPPORTUNITY else None,
                "created_by_name": creator_names.get(history.changed_by_public_id, "Build360 user"),
                "attachments": [],
                "version": history.entity_version,
            }
        )
    timeline.sort(key=lambda item: item["occurred_at"], reverse=True)
    timeline = timeline[:limit]

    now = timezone.now()
    action_candidates: list[dict[str, Any]] = []
    for lead in leads:
        if lead.converted_at is None and lead.disqualified_at is None and lead.next_follow_up_at:
            action_candidates.append(
                {
                    "at": lead.next_follow_up_at,
                    "kind": "lead_follow_up",
                    "label": f"Follow up · {lead.title}",
                    "lead_public_id": str(lead.public_id),
                    "activity_public_id": None,
                }
            )
    for activity in activities:
        if activity.status != Activity.Status.PLANNED:
            continue
        action_at = activity.scheduled_for or activity.follow_up_at
        if action_at:
            action_candidates.append(
                {
                    "at": action_at,
                    "kind": activity.activity_type,
                    "label": activity.subject,
                    "lead_public_id": str(activity.lead.public_id) if activity.lead else None,
                    "activity_public_id": str(activity.public_id),
                }
            )
    action_candidates.sort(key=lambda item: item["at"])
    next_action = None
    if action_candidates:
        candidate = action_candidates[0]
        next_action = {
            **{key: value for key, value in candidate.items() if key != "at"},
            "at": candidate["at"].isoformat(),
            "is_overdue": candidate["at"] < now,
        }

    file_items: list[dict[str, Any]] = []
    seen_files: set[str] = set()
    for activity in activities:
        for attachment in activity.attachments.all():
            payload = attachment_map.get(attachment.pk)
            if not payload:
                continue
            file_id = str(payload.get("file_public_id") or payload.get("public_id"))
            if file_id in seen_files:
                continue
            seen_files.add(file_id)
            file_items.append(
                {
                    **payload,
                    "activity_public_id": str(activity.public_id),
                    "activity_subject": activity.subject,
                }
            )

    active_leads = [row for row in leads if row.converted_at is None and row.disqualified_at is None]
    open_opportunities = [row for row in opportunities if row.won_at is None and row.lost_at is None]
    won_opportunities = [row for row in opportunities if row.won_at is not None]
    last_activity_at = timeline[0]["occurred_at"] if timeline else None
    relationship_customer = contact.customer
    if relationship_customer is None:
        relationship_customer = next((row.customer for row in leads if row.customer_id), None)
    if relationship_customer is None:
        relationship_customer = next((row.customer for row in opportunities if row.customer_id), None)

    return {
        "person": _contact_payload(contact, include_customer_reference=include_customers),
        "company": _customer_payload(relationship_customer) if include_customers else None,
        "relationship": {
            "has_active_lead": bool(active_leads),
            "has_converted_lead": any(row.converted_at is not None for row in leads),
            "has_open_opportunity": bool(open_opportunities),
            "has_won_opportunity": bool(won_opportunities),
            "lead_count": len(leads),
            "opportunity_count": len(opportunities),
        },
        "next_action": next_action,
        "last_activity_at": last_activity_at,
        "leads": [_lead_payload(row, owner_names) for row in leads],
        "opportunities": [_opportunity_payload(row, owner_names) for row in opportunities],
        "timeline": timeline,
        "files": file_items,
        "summary": {
            "activity_count": len(activities),
            "file_count": len(file_items),
            "active_lead_count": len(active_leads),
            "open_opportunity_count": len(open_opportunities),
            "won_opportunity_count": len(won_opportunities),
            "open_pipeline_value": str(sum((row.amount for row in open_opportunities), Decimal("0"))),
            "currency": company.currency,
        },
    }


def my_work_payload(
    *,
    company: Company,
    membership_public_id: uuid.UUID,
    limit: int = 40,
    include_contacts: bool = True,
    include_customers: bool = True,
    include_leads: bool = True,
    include_activities: bool = True,
) -> dict[str, Any]:
    now = timezone.now()
    today = timezone.localdate()
    tomorrow = today + timedelta(days=1)
    week_end = today + timedelta(days=7)
    limit = min(max(limit, 10), 100)

    active_leads = (
        Lead.objects.select_related("primary_contact", "customer", "stage").filter(
            company=company,
            owner_membership_public_id=membership_public_id,
            converted_at__isnull=True,
            disqualified_at__isnull=True,
        )
        if include_leads
        else Lead.objects.none()
    )
    lead_followups = (
        list(active_leads.filter(next_follow_up_at__isnull=False).order_by("next_follow_up_at")[:limit])
        if include_leads
        else []
    )

    activities = (
        list(
            Activity.objects.select_related(
                "contact",
                "lead__primary_contact",
                "lead__customer",
                "opportunity__primary_contact",
                "opportunity__customer",
            )
            .filter(
                company=company,
                owner_membership_public_id=membership_public_id,
                status=Activity.Status.PLANNED,
            )
            .annotate(action_at_value=Coalesce("scheduled_for", "follow_up_at"))
            .filter(action_at_value__isnull=False)
            .order_by("action_at_value")[:limit]
        )
        if include_activities
        else []
    )

    queue: list[dict[str, Any]] = []
    seen_keys: set[tuple[str, str]] = set()

    def add_queue_item(
        *,
        action_at,
        subject: str,
        reason: str,
        person: Contact | None,
        lead: Lead | None,
        activity: Activity | None,
        priority: str,
    ) -> None:
        person_id = str(person.public_id) if person else ""
        key = (person_id, action_at.isoformat() if action_at else subject)
        if key in seen_keys:
            return
        seen_keys.add(key)
        queue.append(
            {
                "action_at": action_at.isoformat() if action_at else None,
                "is_overdue": bool(action_at and action_at < now),
                "is_today": bool(action_at and timezone.localdate(action_at) == today),
                "subject": subject,
                "reason": reason,
                "priority": priority,
                "person": (
                    {
                        "public_id": str(person.public_id),
                        "display_name": _person_name(person),
                        "phone_masked": masked_phone(person.phone_last_four),
                        "alternate_phone_masked": masked_phone(person.alternate_phone_last_four),
                        "email_masked": masked_email(person.email_last_four),
                    }
                    if person and include_contacts
                    else None
                ),
                "company": (
                    _customer_payload(
                        person.customer
                        if person and person.customer_id
                        else (lead.customer if lead and lead.customer_id else None)
                    )
                    if include_customers
                    else None
                ),
                "lead_public_id": str(lead.public_id) if lead else None,
                "activity_public_id": str(activity.public_id) if activity else None,
                "activity_type": activity.activity_type if activity else "follow_up",
            }
        )

    for activity in activities:
        person = activity.contact
        lead = activity.lead
        if person is None and lead and lead.primary_contact:
            person = lead.primary_contact
        if person is None and activity.opportunity and activity.opportunity.primary_contact:
            person = activity.opportunity.primary_contact
        action_at = getattr(activity, "action_at_value", None)
        add_queue_item(
            action_at=action_at,
            subject=activity.subject,
            reason=(
                "Callback requested"
                if activity.outcome_code == "callback_requested"
                else activity.activity_type.replace("_", " ").title()
            ),
            person=person,
            lead=lead,
            activity=activity,
            priority=activity.priority,
        )

    for lead in lead_followups:
        add_queue_item(
            action_at=lead.next_follow_up_at,
            subject=f"Follow up · {lead.title}",
            reason=f"{lead.stage.name} · {lead.source_code or 'Direct'}",
            person=lead.primary_contact,
            lead=lead,
            activity=None,
            priority="high" if lead.next_follow_up_at and lead.next_follow_up_at < now else "normal",
        )

    queue.sort(
        key=lambda item: (
            0 if item["is_overdue"] else 1 if item["is_today"] else 2,
            item["action_at"] or "9999-12-31T23:59:59+00:00",
        )
    )
    queue = queue[:limit]

    planned_owned = (
        Activity.objects.filter(
            company=company,
            owner_membership_public_id=membership_public_id,
            status=Activity.Status.PLANNED,
        ).annotate(action_at_value=Coalesce("scheduled_for", "follow_up_at"))
        if include_activities
        else Activity.objects.none()
    )

    counts = {
        "overdue": (active_leads.filter(next_follow_up_at__lt=now).count() if include_leads else 0)
        + (planned_owned.filter(action_at_value__lt=now).count() if include_activities else 0),
        "today": (active_leads.filter(next_follow_up_at__date=today).count() if include_leads else 0)
        + (planned_owned.filter(action_at_value__date=today).count() if include_activities else 0),
        "tomorrow": (active_leads.filter(next_follow_up_at__date=tomorrow).count() if include_leads else 0)
        + (planned_owned.filter(action_at_value__date=tomorrow).count() if include_activities else 0),
        "this_week": (
            active_leads.filter(next_follow_up_at__date__gte=today, next_follow_up_at__date__lte=week_end).count()
            if include_leads
            else 0
        )
        + (
            planned_owned.filter(action_at_value__date__gte=today, action_at_value__date__lte=week_end).count()
            if include_activities
            else 0
        ),
        "callback_requested": (
            Activity.objects.filter(
                company=company,
                owner_membership_public_id=membership_public_id,
                outcome_code="callback_requested",
                created_at__gte=now - timedelta(days=30),
            ).count()
            if include_activities
            else 0
        ),
        "no_next_action": active_leads.filter(next_follow_up_at__isnull=True).count() if include_leads else 0,
        "new_uncontacted": (
            active_leads.filter(created_at__gte=now - timedelta(days=1))
            .annotate(activity_count=Count("activities"))
            .filter(activity_count=0)
            .count()
            if include_leads and include_activities
            else 0
        ),
    }
    return {
        "generated_at": now.isoformat(),
        "counts": counts,
        "queue": queue,
    }


def account_page(
    *,
    company: Company,
    search: str = "",
    page: int = 1,
    page_size: int = 50,
    include_contacts: bool = True,
    include_leads: bool = True,
    include_opportunities: bool = True,
    include_activities: bool = True,
) -> dict[str, Any]:
    page = max(page, 1)
    page_size = min(max(page_size, 10), 100)
    queryset = Customer.objects.filter(company=company, status=Customer.Status.ACTIVE)
    search = search.strip()
    if search:
        queryset = queryset.filter(
            Q(display_name__icontains=search)
            | Q(legal_name__icontains=search)
            | Q(external_reference__icontains=search)
        )
    annotations: dict[str, Any] = {}
    if include_contacts:
        contact_counts = (
            Contact.objects.filter(company=company, customer=OuterRef("pk"), is_active=True)
            .values("customer")
            .annotate(value=Count("pk"))
            .values("value")[:1]
        )
        annotations["contact_count_value"] = Subquery(contact_counts)
    if include_leads:
        lead_counts = (
            Lead.objects.filter(
                company=company,
                customer=OuterRef("pk"),
                converted_at__isnull=True,
                disqualified_at__isnull=True,
            )
            .values("customer")
            .annotate(value=Count("pk"))
            .values("value")[:1]
        )
        annotations["active_lead_count_value"] = Subquery(lead_counts)
    if include_opportunities:
        open_opportunities = Opportunity.objects.filter(
            company=company,
            customer=OuterRef("pk"),
            won_at__isnull=True,
            lost_at__isnull=True,
        )
        opportunity_counts = (
            open_opportunities.values("customer")
            .annotate(value=Count("pk"))
            .values("value")[:1]
        )
        opportunity_values = (
            open_opportunities.values("customer")
            .annotate(value=Sum("amount"))
            .values("value")[:1]
        )
        annotations["open_opportunity_count_value"] = Subquery(opportunity_counts)
        annotations["open_pipeline_value"] = Subquery(opportunity_values)
    if include_activities:
        recent_activity = (
            Activity.objects.filter(company=company)
            .filter(
                Q(customer=OuterRef("pk"))
                | Q(contact__customer=OuterRef("pk"))
                | Q(lead__customer=OuterRef("pk"))
                | Q(opportunity__customer=OuterRef("pk"))
            )
            .order_by("-created_at")
        )
        annotations["last_activity_at_value"] = Subquery(recent_activity.values("created_at")[:1])
    if annotations:
        queryset = queryset.annotate(**annotations)
    queryset = queryset.order_by("display_name", "id")
    total = queryset.count()
    offset = (page - 1) * page_size
    rows = list(queryset[offset : offset + page_size])
    return {
        "items": [
            {
                "company": _customer_payload(row),
                "contact_count": int(getattr(row, "contact_count_value", 0) or 0),
                "active_lead_count": int(getattr(row, "active_lead_count_value", 0) or 0),
                "open_opportunity_count": int(getattr(row, "open_opportunity_count_value", 0) or 0),
                "open_pipeline_value": str(getattr(row, "open_pipeline_value", None) or Decimal("0")),
                "currency": company.currency,
                "last_activity_at": (
                    row.last_activity_at_value.isoformat()
                    if getattr(row, "last_activity_at_value", None)
                    else None
                ),
            }
            for row in rows
        ],
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total": total,
            "has_next": offset + page_size < total,
            "has_previous": page > 1,
        },
    }


def account_workspace(
    *,
    company: Company,
    customer_public_id: uuid.UUID,
    include_contacts: bool = True,
    include_leads: bool = True,
    include_opportunities: bool = True,
    include_activities: bool = True,
) -> dict[str, Any]:
    customer = Customer.objects.filter(company=company, public_id=customer_public_id).first()
    if customer is None:
        raise Customer.DoesNotExist
    contacts = (
        list(
            Contact.objects.filter(company=company, customer=customer, is_active=True)
            .order_by("first_name", "last_name")
        )
        if include_contacts
        else []
    )
    opportunities = (
        list(
            Opportunity.objects.select_related("stage", "stage__pipeline", "primary_contact")
            .filter(company=company, customer=customer)
            .order_by("-created_at")
        )
        if include_opportunities
        else []
    )
    leads = (
        list(
            Lead.objects.select_related("stage", "stage__pipeline", "primary_contact")
            .filter(company=company, customer=customer)
            .order_by("-created_at")
        )
        if include_leads
        else []
    )
    recent_activities = (
        list(
            Activity.objects.select_related("contact", "lead", "opportunity")
            .filter(company=company)
            .filter(
                Q(customer=customer)
                | Q(contact__customer=customer)
                | Q(lead__customer=customer)
                | Q(opportunity__customer=customer)
            )
            .distinct()
            .order_by("-created_at")[:50]
        )
        if include_activities
        else []
    )
    owner_ids = {
        *(row.owner_membership_public_id for row in leads),
        *(row.owner_membership_public_id for row in opportunities),
    }
    if customer.owner_membership_public_id:
        owner_ids.add(customer.owner_membership_public_id)
    owner_names = membership_display_names(company=company, public_ids=owner_ids)
    creator_names = creator_display_names({row.created_by_public_id for row in recent_activities})
    return {
        "company": _customer_payload(customer),
        "contacts": [_contact_payload(row) for row in contacts],
        "leads": [_lead_payload(row, owner_names) for row in leads],
        "opportunities": [_opportunity_payload(row, owner_names) for row in opportunities],
        "recent_activity": [
            {
                "public_id": str(row.public_id),
                "activity_type": row.activity_type,
                "status": row.status,
                "subject": row.subject,
                "notes": row.notes,
                "occurred_at": (row.occurred_at or row.completed_at or row.created_at).isoformat(),
                "contact_public_id": str(row.contact.public_id) if row.contact else None,
                "created_by_name": creator_names.get(row.created_by_public_id, "Build360 user"),
            }
            for row in recent_activities
        ],
        "summary": {
            "contact_count": len(contacts),
            "active_lead_count": sum(1 for row in leads if row.converted_at is None and row.disqualified_at is None),
            "open_opportunity_count": sum(1 for row in opportunities if row.won_at is None and row.lost_at is None),
            "open_pipeline_value": str(sum((row.amount for row in opportunities if row.won_at is None and row.lost_at is None), Decimal("0"))),
            "currency": company.currency,
        },
    }
