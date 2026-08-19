import uuid
from collections.abc import Callable
from datetime import timedelta
from typing import Any

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from modules.identity.application.tokens import TokenPair, issue_session
from modules.identity.models import User
from modules.tenant.models import Company, Membership


@pytest.fixture
def api_client() -> APIClient:
    return APIClient()


@pytest.fixture
def company_factory(db: None) -> Callable[..., Company]:
    def create(**overrides: Any) -> Company:
        values: dict[str, Any] = {
            "code": f"C-{uuid.uuid4().hex[:8]}",
            "legal_name": "Example Construction Private Limited",
            "display_name": "Example Construction",
            "locale": "en-IN",
            "timezone": "Asia/Kolkata",
            "currency": "INR",
            "unit_system_code": "metric",
            "fiscal_year_start_month": 4,
        }
        values.update(overrides)
        return Company.objects.create(**values)

    return create


@pytest.fixture
def user_factory(db: None) -> Callable[..., User]:
    def create(**overrides: Any) -> User:
        password = overrides.pop("password", "A-secure-test-password-42!")
        values: dict[str, Any] = {
            "email": f"user-{uuid.uuid4().hex[:8]}@example.test",
            "display_name": "Test User",
        }
        values.update(overrides)
        return User.objects.create_user(password=password, **values)

    return create


@pytest.fixture
def membership_factory(
    db: None,
) -> Callable[[User, Company], Membership]:
    def create(user: User, company: Company) -> Membership:
        return Membership.objects.create(
            user=user,
            company=company,
            effective_from=timezone.now() - timedelta(minutes=1),
        )

    return create


@pytest.fixture
def token_pair_factory(
    db: None,
) -> Callable[[User], TokenPair]:
    def create(user: User) -> TokenPair:
        correlation_id = uuid.uuid4()
        return issue_session(
            user=user,
            device_id=uuid.uuid4(),
            device_name="Test browser",
            ip_address="127.0.0.1",
            user_agent="pytest",
            correlation_id=correlation_id,
        )

    return create


@pytest.fixture
def permission_grant_factory(
    db: None,
) -> Callable[[User, Company, list[str]], Membership]:
    from modules.identity.models import Permission, Role, RolePermission
    from modules.tenant.application.memberships import assign_role

    def grant(user: User, company: Company, permission_codes: list[str]) -> Membership:
        membership = Membership.objects.filter(user=user, company=company).first()
        if membership is None:
            membership = Membership.objects.create(
                user=user,
                company=company,
                effective_from=timezone.now() - timedelta(minutes=1),
            )
        role = Role.objects.create(
            company_public_id=company.public_id,
            code=f"test-role-{uuid.uuid4().hex[:8]}",
            name="Test role",
            effective_from=timezone.now() - timedelta(minutes=1),
        )
        for code in permission_codes:
            permission, _ = Permission.objects.get_or_create(
                code=code,
                defaults={"description": f"Test permission {code}"},
            )
            RolePermission.objects.create(role=role, permission=permission)
        assign_role(
            membership=membership,
            role=role,
            assigned_by_public_id=user.public_id,
            correlation_id=uuid.uuid4(),
        )
        return membership

    return grant
