from __future__ import annotations

import uuid

from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from modules.employee.models import Employee
from modules.platform.models import PublicIdModel, TimestampedModel
from modules.tenant.models import Company
from modules.workops.models import WorkItem


class PersonalNotification(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="mywork_notifications",
    )
    employee = models.ForeignKey(
        Employee,
        on_delete=models.PROTECT,
        related_name="mywork_notifications",
    )
    work_item = models.ForeignKey(
        WorkItem,
        on_delete=models.PROTECT,
        related_name="mywork_notifications",
        null=True,
        blank=True,
    )
    source_key = models.CharField(max_length=200)
    notification_type_code = models.CharField(max_length=100)
    severity_code = models.CharField(max_length=50, default="INFO")
    title = models.CharField(max_length=250)
    message = models.TextField(blank=True)
    action_url = models.CharField(max_length=500, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    dismissed_at = models.DateTimeField(null=True, blank=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "myworkops_notification"
        constraints = [
            models.UniqueConstraint(
                fields=["company", "employee", "source_key"],
                name="mywork_notify_source_uq",
            )
        ]
        indexes = [
            models.Index(
                fields=["company", "employee", "read_at"],
                name="mywork_notify_unread_idx",
            ),
            models.Index(
                fields=["company", "severity_code", "created_at"],
                name="mywork_notify_severity_idx",
            ),
        ]

    def clean(self) -> None:
        super().clean()
        if self.employee_id and self.employee.company_id != self.company_id:
            raise ValidationError("Notification employee cannot cross companies")
        if self.work_item_id and self.work_item.company_id != self.company_id:
            raise ValidationError("Notification work item cannot cross companies")


class OfflineDraft(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="mywork_offline_drafts",
    )
    employee = models.ForeignKey(
        Employee,
        on_delete=models.PROTECT,
        related_name="mywork_offline_drafts",
    )
    work_item = models.ForeignKey(
        WorkItem,
        on_delete=models.PROTECT,
        related_name="mywork_offline_drafts",
        null=True,
        blank=True,
    )
    client_draft_id = models.UUIDField(default=uuid.uuid4)
    device_id = models.UUIDField()
    draft_type_code = models.CharField(max_length=100)
    payload = models.JSONField(default=dict)
    status_code = models.CharField(max_length=50, default="DRAFT")
    client_updated_at = models.DateTimeField()
    synced_at = models.DateTimeField(null=True, blank=True)
    conflict_reason = models.TextField(blank=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "myworkops_offline_draft"
        constraints = [
            models.UniqueConstraint(
                fields=["company", "employee", "client_draft_id"],
                name="mywork_draft_client_uq",
            )
        ]
        indexes = [
            models.Index(
                fields=["company", "employee", "status_code", "client_updated_at"],
                name="mywork_draft_state_idx",
            )
        ]

    def clean(self) -> None:
        super().clean()
        if self.employee_id and self.employee.company_id != self.company_id:
            raise ValidationError("Offline draft employee cannot cross companies")
        if self.work_item_id and self.work_item.company_id != self.company_id:
            raise ValidationError("Offline draft work item cannot cross companies")


class WorkActivity(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="mywork_activity",
    )
    employee = models.ForeignKey(
        Employee,
        on_delete=models.PROTECT,
        related_name="mywork_activity",
    )
    work_item = models.ForeignKey(
        WorkItem,
        on_delete=models.PROTECT,
        related_name="mywork_activity",
        null=True,
        blank=True,
    )
    activity_type_code = models.CharField(max_length=100)
    summary = models.CharField(max_length=500)
    occurred_at = models.DateTimeField(default=timezone.now)
    actor_public_id = models.UUIDField()
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "myworkops_activity"
        indexes = [
            models.Index(
                fields=["company", "employee", "occurred_at"],
                name="mywork_activity_emp_idx",
            ),
            models.Index(
                fields=["company", "work_item", "occurred_at"],
                name="mywork_activity_work_idx",
            ),
        ]

    def clean(self) -> None:
        super().clean()
        if self.employee_id and self.employee.company_id != self.company_id:
            raise ValidationError("Activity employee cannot cross companies")
        if self.work_item_id and self.work_item.company_id != self.company_id:
            raise ValidationError("Activity work item cannot cross companies")
