import uuid

import pytest

from modules.accessops.application.services import (
    accept_invitation,
    create_company_with_admin_invitation,
    set_company_feature_preset,
)
from modules.accessops.models import CompanyAccessProfile, PlatformOperator
from modules.identity.application.permissions import effective_permission_codes
from modules.identity.models import Permission, Role, RolePermission
from modules.tenant.application.memberships import assign_role
from modules.subscription.application.feature_control import (
    append_feature_override,
    apply_feature_preset,
    feature_enabled,
    feature_matrix,
)

pytestmark = pytest.mark.django_db


def authorize(client, token_pair, company):
    client.credentials(
        HTTP_AUTHORIZATION=f"Bearer {token_pair.access_token}",
        HTTP_X_COMPANY_ID=str(company.public_id),
        HTTP_X_REQUEST_ID=str(uuid.uuid4()),
    )


def authorize_platform(client, token_pair):
    client.credentials(
        HTTP_AUTHORIZATION=f"Bearer {token_pair.access_token}",
        HTTP_X_REQUEST_ID=str(uuid.uuid4()),
    )


def test_crm_only_preset_disables_construction_modules(company_factory, user_factory):
    company = company_factory()
    actor = user_factory(email="v20g-preset@example.test")

    apply_feature_preset(
        company=company,
        preset_code="CRM_ONLY",
        reason_code="uat",
        set_by_public_id=actor.public_id,
        correlation_id=uuid.uuid4(),
    )

    assert feature_enabled(company=company, code="crm.core") is True
    assert feature_enabled(company=company, code="crm.whatsapp") is True
    assert feature_enabled(company=company, code="module.delivery") is False
    assert feature_enabled(company=company, code="module.finance") is False

    matrix = feature_matrix(company=company)
    modules = {item["code"]: item["enabled"] for item in matrix["items"] if item["kind"] == "MODULE"}
    assert modules["crm.core"] is True
    assert modules["module.delivery"] is False
    assert modules["module.risk_transfer"] is False
    assert {item["code"] for item in matrix["presets"]} == {"CRM_ONLY", "CONSTRUCTION_CORE", "FULL_BUILD360"}


def test_crm_addon_dependency_cannot_bypass_crm_core(company_factory, user_factory):
    company = company_factory()
    actor = user_factory(email="v20g-dependency@example.test")
    append_feature_override(
        company=company,
        code="crm.whatsapp",
        enabled=True,
        reason_code="addon-on",
        set_by_public_id=actor.public_id,
        correlation_id=uuid.uuid4(),
    )
    append_feature_override(
        company=company,
        code="crm.core",
        enabled=False,
        reason_code="crm-off",
        set_by_public_id=actor.public_id,
        correlation_id=uuid.uuid4(),
    )

    assert feature_enabled(company=company, code="crm.whatsapp") is False
    row = next(item for item in feature_matrix(company=company)["items"] if item["code"] == "crm.whatsapp")
    assert row["configured_enabled"] is True
    assert row["enabled"] is False
    assert row["source"] == "dependency:crm.core"


def test_root_operator_can_apply_crm_only_package(
    api_client,
    company_factory,
    user_factory,
    token_pair_factory,
):
    company = company_factory()
    operator_user = user_factory(email="v20g-root@example.test")
    PlatformOperator.objects.create(user=operator_user, operator_type_code="ROOT_OPERATOR")
    authorize_platform(api_client, token_pair_factory(operator_user))

    response = api_client.post(
        f"/api/v1/access-control/platform/companies/{company.public_id}/feature-matrix",
        {"preset_code": "CRM_ONLY", "reason_code": "commercial-package"},
        format="json",
    )
    assert response.status_code == 200
    rows = {item["code"]: item for item in response.json()["items"]}
    assert rows["crm.core"]["enabled"] is True
    assert rows["module.delivery"]["enabled"] is False
    assert rows["module.finance"]["enabled"] is False


def test_disabled_delivery_module_blocks_project_api_even_with_permission(
    api_client,
    company_factory,
    user_factory,
    permission_grant_factory,
    token_pair_factory,
):
    company = company_factory()
    user = user_factory(email="v20g-project-block@example.test")
    permission_grant_factory(user, company, ["project.dashboard.read"])
    append_feature_override(
        company=company,
        code="module.delivery",
        enabled=False,
        reason_code="crm-only",
        set_by_public_id=user.public_id,
        correlation_id=uuid.uuid4(),
    )
    authorize(api_client, token_pair_factory(user), company)

    response = api_client.get("/api/v1/projects/summary")
    assert response.status_code == 403


def test_cloud_operations_are_platform_operator_only_even_with_tenant_permission(
    api_client,
    company_factory,
    user_factory,
    permission_grant_factory,
    token_pair_factory,
):
    company = company_factory()
    user = user_factory(email="v20g-cloud-block@example.test")
    permission_grant_factory(user, company, ["cloudops.dashboard.read"])
    authorize(api_client, token_pair_factory(user), company)

    response = api_client.get("/api/v1/cloudops/summary")
    assert response.status_code == 403


def test_new_company_administrator_is_user_admin_not_business_superuser(user_factory):
    operator_user = user_factory(email="v20g-company-admin-scope@example.test")
    operator = PlatformOperator.objects.create(user=operator_user, operator_type_code="ROOT_OPERATOR")

    company, admin_invitation, _ = create_company_with_admin_invitation(
        code="V20GADM",
        legal_name="V20G Admin Scope Private Limited",
        display_name="V20G Admin Scope",
        locale="en-IN",
        timezone_name="Asia/Kolkata",
        currency="INR",
        unit_system_code="METRIC",
        fiscal_year_start_month=4,
        plan_code="CRM_ONLY",
        admin_email="company-admin-v20g@example.test",
        admin_display_name="Company Admin",
        admin_employee_number="ADM-001",
        actor_public_id=operator.user.public_id,
        correlation_id=uuid.uuid4(),
        preset_code="CRM_ONLY",
    )
    role = Role.objects.get(company_public_id=company.public_id, code="COMPANY_ADMIN", retired_at__isnull=True)
    permission_codes = set(RolePermission.objects.filter(role=role).values_list("permission__code", flat=True))
    assert permission_codes == {
        "access.view",
        "access.user.manage",
        "tenant.branding.read",
        "tenant.branding.manage",
        "tenant.domain.read",
        "tenant.domain.manage",
    }
    assert "crm.dashboard.read" not in permission_codes
    assert "release.view" not in permission_codes

    company_user = Role.objects.get(company_public_id=company.public_id, code="COMPANY_USER", retired_at__isnull=True)
    user_permission_codes = set(
        RolePermission.objects.filter(role=company_user).values_list("permission__code", flat=True)
    )
    assert "crm.dashboard.read" in user_permission_codes
    assert "project.dashboard.read" not in user_permission_codes
    assert "finance.dashboard.read" not in user_permission_codes
    assert "release.view" not in user_permission_codes
    assert set(admin_invitation.role_public_ids) == {str(role.public_id), str(company_user.public_id)}


def test_package_change_republishes_default_company_user_access(user_factory):
    operator_user = user_factory(email="v20g-role-sync@example.test")
    operator = PlatformOperator.objects.create(user=operator_user, operator_type_code="ROOT_OPERATOR")
    company, _, _ = create_company_with_admin_invitation(
        code="V20GSYNC",
        legal_name="V20G Role Sync Private Limited",
        display_name="V20G Role Sync",
        locale="en-IN",
        timezone_name="Asia/Kolkata",
        currency="INR",
        unit_system_code="METRIC",
        fiscal_year_start_month=4,
        plan_code="FULL_BUILD360",
        admin_email="admin-sync-v20g@example.test",
        admin_display_name="Company Admin",
        admin_employee_number="ADM-002",
        actor_public_id=operator.user.public_id,
        correlation_id=uuid.uuid4(),
        preset_code="FULL_BUILD360",
    )
    before = Role.objects.get(company_public_id=company.public_id, code="COMPANY_USER", retired_at__isnull=True)
    before_codes = set(RolePermission.objects.filter(role=before).values_list("permission__code", flat=True))
    assert "project.dashboard.read" in before_codes
    assert "finance.dashboard.read" in before_codes

    set_company_feature_preset(
        company=company,
        preset_code="CRM_ONLY",
        reason_code="downgrade-to-crm",
        actor_public_id=operator.user.public_id,
        correlation_id=uuid.uuid4(),
    )
    after = Role.objects.get(company_public_id=company.public_id, code="COMPANY_USER", retired_at__isnull=True)
    after_codes = set(RolePermission.objects.filter(role=after).values_list("permission__code", flat=True))
    assert after.version > before.version
    assert "crm.dashboard.read" in after_codes
    assert "project.dashboard.read" not in after_codes
    assert "finance.dashboard.read" not in after_codes



def test_primary_admin_effective_access_tracks_package_without_manual_permissions(user_factory):
    operator_user = user_factory(email="v20g-primary-effective@example.test")
    operator = PlatformOperator.objects.create(
        user=operator_user,
        operator_type_code="ROOT_OPERATOR",
    )
    company, _, raw_token = create_company_with_admin_invitation(
        code="V20GEFF",
        legal_name="V20G Effective Access Private Limited",
        display_name="V20G Effective Access",
        locale="en-IN",
        timezone_name="Asia/Kolkata",
        currency="INR",
        unit_system_code="METRIC",
        fiscal_year_start_month=4,
        plan_code="FULL_BUILD360",
        admin_email="primary-effective-v20g@example.test",
        admin_display_name="Primary Company Admin",
        admin_employee_number="ADM-003",
        actor_public_id=operator.user.public_id,
        correlation_id=uuid.uuid4(),
        preset_code="FULL_BUILD360",
    )
    admin_user, membership = accept_invitation(
        raw_token=raw_token,
        password="A-secure-primary-admin-password-42!",
        correlation_id=uuid.uuid4(),
    )

    set_company_feature_preset(
        company=company,
        preset_code="CRM_ONLY",
        reason_code="crm-only-production-contract",
        actor_public_id=operator.user.public_id,
        correlation_id=uuid.uuid4(),
    )

    active_role_ids = membership.role_assignments.filter(
        effective_to__isnull=True
    ).values_list("role_public_id", flat=True)
    role_codes = set(
        Role.objects.filter(
            public_id__in=active_role_ids,
            retired_at__isnull=True,
        ).values_list("code", flat=True)
    )
    assert role_codes == {"COMPANY_ADMIN", "COMPANY_USER"}

    permissions = effective_permission_codes(
        company_public_id=company.public_id,
        role_public_ids=active_role_ids,
    )
    assert "access.user.manage" in permissions
    assert "crm.dashboard.read" in permissions
    assert "crm.contact.read" in permissions
    assert "project.dashboard.read" not in permissions
    assert "finance.dashboard.read" not in permissions
    assert admin_user.email == "primary-effective-v20g@example.test"


def test_package_reconciliation_repairs_legacy_company_administrator(
    company_factory,
    user_factory,
    membership_factory,
):
    company = company_factory(code="V20GLEGACY")
    operator_user = user_factory(email="v20g-legacy-root@example.test")
    operator = PlatformOperator.objects.create(
        user=operator_user,
        operator_type_code="ROOT_OPERATOR",
    )
    admin_user = user_factory(email="legacy-admin-v20g@example.test")
    membership = membership_factory(admin_user, company)
    CompanyAccessProfile.objects.create(
        company=company,
        plan_code="CRM_ONLY",
        onboarding_status_code="ADMIN_ACTIVE",
        primary_admin_email=admin_user.email,
        created_by_public_id=operator.user.public_id,
    )
    legacy_role = Role.objects.create(
        company_public_id=company.public_id,
        code="company_administrator",
        name="Company Administrator",
        effective_from=membership.effective_from,
    )
    access_view = Permission.objects.get(code="access.view")
    RolePermission.objects.create(role=legacy_role, permission=access_view)
    assign_role(
        membership=membership,
        role=legacy_role,
        assigned_by_public_id=admin_user.public_id,
        correlation_id=uuid.uuid4(),
    )

    set_company_feature_preset(
        company=company,
        preset_code="CRM_ONLY",
        reason_code="repair-legacy-admin",
        actor_public_id=operator.user.public_id,
        correlation_id=uuid.uuid4(),
    )

    legacy_role.refresh_from_db()
    assert legacy_role.retired_at is not None

    active_role_ids = list(
        membership.role_assignments.filter(effective_to__isnull=True).values_list(
            "role_public_id", flat=True
        )
    )
    active_codes = set(
        Role.objects.filter(
            public_id__in=active_role_ids,
            retired_at__isnull=True,
        ).values_list("code", flat=True)
    )
    assert active_codes == {"COMPANY_ADMIN", "COMPANY_USER"}

    permissions = effective_permission_codes(
        company_public_id=company.public_id,
        role_public_ids=active_role_ids,
    )
    assert "access.user.manage" in permissions
    assert "crm.dashboard.read" in permissions
    assert "project.dashboard.read" not in permissions
