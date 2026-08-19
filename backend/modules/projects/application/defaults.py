from __future__ import annotations

from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from modules.projects.models import DeliveryStage
from modules.tenant.models import Company

DEFAULT_DELIVERY_STAGES: dict[str, list[dict[str, object]]] = {
    DeliveryStage.EntityType.PROJECT: [
        {
            "code": "planning",
            "name": "Planning",
            "outcome": DeliveryStage.Outcome.OPEN,
            "sort_order": 10,
            "allowed_next_codes": ["approved", "cancelled"],
            "is_initial": True,
        },
        {
            "code": "approved",
            "name": "Approved",
            "outcome": DeliveryStage.Outcome.APPROVED,
            "sort_order": 20,
            "allowed_next_codes": ["active", "cancelled"],
            "allows_baseline": True,
        },
        {
            "code": "active",
            "name": "Active",
            "outcome": DeliveryStage.Outcome.OPEN,
            "sort_order": 30,
            "allowed_next_codes": ["completed", "cancelled"],
        },
        {
            "code": "completed",
            "name": "Completed",
            "outcome": DeliveryStage.Outcome.COMPLETE,
            "sort_order": 90,
            "allowed_next_codes": [],
        },
        {
            "code": "cancelled",
            "name": "Cancelled",
            "outcome": DeliveryStage.Outcome.CANCELLED,
            "sort_order": 100,
            "allowed_next_codes": [],
        },
    ],
    DeliveryStage.EntityType.TASK: [
        {
            "code": "not_started",
            "name": "Not started",
            "outcome": DeliveryStage.Outcome.OPEN,
            "sort_order": 10,
            "allowed_next_codes": ["in_progress", "cancelled"],
            "is_initial": True,
        },
        {
            "code": "in_progress",
            "name": "In progress",
            "outcome": DeliveryStage.Outcome.OPEN,
            "sort_order": 20,
            "allowed_next_codes": ["blocked", "complete", "cancelled"],
        },
        {
            "code": "blocked",
            "name": "Blocked",
            "outcome": DeliveryStage.Outcome.REVIEW,
            "sort_order": 30,
            "allowed_next_codes": ["in_progress", "cancelled"],
        },
        {
            "code": "complete",
            "name": "Complete",
            "outcome": DeliveryStage.Outcome.COMPLETE,
            "sort_order": 90,
            "allowed_next_codes": [],
        },
        {
            "code": "cancelled",
            "name": "Cancelled",
            "outcome": DeliveryStage.Outcome.CANCELLED,
            "sort_order": 100,
            "allowed_next_codes": [],
        },
    ],
    DeliveryStage.EntityType.DESIGN_VERSION: [
        {
            "code": "draft",
            "name": "Draft",
            "outcome": DeliveryStage.Outcome.OPEN,
            "sort_order": 10,
            "allowed_next_codes": ["review"],
            "is_initial": True,
        },
        {
            "code": "review",
            "name": "Under review",
            "outcome": DeliveryStage.Outcome.REVIEW,
            "sort_order": 20,
            "allowed_next_codes": ["approved", "rejected"],
        },
        {
            "code": "approved",
            "name": "Approved",
            "outcome": DeliveryStage.Outcome.APPROVED,
            "sort_order": 30,
            "allowed_next_codes": ["issued"],
        },
        {
            "code": "rejected",
            "name": "Rejected",
            "outcome": DeliveryStage.Outcome.REJECTED,
            "sort_order": 40,
            "allowed_next_codes": ["draft"],
        },
        {
            "code": "issued",
            "name": "Issued",
            "outcome": DeliveryStage.Outcome.ISSUED,
            "sort_order": 90,
            "allowed_next_codes": ["superseded"],
        },
        {
            "code": "superseded",
            "name": "Superseded",
            "outcome": DeliveryStage.Outcome.SUPERSEDED,
            "sort_order": 100,
            "allowed_next_codes": [],
        },
    ],
    DeliveryStage.EntityType.ESTIMATE_VERSION: [
        {
            "code": "draft",
            "name": "Draft",
            "outcome": DeliveryStage.Outcome.OPEN,
            "sort_order": 10,
            "allowed_next_codes": ["review"],
            "is_initial": True,
        },
        {
            "code": "review",
            "name": "Under review",
            "outcome": DeliveryStage.Outcome.REVIEW,
            "sort_order": 20,
            "allowed_next_codes": ["approved", "rejected"],
        },
        {
            "code": "approved",
            "name": "Approved",
            "outcome": DeliveryStage.Outcome.APPROVED,
            "sort_order": 30,
            "allowed_next_codes": ["superseded"],
            "allows_baseline": True,
        },
        {
            "code": "rejected",
            "name": "Rejected",
            "outcome": DeliveryStage.Outcome.REJECTED,
            "sort_order": 40,
            "allowed_next_codes": ["draft"],
        },
        {
            "code": "superseded",
            "name": "Superseded",
            "outcome": DeliveryStage.Outcome.SUPERSEDED,
            "sort_order": 100,
            "allowed_next_codes": [],
        },
    ],
}


@transaction.atomic
def ensure_default_delivery_stages(company: Company) -> int:
    """Install defaults only for completely unconfigured delivery entity types.

    Existing tenant-defined workflows remain authoritative. The company row is
    locked so concurrent first-use requests cannot create duplicate defaults.
    """

    locked_company = Company.objects.select_for_update().get(pk=company.pk)
    now = timezone.now()
    created_count = 0

    for entity_type, definitions in DEFAULT_DELIVERY_STAGES.items():
        if DeliveryStage.objects.filter(company=locked_company, entity_type=entity_type).exists():
            continue
        for definition in definitions:
            DeliveryStage.objects.create(
                company=locked_company,
                entity_type=entity_type,
                code=str(definition["code"]),
                name=str(definition["name"]),
                outcome=str(definition["outcome"]),
                sort_order=int(definition["sort_order"]),
                allowed_next_codes=list(definition.get("allowed_next_codes", [])),
                is_initial=bool(definition.get("is_initial", False)),
                allows_baseline=bool(definition.get("allows_baseline", False)),
                is_active=True,
                effective_from=now - timedelta(seconds=1),
                effective_to=None,
            )
            created_count += 1

    return created_count
