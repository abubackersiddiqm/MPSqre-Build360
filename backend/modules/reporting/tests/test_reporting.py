import hashlib
import uuid

import pytest
from django.core.exceptions import ValidationError

from modules.platform.actors import RequestActor
from modules.reporting.application.services import create_and_execute_run, render_artifact
from modules.reporting.models import MetricDefinition, SavedReport


@pytest.fixture
def reporting_actor(company_factory, user_factory, membership_factory):
    company = company_factory()
    user = user_factory()
    membership = membership_factory(user, company)
    return company, RequestActor(
        user_public_id=user.public_id,
        membership_public_id=membership.public_id,
        request_id=uuid.uuid4(),
        ip_address="127.0.0.1",
        user_agent="pytest",
    )


@pytest.mark.django_db
def test_report_artifacts_are_reproducible_and_integrity_checked(reporting_actor):
    company, actor = reporting_actor
    MetricDefinition.objects.create(
        company=company,
        code="PROJECTS_ACTIVE",
        name="Active projects",
        domain_code="projects",
        calculation_code="projects.active",
        unit_code="count",
    )
    report = SavedReport.objects.create(
        company=company,
        code="PROJECT_OVERVIEW",
        name="Project overview",
        report_type="operations",
        metric_codes=["PROJECTS_ACTIVE"],
        owner_user_public_id=actor.user_public_id,
        default_export_format=SavedReport.ExportFormat.XLSX,
        visibility=SavedReport.Visibility.COMPANY,
    )
    run = create_and_execute_run(
        company=company,
        actor=actor,
        idempotency_key="report-test-1",
        saved_report_public_id=report.public_id,
    )
    duplicate = create_and_execute_run(
        company=company,
        actor=actor,
        idempotency_key="report-test-1",
        saved_report_public_id=report.public_id,
    )
    content, content_type, extension = render_artifact(run)
    assert duplicate.public_id == run.public_id
    assert extension == "xlsx"
    assert content_type.startswith("application/vnd.openxmlformats")
    assert content.startswith(b"PK")
    assert hashlib.sha256(content).hexdigest() == run.artifact.sha256


@pytest.mark.django_db
def test_report_run_rejects_metric_from_another_company(reporting_actor, company_factory):
    company, actor = reporting_actor
    other = company_factory()
    MetricDefinition.objects.create(
        company=other,
        code="PROJECTS_ACTIVE",
        name="Other projects",
        domain_code="projects",
        calculation_code="projects.active",
    )
    with pytest.raises(ValidationError, match="unavailable"):
        create_and_execute_run(
            company=company,
            actor=actor,
            idempotency_key="cross-tenant-metric",
            metric_codes=["PROJECTS_ACTIVE"],
        )
