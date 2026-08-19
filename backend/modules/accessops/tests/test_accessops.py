import uuid

import pytest
from django.core.exceptions import ValidationError as DjangoValidationError

from modules.accessops.application.services import (
    accept_invitation,
    create_company_with_admin_invitation,
    create_invitation,
    create_role,
)
from modules.accessops.models import PlatformOperator
from modules.identity.models import Permission, RolePermission, User
from modules.tenant.models import Company

pytestmark = pytest.mark.django_db


def create_operator() -> PlatformOperator:
    user = User.objects.create_user(
        email="operator@example.test", password="StrongPassword123", display_name="Operator"
    )
    return PlatformOperator.objects.create(user=user, operator_type_code="ROOT_OPERATOR")


def test_platform_operator_creates_company_and_admin_accepts_invitation():
    """B360-P28-001 through B360-P28-004."""
    operator = create_operator()
    Permission.objects.get_or_create(
        code="access.view", defaults={"description": "View access", "data_class": "ACCESS"}
    )
    company, invitation, token = create_company_with_admin_invitation(
        code="ACME",
        legal_name="Acme Construction Private Limited",
        display_name="Acme Construction",
        locale="en-IN",
        timezone_name="Asia/Kolkata",
        currency="INR",
        unit_system_code="METRIC",
        fiscal_year_start_month=4,
        plan_code="PILOT_360",
        admin_email="admin@acme.test",
        admin_display_name="Acme Admin",
        admin_employee_number="ACME-001",
        actor_public_id=operator.user.public_id,
        correlation_id=uuid.uuid4(),
    )
    user, membership = accept_invitation(
        raw_token=token, password="AcmePassword123", correlation_id=uuid.uuid4()
    )
    invitation.refresh_from_db()
    assert company.code == "ACME"
    assert invitation.accepted_at is not None
    assert membership.company == company
    assert membership.user == user
    assert membership.role_assignments.exists()
    assert membership.employee.employee_number == "ACME-001"


def test_company_invitation_rejects_cross_tenant_role():
    """B360-P28-005 and B360-P28-010."""
    operator = create_operator()
    company_a = Company.objects.create(
        code="A", legal_name="A", display_name="A", locale="en-IN", timezone="UTC",
        currency="INR", unit_system_code="METRIC", fiscal_year_start_month=1
    )
    company_b = Company.objects.create(
        code="B", legal_name="B", display_name="B", locale="en-IN", timezone="UTC",
        currency="INR", unit_system_code="METRIC", fiscal_year_start_month=1
    )
    permission = Permission.objects.create(code="sample.view", description="sample")
    role_b = create_role(
        company=company_b, code="VIEWER", name="Viewer", permission_codes=[permission.code],
        actor_public_id=operator.user.public_id, correlation_id=uuid.uuid4()
    )
    with pytest.raises(DjangoValidationError):
        create_invitation(
            company=company_a, email="person@example.test", display_name="Person",
            invitation_type_code="EMPLOYEE", role_public_ids=[role_b.public_id],
            employee_number="", job_title="", invited_by_public_id=operator.user.public_id,
            correlation_id=uuid.uuid4()
        )


def test_role_publication_is_versioned():
    """B360-P28-006."""
    operator = create_operator()
    company = Company.objects.create(
        code="V", legal_name="V", display_name="V", locale="en-IN", timezone="UTC",
        currency="INR", unit_system_code="METRIC", fiscal_year_start_month=1
    )
    permission = Permission.objects.create(code="work.view", description="View work")
    first = create_role(
        company=company, code="ENGINEER", name="Engineer", permission_codes=[permission.code],
        actor_public_id=operator.user.public_id, correlation_id=uuid.uuid4()
    )
    second = create_role(
        company=company, code="ENGINEER", name="Site Engineer", permission_codes=[permission.code],
        actor_public_id=operator.user.public_id, correlation_id=uuid.uuid4()
    )
    first.refresh_from_db()
    assert first.retired_at is not None
    assert second.version == 2
    assert RolePermission.objects.filter(role=second, permission=permission).exists()


def test_administrator_cannot_suspend_own_membership():
    """B360-P28-011 prevents administrator self-lockout."""
    from django.core.exceptions import ValidationError
    from django.utils import timezone

    from modules.accessops.application.services import set_membership_status
    from modules.tenant.models import Membership

    operator = create_operator()
    company = Company.objects.create(
        code="SELF", legal_name="Self", display_name="Self", locale="en-IN", timezone="UTC",
        currency="INR", unit_system_code="METRIC", fiscal_year_start_month=1
    )
    membership = Membership.objects.create(
        company=company, user=operator.user, effective_from=timezone.now()
    )
    with pytest.raises(ValidationError):
        set_membership_status(
            membership=membership,
            status_code="SUSPENDED",
            actor_public_id=operator.user.public_id,
            correlation_id=uuid.uuid4(),
        )


def test_invitation_requires_all_roles_to_remain_active():
    """B360-P28-004 rejects stale invitations after role retirement."""
    from django.core.exceptions import ValidationError

    operator = create_operator()
    company = Company.objects.create(
        code="STALE", legal_name="Stale", display_name="Stale", locale="en-IN", timezone="UTC",
        currency="INR", unit_system_code="METRIC", fiscal_year_start_month=1
    )
    permission = Permission.objects.create(code="stale.view", description="View")
    first = create_role(
        company=company, code="VIEWER", name="Viewer", permission_codes=[permission.code],
        actor_public_id=operator.user.public_id, correlation_id=uuid.uuid4()
    )
    _, token = create_invitation(
        company=company, email="stale@example.test", display_name="Stale User",
        invitation_type_code="EMPLOYEE", role_public_ids=[first.public_id],
        employee_number="STALE-001", job_title="Viewer",
        invited_by_public_id=operator.user.public_id, correlation_id=uuid.uuid4()
    )
    create_role(
        company=company, code="VIEWER", name="Viewer v2", permission_codes=[permission.code],
        actor_public_id=operator.user.public_id, correlation_id=uuid.uuid4()
    )
    with pytest.raises(ValidationError):
        accept_invitation(
            raw_token=token, password="StalePassword123", correlation_id=uuid.uuid4()
        )


def test_existing_identity_must_confirm_current_password():
    """Invitation acceptance is not a password-reset channel."""
    from django.core.exceptions import ValidationError

    operator = create_operator()
    existing = User.objects.create_user(
        email="existing@example.test", password="ExistingPassword123", display_name="Existing"
    )
    company = Company.objects.create(
        code="EXIST", legal_name="Existing Co", display_name="Existing Co", locale="en-IN",
        timezone="UTC", currency="INR", unit_system_code="METRIC", fiscal_year_start_month=1
    )
    permission = Permission.objects.create(code="existing.view", description="View")
    role = create_role(
        company=company, code="VIEWER", name="Viewer", permission_codes=[permission.code],
        actor_public_id=operator.user.public_id, correlation_id=uuid.uuid4()
    )
    invitation, token = create_invitation(
        company=company, email=existing.email, display_name="Existing",
        invitation_type_code="EMPLOYEE", role_public_ids=[role.public_id],
        employee_number="EXIST-001", job_title="Viewer",
        invited_by_public_id=operator.user.public_id, correlation_id=uuid.uuid4()
    )
    with pytest.raises(ValidationError):
        accept_invitation(
            raw_token=token, password="WrongPassword123", correlation_id=uuid.uuid4()
        )
    invitation.refresh_from_db()
    assert invitation.accepted_at is None
