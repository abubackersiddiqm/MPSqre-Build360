from __future__ import annotations

from typing import Any

from django.db.models import Q
from django.utils import timezone

from modules.design.models import DesignReview
from modules.workflow.models import ApprovalTask


def approval_center_items(*, tenant_context) -> dict[str, Any]:
    """Return the current actor's actionable approval inbox across governed domains.

    This is a projection only: decisions still execute through each owning domain's
    existing decision service and audit trail.
    """
    company = tenant_context.company
    permission_codes = tenant_context.permission_codes()
    role_public_ids = tenant_context.role_public_ids()
    actor_public_id = tenant_context.principal.user.public_id
    now = timezone.now()

    items: list[dict[str, Any]] = []

    role_scope = Q(assigned_role_public_id__isnull=True)
    if role_public_ids:
        role_scope |= Q(assigned_role_public_id__in=role_public_ids)

    workflow_approvals = (
        ApprovalTask.objects.filter(
            company=company,
            status=ApprovalTask.Status.PENDING,
            approval_permission_code__in=permission_codes,
        )
        .filter(
            Q(assigned_user_public_id__isnull=True)
            | Q(assigned_user_public_id=actor_public_id)
        )
        .filter(role_scope)
        .select_related("workflow_instance__definition")
        .order_by("due_at", "created_at")[:100]
    )
    for approval in workflow_approvals:
        instance = approval.workflow_instance
        due_at = approval.due_at
        items.append(
            {
                "kind": "WORKFLOW",
                "public_id": str(approval.public_id),
                "title": instance.definition.name,
                "eyebrow": instance.definition.code,
                "subject_type": instance.subject_type,
                "subject_public_id": str(instance.subject_public_id),
                "transition_code": approval.transition_code,
                "from_state_code": approval.from_state_code,
                "to_state_code": approval.to_state_code,
                "due_at": due_at.isoformat() if due_at else None,
                "requested_at": approval.created_at.isoformat(),
                "overdue": bool(due_at and due_at < now),
                "decision_endpoint": f"/api/approvals/workflow/{approval.public_id}/decision",
                "detail_href": None,
            }
        )

    if "design.review.decide" in permission_codes:
        design_reviews = (
            DesignReview.objects.filter(
                company=company,
                reviewer_membership_public_id=tenant_context.membership.public_id,
                decision=DesignReview.Decision.PENDING,
            )
            .select_related(
                "design_version__document__project",
                "design_version__stage",
            )
            .order_by("requested_at")[:100]
        )
        for review in design_reviews:
            version = review.design_version
            document = version.document
            project = document.project
            items.append(
                {
                    "kind": "DESIGN_REVIEW",
                    "public_id": str(review.public_id),
                    "title": document.title,
                    "eyebrow": f"{project.code} · {document.document_number}",
                    "subject_type": "design_version",
                    "subject_public_id": str(version.public_id),
                    "transition_code": "design_review",
                    "from_state_code": version.stage.code,
                    "to_state_code": "review_decision",
                    "due_at": None,
                    "requested_at": review.requested_at.isoformat(),
                    "overdue": False,
                    "revision_code": version.revision_code,
                    "stage_name": version.stage.name,
                    "record_version": review.version,
                    "decision_endpoint": f"/api/approvals/design/{review.public_id}/decision",
                    "detail_href": f"/project360/design?project={project.public_id}&document={document.public_id}",
                }
            )

    items.sort(
        key=lambda item: (
            0 if item["overdue"] else 1,
            item["due_at"] or "9999-12-31T23:59:59",
            item["requested_at"],
        )
    )

    return {
        "items": items[:150],
        "summary": {
            "pending": len(items),
            "overdue": sum(1 for item in items if item["overdue"]),
            "workflow": sum(1 for item in items if item["kind"] == "WORKFLOW"),
            "design_reviews": sum(1 for item in items if item["kind"] == "DESIGN_REVIEW"),
        },
    }
