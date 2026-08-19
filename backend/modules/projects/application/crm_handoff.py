from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any, Literal

from django.core.exceptions import ValidationError
from django.db import IntegrityError

from modules.crm.models import Opportunity, PipelineStage
from modules.platform.actors import RequestActor
from modules.projects.application.services import create_project
from modules.projects.models import Project
from modules.tenant.models import Company

HandoffMode = Literal["preconstruction", "award"]


@dataclass(frozen=True)
class OpportunityProjectHandoffResult:
    project: Project
    created: bool
    mode: HandoffMode
    opportunity_outcome: str


def create_or_reuse_project_from_crm_opportunity(
    *,
    company: Company,
    actor: RequestActor,
    opportunity_public_id: uuid.UUID,
    mode: HandoffMode,
    code: str = "",
    name: str = "",
    description: str = "",
    location: dict[str, Any] | None = None,
    planned_start_date: Any = None,
    planned_end_date: Any = None,
) -> OpportunityProjectHandoffResult:
    """Create exactly one governed Project for a CRM opportunity.

    The dependency direction is intentional: the Delivery/Projects domain consumes
    CRM opportunity data. CRM core does not need construction concepts to exist.
    """

    opportunity = (
        Opportunity.objects.select_related("customer", "stage")
        .filter(company=company, public_id=opportunity_public_id)
        .first()
    )
    if opportunity is None:
        raise ValidationError("CRM opportunity was not found for this company")

    if mode == "preconstruction":
        if opportunity.stage.outcome == PipelineStage.Outcome.LOST:
            raise ValidationError(
                "A lost opportunity cannot start preconstruction until it is reopened"
            )
    elif mode == "award":
        if opportunity.stage.outcome != PipelineStage.Outcome.WON:
            raise ValidationError("Only a won opportunity can continue as an awarded project")
    else:  # pragma: no cover - serializer/API contract prevents this path
        raise ValidationError("Unsupported CRM handoff mode")

    existing = (
        Project.objects.select_related("stage")
        .filter(company=company, opportunity_public_id=opportunity.public_id)
        .first()
    )
    if existing is not None:
        return OpportunityProjectHandoffResult(
            project=existing,
            created=False,
            mode=mode,
            opportunity_outcome=opportunity.stage.outcome,
        )

    project_code = (code or f"PRJ-{str(opportunity.public_id).replace('-', '')[-8:]}").strip().upper()
    project_name = (name or opportunity.name).strip()
    purpose = "Preconstruction workspace" if mode == "preconstruction" else "Awarded project"

    try:
        project = create_project(
            company=company,
            actor=actor,
            code=project_code,
            name=project_name,
            description=(
                description.strip()
                if description.strip()
                else f"{purpose} created from CRM opportunity {opportunity.name}"
            ),
            customer_public_id=opportunity.customer.public_id,
            opportunity_public_id=opportunity.public_id,
            location=location or {},
            planned_start_date=planned_start_date,
            planned_end_date=planned_end_date,
            currency=opportunity.currency,
            approved_budget=opportunity.amount,
        )
    except IntegrityError:
        # The Project table already has a company+opportunity uniqueness contract.
        # A concurrent retry therefore resolves to the same controlled project.
        project = Project.objects.select_related("stage").filter(
            company=company,
            opportunity_public_id=opportunity.public_id,
        ).first()
        if project is None:
            raise
        return OpportunityProjectHandoffResult(
            project=project,
            created=False,
            mode=mode,
            opportunity_outcome=opportunity.stage.outcome,
        )

    return OpportunityProjectHandoffResult(
        project=project,
        created=True,
        mode=mode,
        opportunity_outcome=opportunity.stage.outcome,
    )
