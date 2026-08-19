import uuid
from datetime import date, timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from modules.employee.models import Employee
from modules.identity.application.tokens import AccessPrincipal
from modules.identity.models import AuthSession, Permission, Role, RolePermission, User
from modules.platform.models import BusinessEventOutbox
from modules.tenant.application.context import TenantContext
from modules.tenant.models import Company, Membership, MembershipRole
from modules.workforceops.application.selectors import workforce_overview
from modules.workforceops.application.services import (
    RequestEvidence,
    assign_worker,
    create_plan,
    decide_approval,
    request_approval,
    transition_plan,
)
from modules.workforceops.models import (
    EmployeeSkillCredential,
    SkillDefinition,
    WorkforceAssignment,
    WorkforceDemand,
    WorkforcePlan,
    WorkforcePolicyVersion,
    WorkforceRisk,
)


class WorkforceOperationsTests(TestCase):
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
        now = timezone.now()
        membership = Membership.objects.create(
            company=company,
            user=user,
            effective_from=now - timedelta(days=1),
        )
        employee = Employee.objects.create(
            company=company,
            membership=membership,
            employee_number=f"EMP-{suffix}",
            job_title="Workforce test employee",
            employment_start=date(2026, 1, 1),
        )
        session = AuthSession.objects.create(
            user=user,
            device_id=uuid.uuid4(),
            device_name="Workforce test device",
            user_agent="workforceops-tests",
            expires_at=now + timedelta(days=1),
        )
        role = Role.objects.create(
            company_public_id=company.public_id,
            code=f"workforce_test_{suffix.lower()}",
            name=f"Workforce test role {suffix}",
            version=1,
            effective_from=now - timedelta(minutes=1),
        )
        for permission_code in permissions:
            permission, _ = Permission.objects.get_or_create(
                code=permission_code,
                defaults={
                    "description": f"Test permission {permission_code}",
                    "data_class": "workforce_restricted",
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
            user_agent="workforceops-tests",
        )

    def policy(
        self,
        company: Company,
        code: str = "WORKFORCE",
        configuration: dict | None = None,
    ) -> WorkforcePolicyVersion:
        now = timezone.now()
        return WorkforcePolicyVersion.objects.create(
            company=company,
            code=code,
            name="Workforce policy",
            version=1,
            status_code="PUBLISHED",
            effective_from=now - timedelta(days=1),
            published_at=now,
            configuration=configuration
            or {
                "initial_plan_status": "DRAFT",
                "immutable_statuses": ["LOCKED"],
                "maker_checker_required": True,
                "credential_enforcement": "RISK",
                "accepted_verification_statuses": ["VERIFIED"],
                "credential_gap_risk_code": "SKILL_REQUIREMENT_GAP",
                "credential_gap_severity": "HIGH",
                "open_risk_status": "OPEN",
                "filled_demand_status": "FILLED",
                "approval_decisions": {
                    "APPROVE": "APPROVED",
                    "REJECT": "REJECTED",
                },
                "transitions": [
                    {
                        "from": "DRAFT",
                        "to": "APPROVED",
                        "permission": "workforce.approve",
                        "milestone": "approved",
                        "required_approvals": [
                            {
                                "step_code": "WORKFORCE_APPROVAL",
                                "accepted_statuses": ["APPROVED"],
                            }
                        ],
                    }
                ],
            },
        )

    def plan(self, company: Company, code: str = "PLAN-1") -> WorkforcePlan:
        return WorkforcePlan.objects.create(
            company=company,
            policy=self.policy(company, f"POL-{code}"),
            code=code,
            name="Workforce plan",
            starts_on=date(2026, 8, 1),
            ends_on=date(2026, 12, 31),
            status_code="DRAFT",
            owner_membership_public_id=company.public_id,
        )

    def demand(self, company: Company, code: str = "D-1") -> WorkforceDemand:
        return WorkforceDemand.objects.create(
            company=company,
            plan=self.plan(company, f"PLAN-{code}"),
            demand_code=code,
            role_code="CONFIGURED_ROLE",
            priority_code="HIGH",
            status_code="OPEN",
            quantity_required=2,
            starts_on=date(2026, 8, 1),
            ends_on=date(2026, 10, 31),
            estimated_cost=Decimal("10000.00"),
            currency=company.currency,
            skill_requirements=[],
        )

    def test_policy_requires_configured_initial_status(self):
        company = self.company("AAA")
        policy = WorkforcePolicyVersion(
            company=company,
            code="INVALID",
            name="Invalid",
            status_code="DRAFT",
            effective_from=timezone.now(),
            configuration={},
        )
        with self.assertRaises(ValidationError):
            policy.full_clean()

    def test_plan_rejects_cross_company_policy(self):
        company_a = self.company("AAA")
        company_b = self.company("BBB")
        plan = WorkforcePlan(
            company=company_a,
            policy=self.policy(company_b),
            code="CROSS",
            name="Cross tenant plan",
            starts_on=date(2026, 8, 1),
            ends_on=date(2026, 8, 31),
            status_code="DRAFT",
            owner_membership_public_id=company_a.public_id,
        )
        with self.assertRaises(ValidationError):
            plan.full_clean()

    def test_demand_rejects_overfilled_quantity(self):
        company = self.company("AAA")
        demand = WorkforceDemand(
            company=company,
            plan=self.plan(company),
            demand_code="OVER",
            role_code="ROLE",
            priority_code="HIGH",
            status_code="OPEN",
            quantity_required=1,
            quantity_filled=2,
            starts_on=date(2026, 8, 1),
            ends_on=date(2026, 8, 31),
            estimated_cost=Decimal("0.00"),
            currency="INR",
        )
        with self.assertRaises(ValidationError):
            demand.full_clean()

    def test_assignment_rejects_cross_company_demand(self):
        company_a = self.company("AAA")
        company_b = self.company("BBB")
        assignment = WorkforceAssignment(
            company=company_a,
            demand=self.demand(company_b),
            employee_public_id=company_a.public_id,
            assignment_status_code="ACTIVE",
            allocation_percent=Decimal("100.00"),
            starts_on=date(2026, 8, 1),
        )
        with self.assertRaises(ValidationError):
            assignment.full_clean()

    def test_overview_is_tenant_isolated(self):
        company_a = self.company("AAA")
        company_b = self.company("BBB")
        self.demand(company_a, "A-1")
        demand_b = self.demand(company_b, "B-1")
        WorkforceRisk.objects.create(
            company=company_b,
            plan=demand_b.plan,
            demand=demand_b,
            risk_code="PRIVATE",
            severity_code="CRITICAL",
            status_code="OPEN",
            message="Must not appear in tenant A",
        )
        overview = workforce_overview(company_a)
        self.assertEqual(overview["summary"]["demand_count"], 1)
        self.assertEqual(overview["summary"]["open_risk_count"], 0)
        self.assertNotIn("Must not appear", str(overview))

    def test_assignment_creates_configured_skill_gap_risk(self):
        company = self.company("AAA")
        context, employee = self.actor(
            company,
            "Planner",
            {"workforce.manage", "workforce.view"},
        )
        plan = self.plan(company)
        SkillDefinition.objects.create(
            company=company,
            code="SAFETY-CERT",
            name="Safety certificate",
            version=1,
            category_code="SAFETY",
            proficiency_scale=["QUALIFIED"],
            is_certification=True,
            effective_from=timezone.now() - timedelta(days=1),
        )
        demand = WorkforceDemand.objects.create(
            company=company,
            plan=plan,
            demand_code="SAFETY-NEED",
            role_code="SITE-ROLE",
            priority_code="HIGH",
            status_code="OPEN",
            quantity_required=1,
            starts_on=date(2026, 8, 1),
            ends_on=date(2026, 10, 31),
            estimated_cost=Decimal("1000.00"),
            currency="INR",
            skill_requirements=[
                {"skill_code": "SAFETY-CERT", "mandatory": True}
            ],
        )
        assignment = assign_worker(
            context=context,
            evidence=self.evidence(),
            demand_public_id=demand.public_id,
            employee_public_id=employee.public_id,
            assignment_status_code="ACTIVE",
            allocation_percent="100.00",
            starts_on=date(2026, 8, 1),
        )
        self.assertIsNotNone(assignment.public_id)
        self.assertEqual(
            WorkforceRisk.objects.filter(
                company=company,
                employee_public_id=employee.public_id,
                risk_code="SKILL_REQUIREMENT_GAP",
            ).count(),
            1,
        )

    def test_maker_checker_and_transition_controls(self):
        company = self.company("AAA")
        maker_context, _ = self.actor(
            company,
            "Maker",
            {"workforce.manage", "workforce.view"},
        )
        approver_context, _ = self.actor(
            company,
            "Approver",
            {"workforce.approve", "workforce.view"},
        )
        policy = self.policy(company)
        plan = create_plan(
            context=maker_context,
            evidence=self.evidence(),
            policy_public_id=policy.public_id,
            code="CONTROLLED",
            name="Controlled plan",
            starts_on=date(2026, 8, 1),
            ends_on=date(2026, 12, 31),
        )
        approval = request_approval(
            context=maker_context,
            evidence=self.evidence(),
            plan_public_id=plan.public_id,
            step_code="WORKFORCE_APPROVAL",
            requested_from_membership_public_id=approver_context.membership.public_id,
            status_code="PENDING",
        )
        decide_approval(
            context=approver_context,
            evidence=self.evidence(),
            approval_public_id=approval.public_id,
            decision_code="APPROVE",
            reason="Capacity and credential controls validated",
        )
        transitioned = transition_plan(
            context=approver_context,
            evidence=self.evidence(),
            plan_public_id=plan.public_id,
            expected_version=plan.version,
            target_status_code="APPROVED",
            reason="Approved through maker-checker",
        )
        self.assertEqual(transitioned.status_code, "APPROVED")
        self.assertEqual(transitioned.version, 2)

    def test_credential_proficiency_uses_configured_scale(self):
        company = self.company("AAA")
        skill = SkillDefinition.objects.create(
            company=company,
            code="CONFIGURED-SKILL",
            name="Configured skill",
            version=1,
            category_code="TRADE",
            proficiency_scale=["LEVEL-1", "LEVEL-2"],
            effective_from=timezone.now(),
        )
        credential = EmployeeSkillCredential(
            company=company,
            employee_public_id=company.public_id,
            skill=skill,
            proficiency_code="UNCONFIGURED",
            verification_status_code="PENDING",
        )
        with self.assertRaises(ValidationError):
            credential.full_clean()

    def test_policy_rejects_unconfigured_risk_enforcement(self):
        company = self.company("AAA")
        policy = WorkforcePolicyVersion(
            company=company,
            code="INCOMPLETE",
            name="Incomplete risk policy",
            status_code="DRAFT",
            effective_from=timezone.now(),
            configuration={
                "initial_plan_status": "DRAFT",
                "immutable_statuses": [],
                "credential_enforcement": "RISK",
                "accepted_verification_statuses": ["VERIFIED"],
                "approval_decisions": {},
                "transitions": [],
            },
        )
        with self.assertRaises(ValidationError):
            policy.full_clean()

    def test_multiple_approval_events_do_not_collide(self):
        company = self.company("AAA")
        maker_context, _ = self.actor(
            company,
            "Maker",
            {"workforce.manage", "workforce.view"},
        )
        approver_context, _ = self.actor(
            company,
            "Approver",
            {"workforce.approve", "workforce.view"},
        )
        plan = self.plan(company)
        for step_code in ("CAPACITY", "COMPLIANCE"):
            request_approval(
                context=maker_context,
                evidence=self.evidence(),
                plan_public_id=plan.public_id,
                step_code=step_code,
                requested_from_membership_public_id=(
                    approver_context.membership.public_id
                ),
                status_code="PENDING",
            )
        events = BusinessEventOutbox.objects.filter(
            company_public_id=company.public_id,
            event_type="workforce.approval.requested",
        )
        self.assertEqual(events.count(), 2)
        self.assertEqual(
            events.values("aggregate_public_id").distinct().count(),
            2,
        )

    def test_cost_summary_does_not_mix_currencies(self):
        company = self.company("AAA")
        plan = self.plan(company)
        common = {
            "company": company,
            "plan": plan,
            "role_code": "CONFIGURED_ROLE",
            "priority_code": "HIGH",
            "status_code": "OPEN",
            "quantity_required": 1,
            "starts_on": date(2026, 8, 1),
            "ends_on": date(2026, 10, 31),
        }
        WorkforceDemand.objects.create(
            **common,
            demand_code="INR-DEMAND",
            estimated_cost=Decimal("100.00"),
            currency="INR",
        )
        WorkforceDemand.objects.create(
            **common,
            demand_code="USD-DEMAND",
            estimated_cost=Decimal("200.00"),
            currency="USD",
        )
        overview = workforce_overview(company)
        self.assertEqual(
            Decimal(overview["summary"]["estimated_cost"]),
            Decimal("100.00"),
        )
        costs = {
            item["currency"]: Decimal(item["amount"])
            for item in overview["summary"]["estimated_cost_by_currency"]
        }
        self.assertEqual(
            costs,
            {"INR": Decimal("100.00"), "USD": Decimal("200.00")},
        )

    def test_database_names_stay_within_portable_limit(self):
        from django.apps import apps

        for model in apps.get_app_config("workforceops").get_models():
            for constraint in model._meta.constraints:
                self.assertLessEqual(len(constraint.name), 30, constraint.name)
            for index in model._meta.indexes:
                self.assertLessEqual(len(index.name), 30, index.name)
