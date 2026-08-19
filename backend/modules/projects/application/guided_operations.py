from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

from django.db.models import Q, Sum
from django.utils import timezone

from modules.crm.models import Activity, Customer, Lead, Opportunity
from modules.design.models import DesignDocument, DesignIssue, DesignVersion
from modules.digitaltwinops.models import HandoverAssetRecord
from modules.finance.models import Invoice
from modules.insightops.models import PortfolioSnapshot
from modules.procurement.models import (
    GoodsReceipt,
    PurchaseOrder,
    PurchaseRequest,
    RequestForQuotation,
    VendorQuote,
)
from modules.projects.models import DeliveryStage, Project, ProjectTask
from modules.quality.models import Inspection, NonConformanceReport
from modules.safety.models import SafetyIncident, SafetyObservation
from modules.workflow.application.approval_center import approval_center_items


def _iso(value: Any) -> str | None:
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _event(
    *,
    kind: str,
    when: datetime,
    title: str,
    detail: str,
    tone: str,
    href: str,
    reference: str = "",
) -> dict[str, Any]:
    return {
        "kind": kind,
        "occurred_at": when.isoformat(),
        "title": title,
        "detail": detail,
        "tone": tone,
        "href": href,
        "reference": reference,
    }


def project_site_timeline(
    *,
    company,
    project: Project,
    permission_codes: set[str],
) -> dict[str, Any]:
    """Permission-aware visual site pulse over existing governed records."""
    now = timezone.now()
    today = timezone.localdate()
    events: list[dict[str, Any]] = []

    tasks = (
        ProjectTask.objects.select_related("stage")
        .filter(company=company, project=project)
        .order_by("-updated_at")[:80]
    )
    task_count = tasks.count()
    overdue_tasks = 0
    for task in tasks:
        complete = task.stage.outcome in {
            DeliveryStage.Outcome.COMPLETE,
            DeliveryStage.Outcome.CANCELLED,
        }
        overdue = bool(task.planned_end_date and task.planned_end_date < today and not complete)
        overdue_tasks += int(overdue)
        events.append(
            _event(
                kind="TASK",
                when=task.updated_at,
                title=task.title,
                detail=f"{task.progress_percent}% · {task.stage.name}"
                + (f" · due {task.planned_end_date.isoformat()}" if task.planned_end_date else ""),
                tone="ATTENTION" if overdue else ("SUCCESS" if complete else "INFO"),
                href="/delivery?tab=projects",
                reference=task.code,
            )
        )

    open_ncrs = inspections_today = 0
    if "quality.dashboard.read" in permission_codes:
        inspections = (
            Inspection.objects.select_related("stage")
            .filter(company=company, project=project)
            .order_by("-created_at")[:60]
        )
        for item in inspections:
            when = item.inspected_at or item.scheduled_at or item.created_at
            if when.date() == today:
                inspections_today += 1
            events.append(
                _event(
                    kind="QUALITY",
                    when=when,
                    title=item.title,
                    detail=f"Inspection · {item.stage.name}"
                    + (f" · result {item.overall_result}" if item.overall_result else ""),
                    tone="SUCCESS" if item.overall_result.lower() in {"pass", "passed", "approved"} else "INFO",
                    href="/field-operations?tab=quality",
                    reference=item.inspection_number,
                )
            )

        ncrs = (
            NonConformanceReport.objects.select_related("stage")
            .filter(company=company, project=project)
            .order_by("-created_at")[:60]
        )
        for item in ncrs:
            closed = bool(item.verified_at) or item.stage.outcome in {
                "approved",
                "complete",
                "cancelled",
            }
            open_ncrs += int(not closed)
            events.append(
                _event(
                    kind="NCR",
                    when=item.updated_at,
                    title=item.title,
                    detail=f"{item.severity} · {item.stage.name}"
                    + (f" · due {item.due_date.isoformat()}" if item.due_date else ""),
                    tone="SUCCESS" if closed else "ATTENTION",
                    href="/field-operations?tab=quality",
                    reference=item.ncr_number,
                )
            )

    incidents_30d = open_safety_actions = 0
    if "safety.dashboard.read" in permission_codes:
        cutoff = now - timedelta(days=30)
        incidents = (
            SafetyIncident.objects.select_related("stage")
            .filter(company=company, project=project)
            .order_by("-occurred_at")[:60]
        )
        for item in incidents:
            incidents_30d += int(item.occurred_at >= cutoff)
            events.append(
                _event(
                    kind="SAFETY",
                    when=item.occurred_at,
                    title=item.title,
                    detail=f"{item.severity.replace('_', ' ')} · {item.stage.name}",
                    tone="ATTENTION" if item.severity in {"major", "critical", "fatal"} else "WARNING",
                    href="/field-operations?tab=safety",
                    reference=item.incident_number,
                )
            )

        observations = (
            SafetyObservation.objects.filter(company=company, project=project)
            .order_by("-observed_at")[:60]
        )
        for item in observations:
            open_action = item.action_required and item.closed_at is None
            open_safety_actions += int(open_action)
            events.append(
                _event(
                    kind="SAFETY_OBSERVATION",
                    when=item.observed_at,
                    title=item.observation_type.replace("_", " ").title(),
                    detail=item.description[:220],
                    tone="ATTENTION" if open_action else ("SUCCESS" if item.is_positive else "INFO"),
                    href="/field-operations?tab=safety",
                    reference=item.observation_number,
                )
            )

    receipts_7d = 0
    if "procurement.dashboard.read" in permission_codes:
        cutoff = now - timedelta(days=7)
        receipts = (
            GoodsReceipt.objects.select_related("purchase_order")
            .filter(
                company=company,
                purchase_order__purchase_request__project=project,
            )
            .order_by("-received_at")[:50]
        )
        for receipt in receipts:
            receipts_7d += int(receipt.received_at >= cutoff)
            events.append(
                _event(
                    kind="MATERIAL",
                    when=receipt.received_at,
                    title=f"Goods receipt {receipt.receipt_number}",
                    detail=f"PO {receipt.purchase_order.po_number}",
                    tone="SUCCESS" if receipt.posted_at else "INFO",
                    href=f"/project360/procurement?project={project.public_id}",
                    reference=receipt.receipt_number,
                )
            )

    if "design.dashboard.read" in permission_codes or "design.document.read" in permission_codes:
        issues = (
            DesignIssue.objects.filter(company=company, project=project)
            .order_by("-updated_at")[:40]
        )
        for issue in issues:
            events.append(
                _event(
                    kind="DESIGN",
                    when=issue.updated_at,
                    title=issue.title,
                    detail=f"{issue.severity} · {'closed' if issue.closed_at else 'open'}",
                    tone="SUCCESS" if issue.closed_at else "WARNING",
                    href=f"/project360/design?project={project.public_id}",
                    reference="",
                )
            )

    events.sort(key=lambda item: item["occurred_at"], reverse=True)
    return {
        "project": {
            "public_id": str(project.public_id),
            "code": project.code,
            "name": project.name,
            "stage_name": project.stage.name,
        },
        "summary": {
            "tasks": task_count,
            "overdue_tasks": overdue_tasks,
            "inspections_today": inspections_today if "quality.dashboard.read" in permission_codes else None,
            "open_ncrs": open_ncrs if "quality.dashboard.read" in permission_codes else None,
            "incidents_30d": incidents_30d if "safety.dashboard.read" in permission_codes else None,
            "open_safety_actions": open_safety_actions if "safety.dashboard.read" in permission_codes else None,
            "receipts_7d": receipts_7d if "procurement.dashboard.read" in permission_codes else None,
        },
        "events": events[:180],
    }


def project_procurement_flow(*, company, project: Project) -> dict[str, Any]:
    """Visualize the governed PR -> RFQ -> quote -> PO -> receipt chain."""
    requests = list(
        PurchaseRequest.objects.select_related("stage")
        .filter(company=company, project=project)
        .order_by("-created_at")[:150]
    )
    request_ids = [item.pk for item in requests]
    rfqs = list(
        RequestForQuotation.objects.select_related("stage")
        .filter(company=company, purchase_request_id__in=request_ids)
        .order_by("created_at")
    )
    rfq_ids = [item.pk for item in rfqs]
    quotes = list(
        VendorQuote.objects.select_related("stage", "vendor")
        .filter(company=company, rfq_id__in=rfq_ids)
        .order_by("created_at")
    )
    orders = list(
        PurchaseOrder.objects.select_related("stage", "vendor", "purchase_request")
        .filter(company=company, purchase_request_id__in=request_ids)
        .order_by("created_at")
    )
    order_ids = [item.pk for item in orders]
    receipts = list(
        GoodsReceipt.objects.select_related("stage", "purchase_order")
        .filter(company=company, purchase_order_id__in=order_ids)
        .order_by("received_at")
    )

    rfqs_by_request: dict[int, list[Any]] = defaultdict(list)
    quotes_by_rfq: dict[int, list[Any]] = defaultdict(list)
    orders_by_request: dict[int, list[Any]] = defaultdict(list)
    receipts_by_order: dict[int, list[Any]] = defaultdict(list)
    for item in rfqs:
        rfqs_by_request[item.purchase_request_id].append(item)
    for item in quotes:
        quotes_by_rfq[item.rfq_id].append(item)
    for item in orders:
        orders_by_request[item.purchase_request_id].append(item)
    for item in receipts:
        receipts_by_order[item.purchase_order_id].append(item)

    cards: list[dict[str, Any]] = []
    blocked = 0
    for request in requests:
        request_rfqs = rfqs_by_request[request.pk]
        request_quotes = [q for rfq in request_rfqs for q in quotes_by_rfq[rfq.pk]]
        request_orders = orders_by_request[request.pk]
        request_receipts = [r for order in request_orders for r in receipts_by_order[order.pk]]

        if not request_rfqs:
            current_step = "RFQ"
            status = "ACTION"
            next_action = "Create / issue RFQ"
        elif not request_quotes:
            current_step = "QUOTATION"
            status = "WAITING"
            next_action = "Collect vendor quotations"
        elif not request_orders:
            current_step = "AWARD"
            status = "ACTION"
            next_action = "Compare and award"
        elif not request_receipts:
            current_step = "DELIVERY"
            status = "WAITING"
            next_action = "Track delivery / receive goods"
        else:
            current_step = "RECEIVED"
            status = "COMPLETE"
            next_action = "Review receipt / inventory posting"

        blocked += int(status == "ACTION")
        cards.append(
            {
                "public_id": str(request.public_id),
                "request_number": request.request_number,
                "title": request.title,
                "required_by_date": _iso(request.required_by_date),
                "currency": request.currency,
                "estimated_total": str(request.estimated_total),
                "stage_name": request.stage.name,
                "current_step": current_step,
                "status": status,
                "next_action": next_action,
                "counts": {
                    "rfqs": len(request_rfqs),
                    "quotes": len(request_quotes),
                    "purchase_orders": len(request_orders),
                    "receipts": len(request_receipts),
                },
                "purchase_orders": [
                    {
                        "public_id": str(order.public_id),
                        "po_number": order.po_number,
                        "vendor_name": order.vendor.display_name,
                        "total_amount": str(order.total_amount),
                        "currency": order.currency,
                        "stage_name": order.stage.name,
                        "receipt_count": len(receipts_by_order[order.pk]),
                    }
                    for order in request_orders
                ],
            }
        )

    po_value = sum((order.total_amount for order in orders), Decimal("0"))
    return {
        "project": {
            "public_id": str(project.public_id),
            "code": project.code,
            "name": project.name,
        },
        "summary": {
            "requests": len(requests),
            "rfqs": len(rfqs),
            "quotes": len(quotes),
            "purchase_orders": len(orders),
            "receipts": len(receipts),
            "action_required": blocked,
            "po_value": str(po_value),
            "currency": project.currency,
        },
        "requests": cards,
    }


def project_handover_board(
    *,
    company,
    project: Project,
    permission_codes: set[str],
) -> dict[str, Any]:
    if not ({"digitaltwin.view", "digitaltwin.handover"} & permission_codes):
        return {
            "available": False,
            "project": {"public_id": str(project.public_id), "code": project.code, "name": project.name},
            "message": "Handover evidence is restricted for this user.",
            "summary": {},
            "checkpoints": [],
            "assets": [],
        }

    assets = list(
        HandoverAssetRecord.objects.filter(
            company=company,
            project_public_id=project.public_id,
        ).order_by("asset_tag")[:300]
    )
    verified = sum(1 for item in assets if item.verified_by_public_id)
    commissioned = sum(1 for item in assets if item.commissioned_on)
    with_documents = sum(1 for item in assets if item.document_references)

    tasks = ProjectTask.objects.select_related("stage").filter(company=company, project=project)
    task_count = tasks.count()
    incomplete_tasks = tasks.exclude(
        stage__outcome__in=[DeliveryStage.Outcome.COMPLETE, DeliveryStage.Outcome.CANCELLED]
    ).count()

    open_ncrs: int | None = None
    if "quality.dashboard.read" in permission_codes:
        open_ncrs = (
            NonConformanceReport.objects.select_related("stage")
            .filter(company=company, project=project)
            .exclude(stage__outcome__in=["approved", "complete", "cancelled"])
            .count()
        )

    outstanding: Decimal | None = None
    if "finance.dashboard.read" in permission_codes:
        outstanding = (
            Invoice.objects.filter(
                company=company,
                project=project,
                invoice_type=Invoice.InvoiceType.CLIENT,
                reversed_at__isnull=True,
            ).aggregate(total=Sum("outstanding_amount"))["total"]
            or Decimal("0")
        )

    issued_designs: int | None = None
    if "design.dashboard.read" in permission_codes or "design.document.read" in permission_codes:
        issued_designs = DesignVersion.objects.filter(
            company=company,
            document__project=project,
            issued_at__isnull=False,
        ).count()

    checkpoints = [
        {
            "code": "EXECUTION",
            "label": "Execution work complete",
            "status": "DONE" if task_count > 0 and incomplete_tasks == 0 else "ATTENTION",
            "value": f"{task_count - incomplete_tasks}/{task_count}",
            "href": f"/project360/site?project={project.public_id}",
        },
        {
            "code": "ASSET_REGISTER",
            "label": "Handover asset register captured",
            "status": "DONE" if assets else "PENDING",
            "value": len(assets),
            "href": "/platform/digital-twin-operations",
        },
        {
            "code": "VERIFICATION",
            "label": "Assets independently verified",
            "status": "DONE" if assets and verified == len(assets) else ("ACTIVE" if verified else "PENDING"),
            "value": f"{verified}/{len(assets)}",
            "href": "/platform/digital-twin-operations",
        },
        {
            "code": "COMMISSIONING",
            "label": "Commissioning evidence complete",
            "status": "DONE" if assets and commissioned == len(assets) else ("ACTIVE" if commissioned else "PENDING"),
            "value": f"{commissioned}/{len(assets)}",
            "href": "/platform/digital-twin-operations",
        },
        {
            "code": "DOCUMENTS",
            "label": "O&M / warranty documents attached",
            "status": "DONE" if assets and with_documents == len(assets) else ("ACTIVE" if with_documents else "PENDING"),
            "value": f"{with_documents}/{len(assets)}",
            "href": "/platform/digital-twin-operations",
        },
    ]
    if open_ncrs is not None:
        checkpoints.append(
            {
                "code": "QUALITY",
                "label": "Quality NCRs closed",
                "status": "DONE" if open_ncrs == 0 else "ATTENTION",
                "value": open_ncrs,
                "href": "/field-operations?tab=quality",
            }
        )
    if outstanding is not None:
        checkpoints.append(
            {
                "code": "COMMERCIAL",
                "label": "Client outstanding cleared",
                "status": "DONE" if outstanding == 0 else "ATTENTION",
                "value": str(outstanding),
                "href": "/finance",
            }
        )
    if issued_designs is not None:
        checkpoints.append(
            {
                "code": "ISSUED_DESIGN",
                "label": "Issued design evidence available",
                "status": "DONE" if issued_designs else "PENDING",
                "value": issued_designs,
                "href": f"/project360/design?project={project.public_id}",
            }
        )

    done = sum(1 for item in checkpoints if item["status"] == "DONE")
    readiness = int(done / len(checkpoints) * 100) if checkpoints else 0

    return {
        "available": True,
        "project": {
            "public_id": str(project.public_id),
            "code": project.code,
            "name": project.name,
        },
        "summary": {
            "readiness_percent": readiness,
            "assets": len(assets),
            "verified_assets": verified,
            "commissioned_assets": commissioned,
            "assets_with_documents": with_documents,
            "incomplete_tasks": incomplete_tasks,
            "open_ncrs": open_ncrs,
            "client_outstanding": str(outstanding) if outstanding is not None else None,
        },
        "checkpoints": checkpoints,
        "assets": [
            {
                "public_id": str(item.public_id),
                "asset_tag": item.asset_tag,
                "asset_name": item.asset_name,
                "classification_code": item.classification_code,
                "location_reference": item.location_reference,
                "manufacturer": item.manufacturer,
                "serial_number": item.serial_number,
                "operation_status_code": item.operation_status_code,
                "commissioned_on": _iso(item.commissioned_on),
                "warranty_end_on": _iso(item.warranty_end_on),
                "verified": bool(item.verified_by_public_id),
                "document_count": len(item.document_references or []),
            }
            for item in assets
        ],
    }


def guided_workbench(*, tenant_context) -> dict[str, Any]:
    """Permission-driven 'Today' surface. No hard-coded role names."""
    company = tenant_context.company
    permissions = set(tenant_context.permission_codes())
    membership_id = tenant_context.membership.public_id
    today = timezone.localdate()
    now = timezone.now()
    horizon = today + timedelta(days=7)

    sections: list[dict[str, Any]] = []
    summary = {
        "my_tasks": 0,
        "crm_followups": 0,
        "approvals": 0,
        "overdue_invoices": 0,
        "procurement_due": 0,
    }

    if "project.dashboard.read" in permissions:
        tasks = list(
            ProjectTask.objects.select_related("project", "stage")
            .filter(
                company=company,
                assignee_membership_public_id=membership_id,
            )
            .exclude(stage__outcome__in=[DeliveryStage.Outcome.COMPLETE, DeliveryStage.Outcome.CANCELLED])
            .order_by("planned_end_date", "created_at")[:30]
        )
        summary["my_tasks"] = len(tasks)
        sections.append(
            {
                "code": "MY_TASKS",
                "title": "My project work",
                "href": "/project360",
                "items": [
                    {
                        "title": task.title,
                        "meta": f"{task.project.code} · {task.progress_percent}%"
                        + (f" · due {task.planned_end_date.isoformat()}" if task.planned_end_date else ""),
                        "tone": "ATTENTION"
                        if task.planned_end_date and task.planned_end_date < today
                        else "INFO",
                        "href": f"/project360/site?project={task.project.public_id}",
                    }
                    for task in tasks[:8]
                ],
            }
        )

    if "crm.dashboard.read" in permissions:
        activities = list(
            Activity.objects.filter(
                company=company,
                owner_membership_public_id=membership_id,
                status=Activity.Status.PLANNED,
                scheduled_for__isnull=False,
                scheduled_for__lte=now + timedelta(days=7),
            ).order_by("scheduled_for")[:30]
        )
        summary["crm_followups"] = len(activities)
        sections.append(
            {
                "code": "CRM",
                "title": "Calls & follow-ups",
                "href": "/crm",
                "items": [
                    {
                        "title": item.subject,
                        "meta": f"{item.activity_type.replace('_', ' ')} · {_iso(item.scheduled_for)}",
                        "tone": "ATTENTION" if item.scheduled_for and item.scheduled_for < now else "INFO",
                        "href": "/crm",
                    }
                    for item in activities[:8]
                ],
            }
        )

    if {"workflow.approve", "design.review.decide"} & permissions:
        approvals = approval_center_items(tenant_context=tenant_context)
        summary["approvals"] = approvals["summary"]["pending"]
        sections.append(
            {
                "code": "APPROVALS",
                "title": "My approvals",
                "href": "/approvals",
                "items": [
                    {
                        "title": item["title"],
                        "meta": item["eyebrow"],
                        "tone": "ATTENTION" if item["overdue"] else "INFO",
                        "href": item["detail_href"] or "/approvals",
                    }
                    for item in approvals["items"][:8]
                ],
            }
        )

    if "finance.dashboard.read" in permissions:
        invoices = list(
            Invoice.objects.select_related("project")
            .filter(
                company=company,
                invoice_type=Invoice.InvoiceType.CLIENT,
                reversed_at__isnull=True,
                outstanding_amount__gt=0,
                due_date__lt=today,
            )
            .order_by("due_date")[:30]
        )
        summary["overdue_invoices"] = len(invoices)
        sections.append(
            {
                "code": "COLLECTIONS",
                "title": "Overdue collections",
                "href": "/finance",
                "items": [
                    {
                        "title": item.invoice_number,
                        "meta": f"{item.project.code} · {item.currency} {item.outstanding_amount} · due {item.due_date.isoformat()}",
                        "tone": "ATTENTION",
                        "href": "/finance",
                    }
                    for item in invoices[:8]
                ],
            }
        )

    if "procurement.dashboard.read" in permissions:
        due = list(
            PurchaseRequest.objects.select_related("project", "stage")
            .filter(
                company=company,
                required_by_date__isnull=False,
                required_by_date__lte=horizon,
            )
            .exclude(project__isnull=True)
            .order_by("required_by_date")[:30]
        )
        summary["procurement_due"] = len(due)
        sections.append(
            {
                "code": "PROCUREMENT",
                "title": "Procurement due soon",
                "href": "/supply",
                "items": [
                    {
                        "title": item.title,
                        "meta": f"{item.request_number} · {item.project.code} · required {item.required_by_date.isoformat()}",
                        "tone": "ATTENTION" if item.required_by_date < today else "WARNING",
                        "href": f"/project360/procurement?project={item.project.public_id}",
                    }
                    for item in due[:8]
                ],
            }
        )

    attention_count = sum(
        1
        for section in sections
        for item in section["items"]
        if item["tone"] == "ATTENTION"
    )
    return {
        "generated_at": now.isoformat(),
        "summary": summary,
        "attention_count": attention_count,
        "sections": sections,
        "quick_actions": [
            {"label": "Open Project 360", "href": "/project360"},
            {"label": "Search Build360", "href": "/search"},
            {"label": "My approvals", "href": "/approvals"},
        ],
    }


def universal_search(
    *,
    company,
    query: str,
    permission_codes: set[str],
) -> dict[str, Any]:
    q = query.strip()
    if len(q) < 2:
        return {"query": q, "items": [], "message": "Enter at least 2 characters."}

    items: list[dict[str, Any]] = []

    def add(kind: str, label: str, subtitle: str, href: str, public_id: Any) -> None:
        if len(items) >= 50:
            return
        items.append(
            {
                "kind": kind,
                "label": label,
                "subtitle": subtitle,
                "href": href,
                "public_id": str(public_id),
            }
        )

    if "project.dashboard.read" in permission_codes:
        for item in Project.objects.select_related("stage").filter(
            company=company,
            archived_at__isnull=True,
        ).filter(Q(code__icontains=q) | Q(name__icontains=q)).order_by("code")[:10]:
            add("PROJECT", item.name, f"{item.code} · {item.stage.name}", f"/project360?project={item.public_id}", item.public_id)

    if "crm.dashboard.read" in permission_codes:
        for item in Customer.objects.filter(company=company, archived_at__isnull=True).filter(
            Q(display_name__icontains=q) | Q(legal_name__icontains=q) | Q(external_reference__icontains=q)
        ).order_by("display_name")[:8]:
            add("CUSTOMER", item.display_name, item.external_reference or item.kind, "/crm", item.public_id)
        for item in Lead.objects.select_related("stage").filter(company=company, title__icontains=q).order_by("-created_at")[:8]:
            add("LEAD", item.title, item.stage.name, "/crm", item.public_id)
        for item in Opportunity.objects.select_related("stage", "customer").filter(
            company=company
        ).filter(Q(name__icontains=q) | Q(customer__display_name__icontains=q)).order_by("-created_at")[:8]:
            add("OPPORTUNITY", item.name, f"{item.customer.display_name} · {item.stage.name}", "/crm", item.public_id)

    if "design.document.read" in permission_codes or "design.dashboard.read" in permission_codes:
        for item in DesignDocument.objects.select_related("project").filter(
            company=company,
            archived_at__isnull=True,
        ).filter(Q(document_number__icontains=q) | Q(title__icontains=q)).order_by("document_number")[:10]:
            add(
                "DESIGN",
                item.title,
                f"{item.project.code} · {item.document_number} · {item.discipline_code}",
                f"/project360/design?project={item.project.public_id}&document={item.public_id}",
                item.public_id,
            )

    if "procurement.dashboard.read" in permission_codes:
        for item in PurchaseRequest.objects.select_related("project").filter(
            company=company
        ).filter(Q(request_number__icontains=q) | Q(title__icontains=q)).order_by("-created_at")[:8]:
            add(
                "PURCHASE_REQUEST",
                item.title,
                f"{item.request_number}" + (f" · {item.project.code}" if item.project else ""),
                f"/project360/procurement?project={item.project.public_id}" if item.project else "/supply",
                item.public_id,
            )
        for item in PurchaseOrder.objects.select_related("purchase_request__project", "vendor").filter(
            company=company
        ).filter(Q(po_number__icontains=q) | Q(vendor__display_name__icontains=q)).order_by("-created_at")[:8]:
            project = item.purchase_request.project
            add(
                "PURCHASE_ORDER",
                item.po_number,
                f"{item.vendor.display_name} · {item.currency} {item.total_amount}",
                f"/project360/procurement?project={project.public_id}" if project else "/supply",
                item.public_id,
            )

    if "finance.dashboard.read" in permission_codes:
        for item in Invoice.objects.select_related("project").filter(
            company=company,
            reversed_at__isnull=True,
        ).filter(Q(invoice_number__icontains=q) | Q(counterparty_name__icontains=q)).order_by("-invoice_date")[:8]:
            add(
                "INVOICE",
                item.invoice_number,
                f"{item.project.code} · {item.counterparty_name} · {item.currency} {item.outstanding_amount} outstanding",
                "/finance",
                item.public_id,
            )

    if {"digitaltwin.view", "digitaltwin.handover"} & permission_codes:
        for item in HandoverAssetRecord.objects.filter(company=company).filter(
            Q(asset_tag__icontains=q) | Q(asset_name__icontains=q) | Q(serial_number__icontains=q)
        ).order_by("asset_tag")[:8]:
            href = f"/project360/handover?project={item.project_public_id}" if item.project_public_id else "/platform/digital-twin-operations"
            add("HANDOVER_ASSET", item.asset_name, f"{item.asset_tag} · {item.operation_status_code}", href, item.public_id)

    return {"query": q, "items": items[:50], "count": min(len(items), 50)}



def executive_portfolio(*, company, permission_codes: set[str]) -> dict[str, Any]:
    """Executive portfolio projection. Financial/quality/safety values remain permission-gated."""
    today = timezone.localdate()
    projects = list(
        Project.objects.select_related("stage")
        .filter(company=company, archived_at__isnull=True)
        .order_by("code")[:250]
    )
    project_ids = [item.pk for item in projects]
    tasks = list(
        ProjectTask.objects.select_related("stage")
        .filter(company=company, project_id__in=project_ids)
    )
    tasks_by_project: dict[int, list[ProjectTask]] = defaultdict(list)
    for task in tasks:
        tasks_by_project[task.project_id].append(task)

    ncr_by_project: dict[int, int] = defaultdict(int)
    if "quality.dashboard.read" in permission_codes:
        for item in NonConformanceReport.objects.select_related("stage").filter(
            company=company,
            project_id__in=project_ids,
        ):
            if item.verified_at is None and item.stage.outcome not in {"approved", "complete", "cancelled"}:
                ncr_by_project[item.project_id] += 1

    incidents_by_project: dict[int, int] = defaultdict(int)
    if "safety.dashboard.read" in permission_codes:
        cutoff = timezone.now() - timedelta(days=30)
        for item in SafetyIncident.objects.filter(
            company=company,
            project_id__in=project_ids,
            occurred_at__gte=cutoff,
        ):
            incidents_by_project[item.project_id] += 1

    client_invoiced_by_project: dict[int, Decimal] = defaultdict(lambda: Decimal("0"))
    outstanding_by_project: dict[int, Decimal] = defaultdict(lambda: Decimal("0"))
    vendor_invoiced_by_project: dict[int, Decimal] = defaultdict(lambda: Decimal("0"))
    if "finance.dashboard.read" in permission_codes:
        invoices = Invoice.objects.filter(
            company=company,
            project_id__in=project_ids,
            reversed_at__isnull=True,
        )
        for invoice in invoices:
            if invoice.invoice_type == Invoice.InvoiceType.CLIENT:
                client_invoiced_by_project[invoice.project_id] += invoice.total_amount
                outstanding_by_project[invoice.project_id] += invoice.outstanding_amount
            else:
                vendor_invoiced_by_project[invoice.project_id] += invoice.total_amount

    cards: list[dict[str, Any]] = []
    delayed = attention = 0
    approved_budget = sum((item.approved_budget for item in projects), Decimal("0"))
    for project in projects:
        project_tasks = tasks_by_project[project.pk]
        completed = [
            task for task in project_tasks
            if task.stage.outcome in {DeliveryStage.Outcome.COMPLETE, DeliveryStage.Outcome.CANCELLED}
        ]
        progress = (
            int(sum(task.progress_percent for task in project_tasks) / len(project_tasks))
            if project_tasks else 0
        )
        overdue = sum(
            1 for task in project_tasks
            if task.planned_end_date and task.planned_end_date < today
            and task.stage.outcome not in {DeliveryStage.Outcome.COMPLETE, DeliveryStage.Outcome.CANCELLED}
        )
        schedule_late = bool(project.planned_end_date and project.planned_end_date < today and not project.actual_end_date)
        ncrs = ncr_by_project[project.pk] if "quality.dashboard.read" in permission_codes else None
        incidents = incidents_by_project[project.pk] if "safety.dashboard.read" in permission_codes else None
        outstanding = outstanding_by_project[project.pk] if "finance.dashboard.read" in permission_codes else None
        score = overdue * 2 + int(schedule_late) * 3 + (ncrs or 0) * 2 + (incidents or 0) * 2 + int(bool(outstanding and outstanding > 0))
        if score >= 6:
            health = "CRITICAL"
        elif score >= 3:
            health = "ATTENTION"
        else:
            health = "ON_TRACK"
        delayed += int(schedule_late or overdue > 0)
        attention += int(health != "ON_TRACK")
        cards.append({
            "public_id": str(project.public_id),
            "code": project.code,
            "name": project.name,
            "stage_name": project.stage.name,
            "planned_end_date": _iso(project.planned_end_date),
            "approved_budget": str(project.approved_budget),
            "currency": project.currency,
            "progress_percent": progress,
            "task_count": len(project_tasks),
            "completed_tasks": len(completed),
            "overdue_tasks": overdue,
            "open_ncrs": ncrs,
            "safety_incidents_30d": incidents,
            "client_invoiced": str(client_invoiced_by_project[project.pk]) if outstanding is not None else None,
            "client_outstanding": str(outstanding) if outstanding is not None else None,
            "vendor_invoiced": str(vendor_invoiced_by_project[project.pk]) if outstanding is not None else None,
            "health": health,
            "href": f"/project360?project={project.public_id}",
        })

    finance_summary = None
    if "finance.dashboard.read" in permission_codes:
        finance_summary = {
            "client_invoiced": str(sum(client_invoiced_by_project.values(), Decimal("0"))),
            "client_outstanding": str(sum(outstanding_by_project.values(), Decimal("0"))),
            "vendor_invoiced": str(sum(vendor_invoiced_by_project.values(), Decimal("0"))),
            "currency": company.currency,
        }

    history: list[dict[str, Any]] = []
    if "insights.view" in permission_codes:
        snapshots = (
            PortfolioSnapshot.objects.filter(
                company=company,
                status_code="PUBLISHED",
            )
            .order_by("-as_of_date", "-created_at")[:12]
        )
        history = [
            {
                "public_id": str(item.public_id),
                "code": item.code,
                "as_of_date": item.as_of_date.isoformat(),
                "projects_total": item.projects_total,
                "projects_healthy": item.projects_healthy,
                "projects_at_risk": item.projects_at_risk,
                "projects_critical": item.projects_critical,
                "schedule_performance_percent": str(item.schedule_performance_percent),
                "cost_performance_percent": str(item.cost_performance_percent),
                "portfolio_value": str(item.portfolio_value),
                "currency": item.currency,
                "narrative": item.narrative,
            }
            for item in reversed(list(snapshots))
        ]

    return {
        "generated_at": timezone.now().isoformat(),
        "summary": {
            "active_projects": len(projects),
            "projects_with_attention": attention,
            "schedule_attention": delayed,
            "approved_budget": str(approved_budget),
            "currency": company.currency,
        },
        "finance": finance_summary,
        "history": history,
        "history_available": "insights.view" in permission_codes,
        "snapshot_prefill": (
            {
                "as_of_date": timezone.localdate().isoformat(),
                "projects_total": len(cards),
                "projects_healthy": sum(1 for item in cards if item["health"] == "ON_TRACK"),
                "projects_at_risk": sum(1 for item in cards if item["health"] == "ATTENTION"),
                "projects_critical": sum(1 for item in cards if item["health"] == "CRITICAL"),
                "schedule_performance_percent": (
                    "100.00"
                    if not cards
                    else str(
                        (
                            Decimal(sum(1 for item in cards if item["overdue_tasks"] == 0))
                            / Decimal(len(cards))
                            * Decimal("100")
                        ).quantize(Decimal("0.01"))
                    )
                ),
                "portfolio_value": str(approved_budget),
                "currency": company.currency,
                "cost_performance_percent": None,
                "note": "Suggested draft values only. Cost performance requires governed finance evidence and is intentionally not auto-derived.",
            }
            if "insights.portfolio" in permission_codes
            else None
        ),
        "projects": sorted(cards, key=lambda item: ({"CRITICAL": 0, "ATTENTION": 1, "ON_TRACK": 2}[item["health"]], item["code"])),
    }


def project_evidence_panel(*, company, project: Project, permission_codes: set[str]) -> dict[str, Any]:
    """Evidence-first context panel. Derived signals and governed AI signals are clearly separated."""
    today = timezone.localdate()
    evidence: list[dict[str, Any]] = []

    tasks = ProjectTask.objects.select_related("stage").filter(company=company, project=project)
    overdue = tasks.filter(planned_end_date__lt=today).exclude(
        stage__outcome__in=[DeliveryStage.Outcome.COMPLETE, DeliveryStage.Outcome.CANCELLED]
    ).count()
    if overdue:
        evidence.append({
            "severity": "HIGH" if overdue >= 5 else "MEDIUM",
            "title": f"{overdue} project task(s) overdue",
            "why": "Derived from planned end dates and current governed task stages.",
            "source": "PROJECT_TASK",
            "href": f"/project360/site?project={project.public_id}",
        })

    if "design.dashboard.read" in permission_codes or "design.document.read" in permission_codes:
        open_issues = DesignIssue.objects.filter(company=company, project=project, closed_at__isnull=True).count()
        if open_issues:
            evidence.append({
                "severity": "MEDIUM",
                "title": f"{open_issues} open design issue(s)",
                "why": "Open DesignIssue records linked to this project.",
                "source": "DESIGN_ISSUE",
                "href": f"/project360/design?project={project.public_id}",
            })

    if "procurement.dashboard.read" in permission_codes:
        due_requests = PurchaseRequest.objects.filter(
            company=company,
            project=project,
            required_by_date__lt=today,
        ).count()
        if due_requests:
            evidence.append({
                "severity": "MEDIUM",
                "title": f"{due_requests} procurement request(s) past required date",
                "why": "Derived from PurchaseRequest.required_by_date.",
                "source": "PURCHASE_REQUEST",
                "href": f"/project360/procurement?project={project.public_id}",
            })

    if "quality.dashboard.read" in permission_codes:
        open_ncrs = NonConformanceReport.objects.select_related("stage").filter(
            company=company,
            project=project,
        ).exclude(stage__outcome__in=["approved", "complete", "cancelled"]).count()
        if open_ncrs:
            evidence.append({
                "severity": "HIGH",
                "title": f"{open_ncrs} quality NCR(s) still open",
                "why": "Open governed NCR records on the project.",
                "source": "QUALITY_NCR",
                "href": "/field-operations?tab=quality",
            })

    if "finance.dashboard.read" in permission_codes:
        outstanding = Invoice.objects.filter(
            company=company,
            project=project,
            invoice_type=Invoice.InvoiceType.CLIENT,
            reversed_at__isnull=True,
        ).aggregate(total=Sum("outstanding_amount"))["total"] or Decimal("0")
        if outstanding > 0:
            evidence.append({
                "severity": "MEDIUM",
                "title": f"{project.currency} {outstanding} client outstanding",
                "why": "Sum of unreversed client invoice outstanding amounts.",
                "source": "FINANCE_INVOICE",
                "href": "/finance",
            })

    ai_signals: list[dict[str, Any]] = []
    if "ai.risk.read" in permission_codes:
        from modules.ai.models import AIRiskSignal
        signals = AIRiskSignal.objects.filter(
            company=company,
            source_public_id=project.public_id,
            status__in=[AIRiskSignal.Status.OPEN, AIRiskSignal.Status.ACKNOWLEDGED],
        ).order_by("-created_at")[:30]
        ai_signals = [
            {
                "public_id": str(item.public_id),
                "severity": item.severity.upper(),
                "title": item.title,
                "description": item.description,
                "source_type": item.source_type,
                "evidence": item.evidence,
                "status": item.status,
                "created_at": item.created_at.isoformat(),
            }
            for item in signals
        ]

    evidence.sort(key=lambda item: ({"HIGH": 0, "MEDIUM": 1, "LOW": 2}.get(item["severity"], 3), item["title"]))
    return {
        "project": {"public_id": str(project.public_id), "code": project.code, "name": project.name},
        "derived_evidence": evidence,
        "ai_signals": ai_signals,
        "ai_available": "ai.risk.read" in permission_codes,
        "disclaimer": "Derived evidence is deterministic from governed records. AI signals are shown only when already created by the governed AI module.",
    }
