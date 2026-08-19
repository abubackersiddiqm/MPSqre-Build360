import uuid
from datetime import date, timedelta

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied

from modules.employee.models import Employee
from modules.identity.application.tokens import AccessPrincipal
from modules.identity.models import AuthSession, Permission, Role, RolePermission, User
from modules.qualityops.application.selectors import quality_overview
from modules.qualityops.application.services import (
    RequestEvidence,
    create_itp,
    create_risk,
    decide_approval,
    request_approval,
    resolve_risk,
)
from modules.qualityops.models import (
    InspectionTestPlan,
    NonConformanceReport,
    QualityInspection,
    QualityPolicyVersion,
)
from modules.tenant.application.context import TenantContext
from modules.tenant.models import Company, Membership, MembershipRole


class QualityOperationsTests(TestCase):
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

    def actor(self, company: Company, suffix: str, permissions: set[str]) -> TenantContext:
        user = User.objects.create_user(
            email=f"{suffix.lower()}@example.test",
            password="A-secure-test-password-123",
            display_name=suffix,
        )
        now = timezone.now()
        membership = Membership.objects.create(
            company=company, user=user, effective_from=now - timedelta(days=1)
        )
        Employee.objects.create(
            company=company,
            membership=membership,
            employee_number=f"EMP-{suffix}",
            job_title="Quality test employee",
            employment_start=date(2026, 1, 1),
        )
        session = AuthSession.objects.create(
            user=user,
            device_id=uuid.uuid4(),
            device_name="Quality test device",
            user_agent="qualityops-tests",
            expires_at=now + timedelta(days=1),
        )
        role = Role.objects.create(
            company_public_id=company.public_id,
            code=f"quality_test_{suffix.lower()}",
            name=f"Quality test role {suffix}",
            version=1,
            effective_from=now - timedelta(minutes=1),
        )
        for permission_code in permissions:
            permission, _ = Permission.objects.get_or_create(
                code=permission_code,
                defaults={
                    "description": f"Test permission {permission_code}",
                    "data_class": "quality_restricted",
                },
            )
            RolePermission.objects.create(role=role, permission=permission)
        MembershipRole.objects.create(
            membership=membership,
            role_public_id=role.public_id,
            assigned_by_public_id=user.public_id,
            effective_from=now - timedelta(minutes=1),
        )
        return TenantContext(
            company=company,
            membership=membership,
            principal=AccessPrincipal(user=user, session=session, assurance_at=None),
        )

    def evidence(self) -> RequestEvidence:
        request_id = uuid.uuid4()
        return RequestEvidence(
            request_id=request_id,
            correlation_id=request_id,
            ip_address="127.0.0.1",
            user_agent="qualityops-tests",
        )

    def policy(self, company: Company, code: str = "QAQC") -> QualityPolicyVersion:
        now = timezone.now()
        policy = QualityPolicyVersion(
            company=company,
            code=code,
            name="Quality policy",
            version=1,
            status_code="PUBLISHED",
            effective_from=now - timedelta(days=1),
            published_at=now,
            configuration={
                "initial_itp_status": "DRAFT",
                "active_itp_statuses": ["APPROVED", "ACTIVE"],
                "initial_request_status": "SUBMITTED",
                "open_request_statuses": ["SUBMITTED", "SCHEDULED"],
                "initial_inspection_status": "SCHEDULED",
                "completed_inspection_status": "COMPLETED",
                "initial_ncr_status": "OPEN",
                "open_ncr_statuses": ["OPEN", "ACTION_PENDING"],
                "initial_action_status": "OPEN",
                "open_action_statuses": ["OPEN", "IN_PROGRESS", "COMPLETED"],
                "initial_risk_status": "OPEN",
                "resolved_risk_status": "RESOLVED",
                "critical_severity_codes": ["CRITICAL", "MAJOR"],
                "accepted_inspection_results": ["ACCEPTED"],
                "accepted_test_results": ["PASSED"],
                "initial_approval_status": "PENDING",
                "approval_decisions": {"APPROVE": "APPROVED", "REJECT": "REJECTED"},
                "itp_transitions": [
                    {
                        "from": "DRAFT",
                        "to": "APPROVED",
                        "permission": "quality.approve",
                        "milestone": "approved",
                        "required_approvals": [
                            {"step_code": "ITP_APPROVAL", "accepted_statuses": ["APPROVED"]}
                        ],
                    }
                ],
                "request_transitions": [],
                "ncr_transitions": [],
                "action_transitions": [],
            },
        )
        policy.full_clean()
        policy.save()
        return policy

    def test_policy_requires_governed_configuration(self):
        company = self.company("AAA")
        policy = QualityPolicyVersion(
            company=company,
            code="INVALID",
            name="Invalid",
            version=1,
            status_code="DRAFT",
            effective_from=timezone.now(),
            configuration={},
        )
        with self.assertRaises(ValidationError):
            policy.full_clean()

    def test_itp_rejects_cross_company_policy(self):
        company_a = self.company("AAA")
        company_b = self.company("BBB")
        itp = InspectionTestPlan(
            company=company_a,
            policy=self.policy(company_b),
            itp_code="ITP-1",
            discipline_code="CIVIL",
            work_package_code="CONCRETE",
            status_code="DRAFT",
            title="Cross-company ITP",
        )
        with self.assertRaises(ValidationError):
            itp.full_clean()

    def test_maker_checker_prevents_self_approval(self):
        company = self.company("AAA")
        maker = self.actor(company, "Maker", {"quality.manage", "quality.approve"})
        checker = self.actor(company, "Checker", {"quality.approve"})
        other_checker = self.actor(company, "OtherChecker", {"quality.approve"})
        policy = self.policy(company)
        itp = create_itp(
            context=maker,
            evidence=self.evidence(),
            policy_public_id=policy.public_id,
            attributes={
                "itp_code": "ITP-1",
                "discipline_code": "CIVIL",
                "work_package_code": "CONCRETE",
                "title": "Concrete inspection plan",
            },
        )
        approval = request_approval(
            context=maker,
            evidence=self.evidence(),
            policy_public_id=policy.public_id,
            attributes={
                "entity_type_code": "ITP",
                "entity_public_id": itp.public_id,
                "step_code": "ITP_APPROVAL",
                "requested_from_membership_public_id": checker.membership.public_id,
            },
        )
        with self.assertRaises(PermissionDenied):
            decide_approval(
                context=maker,
                evidence=self.evidence(),
                approval_public_id=approval.public_id,
                decision_code="APPROVE",
            )
        with self.assertRaises(PermissionDenied):
            decide_approval(
                context=other_checker,
                evidence=self.evidence(),
                approval_public_id=approval.public_id,
                decision_code="APPROVE",
            )
        decided = decide_approval(
            context=checker,
            evidence=self.evidence(),
            approval_public_id=approval.public_id,
            decision_code="APPROVE",
        )
        self.assertEqual(decided.status_code, "APPROVED")

    def test_overview_is_tenant_isolated(self):
        company_a = self.company("AAA")
        company_b = self.company("BBB")
        policy_a = self.policy(company_a, "QA-A")
        policy_b = self.policy(company_b, "QA-B")
        now = timezone.now()
        records = (
            (company_a, policy_a, "A-NCR"),
            (company_b, policy_b, "B-NCR"),
        )
        for company, policy, code in records:
            NonConformanceReport.objects.create(
                company=company,
                policy=policy,
                ncr_code=code,
                source_type_code="INSPECTION",
                category_code="WORKMANSHIP",
                severity_code="MAJOR",
                status_code="OPEN",
                title=f"{code} title",
                description="Tenant-specific record",
                detected_at=now,
                detected_by_membership_public_id=uuid.uuid4(),
            )
        overview = quality_overview(company_a)
        self.assertEqual(overview["summary"]["open_ncr_count"], 1)
        self.assertEqual(overview["open_ncrs"][0]["ncr_code"], "A-NCR")

    def test_inspection_quantity_controls(self):
        company = self.company("AAA")
        inspection = QualityInspection(
            company=company,
            policy=self.policy(company),
            inspection_code="INSP-1",
            inspection_type_code="WORK",
            status_code="COMPLETED",
            result_code="REJECTED",
            scheduled_at=timezone.now(),
            completed_at=timezone.now(),
            sample_size=10,
            accepted_quantity=8,
            rejected_quantity=4,
        )
        with self.assertRaises(ValidationError):
            inspection.full_clean()


    def test_risk_resolution_rejects_stale_version(self):
        company = self.company("AAA")
        manager = self.actor(company, "Manager", {"quality.manage"})
        policy = self.policy(company)
        risk = create_risk(
            context=manager,
            evidence=self.evidence(),
            policy_public_id=policy.public_id,
            attributes={
                "linked_entity_type_code": "NCR",
                "risk_code": "Q-RISK-1",
                "severity_code": "MAJOR",
                "message": "Quality control risk",
            },
        )
        with self.assertRaises(ValidationError):
            resolve_risk(
                context=manager,
                evidence=self.evidence(),
                risk_public_id=risk.public_id,
                resolution_note="Resolved after corrective verification",
                expected_version=risk.version + 1,
            )
        risk.refresh_from_db()
        self.assertIsNone(risk.resolved_at)
        self.assertEqual(risk.version, 1)

    def test_database_names_stay_within_portable_limit(self):
        from django.apps import apps

        for model in apps.get_app_config("qualityops").get_models():
            self.assertLessEqual(len(model._meta.db_table), 30)
            for constraint in model._meta.constraints:
                self.assertLessEqual(len(constraint.name), 30)
            for index in model._meta.indexes:
                self.assertLessEqual(len(index.name), 30)
