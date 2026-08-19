import uuid
from datetime import date, timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from modules.employee.models import Employee
from modules.equipmentops.application.selectors import equipment_overview
from modules.equipmentops.application.services import (
    RequestEvidence,
    create_work_order,
    decide_approval,
    record_meter_reading,
    request_approval,
    transition_work_order,
)
from modules.equipmentops.models import (
    EquipmentAsset,
    EquipmentDeployment,
    EquipmentPolicyVersion,
    EquipmentRisk,
    MaintenanceWorkOrder,
)
from modules.identity.application.tokens import AccessPrincipal
from modules.identity.models import AuthSession, Permission, Role, RolePermission, User
from modules.platform.models import BusinessEventOutbox
from modules.tenant.application.context import TenantContext
from modules.tenant.models import Company, Membership, MembershipRole


class EquipmentOperationsTests(TestCase):
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
            job_title="Equipment test employee",
            employment_start=date(2026, 1, 1),
        )
        session = AuthSession.objects.create(
            user=user,
            device_id=uuid.uuid4(),
            device_name="Equipment test device",
            user_agent="equipmentops-tests",
            expires_at=now + timedelta(days=1),
        )
        role = Role.objects.create(
            company_public_id=company.public_id,
            code=f"equipment_test_{suffix.lower()}",
            name=f"Equipment test role {suffix}",
            version=1,
            effective_from=now - timedelta(minutes=1),
        )
        for permission_code in permissions:
            permission, _ = Permission.objects.get_or_create(
                code=permission_code,
                defaults={
                    "description": f"Test permission {permission_code}",
                    "data_class": "equipment_restricted",
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
            user_agent="equipmentops-tests",
        )

    def policy(
        self,
        company: Company,
        code: str = "EQUIPMENT",
        meter_action: str = "BLOCK",
    ) -> EquipmentPolicyVersion:
        now = timezone.now()
        configuration = {
            "initial_asset_status": "AVAILABLE",
            "immutable_asset_statuses": ["RETIRED"],
            "initial_deployment_status": "ACTIVE",
            "active_deployment_statuses": ["ACTIVE"],
            "deployed_asset_status": "DEPLOYED",
            "initial_work_order_status": "OPEN",
            "open_work_order_statuses": [
                "OPEN",
                "APPROVAL_PENDING",
                "PLANNED",
                "IN_PROGRESS",
            ],
            "meter_regression_action": meter_action,
            "accepted_inspection_results": ["PASSED"],
            "inspection_failure_risk_code": "INSPECTION_NOT_ACCEPTED",
            "inspection_failure_severity": "HIGH",
            "open_risk_status": "OPEN",
            "maker_checker_required": True,
            "maintenance_hold_priorities": ["CRITICAL"],
            "maintenance_hold_asset_status": "MAINTENANCE_HOLD",
            "approval_decisions": {
                "APPROVE": "APPROVED",
                "REJECT": "REJECTED",
            },
            "asset_status_by_work_order_status": {
                "IN_PROGRESS": "MAINTENANCE_HOLD",
                "COMPLETED": "AVAILABLE",
            },
            "work_order_transitions": [
                {
                    "from": "OPEN",
                    "to": "APPROVAL_PENDING",
                    "permission": "equipment.maintain",
                },
                {
                    "from": "APPROVAL_PENDING",
                    "to": "PLANNED",
                    "permission": "equipment.approve",
                    "milestone": "approved",
                    "required_approvals": [
                        {
                            "step_code": "MAINTENANCE_APPROVAL",
                            "accepted_statuses": ["APPROVED"],
                        }
                    ],
                },
                {
                    "from": "PLANNED",
                    "to": "IN_PROGRESS",
                    "permission": "equipment.maintain",
                },
                {
                    "from": "IN_PROGRESS",
                    "to": "COMPLETED",
                    "permission": "equipment.maintain",
                    "milestone": "completed",
                },
            ],
        }
        if meter_action == "RISK":
            configuration.update(
                {
                    "meter_regression_risk_code": "METER_REGRESSION",
                    "meter_regression_severity": "HIGH",
                }
            )
        policy = EquipmentPolicyVersion(
            company=company,
            code=code,
            name="Equipment policy",
            version=1,
            status_code="PUBLISHED",
            effective_from=now - timedelta(days=1),
            published_at=now,
            configuration=configuration,
        )
        policy.full_clean()
        policy.save()
        return policy

    def asset(
        self,
        company: Company,
        code: str = "EQ-1",
        meter_action: str = "BLOCK",
    ) -> EquipmentAsset:
        return EquipmentAsset.objects.create(
            company=company,
            policy=self.policy(company, f"POL-{code}", meter_action),
            asset_code=code,
            name="Tower crane",
            category_code="LIFTING",
            asset_type_code="TOWER_CRANE",
            ownership_code="OWNED",
            status_code="AVAILABLE",
            meter_type_code="HOURS",
            current_meter_value=Decimal("100.00"),
            acquisition_cost=Decimal("1000000.00"),
            currency=company.currency,
            next_service_on=date(2026, 8, 20),
            compliance_due_on=date(2026, 9, 1),
        )

    def test_policy_requires_governed_initial_statuses(self):
        company = self.company("AAA")
        policy = EquipmentPolicyVersion(
            company=company,
            code="INVALID",
            name="Invalid",
            status_code="DRAFT",
            effective_from=timezone.now(),
            configuration={},
        )
        with self.assertRaises(ValidationError):
            policy.full_clean()

    def test_asset_rejects_cross_company_policy(self):
        company_a = self.company("AAA")
        company_b = self.company("BBB")
        asset = EquipmentAsset(
            company=company_a,
            policy=self.policy(company_b),
            asset_code="CROSS",
            name="Cross tenant asset",
            category_code="PLANT",
            asset_type_code="GENERIC",
            ownership_code="OWNED",
            status_code="AVAILABLE",
            acquisition_cost=Decimal("0.00"),
            currency="INR",
        )
        with self.assertRaises(ValidationError):
            asset.full_clean()

    def test_deployment_rejects_cross_company_asset(self):
        company_a = self.company("AAA")
        company_b = self.company("BBB")
        deployment = EquipmentDeployment(
            company=company_a,
            asset=self.asset(company_b),
            deployment_code="CROSS-DEPLOY",
            status_code="ACTIVE",
            starts_at=timezone.now(),
        )
        with self.assertRaises(ValidationError):
            deployment.full_clean()

    def test_meter_regression_is_blocked_by_policy(self):
        company = self.company("AAA")
        context, _ = self.actor(
            company,
            "Operator",
            {"equipment.manage", "equipment.view"},
        )
        asset = self.asset(company)
        with self.assertRaises(ValidationError):
            record_meter_reading(
                context=context,
                evidence=self.evidence(),
                asset_public_id=asset.public_id,
                reading_at=timezone.now(),
                meter_type_code="HOURS",
                reading_value="90.00",
                source_code="MANUAL",
            )
        asset.refresh_from_db()
        self.assertEqual(asset.current_meter_value, Decimal("100.00"))

    def test_meter_regression_risk_and_event_are_created(self):
        company = self.company("AAA")
        context, _ = self.actor(
            company,
            "Operator",
            {"equipment.manage", "equipment.view"},
        )
        asset = self.asset(company, meter_action="RISK")
        reading = record_meter_reading(
            context=context,
            evidence=self.evidence(),
            asset_public_id=asset.public_id,
            reading_at=timezone.now(),
            meter_type_code="HOURS",
            reading_value="90.00",
            source_code="TELEMATICS",
        )
        self.assertEqual(reading.reading_value, Decimal("90.00"))
        self.assertEqual(
            EquipmentRisk.objects.filter(
                company=company,
                asset=asset,
                risk_code="METER_REGRESSION",
            ).count(),
            1,
        )
        self.assertEqual(
            BusinessEventOutbox.objects.filter(
                company_public_id=company.public_id,
                event_type="equipment.meter.recorded",
            ).count(),
            1,
        )

    def test_maker_checker_approval_enables_transition(self):
        company = self.company("AAA")
        maker_context, _ = self.actor(
            company,
            "Maker",
            {"equipment.maintain", "equipment.manage", "equipment.view"},
        )
        approver_context, _ = self.actor(
            company,
            "Approver",
            {"equipment.approve", "equipment.view"},
        )
        asset = self.asset(company)
        work_order = create_work_order(
            context=maker_context,
            evidence=self.evidence(),
            asset_public_id=asset.public_id,
            attributes={
                "code": "WO-1",
                "maintenance_type_code": "CORRECTIVE",
                "priority_code": "HIGH",
                "summary": "Hydraulic inspection",
                "estimated_cost": Decimal("5000.00"),
                "currency": "INR",
                "requires_approval": True,
            },
        )
        work_order = transition_work_order(
            context=maker_context,
            evidence=self.evidence(),
            work_order_public_id=work_order.public_id,
            target_status_code="APPROVAL_PENDING",
            expected_version=work_order.version,
        )
        approval = request_approval(
            context=maker_context,
            evidence=self.evidence(),
            work_order_public_id=work_order.public_id,
            step_code="MAINTENANCE_APPROVAL",
            requested_from_membership_public_id=approver_context.membership.public_id,
            status_code="PENDING",
        )
        decide_approval(
            context=approver_context,
            evidence=self.evidence(),
            approval_public_id=approval.public_id,
            decision_code="APPROVE",
            decision_reason="Cost and shutdown window validated",
        )
        transitioned = transition_work_order(
            context=approver_context,
            evidence=self.evidence(),
            work_order_public_id=work_order.public_id,
            target_status_code="PLANNED",
            expected_version=work_order.version,
        )
        self.assertEqual(transitioned.status_code, "PLANNED")
        self.assertEqual(transitioned.version, 3)
        self.assertIsNotNone(transitioned.approved_at)

    def test_overview_is_tenant_isolated(self):
        company_a = self.company("AAA")
        company_b = self.company("BBB")
        self.asset(company_a, "A-1")
        private_asset = self.asset(company_b, "B-1")
        EquipmentRisk.objects.create(
            company=company_b,
            asset=private_asset,
            risk_code="PRIVATE",
            severity_code="CRITICAL",
            status_code="OPEN",
            message="Must not appear in tenant A",
        )
        overview = equipment_overview(company_a)
        self.assertEqual(overview["summary"]["asset_count"], 1)
        self.assertEqual(overview["summary"]["open_risk_count"], 0)
        self.assertNotIn("Must not appear", str(overview))

    def test_cost_summary_does_not_mix_currencies(self):
        company = self.company("AAA")
        asset = self.asset(company)
        common = {
            "company": company,
            "asset": asset,
            "maintenance_type_code": "PREVENTIVE",
            "priority_code": "HIGH",
            "status_code": "OPEN",
            "reported_at": timezone.now(),
            "summary": "Planned maintenance",
        }
        MaintenanceWorkOrder.objects.create(
            **common,
            code="WO-INR",
            estimated_cost=Decimal("100.00"),
            currency="INR",
        )
        MaintenanceWorkOrder.objects.create(
            **common,
            code="WO-USD",
            estimated_cost=Decimal("200.00"),
            currency="USD",
        )
        overview = equipment_overview(company)
        self.assertEqual(
            Decimal(overview["summary"]["estimated_maintenance_cost"]),
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

        for model in apps.get_app_config("equipmentops").get_models():
            for constraint in model._meta.constraints:
                self.assertLessEqual(len(constraint.name), 30, constraint.name)
            for index in model._meta.indexes:
                self.assertLessEqual(len(index.name), 30, index.name)
