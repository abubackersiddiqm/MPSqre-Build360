from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from modules.employee.models import Employee
from modules.identity.models import Permission, Role, RolePermission, User
from modules.notifications.models import Notification
from modules.peopleops.models import (
    Department,
    EmploymentContract,
    LeaveBalance,
    LeavePolicy,
    PayrollEntry,
    PayrollRun,
    payroll_entry_digest,
)
from modules.tenant.models import Company, Membership

DEPARTMENTS = [
    ("EXEC", "Executive", "CORP-EXEC"),
    ("PROJECTS", "Project Delivery", "OPS-PROJ"),
    ("FINANCE", "Finance and Commercial", "CORP-FIN"),
    ("OPERATIONS", "Site and Field Operations", "OPS-FIELD"),
]

LEAVE_POLICIES = [
    ("ANNUAL", "Annual leave", LeavePolicy.LeaveType.ANNUAL, Decimal("18"), Decimal("6"), True),
    ("SICK", "Sick leave", LeavePolicy.LeaveType.SICK, Decimal("12"), Decimal("0"), True),
    ("CASUAL", "Casual leave", LeavePolicy.LeaveType.CASUAL, Decimal("6"), Decimal("0"), True),
]


class Command(BaseCommand):
    help = "Initialize Phase 20 people operations, leave, timesheets and payroll foundations."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--company-code", required=True)
        parser.add_argument("--admin-email", required=True)

    @transaction.atomic
    def handle(self, *args: object, **options: object) -> None:
        company = Company.objects.filter(
            code__iexact=str(options["company_code"]).strip(),
            is_active=True,
        ).first()
        user = User.objects.filter(
            email__iexact=str(options["admin_email"]).strip().lower(),
            is_active=True,
        ).first()
        if company is None or user is None:
            raise CommandError("Active company or administrator was not found")
        membership = Membership.objects.filter(
            company=company,
            user=user,
            suspended_at__isnull=True,
            terminated_at__isnull=True,
        ).first()
        if membership is None:
            raise CommandError("Administrator has no active company membership")

        today = timezone.localdate()
        employee, _ = Employee.objects.update_or_create(
            company=company,
            membership=membership,
            defaults={
                "employee_number": "EMP-0001",
                "job_title": "Build360 Administrator",
                "employment_start": today,
                "employment_end": None,
            },
        )
        employee.full_clean()
        employee.save()

        departments: dict[str, Department] = {}
        for code, name, cost_code in DEPARTMENTS:
            department, _ = Department.objects.update_or_create(
                company=company,
                code=code,
                defaults={
                    "name": name,
                    "cost_code": cost_code,
                    "status": Department.Status.ACTIVE,
                    "manager_employee": employee if code == "EXEC" else None,
                },
            )
            department.full_clean()
            department.save()
            departments[code] = department

        system_actor = uuid.UUID(int=0)
        contract, _ = EmploymentContract.objects.update_or_create(
            company=company,
            contract_number="EMP-0001-PRIMARY",
            defaults={
                "employee": employee,
                "department": departments["EXEC"],
                "position_title": "Build360 Administrator",
                "employment_type": EmploymentContract.EmploymentType.PERMANENT,
                "start_on": today,
                "end_on": None,
                "currency": company.currency,
                "annual_compensation": Decimal("0"),
                "pay_frequency": EmploymentContract.PayFrequency.MONTHLY,
                "status": EmploymentContract.Status.ACTIVE,
                "created_by_user_public_id": system_actor,
                "approved_by_user_public_id": user.public_id,
                "approved_at": timezone.now(),
            },
        )
        contract.full_clean()
        contract.save()

        policies: list[LeavePolicy] = []
        for code, name, leave_type, annual_days, carry_forward, requires_approval in LEAVE_POLICIES:
            policy, _ = LeavePolicy.objects.update_or_create(
                company=company,
                code=code,
                defaults={
                    "name": name,
                    "leave_type": leave_type,
                    "annual_days": annual_days,
                    "carry_forward_days": carry_forward,
                    "requires_approval": requires_approval,
                    "is_active": True,
                },
            )
            policy.full_clean()
            policy.save()
            policies.append(policy)
            balance, _ = LeaveBalance.objects.update_or_create(
                company=company,
                employee=employee,
                policy=policy,
                period_year=today.year,
                defaults={
                    "opening_days": Decimal("0"),
                    "accrued_days": annual_days,
                    "taken_days": Decimal("0"),
                    "adjustment_days": Decimal("0"),
                },
            )
            balance.full_clean()
            balance.save()

        month_start = date(today.year, today.month, 1)
        if today.month == 12:
            month_end = date(today.year, 12, 31)
        else:
            month_end = date(today.year, today.month + 1, 1) - timedelta(days=1)
        payroll, _ = PayrollRun.objects.update_or_create(
            company=company,
            code=f"PAY-{today:%Y-%m}",
            defaults={
                "period_start": month_start,
                "period_end": month_end,
                "currency": company.currency,
                "status": PayrollRun.Status.DRAFT,
                "gross_total": Decimal("0"),
                "deduction_total": Decimal("0"),
                "net_total": Decimal("0"),
                "created_by_user_public_id": user.public_id,
                "approved_by_user_public_id": None,
                "approved_at": None,
                "posted_at": None,
                "evidence_sha256": "",
            },
        )
        PayrollEntry.objects.get_or_create(
            company=company,
            payroll_run=payroll,
            employee=employee,
            defaults={
                "gross_amount": Decimal("0"),
                "deduction_amount": Decimal("0"),
                "net_amount": Decimal("0"),
                "components": {"base": "0.00", "statutory_calculation": "not_configured"},
                "evidence_sha256": payroll_entry_digest(
                    run_code=payroll.code,
                    employee_number=employee.employee_number,
                    gross=Decimal("0"),
                    deductions=Decimal("0"),
                ),
            },
        )

        permissions = list(Permission.objects.filter(code__startswith="people."))
        now = timezone.now()
        role_ids = membership.role_assignments.filter(effective_from__lte=now).filter(
            Q(effective_to__isnull=True) | Q(effective_to__gt=now)
        ).values_list("role_public_id", flat=True)
        roles = list(
            Role.objects.filter(
                company_public_id=company.public_id,
                public_id__in=role_ids,
                retired_at__isnull=True,
            )
        )
        grants = 0
        for role in roles:
            for permission in permissions:
                _, created = RolePermission.objects.get_or_create(role=role, permission=permission)
                grants += int(created)

        Notification.objects.get_or_create(
            company=company,
            user_public_id=user.public_id,
            event_code="system.phase20.ready",
            defaults={
                "title": "Phase 20 people operations is active",
                "body": "Employee administration, leave, timesheet and payroll controls are ready.",
                "severity": Notification.Severity.SUCCESS,
                "action_path": "/people-operations",
                "source_type": "phase20_bootstrap",
            },
        )

        self.stdout.write(self.style.SUCCESS("PHASE 20 PEOPLE OPERATIONS INITIALIZATION COMPLETED"))
        self.stdout.write(f"Employees available: {Employee.objects.filter(company=company).count()}")
        self.stdout.write(f"Departments available: {Department.objects.filter(company=company).count()}")
        self.stdout.write(f"Leave policies available: {len(policies)}")
        self.stdout.write(f"Payroll runs available: {PayrollRun.objects.filter(company=company).count()}")
        self.stdout.write(f"Phase 20 permissions available: {len(permissions)}")
        self.stdout.write(f"New role grants: {grants}")
