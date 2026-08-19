from __future__ import annotations

from decimal import Decimal
from typing import Any

from django.db import models
from django.db.models import Sum
from django.utils import timezone

from modules.configuration.models import ConfigurationVersion
from modules.design.models import DesignDocument, DesignIssue, DesignVersion
from modules.digitaltwinops.models import HandoverAssetRecord
from modules.estimation.models import Estimate, EstimateBaseline, EstimateVersion
from modules.finance.models import BudgetLine, Invoice, Payment, ProjectBudget, Variation
from modules.portal.models import PortalShare
from modules.procurement.models import GoodsReceipt, PurchaseOrder, PurchaseRequest
from modules.projects.models import DeliveryStage, Project, ProjectTask, WbsNode

LIFECYCLE_CODE = "PROJECT360_LIFECYCLE"


def _published_lifecycle(company) -> ConfigurationVersion | None:
    now = timezone.now()
    return (
        ConfigurationVersion.objects.select_related("definition")
        .filter(
            company=company,
            definition__code=LIFECYCLE_CODE,
            definition__is_active=True,
            status=ConfigurationVersion.Status.PUBLISHED,
            effective_from__lte=now,
        )
        .filter(models.Q(effective_to__isnull=True) | models.Q(effective_to__gt=now))
        .order_by("-version")
        .first()
    )


def _step(
    code: str,
    label: str,
    description: str,
    status: str,
    progress: int,
    evidence: dict[str, Any],
    *,
    action: dict[str, str] | None = None,
    workspace_href: str | None = None,
    checkpoints: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "code": code,
        "label": label,
        "description": description,
        "status": status,
        "progress_percent": max(0, min(100, progress)),
        "evidence": evidence,
        "workspace_href": workspace_href,
        "checkpoints": checkpoints or [],
    }
    if action:
        result["next_action"] = action
    return result


def _status(count: int, complete: bool = False, *, blocked: bool = False) -> str:
    if complete:
        return "COMPLETE"
    if blocked:
        return "BLOCKED"
    return "IN_PROGRESS" if count else "PENDING"


def _project_identity(project: Project) -> dict[str, Any]:
    return {
        "public_id": str(project.public_id),
        "code": project.code,
        "name": project.name,
        "stage_code": project.stage.code,
        "stage_name": project.stage.name,
        "currency": project.currency,
        "approved_budget": str(project.approved_budget),
        "planned_start_date": project.planned_start_date,
        "planned_end_date": project.planned_end_date,
        "actual_start_date": project.actual_start_date,
        "actual_end_date": project.actual_end_date,
        "location": project.location,
    }


def project_experience(*, company, project: Project, permission_codes: set[str]) -> dict[str, Any]:
    """Build a read-only Project360 projection from existing source-of-truth domains.

    Lifecycle order/labels are tenant configuration. Evidence is queried from the
    owning domain tables only when the current user can read that domain. No CRM,
    design, estimate, procurement or finance shadow record is created here.
    """
    lifecycle = _published_lifecycle(company)
    if lifecycle is None:
        return {
            "configured": False,
            "project": _project_identity(project),
            "message": "Project360 lifecycle is not published for this company.",
            "steps": [],
            "next_actions": [],
        }

    design_available = "design.dashboard.read" in permission_codes
    estimation_available = "estimation.dashboard.read" in permission_codes
    portal_available = bool(
        {"portal.dashboard.read", "portal.grant.read", "portal.share.read"}
        & permission_codes
    )
    procurement_available = "procurement.dashboard.read" in permission_codes
    finance_available = "finance.dashboard.read" in permission_codes
    handover_available = bool(
        {"digitaltwin.view", "digitaltwin.handover"} & permission_codes
    )

    document_count = approved_design_count = open_design_issues = 0
    latest_revision: str | None = None
    if design_available:
        documents = DesignDocument.objects.filter(
            company=company, project=project, archived_at__isnull=True
        )
        document_count = documents.count()
        versions = DesignVersion.objects.filter(company=company, document__project=project)
        approved_design_count = versions.filter(approved_at__isnull=False).count()
        latest_design = versions.order_by("-created_at").first()
        latest_revision = latest_design.revision_code if latest_design else None
        open_design_issues = DesignIssue.objects.filter(
            company=company, project=project, closed_at__isnull=True
        ).count()

    estimate_count = baseline_count = 0
    latest_estimate_value = "0"
    baseline_version_ids: list[Any] = []
    if estimation_available:
        estimates = Estimate.objects.filter(
            company=company, project=project, archived_at__isnull=True
        )
        estimate_count = estimates.count()
        estimate_versions = EstimateVersion.objects.filter(
            company=company, estimate__project=project
        )
        baselines = EstimateBaseline.objects.filter(
            company=company, estimate__project=project
        ).select_related("estimate_version")
        baseline_count = baselines.count()
        baseline_version_ids = list(
            baselines.values_list("estimate_version__public_id", flat=True)
        )
        latest_estimate_version = estimate_versions.order_by("-created_at").first()
        if latest_estimate_version is not None:
            latest_estimate_value = str(latest_estimate_version.grand_total)

    client_share_count = 0
    if portal_available and baseline_version_ids:
        now = timezone.now()
        client_share_count = (
            PortalShare.objects.filter(
                company=company,
                revoked_at__isnull=True,
                entity_type__in=["estimate_version", "estimation.version"],
                entity_public_id__in=baseline_version_ids,
            )
            .filter(models.Q(expires_at__isnull=True) | models.Q(expires_at__gt=now))
            .count()
        )

    # Project-owned planning/execution evidence is available with project dashboard read.
    wbs_count = WbsNode.objects.filter(company=company, project=project).count()
    tasks = ProjectTask.objects.select_related("stage").filter(company=company, project=project)
    task_count = tasks.count()
    completed_tasks = tasks.filter(stage__outcome=DeliveryStage.Outcome.COMPLETE).count()
    overdue_tasks = (
        tasks.filter(planned_end_date__lt=timezone.localdate())
        .exclude(
            stage__outcome__in=[
                DeliveryStage.Outcome.COMPLETE,
                DeliveryStage.Outcome.CANCELLED,
            ]
        )
        .count()
    )
    task_total_progress = tasks.aggregate(total=Sum("progress_percent"))["total"] or 0
    task_progress = int(task_total_progress / task_count) if task_count else 0

    pr_count = po_count = receipt_count = 0
    if procurement_available:
        requests = PurchaseRequest.objects.filter(company=company, project=project)
        pr_count = requests.count()
        po_count = PurchaseOrder.objects.filter(
            company=company, purchase_request__project=project
        ).count()
        receipt_count = GoodsReceipt.objects.filter(
            company=company,
            purchase_order__purchase_request__project=project,
        ).count()

    finance: dict[str, Any] = {"available": False}
    billing_count = 0
    if finance_available:
        client_invoices = Invoice.objects.filter(
            company=company,
            project=project,
            invoice_type=Invoice.InvoiceType.CLIENT,
            reversed_at__isnull=True,
        )
        billing_count = client_invoices.count()
        invoice_totals = client_invoices.aggregate(
            total=Sum("total_amount"), outstanding=Sum("outstanding_amount")
        )
        payments_total = (
            Payment.objects.filter(
                company=company,
                invoice__project=project,
                invoice__invoice_type=Invoice.InvoiceType.CLIENT,
                reversed_at__isnull=True,
            ).aggregate(total=Sum("amount"))["total"]
            or Decimal("0")
        )
        latest_budget = (
            ProjectBudget.objects.filter(company=company, project=project)
            .order_by("-created_at")
            .first()
        )
        approved_variations = (
            Variation.objects.filter(
                company=company,
                project=project,
                approved_at__isnull=False,
            ).aggregate(total=Sum("total_amount"))["total"]
            or Decimal("0")
        )
        cost = BudgetLine.objects.filter(
            company=company, budget__project=project
        ).aggregate(
            committed=Sum("committed_amount"),
            actual=Sum("actual_amount"),
            forecast=Sum("forecast_amount"),
        )
        contract_value = Decimal(project.approved_budget or 0) + approved_variations
        forecast_cost = cost["forecast"] or Decimal("0")
        margin = contract_value - forecast_cost
        margin_percent = (
            margin / contract_value * Decimal("100")
            if contract_value
            else Decimal("0")
        )
        finance = {
            "available": True,
            "currency": project.currency,
            "contract_value": str(contract_value),
            "approved_variations": str(approved_variations),
            "certified_or_invoiced": str(invoice_totals["total"] or Decimal("0")),
            "received": str(payments_total),
            "outstanding": str(
                invoice_totals["outstanding"] or Decimal("0")
            ),
            "approved_budget": str(
                latest_budget.approved_total
                if latest_budget
                else project.approved_budget
            ),
            "committed_cost": str(cost["committed"] or Decimal("0")),
            "actual_cost": str(cost["actual"] or Decimal("0")),
            "forecast_cost": str(forecast_cost),
            "forecast_margin": str(margin),
            "forecast_margin_percent": str(
                margin_percent.quantize(Decimal("0.1"))
            ),
        }

    handover_count = 0
    if handover_available:
        handover_count = HandoverAssetRecord.objects.filter(
            company=company, project_public_id=project.public_id
        ).count()

    crm_complete = bool(project.customer_public_id and project.opportunity_public_id)
    precon_complete = bool(
        project.baselined_at
        or project.actual_start_date
        or project.stage.outcome
        in {
            DeliveryStage.Outcome.APPROVED,
            DeliveryStage.Outcome.ISSUED,
            DeliveryStage.Outcome.COMPLETE,
        }
    )
    design_complete = (
        design_available
        and document_count > 0
        and approved_design_count > 0
        and open_design_issues == 0
    )
    estimate_complete = estimation_available and baseline_count > 0
    client_complete = portal_available and client_share_count > 0
    planning_complete = project.baseline_version > 0 and wbs_count > 0
    procurement_complete = (
        procurement_available and po_count > 0 and receipt_count > 0
    )
    execution_complete = task_count > 0 and completed_tasks == task_count
    billing_complete = (
        finance_available
        and billing_count > 0
        and Decimal(str(finance.get("outstanding", "0"))) == 0
    )
    handover_complete = (
        handover_available and handover_count > 0 and execution_complete
    )

    evidence_by_code: dict[str, dict[str, Any]] = {
        "CRM": {
            "customer_linked": bool(project.customer_public_id),
            "opportunity_linked": bool(project.opportunity_public_id),
        },
        "PRECONSTRUCTION": {
            "project_stage": project.stage.name,
            "project_stage_code": project.stage.code,
            "baseline_version": project.baseline_version,
        },
        "DESIGN": (
            {
                "available": True,
                "documents": document_count,
                "approved_versions": approved_design_count,
                "open_issues": open_design_issues,
                "latest_revision": latest_revision,
            }
            if design_available
            else {"available": False}
        ),
        "ESTIMATION": (
            {
                "available": True,
                "estimates": estimate_count,
                "baselines": baseline_count,
                "latest_value": latest_estimate_value,
            }
            if estimation_available
            else {"available": False}
        ),
        "CLIENT_APPROVAL": (
            {"available": True, "active_baselined_estimate_shares": client_share_count}
            if portal_available
            else {"available": False}
        ),
        "PLANNING": {
            "project_baseline_version": project.baseline_version,
            "wbs_nodes": wbs_count,
            "tasks": task_count,
        },
        "PROCUREMENT": (
            {
                "available": True,
                "requests": pr_count,
                "purchase_orders": po_count,
                "goods_receipts": receipt_count,
            }
            if procurement_available
            else {"available": False}
        ),
        "EXECUTION": {
            "tasks": task_count,
            "completed_tasks": completed_tasks,
            "overdue_tasks": overdue_tasks,
            "average_progress_percent": task_progress,
        },
        "BILLING": (
            {
                "available": True,
                "client_invoices": billing_count,
                "outstanding": finance.get("outstanding"),
            }
            if finance_available
            else {"available": False}
        ),
        "HANDOVER": (
            {"available": True, "handover_assets": handover_count}
            if handover_available
            else {"available": False}
        ),
    }

    restricted_by_code = {
        "CRM": False,
        "PRECONSTRUCTION": False,
        "DESIGN": not design_available,
        "ESTIMATION": not estimation_available,
        "CLIENT_APPROVAL": not portal_available,
        "PLANNING": False,
        "PROCUREMENT": not procurement_available,
        "EXECUTION": False,
        "BILLING": not finance_available,
        "HANDOVER": not handover_available,
    }
    complete_by_code = {
        "CRM": crm_complete,
        "PRECONSTRUCTION": precon_complete,
        "DESIGN": design_complete,
        "ESTIMATION": estimate_complete,
        "CLIENT_APPROVAL": client_complete,
        "PLANNING": planning_complete,
        "PROCUREMENT": procurement_complete,
        "EXECUTION": execution_complete,
        "BILLING": billing_complete,
        "HANDOVER": handover_complete,
    }
    count_by_code = {
        "CRM": int(bool(project.customer_public_id or project.opportunity_public_id)),
        "PRECONSTRUCTION": 1,
        "DESIGN": document_count,
        "ESTIMATION": estimate_count,
        "CLIENT_APPROVAL": client_share_count,
        "PLANNING": wbs_count + task_count + project.baseline_version,
        "PROCUREMENT": pr_count + po_count + receipt_count,
        "EXECUTION": task_count,
        "BILLING": billing_count,
        "HANDOVER": handover_count,
    }
    progress_by_code = {
        "CRM": 100 if crm_complete else (50 if count_by_code["CRM"] else 0),
        "PRECONSTRUCTION": 100 if precon_complete else 60,
        "DESIGN": 100 if design_complete else (
            min(90, 25 + approved_design_count * 20) if document_count else 0
        ),
        "ESTIMATION": 100 if estimate_complete else (60 if estimate_count else 0),
        "CLIENT_APPROVAL": 100 if client_complete else 0,
        "PLANNING": 100 if planning_complete else (
            60 if count_by_code["PLANNING"] else 0
        ),
        "PROCUREMENT": 100 if procurement_complete else (
            65 if po_count else (30 if pr_count else 0)
        ),
        "EXECUTION": 100 if execution_complete else task_progress,
        "BILLING": 100 if billing_complete else (60 if billing_count else 0),
        "HANDOVER": 100 if handover_complete else (50 if handover_count else 0),
    }

    project_id = str(project.public_id)
    workspace_by_code = {
        "CRM": "/crm",
        "PRECONSTRUCTION": "/delivery?tab=projects",
        "DESIGN": f"/project360/design?project={project_id}",
        "ESTIMATION": "/delivery?tab=estimation",
        "CLIENT_APPROVAL": "/delivery?tab=portal",
        "PLANNING": "/delivery?tab=projects",
        "PROCUREMENT": f"/project360/procurement?project={project_id}",
        "EXECUTION": f"/project360/site?project={project_id}",
        "BILLING": "/finance",
        "HANDOVER": f"/project360/handover?project={project_id}",
    }
    actions = {
        "CRM": {"label": "Complete customer & opportunity context", "href": workspace_by_code["CRM"]},
        "PRECONSTRUCTION": {"label": "Complete project setup", "href": workspace_by_code["PRECONSTRUCTION"]},
        "DESIGN": {"label": "Open visual design board", "href": workspace_by_code["DESIGN"]},
        "ESTIMATION": {"label": "Prepare / baseline estimate", "href": workspace_by_code["ESTIMATION"]},
        "CLIENT_APPROVAL": {"label": "Share approved information", "href": workspace_by_code["CLIENT_APPROVAL"]},
        "PLANNING": {"label": "Build WBS & project baseline", "href": workspace_by_code["PLANNING"]},
        "PROCUREMENT": {"label": "Open visual procurement flow", "href": workspace_by_code["PROCUREMENT"]},
        "EXECUTION": {"label": "Open site pulse", "href": workspace_by_code["EXECUTION"]},
        "BILLING": {"label": "Open finance & collections", "href": workspace_by_code["BILLING"]},
        "HANDOVER": {"label": "Open handover readiness", "href": workspace_by_code["HANDOVER"]},
    }

    checkpoints_by_code: dict[str, list[dict[str, Any]]] = {
        "CRM": [
            {"label": "Customer linked", "status": "DONE" if project.customer_public_id else "PENDING"},
            {"label": "Opportunity linked", "status": "DONE" if project.opportunity_public_id else "PENDING"},
        ],
        "PRECONSTRUCTION": [
            {"label": "Project created", "status": "DONE"},
            {"label": "Project baseline", "status": "DONE" if project.baseline_version > 0 else "PENDING"},
            {"label": "Mobilization / approved stage", "status": "DONE" if precon_complete else "ACTIVE"},
        ],
        "DESIGN": (
            [
                {"label": "Design documents", "status": "DONE" if document_count else "PENDING", "value": document_count},
                {"label": "Approved revisions", "status": "DONE" if approved_design_count else ("ACTIVE" if document_count else "PENDING"), "value": approved_design_count},
                {"label": "Open design issues", "status": "ATTENTION" if open_design_issues else ("DONE" if document_count else "PENDING"), "value": open_design_issues},
            ]
            if design_available
            else []
        ),
        "ESTIMATION": (
            [
                {"label": "Estimate prepared", "status": "DONE" if estimate_count else "PENDING", "value": estimate_count},
                {"label": "Approved baseline", "status": "DONE" if baseline_count else ("ACTIVE" if estimate_count else "PENDING"), "value": baseline_count},
            ]
            if estimation_available
            else []
        ),
        "CLIENT_APPROVAL": (
            [
                {"label": "Baselined estimate shared", "status": "DONE" if client_share_count else "PENDING", "value": client_share_count},
            ]
            if portal_available
            else []
        ),
        "PLANNING": [
            {"label": "Project baseline", "status": "DONE" if project.baseline_version > 0 else "PENDING"},
            {"label": "WBS created", "status": "DONE" if wbs_count else "PENDING", "value": wbs_count},
            {"label": "Tasks planned", "status": "DONE" if task_count else "PENDING", "value": task_count},
        ],
        "PROCUREMENT": (
            [
                {"label": "Purchase requests", "status": "DONE" if pr_count else "PENDING", "value": pr_count},
                {"label": "Purchase orders", "status": "DONE" if po_count else ("ACTIVE" if pr_count else "PENDING"), "value": po_count},
                {"label": "Goods received", "status": "DONE" if receipt_count else ("ACTIVE" if po_count else "PENDING"), "value": receipt_count},
            ]
            if procurement_available
            else []
        ),
        "EXECUTION": [
            {"label": "Execution tasks", "status": "DONE" if task_count else "PENDING", "value": task_count},
            {"label": "Completed tasks", "status": "DONE" if execution_complete else ("ACTIVE" if completed_tasks else "PENDING"), "value": completed_tasks},
            {"label": "Overdue tasks", "status": "ATTENTION" if overdue_tasks else ("DONE" if task_count else "PENDING"), "value": overdue_tasks},
        ],
        "BILLING": (
            [
                {"label": "Client invoices", "status": "DONE" if billing_count else "PENDING", "value": billing_count},
                {"label": "Collections complete", "status": "DONE" if billing_complete else ("ACTIVE" if billing_count else "PENDING")},
            ]
            if finance_available
            else []
        ),
        "HANDOVER": (
            [
                {"label": "Execution complete", "status": "DONE" if execution_complete else "PENDING"},
                {"label": "Handover evidence", "status": "DONE" if handover_count else ("ACTIVE" if execution_complete else "PENDING"), "value": handover_count},
            ]
            if handover_available
            else []
        ),
    }

    configured_steps = (
        lifecycle.payload.get("steps", [])
        if isinstance(lifecycle.payload, dict)
        else []
    )
    steps: list[dict[str, Any]] = []
    next_actions: list[dict[str, str]] = []
    previous_complete = True
    for configured in configured_steps:
        code = str(configured.get("code", "")).upper()
        if code not in evidence_by_code:
            continue
        restricted = restricted_by_code[code]
        complete = bool(complete_by_code[code])
        blocked = not previous_complete and count_by_code[code] == 0
        status = (
            "RESTRICTED"
            if restricted
            else _status(count_by_code[code], complete, blocked=blocked)
        )
        action = None if complete or restricted else actions.get(code)
        item = _step(
            code,
            str(configured.get("label") or code.replace("_", " ").title()),
            str(configured.get("description") or ""),
            status,
            0 if restricted else progress_by_code[code],
            evidence_by_code[code],
            action=action,
            workspace_href=workspace_by_code.get(code),
            checkpoints=[] if restricted else checkpoints_by_code.get(code, []),
        )
        steps.append(item)
        if action and len(next_actions) < 4:
            next_actions.append({"step_code": code, **action})
        if not restricted:
            previous_complete = previous_complete and complete

    visible_steps = [step for step in steps if step["status"] != "RESTRICTED"]
    overall = (
        int(
            sum(int(item["progress_percent"]) for item in visible_steps)
            / len(visible_steps)
        )
        if visible_steps
        else 0
    )
    current = next(
        (
            item
            for item in steps
            if item["status"] not in {"COMPLETE", "RESTRICTED"}
        ),
        visible_steps[-1] if visible_steps else None,
    )

    return {
        "configured": True,
        "configuration_version": lifecycle.version,
        "project": _project_identity(project),
        "overall_progress_percent": overall,
        "current_step": current,
        "steps": steps,
        "next_actions": next_actions,
        "health": {
            "overdue_tasks": overdue_tasks,
            "open_design_issues": open_design_issues if design_available else None,
            "status": (
                "ATTENTION"
                if overdue_tasks or (design_available and open_design_issues)
                else "ON_TRACK"
            ),
        },
        "finance": finance,
    }
