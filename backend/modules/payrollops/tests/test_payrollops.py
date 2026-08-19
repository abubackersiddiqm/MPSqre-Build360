import uuid
from datetime import date, timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from modules.employee.models import Employee
from modules.identity.application.tokens import AccessPrincipal
from modules.identity.models import (
    AuthSession,
    Permission,
    Role,
    RolePermission,
    User,
)
from modules.payrollops.application.selectors import payroll_overview
from modules.payrollops.application.services import (
    RequestEvidence,
    create_run,
    decide_approval,
    request_approval,
    transition_run,
    upsert_run_lines,
)
from modules.payrollops.models import (
    PayrollException,
    PayrollPeriod,
    PayrollPolicyVersion,
    PayrollRun,
    PayrollRunLine,
)
from modules.tenant.application.context import TenantContext
from modules.tenant.models import Company, Membership, MembershipRole


class PayrollOperationsTests(TestCase):
    def company(self, code: str) -> Company:
        return Company.objects.create(
            code=code,
            legal_name=f"{code} Legal",
            display_name=code,
            locale="en-IN",
            timezone="Asia/Kolkata",
            currency="INR",
            unit_system_code="metric",
            fiscal_year_start_month=4,
        )

    def actor(
        self,
        company: Company,
        suffix: str,
        permissions: set[str],
    ) -> tuple[TenantContext, Employee]:
        user = User.objects.create_user(
            email=f"{suffix.lower()}@example.test",
            password="A-secure-test-password-123",
            display_name=suffix,
        )
        membership = Membership.objects.create(
            company=company,
            user=user,
            effective_from=timezone.now() - timedelta(days=1),
        )
        employee = Employee.objects.create(
            company=company,
            membership=membership,
            employee_number=f"EMP-{suffix}",
            job_title="Payroll test employee",
            employment_start=date(2026, 1, 1),
        )
        now = timezone.now()
        session = AuthSession.objects.create(
            user=user,
            device_id=uuid.uuid4(),
            device_name="Payroll test device",
            user_agent="payrollops-tests",
            expires_at=now + timedelta(days=1),
        )
        role = Role.objects.create(
            company_public_id=company.public_id,
            code=f"payroll_test_{suffix.lower()}",
            name=f"Payroll test role {suffix}",
            version=1,
            effective_from=now - timedelta(minutes=1),
        )
        for permission_code in permissions:
            permission, _ = Permission.objects.get_or_create(
                code=permission_code,
                defaults={
                    "description": f"Test permission {permission_code}",
                    "data_class": "payroll_restricted",
                },
            )
            RolePermission.objects.create(role=role, permission=permission)
        MembershipRole.objects.create(
            membership=membership,
            role_public_id=role.public_id,
            assigned_by_public_id=user.public_id,
            effective_from=now - timedelta(minutes=1),
        )
        return (
            TenantContext(
                company=company,
                membership=membership,
                principal=AccessPrincipal(
                    user=user,
                    session=session,
                    assurance_at=None,
                ),
            ),
            employee,
        )

    def evidence(self) -> RequestEvidence:
        request_id = uuid.uuid4()
        return RequestEvidence(
            request_id=request_id,
            correlation_id=request_id,
            ip_address="127.0.0.1",
            user_agent="payrollops-tests",
        )

    def policy(
        self,
        company: Company,
        code: str = "PAY",
        configuration: dict[str, object] | None = None,
    ) -> PayrollPolicyVersion:
        now = timezone.now()
        return PayrollPolicyVersion.objects.create(
            company=company,
            code=code,
            name="Payroll policy",
            version=1,
            status_code="PUBLISHED",
            locale_code=company.locale,
            currency=company.currency,
            effective_from=now - timedelta(days=1),
            published_at=now,
            configuration=configuration
            or {
                "initial_run_status": "DRAFT",
                "immutable_statuses": ["LOCKED"],
                "transitions": [
                    {
                        "from": "DRAFT",
                        "to": "LOCKED",
                        "permission": "payroll.approve",
                    }
                ],
            },
        )

    def period(self, company: Company, code: str = "2026-08") -> PayrollPeriod:
        return PayrollPeriod.objects.create(
            company=company,
            code=code,
            starts_on=date(2026, 8, 1),
            ends_on=date(2026, 8, 31),
            payment_due_on=date(2026, 9, 5),
            status_code="OPEN",
        )

    def payroll_run(self, company: Company, code: str = "2026-08") -> PayrollRun:
        period = self.period(company, code)
        policy = self.policy(company, f"PAY-{code}")
        return PayrollRun.objects.create(
            company=company,
            period=period,
            policy=policy,
            run_number=1,
            run_type_code="REGULAR",
            status_code="DRAFT",
            currency=company.currency,
            initiated_by_public_id=company.public_id,
        )

    def test_policy_requires_configured_initial_status_and_transitions(self):
        company = self.company("AAA")
        policy = PayrollPolicyVersion(
            company=company,
            code="INVALID",
            name="Invalid",
            version=1,
            status_code="DRAFT",
            currency="INR",
            effective_from=timezone.now(),
            configuration={},
        )
        with self.assertRaises(ValidationError):
            policy.full_clean()

    def test_run_rejects_cross_company_period_and_policy(self):
        company_a = self.company("AAA")
        company_b = self.company("BBB")
        run = PayrollRun(
            company=company_a,
            period=self.period(company_b, "B-2026-08"),
            policy=self.policy(company_a),
            run_number=1,
            run_type_code="REGULAR",
            status_code="DRAFT",
            currency="INR",
            initiated_by_public_id=company_a.public_id,
        )
        with self.assertRaises(ValidationError):
            run.full_clean()

    def test_line_enforces_net_formula(self):
        company = self.company("AAA")
        run = self.payroll_run(company)
        line = PayrollRunLine(
            company=company,
            run=run,
            employee_public_id=company.public_id,
            currency="INR",
            gross_amount=Decimal("1000.00"),
            deduction_amount=Decimal("100.00"),
            employer_cost_amount=Decimal("1100.00"),
            net_amount=Decimal("950.00"),
            status_code="CALCULATED",
        )
        with self.assertRaises(ValidationError):
            line.full_clean()

    def test_overview_is_tenant_isolated(self):
        company_a = self.company("AAA")
        company_b = self.company("BBB")
        run_a = self.payroll_run(company_a, "A-2026-08")
        run_b = self.payroll_run(company_b, "B-2026-08")
        PayrollException.objects.create(
            company=company_b,
            run=run_b,
            exception_code="MISSING_INPUT",
            severity_code="HIGH",
            status_code="OPEN",
            message="Should never appear for company A",
        )
        overview = payroll_overview(company_a)
        self.assertEqual(overview["summary"]["run_count"], 1)
        self.assertEqual(overview["summary"]["open_exception_count"], 0)
        self.assertEqual(overview["latest_run"]["public_id"], str(run_a.public_id))
        self.assertNotEqual(overview["latest_run"]["public_id"], str(run_b.public_id))

    def test_run_lines_reject_employee_from_another_tenant(self):
        company_a = self.company("AAA")
        company_b = self.company("BBB")
        context_a, _ = self.actor(company_a, "A-MANAGER", {"payroll.manage"})
        _, employee_b = self.actor(company_b, "B-EMPLOYEE", set())
        policy = self.policy(company_a)
        period = self.period(company_a)
        run = create_run(
            context=context_a,
            evidence=self.evidence(),
            period_public_id=period.public_id,
            policy_public_id=policy.public_id,
            run_number=1,
            run_type_code="REGULAR",
        )
        with self.assertRaises(ValidationError):
            upsert_run_lines(
                context=context_a,
                evidence=self.evidence(),
                run_public_id=run.public_id,
                expected_version=run.version,
                lines=[
                    {
                        "employee_public_id": employee_b.public_id,
                        "gross_amount": "1000.00",
                        "deduction_amount": "100.00",
                        "employer_cost_amount": "1100.00",
                        "status_code": "CALCULATED",
                    }
                ],
            )

    def test_required_approval_and_assignment_gate_transition(self):
        company = self.company("AAA")
        manager_context, _ = self.actor(
            company,
            "MANAGER",
            {"payroll.manage", "payroll.approve"},
        )
        approver_context, _ = self.actor(
            company,
            "APPROVER",
            {"payroll.approve"},
        )
        policy = self.policy(
            company,
            configuration={
                "initial_run_status": "DRAFT",
                "immutable_statuses": ["LOCKED"],
                "approval_assignment_required": True,
                "approval_segregation_of_duties": True,
                "approval_decisions": {"APPROVE": "APPROVED"},
                "transitions": [
                    {
                        "from": "DRAFT",
                        "to": "APPROVED",
                        "permission": "payroll.approve",
                        "required_approvals": [
                            {
                                "step_code": "PAYROLL_APPROVAL",
                                "accepted_statuses": ["APPROVED"],
                            }
                        ],
                    }
                ],
            },
        )
        period = self.period(company)
        run = create_run(
            context=manager_context,
            evidence=self.evidence(),
            period_public_id=period.public_id,
            policy_public_id=policy.public_id,
            run_number=1,
            run_type_code="REGULAR",
        )
        with self.assertRaises(ValidationError):
            transition_run(
                context=approver_context,
                evidence=self.evidence(),
                run_public_id=run.public_id,
                expected_version=run.version,
                target_status_code="APPROVED",
                reason="",
            )

        approval = request_approval(
            context=manager_context,
            evidence=self.evidence(),
            run_public_id=run.public_id,
            step_code="PAYROLL_APPROVAL",
            status_code="PENDING",
            requested_from_membership_public_id=(
                approver_context.membership.public_id
            ),
        )
        decide_approval(
            context=approver_context,
            evidence=self.evidence(),
            approval_public_id=approval.public_id,
            decision_code="APPROVE",
            status_code="APPROVED",
            reason="Validated payroll control totals",
        )
        transitioned = transition_run(
            context=approver_context,
            evidence=self.evidence(),
            run_public_id=run.public_id,
            expected_version=run.version,
            target_status_code="APPROVED",
            reason="Approved through maker-checker",
        )
        self.assertEqual(transitioned.status_code, "APPROVED")
        self.assertEqual(transitioned.version, 2)

    def test_database_names_stay_within_portable_limit(self):
        from django.apps import apps

        for model in apps.get_app_config("payrollops").get_models():
            for constraint in model._meta.constraints:
                self.assertLessEqual(len(constraint.name), 30, constraint.name)
            for index in model._meta.indexes:
                self.assertLessEqual(len(index.name), 30, index.name)
