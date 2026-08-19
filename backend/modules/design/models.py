from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import models

from modules.platform.models import TenantOwnedModel
from modules.projects.models import DeliveryStage, Project


class DesignDocument(TenantOwnedModel):
    project = models.ForeignKey(Project, on_delete=models.PROTECT, related_name="design_documents")
    document_number = models.CharField(max_length=120)
    title = models.CharField(max_length=250)
    discipline_code = models.CharField(max_length=80)
    document_type_code = models.CharField(max_length=80)
    description = models.TextField(blank=True)
    created_by_public_id = models.UUIDField()
    version = models.PositiveBigIntegerField(default=1)
    archived_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "design_document"
        constraints = [
            models.UniqueConstraint(
                fields=["company", "project", "document_number"],
                name="des_doc_number_uq",
            )
        ]
        indexes = [
            models.Index(
                fields=["company", "project", "discipline_code"],
                name="des_doc_project_idx",
            )
        ]

    def clean(self) -> None:
        super().clean()
        if self.project_id and self.project.company_id != self.company_id:
            raise ValidationError("Design document project cannot cross companies")


class DesignVersion(TenantOwnedModel):
    document = models.ForeignKey(DesignDocument, on_delete=models.PROTECT, related_name="versions")
    version_number = models.PositiveIntegerField()
    revision_code = models.CharField(max_length=80)
    stage = models.ForeignKey(
        DeliveryStage,
        on_delete=models.PROTECT,
        related_name="design_versions",
    )
    description = models.TextField(blank=True)
    file_object_public_id = models.UUIDField(null=True, blank=True)
    checksum_sha256 = models.CharField(max_length=64, blank=True)
    created_by_public_id = models.UUIDField()
    submitted_at = models.DateTimeField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    issued_at = models.DateTimeField(null=True, blank=True)
    superseded_at = models.DateTimeField(null=True, blank=True)
    version = models.PositiveBigIntegerField(default=1)

    class Meta:
        db_table = "design_version"
        constraints = [
            models.UniqueConstraint(
                fields=["company", "document", "version_number"],
                name="des_version_number_uq",
            ),
            models.UniqueConstraint(
                fields=["company", "document", "revision_code"],
                name="des_revision_code_uq",
            ),
        ]
        indexes = [
            models.Index(
                fields=["company", "document", "stage", "version_number"],
                name="des_version_lookup_idx",
            )
        ]

    def clean(self) -> None:
        super().clean()
        if self.document_id and self.document.company_id != self.company_id:
            raise ValidationError("Design version document cannot cross companies")
        if self.stage_id and (
            self.stage.company_id != self.company_id
            or self.stage.entity_type != DeliveryStage.EntityType.DESIGN_VERSION
        ):
            raise ValidationError("Design version requires a design stage from the same company")


class DesignReview(TenantOwnedModel):
    class Decision(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        APPROVED_WITH_COMMENTS = "approved_with_comments", "Approved with comments"
        REJECTED = "rejected", "Rejected"

    design_version = models.ForeignKey(
        DesignVersion,
        on_delete=models.PROTECT,
        related_name="reviews",
    )
    reviewer_membership_public_id = models.UUIDField()
    decision = models.CharField(
        max_length=40,
        choices=Decision.choices,
        default=Decision.PENDING,
    )
    comments = models.TextField(blank=True)
    requested_by_public_id = models.UUIDField()
    requested_at = models.DateTimeField()
    decided_by_public_id = models.UUIDField(null=True, blank=True)
    decided_at = models.DateTimeField(null=True, blank=True)
    version = models.PositiveBigIntegerField(default=1)

    class Meta:
        db_table = "design_review"
        constraints = [
            models.UniqueConstraint(
                fields=["company", "design_version", "reviewer_membership_public_id"],
                name="des_review_reviewer_uq",
            )
        ]
        indexes = [
            models.Index(
                fields=["company", "reviewer_membership_public_id", "decision"],
                name="des_review_inbox_idx",
            )
        ]

    def clean(self) -> None:
        super().clean()
        if self.design_version_id and self.design_version.company_id != self.company_id:
            raise ValidationError("Design review version cannot cross companies")


class DesignIssue(TenantOwnedModel):
    class Severity(models.TextChoices):
        LOW = "low", "Low"
        MEDIUM = "medium", "Medium"
        HIGH = "high", "High"
        CRITICAL = "critical", "Critical"

    project = models.ForeignKey(Project, on_delete=models.PROTECT, related_name="design_issues")
    design_version = models.ForeignKey(
        DesignVersion,
        on_delete=models.PROTECT,
        related_name="issues",
        null=True,
        blank=True,
    )
    title = models.CharField(max_length=250)
    description = models.TextField(blank=True)
    severity = models.CharField(max_length=20, choices=Severity.choices)
    raised_by_public_id = models.UUIDField()
    assigned_membership_public_id = models.UUIDField(null=True, blank=True)
    due_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    closed_by_public_id = models.UUIDField(null=True, blank=True)
    resolution = models.TextField(blank=True)
    version = models.PositiveBigIntegerField(default=1)

    class Meta:
        db_table = "design_issue"
        indexes = [
            models.Index(
                fields=["company", "project", "closed_at", "severity"],
                name="des_issue_project_idx",
            ),
            models.Index(
                fields=["company", "assigned_membership_public_id", "closed_at"],
                name="des_issue_assignee_idx",
            ),
        ]

    def clean(self) -> None:
        super().clean()
        if self.project_id and self.project.company_id != self.company_id:
            raise ValidationError("Design issue project cannot cross companies")
        if self.design_version_id and (
            self.design_version.company_id != self.company_id
            or self.design_version.document.project_id != self.project_id
        ):
            raise ValidationError("Design issue version must belong to the same project")


class DesignTransmittal(TenantOwnedModel):
    project = models.ForeignKey(Project, on_delete=models.PROTECT, related_name="transmittals")
    reference = models.CharField(max_length=120)
    purpose_code = models.CharField(max_length=80)
    recipient = models.CharField(max_length=250)
    notes = models.TextField(blank=True)
    issued_by_public_id = models.UUIDField()
    issued_at = models.DateTimeField()

    class Meta:
        db_table = "design_transmittal"
        constraints = [
            models.UniqueConstraint(
                fields=["company", "project", "reference"],
                name="des_transmittal_ref_uq",
            )
        ]
        indexes = [
            models.Index(
                fields=["company", "project", "issued_at"],
                name="des_transmittal_lookup_idx",
            )
        ]

    def clean(self) -> None:
        super().clean()
        if self.project_id and self.project.company_id != self.company_id:
            raise ValidationError("Design transmittal project cannot cross companies")


class TransmittalItem(TenantOwnedModel):
    transmittal = models.ForeignKey(
        DesignTransmittal,
        on_delete=models.PROTECT,
        related_name="items",
    )
    design_version = models.ForeignKey(
        DesignVersion,
        on_delete=models.PROTECT,
        related_name="transmittal_items",
    )

    class Meta:
        db_table = "design_transmittal_item"
        constraints = [
            models.UniqueConstraint(
                fields=["company", "transmittal", "design_version"],
                name="des_trans_item_uq",
            )
        ]

    def clean(self) -> None:
        super().clean()
        if self.transmittal_id and self.transmittal.company_id != self.company_id:
            raise ValidationError("Transmittal item cannot cross companies")
        if self.design_version_id and (
            self.design_version.company_id != self.company_id
            or self.design_version.document.project_id != self.transmittal.project_id
        ):
            raise ValidationError("Transmittal version must belong to the same project")
