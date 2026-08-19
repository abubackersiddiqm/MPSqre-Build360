from __future__ import annotations

import uuid

import pytest
from django.core.exceptions import ValidationError

from modules.files.models import FileObject, FileVersion
from modules.releaseops.application.services import attach_gate_evidence_file
from modules.releaseops.models import ReleaseCandidate, ReleaseGate

pytestmark = pytest.mark.django_db


def test_release_gate_evidence_requires_clean_governed_file(company_factory):
    company = company_factory()
    actor = uuid.uuid4()
    release = ReleaseCandidate.objects.create(
        company=company,
        release_code="R-EVIDENCE",
        version_label="v-test",
        title="Evidence test",
        created_by_public_id=actor,
    )
    gate = ReleaseGate.objects.create(
        company=company,
        release=release,
        code="SECURITY_REVIEW",
        name="Security review",
    )
    file_object = FileObject.objects.create(
        company=company,
        purpose_code="release_evidence",
        data_class="internal",
        created_by_public_id=actor,
    )
    version = FileVersion.objects.create(
        file_object=file_object,
        version=1,
        object_key="release-evidence/test.txt",
        original_name="security-review.txt",
        content_type="text/plain",
        expected_size_bytes=10,
        actual_size_bytes=10,
        expected_sha256="a" * 64,
        actual_sha256="a" * 64,
        upload_status=FileVersion.UploadStatus.FINALIZED,
        scan_status=FileVersion.ScanStatus.PENDING,
        created_by_public_id=actor,
    )
    with pytest.raises(ValidationError):
        attach_gate_evidence_file(
            gate=gate,
            file_public_id=file_object.public_id,
            note="pending scan",
            expected_version=gate.version,
            actor_public_id=actor,
            correlation_id=uuid.uuid4(),
        )
    version.scan_status = FileVersion.ScanStatus.CLEAN
    version.save(update_fields=["scan_status", "updated_at"])
    gate = attach_gate_evidence_file(
        gate=gate,
        file_public_id=file_object.public_id,
        note="security evidence",
        expected_version=gate.version,
        actor_public_id=actor,
        correlation_id=uuid.uuid4(),
    )
    assert gate.evidence["attachments"][0]["file_public_id"] == str(file_object.public_id)
