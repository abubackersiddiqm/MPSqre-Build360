from __future__ import annotations

import uuid
from datetime import timedelta

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from modules.crm.application.logbook import (
    activity_dashboard,
    attach_activity_file,
    lead_timeline,
)
from modules.crm.application.services import (
    RequestActor,
    create_activity,
    create_contact,
    create_lead,
    create_or_reuse_lead_from_contact,
)
from modules.crm.models import Activity, ActivityAttachment, PipelineStage
from modules.files.models import FileObject, FileVersion

pytestmark = pytest.mark.django_db


def actor(membership, user) -> RequestActor:
    return RequestActor(
        user_public_id=user.public_id,
        membership_public_id=membership.public_id,
        request_id=uuid.uuid4(),
    )


def install_lead_stage(company):
    return PipelineStage.objects.create(
        company=company,
        entity_type=PipelineStage.EntityType.LEAD,
        code="new",
        name="New",
        outcome=PipelineStage.Outcome.OPEN,
        sort_order=10,
        probability_percent=5,
        allowed_next_codes=[],
        is_initial=True,
        effective_from=timezone.now() - timedelta(minutes=1),
    )


def test_crm_li_001_contact_metadata_keeps_protected_endpoints(
    company_factory,
    user_factory,
    membership_factory,
):
    company = company_factory()
    user = user_factory()
    membership = membership_factory(user, company)
    contact = create_contact(
        company=company,
        actor=actor(membership, user),
        first_name="Kavin",
        email="kavin@example.test",
        phone="+91 98765 12345",
        address={"formatted": "Coimbatore"},
        source_code="referral",
        tags=["premium", "builder", "premium"],
        notes="Decision maker",
        custom_fields={"preferred_product": "doors"},
    )
    assert contact.email_ciphertext != "kavin@example.test"
    assert contact.phone_ciphertext != "+919876512345"
    assert contact.address == {"formatted": "Coimbatore"}
    assert contact.source_code == "referral"
    assert contact.tags == ["builder", "premium"]
    assert contact.notes == "Decision maker"
    assert contact.custom_fields["preferred_product"] == "doors"
    assert contact.owner_membership_public_id == membership.public_id


def test_crm_li_002_003_logbook_supports_structured_activity_and_stage_history(
    company_factory,
    user_factory,
    membership_factory,
):
    company = company_factory()
    user = user_factory()
    membership = membership_factory(user, company)
    install_lead_stage(company)
    lead = create_lead(
        company=company,
        actor=actor(membership, user),
        title="ABC Construction enquiry",
        source_code="META_ADS",
    )
    create_activity(
        company=company,
        actor=actor(membership, user),
        lead=lead,
        activity_type=Activity.ActivityType.WHATSAPP,
        status=Activity.Status.COMPLETED,
        priority=Activity.Priority.HIGH,
        subject="WhatsApp pricing discussion",
        notes="Customer requested quotation.",
        follow_up_at=timezone.now() + timedelta(days=1),
    )
    payload = lead_timeline(company=company, lead=lead, limit=50)
    kinds = {item["kind"] for item in payload["items"]}
    assert "activity" in kinds
    assert "stage_change" in kinds
    activity = next(item for item in payload["items"] if item["kind"] == "activity")
    assert activity["activity_type"] == "whatsapp"
    assert activity["priority"] == "high"
    assert activity["follow_up_at"] is not None


def test_crm_li_004_008_activity_attachment_is_tenant_scoped_and_scan_gated(
    company_factory,
    user_factory,
    membership_factory,
):
    company = company_factory()
    other = company_factory()
    user = user_factory()
    membership = membership_factory(user, company)
    install_lead_stage(company)
    lead = create_lead(company=company, actor=actor(membership, user), title="Attachment lead")
    activity = create_activity(
        company=company,
        actor=actor(membership, user),
        lead=lead,
        activity_type=Activity.ActivityType.DOCUMENT,
        status=Activity.Status.COMPLETED,
        subject="Quotation received",
    )
    own_file = FileObject.objects.create(
        company=company,
        purpose_code="crm_activity_attachment",
        data_class="internal",
        created_by_public_id=user.public_id,
    )
    FileVersion.objects.create(
        file_object=own_file,
        version=1,
        object_key="companies/test/crm/activity/quotation.pdf",
        original_name="quotation.pdf",
        content_type="application/pdf",
        expected_size_bytes=10,
        actual_size_bytes=10,
        expected_sha256="a" * 64,
        actual_sha256="a" * 64,
        upload_status=FileVersion.UploadStatus.FINALIZED,
        scan_status=FileVersion.ScanStatus.PENDING,
        created_by_public_id=user.public_id,
        finalized_at=timezone.now(),
    )
    attachment = attach_activity_file(
        company=company,
        actor=actor(membership, user),
        activity_public_id=activity.public_id,
        file_public_id=own_file.public_id,
        attachment_kind=ActivityAttachment.AttachmentKind.DOCUMENT,
    )
    assert attachment.file_object_public_id == own_file.public_id

    other_file = FileObject.objects.create(
        company=other,
        purpose_code="crm_activity_attachment",
        data_class="internal",
        created_by_public_id=user.public_id,
    )
    FileVersion.objects.create(
        file_object=other_file,
        version=1,
        object_key="companies/other/crm/activity/file.pdf",
        original_name="other.pdf",
        content_type="application/pdf",
        expected_size_bytes=10,
        actual_size_bytes=10,
        expected_sha256="b" * 64,
        actual_sha256="b" * 64,
        upload_status=FileVersion.UploadStatus.FINALIZED,
        scan_status=FileVersion.ScanStatus.CLEAN,
        created_by_public_id=user.public_id,
        finalized_at=timezone.now(),
        scan_completed_at=timezone.now(),
    )
    with pytest.raises(ValidationError, match="File was not found"):
        attach_activity_file(
            company=company,
            actor=actor(membership, user),
            activity_public_id=activity.public_id,
            file_public_id=other_file.public_id,
            attachment_kind=ActivityAttachment.AttachmentKind.DOCUMENT,
        )


def test_crm_li_005_activity_dashboard_counts_due_work(
    company_factory,
    user_factory,
    membership_factory,
):
    company = company_factory()
    user = user_factory()
    membership = membership_factory(user, company)
    install_lead_stage(company)
    lead = create_lead(company=company, actor=actor(membership, user), title="Follow-up lead")
    create_activity(
        company=company,
        actor=actor(membership, user),
        lead=lead,
        activity_type=Activity.ActivityType.FOLLOW_UP,
        status=Activity.Status.PLANNED,
        subject="Overdue follow-up",
        scheduled_for=timezone.now() - timedelta(hours=2),
    )
    create_activity(
        company=company,
        actor=actor(membership, user),
        lead=lead,
        activity_type=Activity.ActivityType.CALL,
        status=Activity.Status.PLANNED,
        subject="Upcoming call",
        scheduled_for=timezone.now() + timedelta(days=2),
    )
    payload = activity_dashboard(company=company)
    assert payload["overdue"] == 1
    assert payload["upcoming_7d"] == 1
    assert payload["followups"] >= 1


def test_crm_li_010_contact_to_lead_reuses_contact_and_active_lead(
    company_factory,
    user_factory,
    membership_factory,
):
    company = company_factory()
    user = user_factory()
    membership = membership_factory(user, company)
    install_lead_stage(company)
    contact = create_contact(
        company=company,
        actor=actor(membership, user),
        first_name="Meena",
        phone="+91 90000 00000",
        source_code="referral",
    )
    first, created = create_or_reuse_lead_from_contact(
        company=company,
        actor=actor(membership, user),
        contact_public_id=contact.public_id,
    )
    second, created_again = create_or_reuse_lead_from_contact(
        company=company,
        actor=actor(membership, user),
        contact_public_id=contact.public_id,
    )
    assert created is True
    assert created_again is False
    assert first.public_id == second.public_id
    assert first.primary_contact_id == contact.pk
    assert first.source_code == "referral"
