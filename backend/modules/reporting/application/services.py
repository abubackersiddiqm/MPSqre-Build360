
from __future__ import annotations

import csv
import hashlib
import io
import uuid
import zipfile
from collections.abc import Callable
from datetime import timedelta
from decimal import Decimal
from typing import Any

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from modules.crm.models import Lead, Opportunity
from modules.finance.models import Invoice, ProjectBudget
from modules.inventory.models import InventoryItem
from modules.notifications.models import Notification
from modules.platform.actors import RequestActor
from modules.platform.audit import AuditRecord, append_audit
from modules.platform.events import EventRecord, append_event
from modules.procurement.models import PurchaseOrder
from modules.projects.models import Project, ProjectTask
from modules.reporting.models import ExportArtifact, MetricDefinition, ReportRun, SavedReport
from modules.safety.models import SafetyIncident
from modules.tenant.models import Company
from modules.vendor.models import VendorProfile


def _decimal(value: Decimal | None) -> str:
    return str(value or Decimal("0"))


def _metric_calculators(company: Company, user_public_id: uuid.UUID) -> dict[str, Callable[[], object]]:
    today = timezone.localdate()
    return {
        "crm.leads.total": lambda: Lead.objects.filter(company=company).count(),
        "crm.opportunities.open": lambda: Opportunity.objects.filter(
            company=company,
            won_at__isnull=True,
            lost_at__isnull=True,
        ).count(),
        "projects.active": lambda: Project.objects.filter(
            company=company,
            archived_at__isnull=True,
        ).count(),
        "projects.tasks.overdue": lambda: ProjectTask.objects.filter(
            company=company,
            planned_end_date__lt=today,
            progress_percent__lt=100,
        ).count(),
        "supply.vendors.active": lambda: VendorProfile.objects.filter(
            company=company,
            retired_at__isnull=True,
        ).count(),
        "procurement.purchase_orders": lambda: PurchaseOrder.objects.filter(company=company).count(),
        "inventory.items": lambda: InventoryItem.objects.filter(company=company).count(),
        "safety.incidents.open": lambda: SafetyIncident.objects.filter(
            company=company,
        ).exclude(stage__outcome__in=["complete", "cancelled"]).count(),
        "finance.approved_budget": lambda: _decimal(
            ProjectBudget.objects.filter(company=company).aggregate(total=Sum("approved_total"))["total"]
        ),
        "finance.invoice.outstanding": lambda: _decimal(
            Invoice.objects.filter(company=company).aggregate(total=Sum("outstanding_amount"))["total"]
        ),
        "notifications.unread": lambda: Notification.objects.filter(
            company=company,
            user_public_id=user_public_id,
            read_at__isnull=True,
        ).count(),
    }


def calculate_metric(
    *,
    company: Company,
    metric: MetricDefinition,
    user_public_id: uuid.UUID,
) -> object:
    calculator = _metric_calculators(company, user_public_id).get(metric.calculation_code)
    if calculator is None:
        raise ValidationError(f"Unsupported metric calculation: {metric.calculation_code}")
    return calculator()


def _record(
    *,
    company: Company,
    actor: RequestActor,
    action: str,
    entity_type: str,
    entity_public_id: uuid.UUID,
    version: int,
    payload: dict[str, Any],
) -> None:
    append_audit(
        AuditRecord(
            action=action,
            entity_type=entity_type,
            entity_public_id=entity_public_id,
            actor_public_id=actor.user_public_id,
            company_public_id=company.public_id,
            request_id=actor.request_id,
            correlation_id=actor.request_id,
            ip_address=actor.ip_address,
            user_agent=actor.user_agent,
            after=payload,
        )
    )
    append_event(
        EventRecord(
            event_type=action,
            aggregate_type=entity_type,
            aggregate_public_id=entity_public_id,
            aggregate_version=version,
            company_public_id=company.public_id,
            correlation_id=actor.request_id,
            payload=payload,
        )
    )


def reporting_summary(company: Company) -> dict[str, int]:
    return {
        "active_metrics": MetricDefinition.objects.filter(company=company, is_active=True).count(),
        "saved_reports": SavedReport.objects.filter(company=company, is_active=True).count(),
        "queued_runs": ReportRun.objects.filter(
            company=company,
            status__in=[ReportRun.Status.QUEUED, ReportRun.Status.RUNNING],
        ).count(),
        "completed_runs": ReportRun.objects.filter(
            company=company,
            status=ReportRun.Status.COMPLETED,
        ).count(),
        "failed_runs": ReportRun.objects.filter(
            company=company,
            status=ReportRun.Status.FAILED,
        ).count(),
    }


@transaction.atomic
def create_metric(
    *,
    company: Company,
    actor: RequestActor,
    code: str,
    name: str,
    domain_code: str,
    calculation_code: str,
    unit_code: str = "count",
    description: str = "",
    data_classification: str = "internal",
) -> MetricDefinition:
    known = _metric_calculators(company, actor.user_public_id)
    normalized_calc = calculation_code.strip().lower()
    if normalized_calc not in known:
        raise ValidationError("The requested metric calculation is not supported")
    metric = MetricDefinition(
        company=company,
        code=code.strip().upper(),
        name=name.strip(),
        description=description.strip(),
        domain_code=domain_code.strip().lower(),
        calculation_code=normalized_calc,
        unit_code=unit_code.strip().lower(),
        data_classification=data_classification,
    )
    metric.full_clean()
    metric.save()
    _record(
        company=company,
        actor=actor,
        action="reporting.metric.created",
        entity_type="metric_definition",
        entity_public_id=metric.public_id,
        version=metric.version,
        payload={"code": metric.code, "calculation_code": metric.calculation_code},
    )
    return metric


@transaction.atomic
def create_saved_report(
    *,
    company: Company,
    actor: RequestActor,
    code: str,
    name: str,
    report_type: str,
    metric_codes: list[str],
    description: str = "",
    filters: dict[str, Any] | None = None,
    columns: list[str] | None = None,
    visibility: str = SavedReport.Visibility.PRIVATE,
    role_public_ids: list[str] | None = None,
    default_export_format: str = SavedReport.ExportFormat.CSV,
    schedule_expression: str = "",
) -> SavedReport:
    normalized_metrics = [item.strip().upper() for item in metric_codes if item.strip()]
    if not normalized_metrics:
        raise ValidationError("At least one metric is required")
    existing = set(
        MetricDefinition.objects.filter(
            company=company,
            code__in=normalized_metrics,
            is_active=True,
        ).values_list("code", flat=True)
    )
    missing = sorted(set(normalized_metrics) - existing)
    if missing:
        raise ValidationError({"metric_codes": [f"Unknown metrics: {', '.join(missing)}"]})
    report = SavedReport(
        company=company,
        code=code.strip().upper(),
        name=name.strip(),
        description=description.strip(),
        report_type=report_type.strip().lower(),
        metric_codes=normalized_metrics,
        filters=filters or {},
        columns=columns or [],
        visibility=visibility,
        role_public_ids=[str(item) for item in (role_public_ids or [])],
        owner_user_public_id=actor.user_public_id,
        default_export_format=default_export_format,
        schedule_expression=schedule_expression.strip(),
    )
    report.full_clean()
    report.save()
    _record(
        company=company,
        actor=actor,
        action="reporting.saved_report.created",
        entity_type="saved_report",
        entity_public_id=report.public_id,
        version=report.version,
        payload={"code": report.code, "metrics": report.metric_codes},
    )
    return report


def _metric_rows(run: ReportRun) -> list[dict[str, str]]:
    snapshot = run.metric_snapshot if isinstance(run.metric_snapshot, dict) else {}
    items = snapshot.get("items", [])
    if not isinstance(items, list):
        return []
    rows: list[dict[str, str]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        rows.append(
            {
                "code": str(item.get("code", "")),
                "name": str(item.get("name", "")),
                "value": str(item.get("value", "")),
                "unit": str(item.get("unit", "")),
                "classification": str(item.get("classification", "")),
            }
        )
    return rows


def _csv_bytes(rows: list[dict[str, str]]) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(
        stream,
        fieldnames=["code", "name", "value", "unit", "classification"],
    )
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode("utf-8-sig")


def _xlsx_bytes(rows: list[dict[str, str]]) -> bytes:
    values = [["Code", "Name", "Value", "Unit", "Classification"]]
    values.extend(
        [[row["code"], row["name"], row["value"], row["unit"], row["classification"]] for row in rows]
    )

    def cell(column: int, row_number: int, value: str) -> str:
        letters = ""
        number = column
        while number:
            number, remainder = divmod(number - 1, 26)
            letters = chr(65 + remainder) + letters
        escaped = (
            value.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
        )
        return f'<c r="{letters}{row_number}" t="inlineStr"><is><t>{escaped}</t></is></c>'

    sheet_rows = []
    for row_number, row in enumerate(values, start=1):
        cells = "".join(cell(index, row_number, str(value)) for index, value in enumerate(row, start=1))
        sheet_rows.append(f'<row r="{row_number}">{cells}</row>')
    sheet = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f'<sheetData>{"".join(sheet_rows)}</sheetData></worksheet>'
    )
    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        '</Types>'
    )
    relationships = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
        '</Relationships>'
    )
    workbook = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        '<sheets><sheet name="Build360 Metrics" sheetId="1" r:id="rId1"/></sheets></workbook>'
    )
    workbook_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
        '</Relationships>'
    )
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("_rels/.rels", relationships)
        archive.writestr("xl/workbook.xml", workbook)
        archive.writestr("xl/_rels/workbook.xml.rels", workbook_rels)
        archive.writestr("xl/worksheets/sheet1.xml", sheet)
    return output.getvalue()


def _pdf_bytes(rows: list[dict[str, str]]) -> bytes:
    lines = ["MPSqre Build360 Metric Report"]
    lines.extend(f"{row['name']}: {row['value']} {row['unit']}" for row in rows)
    text_parts = ["BT /F1 12 Tf 50 790 Td"]
    for index, line in enumerate(lines[:42]):
        escaped = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        if index:
            text_parts.append("0 -18 Td")
        text_parts.append(f"({escaped}) Tj")
    text_parts.append("ET")
    stream = "\n".join(text_parts).encode("latin-1", "replace")
    objects = [
        b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n",
        b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n",
        b"3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >> endobj\n",
        f"4 0 obj << /Length {len(stream)} >> stream\n".encode() + stream + b"\nendstream endobj\n",
        b"5 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj\n",
    ]
    output = io.BytesIO()
    output.write(b"%PDF-1.4\n")
    offsets = [0]
    for obj in objects:
        offsets.append(output.tell())
        output.write(obj)
    xref = output.tell()
    output.write(f"xref\n0 {len(objects) + 1}\n".encode())
    output.write(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        output.write(f"{offset:010d} 00000 n \n".encode())
    output.write(
        f"trailer << /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    )
    return output.getvalue()


def render_artifact(run: ReportRun) -> tuple[bytes, str, str]:
    rows = _metric_rows(run)
    if run.export_format == SavedReport.ExportFormat.CSV:
        return _csv_bytes(rows), "text/csv; charset=utf-8", "csv"
    if run.export_format == SavedReport.ExportFormat.XLSX:
        return (
            _xlsx_bytes(rows),
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "xlsx",
        )
    if run.export_format == SavedReport.ExportFormat.PDF:
        return _pdf_bytes(rows), "application/pdf", "pdf"
    raise ValidationError("Unsupported export format")


@transaction.atomic
def create_and_execute_run(
    *,
    company: Company,
    actor: RequestActor,
    idempotency_key: str,
    saved_report_public_id: uuid.UUID | None = None,
    metric_codes: list[str] | None = None,
    export_format: str | None = None,
    parameters: dict[str, Any] | None = None,
) -> ReportRun:
    existing = ReportRun.objects.filter(company=company, idempotency_key=idempotency_key).first()
    if existing is not None:
        return existing
    saved_report = None
    report_code = "AD_HOC"
    selected_codes = [item.strip().upper() for item in (metric_codes or []) if item.strip()]
    selected_format = export_format or SavedReport.ExportFormat.CSV
    if saved_report_public_id:
        saved_report = SavedReport.objects.filter(
            company=company,
            public_id=saved_report_public_id,
            is_active=True,
        ).first()
        if saved_report is None:
            raise ValidationError("Saved report was not found")
        report_code = saved_report.code
        selected_codes = saved_report.metric_codes
        selected_format = export_format or saved_report.default_export_format
    if not selected_codes:
        raise ValidationError("At least one metric is required")
    metrics = list(
        MetricDefinition.objects.filter(
            company=company,
            code__in=selected_codes,
            is_active=True,
        ).order_by("domain_code", "name")
    )
    if len(metrics) != len(set(selected_codes)):
        raise ValidationError("One or more metrics are unavailable")
    run = ReportRun.objects.create(
        company=company,
        saved_report=saved_report,
        report_code=report_code,
        requested_by_public_id=actor.user_public_id,
        idempotency_key=idempotency_key.strip(),
        status=ReportRun.Status.RUNNING,
        export_format=selected_format,
        parameters=parameters or {},
        started_at=timezone.now(),
    )
    try:
        items = [
            {
                "code": metric.code,
                "name": metric.name,
                "value": calculate_metric(
                    company=company,
                    metric=metric,
                    user_public_id=actor.user_public_id,
                ),
                "unit": metric.unit_code,
                "classification": metric.data_classification,
            }
            for metric in metrics
        ]
        run.metric_snapshot = {
            "generated_at": timezone.now().isoformat(),
            "company": {"code": company.code, "name": company.display_name},
            "items": items,
        }
        run.row_count = len(items)
        run.status = ReportRun.Status.COMPLETED
        run.completed_at = timezone.now()
        run.expires_at = timezone.now() + timedelta(days=7)
        run.version += 1
        run.full_clean()
        run.save()
        content, content_type, extension = render_artifact(run)
        ExportArtifact.objects.create(
            company=company,
            run=run,
            file_name=f"{report_code.lower()}-{run.public_id}.{extension}",
            content_type=content_type,
            sha256=hashlib.sha256(content).hexdigest(),
            byte_size=len(content),
            data_classification=max(
                (metric.data_classification for metric in metrics),
                default="internal",
                key=lambda value: {"internal": 1, "confidential": 2, "restricted": 3}.get(value, 0),
            ),
            created_by_public_id=actor.user_public_id,
            expires_at=run.expires_at,
        )
    except Exception as exc:
        run.status = ReportRun.Status.FAILED
        run.error_message = str(exc)[:1000]
        run.completed_at = timezone.now()
        run.version += 1
        run.save(update_fields=["status", "error_message", "completed_at", "version", "updated_at"])
        raise
    _record(
        company=company,
        actor=actor,
        action="reporting.run.completed",
        entity_type="report_run",
        entity_public_id=run.public_id,
        version=run.version,
        payload={"report_code": run.report_code, "row_count": run.row_count, "format": run.export_format},
    )
    return run


@transaction.atomic
def mark_artifact_downloaded(*, company: Company, run_public_id: uuid.UUID) -> tuple[ReportRun, bytes, str, str]:
    run = (
        ReportRun.objects.select_for_update()
        .select_related("artifact")
        .filter(company=company, public_id=run_public_id, status=ReportRun.Status.COMPLETED)
        .first()
    )
    if run is None or not hasattr(run, "artifact"):
        raise ValidationError("Report export was not found")
    if run.expires_at and run.expires_at <= timezone.now():
        raise ValidationError("Report export has expired")
    content, content_type, extension = render_artifact(run)
    digest = hashlib.sha256(content).hexdigest()
    if digest != run.artifact.sha256:
        raise ValidationError("Report export integrity check failed")
    run.artifact.download_count += 1
    run.artifact.last_downloaded_at = timezone.now()
    run.artifact.save(update_fields=["download_count", "last_downloaded_at", "updated_at"])
    return run, content, content_type, extension
