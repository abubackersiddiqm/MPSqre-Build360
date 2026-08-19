import uuid
from collections.abc import Callable

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone
from rest_framework.test import APIClient

from modules.identity.application.tokens import TokenPair
from modules.identity.models import Permission, Role, RolePermission, User
from modules.tenant.application.memberships import assign_role
from modules.tenant.models import Company, Membership, MembershipRole


@pytest.mark.django_db
def test_company_header_is_not_authorization(
    api_client: APIClient,
    company_factory: Callable[..., Company],
    user_factory: Callable[..., User],
    membership_factory: Callable[[User, Company], Membership],
    token_pair_factory: Callable[[User], TokenPair],
) -> None:
    user = user_factory()
    allowed = company_factory(display_name="Allowed")
    denied = company_factory(display_name="Denied")
    membership_factory(user, allowed)
    pair = token_pair_factory(user)

    response = api_client.get(
        "/api/v1/companies/current",
        headers={
            "Authorization": f"Bearer {pair.access_token}",
            "X-Company-Id": str(denied.public_id),
        },
    )

    assert response.status_code == 404
    assert "Denied" not in response.content.decode()


@pytest.mark.django_db
def test_active_membership_resolves_company_context(
    api_client: APIClient,
    company_factory: Callable[..., Company],
    user_factory: Callable[..., User],
    membership_factory: Callable[[User, Company], Membership],
    token_pair_factory: Callable[[User], TokenPair],
) -> None:
    user = user_factory()
    company = company_factory()
    membership_factory(user, company)
    pair = token_pair_factory(user)

    response = api_client.get(
        "/api/v1/companies/current",
        headers={
            "Authorization": f"Bearer {pair.access_token}",
            "X-Company-Id": str(company.public_id),
        },
    )

    assert response.status_code == 200
    assert response.data["public_id"] == str(company.public_id)


@pytest.mark.django_db
def test_suspended_membership_is_concealed(
    api_client: APIClient,
    company_factory: Callable[..., Company],
    user_factory: Callable[..., User],
    membership_factory: Callable[[User, Company], Membership],
    token_pair_factory: Callable[[User], TokenPair],
) -> None:
    user = user_factory()
    company = company_factory()
    membership = membership_factory(user, company)
    membership.suspended_at = timezone.now()
    membership.save(update_fields=["suspended_at"])
    pair = token_pair_factory(user)

    response = api_client.get(
        "/api/v1/companies/current",
        headers={
            "Authorization": f"Bearer {pair.access_token}",
            "X-Company-Id": str(company.public_id),
        },
    )

    assert response.status_code == 404


@pytest.mark.django_db
def test_capabilities_come_from_permission_grants_not_role_name(
    api_client: APIClient,
    company_factory: Callable[..., Company],
    user_factory: Callable[..., User],
    membership_factory: Callable[[User, Company], Membership],
    token_pair_factory: Callable[[User], TokenPair],
) -> None:
    user = user_factory()
    company = company_factory()
    membership = membership_factory(user, company)
    permission = Permission.objects.create(
        code="company.read",
        description="Read company configuration",
    )
    role = Role.objects.create(
        company_public_id=company.public_id,
        code="tenant-configured-code",
        name="A tenant-selected label",
        effective_from=timezone.now(),
    )
    RolePermission.objects.create(role=role, permission=permission)
    MembershipRole.objects.create(
        membership=membership,
        role_public_id=role.public_id,
        assigned_by_public_id=uuid.uuid4(),
        effective_from=timezone.now(),
    )
    pair = token_pair_factory(user)

    response = api_client.get(
        "/api/v1/companies/current/capabilities",
        headers={
            "Authorization": f"Bearer {pair.access_token}",
            "X-Company-Id": str(company.public_id),
        },
    )

    assert response.status_code == 200
    assert response.data == {"permissions": ["company.read"]}


@pytest.mark.django_db
def test_role_assignment_rejects_cross_company_reference(
    company_factory: Callable[..., Company],
    user_factory: Callable[..., User],
    membership_factory: Callable[[User, Company], Membership],
) -> None:
    membership = membership_factory(user_factory(), company_factory())
    other_company = company_factory()
    role = Role.objects.create(
        company_public_id=other_company.public_id,
        code="other-company-role",
        name="Other company role",
        effective_from=timezone.now(),
    )

    with pytest.raises(ValidationError, match="cross companies"):
        assign_role(
            membership=membership,
            role=role,
            assigned_by_public_id=uuid.uuid4(),
            correlation_id=uuid.uuid4(),
        )
