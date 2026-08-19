from __future__ import annotations

import hashlib
import json
import uuid
from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone

from modules.compliance.models import (
    AccessReviewCampaign,
    AccessReviewItem,
    ComplianceAssessment,
    ComplianceControl,
    ComplianceFramework,
    ControlEvaluation,
    RiskRegisterItem,
    SecurityException,
)
from modules.identity.models import Role
from modules.platform.actors import RequestActor
from modules.platform.audit import AuditRecord, append_audit
from modules.platform.events import EventRecord, append_event
from modules.tenant.models import Company, Membership


def _audit(
    *,
    actor: RequestActor,
    company: Company,
    action: str,
    entity_type: str,
    entity_public_id: uuid.UUID,
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
            company_public_id=company.public_id,
            request_id=actor.request_id,
            correlation_id=actor.request_id,
            ip_address=actor.ip_address,
            user_agent=actor.user_agent,
            reason_code=reason_code[:100],
            before=before or {},
            after=after or {},
        )
    )


def _event(
    *,
    actor: RequestActor,
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
            correlation_id=actor.request_id,
            company_public_id=company.public_id,
            payload=payload,
        )
    )


def active_membership(company: Company, public_id: uuid.UUID) -> Membership:
    now = timezone.now()
    membership = (
        Membership.objects.select_related("user")
        .filter(
            company=company,
            public_id=public_id,
            effective_from__lte=now,
            suspended_at__isnull=True,
            terminated_at__isnull=True,
            user__is_active=True,
        )
        .filter(Q(effective_to__isnull=True) | Q(effective_to__gt=now))
        .first()
    )
    if membership is None:
        raise ValidationError("An active company membership is required")
    return membership


def compliance_summary(company: Company) -> dict[str, Any]:
    published_frameworks = ComplianceFramework.objects.filter(
        company=company,
        status=ComplianceFramework.Status.PUBLISHED,
    ).count()
    assessments = ComplianceAssessment.objects.filter(company=company)
    latest = assessments.order_by("-created_at").first()
    open_risks = RiskRegisterItem.objects.filter(company=company).exclude(
        status=RiskRegisterItem.Status.CLOSED
    )
    high_risks = open_risks.filter(score__gte=15).count()
    exceptions = SecurityException.objects.filter(
        company=company,
        status=SecurityException.Status.APPROVED,
        expires_at__gt=timezone.now(),
    ).count()
    pending_access = AccessReviewItem.objects.filter(
        company=company,
        decision=AccessReviewItem.Decision.PENDING,
    ).count()
    return {
        "published_frameworks": published_frameworks,
        "latest_assessment_score": (
            str(latest.score_percent) if latest is not None else None
        ),
        "open_risks": open_risks.count(),
        "high_risks": high_risks,
        "active_exceptions": exceptions,
        "pending_access_reviews": pending_access,
    }


def assessment_score(assessment: ComplianceAssessment) -> Decimal:
    evaluations = assessment.evaluations.exclude(
        result__in=[
            ControlEvaluation.Result.PENDING,
            ControlEvaluation.Result.NOT_APPLICABLE,
        ]
    )
    total = evaluations.count()
    if total == 0:
        return Decimal("0.00")
    points = Decimal("0")
    for result in evaluations.values_list("result", flat=True):
        if result == ControlEvaluation.Result.COMPLIANT:
            points += Decimal("1")
        elif result == ControlEvaluation.Result.PARTIAL:
            points += Decimal("0.5")
    return ((points / Decimal(total)) * Decimal("100")).quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP,
    )


def assessment_evidence_digest(assessment: ComplianceAssessment) -> str:
    payload = [
        {
            "control": str(item.control.public_id),
            "result": item.result,
            "reference": item.evidence_reference,
            "summary": item.evidence_summary,
            "remediation_due_at": (
                item.remediation_due_at.isoformat()
                if item.remediation_due_at
                else None
            ),
        }
        for item in assessment.evaluations.select_related("control").order_by(
            "control__code"
        )
    ]
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@transaction.atomic
def create_assessment(
    *,
    company: Company,
    actor: RequestActor,
    framework_public_id: uuid.UUID,
    assessment_code: str,
    assessment_type: str,
    scope: str,
    period_start: date,
    period_end: date,
    assessor_membership_public_id: uuid.UUID,
) -> ComplianceAssessment:
    framework = ComplianceFramework.objects.filter(
        company=company,
        public_id=framework_public_id,
        status=ComplianceFramework.Status.PUBLISHED,
    ).first()
    if framework is None:
        raise ValidationError("A published compliance framework is required")
    assessor = active_membership(company, assessor_membership_public_id)
    assessment = ComplianceAssessment(
        company=company,
        framework=framework,
        assessment_code=assessment_code.strip().upper(),
        assessment_type=assessment_type,
        scope=scope.strip(),
        period_start=period_start,
        period_end=period_end,
        assessor_membership=assessor,
        status=ComplianceAssessment.Status.IN_PROGRESS,
    )
    assessment.full_clean()
    assessment.save()
    controls = framework.controls.filter(status=ComplianceControl.Status.ACTIVE)
    ControlEvaluation.objects.bulk_create(
        [
            ControlEvaluation(
                company=company,
                assessment=assessment,
                control=control,
            )
            for control in controls
        ]
    )
    _audit(
        actor=actor,
        company=company,
        action="compliance.assessment.created",
        entity_type="compliance_assessment",
        entity_public_id=assessment.public_id,
        after={
            "framework": framework.code,
            "assessment_code": assessment.assessment_code,
            "controls": controls.count(),
        },
    )
    _event(
        actor=actor,
        company=company,
        event_type="compliance.assessment.created",
        aggregate_type="compliance_assessment",
        aggregate_public_id=assessment.public_id,
        aggregate_version=assessment.version,
        payload={"assessment_code": assessment.assessment_code},
    )
    return assessment


@transaction.atomic
def evaluate_control(
    *,
    company: Company,
    actor: RequestActor,
    evaluation_public_id: uuid.UUID,
    result: str,
    evidence_summary: str,
    evidence_reference: str,
    remediation_due_at: datetime | None,
    expected_version: int,
) -> ControlEvaluation:
    evaluation = (
        ControlEvaluation.objects.select_for_update()
        .select_related("assessment", "control")
        .filter(company=company, public_id=evaluation_public_id)
        .first()
    )
    if evaluation is None:
        raise ValidationError("Control evaluation was not found")
    if evaluation.version != expected_version:
        raise ValidationError("Control evaluation version conflict")
    if evaluation.assessment.status not in {
        ComplianceAssessment.Status.DRAFT,
        ComplianceAssessment.Status.IN_PROGRESS,
    }:
        raise ValidationError("Submitted assessments cannot be edited")
    before = {"result": evaluation.result, "version": evaluation.version}
    evaluation.result = result
    evaluation.evidence_summary = evidence_summary.strip()
    evaluation.evidence_reference = evidence_reference.strip()
    evaluation.remediation_due_at = remediation_due_at
    evaluation.assessed_by_membership = active_membership(
        company, actor.membership_public_id
    )
    evaluation.assessed_at = timezone.now()
    evaluation.version += 1
    evaluation.full_clean()
    evaluation.save()
    _audit(
        actor=actor,
        company=company,
        action="compliance.control.evaluated",
        entity_type="control_evaluation",
        entity_public_id=evaluation.public_id,
        before=before,
        after={"result": evaluation.result, "version": evaluation.version},
    )
    _event(
        actor=actor,
        company=company,
        event_type="compliance.control.evaluated",
        aggregate_type="control_evaluation",
        aggregate_public_id=evaluation.public_id,
        aggregate_version=evaluation.version,
        payload={"result": evaluation.result, "control": evaluation.control.code},
    )
    return evaluation


@transaction.atomic
def transition_assessment(
    *,
    company: Company,
    actor: RequestActor,
    assessment_public_id: uuid.UUID,
    target_status: str,
    expected_version: int,
    decision_reason: str = "",
) -> ComplianceAssessment:
    assessment = (
        ComplianceAssessment.objects.select_for_update(of=("self",))
        .select_related("assessor_membership", "reviewer_membership")
        .filter(company=company, public_id=assessment_public_id)
        .first()
    )
    if assessment is None:
        raise ValidationError("Compliance assessment was not found")
    if assessment.version != expected_version:
        raise ValidationError("Assessment version conflict")
    allowed = {
        ComplianceAssessment.Status.DRAFT: {ComplianceAssessment.Status.IN_PROGRESS},
        ComplianceAssessment.Status.IN_PROGRESS: {
            ComplianceAssessment.Status.SUBMITTED,
        },
        ComplianceAssessment.Status.SUBMITTED: {
            ComplianceAssessment.Status.APPROVED,
            ComplianceAssessment.Status.REJECTED,
        },
        ComplianceAssessment.Status.REJECTED: {
            ComplianceAssessment.Status.IN_PROGRESS,
        },
        ComplianceAssessment.Status.APPROVED: set(),
    }
    if target_status not in allowed[assessment.status]:
        raise ValidationError("Assessment status transition is not allowed")
    now = timezone.now()
    before = {"status": assessment.status, "version": assessment.version}
    if target_status == ComplianceAssessment.Status.SUBMITTED:
        if assessment.evaluations.filter(result=ControlEvaluation.Result.PENDING).exists():
            raise ValidationError("Every applicable control must be evaluated")
        assessment.score_percent = assessment_score(assessment)
        assessment.evidence_sha256 = assessment_evidence_digest(assessment)
        assessment.submitted_at = now
    elif target_status in {
        ComplianceAssessment.Status.APPROVED,
        ComplianceAssessment.Status.REJECTED,
    }:
        reviewer = active_membership(company, actor.membership_public_id)
        if reviewer.pk == assessment.assessor_membership_id:
            raise ValidationError("The assessor cannot decide their own assessment")
        if not decision_reason.strip():
            raise ValidationError("An assessment decision requires a reason")
        assessment.reviewer_membership = reviewer
        assessment.decided_at = now
        assessment.decision_reason = decision_reason.strip()
    assessment.status = target_status
    assessment.version += 1
    assessment.full_clean()
    assessment.save()
    _audit(
        actor=actor,
        company=company,
        action="compliance.assessment.transitioned",
        entity_type="compliance_assessment",
        entity_public_id=assessment.public_id,
        before=before,
        after={
            "status": assessment.status,
            "version": assessment.version,
            "score_percent": str(assessment.score_percent),
        },
        reason_code=decision_reason,
    )
    _event(
        actor=actor,
        company=company,
        event_type="compliance.assessment.transitioned",
        aggregate_type="compliance_assessment",
        aggregate_public_id=assessment.public_id,
        aggregate_version=assessment.version,
        payload={"status": assessment.status},
    )
    return assessment


@transaction.atomic
def create_risk(
    *,
    company: Company,
    actor: RequestActor,
    risk_code: str,
    title: str,
    description: str,
    category: str,
    likelihood: int,
    impact: int,
    treatment: str,
    treatment_plan: str,
    owner_membership_public_id: uuid.UUID,
    due_at: datetime | None,
) -> RiskRegisterItem:
    owner = active_membership(company, owner_membership_public_id)
    risk = RiskRegisterItem(
        company=company,
        risk_code=risk_code.strip().upper(),
        title=title.strip(),
        description=description.strip(),
        category=category,
        likelihood=likelihood,
        impact=impact,
        score=likelihood * impact,
        treatment=treatment,
        treatment_plan=treatment_plan.strip(),
        owner_membership=owner,
        due_at=due_at,
    )
    risk.full_clean()
    risk.save()
    _audit(
        actor=actor,
        company=company,
        action="compliance.risk.created",
        entity_type="risk_register_item",
        entity_public_id=risk.public_id,
        after={"risk_code": risk.risk_code, "score": risk.score},
    )
    _event(
        actor=actor,
        company=company,
        event_type="compliance.risk.created",
        aggregate_type="risk_register_item",
        aggregate_public_id=risk.public_id,
        aggregate_version=risk.version,
        payload={"risk_code": risk.risk_code, "score": risk.score},
    )
    return risk


@transaction.atomic
def transition_risk(
    *,
    company: Company,
    actor: RequestActor,
    risk_public_id: uuid.UUID,
    target_status: str,
    treatment_plan: str,
    expected_version: int,
) -> RiskRegisterItem:
    risk = (
        RiskRegisterItem.objects.select_for_update()
        .filter(company=company, public_id=risk_public_id)
        .first()
    )
    if risk is None:
        raise ValidationError("Risk was not found")
    if risk.version != expected_version:
        raise ValidationError("Risk version conflict")
    allowed = {
        RiskRegisterItem.Status.OPEN: {
            RiskRegisterItem.Status.TREATMENT,
            RiskRegisterItem.Status.ACCEPTED,
            RiskRegisterItem.Status.CLOSED,
        },
        RiskRegisterItem.Status.TREATMENT: {
            RiskRegisterItem.Status.ACCEPTED,
            RiskRegisterItem.Status.CLOSED,
        },
        RiskRegisterItem.Status.ACCEPTED: {
            RiskRegisterItem.Status.TREATMENT,
            RiskRegisterItem.Status.CLOSED,
        },
        RiskRegisterItem.Status.CLOSED: {RiskRegisterItem.Status.OPEN},
    }
    if target_status not in allowed[risk.status]:
        raise ValidationError("Risk status transition is not allowed")
    if treatment_plan.strip():
        risk.treatment_plan = treatment_plan.strip()
    before = {"status": risk.status, "version": risk.version}
    risk.status = target_status
    if target_status == RiskRegisterItem.Status.ACCEPTED:
        risk.accepted_by_public_id = actor.user_public_id
        risk.accepted_at = timezone.now()
    if target_status == RiskRegisterItem.Status.CLOSED:
        risk.closed_at = timezone.now()
    if target_status == RiskRegisterItem.Status.OPEN:
        risk.closed_at = None
    risk.version += 1
    risk.full_clean()
    risk.save()
    _audit(
        actor=actor,
        company=company,
        action="compliance.risk.transitioned",
        entity_type="risk_register_item",
        entity_public_id=risk.public_id,
        before=before,
        after={"status": risk.status, "version": risk.version},
        reason_code=risk.treatment_plan,
    )
    _event(
        actor=actor,
        company=company,
        event_type="compliance.risk.transitioned",
        aggregate_type="risk_register_item",
        aggregate_public_id=risk.public_id,
        aggregate_version=risk.version,
        payload={"status": risk.status},
    )
    return risk


@transaction.atomic
def request_exception(
    *,
    company: Company,
    actor: RequestActor,
    exception_code: str,
    control_public_id: uuid.UUID | None,
    title: str,
    justification: str,
    compensating_controls: str,
    risk_rating: str,
    expires_at: datetime,
) -> SecurityException:
    control = None
    if control_public_id:
        control = ComplianceControl.objects.filter(
            company=company,
            public_id=control_public_id,
            status=ComplianceControl.Status.ACTIVE,
        ).first()
        if control is None:
            raise ValidationError("Compliance control was not found")
    if expires_at <= timezone.now():
        raise ValidationError("Security exceptions must expire in the future")
    maximum_expiry = timezone.now() + timedelta(
        days=settings.COMPLIANCE_EXCEPTION_MAX_DAYS
    )
    if expires_at > maximum_expiry:
        raise ValidationError(
            "Security exception expiry exceeds the configured maximum duration"
        )
    requester = active_membership(company, actor.membership_public_id)
    item = SecurityException(
        company=company,
        exception_code=exception_code.strip().upper(),
        control=control,
        title=title.strip(),
        justification=justification.strip(),
        compensating_controls=compensating_controls.strip(),
        risk_rating=risk_rating,
        requested_by_membership=requester,
        expires_at=expires_at,
    )
    item.full_clean()
    item.save()
    _audit(
        actor=actor,
        company=company,
        action="compliance.exception.requested",
        entity_type="security_exception",
        entity_public_id=item.public_id,
        after={"exception_code": item.exception_code, "risk_rating": item.risk_rating},
    )
    _event(
        actor=actor,
        company=company,
        event_type="compliance.exception.requested",
        aggregate_type="security_exception",
        aggregate_public_id=item.public_id,
        aggregate_version=item.version,
        payload={"exception_code": item.exception_code},
    )
    return item


@transaction.atomic
def decide_exception(
    *,
    company: Company,
    actor: RequestActor,
    exception_public_id: uuid.UUID,
    target_status: str,
    decision_reason: str,
    expected_version: int,
) -> SecurityException:
    item = (
        SecurityException.objects.select_for_update()
        .select_related("requested_by_membership")
        .filter(company=company, public_id=exception_public_id)
        .first()
    )
    if item is None:
        raise ValidationError("Security exception was not found")
    if item.version != expected_version:
        raise ValidationError("Security exception version conflict")
    allowed = {
        SecurityException.Status.REQUESTED: {
            SecurityException.Status.APPROVED,
            SecurityException.Status.REJECTED,
        },
        SecurityException.Status.APPROVED: {
            SecurityException.Status.REVOKED,
            SecurityException.Status.EXPIRED,
        },
        SecurityException.Status.REJECTED: set(),
        SecurityException.Status.REVOKED: set(),
        SecurityException.Status.EXPIRED: set(),
    }
    if target_status not in allowed[item.status]:
        raise ValidationError("Security exception transition is not allowed")
    if not decision_reason.strip():
        raise ValidationError("A security exception decision requires a reason")
    reviewer = active_membership(company, actor.membership_public_id)
    if reviewer.pk == item.requested_by_membership_id:
        raise ValidationError("The requester cannot decide their own exception")
    before = {"status": item.status, "version": item.version}
    item.status = target_status
    item.reviewer_membership = reviewer
    item.decision_reason = decision_reason.strip()
    item.decided_at = timezone.now()
    item.version += 1
    item.full_clean()
    item.save()
    _audit(
        actor=actor,
        company=company,
        action="compliance.exception.decided",
        entity_type="security_exception",
        entity_public_id=item.public_id,
        before=before,
        after={"status": item.status, "version": item.version},
        reason_code=decision_reason,
    )
    _event(
        actor=actor,
        company=company,
        event_type="compliance.exception.decided",
        aggregate_type="security_exception",
        aggregate_public_id=item.public_id,
        aggregate_version=item.version,
        payload={"status": item.status},
    )
    return item


@transaction.atomic
def create_access_review(
    *,
    company: Company,
    actor: RequestActor,
    campaign_code: str,
    name: str,
    scope: str,
    owner_membership_public_id: uuid.UUID,
    due_at: datetime,
) -> AccessReviewCampaign:
    owner = active_membership(company, owner_membership_public_id)
    campaign = AccessReviewCampaign(
        company=company,
        campaign_code=campaign_code.strip().upper(),
        name=name.strip(),
        scope=scope,
        owner_membership=owner,
        due_at=due_at,
        status=AccessReviewCampaign.Status.ACTIVE,
    )
    campaign.full_clean()
    campaign.save()
    now = timezone.now()
    assignments = (
        company.memberships.filter(
            effective_from__lte=now,
            suspended_at__isnull=True,
            terminated_at__isnull=True,
            user__is_active=True,
        )
        .filter(Q(effective_to__isnull=True) | Q(effective_to__gt=now))
        .select_related("user")
        .prefetch_related("role_assignments")
    )
    role_ids = {
        assignment.role_public_id
        for membership in assignments
        for assignment in membership.role_assignments.filter(
            effective_from__lte=now,
        ).filter(Q(effective_to__isnull=True) | Q(effective_to__gt=now))
    }
    roles = {
        role.public_id: role
        for role in Role.objects.filter(
            company_public_id=company.public_id,
            public_id__in=role_ids,
            retired_at__isnull=True,
        ).prefetch_related("permission_grants")
    }
    items: list[AccessReviewItem] = []
    for membership in assignments:
        active_roles = membership.role_assignments.filter(
            effective_from__lte=now,
        ).filter(Q(effective_to__isnull=True) | Q(effective_to__gt=now))
        for assignment in active_roles:
            role = roles.get(assignment.role_public_id)
            if role is None:
                continue
            permission_count = role.permission_grants.count()
            if (
                scope == AccessReviewCampaign.Scope.PRIVILEGED_ROLES
                and permission_count < 10
            ):
                continue
            items.append(
                AccessReviewItem(
                    company=company,
                    campaign=campaign,
                    membership=membership,
                    role_public_id=role.public_id,
                    role_code=role.code,
                    role_name=role.name,
                    permission_count=permission_count,
                )
            )
    AccessReviewItem.objects.bulk_create(items)
    _audit(
        actor=actor,
        company=company,
        action="compliance.access_review.created",
        entity_type="access_review_campaign",
        entity_public_id=campaign.public_id,
        after={"campaign_code": campaign.campaign_code, "items": len(items)},
    )
    _event(
        actor=actor,
        company=company,
        event_type="compliance.access_review.created",
        aggregate_type="access_review_campaign",
        aggregate_public_id=campaign.public_id,
        aggregate_version=campaign.version,
        payload={"campaign_code": campaign.campaign_code, "items": len(items)},
    )
    return campaign


@transaction.atomic
def decide_access_review_item(
    *,
    company: Company,
    actor: RequestActor,
    item_public_id: uuid.UUID,
    decision: str,
    reason: str,
    expected_version: int,
) -> AccessReviewItem:
    item = (
        AccessReviewItem.objects.select_for_update()
        .select_related("campaign", "membership")
        .filter(company=company, public_id=item_public_id)
        .first()
    )
    if item is None:
        raise ValidationError("Access-review item was not found")
    if item.version != expected_version:
        raise ValidationError("Access-review item version conflict")
    if item.campaign.status != AccessReviewCampaign.Status.ACTIVE:
        raise ValidationError("Only active access reviews can be completed")
    if decision == AccessReviewItem.Decision.PENDING:
        raise ValidationError("A completed review requires a decision")
    if not reason.strip():
        raise ValidationError("An access-review decision requires a reason")
    reviewer = active_membership(company, actor.membership_public_id)
    before = {"decision": item.decision, "version": item.version}
    item.decision = decision
    item.reason = reason.strip()
    item.reviewed_by_membership = reviewer
    item.reviewed_at = timezone.now()
    item.version += 1
    item.full_clean()
    item.save()
    _audit(
        actor=actor,
        company=company,
        action="compliance.access_review.item_decided",
        entity_type="access_review_item",
        entity_public_id=item.public_id,
        before=before,
        after={"decision": item.decision, "version": item.version},
        reason_code=reason,
    )
    _event(
        actor=actor,
        company=company,
        event_type="compliance.access_review.item_decided",
        aggregate_type="access_review_item",
        aggregate_public_id=item.public_id,
        aggregate_version=item.version,
        payload={"decision": item.decision, "role_code": item.role_code},
    )
    return item


@transaction.atomic
def transition_access_review(
    *,
    company: Company,
    actor: RequestActor,
    campaign_public_id: uuid.UUID,
    target_status: str,
    expected_version: int,
) -> AccessReviewCampaign:
    campaign = (
        AccessReviewCampaign.objects.select_for_update()
        .select_related("owner_membership")
        .filter(company=company, public_id=campaign_public_id)
        .first()
    )
    if campaign is None:
        raise ValidationError("Access-review campaign was not found")
    if campaign.version != expected_version:
        raise ValidationError("Access-review campaign version conflict")
    allowed = {
        AccessReviewCampaign.Status.DRAFT: {AccessReviewCampaign.Status.ACTIVE},
        AccessReviewCampaign.Status.ACTIVE: {AccessReviewCampaign.Status.SUBMITTED},
        AccessReviewCampaign.Status.SUBMITTED: {AccessReviewCampaign.Status.APPROVED},
        AccessReviewCampaign.Status.APPROVED: {AccessReviewCampaign.Status.CLOSED},
        AccessReviewCampaign.Status.CLOSED: set(),
    }
    if target_status not in allowed[campaign.status]:
        raise ValidationError("Access-review status transition is not allowed")
    if (
        target_status == AccessReviewCampaign.Status.SUBMITTED
        and campaign.items.filter(decision=AccessReviewItem.Decision.PENDING).exists()
    ):
        raise ValidationError("Every access-review item must be decided")
    reviewer = active_membership(company, actor.membership_public_id)
    if target_status == AccessReviewCampaign.Status.APPROVED:
        if reviewer.pk == campaign.owner_membership_id:
            raise ValidationError("The campaign owner cannot approve their own review")
        campaign.reviewer_membership = reviewer
        campaign.approved_at = timezone.now()
    if target_status == AccessReviewCampaign.Status.SUBMITTED:
        campaign.submitted_at = timezone.now()
    before = {"status": campaign.status, "version": campaign.version}
    campaign.status = target_status
    campaign.version += 1
    campaign.full_clean()
    campaign.save()
    _audit(
        actor=actor,
        company=company,
        action="compliance.access_review.transitioned",
        entity_type="access_review_campaign",
        entity_public_id=campaign.public_id,
        before=before,
        after={"status": campaign.status, "version": campaign.version},
    )
    _event(
        actor=actor,
        company=company,
        event_type="compliance.access_review.transitioned",
        aggregate_type="access_review_campaign",
        aggregate_public_id=campaign.public_id,
        aggregate_version=campaign.version,
        payload={"status": campaign.status},
    )
    return campaign


def compliance_portfolio(company: Company) -> dict[str, Any]:
    frameworks = list(
        ComplianceFramework.objects.filter(company=company)
        .annotate(control_count=Count("controls"))
        .order_by("code", "version_label")[:100]
    )
    assessments = list(
        ComplianceAssessment.objects.select_related(
            "framework",
            "assessor_membership__user",
            "reviewer_membership__user",
        )
        .prefetch_related("evaluations__control")
        .filter(company=company)[:100]
    )
    risks = list(
        RiskRegisterItem.objects.select_related("owner_membership__user")
        .filter(company=company)[:200]
    )
    exceptions = list(
        SecurityException.objects.select_related(
            "control",
            "requested_by_membership__user",
            "reviewer_membership__user",
        )
        .filter(company=company)[:200]
    )
    campaigns = list(
        AccessReviewCampaign.objects.select_related(
            "owner_membership__user",
            "reviewer_membership__user",
        )
        .prefetch_related("items__membership__user")
        .filter(company=company)[:100]
    )
    return {
        "summary": compliance_summary(company),
        "frameworks": frameworks,
        "assessments": assessments,
        "risks": risks,
        "exceptions": exceptions,
        "access_reviews": campaigns,
    }
