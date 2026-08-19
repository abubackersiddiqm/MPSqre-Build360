from __future__ import annotations

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models

from modules.platform.models import PublicIdModel, TimestampedModel
from modules.tenant.models import Company


def normalize_code(value: str) -> str:
    return value.strip().upper().replace(" ", "_").replace("-", "_")


class SupportPolicyVersion(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="support_policies")
    version = models.PositiveIntegerField(default=1)
    status_code = models.CharField(max_length=30, default="DRAFT")
    default_response_minutes = models.PositiveIntegerField(default=240)
    default_resolution_minutes = models.PositiveIntegerField(default=2880)
    escalation_warning_percent = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("80.00"))
    customer_feedback_required = models.BooleanField(default=True)
    configuration = models.JSONField(default=dict, blank=True)
    effective_from = models.DateTimeField(null=True, blank=True)
    effective_to = models.DateTimeField(null=True, blank=True)
    published_by_public_id = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = "supportops_policy_version"
        constraints = [
            models.UniqueConstraint(fields=["company", "version"], name="sup_policy_version_uq"),
            models.CheckConstraint(
                condition=models.Q(effective_to__isnull=True)
                | models.Q(effective_from__isnull=True)
                | models.Q(effective_to__gt=models.F("effective_from")),
                name="sup_policy_dates_ck",
            ),
            models.CheckConstraint(
                condition=models.Q(escalation_warning_percent__gte=0)
                & models.Q(escalation_warning_percent__lte=100),
                name="sup_policy_warning_ck",
            ),
        ]
        indexes = [models.Index(fields=["company", "status_code"], name="sup_policy_status_idx")]


class ServiceCatalogItem(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="support_catalog_items")
    code = models.CharField(max_length=80)
    name = models.CharField(max_length=220)
    category_code = models.CharField(max_length=80, default="GENERAL")
    description = models.TextField(blank=True)
    response_minutes = models.PositiveIntegerField(default=240)
    resolution_minutes = models.PositiveIntegerField(default=2880)
    business_hours_only = models.BooleanField(default=True)
    active = models.BooleanField(default=True)
    configuration = models.JSONField(default=dict, blank=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "supportops_catalog_item"
        constraints = [models.UniqueConstraint(fields=["company", "code"], name="sup_catalog_code_uq")]
        indexes = [
            models.Index(fields=["company", "active", "category_code"], name="sup_catalog_active_idx"),
        ]

    def clean(self) -> None:
        super().clean()
        self.code = normalize_code(self.code)
        self.category_code = normalize_code(self.category_code)


class SupportTicket(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="support_tickets")
    catalog_item = models.ForeignKey(
        ServiceCatalogItem,
        on_delete=models.PROTECT,
        related_name="tickets",
        null=True,
        blank=True,
    )
    code = models.CharField(max_length=80)
    title = models.CharField(max_length=240)
    description = models.TextField(blank=True)
    category_code = models.CharField(max_length=80, default="GENERAL")
    priority_code = models.CharField(max_length=10, default="P3")
    channel_code = models.CharField(max_length=30, default="PORTAL")
    status_code = models.CharField(max_length=30, default="NEW")
    requester_name = models.CharField(max_length=180)
    requester_email = models.EmailField(blank=True)
    requester_public_id = models.UUIDField(null=True, blank=True)
    assigned_to_public_id = models.UUIDField(null=True, blank=True)
    created_by_public_id = models.UUIDField()
    response_due_at = models.DateTimeField(null=True, blank=True)
    resolution_due_at = models.DateTimeField(null=True, blank=True)
    first_responded_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    resolution_summary = models.TextField(blank=True)
    sla_breached = models.BooleanField(default=False)
    escalation_level = models.PositiveIntegerField(default=0)
    tags = models.JSONField(default=list, blank=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "supportops_ticket"
        constraints = [models.UniqueConstraint(fields=["company", "code"], name="sup_ticket_code_uq")]
        indexes = [
            models.Index(fields=["company", "status_code", "priority_code"], name="sup_ticket_status_idx"),
            models.Index(fields=["company", "resolution_due_at"], name="sup_ticket_due_idx"),
            models.Index(fields=["company", "assigned_to_public_id"], name="sup_ticket_owner_idx"),
        ]

    def clean(self) -> None:
        super().clean()
        self.code = normalize_code(self.code)
        self.category_code = normalize_code(self.category_code)
        self.priority_code = self.priority_code.strip().upper()
        self.channel_code = normalize_code(self.channel_code)
        if self.priority_code not in {"P0", "P1", "P2", "P3", "P4"}:
            raise ValidationError({"priority_code": "Priority must be P0, P1, P2, P3 or P4."})
        if self.catalog_item_id and self.catalog_item.company_id != self.company_id:
            raise ValidationError("Support ticket catalog item cannot cross companies.")
        if self.resolution_due_at and self.response_due_at and self.resolution_due_at < self.response_due_at:
            raise ValidationError("Resolution due time cannot be earlier than response due time.")


class TicketInteraction(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="support_interactions")
    ticket = models.ForeignKey(SupportTicket, on_delete=models.PROTECT, related_name="interactions")
    interaction_type_code = models.CharField(max_length=30, default="COMMENT")
    visibility_code = models.CharField(max_length=30, default="INTERNAL")
    body = models.TextField()
    actor_public_id = models.UUIDField()
    customer_visible = models.BooleanField(default=False)
    occurred_at = models.DateTimeField()
    attachments = models.JSONField(default=list, blank=True)

    class Meta:
        db_table = "supportops_interaction"
        indexes = [
            models.Index(fields=["ticket", "occurred_at"], name="sup_interaction_time_idx"),
            models.Index(fields=["company", "customer_visible"], name="sup_interaction_vis_idx"),
        ]

    def clean(self) -> None:
        super().clean()
        if self.ticket_id and self.ticket.company_id != self.company_id:
            raise ValidationError("Ticket interaction cannot cross companies.")
        self.interaction_type_code = normalize_code(self.interaction_type_code)
        self.visibility_code = normalize_code(self.visibility_code)


class ProblemRecord(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="support_problems")
    source_ticket = models.ForeignKey(
        SupportTicket, on_delete=models.PROTECT, related_name="problems", null=True, blank=True
    )
    code = models.CharField(max_length=80)
    title = models.CharField(max_length=240)
    impact_summary = models.TextField(blank=True)
    root_cause = models.TextField(blank=True)
    workaround = models.TextField(blank=True)
    permanent_fix = models.TextField(blank=True)
    priority_code = models.CharField(max_length=10, default="P2")
    status_code = models.CharField(max_length=30, default="OPEN")
    owner_public_id = models.UUIDField(null=True, blank=True)
    created_by_public_id = models.UUIDField()
    resolved_at = models.DateTimeField(null=True, blank=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "supportops_problem"
        constraints = [models.UniqueConstraint(fields=["company", "code"], name="sup_problem_code_uq")]
        indexes = [models.Index(fields=["company", "status_code", "priority_code"], name="sup_problem_status_idx")]

    def clean(self) -> None:
        super().clean()
        self.code = normalize_code(self.code)
        self.priority_code = self.priority_code.strip().upper()
        if self.source_ticket_id and self.source_ticket.company_id != self.company_id:
            raise ValidationError("Problem source ticket cannot cross companies.")


class ChangeRequest(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="support_changes")
    source_ticket = models.ForeignKey(
        SupportTicket, on_delete=models.PROTECT, related_name="change_requests", null=True, blank=True
    )
    problem = models.ForeignKey(
        ProblemRecord, on_delete=models.PROTECT, related_name="change_requests", null=True, blank=True
    )
    code = models.CharField(max_length=80)
    title = models.CharField(max_length=240)
    description = models.TextField(blank=True)
    change_type_code = models.CharField(max_length=40, default="NORMAL")
    risk_code = models.CharField(max_length=20, default="MEDIUM")
    status_code = models.CharField(max_length=30, default="DRAFT")
    planned_start_at = models.DateTimeField(null=True, blank=True)
    planned_end_at = models.DateTimeField(null=True, blank=True)
    rollback_plan = models.TextField(blank=True)
    test_evidence = models.JSONField(default=dict, blank=True)
    created_by_public_id = models.UUIDField()
    approved_by_public_id = models.UUIDField(null=True, blank=True)
    implemented_at = models.DateTimeField(null=True, blank=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "supportops_change_request"
        constraints = [
            models.UniqueConstraint(fields=["company", "code"], name="sup_change_code_uq"),
            models.CheckConstraint(
                condition=models.Q(planned_end_at__isnull=True)
                | models.Q(planned_start_at__isnull=True)
                | models.Q(planned_end_at__gt=models.F("planned_start_at")),
                name="sup_change_dates_ck",
            ),
        ]
        indexes = [models.Index(fields=["company", "status_code", "risk_code"], name="sup_change_status_idx")]

    def clean(self) -> None:
        super().clean()
        self.code = normalize_code(self.code)
        self.change_type_code = normalize_code(self.change_type_code)
        self.risk_code = normalize_code(self.risk_code)
        if self.source_ticket_id and self.source_ticket.company_id != self.company_id:
            raise ValidationError("Change request source ticket cannot cross companies.")
        if self.problem_id and self.problem.company_id != self.company_id:
            raise ValidationError("Change request problem cannot cross companies.")


class KnowledgeArticle(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="support_knowledge_articles")
    code = models.CharField(max_length=80)
    title = models.CharField(max_length=240)
    summary = models.TextField(blank=True)
    content = models.TextField()
    category_code = models.CharField(max_length=80, default="GENERAL")
    audience_code = models.CharField(max_length=40, default="INTERNAL")
    status_code = models.CharField(max_length=30, default="DRAFT")
    keywords = models.JSONField(default=list, blank=True)
    created_by_public_id = models.UUIDField()
    published_by_public_id = models.UUIDField(null=True, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "supportops_knowledge_article"
        constraints = [models.UniqueConstraint(fields=["company", "code"], name="sup_article_code_uq")]
        indexes = [models.Index(fields=["company", "status_code", "category_code"], name="sup_article_status_idx")]

    def clean(self) -> None:
        super().clean()
        self.code = normalize_code(self.code)
        self.category_code = normalize_code(self.category_code)
        self.audience_code = normalize_code(self.audience_code)


class CustomerFeedback(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="support_feedback")
    ticket = models.OneToOneField(SupportTicket, on_delete=models.PROTECT, related_name="feedback")
    rating = models.PositiveSmallIntegerField()
    comments = models.TextField(blank=True)
    submitted_by_name = models.CharField(max_length=180, blank=True)
    submitted_by_email = models.EmailField(blank=True)
    submitted_at = models.DateTimeField()
    follow_up_required = models.BooleanField(default=False)
    follow_up_notes = models.TextField(blank=True)

    class Meta:
        db_table = "supportops_feedback"
        indexes = [models.Index(fields=["company", "rating", "submitted_at"], name="sup_feedback_rating_idx")]

    def clean(self) -> None:
        super().clean()
        if self.ticket_id and self.ticket.company_id != self.company_id:
            raise ValidationError("Customer feedback ticket cannot cross companies.")
        if self.rating < 1 or self.rating > 5:
            raise ValidationError({"rating": "Rating must be between 1 and 5."})


class ImprovementItem(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="support_improvements")
    source_ticket = models.ForeignKey(
        SupportTicket, on_delete=models.PROTECT, related_name="improvements", null=True, blank=True
    )
    source_problem = models.ForeignKey(
        ProblemRecord, on_delete=models.PROTECT, related_name="improvements", null=True, blank=True
    )
    source_feedback = models.ForeignKey(
        CustomerFeedback, on_delete=models.PROTECT, related_name="improvements", null=True, blank=True
    )
    code = models.CharField(max_length=80)
    title = models.CharField(max_length=240)
    description = models.TextField(blank=True)
    theme_code = models.CharField(max_length=80, default="SERVICE_QUALITY")
    priority_code = models.CharField(max_length=10, default="P3")
    status_code = models.CharField(max_length=30, default="BACKLOG")
    expected_benefit = models.TextField(blank=True)
    measured_benefit = models.TextField(blank=True)
    owner_public_id = models.UUIDField(null=True, blank=True)
    due_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_by_public_id = models.UUIDField()
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "supportops_improvement_item"
        constraints = [models.UniqueConstraint(fields=["company", "code"], name="sup_improvement_code_uq")]
        indexes = [
            models.Index(fields=["company", "status_code", "priority_code"], name="sup_improvement_status_idx"),
            models.Index(fields=["company", "due_at"], name="sup_improvement_due_idx"),
        ]

    def clean(self) -> None:
        super().clean()
        self.code = normalize_code(self.code)
        self.theme_code = normalize_code(self.theme_code)
        self.priority_code = self.priority_code.strip().upper()
        for source in (self.source_ticket, self.source_problem, self.source_feedback):
            if source is not None and source.company_id != self.company_id:
                raise ValidationError("Improvement source cannot cross companies.")
