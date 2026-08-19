import uuid
from datetime import timedelta

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from modules.pilotops.application.services import (
    assess_readiness,
    readiness_metrics,
    transition_checklist_item,
    transition_go_live,
)
from modules.pilotops.models import (
    GoLivePlan,
    GoLiveSignoff,
    MasterDataReadiness,
    PilotChecklistItem,
    PilotProgram,
)
from modules.platform.actors import RequestActor


@pytest.fixture
def pilot_context(company_factory, user_factory, membership_factory):
    company = company_factory()
    owner_user = user_factory()
    reviewer_user = user_factory()
    owner = membership_factory(owner_user, company)
    reviewer = membership_factory(reviewer_user, company)
    program = PilotProgram.objects.create(
        company=company,
        cohort_code="PILOT_TEST",
        name="Pilot test",
        status=PilotProgram.Status.PREPARING,
        owner_membership=owner,
        target_go_live_at=timezone.now() + timedelta(days=7),
    )
    checklist = PilotChecklistItem.objects.create(
        company=company,
        program=program,
        code="CONTROL",
        category=PilotChecklistItem.Category.GOVERNANCE,
        title="Required control",
        is_required=True,
        owner_membership=owner,
    )
    master = MasterDataReadiness.objects.create(
        company=company,
        program=program,
        domain_code="company_profile",
        domain_name="Company profile",
        minimum_records=1,
        current_records=1,
        is_required=True,
        status=MasterDataReadiness.Status.READY,
    )
    plan = GoLivePlan.objects.create(company=company, program=program)
    signoff = GoLiveSignoff.objects.create(
        company=company,
        plan=plan,
        code="REVIEW",
        area="governance",
        title="Independent review",
        status=GoLiveSignoff.Status.APPROVED,
        signer_membership=reviewer,
        signed_by_public_id=reviewer_user.public_id,
        signed_at=timezone.now(),
    )
    return {
        "company": company,
        "program": program,
        "checklist": checklist,
        "master": master,
        "plan": plan,
        "signoff": signoff,
        "owner": RequestActor(
            owner_user.public_id,
            owner.public_id,
            uuid.uuid4(),
            "127.0.0.1",
            "pytest",
        ),
        "reviewer": RequestActor(
            reviewer_user.public_id,
            reviewer.public_id,
            uuid.uuid4(),
            "127.0.0.1",
            "pytest",
        ),
    }


@pytest.mark.django_db
def test_readiness_is_evidence_backed_and_append_only(pilot_context):
    item = transition_checklist_item(
        company=pilot_context["company"],
        actor=pilot_context["owner"],
        item_public_id=pilot_context["checklist"].public_id,
        status=PilotChecklistItem.Status.COMPLETED,
        expected_version=1,
        evidence={"reference": "UAT-001"},
    )
    assert item.status == PilotChecklistItem.Status.COMPLETED
    metrics = readiness_metrics(pilot_context["program"])
    assert metrics["ready"] is True
    assessment = assess_readiness(
        company=pilot_context["company"],
        actor=pilot_context["reviewer"],
        program_public_id=pilot_context["program"].public_id,
    )
    assert assessment.score_percent == 100
    with pytest.raises(ValidationError, match="append-only"):
        assessment.save()


@pytest.mark.django_db
def test_go_live_approval_requires_independent_reviewer(pilot_context):
    transition_checklist_item(
        company=pilot_context["company"],
        actor=pilot_context["owner"],
        item_public_id=pilot_context["checklist"].public_id,
        status=PilotChecklistItem.Status.COMPLETED,
        expected_version=1,
    )
    review = transition_go_live(
        company=pilot_context["company"],
        actor=pilot_context["owner"],
        plan_public_id=pilot_context["plan"].public_id,
        target_status=GoLivePlan.Status.IN_REVIEW,
        expected_version=1,
    )
    with pytest.raises(ValidationError, match="independently"):
        transition_go_live(
            company=pilot_context["company"],
            actor=pilot_context["owner"],
            plan_public_id=pilot_context["plan"].public_id,
            target_status=GoLivePlan.Status.APPROVED,
            expected_version=review.version,
        )
    approved = transition_go_live(
        company=pilot_context["company"],
        actor=pilot_context["reviewer"],
        plan_public_id=pilot_context["plan"].public_id,
        target_status=GoLivePlan.Status.APPROVED,
        expected_version=review.version,
    )
    assert approved.status == GoLivePlan.Status.APPROVED
