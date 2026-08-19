import uuid
from datetime import date, timedelta

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied

from modules.employee.models import Employee
from modules.identity.application.tokens import AccessPrincipal
from modules.identity.models import AuthSession, Permission, Role, RolePermission, User
from modules.platform.models import BusinessEventOutbox
from modules.safetyops.application.selectors import safety_overview
from modules.safetyops.application.services import (
    RequestEvidence,
    create_permit,
    decide_approval,
    report_incident,
    request_approval,
)
from modules.safetyops.models import (
    PermitToWork,
    SafetyIncident,
    SafetyObservation,
    SafetyPolicyVersion,
    SafetyRisk,
)
from modules.tenant.application.context import TenantContext
from modules.tenant.models import Company, Membership, MembershipRole


class SafetyOperationsTests(TestCase):
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
            job_title="Safety test employee",
            employment_start=date(2026, 1, 1),
        )
        session = AuthSession.objects.create(
            user=user,
            device_id=uuid.uuid4(),
            device_name="Safety test device",
            user_agent="safetyops-tests",
            expires_at=now + timedelta(days=1),
        )
        role = Role.objects.create(
            company_public_id=company.public_id,
            code=f"safety_test_{suffix.lower()}",
            name=f"Safety test role {suffix}",
            version=1,
            effective_from=now - timedelta(minutes=1),
        )
        for permission_code in permissions:
            permission, _ = Permission.objects.get_or_create(
                code=permission_code,
                defaults={
                    "description": f"Test permission {permission_code}",
                    "data_class": "safety_restricted",
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
            user_agent="safetyops-tests",
        )

    def policy(self, company: Company, code: str = "HSE") -> SafetyPolicyVersion:
        now = timezone.now()
        policy = SafetyPolicyVersion(
            company=company,
            code=code,
            name="Safety policy",
            version=1,
            status_code="PUBLISHED",
            effective_from=now - timedelta(days=1),
            published_at=now,
            configuration={
                "initial_observation_status": "OPEN",
                "open_observation_statuses": ["OPEN", "ACTION_REQUIRED"],
                "initial_incident_status": "REPORTED",
                "open_incident_statuses": ["REPORTED", "INVESTIGATING"],
                "initial_permit_status": "DRAFT",
                "active_permit_statuses": ["ACTIVE"],
                "initial_action_status": "OPEN",
                "open_action_statuses": ["OPEN", "IN_PROGRESS", "COMPLETED"],
                "initial_risk_status": "OPEN",
                "resolved_risk_status": "RESOLVED",
                "critical_severity_codes": ["CRITICAL", "FATAL"],
                "accepted_inspection_results": ["PASSED"],
                "initial_approval_status": "PENDING",
                "approval_decisions": {
                    "APPROVE": "APPROVED",
                    "REJECT": "REJECTED",
                },
                "observation_transitions": [],
                "incident_transitions": [],
                "permit_transitions": [
                    {
                        "from": "DRAFT",
                        "to": "ACTIVE",
                        "permission": "safety.approve",
                        "milestone": "approved",
                        "required_approvals": [
                            {
                                "step_code": "PERMIT_ISSUE",
                                "accepted_statuses": ["APPROVED"],
                            }
                        ],
                    }
                ],
                "action_transitions": [],
            },
        )
        policy.full_clean()
        policy.save()
        return policy

    def test_policy_requires_governed_initial_statuses(self):
        company = self.company("AAA")
        policy = SafetyPolicyVersion(
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

    def test_observation_rejects_cross_company_policy(self):
        company_a = self.company("AAA")
        company_b = self.company("BBB")
        observation = SafetyObservation(
            company=company_a,
            policy=self.policy(company_b),
            observation_code="OBS-1",
            category_code="HOUSEKEEPING",
            severity_code="LOW",
            status_code="OPEN",
            title="Cross-company observation",
            observed_at=timezone.now(),
            observed_by_membership_public_id=uuid.uuid4(),
        )
        with self.assertRaises(ValidationError):
            observation.full_clean()

    def test_critical_incident_creates_governed_risk_without_evidence_payload(self):
        company = self.company("AAA")
        context, _ = self.actor(company, "Reporter", {"safety.incident"})
        policy = self.policy(company)
        now = timezone.now()
        incident = report_incident(
            context=context,
            evidence=self.evidence(),
            policy_public_id=policy.public_id,
            attributes={
                "incident_code": "INC-1",
                "incident_type_code": "NEAR_MISS",
                "severity_code": "CRITICAL",
                "title": "Critical lifting near miss",
                "description": "A controlled test incident.",
                "occurred_at": now - timedelta(minutes=10),
                "reported_at": now,
                "evidence_reference": "private/object/key",
            },
        )
        self.assertTrue(
            SafetyRisk.objects.filter(
                company=company,
                linked_entity_public_id=incident.public_id,
                resolved_at__isnull=True,
            ).exists()
        )
        event = BusinessEventOutbox.objects.get(
            aggregate_public_id=incident.public_id,
            event_type="safety.incident.reported",
        )
        self.assertNotIn("evidence_reference", event.payload)
        self.assertNotIn("description", event.payload)

    def test_permit_rejects_invalid_effective_range(self):
        company = self.company("AAA")
        policy = self.policy(company)
        now = timezone.now()
        permit = PermitToWork(
            company=company,
            policy=policy,
            permit_code="PTW-1",
            permit_type_code="HOT_WORK",
            risk_level_code="HIGH",
            status_code="DRAFT",
            work_summary="Controlled hot work test",
            valid_from=now,
            valid_until=now,
            issuer_membership_public_id=uuid.uuid4(),
            receiver_membership_public_id=uuid.uuid4(),
        )
        with self.assertRaises(ValidationError):
            permit.full_clean()

    def test_maker_checker_approval_prevents_self_decision(self):
        company = self.company("AAA")
        maker, _ = self.actor(
            company,
            "Maker",
            {"safety.manage", "safety.permit", "safety.approve"},
        )
        checker, _ = self.actor(company, "Checker", {"safety.approve"})
        policy = self.policy(company)
        now = timezone.now()
        permit = create_permit(
            context=maker,
            evidence=self.evidence(),
            policy_public_id=policy.public_id,
            attributes={
                "permit_code": "PTW-1",
                "permit_type_code": "HOT_WORK",
                "risk_level_code": "HIGH",
                "work_summary": "Controlled hot work",
                "valid_from": now,
                "valid_until": now + timedelta(hours=8),
                "receiver_membership_public_id": checker.membership.public_id,
            },
        )
        approval = request_approval(
            context=maker,
            evidence=self.evidence(),
            policy_public_id=policy.public_id,
            attributes={
                "entity_type_code": "PERMIT",
                "entity_public_id": permit.public_id,
                "step_code": "PERMIT_ISSUE",
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
        policy_a = self.policy(company_a, "HSE-A")
        policy_b = self.policy(company_b, "HSE-B")
        now = timezone.now()
        SafetyIncident.objects.create(
            company=company_a,
            policy=policy_a,
            incident_code="A-INC",
            incident_type_code="NEAR_MISS",
            severity_code="HIGH",
            status_code="REPORTED",
            title="A incident",
            description="Tenant A",
            occurred_at=now,
            reported_at=now,
            reported_by_membership_public_id=uuid.uuid4(),
        )
        SafetyIncident.objects.create(
            company=company_b,
            policy=policy_b,
            incident_code="B-INC",
            incident_type_code="NEAR_MISS",
            severity_code="HIGH",
            status_code="REPORTED",
            title="B incident",
            description="Tenant B",
            occurred_at=now,
            reported_at=now,
            reported_by_membership_public_id=uuid.uuid4(),
        )
        overview = safety_overview(company_a)
        self.assertEqual(overview["summary"]["open_incident_count"], 1)
        self.assertEqual(overview["open_incidents"][0]["incident_code"], "A-INC")

    def test_database_names_stay_within_portable_limit(self):
        from django.apps import apps

        for model in apps.get_app_config("safetyops").get_models():
            self.assertLessEqual(len(model._meta.db_table), 30)
            for constraint in model._meta.constraints:
                self.assertLessEqual(len(constraint.name), 30)
            for index in model._meta.indexes:
                self.assertLessEqual(len(index.name), 30)
