from __future__ import annotations

from django.db.models import Q
from django.utils import timezone

from modules.collabops.models import (
    CollaborationItem,
    PartnerContact,
    PartnerOrganization,
    ProjectAccessGrant,
)
from modules.tenant.models import Company
from modules.workops.models import Project


def _item(item: CollaborationItem) -> dict[str, object]:
    return {
        "public_id": str(item.public_id),
        "reference": item.reference,
        "type": item.item_type_code,
        "title": item.title,
        "status": item.status_code,
        "priority": item.priority_code,
        "due_at": item.due_at,
        "project": {"public_id": str(item.project.public_id), "code": item.project.code, "name": item.project.name},
        "site": ({"public_id": str(item.site.public_id), "code": item.site.code, "name": item.site.name} if item.site else None),
        "partner": {"public_id": str(item.organization.public_id), "code": item.organization.code, "name": item.organization.display_name},
        "assigned_contact": ({"public_id": str(item.assigned_contact.public_id), "name": item.assigned_contact.full_name} if item.assigned_contact else None),
        "submission_count": item.submissions.count(),
        "message_count": item.messages.filter(is_internal=False).count(),
        "version": item.version,
    }


def internal_overview(company: Company) -> dict[str, object]:
    now = timezone.now()
    items = CollaborationItem.objects.filter(company=company).select_related(
        "organization", "assigned_contact", "project", "site"
    ).prefetch_related("submissions", "messages")
    open_items = items.exclude(status_code__in=["APPROVED", "REJECTED", "ACKNOWLEDGED", "CANCELLED"])
    partners = PartnerOrganization.objects.filter(company=company)
    contacts = PartnerContact.objects.filter(company=company)
    grants = ProjectAccessGrant.objects.filter(company=company, status_code="ACTIVE", revoked_at__isnull=True)
    return {
        "company": {"public_id": str(company.public_id), "name": company.display_name, "currency": company.currency, "timezone": company.timezone},
        "metrics": {
            "active_partners": partners.filter(status_code="ACTIVE").count(),
            "active_contacts": contacts.filter(status_code="ACTIVE").count(),
            "pending_invites": contacts.filter(status_code="INVITED").count(),
            "active_project_grants": grants.filter(Q(effective_to__isnull=True) | Q(effective_to__gt=now)).count(),
            "open_items": open_items.count(),
            "overdue_items": open_items.filter(due_at__lt=now).count(),
            "pending_submissions": open_items.filter(status_code="SUBMITTED").count(),
        },
        "partners": [
            {
                "public_id": str(partner.public_id),
                "code": partner.code,
                "name": partner.display_name,
                "type": partner.organization_type_code,
                "status": partner.status_code,
                "contact_count": partner.contacts.count(),
                "open_item_count": partner.collaboration_items.exclude(status_code__in=["APPROVED", "REJECTED", "ACKNOWLEDGED", "CANCELLED"]).count(),
            }
            for partner in partners.prefetch_related("contacts", "collaboration_items").order_by("display_name")[:100]
        ],
        "projects": [
            {
                "public_id": str(project.public_id),
                "code": project.code,
                "name": project.name,
                "status": project.status_code,
                "sites": [
                    {"public_id": str(site.public_id), "code": site.code, "name": site.name}
                    for site in project.sites.all()
                ],
            }
            for project in Project.objects.filter(company=company).prefetch_related("sites").order_by("code")[:200]
        ],
        "contacts": [
            {
                "public_id": str(contact.public_id),
                "organization_public_id": str(contact.organization.public_id),
                "organization_name": contact.organization.display_name,
                "name": contact.full_name,
                "email": contact.email,
                "status": contact.status_code,
                "can_approve": contact.can_approve,
            }
            for contact in contacts.select_related("organization").order_by("organization__display_name", "full_name")[:200]
        ],
        "items": [_item(item) for item in items.order_by("due_at", "-created_at")[:200]],
    }


def partner_overview(contact: PartnerContact) -> dict[str, object]:
    now = timezone.now()
    grants = ProjectAccessGrant.objects.filter(
        company=contact.company,
        contact=contact,
        status_code="ACTIVE",
        revoked_at__isnull=True,
        effective_from__lte=now,
    ).filter(Q(effective_to__isnull=True) | Q(effective_to__gt=now)).select_related("project", "site")
    project_ids = list(grants.values_list("project_id", flat=True))
    items = CollaborationItem.objects.filter(
        company=contact.company,
        organization=contact.organization,
        project_id__in=project_ids,
    ).filter(Q(assigned_contact__isnull=True) | Q(assigned_contact=contact)).select_related(
        "organization", "assigned_contact", "project", "site"
    ).prefetch_related("submissions", "messages")
    open_items = items.exclude(status_code__in=["APPROVED", "REJECTED", "ACKNOWLEDGED", "CANCELLED"])
    return {
        "company": {"public_id": str(contact.company.public_id), "name": contact.company.display_name},
        "contact": {
            "public_id": str(contact.public_id),
            "name": contact.full_name,
            "email": contact.email,
            "organization": {"public_id": str(contact.organization.public_id), "name": contact.organization.display_name, "type": contact.organization.organization_type_code},
            "can_approve": contact.can_approve,
        },
        "metrics": {
            "active_projects": len(set(project_ids)),
            "open_items": open_items.count(),
            "due_today": open_items.filter(due_at__date=timezone.localdate()).count(),
            "overdue": open_items.filter(due_at__lt=now).count(),
            "submitted": items.filter(status_code="SUBMITTED").count(),
        },
        "grants": [
            {
                "public_id": str(grant.public_id),
                "project": {"public_id": str(grant.project.public_id), "code": grant.project.code, "name": grant.project.name},
                "site": ({"public_id": str(grant.site.public_id), "code": grant.site.code, "name": grant.site.name} if grant.site else None),
                "scopes": grant.scopes,
                "effective_to": grant.effective_to,
            }
            for grant in grants
        ],
        "items": [_item(item) for item in items.order_by("due_at", "-created_at")[:200]],
    }
