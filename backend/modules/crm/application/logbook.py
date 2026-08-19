from __future__ import annotations

import uuid
from datetime import timedelta
from typing import Any

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count, Max, Min, Q
from django.utils import timezone

from modules.crm.models import (
    Activity,
    ActivityAttachment,
    ConversionSnapshot,
    Lead,
    PipelineStage,
    StageHistory,
)
from modules.files.application.services import governed_download_url
from modules.files.models import FileObject, FileVersion
from modules.identity.models import User
from modules.platform.actors import RequestActor
from modules.platform.audit import AuditRecord, append_audit
from modules.platform.events import EventRecord, append_event
from modules.tenant.models import Company, Membership


def lead_card_queryset(*, company: Company):
    now = timezone.now()
    return (
        Lead.objects.select_related("stage", "stage__pipeline", "customer", "primary_contact")
        .filter(company=company)
        .annotate(
            activity_count_value=Count("activities", distinct=True),
            last_activity_at_value=Max("activities__created_at"),
            next_activity_at_value=Min(
                "activities__scheduled_for",
                filter=Q(
                    activities__status=Activity.Status.PLANNED,
                    activities__scheduled_for__gte=now,
                ),
            ),
        )
    )


def membership_display_names(*, company: Company, public_ids: set[uuid.UUID]) -> dict[uuid.UUID, str]:
    if not public_ids:
        return {}
    return {
        item.public_id: item.user.display_name or item.user.email
        for item in Membership.objects.select_related("user").filter(
            company=company,
            public_id__in=public_ids,
        )
    }


def creator_display_names(public_ids: set[uuid.UUID]) -> dict[uuid.UUID, str]:
    if not public_ids:
        return {}
    return {
        item.public_id: item.display_name or item.email
        for item in User.objects.filter(public_id__in=public_ids)
    }


def attachment_payloads(*, company: Company, attachments: list[ActivityAttachment]) -> dict[int, dict[str, Any]]:
    if not attachments:
        return {}
    file_ids = {item.file_object_public_id for item in attachments}
    files = {
        item.public_id: item
        for item in FileObject.objects.filter(company=company, public_id__in=file_ids).prefetch_related("versions")
    }
    payloads: dict[int, dict[str, Any]] = {}
    for attachment in attachments:
        file_object = files.get(attachment.file_object_public_id)
        version = None
        if file_object:
            versions = list(file_object.versions.all())
            version = max(versions, key=lambda row: row.version) if versions else None
        payloads[attachment.pk] = {
            "public_id": str(attachment.public_id),
            "activity_public_id": str(attachment.activity.public_id),
            "file_public_id": str(attachment.file_object_public_id),
            "attachment_kind": attachment.attachment_kind,
            "caption": attachment.caption,
            "original_name": version.original_name if version else "",
            "content_type": version.content_type if version else "",
            "size_bytes": (
                (version.actual_size_bytes or version.expected_size_bytes)
                if version else 0
            ),
            "upload_status": version.upload_status if version else "missing",
            "scan_status": version.scan_status if version else "missing",
            "available": bool(
                file_object
                and file_object.status == FileObject.Status.ACTIVE
                and version
                and version.upload_status == FileVersion.UploadStatus.FINALIZED
                and version.scan_status == FileVersion.ScanStatus.CLEAN
            ),
            "created_at": attachment.created_at.isoformat(),
        }
    return payloads


@transaction.atomic
def attach_activity_file(
    *,
    company: Company,
    actor: RequestActor,
    activity_public_id: uuid.UUID,
    file_public_id: uuid.UUID,
    attachment_kind: str,
    caption: str = "",
) -> ActivityAttachment:
    activity = Activity.objects.filter(
        company=company,
        public_id=activity_public_id,
    ).first()
    if activity is None:
        raise ValidationError("CRM activity was not found")
    file_object = FileObject.objects.filter(
        company=company,
        public_id=file_public_id,
        status=FileObject.Status.ACTIVE,
    ).first()
    if file_object is None:
        raise ValidationError("File was not found")
    version = file_object.versions.order_by("-version").first()
    if version is None or version.upload_status != FileVersion.UploadStatus.FINALIZED:
        raise ValidationError("File must be finalized before it can be attached")
    if version.scan_status == FileVersion.ScanStatus.INFECTED:
        raise ValidationError("Infected files cannot be attached")
    attachment, created = ActivityAttachment.objects.get_or_create(
        company=company,
        activity=activity,
        file_object_public_id=file_object.public_id,
        defaults={
            "attachment_kind": attachment_kind,
            "caption": caption.strip(),
            "created_by_public_id": actor.user_public_id,
        },
    )
    if created:
        append_audit(
            AuditRecord(
                action="crm.activity.attachment.created",
                entity_type="crm_activity_attachment",
                entity_public_id=attachment.public_id,
                actor_public_id=actor.user_public_id,
                company_public_id=company.public_id,
                request_id=actor.request_id,
                correlation_id=actor.request_id,
                after={
                    "activity_public_id": str(activity.public_id),
                    "file_public_id": str(file_object.public_id),
                    "attachment_kind": attachment.attachment_kind,
                    "scan_status": version.scan_status,
                },
            )
        )
        append_event(
            EventRecord(
                event_type="crm.activity_attachment_created",
                aggregate_type="crm_activity",
                aggregate_public_id=activity.public_id,
                aggregate_version=activity.version,
                company_public_id=company.public_id,
                correlation_id=actor.request_id,
                payload={"attachment_public_id": str(attachment.public_id)},
            )
        )
    return attachment


def activity_attachment_download(
    *,
    company: Company,
    actor: RequestActor,
    activity_public_id: uuid.UUID,
    attachment_public_id: uuid.UUID,
) -> dict[str, Any]:
    attachment = (
        ActivityAttachment.objects.select_related("activity")
        .filter(
            company=company,
            activity__public_id=activity_public_id,
            public_id=attachment_public_id,
        )
        .first()
    )
    if attachment is None:
        raise ValidationError("Activity attachment was not found")
    file_object = FileObject.objects.filter(
        company=company,
        public_id=attachment.file_object_public_id,
    ).first()
    if file_object is None:
        raise ValidationError("Attachment file was not found")
    version, url = governed_download_url(file_object=file_object)
    append_audit(
        AuditRecord(
            action="crm.activity.attachment.download",
            entity_type="crm_activity_attachment",
            entity_public_id=attachment.public_id,
            actor_public_id=actor.user_public_id,
            company_public_id=company.public_id,
            request_id=actor.request_id,
            correlation_id=actor.request_id,
            after={
                "file_version_public_id": str(version.public_id),
                "expires_in_seconds": settings.FILE_DOWNLOAD_URL_TTL_SECONDS,
            },
        )
    )
    return {
        "download_url": url,
        "expires_in_seconds": settings.FILE_DOWNLOAD_URL_TTL_SECONDS,
    }


def lead_timeline(*, company: Company, lead: Lead, limit: int = 200) -> dict[str, Any]:
    limit = max(1, min(limit, 500))
    activities = list(
        Activity.objects.prefetch_related("attachments")
        .filter(company=company, lead=lead)
        .order_by("-created_at")[:limit]
    )
    all_attachments = [attachment for activity in activities for attachment in activity.attachments.all()]
    attachment_map = attachment_payloads(company=company, attachments=all_attachments)
    creator_ids = {activity.created_by_public_id for activity in activities}

    histories = list(
        StageHistory.objects.filter(
            company=company,
            entity_type=PipelineStage.EntityType.LEAD,
            entity_public_id=lead.public_id,
        )
        .order_by("-changed_at")[:limit]
    )
    creator_ids.update(row.changed_by_public_id for row in histories)
    creator_names = creator_display_names(creator_ids)

    items: list[dict[str, Any]] = []
    for activity in activities:
        items.append(
            {
                "kind": "activity",
                "public_id": str(activity.public_id),
                "occurred_at": (
                    activity.occurred_at
                    or activity.completed_at
                    or activity.created_at
                ).isoformat(),
                "activity_type": activity.activity_type,
                "status": activity.status,
                "priority": activity.priority,
                "subject": activity.subject,
                "description": activity.notes,
                "scheduled_for": activity.scheduled_for.isoformat() if activity.scheduled_for else None,
                "follow_up_at": activity.follow_up_at.isoformat() if activity.follow_up_at else None,
                "created_by_public_id": str(activity.created_by_public_id),
                "created_by_name": creator_names.get(activity.created_by_public_id, "Build360 user"),
                "attachments": [
                    attachment_map[row.pk] for row in activity.attachments.all()
                    if row.pk in attachment_map
                ],
            }
        )
    for history in histories:
        items.append(
            {
                "kind": "stage_change",
                "public_id": str(history.public_id),
                "occurred_at": history.changed_at.isoformat(),
                "activity_type": "status_change",
                "status": "completed",
                "priority": "normal",
                "subject": f"Lead moved to {history.to_stage_code}",
                "description": (
                    f"{history.from_stage_code or 'Created'} → {history.to_stage_code}"
                    + (f" · {history.reason_code}" if history.reason_code else "")
                ),
                "scheduled_for": None,
                "follow_up_at": None,
                "created_by_public_id": str(history.changed_by_public_id),
                "created_by_name": creator_names.get(history.changed_by_public_id, "Build360 user"),
                "attachments": [],
            }
        )

    conversion = ConversionSnapshot.objects.filter(company=company, lead=lead).first()
    if conversion:
        items.append(
            {
                "kind": "conversion",
                "public_id": str(conversion.public_id),
                "occurred_at": conversion.converted_at.isoformat(),
                "activity_type": "status_change",
                "status": "completed",
                "priority": "normal",
                "subject": "Lead converted",
                "description": "Customer and opportunity were created/reused from the governed conversion snapshot.",
                "scheduled_for": None,
                "follow_up_at": None,
                "created_by_public_id": str(conversion.converted_by_public_id),
                "created_by_name": creator_names.get(conversion.converted_by_public_id, "Build360 user"),
                "attachments": [],
            }
        )

    items.sort(key=lambda row: row["occurred_at"], reverse=True)
    return {
        "lead": {
            "public_id": str(lead.public_id),
            "title": lead.title,
            "source_code": lead.source_code,
            "stage": {
                "code": lead.stage.code,
                "name": lead.stage.name,
                "outcome": lead.stage.outcome,
            },
        },
        "items": items[:limit],
        "count": min(len(items), limit),
    }


def activity_dashboard(*, company: Company) -> dict[str, Any]:
    now = timezone.now()
    today = timezone.localdate()
    week = now + timedelta(days=7)

    planned = Activity.objects.filter(company=company, status=Activity.Status.PLANNED)
    today_items = planned.filter(
        scheduled_for__date=today,
    ).count()
    overdue = planned.filter(
        scheduled_for__lt=now,
    ).count()
    upcoming = planned.filter(
        scheduled_for__gte=now,
        scheduled_for__lte=week,
    ).count()
    followups = planned.filter(
        Q(activity_type=Activity.ActivityType.FOLLOW_UP)
        | Q(follow_up_at__date=today)
    ).count()
    recent_activity = Activity.objects.filter(
        company=company,
        created_at__gte=now - timedelta(days=1),
    ).count()
    unassigned_leads = Lead.objects.filter(
        company=company,
        converted_at__isnull=True,
        disqualified_at__isnull=True,
        owner_membership_public_id__isnull=True,
    ).count()
    recent_leads = Lead.objects.filter(
        company=company,
        created_at__gte=now - timedelta(days=1),
    ).count()
    by_type = list(
        Activity.objects.filter(company=company, created_at__gte=now - timedelta(days=30))
        .values("activity_type")
        .annotate(count=Count("id"))
        .order_by("-count", "activity_type")[:12]
    )
    return {
        "generated_at": now.isoformat(),
        "today": today_items,
        "overdue": overdue,
        "upcoming_7d": upcoming,
        "followups": followups,
        "recent_activity_24h": recent_activity,
        "new_leads_24h": recent_leads,
        "unassigned_leads": unassigned_leads,
        "by_type": by_type,
    }
