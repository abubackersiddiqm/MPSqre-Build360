from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import models

from modules.platform.models import PublicIdModel, TimestampedModel
from modules.tenant.models import Company, Membership
from modules.workops.models import Project, ProjectSite


class CollaborationPolicyVersion(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="collaboration_policies")
    version = models.PositiveIntegerField(default=1)
    status_code = models.CharField(max_length=30, default="DRAFT")
    invitation_ttl_hours = models.PositiveSmallIntegerField(default=72)
    require_project_grant = models.BooleanField(default=True)
    require_submission_review = models.BooleanField(default=True)
    allow_external_decisions = models.BooleanField(default=False)
    configuration = models.JSONField(default=dict, blank=True)
    effective_from = models.DateTimeField(null=True, blank=True)
    effective_to = models.DateTimeField(null=True, blank=True)
    published_by_public_id = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = "collabops_policy_version"
        constraints = [
            models.UniqueConstraint(fields=["company", "version"], name="co_policy_version_uq"),
            models.CheckConstraint(
                condition=models.Q(effective_to__isnull=True)
                | models.Q(effective_from__isnull=True)
                | models.Q(effective_to__gt=models.F("effective_from")),
                name="co_policy_dates_ck",
            ),
        ]
        indexes = [models.Index(fields=["company", "status_code"], name="co_policy_status_idx")]


class PartnerOrganization(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="partner_organizations")
    code = models.CharField(max_length=60)
    legal_name = models.CharField(max_length=250)
    display_name = models.CharField(max_length=250)
    organization_type_code = models.CharField(max_length=40, default="VENDOR")
    registration_number = models.CharField(max_length=120, blank=True)
    tax_registration_number = models.CharField(max_length=120, blank=True)
    country_code = models.CharField(max_length=2, blank=True)
    primary_email = models.EmailField(blank=True)
    primary_phone = models.CharField(max_length=40, blank=True)
    status_code = models.CharField(max_length=30, default="ACTIVE")
    risk_rating_code = models.CharField(max_length=30, default="UNASSESSED")
    metadata = models.JSONField(default=dict, blank=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "collabops_partner_org"
        constraints = [models.UniqueConstraint(fields=["company", "code"], name="co_partner_code_uq")]
        indexes = [
            models.Index(fields=["company", "organization_type_code", "status_code"], name="co_partner_status_idx")
        ]


class PartnerContact(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="partner_contacts")
    organization = models.ForeignKey(PartnerOrganization, on_delete=models.PROTECT, related_name="contacts")
    membership = models.OneToOneField(
        Membership,
        on_delete=models.PROTECT,
        related_name="external_collaboration_contact",
        null=True,
        blank=True,
    )
    full_name = models.CharField(max_length=200)
    email = models.EmailField(max_length=254)
    mobile = models.CharField(max_length=40, blank=True)
    job_title = models.CharField(max_length=150, blank=True)
    is_primary = models.BooleanField(default=False)
    can_approve = models.BooleanField(default=False)
    status_code = models.CharField(max_length=30, default="INVITED")
    invitation_public_id = models.UUIDField(null=True, blank=True)
    invited_at = models.DateTimeField(null=True, blank=True)
    activated_at = models.DateTimeField(null=True, blank=True)
    suspended_at = models.DateTimeField(null=True, blank=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "collabops_partner_contact"
        constraints = [models.UniqueConstraint(fields=["company", "email"], name="co_contact_email_uq")]
        indexes = [models.Index(fields=["company", "status_code"], name="co_contact_status_idx")]

    def clean(self) -> None:
        super().clean()
        if self.organization_id and self.organization.company_id != self.company_id:
            raise ValidationError("Partner contact cannot cross companies")
        if self.membership_id and self.membership.company_id != self.company_id:
            raise ValidationError("Partner membership cannot cross companies")


class ProjectAccessGrant(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="partner_project_grants")
    contact = models.ForeignKey(PartnerContact, on_delete=models.PROTECT, related_name="project_grants")
    project = models.ForeignKey(Project, on_delete=models.PROTECT, related_name="external_access_grants")
    site = models.ForeignKey(
        ProjectSite,
        on_delete=models.PROTECT,
        related_name="external_access_grants",
        null=True,
        blank=True,
    )
    scopes = models.JSONField(default=list)
    effective_from = models.DateTimeField()
    effective_to = models.DateTimeField(null=True, blank=True)
    status_code = models.CharField(max_length=30, default="ACTIVE")
    granted_by_public_id = models.UUIDField()
    revoked_at = models.DateTimeField(null=True, blank=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "collabops_project_grant"
        constraints = [
            models.UniqueConstraint(fields=["contact", "project", "site"], name="co_grant_scope_uq"),
            models.CheckConstraint(
                condition=models.Q(effective_to__isnull=True)
                | models.Q(effective_to__gt=models.F("effective_from")),
                name="co_grant_dates_ck",
            ),
        ]
        indexes = [models.Index(fields=["company", "project", "status_code"], name="co_grant_project_idx")]

    def clean(self) -> None:
        super().clean()
        if self.contact_id and self.contact.company_id != self.company_id:
            raise ValidationError("Project grant contact cannot cross companies")
        if self.project_id and self.project.company_id != self.company_id:
            raise ValidationError("Project grant cannot cross companies")
        if self.site_id and (self.site.company_id != self.company_id or self.site.project_id != self.project_id):
            raise ValidationError("Project grant site must belong to the selected project")


class CollaborationItem(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="collaboration_items")
    organization = models.ForeignKey(PartnerOrganization, on_delete=models.PROTECT, related_name="collaboration_items")
    assigned_contact = models.ForeignKey(
        PartnerContact,
        on_delete=models.PROTECT,
        related_name="assigned_items",
        null=True,
        blank=True,
    )
    project = models.ForeignKey(Project, on_delete=models.PROTECT, related_name="collaboration_items")
    site = models.ForeignKey(
        ProjectSite,
        on_delete=models.PROTECT,
        related_name="collaboration_items",
        null=True,
        blank=True,
    )
    reference = models.CharField(max_length=100)
    item_type_code = models.CharField(max_length=50, default="GENERAL")
    title = models.CharField(max_length=250)
    description = models.TextField(blank=True)
    status_code = models.CharField(max_length=40, default="DRAFT")
    priority_code = models.CharField(max_length=30, default="NORMAL")
    due_at = models.DateTimeField(null=True, blank=True)
    response_required = models.BooleanField(default=True)
    approval_required = models.BooleanField(default=False)
    amount = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    currency = models.CharField(max_length=3, blank=True)
    source_module = models.CharField(max_length=50, blank=True)
    source_public_id = models.UUIDField(null=True, blank=True)
    created_by_public_id = models.UUIDField()
    closed_at = models.DateTimeField(null=True, blank=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "collabops_item"
        constraints = [
            models.UniqueConstraint(fields=["company", "reference"], name="co_item_reference_uq"),
            models.CheckConstraint(condition=models.Q(amount__isnull=True) | models.Q(amount__gte=0), name="co_item_amount_ck"),
        ]
        indexes = [
            models.Index(fields=["company", "status_code", "due_at"], name="co_item_due_idx"),
            models.Index(fields=["company", "organization", "project"], name="co_item_partner_idx"),
        ]

    def clean(self) -> None:
        super().clean()
        if self.organization_id and self.organization.company_id != self.company_id:
            raise ValidationError("Collaboration item partner cannot cross companies")
        if self.assigned_contact_id:
            if self.assigned_contact.company_id != self.company_id:
                raise ValidationError("Assigned contact cannot cross companies")
            if self.assigned_contact.organization_id != self.organization_id:
                raise ValidationError("Assigned contact must belong to the selected partner")
        if self.project_id and self.project.company_id != self.company_id:
            raise ValidationError("Collaboration item project cannot cross companies")
        if self.site_id and (self.site.company_id != self.company_id or self.site.project_id != self.project_id):
            raise ValidationError("Collaboration item site must belong to the selected project")
        if self.amount is not None and not self.currency:
            raise ValidationError("Currency is required when an amount is supplied")


class CollaborationSubmission(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="collaboration_submissions")
    item = models.ForeignKey(CollaborationItem, on_delete=models.PROTECT, related_name="submissions")
    contact = models.ForeignKey(PartnerContact, on_delete=models.PROTECT, related_name="submissions")
    revision = models.PositiveIntegerField(default=1)
    status_code = models.CharField(max_length=30, default="SUBMITTED")
    summary = models.TextField(blank=True)
    data = models.JSONField(default=dict, blank=True)
    attachment_references = models.JSONField(default=list, blank=True)
    submitted_at = models.DateTimeField()
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by_public_id = models.UUIDField(null=True, blank=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "collabops_submission"
        constraints = [models.UniqueConstraint(fields=["item", "revision"], name="co_submission_revision_uq")]
        indexes = [models.Index(fields=["company", "status_code", "submitted_at"], name="co_submission_status_idx")]

    def clean(self) -> None:
        super().clean()
        if self.item_id and self.item.company_id != self.company_id:
            raise ValidationError("Submission cannot cross companies")
        if self.contact_id:
            if self.contact.company_id != self.company_id:
                raise ValidationError("Submission contact cannot cross companies")
            if self.contact.organization_id != self.item.organization_id:
                raise ValidationError("Submission contact must belong to the item partner")


class CollaborationDecision(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="collaboration_decisions")
    item = models.ForeignKey(CollaborationItem, on_delete=models.PROTECT, related_name="decisions")
    submission = models.ForeignKey(
        CollaborationSubmission,
        on_delete=models.PROTECT,
        related_name="decisions",
        null=True,
        blank=True,
    )
    decision_code = models.CharField(max_length=40)
    notes = models.TextField(blank=True)
    decided_by_public_id = models.UUIDField()
    decided_by_type = models.CharField(max_length=30, default="INTERNAL")
    decided_at = models.DateTimeField()
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "collabops_decision"
        indexes = [models.Index(fields=["company", "decision_code", "decided_at"], name="co_decision_status_idx")]

    def clean(self) -> None:
        super().clean()
        if self.item_id and self.item.company_id != self.company_id:
            raise ValidationError("Decision cannot cross companies")
        if self.submission_id and self.submission.item_id != self.item_id:
            raise ValidationError("Decision submission must belong to the selected item")


class CollaborationMessage(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="collaboration_messages")
    item = models.ForeignKey(CollaborationItem, on_delete=models.PROTECT, related_name="messages")
    contact = models.ForeignKey(
        PartnerContact,
        on_delete=models.PROTECT,
        related_name="messages",
        null=True,
        blank=True,
    )
    sender_type_code = models.CharField(max_length=30, default="INTERNAL")
    sender_public_id = models.UUIDField()
    body = models.TextField()
    attachment_references = models.JSONField(default=list, blank=True)
    is_internal = models.BooleanField(default=False)
    sent_at = models.DateTimeField()

    class Meta:
        db_table = "collabops_message"
        indexes = [models.Index(fields=["company", "item", "sent_at"], name="co_message_thread_idx")]

    def clean(self) -> None:
        super().clean()
        if self.item_id and self.item.company_id != self.company_id:
            raise ValidationError("Message cannot cross companies")
        if self.contact_id and self.contact.company_id != self.company_id:
            raise ValidationError("Message contact cannot cross companies")
