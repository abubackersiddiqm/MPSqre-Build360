from __future__ import annotations

from collections.abc import Iterable

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.base import ModelBase

from modules.platform.models import PublicIdModel, TimestampedModel
from modules.tenant.models import Company


class WorkflowDefinition(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="workflow_definitions",
    )
    code = models.CharField(max_length=150)
    name = models.CharField(max_length=200)
    description = models.CharField(max_length=500, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "workflow_definition"
        constraints = [
            models.UniqueConstraint(
                fields=["company", "code"],
                name="workflow_company_code_unique",
            )
        ]


class WorkflowVersion(PublicIdModel, TimestampedModel):
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        PUBLISHED = "PUBLISHED", "Published"
        RETIRED = "RETIRED", "Retired"

    definition = models.ForeignKey(
        WorkflowDefinition,
        on_delete=models.PROTECT,
        related_name="versions",
    )
    version = models.PositiveIntegerField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    initial_state_code = models.CharField(max_length=100)
    states = models.JSONField(default=list)
    transitions = models.JSONField(default=list)
    created_by_public_id = models.UUIDField()
    published_at = models.DateTimeField(null=True, blank=True)
    checksum = models.CharField(max_length=64, blank=True)

    class Meta:
        db_table = "workflow_version"
        constraints = [
            models.UniqueConstraint(
                fields=["definition", "version"],
                name="workflow_definition_version_unique",
            ),
            models.CheckConstraint(
                condition=models.Q(status="DRAFT", published_at__isnull=True)
                | models.Q(status__in=["PUBLISHED", "RETIRED"], published_at__isnull=False),
                name="workflow_publish_state_valid",
            ),
        ]
        indexes = [
            models.Index(
                fields=["definition", "status", "version"],
                name="workflow_published_lookup_idx",
            )
        ]

    def save(
        self,
        *,
        force_insert: bool | tuple[ModelBase, ...] = False,
        force_update: bool = False,
        using: str | None = None,
        update_fields: Iterable[str] | None = None,
    ) -> None:
        if self.pk:
            previous = type(self).objects.filter(pk=self.pk).values("status").first()
            if previous and previous["status"] in {
                self.Status.PUBLISHED,
                self.Status.RETIRED,
            }:
                raise ValidationError("Published workflow versions are immutable")
        super().save(
            force_insert=force_insert,
            force_update=force_update,
            using=using,
            update_fields=update_fields,
        )


class WorkflowInstance(PublicIdModel, TimestampedModel):
    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        COMPLETED = "COMPLETED", "Completed"
        CANCELLED = "CANCELLED", "Cancelled"

    company = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="workflow_instances",
    )
    definition = models.ForeignKey(
        WorkflowDefinition,
        on_delete=models.PROTECT,
        related_name="instances",
    )
    workflow_version = models.ForeignKey(
        WorkflowVersion,
        on_delete=models.PROTECT,
        related_name="instances",
    )
    subject_type = models.CharField(max_length=100)
    subject_public_id = models.UUIDField()
    current_state_code = models.CharField(max_length=100)
    lock_version = models.PositiveBigIntegerField(default=1)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    started_by_public_id = models.UUIDField()
    started_at = models.DateTimeField()
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "workflow_instance"
        constraints = [
            models.UniqueConstraint(
                fields=["company", "definition", "subject_type", "subject_public_id"],
                name="workflow_subject_instance_unique",
            )
        ]
        indexes = [
            models.Index(
                fields=["company", "status", "current_state_code"],
                name="workflow_instance_state_idx",
            )
        ]

    def clean(self) -> None:
        super().clean()
        if self.definition_id and self.company_id != self.definition.company_id:
            raise ValidationError("Workflow instance cannot cross companies")
        if self.workflow_version_id and self.workflow_version.definition_id != self.definition_id:
            raise ValidationError("Workflow version does not belong to the selected definition")


class WorkflowTransitionLog(PublicIdModel):
    workflow_instance = models.ForeignKey(
        WorkflowInstance,
        on_delete=models.PROTECT,
        related_name="transition_history",
    )
    sequence = models.PositiveBigIntegerField()
    transition_code = models.CharField(max_length=100)
    from_state_code = models.CharField(max_length=100)
    to_state_code = models.CharField(max_length=100)
    actor_public_id = models.UUIDField()
    occurred_at = models.DateTimeField()
    correlation_id = models.UUIDField()
    comment = models.CharField(max_length=1000, blank=True)

    class Meta:
        db_table = "workflow_transition_log"
        constraints = [
            models.UniqueConstraint(
                fields=["workflow_instance", "sequence"],
                name="workflow_transition_sequence_unique",
            )
        ]

    def save(
        self,
        *,
        force_insert: bool | tuple[ModelBase, ...] = False,
        force_update: bool = False,
        using: str | None = None,
        update_fields: Iterable[str] | None = None,
    ) -> None:
        if self.pk:
            raise ValidationError("Workflow transition history is append-only")
        super().save(
            force_insert=force_insert,
            force_update=force_update,
            using=using,
            update_fields=update_fields,
        )


class ApprovalTask(PublicIdModel, TimestampedModel):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"
        CANCELLED = "CANCELLED", "Cancelled"

    company = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="approval_tasks",
    )
    workflow_instance = models.ForeignKey(
        WorkflowInstance,
        on_delete=models.PROTECT,
        related_name="approval_tasks",
    )
    transition_code = models.CharField(max_length=100)
    from_state_code = models.CharField(max_length=100)
    to_state_code = models.CharField(max_length=100)
    approval_permission_code = models.CharField(max_length=150, default="workflow.approve")
    assigned_role_public_id = models.UUIDField(null=True, blank=True)
    assigned_user_public_id = models.UUIDField(null=True, blank=True)
    requested_by_public_id = models.UUIDField()
    due_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    decided_by_public_id = models.UUIDField(null=True, blank=True)
    decided_at = models.DateTimeField(null=True, blank=True)
    comment = models.CharField(max_length=1000, blank=True)

    class Meta:
        db_table = "workflow_approval_task"
        constraints = [
            models.UniqueConstraint(
                fields=["workflow_instance", "transition_code"],
                condition=models.Q(status="PENDING"),
                name="workflow_pending_transition_unique",
            )
        ]
        indexes = [
            models.Index(
                fields=["company", "status", "due_at"],
                name="workflow_approval_inbox_idx",
            )
        ]

    def clean(self) -> None:
        super().clean()
        if self.workflow_instance_id and self.company_id != self.workflow_instance.company_id:
            raise ValidationError("Approval task cannot cross companies")
