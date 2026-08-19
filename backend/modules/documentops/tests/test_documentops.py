import uuid
from datetime import date, timedelta

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied

from modules.documentops.application.selectors import document_control_overview
from modules.documentops.application.services import (
    RequestEvidence,
    create_document,
    create_revision,
    decide_approval,
    request_approval,
    transition_revision,
)
from modules.documentops.models import (
    ControlledDocument,
    DocumentControlPolicyVersion,
    DocumentRevision,
)
from modules.employee.models import Employee
from modules.identity.application.tokens import AccessPrincipal
from modules.identity.models import AuthSession, Permission, Role, RolePermission, User
from modules.tenant.application.context import TenantContext
from modules.tenant.models import Company, Membership, MembershipRole


class DocumentOperationsTests(TestCase):
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
            job_title="Document control test employee",
            employment_start=date(2026, 1, 1),
        )
        session = AuthSession.objects.create(
            user=user,
            device_id=uuid.uuid4(),
            device_name="Document control test device",
            user_agent="documentops-tests",
            expires_at=now + timedelta(days=1),
        )
        role = Role.objects.create(
            company_public_id=company.public_id,
            code=f"document_test_{suffix.lower()}",
            name=f"Document test role {suffix}",
            version=1,
            effective_from=now - timedelta(minutes=1),
        )
        for permission_code in permissions:
            permission, _ = Permission.objects.get_or_create(
                code=permission_code,
                defaults={
                    "description": f"Test permission {permission_code}",
                    "data_class": "document_restricted",
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
            user_agent="documentops-tests",
        )

    def policy(self, company: Company) -> DocumentControlPolicyVersion:
        now = timezone.now()
        policy = DocumentControlPolicyVersion(
            company=company,
            code="DOC",
            name="Document control policy",
            version=1,
            status_code="PUBLISHED",
            effective_from=now - timedelta(days=1),
            published_at=now,
            configuration={
                "initial_document_status": "DRAFT",
                "initial_revision_status": "DRAFT",
                "initial_transmittal_status": "DRAFT",
                "initial_rfi_status": "OPEN",
                "initial_submittal_status": "DRAFT",
                "initial_approval_status": "PENDING",
                "initial_distribution_status": "DISTRIBUTED",
                "acknowledged_distribution_status": "ACKNOWLEDGED",
                "initial_risk_status": "OPEN",
                "resolved_risk_status": "RESOLVED",
                "active_document_statuses": ["DRAFT", "ACTIVE"],
                "review_revision_statuses": ["SUBMITTED", "UNDER_REVIEW"],
                "open_transmittal_statuses": ["DRAFT", "ISSUED"],
                "open_rfi_statuses": ["OPEN", "ASSIGNED"],
                "open_submittal_statuses": ["DRAFT", "SUBMITTED"],
                "critical_priority_codes": ["CRITICAL"],
                "approved_submittal_decisions": ["APPROVED"],
                "approval_decisions": {"APPROVE": "APPROVED", "REJECT": "REJECTED"},
                "document_transitions": [],
                "revision_transitions": [
                    {
                        "from": "DRAFT",
                        "to": "ISSUED",
                        "permission": "document.issue",
                        "milestone": "issued",
                        "required_approvals": [
                            {"step_code": "REVISION_ISSUE", "accepted_statuses": ["APPROVED"]}
                        ],
                    }
                ],
                "transmittal_transitions": [],
                "rfi_transitions": [],
                "submittal_transitions": [],
            },
        )
        policy.full_clean()
        policy.save()
        return policy

    def test_policy_requires_governed_configuration(self):
        company = self.company("AAA")
        invalid = DocumentControlPolicyVersion(
            company=company,
            code="INVALID",
            name="Invalid",
            version=1,
            status_code="DRAFT",
            effective_from=timezone.now(),
            configuration={},
        )
        with self.assertRaises(ValidationError):
            invalid.full_clean()

    def test_document_rejects_cross_company_policy(self):
        company_a = self.company("AAA")
        company_b = self.company("BBB")
        document = ControlledDocument(
            company=company_a,
            policy=self.policy(company_b),
            document_number="DOC-001",
            discipline_code="CIVIL",
            document_type_code="DRAWING",
            title="Cross-company document",
            status_code="DRAFT",
        )
        with self.assertRaises(ValidationError):
            document.full_clean()

    def test_revision_hides_sensitive_file_fields_from_overview(self):
        company = self.company("AAA")
        maker = self.actor(company, "Maker", {"document.manage", "document.view"})
        policy = self.policy(company)
        document = create_document(
            context=maker,
            evidence=self.evidence(),
            policy_public_id=policy.public_id,
            attributes={
                "document_number": "DOC-001",
                "discipline_code": "CIVIL",
                "document_type_code": "DRAWING",
                "title": "Foundation drawing",
            },
        )
        create_revision(
            context=maker,
            evidence=self.evidence(),
            policy_public_id=policy.public_id,
            document_public_id=document.public_id,
            attributes={
                "revision_code": "A",
                "sequence_number": 1,
                "purpose_code": "REVIEW",
                "file_reference": "private/storage/object.pdf",
                "checksum_sha256": "a" * 64,
            },
        )
        payload = document_control_overview(company)
        serialized = str(payload)
        self.assertNotIn("private/storage/object.pdf", serialized)
        self.assertNotIn("a" * 64, serialized)

    def test_maker_checker_and_revision_issue(self):
        company = self.company("AAA")
        maker = self.actor(company, "Maker", {"document.manage", "document.issue"})
        checker = self.actor(company, "Checker", {"document.approve", "document.issue"})
        policy = self.policy(company)
        document = create_document(
            context=maker,
            evidence=self.evidence(),
            policy_public_id=policy.public_id,
            attributes={
                "document_number": "DOC-001",
                "discipline_code": "CIVIL",
                "document_type_code": "DRAWING",
                "title": "Foundation drawing",
            },
        )
        revision = create_revision(
            context=maker,
            evidence=self.evidence(),
            policy_public_id=policy.public_id,
            document_public_id=document.public_id,
            attributes={
                "revision_code": "A",
                "sequence_number": 1,
                "purpose_code": "CONSTRUCTION",
            },
        )
        approval = request_approval(
            context=maker,
            evidence=self.evidence(),
            policy_public_id=policy.public_id,
            attributes={
                "entity_type_code": "REVISION",
                "entity_public_id": revision.public_id,
                "step_code": "REVISION_ISSUE",
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
        decide_approval(
            context=checker,
            evidence=self.evidence(),
            approval_public_id=approval.public_id,
            decision_code="APPROVE",
        )
        issued = transition_revision(
            context=checker,
            evidence=self.evidence(),
            revision_public_id=revision.public_id,
            target_status_code="ISSUED",
            expected_version=1,
        )
        document.refresh_from_db()
        self.assertIsNotNone(issued.issued_at)
        self.assertEqual(document.current_revision_code, "A")

    def test_stale_revision_version_is_rejected(self):
        company = self.company("AAA")
        maker = self.actor(company, "Maker", {"document.manage", "document.issue"})
        checker = self.actor(company, "Checker", {"document.approve", "document.issue"})
        policy = self.policy(company)
        document = create_document(
            context=maker,
            evidence=self.evidence(),
            policy_public_id=policy.public_id,
            attributes={
                "document_number": "DOC-001",
                "discipline_code": "CIVIL",
                "document_type_code": "DRAWING",
                "title": "Foundation drawing",
            },
        )
        revision = create_revision(
            context=maker,
            evidence=self.evidence(),
            policy_public_id=policy.public_id,
            document_public_id=document.public_id,
            attributes={
                "revision_code": "A",
                "sequence_number": 1,
                "purpose_code": "CONSTRUCTION",
            },
        )
        approval = request_approval(
            context=maker,
            evidence=self.evidence(),
            policy_public_id=policy.public_id,
            attributes={
                "entity_type_code": "REVISION",
                "entity_public_id": revision.public_id,
                "step_code": "REVISION_ISSUE",
                "requested_from_membership_public_id": checker.membership.public_id,
            },
        )
        decide_approval(
            context=checker,
            evidence=self.evidence(),
            approval_public_id=approval.public_id,
            decision_code="APPROVE",
        )
        with self.assertRaises(ValidationError):
            transition_revision(
                context=checker,
                evidence=self.evidence(),
                revision_public_id=revision.public_id,
                target_status_code="ISSUED",
                expected_version=99,
            )

    def test_revision_rejects_invalid_checksum(self):
        company = self.company("AAA")
        policy = self.policy(company)
        document = ControlledDocument.objects.create(
            company=company,
            policy=policy,
            document_number="DOC-001",
            discipline_code="CIVIL",
            document_type_code="DRAWING",
            title="Foundation drawing",
            status_code="DRAFT",
        )
        revision = DocumentRevision(
            company=company,
            policy=policy,
            document=document,
            revision_code="A",
            sequence_number=1,
            status_code="DRAFT",
            purpose_code="REVIEW",
            created_by_membership_public_id=uuid.uuid4(),
            checksum_sha256="not-a-checksum",
        )
        with self.assertRaises(ValidationError):
            revision.full_clean()
