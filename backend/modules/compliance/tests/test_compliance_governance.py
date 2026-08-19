import uuid
from datetime import timedelta

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from modules.compliance.application.services import (
    create_access_review,
    create_assessment,
    create_risk,
    decide_access_review_item,
    evaluate_control,
    transition_access_review,
    transition_assessment,
)
from modules.compliance.models import (
    AccessReviewCampaign,
    AccessReviewItem,
    ComplianceAssessment,
    ComplianceControl,
    ComplianceFramework,
    ControlEvaluation,
    RiskRegisterItem,
)
from modules.identity.models import Permission, Role, RolePermission
from modules.platform.actors import RequestActor
from modules.tenant.application.memberships import assign_role


def actor(user, membership):
    return RequestActor(
        user.public_id,
        membership.public_id,
        uuid.uuid4(),
        "127.0.0.1",
        "pytest",
    )


@pytest.mark.django_db
def test_assessment_requires_independent_approval(
    company_factory,
    user_factory,
    membership_factory,
):
    company = company_factory()
    assessor_user = user_factory()
    reviewer_user = user_factory()
    assessor = membership_factory(assessor_user, company)
    reviewer = membership_factory(reviewer_user, company)
    framework = ComplianceFramework.objects.create(
        company=company,
        code="BASELINE",
        name="Baseline",
        framework_type=ComplianceFramework.FrameworkType.INTERNAL,
        version_label="1",
        status=ComplianceFramework.Status.PUBLISHED,
        effective_from=timezone.localdate(),
    )
    ComplianceControl.objects.create(
        company=company,
        framework=framework,
        code="IAM-01",
        title="Tenant access",
        domain=ComplianceControl.Domain.ACCESS,
        severity=ComplianceControl.Severity.CRITICAL,
        owner_membership=assessor,
    )
    assessment = create_assessment(
        company=company,
        actor=actor(assessor_user, assessor),
        framework_public_id=framework.public_id,
        assessment_code="ASSESS-001",
        assessment_type=ComplianceAssessment.AssessmentType.READINESS,
        scope="Pilot tenant",
        period_start=timezone.localdate() - timedelta(days=30),
        period_end=timezone.localdate(),
        assessor_membership_public_id=assessor.public_id,
    )
    evaluation = assessment.evaluations.get()
    evaluate_control(
        company=company,
        actor=actor(assessor_user, assessor),
        evaluation_public_id=evaluation.public_id,
        result=ControlEvaluation.Result.COMPLIANT,
        evidence_summary="Tenant-isolation tests passed",
        evidence_reference="TEST-ACCESS-001",
        remediation_due_at=None,
        expected_version=1,
    )
    submitted = transition_assessment(
        company=company,
        actor=actor(assessor_user, assessor),
        assessment_public_id=assessment.public_id,
        target_status=ComplianceAssessment.Status.SUBMITTED,
        expected_version=1,
    )
    assert submitted.score_percent == 100
    assert len(submitted.evidence_sha256) == 64
    with pytest.raises(ValidationError, match="cannot decide"):
        transition_assessment(
            company=company,
            actor=actor(assessor_user, assessor),
            assessment_public_id=assessment.public_id,
            target_status=ComplianceAssessment.Status.APPROVED,
            expected_version=submitted.version,
            decision_reason="Self approval",
        )
    approved = transition_assessment(
        company=company,
        actor=actor(reviewer_user, reviewer),
        assessment_public_id=assessment.public_id,
        target_status=ComplianceAssessment.Status.APPROVED,
        expected_version=submitted.version,
        decision_reason="Evidence independently reviewed",
    )
    assert approved.status == ComplianceAssessment.Status.APPROVED


@pytest.mark.django_db
def test_risk_score_is_derived_and_validated(
    company_factory,
    user_factory,
    membership_factory,
):
    company = company_factory()
    user = user_factory()
    membership = membership_factory(user, company)
    risk = create_risk(
        company=company,
        actor=actor(user, membership),
        risk_code="RISK-001",
        title="Restore evidence missing",
        description="Restore evidence requires rehearsal",
        category=RiskRegisterItem.Category.AVAILABILITY,
        likelihood=3,
        impact=5,
        treatment=RiskRegisterItem.Treatment.MITIGATE,
        treatment_plan="Run restore rehearsal",
        owner_membership_public_id=membership.public_id,
        due_at=timezone.now() + timedelta(days=7),
    )
    assert risk.score == 15
    risk.score = 14
    with pytest.raises(ValidationError, match="multiplied"):
        risk.full_clean()


@pytest.mark.django_db
def test_access_review_requires_completed_items_and_independent_approval(
    company_factory,
    user_factory,
    membership_factory,
):
    company = company_factory()
    owner_user = user_factory()
    reviewer_user = user_factory()
    owner = membership_factory(owner_user, company)
    reviewer = membership_factory(reviewer_user, company)
    permission = Permission.objects.create(
        code=f"test.permission.{uuid.uuid4().hex[:8]}",
        description="Test permission",
    )
    role = Role.objects.create(
        company_public_id=company.public_id,
        code="ADMIN",
        name="Administrator",
        effective_from=timezone.now() - timedelta(minutes=1),
    )
    RolePermission.objects.create(role=role, permission=permission)
    assign_role(
        membership=owner,
        role=role,
        assigned_by_public_id=owner_user.public_id,
        correlation_id=uuid.uuid4(),
    )
    campaign = create_access_review(
        company=company,
        actor=actor(owner_user, owner),
        campaign_code="ACCESS-Q1",
        name="Quarterly access review",
        scope=AccessReviewCampaign.Scope.ALL_MEMBERSHIPS,
        owner_membership_public_id=owner.public_id,
        due_at=timezone.now() + timedelta(days=14),
    )
    assert campaign.items.count() == 1
    with pytest.raises(ValidationError, match="must be decided"):
        transition_access_review(
            company=company,
            actor=actor(owner_user, owner),
            campaign_public_id=campaign.public_id,
            target_status=AccessReviewCampaign.Status.SUBMITTED,
            expected_version=1,
        )
    review_item = campaign.items.get()
    decide_access_review_item(
        company=company,
        actor=actor(reviewer_user, reviewer),
        item_public_id=review_item.public_id,
        decision=AccessReviewItem.Decision.RETAIN,
        reason="Role remains necessary",
        expected_version=1,
    )
    submitted = transition_access_review(
        company=company,
        actor=actor(owner_user, owner),
        campaign_public_id=campaign.public_id,
        target_status=AccessReviewCampaign.Status.SUBMITTED,
        expected_version=1,
    )
    with pytest.raises(ValidationError, match="owner cannot approve"):
        transition_access_review(
            company=company,
            actor=actor(owner_user, owner),
            campaign_public_id=campaign.public_id,
            target_status=AccessReviewCampaign.Status.APPROVED,
            expected_version=submitted.version,
        )
    approved = transition_access_review(
        company=company,
        actor=actor(reviewer_user, reviewer),
        campaign_public_id=campaign.public_id,
        target_status=AccessReviewCampaign.Status.APPROVED,
        expected_version=submitted.version,
    )
    assert approved.status == AccessReviewCampaign.Status.APPROVED
