import hashlib
import uuid

import pytest
from django.core.exceptions import ValidationError

from modules.adminops.application.services import (
    create_feature_flag,
    create_release,
    record_release_check,
    transition_release,
    update_feature_flag,
)
from modules.adminops.models import ReleaseCheck, ReleaseRecord, RuntimeEnvironment
from modules.platform.actors import RequestActor


@pytest.fixture
def adminops_context(company_factory, user_factory, membership_factory):
    company = company_factory()
    requester = user_factory()
    reviewer = user_factory()
    requester_membership = membership_factory(requester, company)
    reviewer_membership = membership_factory(reviewer, company)
    environment = RuntimeEnvironment.objects.create(
        company=company,
        code="STAGING",
        name="Staging",
        environment_type=RuntimeEnvironment.EnvironmentType.STAGING,
        requires_change_approval=True,
    )
    return {
        "company": company,
        "environment": environment,
        "requester": RequestActor(
            user_public_id=requester.public_id,
            membership_public_id=requester_membership.public_id,
            request_id=uuid.uuid4(),
            ip_address="127.0.0.1",
            user_agent="pytest",
        ),
        "reviewer": RequestActor(
            user_public_id=reviewer.public_id,
            membership_public_id=reviewer_membership.public_id,
            request_id=uuid.uuid4(),
            ip_address="127.0.0.1",
            user_agent="pytest",
        ),
    }


@pytest.mark.django_db
def test_release_requires_passing_critical_checks_and_independent_approval(adminops_context):
    release = create_release(
        company=adminops_context["company"],
        actor=adminops_context["requester"],
        environment_public_id=adminops_context["environment"].public_id,
        version_label="0.12.1",
        release_name="Pilot release",
        source_revision="revision-1",
        artifact_sha256=hashlib.sha256(b"artifact").hexdigest(),
    )
    with pytest.raises(ValidationError, match="Critical release checks"):
        transition_release(
            company=adminops_context["company"],
            actor=adminops_context["requester"],
            release_public_id=release.public_id,
            target_status=ReleaseRecord.Status.VALIDATED,
            expected_version=release.version,
        )
    record_release_check(
        company=adminops_context["company"],
        actor=adminops_context["requester"],
        release_public_id=release.public_id,
        code="BACKEND_TESTS",
        name="Backend tests",
        category=ReleaseCheck.Category.API,
        status=ReleaseCheck.Status.PASSED,
        is_critical=True,
        evidence="All backend tests passed",
    )
    validated = transition_release(
        company=adminops_context["company"],
        actor=adminops_context["requester"],
        release_public_id=release.public_id,
        target_status=ReleaseRecord.Status.VALIDATED,
        expected_version=release.version,
    )
    with pytest.raises(ValidationError, match="independent"):
        transition_release(
            company=adminops_context["company"],
            actor=adminops_context["requester"],
            release_public_id=release.public_id,
            target_status=ReleaseRecord.Status.APPROVED,
            expected_version=validated.version,
        )
    approved = transition_release(
        company=adminops_context["company"],
        actor=adminops_context["reviewer"],
        release_public_id=release.public_id,
        target_status=ReleaseRecord.Status.APPROVED,
        expected_version=validated.version,
    )
    assert approved.status == ReleaseRecord.Status.APPROVED
    assert approved.approved_by_public_id == adminops_context["reviewer"].user_public_id


@pytest.mark.django_db
def test_feature_enablement_requires_independent_approval(adminops_context):
    flag = create_feature_flag(
        company=adminops_context["company"],
        actor=adminops_context["requester"],
        code="PILOT_CAPABILITY",
        name="Pilot capability",
        description="Controlled pilot capability",
        scope={"company": "all"},
        requires_approval=True,
    )
    with pytest.raises(ValidationError, match="independent"):
        update_feature_flag(
            company=adminops_context["company"],
            actor=adminops_context["requester"],
            flag_public_id=flag.public_id,
            is_enabled=True,
            rollout_percent=100,
            expected_version=flag.version,
        )
    enabled = update_feature_flag(
        company=adminops_context["company"],
        actor=adminops_context["reviewer"],
        flag_public_id=flag.public_id,
        is_enabled=True,
        rollout_percent=25,
        expected_version=flag.version,
    )
    assert enabled.is_enabled is True
    assert enabled.rollout_percent == 25
