from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from modules.platform.models import TenantOwnedModel


class AIProviderProfile(TenantOwnedModel):
    code = models.CharField(max_length=80)
    display_name = models.CharField(max_length=160)
    adapter_code = models.CharField(max_length=100)
    secret_reference = models.CharField(max_length=240, blank=True)
    data_residency = models.CharField(max_length=80, blank=True)
    configuration = models.JSONField(default=dict)
    supports_citations = models.BooleanField(default=True)
    supports_extraction = models.BooleanField(default=False)
    supports_tools = models.BooleanField(default=False)
    is_active = models.BooleanField(default=False)
    version = models.PositiveBigIntegerField(default=1)

    class Meta:
        db_table = "ai_provider_profile"
        ordering = ["display_name"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "code"],
                name="ai_provider_code_uq",
            )
        ]
        indexes = [
            models.Index(
                fields=["company", "is_active", "adapter_code"],
                name="ai_provider_active_idx",
            )
        ]

    def clean(self) -> None:
        super().clean()
        if self.is_active and self.adapter_code != "local_grounded" and not self.secret_reference:
            raise ValidationError("An active external AI provider requires a secret reference")


class AIModelPolicy(TenantOwnedModel):
    class Purpose(models.TextChoices):
        ASSISTANT = "assistant", "Grounded assistant"
        EXTRACTION = "extraction", "Document extraction"
        RISK = "risk", "Risk signal detection"
        EVALUATION = "evaluation", "Model evaluation"

    code = models.CharField(max_length=100)
    name = models.CharField(max_length=180)
    provider = models.ForeignKey(
        AIProviderProfile,
        on_delete=models.PROTECT,
        related_name="policies",
    )
    model_name = models.CharField(max_length=160)
    purpose = models.CharField(max_length=20, choices=Purpose.choices)
    system_instruction = models.TextField(blank=True)
    allowed_source_types = models.JSONField(default=list)
    allowed_data_classifications = models.JSONField(default=list)
    allowed_tool_codes = models.JSONField(default=list, blank=True)
    max_context_records = models.PositiveSmallIntegerField(default=20)
    max_output_characters = models.PositiveIntegerField(default=6000)
    human_review_required = models.BooleanField(default=True)
    citations_required = models.BooleanField(default=True)
    retention_days = models.PositiveIntegerField(default=30)
    effective_from = models.DateTimeField()
    effective_to = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "ai_model_policy"
        ordering = ["purpose", "name", "-version"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "code", "version"],
                name="ai_policy_version_uq",
            ),
            models.UniqueConstraint(
                fields=["company", "code"],
                condition=Q(is_active=True),
                name="ai_policy_active_uq",
            ),
        ]
        indexes = [
            models.Index(
                fields=["company", "purpose", "is_active"],
                name="ai_policy_purpose_idx",
            )
        ]

    def clean(self) -> None:
        super().clean()
        if self.provider_id and self.provider.company_id != self.company_id:
            raise ValidationError("An AI policy cannot use another company's provider")
        if not 1 <= self.max_context_records <= 100:
            raise ValidationError("AI context records must be between 1 and 100")
        if not 500 <= self.max_output_characters <= 20000:
            raise ValidationError("AI output length must be between 500 and 20000 characters")
        if not isinstance(self.allowed_source_types, list):
            raise ValidationError("Allowed source types must be a list")
        if self.effective_to and self.effective_to <= self.effective_from:
            raise ValidationError("Policy effective-to must be after effective-from")


class AIInteraction(TenantOwnedModel):
    class Status(models.TextChoices):
        QUEUED = "queued", "Queued"
        RUNNING = "running", "Running"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"
        BLOCKED = "blocked", "Blocked"

    class ReviewStatus(models.TextChoices):
        NOT_REQUIRED = "not_required", "Not required"
        PENDING = "pending", "Pending review"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        CORRECTED = "corrected", "Corrected"

    policy = models.ForeignKey(
        AIModelPolicy,
        on_delete=models.PROTECT,
        related_name="interactions",
    )
    requested_by_public_id = models.UUIDField()
    membership_public_id = models.UUIDField()
    idempotency_key = models.CharField(max_length=120)
    purpose = models.CharField(max_length=20, choices=AIModelPolicy.Purpose.choices)
    prompt_digest = models.CharField(max_length=64)
    prompt_excerpt = models.CharField(max_length=500, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.QUEUED)
    response_text = models.TextField(blank=True)
    confidence = models.DecimalField(max_digits=5, decimal_places=4, null=True, blank=True)
    citations_required = models.BooleanField(default=True)
    review_status = models.CharField(
        max_length=20,
        choices=ReviewStatus.choices,
        default=ReviewStatus.PENDING,
    )
    reviewed_by_public_id = models.UUIDField(null=True, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_reason = models.CharField(max_length=500, blank=True)
    input_metadata = models.JSONField(default=dict)
    output_metadata = models.JSONField(default=dict, blank=True)
    provider_request_id = models.CharField(max_length=200, blank=True)
    provider_code_snapshot = models.CharField(max_length=80)
    model_name_snapshot = models.CharField(max_length=160)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    error_message = models.CharField(max_length=1000, blank=True)
    version = models.PositiveBigIntegerField(default=1)

    class Meta:
        db_table = "ai_interaction"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "idempotency_key"],
                name="ai_interaction_idem_uq",
            )
        ]
        indexes = [
            models.Index(
                fields=["company", "status", "created_at"],
                name="ai_interaction_status_idx",
            ),
            models.Index(
                fields=["company", "requested_by_public_id", "created_at"],
                name="ai_interaction_user_idx",
            ),
        ]

    def clean(self) -> None:
        super().clean()
        if self.policy_id and self.policy.company_id != self.company_id:
            raise ValidationError("An AI interaction cannot cross companies")
        if self.response_text and len(self.response_text) > self.policy.max_output_characters:
            raise ValidationError("AI response exceeds the active policy limit")


class AICitation(TenantOwnedModel):
    interaction = models.ForeignKey(
        AIInteraction,
        on_delete=models.PROTECT,
        related_name="citations",
    )
    rank = models.PositiveSmallIntegerField()
    source_type = models.CharField(max_length=100)
    source_public_id = models.UUIDField()
    source_label = models.CharField(max_length=240)
    source_version = models.CharField(max_length=80, blank=True)
    excerpt = models.CharField(max_length=600, blank=True)
    authorization_basis = models.CharField(max_length=160)
    data_classification = models.CharField(max_length=30, default="internal")

    class Meta:
        db_table = "ai_citation"
        ordering = ["rank"]
        constraints = [
            models.UniqueConstraint(
                fields=["interaction", "rank"],
                name="ai_citation_rank_uq",
            )
        ]
        indexes = [
            models.Index(
                fields=["company", "source_type", "source_public_id"],
                name="ai_citation_source_idx",
            )
        ]

    def clean(self) -> None:
        super().clean()
        if self.interaction_id and self.interaction.company_id != self.company_id:
            raise ValidationError("An AI citation cannot cross companies")


class AIEntityInsight(TenantOwnedModel):
    """Latest governed AI cache for any business entity.

    AIInteraction remains the immutable generation history. This row only points
    to the latest interaction and keeps optional human override data.
    """

    interaction = models.ForeignKey(
        AIInteraction,
        on_delete=models.PROTECT,
        related_name="entity_insights",
    )
    subject_type = models.CharField(max_length=100)
    subject_public_id = models.UUIDField()
    insight_code = models.CharField(max_length=100)
    source_digest = models.CharField(max_length=64)
    output_payload = models.JSONField(default=dict)
    override_payload = models.JSONField(default=dict, blank=True)
    generated_at = models.DateTimeField()
    overridden_by_public_id = models.UUIDField(null=True, blank=True)
    overridden_at = models.DateTimeField(null=True, blank=True)
    version = models.PositiveBigIntegerField(default=1)

    class Meta:
        db_table = "ai_entity_insight"
        constraints = [
            models.UniqueConstraint(
                fields=["company", "subject_type", "subject_public_id", "insight_code"],
                name="ai_insight_subject_uq",
            )
        ]
        indexes = [
            models.Index(
                fields=["company", "subject_type", "subject_public_id"],
                name="ai_insight_subject_idx",
            ),
            models.Index(
                fields=["company", "insight_code", "generated_at"],
                name="ai_insight_code_idx",
            ),
        ]

    def clean(self) -> None:
        super().clean()
        if self.interaction_id and self.interaction.company_id != self.company_id:
            raise ValidationError("An AI entity insight cannot cross companies")


class AIExtractionJob(TenantOwnedModel):
    class Status(models.TextChoices):
        QUEUED = "queued", "Queued"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"
        REVIEWED = "reviewed", "Reviewed"
        REJECTED = "rejected", "Rejected"

    policy = models.ForeignKey(
        AIModelPolicy,
        on_delete=models.PROTECT,
        related_name="extraction_jobs",
    )
    requested_by_public_id = models.UUIDField()
    idempotency_key = models.CharField(max_length=120)
    source_type = models.CharField(max_length=100)
    source_public_id = models.UUIDField(null=True, blank=True)
    source_digest = models.CharField(max_length=64)
    schema_code = models.CharField(max_length=100)
    requested_fields = models.JSONField(default=list)
    extracted_payload = models.JSONField(default=dict)
    confidence_by_field = models.JSONField(default=dict)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.QUEUED)
    reviewed_by_public_id = models.UUIDField(null=True, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    corrections = models.JSONField(default=dict, blank=True)
    review_reason = models.CharField(max_length=500, blank=True)
    error_message = models.CharField(max_length=1000, blank=True)
    version = models.PositiveBigIntegerField(default=1)

    class Meta:
        db_table = "ai_extraction_job"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "idempotency_key"],
                name="ai_extract_idem_uq",
            )
        ]
        indexes = [
            models.Index(
                fields=["company", "status", "created_at"],
                name="ai_extract_status_idx",
            )
        ]

    def clean(self) -> None:
        super().clean()
        if self.policy_id and self.policy.company_id != self.company_id:
            raise ValidationError("An extraction job cannot cross companies")
        if not isinstance(self.requested_fields, list) or not self.requested_fields:
            raise ValidationError("At least one extraction field is required")
        if len(self.requested_fields) > 100:
            raise ValidationError("An extraction job supports at most 100 fields")


class AIRiskSignal(TenantOwnedModel):
    class Severity(models.TextChoices):
        LOW = "low", "Low"
        MEDIUM = "medium", "Medium"
        HIGH = "high", "High"
        CRITICAL = "critical", "Critical"

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        ACKNOWLEDGED = "acknowledged", "Acknowledged"
        RESOLVED = "resolved", "Resolved"
        DISMISSED = "dismissed", "Dismissed"

    signal_code = models.CharField(max_length=120)
    severity = models.CharField(max_length=20, choices=Severity.choices)
    title = models.CharField(max_length=240)
    description = models.TextField()
    source_type = models.CharField(max_length=100)
    source_public_id = models.UUIDField(null=True, blank=True)
    evidence = models.JSONField(default=dict)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
    detected_by_interaction = models.ForeignKey(
        AIInteraction,
        on_delete=models.PROTECT,
        related_name="risk_signals",
        null=True,
        blank=True,
    )
    assigned_to_public_id = models.UUIDField(null=True, blank=True)
    resolved_by_public_id = models.UUIDField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    disposition_reason = models.CharField(max_length=500, blank=True)
    fingerprint = models.CharField(max_length=64)
    version = models.PositiveBigIntegerField(default=1)

    class Meta:
        db_table = "ai_risk_signal"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "fingerprint"],
                condition=Q(status__in=["open", "acknowledged"]),
                name="ai_risk_open_fingerprint_uq",
            )
        ]
        indexes = [
            models.Index(
                fields=["company", "status", "severity"],
                name="ai_risk_status_idx",
            )
        ]

    def clean(self) -> None:
        super().clean()
        if (
            self.detected_by_interaction_id
            and self.detected_by_interaction.company_id != self.company_id
        ):
            raise ValidationError("A risk signal cannot cross companies")


class AIToolAction(TenantOwnedModel):
    class Status(models.TextChoices):
        PROPOSED = "proposed", "Proposed"
        CONFIRMED = "confirmed", "Confirmed"
        REJECTED = "rejected", "Rejected"
        EXPIRED = "expired", "Expired"

    interaction = models.ForeignKey(
        AIInteraction,
        on_delete=models.PROTECT,
        related_name="tool_actions",
    )
    action_code = models.CharField(max_length=120)
    target_type = models.CharField(max_length=100)
    target_public_id = models.UUIDField(null=True, blank=True)
    proposed_payload = models.JSONField(default=dict)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PROPOSED)
    proposed_by_public_id = models.UUIDField()
    decided_by_public_id = models.UUIDField(null=True, blank=True)
    decided_at = models.DateTimeField(null=True, blank=True)
    decision_reason = models.CharField(max_length=500, blank=True)
    expires_at = models.DateTimeField()
    idempotency_key = models.CharField(max_length=120)
    version = models.PositiveBigIntegerField(default=1)

    class Meta:
        db_table = "ai_tool_action"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "idempotency_key"],
                name="ai_action_idem_uq",
            )
        ]
        indexes = [
            models.Index(
                fields=["company", "status", "expires_at"],
                name="ai_action_status_idx",
            )
        ]

    def clean(self) -> None:
        super().clean()
        if self.interaction_id and self.interaction.company_id != self.company_id:
            raise ValidationError("An AI tool proposal cannot cross companies")
        if not self.interaction.policy.human_review_required:
            raise ValidationError("Tool actions require a human-review policy")


class AIEvaluationRun(TenantOwnedModel):
    class Status(models.TextChoices):
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"

    policy = models.ForeignKey(
        AIModelPolicy,
        on_delete=models.PROTECT,
        related_name="evaluation_runs",
    )
    requested_by_public_id = models.UUIDField()
    suite_code = models.CharField(max_length=100)
    status = models.CharField(max_length=20, choices=Status.choices)
    scenario_count = models.PositiveIntegerField(default=0)
    passed_count = models.PositiveIntegerField(default=0)
    scores = models.JSONField(default=dict)
    failures = models.JSONField(default=list, blank=True)
    provider_code_snapshot = models.CharField(max_length=80)
    model_name_snapshot = models.CharField(max_length=160)
    completed_at = models.DateTimeField()

    class Meta:
        db_table = "ai_evaluation_run"
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["company", "suite_code", "created_at"],
                name="ai_eval_suite_idx",
            )
        ]

    def clean(self) -> None:
        super().clean()
        if self.policy_id and self.policy.company_id != self.company_id:
            raise ValidationError("An AI evaluation cannot cross companies")
        if self.passed_count > self.scenario_count:
            raise ValidationError("Passed scenarios cannot exceed scenario count")
