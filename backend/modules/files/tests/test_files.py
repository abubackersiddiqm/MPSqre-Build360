import uuid
from collections.abc import Callable
from unittest.mock import patch

import pytest
from django.core.exceptions import ValidationError

from modules.files.application.services import (
    finalize_upload,
    governed_download_url,
    initiate_upload,
    record_scan_result,
)
from modules.files.application.storage import StoredObjectMetadata
from modules.files.models import FileObject, FileVersion
from modules.tenant.models import Company


@pytest.mark.django_db
def test_file_requires_checksum_finalization_and_clean_scan(
    company_factory: Callable[..., Company],
) -> None:
    company = company_factory()
    checksum = "a" * 64
    with patch(
        "modules.files.application.services.create_upload_url",
        return_value="https://storage.test/upload",
    ):
        grant = initiate_upload(
            company=company,
            purpose_code="design.document",
            data_class="internal",
            original_name="drawing.pdf",
            content_type="application/pdf",
            size_bytes=1024,
            sha256=checksum,
            actor_public_id=uuid.uuid4(),
            correlation_id=uuid.uuid4(),
        )
    with patch(
        "modules.files.application.services.head_object",
        return_value=StoredObjectMetadata(
            size_bytes=1024,
            sha256=checksum,
            content_type="application/pdf",
        ),
    ):
        finalized = finalize_upload(
            version_public_id=grant.file_version.public_id,
            company=company,
            actor_public_id=uuid.uuid4(),
            correlation_id=uuid.uuid4(),
        )
    assert finalized.upload_status == FileVersion.UploadStatus.FINALIZED
    with pytest.raises(ValidationError, match="not available"):
        governed_download_url(file_object=grant.file_object)

    record_scan_result(
        version_public_id=finalized.public_id,
        clean=True,
        scanner_reference="scanner-test-1",
        correlation_id=uuid.uuid4(),
    )
    with patch(
        "modules.files.application.services.create_download_url",
        return_value="https://storage.test/download",
    ):
        version, url = governed_download_url(file_object=grant.file_object)
    assert version.public_id == finalized.public_id
    assert url.endswith("/download")


@pytest.mark.django_db
def test_checksum_mismatch_is_persistently_rejected(
    company_factory: Callable[..., Company],
) -> None:
    company = company_factory()
    with patch(
        "modules.files.application.services.create_upload_url",
        return_value="https://storage.test/upload",
    ):
        grant = initiate_upload(
            company=company,
            purpose_code="contract.document",
            data_class="confidential",
            original_name="contract.pdf",
            content_type="application/pdf",
            size_bytes=100,
            sha256="a" * 64,
            actor_public_id=uuid.uuid4(),
            correlation_id=uuid.uuid4(),
        )
    with patch(
        "modules.files.application.services.head_object",
        return_value=StoredObjectMetadata(
            size_bytes=100,
            sha256="b" * 64,
            content_type="application/pdf",
        ),
    ):
        with pytest.raises(ValidationError, match="checksum"):
            finalize_upload(
                version_public_id=grant.file_version.public_id,
                company=company,
                actor_public_id=uuid.uuid4(),
                correlation_id=uuid.uuid4(),
            )
    grant.file_version.refresh_from_db()
    assert grant.file_version.upload_status == FileVersion.UploadStatus.REJECTED
    assert grant.file_version.rejection_reason == "checksum_mismatch"


@pytest.mark.django_db
def test_file_metadata_lookup_is_tenant_owned(
    company_factory: Callable[..., Company],
) -> None:
    first = company_factory()
    second = company_factory()
    file_object = FileObject.objects.create(
        company=first,
        purpose_code="test",
        data_class="internal",
        created_by_public_id=uuid.uuid4(),
    )
    assert (
        FileObject.objects.filter(public_id=file_object.public_id, company=second).first()
        is None
    )
