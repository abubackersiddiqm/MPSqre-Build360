from __future__ import annotations

from typing import Any

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q

from modules.platform.models import PublicIdModel, TimestampedModel
from modules.tenant.models import Company


def _code(value: str) -> str:
    return value.strip().upper()


def _require_code(configuration: dict[str, Any], key: str) -> None:
    value = configuration.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValidationError({"configuration": f"{key} must be a non-empty code"})


def _require_codes(configuration: dict[str, Any], key: str) -> None:
    value = configuration.get(key)
    if not isinstance(value, list) or not all(
        isinstance(item, str) and item.strip() for item in value
    ):
        raise ValidationError(
            {"configuration": f"{key} must be a list of non-empty codes"}
        )


class DocumentControlPolicyVersion(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="document_control_policy_versions",
    )
    code = models.CharField(max_length=80)
    name = models.CharField(max_length=200)
    version = models.PositiveIntegerField()
    status_code = models.CharField(max_length=80)
    effective_from = models.DateTimeField()
    effective_to = models.DateTimeField(null=True, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    retired_at = models.DateTimeField(null=True, blank=True)
    configuration = models.JSONField(default=dict)
    change_note = models.TextField(blank=True)
    created_by_membership_public_id = models.UUIDField(null=True, blank=True)
    published_by_membership_public_id = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = "documentops_policy_version"
        constraints = [
            models.UniqueConstraint(
                fields=["company", "code", "version"], name="dops_pol_code_ver_uq"
            ),
            models.CheckConstraint(
                condition=Q(effective_to__isnull=True)
                | Q(effective_to__gt=F("effective_from")),
                name="dops_pol_range_ck",
            ),
            models.CheckConstraint(
                condition=Q(retired_at__isnull=True)
                | Q(published_at__isnull=False),
                name="dops_pol_retire_ck",
            ),
        ]
        indexes = [
            models.Index(
                fields=["company", "code", "published_at", "retired_at"],
                name="dops_pol_active_ix",
            )
        ]

    def clean(self) -> None:
        super().clean()
        self.code = _code(self.code)
        self.status_code = _code(self.status_code)
        if not isinstance(self.configuration, dict):
            raise ValidationError(
                {"configuration": "Document-control policy must be an object"}
            )
        for key in (
            "initial_document_status",
            "initial_revision_status",
            "initial_transmittal_status",
            "initial_rfi_status",
            "initial_submittal_status",
            "initial_approval_status",
            "initial_risk_status",
            "resolved_risk_status",
        ):
            _require_code(self.configuration, key)
        for key in (
            "active_document_statuses",
            "review_revision_statuses",
            "open_transmittal_statuses",
            "open_rfi_statuses",
            "open_submittal_statuses",
            "critical_priority_codes",
            "approved_submittal_decisions",
        ):
            _require_codes(self.configuration, key)
        for key in (
            "document_transitions",
            "revision_transitions",
            "transmittal_transitions",
            "rfi_transitions",
            "submittal_transitions",
        ):
            if not isinstance(self.configuration.get(key, []), list):
                raise ValidationError({"configuration": f"{key} must be a list"})
        decisions = self.configuration.get("approval_decisions", {})
        if not isinstance(decisions, dict) or not decisions:
            raise ValidationError(
                {"configuration": "approval_decisions must be a non-empty object"}
            )
        if self.effective_to and self.effective_to <= self.effective_from:
            raise ValidationError(
                {"effective_to": "Effective end must follow effective start"}
            )
        if self.retired_at and not self.published_at:
            raise ValidationError({"retired_at": "A draft policy cannot be retired"})


class ControlledDocument(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(
        Company, on_delete=models.PROTECT, related_name="controlled_documents"
    )
    policy = models.ForeignKey(
        DocumentControlPolicyVersion,
        on_delete=models.PROTECT,
        related_name="documents",
    )
    document_number = models.CharField(max_length=120)
    project_public_id = models.UUIDField(null=True, blank=True)
    discipline_code = models.CharField(max_length=100)
    document_type_code = models.CharField(max_length=100)
    title = models.CharField(max_length=300)
    description = models.TextField(blank=True)
    status_code = models.CharField(max_length=80)
    current_revision_code = models.CharField(max_length=40, blank=True)
    confidentiality_code = models.CharField(max_length=80, blank=True)
    originator_membership_public_id = models.UUIDField(null=True, blank=True)
    owner_membership_public_id = models.UUIDField(null=True, blank=True)
    attributes = models.JSONField(default=dict, blank=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "documentops_document"
        constraints = [
            models.UniqueConstraint(
                fields=["company", "document_number"], name="dops_doc_no_uq"
            )
        ]
        indexes = [
            models.Index(
                fields=["company", "status_code", "discipline_code"],
                name="dops_doc_status_ix",
            ),
            models.Index(
                fields=["company", "document_type_code", "project_public_id"],
                name="dops_doc_type_ix",
            ),
        ]

    def clean(self) -> None:
        super().clean()
        for field in (
            "document_number",
            "discipline_code",
            "document_type_code",
            "status_code",
        ):
            setattr(self, field, _code(getattr(self, field)))
        self.current_revision_code = (
            _code(self.current_revision_code) if self.current_revision_code else ""
        )
        self.confidentiality_code = (
            _code(self.confidentiality_code) if self.confidentiality_code else ""
        )
        if self.policy_id and self.company_id and self.policy.company_id != self.company_id:
            raise ValidationError("Document-control policy cannot cross companies")
        if not isinstance(self.attributes, dict):
            raise ValidationError({"attributes": "Document attributes must be an object"})


class DocumentRevision(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(
        Company, on_delete=models.PROTECT, related_name="document_revisions"
    )
    policy = models.ForeignKey(
        DocumentControlPolicyVersion,
        on_delete=models.PROTECT,
        related_name="revisions",
    )
    document = models.ForeignKey(
        ControlledDocument, on_delete=models.PROTECT, related_name="revisions"
    )
    revision_code = models.CharField(max_length=40)
    sequence_number = models.PositiveIntegerField(default=1)
    status_code = models.CharField(max_length=80)
    purpose_code = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    file_reference = models.CharField(max_length=500, blank=True)
    checksum_sha256 = models.CharField(max_length=64, blank=True)
    file_size_bytes = models.PositiveBigIntegerField(null=True, blank=True)
    created_by_membership_public_id = models.UUIDField()
    reviewed_by_membership_public_id = models.UUIDField(null=True, blank=True)
    approved_by_membership_public_id = models.UUIDField(null=True, blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    issued_at = models.DateTimeField(null=True, blank=True)
    superseded_at = models.DateTimeField(null=True, blank=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "documentops_revision"
        constraints = [
            models.UniqueConstraint(
                fields=["company", "document", "revision_code"],
                name="dops_rev_code_uq",
            ),
            models.UniqueConstraint(
                fields=["company", "document", "sequence_number"],
                name="dops_rev_seq_uq",
            ),
            models.CheckConstraint(
                condition=Q(sequence_number__gte=1), name="dops_rev_seq_ck"
            ),
            models.CheckConstraint(
                condition=Q(superseded_at__isnull=True) | Q(issued_at__isnull=False),
                name="dops_rev_super_ck",
            ),
        ]
        indexes = [
            models.Index(
                fields=["company", "status_code", "submitted_at"],
                name="dops_rev_status_ix",
            )
        ]

    def clean(self) -> None:
        super().clean()
        for field in ("revision_code", "status_code", "purpose_code"):
            setattr(self, field, _code(getattr(self, field)))
        if self.policy_id and self.company_id and self.policy.company_id != self.company_id:
            raise ValidationError("Document-control policy cannot cross companies")
        if self.document_id and self.document.company_id != self.company_id:
            raise ValidationError("Controlled document cannot cross companies")
        if self.document_id and self.document.policy_id != self.policy_id:
            raise ValidationError("Revision and document must use the same policy")
        if self.checksum_sha256 and (
            len(self.checksum_sha256) != 64
            or any(character not in "0123456789abcdefABCDEF" for character in self.checksum_sha256)
        ):
            raise ValidationError({"checksum_sha256": "Checksum must be 64 hexadecimal characters"})
        if self.superseded_at and not self.issued_at:
            raise ValidationError({"superseded_at": "Only an issued revision can be superseded"})


class DocumentTransmittal(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(
        Company, on_delete=models.PROTECT, related_name="document_transmittals"
    )
    policy = models.ForeignKey(
        DocumentControlPolicyVersion,
        on_delete=models.PROTECT,
        related_name="transmittals",
    )
    transmittal_number = models.CharField(max_length=120)
    project_public_id = models.UUIDField(null=True, blank=True)
    direction_code = models.CharField(max_length=40)
    status_code = models.CharField(max_length=80)
    subject = models.CharField(max_length=300)
    sender_party_public_id = models.UUIDField(null=True, blank=True)
    recipient_party_public_id = models.UUIDField(null=True, blank=True)
    issued_at = models.DateTimeField(null=True, blank=True)
    due_at = models.DateTimeField(null=True, blank=True)
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    document_manifest = models.JSONField(default=list)
    notes = models.TextField(blank=True)
    created_by_membership_public_id = models.UUIDField()
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "documentops_transmittal"
        constraints = [
            models.UniqueConstraint(
                fields=["company", "transmittal_number"], name="dops_tx_no_uq"
            ),
            models.CheckConstraint(
                condition=Q(due_at__isnull=True)
                | Q(issued_at__isnull=True)
                | Q(due_at__gte=F("issued_at")),
                name="dops_tx_due_ck",
            ),
            models.CheckConstraint(
                condition=Q(closed_at__isnull=True)
                | Q(acknowledged_at__isnull=False),
                name="dops_tx_close_ck",
            ),
        ]
        indexes = [
            models.Index(
                fields=["company", "status_code", "due_at"],
                name="dops_tx_status_ix",
            )
        ]

    def clean(self) -> None:
        super().clean()
        for field in ("transmittal_number", "direction_code", "status_code"):
            setattr(self, field, _code(getattr(self, field)))
        if self.policy_id and self.company_id and self.policy.company_id != self.company_id:
            raise ValidationError("Document-control policy cannot cross companies")
        if not isinstance(self.document_manifest, list):
            raise ValidationError({"document_manifest": "Manifest must be a list"})
        if self.due_at and self.issued_at and self.due_at < self.issued_at:
            raise ValidationError({"due_at": "Due date cannot precede issue date"})
        if self.closed_at and not self.acknowledged_at:
            raise ValidationError({"closed_at": "Acknowledgement is required before closure"})


class RequestForInformation(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(
        Company, on_delete=models.PROTECT, related_name="document_rfis"
    )
    policy = models.ForeignKey(
        DocumentControlPolicyVersion, on_delete=models.PROTECT, related_name="rfis"
    )
    rfi_number = models.CharField(max_length=120)
    project_public_id = models.UUIDField(null=True, blank=True)
    discipline_code = models.CharField(max_length=100)
    priority_code = models.CharField(max_length=80)
    status_code = models.CharField(max_length=80)
    subject = models.CharField(max_length=300)
    question = models.TextField()
    raised_at = models.DateTimeField()
    raised_by_membership_public_id = models.UUIDField()
    assigned_to_membership_public_id = models.UUIDField(null=True, blank=True)
    response_due_at = models.DateTimeField(null=True, blank=True)
    responded_at = models.DateTimeField(null=True, blank=True)
    responded_by_membership_public_id = models.UUIDField(null=True, blank=True)
    response_text = models.TextField(blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    linked_document_public_ids = models.JSONField(default=list)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "documentops_rfi"
        constraints = [
            models.UniqueConstraint(
                fields=["company", "rfi_number"], name="dops_rfi_no_uq"
            ),
            models.CheckConstraint(
                condition=Q(response_due_at__isnull=True)
                | Q(response_due_at__gte=F("raised_at")),
                name="dops_rfi_due_ck",
            ),
            models.CheckConstraint(
                condition=Q(responded_at__isnull=True)
                | Q(responded_by_membership_public_id__isnull=False),
                name="dops_rfi_resp_ck",
            ),
        ]
        indexes = [
            models.Index(
                fields=["company", "status_code", "response_due_at"],
                name="dops_rfi_status_ix",
            ),
            models.Index(
                fields=["company", "priority_code", "discipline_code"],
                name="dops_rfi_priority_ix",
            ),
        ]

    def clean(self) -> None:
        super().clean()
        for field in ("rfi_number", "discipline_code", "priority_code", "status_code"):
            setattr(self, field, _code(getattr(self, field)))
        if self.policy_id and self.company_id and self.policy.company_id != self.company_id:
            raise ValidationError("Document-control policy cannot cross companies")
        if not isinstance(self.linked_document_public_ids, list):
            raise ValidationError(
                {"linked_document_public_ids": "Linked documents must be a list"}
            )
        if self.response_due_at and self.response_due_at < self.raised_at:
            raise ValidationError({"response_due_at": "Response due date cannot precede raised date"})
        if self.responded_at and not self.responded_by_membership_public_id:
            raise ValidationError(
                {"responded_by_membership_public_id": "Responder is required"}
            )
        if self.closed_at and not self.responded_at:
            raise ValidationError({"closed_at": "An RFI must be responded before closure"})


class TechnicalSubmittal(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(
        Company, on_delete=models.PROTECT, related_name="technical_submittals"
    )
    policy = models.ForeignKey(
        DocumentControlPolicyVersion,
        on_delete=models.PROTECT,
        related_name="submittals",
    )
    submittal_number = models.CharField(max_length=120)
    revision_number = models.PositiveIntegerField(default=1)
    project_public_id = models.UUIDField(null=True, blank=True)
    category_code = models.CharField(max_length=100)
    package_code = models.CharField(max_length=120, blank=True)
    status_code = models.CharField(max_length=80)
    title = models.CharField(max_length=300)
    description = models.TextField(blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    review_due_at = models.DateTimeField(null=True, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    submitted_by_membership_public_id = models.UUIDField()
    reviewer_membership_public_id = models.UUIDField(null=True, blank=True)
    decision_code = models.CharField(max_length=80, blank=True)
    decision_note = models.TextField(blank=True)
    linked_document_public_ids = models.JSONField(default=list)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "documentops_submittal"
        constraints = [
            models.UniqueConstraint(
                fields=["company", "submittal_number", "revision_number"],
                name="dops_sub_no_rev_uq",
            ),
            models.CheckConstraint(
                condition=Q(revision_number__gte=1), name="dops_sub_rev_ck"
            ),
            models.CheckConstraint(
                condition=Q(review_due_at__isnull=True)
                | Q(submitted_at__isnull=True)
                | Q(review_due_at__gte=F("submitted_at")),
                name="dops_sub_due_ck",
            ),
            models.CheckConstraint(
                condition=Q(reviewed_at__isnull=True)
                | Q(reviewer_membership_public_id__isnull=False),
                name="dops_sub_review_ck",
            ),
        ]
        indexes = [
            models.Index(
                fields=["company", "status_code", "review_due_at"],
                name="dops_sub_status_ix",
            ),
            models.Index(
                fields=["company", "category_code", "project_public_id"],
                name="dops_sub_category_ix",
            ),
        ]

    def clean(self) -> None:
        super().clean()
        for field in ("submittal_number", "category_code", "status_code"):
            setattr(self, field, _code(getattr(self, field)))
        self.package_code = _code(self.package_code) if self.package_code else ""
        self.decision_code = _code(self.decision_code) if self.decision_code else ""
        if self.policy_id and self.company_id and self.policy.company_id != self.company_id:
            raise ValidationError("Document-control policy cannot cross companies")
        if not isinstance(self.linked_document_public_ids, list):
            raise ValidationError(
                {"linked_document_public_ids": "Linked documents must be a list"}
            )
        if self.review_due_at and self.submitted_at and self.review_due_at < self.submitted_at:
            raise ValidationError({"review_due_at": "Review due date cannot precede submission"})
        if self.reviewed_at and not self.reviewer_membership_public_id:
            raise ValidationError({"reviewer_membership_public_id": "Reviewer is required"})


class DocumentApproval(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(
        Company, on_delete=models.PROTECT, related_name="document_approvals"
    )
    policy = models.ForeignKey(
        DocumentControlPolicyVersion,
        on_delete=models.PROTECT,
        related_name="approvals",
    )
    entity_type_code = models.CharField(max_length=80)
    entity_public_id = models.UUIDField()
    step_code = models.CharField(max_length=100)
    status_code = models.CharField(max_length=80)
    requested_by_membership_public_id = models.UUIDField()
    requested_from_membership_public_id = models.UUIDField()
    requested_at = models.DateTimeField()
    due_at = models.DateTimeField(null=True, blank=True)
    decided_by_membership_public_id = models.UUIDField(null=True, blank=True)
    decided_at = models.DateTimeField(null=True, blank=True)
    decision_note = models.TextField(blank=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "documentops_approval"
        constraints = [
            models.UniqueConstraint(
                fields=["company", "entity_type_code", "entity_public_id", "step_code"],
                name="dops_appr_step_uq",
            ),
            models.CheckConstraint(
                condition=Q(decided_at__isnull=True)
                | Q(decided_by_membership_public_id__isnull=False),
                name="dops_appr_decide_ck",
            ),
        ]
        indexes = [
            models.Index(
                fields=["company", "status_code", "due_at"],
                name="dops_appr_due_ix",
            )
        ]

    def clean(self) -> None:
        super().clean()
        for field in ("entity_type_code", "step_code", "status_code"):
            setattr(self, field, _code(getattr(self, field)))
        if self.policy_id and self.company_id and self.policy.company_id != self.company_id:
            raise ValidationError("Document-control policy cannot cross companies")
        if self.requested_by_membership_public_id == self.requested_from_membership_public_id:
            raise ValidationError("Maker and checker must be different memberships")
        if self.decided_at and not self.decided_by_membership_public_id:
            raise ValidationError({"decided_by_membership_public_id": "Decision actor is required"})


class DocumentDistribution(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(
        Company, on_delete=models.PROTECT, related_name="document_distributions"
    )
    policy = models.ForeignKey(
        DocumentControlPolicyVersion,
        on_delete=models.PROTECT,
        related_name="distributions",
    )
    revision = models.ForeignKey(
        DocumentRevision, on_delete=models.PROTECT, related_name="distributions"
    )
    recipient_type_code = models.CharField(max_length=80)
    recipient_public_id = models.UUIDField()
    purpose_code = models.CharField(max_length=100)
    status_code = models.CharField(max_length=80)
    distributed_at = models.DateTimeField()
    distributed_by_membership_public_id = models.UUIDField()
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    note = models.TextField(blank=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "documentops_distribution"
        constraints = [
            models.UniqueConstraint(
                fields=["company", "revision", "recipient_type_code", "recipient_public_id", "purpose_code"],
                name="dops_dist_rec_uq",
            ),
            models.CheckConstraint(
                condition=Q(acknowledged_at__isnull=True)
                | Q(acknowledged_at__gte=F("distributed_at")),
                name="dops_dist_ack_ck",
            ),
            models.CheckConstraint(
                condition=Q(revoked_at__isnull=True)
                | Q(revoked_at__gte=F("distributed_at")),
                name="dops_dist_revoke_ck",
            ),
        ]
        indexes = [
            models.Index(
                fields=["company", "status_code", "distributed_at"],
                name="dops_dist_status_ix",
            )
        ]

    def clean(self) -> None:
        super().clean()
        for field in ("recipient_type_code", "purpose_code", "status_code"):
            setattr(self, field, _code(getattr(self, field)))
        if self.policy_id and self.company_id and self.policy.company_id != self.company_id:
            raise ValidationError("Document-control policy cannot cross companies")
        if self.revision_id and self.revision.company_id != self.company_id:
            raise ValidationError("Document revision cannot cross companies")
        if self.revision_id and self.revision.policy_id != self.policy_id:
            raise ValidationError("Distribution and revision must use the same policy")
        if self.acknowledged_at and self.acknowledged_at < self.distributed_at:
            raise ValidationError({"acknowledged_at": "Acknowledgement cannot precede distribution"})
        if self.revoked_at and self.revoked_at < self.distributed_at:
            raise ValidationError({"revoked_at": "Revocation cannot precede distribution"})


class DocumentRisk(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(
        Company, on_delete=models.PROTECT, related_name="document_risks"
    )
    policy = models.ForeignKey(
        DocumentControlPolicyVersion,
        on_delete=models.PROTECT,
        related_name="risks",
    )
    linked_entity_type_code = models.CharField(max_length=80)
    linked_entity_public_id = models.UUIDField(null=True, blank=True)
    risk_code = models.CharField(max_length=100)
    severity_code = models.CharField(max_length=80)
    status_code = models.CharField(max_length=80)
    message = models.CharField(max_length=500)
    due_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by_membership_public_id = models.UUIDField(null=True, blank=True)
    resolution_note = models.TextField(blank=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "documentops_risk"
        constraints = [
            models.CheckConstraint(
                condition=Q(resolved_at__isnull=True)
                | Q(resolved_by_membership_public_id__isnull=False),
                name="dops_risk_resolve_ck",
            )
        ]
        indexes = [
            models.Index(
                fields=["company", "status_code", "severity_code"],
                name="dops_risk_status_ix",
            ),
            models.Index(
                fields=["company", "linked_entity_type_code", "linked_entity_public_id"],
                name="dops_risk_entity_ix",
            ),
        ]

    def clean(self) -> None:
        super().clean()
        for field in (
            "linked_entity_type_code",
            "risk_code",
            "severity_code",
            "status_code",
        ):
            setattr(self, field, _code(getattr(self, field)))
        if self.policy_id and self.company_id and self.policy.company_id != self.company_id:
            raise ValidationError("Document-control policy cannot cross companies")
        if self.resolved_at and not self.resolved_by_membership_public_id:
            raise ValidationError({"resolved_by_membership_public_id": "Resolver is required"})
