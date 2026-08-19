from __future__ import annotations

import hashlib
import json
import uuid
from datetime import timedelta
from typing import Any

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q, Sum
from django.utils import timezone

from modules.ai.models import AIInteraction
from modules.communication.models import CommunicationRequest
from modules.controlplane.application.context import PlatformActor
from modules.controlplane.models import (
    SupportAccessRequest,
    TenantAccount,
    TenantUsageSnapshot,
)
from modules.files.models import FileVersion
from modules.platform.actors import RequestActor
from modules.platform.audit import AuditRecord, append_audit
from modules.platform.events import EventRecord, append_event
from modules.projects.models import Project
from modules.subscription.models import CompanySubscription, PlanVersion
from modules.tenant.models import Company, Membership
from modules.vendor.models import VendorProfile

ACTIVE_SUBSCRIPTION_STATUSES = {
    CompanySubscription.Status.TRIAL,
    CompanySubscription.Status.ACTIVE,
    CompanySubscription.Status.GRACE,
}
SUPPORT_SCOPE_CODES = {
    "tenant.read_only",
    "tenant.diagnostics",
    "tenant.audit",
    "tenant.configuration",
}


def _audit(
    *,
    actor: PlatformActor | RequestActor,
    action: str,
    entity_type: str,
    entity_public_id: uuid.UUID,
    company_public_id: uuid.UUID | None = None,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
    reason_code: str = "",
) -> None:
    append_audit(
        AuditRecord(
            action=action,
            entity_type=entity_type,
            entity_public_id=entity_public_id,
            actor_public_id=actor.user_public_id,
            actor_type=(
                "platform_operator" if isinstance(actor, PlatformActor) else "user"
            ),
            company_public_id=company_public_id,
            request_id=actor.request_id,
            correlation_id=actor.request_id,
            ip_address=actor.ip_address,
            user_agent=actor.user_agent,
            before=before or {},
            after=after or {},
            reason_code=reason_code,
        )
    )


def _event(
    *,
    actor: PlatformActor,
    company: Company,
    event_type: str,
    aggregate_type: str,
    aggregate_public_id: uuid.UUID,
    aggregate_version: int,
    payload: dict[str, Any],
) -> None:
    append_event(
        EventRecord(
            event_type=event_type,
            aggregate_type=aggregate_type,
            aggregate_public_id=aggregate_public_id,
            aggregate_version=aggregate_version,
            company_public_id=company.public_id,
            correlation_id=actor.request_id,
            payload=payload,
        )
    )


def current_subscription(company: Company) -> CompanySubscription | None:
    moment = timezone.now()
    return (
        CompanySubscription.objects.select_related("plan_version")
        .filter(company=company, starts_at__lte=moment, status__in=ACTIVE_SUBSCRIPTION_STATUSES)
        .filter(Q(ends_at__isnull=True) | Q(ends_at__gt=moment))
        .filter(Q(grace_until__isnull=True) | Q(grace_until__gt=moment))
        .order_by("-starts_at")
        .first()
    )


def controlplane_summary() -> dict[str, int]:
    now = timezone.now()
    active_subscriptions = (
        CompanySubscription.objects.filter(
            status__in=ACTIVE_SUBSCRIPTION_STATUSES,
            starts_at__lte=now,
        )
        .filter(Q(ends_at__isnull=True) | Q(ends_at__gt=now))
        .count()
    )
    latest_snapshots: list[TenantUsageSnapshot] = []
    for tenant_id in TenantAccount.objects.values_list("id", flat=True):
        item = (
            TenantUsageSnapshot.objects.filter(tenant_account_id=tenant_id)
            .order_by("-period_end")
            .first()
        )
        if item:
            latest_snapshots.append(item)
    quota_breaches = sum(
        1
        for snapshot in latest_snapshots
        if any(
            isinstance(value, dict) and bool(value.get("exceeded"))
            for value in snapshot.quota_status.values()
        )
    )
    return {
        "total_tenants": TenantAccount.objects.count(),
        "active_tenants": TenantAccount.objects.filter(
            lifecycle_status__in=[
                TenantAccount.LifecycleStatus.PILOT,
                TenantAccount.LifecycleStatus.ACTIVE,
                TenantAccount.LifecycleStatus.GRACE,
            ]
        ).count(),
        "suspended_tenants": TenantAccount.objects.filter(
            lifecycle_status=TenantAccount.LifecycleStatus.SUSPENDED
        ).count(),
        "active_subscriptions": active_subscriptions,
        "quota_breaches": quota_breaches,
        "open_support_requests": SupportAccessRequest.objects.filter(
            status__in=[
                SupportAccessRequest.Status.REQUESTED,
                SupportAccessRequest.Status.APPROVED,
            ],
            expires_at__gt=now,
        ).count(),
    }


@transaction.atomic
def transition_tenant_lifecycle(
    *,
    tenant_public_id: uuid.UUID,
    target_status: str,
    expected_version: int,
    reason: str,
    actor: PlatformActor,
    grace_until: Any | None = None,
) -> TenantAccount:
    tenant = (
        TenantAccount.objects.select_for_update()
        .select_related("company")
        .filter(public_id=tenant_public_id)
        .first()
    )
    if tenant is None:
        raise ValidationError("Tenant account was not found")
    if tenant.version != expected_version:
        raise ValidationError("Tenant lifecycle version conflict")
    allowed = {
        TenantAccount.LifecycleStatus.PILOT: {
            TenantAccount.LifecycleStatus.ACTIVE,
            TenantAccount.LifecycleStatus.SUSPENDED,
            TenantAccount.LifecycleStatus.CLOSED,
        },
        TenantAccount.LifecycleStatus.ACTIVE: {
            TenantAccount.LifecycleStatus.GRACE,
            TenantAccount.LifecycleStatus.SUSPENDED,
            TenantAccount.LifecycleStatus.CLOSED,
        },
        TenantAccount.LifecycleStatus.GRACE: {
            TenantAccount.LifecycleStatus.ACTIVE,
            TenantAccount.LifecycleStatus.SUSPENDED,
            TenantAccount.LifecycleStatus.CLOSED,
        },
        TenantAccount.LifecycleStatus.SUSPENDED: {
            TenantAccount.LifecycleStatus.ACTIVE,
            TenantAccount.LifecycleStatus.CLOSED,
        },
        TenantAccount.LifecycleStatus.CLOSED: set(),
    }
    if target_status not in allowed[tenant.lifecycle_status]:
        raise ValidationError("Tenant lifecycle transition is not allowed")
    now = timezone.now()
    before = tenant.lifecycle_status
    tenant.lifecycle_status = target_status
    tenant.lifecycle_reason = reason.strip()
    tenant.grace_until = None
    if target_status == TenantAccount.LifecycleStatus.ACTIVE:
        tenant.activated_at = tenant.activated_at or now
        tenant.suspended_at = None
        tenant.company.is_active = True
        tenant.company.suspended_at = None
    elif target_status == TenantAccount.LifecycleStatus.GRACE:
        if grace_until is None or grace_until <= now:
            raise ValidationError("A future grace-until timestamp is required")
        tenant.grace_until = grace_until
        tenant.company.is_active = True
        tenant.company.suspended_at = None
    elif target_status == TenantAccount.LifecycleStatus.SUSPENDED:
        tenant.suspended_at = now
        tenant.company.is_active = False
        tenant.company.suspended_at = now
    elif target_status == TenantAccount.LifecycleStatus.CLOSED:
        tenant.closed_at = now
        tenant.company.is_active = False
        tenant.company.closed_at = now
    tenant.version += 1
    tenant.full_clean()
    tenant.company.full_clean()
    tenant.company.save()
    tenant.save()
    _audit(
        actor=actor,
        action="controlplane.tenant.lifecycle_changed",
        entity_type="tenant_account",
        entity_public_id=tenant.public_id,
        company_public_id=tenant.company.public_id,
        before={"status": before},
        after={"status": tenant.lifecycle_status, "version": tenant.version},
        reason_code=reason.strip(),
    )
    _event(
        actor=actor,
        company=tenant.company,
        event_type="controlplane.tenant.lifecycle_changed",
        aggregate_type="tenant_account",
        aggregate_public_id=tenant.public_id,
        aggregate_version=tenant.version,
        payload={"from": before, "to": tenant.lifecycle_status},
    )
    return tenant


@transaction.atomic
def create_plan(
    *,
    code: str,
    version: int,
    name: str,
    entitlements: dict[str, bool],
    limits: dict[str, int | None],
    effective_from: Any,
    effective_to: Any | None,
    actor: PlatformActor,
) -> PlanVersion:
    normalized_entitlements = {str(key): bool(value) for key, value in entitlements.items()}
    normalized_limits: dict[str, int | None] = {}
    for key, value in limits.items():
        if value is not None and (not isinstance(value, int) or value < 0):
            raise ValidationError("Plan limits must be non-negative integers or null")
        normalized_limits[str(key)] = value
    plan = PlanVersion(
        code=code.strip().upper(),
        version=version,
        name=name.strip(),
        status=PlanVersion.Status.DRAFT,
        entitlements=normalized_entitlements,
        limits=normalized_limits,
        effective_from=effective_from,
        effective_to=effective_to,
    )
    plan.full_clean()
    plan.save()
    _audit(
        actor=actor,
        action="controlplane.plan.created",
        entity_type="plan_version",
        entity_public_id=plan.public_id,
        after={"code": plan.code, "version": plan.version, "status": plan.status},
    )
    return plan


@transaction.atomic
def publish_plan(*, plan_public_id: uuid.UUID, actor: PlatformActor) -> PlanVersion:
    plan = PlanVersion.objects.select_for_update().filter(public_id=plan_public_id).first()
    if plan is None:
        raise ValidationError("Plan version was not found")
    if plan.status != PlanVersion.Status.DRAFT:
        raise ValidationError("Only draft plan versions can be published")
    plan.status = PlanVersion.Status.PUBLISHED
    plan.published_at = timezone.now()
    plan.full_clean()
    plan.save()
    _audit(
        actor=actor,
        action="controlplane.plan.published",
        entity_type="plan_version",
        entity_public_id=plan.public_id,
        after={"code": plan.code, "version": plan.version, "status": plan.status},
    )
    return plan


@transaction.atomic
def assign_subscription(
    *,
    tenant_public_id: uuid.UUID,
    plan_public_id: uuid.UUID,
    status: str,
    starts_at: Any,
    ends_at: Any | None,
    grace_until: Any | None,
    reason: str,
    actor: PlatformActor,
) -> CompanySubscription:
    tenant = TenantAccount.objects.select_related("company").filter(
        public_id=tenant_public_id
    ).first()
    if tenant is None:
        raise ValidationError("Tenant account was not found")
    plan = PlanVersion.objects.filter(
        public_id=plan_public_id,
        status=PlanVersion.Status.PUBLISHED,
    ).first()
    if plan is None:
        raise ValidationError("Published plan version was not found")
    if status not in ACTIVE_SUBSCRIPTION_STATUSES:
        raise ValidationError("A new subscription must be trial, active, or grace")
    if status == CompanySubscription.Status.GRACE and grace_until is None:
        raise ValidationError("Grace subscriptions require grace-until")
    moment = timezone.now()
    previous = list(
        CompanySubscription.objects.select_for_update().filter(
            company=tenant.company,
            status__in=ACTIVE_SUBSCRIPTION_STATUSES,
        )
    )
    for item in previous:
        item.status = CompanySubscription.Status.ENDED
        item.ends_at = min(item.ends_at, moment) if item.ends_at else moment
        item.save(update_fields=["status", "ends_at", "updated_at"])
    subscription = CompanySubscription(
        company=tenant.company,
        plan_version=plan,
        status=status,
        starts_at=starts_at,
        ends_at=ends_at,
        grace_until=grace_until,
    )
    subscription.full_clean()
    subscription.save()
    _audit(
        actor=actor,
        action="controlplane.subscription.assigned",
        entity_type="company_subscription",
        entity_public_id=subscription.public_id,
        company_public_id=tenant.company.public_id,
        before={"replaced": [str(item.public_id) for item in previous]},
        after={"plan": plan.code, "version": plan.version, "status": status},
        reason_code=reason.strip(),
    )
    _event(
        actor=actor,
        company=tenant.company,
        event_type="controlplane.subscription.assigned",
        aggregate_type="company_subscription",
        aggregate_public_id=subscription.public_id,
        aggregate_version=1,
        payload={"plan": plan.code, "version": plan.version, "status": status},
    )
    return subscription


def _usage_metrics(company: Company) -> dict[str, int]:
    now = timezone.now()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    storage_bytes = (
        FileVersion.objects.filter(
            file_object__company=company,
            upload_status=FileVersion.UploadStatus.FINALIZED,
        ).aggregate(total=Sum("actual_size_bytes"))["total"]
        or 0
    )
    active_users = (
        Membership.objects.filter(
            company=company,
            suspended_at__isnull=True,
            terminated_at__isnull=True,
            user__is_active=True,
        )
        .filter(Q(effective_to__isnull=True) | Q(effective_to__gt=now))
        .count()
    )
    return {
        "users": active_users,
        "projects": Project.objects.filter(company=company, archived_at__isnull=True).count(),
        "storage_bytes": int(storage_bytes),
        "ai_interactions_month": AIInteraction.objects.filter(
            company=company,
            created_at__gte=month_start,
        ).count(),
        "communications_month": CommunicationRequest.objects.filter(
            company=company,
            created_at__gte=month_start,
        ).count(),
        "vendors": VendorProfile.objects.filter(company=company).count(),
    }


def _quota_status(company: Company, metrics: dict[str, int]) -> dict[str, dict[str, Any]]:
    subscription = current_subscription(company)
    limits = subscription.plan_version.limits if subscription else {}
    if not isinstance(limits, dict):
        limits = {}
    result: dict[str, dict[str, Any]] = {}
    for code, used in metrics.items():
        raw_limit = limits.get(code)
        limit = raw_limit if isinstance(raw_limit, int) and raw_limit >= 0 else None
        result[code] = {
            "used": used,
            "limit": limit,
            "exceeded": limit is not None and used > limit,
            "utilization_percent": (
                round((used / limit) * 100, 2) if limit not in {None, 0} else None
            ),
        }
    return result


@transaction.atomic
def collect_usage_snapshot(
    *,
    tenant_public_id: uuid.UUID,
    actor: PlatformActor,
) -> TenantUsageSnapshot:
    tenant = TenantAccount.objects.select_related("company").filter(
        public_id=tenant_public_id
    ).first()
    if tenant is None:
        raise ValidationError("Tenant account was not found")
    today = timezone.localdate()
    period_start = today.replace(day=1)
    existing = TenantUsageSnapshot.objects.filter(
        tenant_account=tenant,
        period_start=period_start,
        period_end=today,
    ).first()
    if existing:
        return existing
    metrics = _usage_metrics(tenant.company)
    quota_status = _quota_status(tenant.company, metrics)
    digest_payload = json.dumps(
        {"metrics": metrics, "quota_status": quota_status},
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    item = TenantUsageSnapshot(
        tenant_account=tenant,
        period_start=period_start,
        period_end=today,
        metrics=metrics,
        quota_status=quota_status,
        checksum_sha256=hashlib.sha256(digest_payload).hexdigest(),
        collected_by_public_id=actor.user_public_id,
        collected_at=timezone.now(),
    )
    item.full_clean()
    item.save()
    _audit(
        actor=actor,
        action="controlplane.usage.collected",
        entity_type="tenant_usage_snapshot",
        entity_public_id=item.public_id,
        company_public_id=tenant.company.public_id,
        after={"period_end": str(today), "metrics": metrics},
    )
    return item


@transaction.atomic
def create_support_access_request(
    *,
    tenant_public_id: uuid.UUID,
    reason: str,
    scope_codes: list[str],
    duration_hours: int,
    actor: PlatformActor,
    operator_assignment: Any,
) -> SupportAccessRequest:
    tenant = TenantAccount.objects.select_related("company").filter(
        public_id=tenant_public_id
    ).first()
    if tenant is None:
        raise ValidationError("Tenant account was not found")
    normalized_scopes = sorted({str(value).strip() for value in scope_codes if str(value).strip()})
    invalid_scopes = set(normalized_scopes) - SUPPORT_SCOPE_CODES
    if invalid_scopes:
        raise ValidationError(f"Unsupported support scopes: {', '.join(sorted(invalid_scopes))}")
    max_hours = settings.CONTROLPLANE_SUPPORT_MAX_HOURS
    if not 1 <= duration_hours <= max_hours:
        raise ValidationError(f"Support access duration must be between 1 and {max_hours} hours")
    now = timezone.now()
    item = SupportAccessRequest(
        tenant_account=tenant,
        operator_assignment=operator_assignment,
        requested_by_public_id=actor.user_public_id,
        reason=reason.strip(),
        scope_codes=normalized_scopes,
        requested_at=now,
        expires_at=now + timedelta(hours=duration_hours),
    )
    item.full_clean()
    item.save()
    _audit(
        actor=actor,
        action="controlplane.support.requested",
        entity_type="support_access_request",
        entity_public_id=item.public_id,
        company_public_id=tenant.company.public_id,
        after={"scopes": normalized_scopes, "expires_at": item.expires_at.isoformat()},
        reason_code=reason.strip()[:100],
    )
    _event(
        actor=actor,
        company=tenant.company,
        event_type="controlplane.support.requested",
        aggregate_type="support_access_request",
        aggregate_public_id=item.public_id,
        aggregate_version=item.version,
        payload={"scopes": normalized_scopes, "expires_at": item.expires_at.isoformat()},
    )
    return item


@transaction.atomic
def decide_support_access_request(
    *,
    company: Company,
    request_public_id: uuid.UUID,
    decision: str,
    reason: str,
    actor: RequestActor,
) -> SupportAccessRequest:
    item = (
        SupportAccessRequest.objects.select_for_update()
        .select_related("tenant_account__company", "operator_assignment__user")
        .filter(
            public_id=request_public_id,
            tenant_account__company=company,
        )
        .first()
    )
    if item is None:
        raise ValidationError("Support access request was not found")
    if item.status != SupportAccessRequest.Status.REQUESTED:
        raise ValidationError("Only requested support access can be decided")
    if item.expires_at <= timezone.now():
        item.status = SupportAccessRequest.Status.EXPIRED
        item.version += 1
        item.save(update_fields=["status", "version", "updated_at"])
        raise ValidationError("Support access request has expired")
    if decision not in {
        SupportAccessRequest.Status.APPROVED,
        SupportAccessRequest.Status.REJECTED,
    }:
        raise ValidationError("Support decision must be approved or rejected")
    if decision == SupportAccessRequest.Status.APPROVED and (
        actor.user_public_id == item.requested_by_public_id
    ):
        raise ValidationError("Support access approval requires an independent tenant reviewer")
    item.status = decision
    item.decided_by_membership_public_id = actor.membership_public_id
    item.decided_at = timezone.now()
    item.decision_reason = reason.strip()
    item.version += 1
    item.full_clean()
    item.save()
    _audit(
        actor=actor,
        action="controlplane.support.decided",
        entity_type="support_access_request",
        entity_public_id=item.public_id,
        company_public_id=company.public_id,
        before={"status": SupportAccessRequest.Status.REQUESTED},
        after={"status": item.status, "version": item.version},
        reason_code=reason.strip()[:100],
    )
    return item
