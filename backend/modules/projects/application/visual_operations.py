from __future__ import annotations

from typing import Any

from django.db.models import Prefetch

from modules.design.models import DesignDocument, DesignVersion
from modules.files.models import FileObject, FileVersion
from modules.projects.models import Project


def _file_metadata(file_object: FileObject | None) -> dict[str, Any] | None:
    if file_object is None:
        return None
    versions = list(file_object.versions.all())
    latest = versions[0] if versions else None
    if latest is None:
        return None
    return {
        "public_id": str(file_object.public_id),
        "status": file_object.status,
        "original_name": latest.original_name,
        "content_type": latest.content_type,
        "size_bytes": latest.actual_size_bytes or latest.expected_size_bytes,
        "upload_status": latest.upload_status,
        "scan_status": latest.scan_status,
        "is_image": latest.content_type.startswith("image/"),
        "is_pdf": latest.content_type == "application/pdf",
    }


def project_design_board(
    *,
    company,
    project: Project,
    permission_codes: set[str],
) -> dict[str, Any]:
    """Visual, read-only Design Board projected from governed Design + Files records.

    The board never creates a shadow design record. File download URLs are intentionally
    not generated here because issuing a governed download URL is separately permissioned
    and audited by the Files domain.
    """
    if "design.document.read" not in permission_codes:
        return {
            "available": False,
            "project": {
                "public_id": str(project.public_id),
                "code": project.code,
                "name": project.name,
            },
            "message": "Design documents are restricted for this user.",
            "summary": {},
            "disciplines": [],
            "documents": [],
        }

    version_queryset = (
        DesignVersion.objects.select_related("stage")
        .prefetch_related("reviews", "issues")
        .order_by("-version_number")
    )
    documents = list(
        DesignDocument.objects.filter(
            company=company,
            project=project,
            archived_at__isnull=True,
        )
        .prefetch_related(Prefetch("versions", queryset=version_queryset))
        .order_by("discipline_code", "document_number")[:200]
    )

    file_ids = {
        version.file_object_public_id
        for document in documents
        for version in list(document.versions.all())[:1]
        if version.file_object_public_id
    }
    file_queryset = FileVersion.objects.order_by("-version")
    file_objects = {
        item.public_id: item
        for item in FileObject.objects.filter(
            company=company,
            public_id__in=file_ids,
        ).prefetch_related(Prefetch("versions", queryset=file_queryset))
    }

    cards: list[dict[str, Any]] = []
    disciplines: dict[str, int] = {}
    pending_review_total = 0
    open_issue_total = 0
    approved_total = 0
    issued_total = 0
    with_files = 0

    for document in documents:
        versions = list(document.versions.all())
        latest = versions[0] if versions else None
        disciplines[document.discipline_code] = disciplines.get(document.discipline_code, 0) + 1
        pending_reviews = 0
        open_issues = 0
        if latest is not None:
            pending_reviews = sum(
                1 for review in latest.reviews.all() if review.decision == "pending"
            )
            open_issues = sum(1 for issue in latest.issues.all() if issue.closed_at is None)
        pending_review_total += pending_reviews
        open_issue_total += open_issues

        approved = bool(latest and latest.approved_at)
        issued = bool(latest and latest.issued_at)
        approved_total += int(approved)
        issued_total += int(issued)
        file_info = (
            _file_metadata(file_objects.get(latest.file_object_public_id))
            if latest and latest.file_object_public_id
            else None
        )
        with_files += int(file_info is not None)

        cards.append(
            {
                "public_id": str(document.public_id),
                "document_number": document.document_number,
                "title": document.title,
                "discipline_code": document.discipline_code,
                "document_type_code": document.document_type_code,
                "description": document.description,
                "version_count": len(versions),
                "latest_version": (
                    {
                        "public_id": str(latest.public_id),
                        "version_number": latest.version_number,
                        "revision_code": latest.revision_code,
                        "stage": {
                            "code": latest.stage.code,
                            "name": latest.stage.name,
                            "outcome": latest.stage.outcome,
                        },
                        "description": latest.description,
                        "submitted_at": latest.submitted_at,
                        "approved_at": latest.approved_at,
                        "issued_at": latest.issued_at,
                        "superseded_at": latest.superseded_at,
                        "pending_reviews": pending_reviews,
                        "open_issues": open_issues,
                        "file": file_info,
                    }
                    if latest
                    else None
                ),
            }
        )

    return {
        "available": True,
        "project": {
            "public_id": str(project.public_id),
            "code": project.code,
            "name": project.name,
            "stage_name": project.stage.name,
        },
        "permissions": {
            "can_manage_documents": "design.document.manage" in permission_codes,
            "can_manage_versions": "design.version.manage" in permission_codes,
            "can_request_review": "design.review.manage" in permission_codes,
            "can_decide_review": "design.review.decide" in permission_codes,
            "can_manage_issues": "design.issue.manage" in permission_codes,
            "can_download_files": "files.download" in permission_codes,
        },
        "summary": {
            "documents": len(cards),
            "with_files": with_files,
            "approved_latest": approved_total,
            "issued_latest": issued_total,
            "pending_reviews": pending_review_total,
            "open_issues": open_issue_total,
        },
        "disciplines": [
            {"code": code, "count": count}
            for code, count in sorted(disciplines.items(), key=lambda item: item[0].lower())
        ],
        "documents": cards,
    }
