from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q

from modules.platform.models import TenantOwnedModel


class ComplianceFramework(TenantOwnedModel):
    class FrameworkType(models.TextChoices):
        INTERNAL = "internal", "Internal baseline"
        ISO_27001 = "iso_27001", "ISO 27001 aligned"
        PRIVACY = "privacy", "Privacy readiness"
        CUSTOMER = "customer", "Customer assurance"
        REGULATORY = "regulatory", "Regulatory readiness"

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"
        RETIRED = "retired", "Retired"

    code = models.CharField(max_length=100)
    name = models.CharField(max_length=180)
    framework_type = models.CharField(max_length=24, choices=FrameworkType.choices)
    jurisdiction = models.CharField(max_length=100, blank=True)
    version_label = models.CharField(max_length=60)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    effective_from = models.DateField(null=True, blank=True)
    effective_to = models.DateField(null=True, blank=True)
    certification_claim = models.BooleanField(default=False)
    version = models.PositiveBigIntegerField(default=1)

    class Meta:
        db_table = "compliance_framework"
        ordering = ["code", "version_label"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "code", "version_label"],
                name="cmp_framework_ver_uq",
            ),
            models.CheckConstraint(
                condition=Q(effective_to__isnull=True)
                | Q(effective_from__isnull=False, effective_to__gt=F("effective_from")),
                name="cmp_framework_dates_ck",
            ),
        ]
        indexes = [
            models.Index(
                fields=["company", "framework_type", "status"],
                name="cmp_framework_status_idx",
            )
        ]

    def clean(self) -> None:
        super().clean()
        if self.status == self.Status.PUBLISHED and self.effective_from is None:
            raise ValidationError("A published framework requires an effective date")
        if self.certification_claim:
            raise ValidationError(
                "Build360 readiness frameworks cannot be presented as certifications"
            )


class ComplianceControl(TenantOwnedModel):
    class Domain(models.TextChoices):
        GOVERNANCE = "governance", "Governance"
        ACCESS = "access", "Access control"
        DATA = "data", "Data protection"
        SECURE_DELIVERY = "secure_delivery", "Secure delivery"
        OPERATIONS = "operations", "Security operations"
        INCIDENT = "incident", "Incident response"
        CONTINUITY = "continuity", "Business continuity"
        THIRD_PARTY = "third_party", "Third-party risk"
        PRIVACY = "privacy", "Privacy"

    class Severity(models.TextChoices):
        LOW = "low", "Low"
        MEDIUM = "medium", "Medium"
        HIGH = "high", "High"
        CRITICAL = "critical", "Critical"

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        RETIRED = "retired", "Retired"

    framework = models.ForeignKey(
        ComplianceFramework,
        on_delete=models.PROTECT,
        related_name="controls",
    )
    code = models.CharField(max_length=100)
    title = models.CharField(max_length=220)
    description = models.TextField(blank=True)
    domain = models.CharField(max_length=24, choices=Domain.choices)
    severity = models.CharField(max_length=16, choices=Severity.choices)
    evidence_frequency_days = models.PositiveSmallIntegerField(default=90)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.ACTIVE)
    owner_membership = models.ForeignKey(
        "tenant.Membership",
        on_delete=models.PROTECT,
        related_name="owned_compliance_controls",
        null=True,
        blank=True,
    )
    version = models.PositiveBigIntegerField(default=1)

    class Meta:
        db_table = "compliance_control"
        ordering = ["framework", "code"]
        constraints = [
            models.UniqueConstraint(
                fields=["framework", "code"],
                name="cmp_control_code_uq",
            ),
            models.CheckConstraint(
                condition=Q(evidence_frequency_days__gte=1)
                & Q(evidence_frequency_days__lte=3650),
                name="cmp_control_frequency_ck",
            ),
        ]
        indexes = [
            models.Index(
                fields=["company", "domain", "status"],
                name="cmp_control_domain_idx",
            )
        ]

    def clean(self) -> None:
        super().clean()
        if self.framework_id and self.framework.company_id != self.company_id:
            raise ValidationError("A compliance control cannot cross companies")
        if (
            self.owner_membership_id
            and self.owner_membership.company_id != self.company_id
        ):
            raise ValidationError("A control owner must belong to the same company")


class ComplianceAssessment(TenantOwnedModel):
    class AssessmentType(models.TextChoices):
        INTERNAL = "internal", "Internal"
        READINESS = "readiness", "Readiness"
        CUSTOMER = "customer", "Customer assurance"
        REGULATORY = "regulatory", "Regulatory"

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        IN_PROGRESS = "in_progress", "In progress"
        SUBMITTED = "submitted", "Submitted"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    framework = models.ForeignKey(
        ComplianceFramework,
        on_delete=models.PROTECT,
        related_name="assessments",
    )
    assessment_code = models.CharField(max_length=100)
    assessment_type = models.CharField(max_length=24, choices=AssessmentType.choices)
    scope = models.CharField(max_length=500)
    period_start = models.DateField()
    period_end = models.DateField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    assessor_membership = models.ForeignKey(
        "tenant.Membership",
        on_delete=models.PROTECT,
        related_name="compliance_assessments",
    )
    reviewer_membership = models.ForeignKey(
        "tenant.Membership",
        on_delete=models.PROTECT,
        related_name="reviewed_compliance_assessments",
        null=True,
        blank=True,
    )
    score_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    evidence_sha256 = models.CharField(max_length=64, blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    decided_at = models.DateTimeField(null=True, blank=True)
    decision_reason = models.CharField(max_length=1000, blank=True)
    version = models.PositiveBigIntegerField(default=1)

    class Meta:
        db_table = "compliance_assessment"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "assessment_code"],
                name="cmp_assessment_code_uq",
            ),
            models.CheckConstraint(
                condition=Q(period_end__gte=F("period_start")),
                name="cmp_assessment_period_ck",
            ),
            models.CheckConstraint(
                condition=Q(score_percent__gte=0) & Q(score_percent__lte=100),
                name="cmp_assessment_score_ck",
            ),
        ]
        indexes = [
            models.Index(
                fields=["company", "status", "created_at"],
                name="cmp_assessment_status_idx",
            )
        ]

    def clean(self) -> None:
        super().clean()
        if self.framework_id and self.framework.company_id != self.company_id:
            raise ValidationError("An assessment cannot use another company's framework")
        for membership in (self.assessor_membership, self.reviewer_membership):
            if membership and membership.company_id != self.company_id:
                raise ValidationError("Assessment participants must belong to the company")
        if (
            self.reviewer_membership_id
            and self.reviewer_membership_id == self.assessor_membership_id
        ):
            raise ValidationError("The assessment reviewer must be independent")
        if self.evidence_sha256 and (
            len(self.evidence_sha256) != 64
            or any(char not in "0123456789abcdef" for char in self.evidence_sha256.lower())
        ):
            raise ValidationError({"evidence_sha256": "A SHA-256 digest is required"})


class ControlEvaluation(TenantOwnedModel):
    class Result(models.TextChoices):
        PENDING = "pending", "Pending"
        COMPLIANT = "compliant", "Compliant"
        PARTIAL = "partial", "Partially compliant"
        NON_COMPLIANT = "non_compliant", "Non-compliant"
        NOT_APPLICABLE = "not_applicable", "Not applicable"

    assessment = models.ForeignKey(
        ComplianceAssessment,
        on_delete=models.PROTECT,
        related_name="evaluations",
    )
    control = models.ForeignKey(
        ComplianceControl,
        on_delete=models.PROTECT,
        related_name="evaluations",
    )
    result = models.CharField(max_length=20, choices=Result.choices, default=Result.PENDING)
    evidence_summary = models.TextField(blank=True)
    evidence_reference = models.CharField(max_length=500, blank=True)
    remediation_due_at = models.DateTimeField(null=True, blank=True)
    assessed_by_membership = models.ForeignKey(
        "tenant.Membership",
        on_delete=models.PROTECT,
        related_name="compliance_control_evaluations",
        null=True,
        blank=True,
    )
    assessed_at = models.DateTimeField(null=True, blank=True)
    version = models.PositiveBigIntegerField(default=1)

    class Meta:
        db_table = "compliance_control_evaluation"
        ordering = ["control__code"]
        constraints = [
            models.UniqueConstraint(
                fields=["assessment", "control"],
                name="cmp_evaluation_control_uq",
            )
        ]
        indexes = [
            models.Index(
                fields=["company", "result", "remediation_due_at"],
                name="cmp_evaluation_result_idx",
            )
        ]

    def clean(self) -> None:
        super().clean()
        if self.assessment_id and self.assessment.company_id != self.company_id:
            raise ValidationError("An evaluation cannot cross companies")
        if self.control_id and self.control.company_id != self.company_id:
            raise ValidationError("An evaluation control cannot cross companies")
        if (
            self.assessment_id
            and self.control_id
            and self.control.framework_id != self.assessment.framework_id
        ):
            raise ValidationError("The control must belong to the assessed framework")
        if (
            self.result == self.Result.NON_COMPLIANT
            and self.remediation_due_at is None
        ):
            raise ValidationError("A non-compliant result requires a remediation due date")


class RiskRegisterItem(TenantOwnedModel):
    class Category(models.TextChoices):
        SECURITY = "security", "Security"
        PRIVACY = "privacy", "Privacy"
        AVAILABILITY = "availability", "Availability"
        THIRD_PARTY = "third_party", "Third party"
        COMPLIANCE = "compliance", "Compliance"
        DELIVERY = "delivery", "Delivery"

    class Treatment(models.TextChoices):
        MITIGATE = "mitigate", "Mitigate"
        AVOID = "avoid", "Avoid"
        TRANSFER = "transfer", "Transfer"
        ACCEPT = "accept", "Accept"

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        TREATMENT = "treatment", "Treatment in progress"
        ACCEPTED = "accepted", "Accepted"
        CLOSED = "closed", "Closed"

    risk_code = models.CharField(max_length=100)
    title = models.CharField(max_length=220)
    description = models.TextField(blank=True)
    category = models.CharField(max_length=24, choices=Category.choices)
    likelihood = models.PositiveSmallIntegerField()
    impact = models.PositiveSmallIntegerField()
    score = models.PositiveSmallIntegerField()
    treatment = models.CharField(max_length=16, choices=Treatment.choices)
    treatment_plan = models.TextField(blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.OPEN)
    owner_membership = models.ForeignKey(
        "tenant.Membership",
        on_delete=models.PROTECT,
        related_name="owned_risks",
    )
    due_at = models.DateTimeField(null=True, blank=True)
    accepted_by_public_id = models.UUIDField(null=True, blank=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    version = models.PositiveBigIntegerField(default=1)

    class Meta:
        db_table = "compliance_risk_register"
        ordering = ["-score", "risk_code"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "risk_code"],
                name="cmp_risk_code_uq",
            ),
            models.CheckConstraint(
                condition=Q(likelihood__gte=1) & Q(likelihood__lte=5),
                name="cmp_risk_likelihood_ck",
            ),
            models.CheckConstraint(
                condition=Q(impact__gte=1) & Q(impact__lte=5),
                name="cmp_risk_impact_ck",
            ),
            models.CheckConstraint(
                condition=Q(score__gte=1) & Q(score__lte=25),
                name="cmp_risk_score_ck",
            ),
        ]
        indexes = [
            models.Index(
                fields=["company", "status", "score"],
                name="cmp_risk_status_idx",
            )
        ]

    def clean(self) -> None:
        super().clean()
        if self.owner_membership_id and self.owner_membership.company_id != self.company_id:
            raise ValidationError("A risk owner must belong to the same company")
        if self.score != self.likelihood * self.impact:
            raise ValidationError("Risk score must equal likelihood multiplied by impact")
        if self.treatment == self.Treatment.ACCEPT and not self.treatment_plan:
            raise ValidationError("Accepted risks require documented rationale")


class SecurityException(TenantOwnedModel):
    class RiskRating(models.TextChoices):
        LOW = "low", "Low"
        MEDIUM = "medium", "Medium"
        HIGH = "high", "High"
        CRITICAL = "critical", "Critical"

    class Status(models.TextChoices):
        REQUESTED = "requested", "Requested"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        REVOKED = "revoked", "Revoked"
        EXPIRED = "expired", "Expired"

    exception_code = models.CharField(max_length=100)
    control = models.ForeignKey(
        ComplianceControl,
        on_delete=models.PROTECT,
        related_name="exceptions",
        null=True,
        blank=True,
    )
    title = models.CharField(max_length=220)
    justification = models.TextField()
    compensating_controls = models.TextField()
    risk_rating = models.CharField(max_length=16, choices=RiskRating.choices)
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.REQUESTED,
    )
    requested_by_membership = models.ForeignKey(
        "tenant.Membership",
        on_delete=models.PROTECT,
        related_name="requested_security_exceptions",
    )
    reviewer_membership = models.ForeignKey(
        "tenant.Membership",
        on_delete=models.PROTECT,
        related_name="reviewed_security_exceptions",
        null=True,
        blank=True,
    )
    expires_at = models.DateTimeField()
    decision_reason = models.CharField(max_length=1000, blank=True)
    decided_at = models.DateTimeField(null=True, blank=True)
    version = models.PositiveBigIntegerField(default=1)

    class Meta:
        db_table = "compliance_security_exception"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "exception_code"],
                name="cmp_exception_code_uq",
            )
        ]
        indexes = [
            models.Index(
                fields=["company", "status", "expires_at"],
                name="cmp_exception_status_idx",
            )
        ]

    def clean(self) -> None:
        super().clean()
        if self.control_id and self.control.company_id != self.company_id:
            raise ValidationError("A security exception cannot cross companies")
        for membership in (self.requested_by_membership, self.reviewer_membership):
            if membership and membership.company_id != self.company_id:
                raise ValidationError("Exception participants must belong to the company")
        if (
            self.reviewer_membership_id
            and self.reviewer_membership_id == self.requested_by_membership_id
        ):
            raise ValidationError("The exception reviewer must be independent")
        if self.status == self.Status.APPROVED and not self.decision_reason:
            raise ValidationError("An approved exception requires a decision reason")


class AccessReviewCampaign(TenantOwnedModel):
    class Scope(models.TextChoices):
        ALL_MEMBERSHIPS = "all_memberships", "All active memberships"
        PRIVILEGED_ROLES = "privileged_roles", "Privileged roles"

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        ACTIVE = "active", "Active"
        SUBMITTED = "submitted", "Submitted"
        APPROVED = "approved", "Approved"
        CLOSED = "closed", "Closed"

    campaign_code = models.CharField(max_length=100)
    name = models.CharField(max_length=220)
    scope = models.CharField(max_length=24, choices=Scope.choices)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.DRAFT)
    owner_membership = models.ForeignKey(
        "tenant.Membership",
        on_delete=models.PROTECT,
        related_name="owned_access_reviews",
    )
    reviewer_membership = models.ForeignKey(
        "tenant.Membership",
        on_delete=models.PROTECT,
        related_name="reviewed_access_campaigns",
        null=True,
        blank=True,
    )
    due_at = models.DateTimeField()
    submitted_at = models.DateTimeField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    version = models.PositiveBigIntegerField(default=1)

    class Meta:
        db_table = "compliance_access_review"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "campaign_code"],
                name="cmp_access_review_code_uq",
            )
        ]
        indexes = [
            models.Index(
                fields=["company", "status", "due_at"],
                name="cmp_access_review_idx",
            )
        ]

    def clean(self) -> None:
        super().clean()
        for membership in (self.owner_membership, self.reviewer_membership):
            if membership and membership.company_id != self.company_id:
                raise ValidationError("Access-review participants must belong to the company")
        if (
            self.reviewer_membership_id
            and self.reviewer_membership_id == self.owner_membership_id
        ):
            raise ValidationError("The access-review approver must be independent")


class AccessReviewItem(TenantOwnedModel):
    class Decision(models.TextChoices):
        PENDING = "pending", "Pending"
        RETAIN = "retain", "Retain"
        REMOVE = "remove", "Remove"
        MODIFY = "modify", "Modify"

    campaign = models.ForeignKey(
        AccessReviewCampaign,
        on_delete=models.PROTECT,
        related_name="items",
    )
    membership = models.ForeignKey(
        "tenant.Membership",
        on_delete=models.PROTECT,
        related_name="access_review_items",
    )
    role_public_id = models.UUIDField()
    role_code = models.CharField(max_length=100)
    role_name = models.CharField(max_length=200)
    permission_count = models.PositiveIntegerField(default=0)
    decision = models.CharField(
        max_length=16,
        choices=Decision.choices,
        default=Decision.PENDING,
    )
    reason = models.CharField(max_length=1000, blank=True)
    reviewed_by_membership = models.ForeignKey(
        "tenant.Membership",
        on_delete=models.PROTECT,
        related_name="completed_access_reviews",
        null=True,
        blank=True,
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    version = models.PositiveBigIntegerField(default=1)

    class Meta:
        db_table = "compliance_access_review_item"
        ordering = ["membership__user__email", "role_code"]
        constraints = [
            models.UniqueConstraint(
                fields=["campaign", "membership", "role_public_id"],
                name="cmp_access_item_role_uq",
            )
        ]
        indexes = [
            models.Index(
                fields=["company", "decision", "reviewed_at"],
                name="cmp_access_item_idx",
            )
        ]

    def clean(self) -> None:
        super().clean()
        if self.campaign_id and self.campaign.company_id != self.company_id:
            raise ValidationError("An access-review item cannot cross companies")
        if self.membership_id and self.membership.company_id != self.company_id:
            raise ValidationError("The reviewed membership must belong to the company")
        if (
            self.reviewed_by_membership_id
            and self.reviewed_by_membership.company_id != self.company_id
        ):
            raise ValidationError("The reviewer must belong to the company")
        if self.decision != self.Decision.PENDING and not self.reason:
            raise ValidationError("A completed access-review decision requires a reason")
