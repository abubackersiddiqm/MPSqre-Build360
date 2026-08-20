from __future__ import annotations

import uuid

from django.conf import settings
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from modules.accessops.application.authorization import require_platform_operator
from modules.accessops.application.invitation_delivery import (
    deliver_invitation_email,
    invitation_acceptance_url,
    preview_invitation,
)
from modules.accessops.application.managed_access import (
    managed_access_history,
    managed_access_matrix,
    managed_role_public_ids_for_levels,
    set_membership_managed_access,
)
from modules.accessops.application.selectors import company_overview, platform_overview
from modules.accessops.application.services import (
    accept_invitation,
    create_company_with_admin_invitation,
    create_invitation,
    create_role,
    current_company_user_role,
    regenerate_company_user_invitation,
    regenerate_primary_admin_invitation,
    replace_membership_roles,
    revoke_invitation,
    set_company_active,
    set_company_feature_override,
    set_company_feature_preset,
    set_membership_status,
    transfer_primary_company_admin,
)
from modules.accessops.models import AccessInvitation, CompanyAccessProfile, PlatformOperator
from modules.identity.application.tokens import AccessPrincipal
from modules.subscription.application.feature_control import feature_matrix
from modules.tenant.api.base import TenantScopedAPIView
from modules.tenant.models import Company, Membership

from .serializers import (
    CompanyCreateSerializer,
    CompanyFeatureOverrideSerializer,
    CompanyFeaturePresetSerializer,
    CompanyStatusSerializer,
    InvitationAcceptSerializer,
    InvitationCreateSerializer,
    ManagedAccessProfileSerializer,
    MembershipRolesSerializer,
    MembershipStatusSerializer,
    PrimaryAdminInviteRegenerateSerializer,
    PrimaryAdminTransferSerializer,
    RoleCreateSerializer,
    uuid_list,
)


def correlation_id(request: Request) -> uuid.UUID:
    return getattr(request, "request_id", uuid.uuid4())


def translate_validation_error(error: DjangoValidationError) -> ValidationError:
    if hasattr(error, "message_dict"):
        return ValidationError(error.message_dict)
    return ValidationError(error.messages if hasattr(error, "messages") else str(error))


def invitation_link_material_allowed() -> bool:
    environment = str(
        getattr(settings, "BUILD360_ENVIRONMENT", "development") or "development"
    ).strip().lower()
    return environment in {"development", "demo"}


def invitation_response(invitation: AccessInvitation, raw_token: str) -> dict[str, object]:
    delivery = deliver_invitation_email(invitation=invitation, raw_token=raw_token)
    safe_delivery = {
        key: value
        for key, value in delivery.items()
        if key != "acceptance_url"
    }
    payload: dict[str, object] = {
        "public_id": str(invitation.public_id),
        "email": invitation.email,
        "expires_at": invitation.expires_at.isoformat(),
        "delivery": safe_delivery,
    }
    if invitation_link_material_allowed():
        payload["acceptance_token"] = raw_token
        payload["acceptance_url"] = invitation_acceptance_url(
            company=invitation.company,
            raw_token=raw_token,
        )
    return payload


class PlatformAPIView(APIView):
    operator: PlatformOperator

    def initial(self, request: Request, *args: object, **kwargs: object) -> None:
        super().initial(request, *args, **kwargs)
        self.operator = require_platform_operator(request)

    def require_root_operator(self) -> None:
        if self.operator.operator_type_code != "ROOT_OPERATOR":
            raise PermissionDenied("ROOT_OPERATOR access is required for SaaS feature control")


class CompanyAccessAPIView(TenantScopedAPIView):
    required_permission = "access.view"

    def initial(self, request: Request, *args: object, **kwargs: object) -> None:
        super().initial(request, *args, **kwargs)
        self.tenant_context.require(self.required_permission)


class PlatformSessionView(APIView):
    def get(self, request: Request) -> Response:
        if not isinstance(request.auth, AccessPrincipal):
            raise PermissionDenied("Authentication required")
        operator = PlatformOperator.objects.filter(
            user=request.auth.user, is_active=True
        ).first()
        return Response(
            {
                "is_platform_operator": operator is not None,
                "operator": (
                    {
                        "public_id": str(operator.public_id),
                        "operator_type_code": operator.operator_type_code,
                    }
                    if operator
                    else None
                ),
            }
        )


class PlatformOverviewView(PlatformAPIView):
    def get(self, request: Request) -> Response:
        return Response(platform_overview())


class PlatformCompanyListCreateView(PlatformAPIView):
    def get(self, request: Request) -> Response:
        return Response(platform_overview())

    def post(self, request: Request) -> Response:
        serializer = CompanyCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            company, invitation, raw_token = create_company_with_admin_invitation(
                code=serializer.validated_data["code"],
                legal_name=serializer.validated_data["legal_name"],
                display_name=serializer.validated_data["display_name"],
                locale=serializer.validated_data["locale"],
                timezone_name=serializer.validated_data["timezone"],
                currency=serializer.validated_data["currency"],
                unit_system_code=serializer.validated_data["unit_system_code"],
                fiscal_year_start_month=serializer.validated_data["fiscal_year_start_month"],
                plan_code=serializer.validated_data.get("plan_code", ""),
                admin_email=serializer.validated_data["admin_email"],
                admin_display_name=serializer.validated_data["admin_display_name"],
                admin_employee_number=serializer.validated_data.get("admin_employee_number", ""),
                preset_code=serializer.validated_data.get("preset_code", "FULL_BUILD360"),
                actor_public_id=self.operator.user.public_id,
                correlation_id=correlation_id(request),
            )
        except DjangoValidationError as error:
            raise translate_validation_error(error) from error
        return Response(
            {
                "company": {
                    "public_id": str(company.public_id),
                    "code": company.code,
                    "display_name": company.display_name,
                },
                "invitation": invitation_response(invitation, raw_token),
            },
            status=201,
        )


class PlatformCompanyStatusView(PlatformAPIView):
    def patch(self, request: Request, company_id: uuid.UUID) -> Response:
        serializer = CompanyStatusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        company = Company.objects.filter(public_id=company_id).first()
        if not company:
            raise NotFound("Resource not found")
        company = set_company_active(
            company=company,
            is_active=serializer.validated_data["is_active"],
            actor_public_id=self.operator.user.public_id,
            correlation_id=correlation_id(request),
            reason_code=serializer.validated_data.get("reason_code", ""),
        )
        return Response({"public_id": str(company.public_id), "is_active": company.is_active})


class PlatformCompanyFeatureMatrixView(PlatformAPIView):
    def _company(self, company_id: uuid.UUID) -> Company:
        company = Company.objects.filter(public_id=company_id).first()
        if company is None:
            raise NotFound("Resource not found")
        return company

    def get(self, request: Request, company_id: uuid.UUID) -> Response:
        self.require_root_operator()
        return Response(feature_matrix(company=self._company(company_id)))

    def patch(self, request: Request, company_id: uuid.UUID) -> Response:
        self.require_root_operator()
        serializer = CompanyFeatureOverrideSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        company = self._company(company_id)
        try:
            set_company_feature_override(
                company=company,
                feature_code=serializer.validated_data["feature_code"],
                enabled=serializer.validated_data["enabled"],
                reason_code=serializer.validated_data["reason_code"],
                actor_public_id=self.operator.user.public_id,
                correlation_id=correlation_id(request),
            )
        except DjangoValidationError as error:
            raise translate_validation_error(error) from error
        return Response(feature_matrix(company=company))

    def post(self, request: Request, company_id: uuid.UUID) -> Response:
        self.require_root_operator()
        serializer = CompanyFeaturePresetSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        company = self._company(company_id)
        try:
            set_company_feature_preset(
                company=company,
                preset_code=serializer.validated_data["preset_code"],
                reason_code=serializer.validated_data["reason_code"],
                actor_public_id=self.operator.user.public_id,
                correlation_id=correlation_id(request),
            )
        except DjangoValidationError as error:
            raise translate_validation_error(error) from error
        return Response(feature_matrix(company=company))


class PlatformPrimaryAdminInvitationView(PlatformAPIView):
    def post(self, request: Request, company_id: uuid.UUID) -> Response:
        self.require_root_operator()
        company = Company.objects.filter(public_id=company_id).first()
        if company is None:
            raise NotFound("Resource not found")
        serializer = PrimaryAdminInviteRegenerateSerializer(data=request.data or {})
        serializer.is_valid(raise_exception=True)
        try:
            invitation, raw_token = regenerate_primary_admin_invitation(
                company=company,
                actor_public_id=self.operator.user.public_id,
                correlation_id=correlation_id(request),
                ttl_hours=serializer.validated_data["ttl_hours"],
            )
        except DjangoValidationError as error:
            raise translate_validation_error(error) from error
        return Response(invitation_response(invitation, raw_token), status=201)


class PlatformPrimaryAdminTransferView(PlatformAPIView):
    def _company(self, company_id: uuid.UUID) -> Company:
        company = Company.objects.filter(public_id=company_id).first()
        if company is None:
            raise NotFound("Resource not found")
        return company

    def get(self, request: Request, company_id: uuid.UUID) -> Response:
        self.require_root_operator()
        company = self._company(company_id)
        now = timezone.now()
        profile = CompanyAccessProfile.objects.filter(company=company).first()
        current_email = profile.primary_admin_email.strip().lower() if profile else ""
        memberships = (
            Membership.objects.select_related("user")
            .filter(
                company=company,
                effective_from__lte=now,
                suspended_at__isnull=True,
                terminated_at__isnull=True,
                user__is_active=True,
            )
            .filter(Q(effective_to__isnull=True) | Q(effective_to__gt=now))
            .order_by("user__display_name", "user__email")
        )
        return Response(
            {
                "company": {
                    "public_id": str(company.public_id),
                    "code": company.code,
                    "display_name": company.display_name,
                },
                "current_primary_admin_email": current_email,
                "candidates": [
                    {
                        "membership_public_id": str(item.public_id),
                        "email": item.user.email,
                        "display_name": item.user.display_name,
                        "is_current_primary": item.user.email.strip().lower() == current_email,
                    }
                    for item in memberships
                ],
            }
        )

    def post(self, request: Request, company_id: uuid.UUID) -> Response:
        self.require_root_operator()
        company = self._company(company_id)
        serializer = PrimaryAdminTransferSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        membership = Membership.objects.select_related("user", "company").filter(
            company=company,
            public_id=serializer.validated_data["membership_public_id"],
        ).first()
        if membership is None:
            raise NotFound("Resource not found")
        try:
            result = transfer_primary_company_admin(
                company=company,
                membership=membership,
                actor_public_id=self.operator.user.public_id,
                correlation_id=correlation_id(request),
                reason_code=serializer.validated_data["reason_code"],
            )
        except DjangoValidationError as error:
            raise translate_validation_error(error) from error
        return Response(result)


class PlatformCompanyAdminInviteView(PlatformAPIView):
    def post(self, request: Request, company_id: uuid.UUID) -> Response:
        company = Company.objects.filter(public_id=company_id).first()
        if not company:
            raise NotFound("Resource not found")
        serializer = InvitationCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            invitation, raw_token = create_invitation(
                company=company,
                email=serializer.validated_data["email"],
                display_name=serializer.validated_data["display_name"],
                invitation_type_code="COMPANY_ADMIN",
                role_public_ids=uuid_list(serializer.validated_data["role_public_ids"]),
                employee_number=serializer.validated_data.get("employee_number", ""),
                job_title=serializer.validated_data.get("job_title", "Company Administrator"),
                invited_by_public_id=self.operator.user.public_id,
                correlation_id=correlation_id(request),
                ttl_hours=serializer.validated_data["ttl_hours"],
                actor_type="platform_operator",
            )
        except DjangoValidationError as error:
            raise translate_validation_error(error) from error
        return Response(invitation_response(invitation, raw_token), status=201)


class CompanyOverviewView(CompanyAccessAPIView):
    def get(self, request: Request) -> Response:
        payload = company_overview(self.tenant_context.company)
        if "access.role.manage" not in self.tenant_context.permission_codes():
            payload["permissions"] = []
            payload["summary"]["permission_catalog_count"] = 0
            for role in payload["roles"]:
                role["permission_codes"] = []
        return Response(payload)


class CompanyRoleListCreateView(CompanyAccessAPIView):
    required_permission = "access.role.manage"

    def get(self, request: Request) -> Response:
        return Response(company_overview(self.tenant_context.company))

    def post(self, request: Request) -> Response:
        serializer = RoleCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            role = create_role(
                company=self.tenant_context.company,
                code=serializer.validated_data["code"],
                name=serializer.validated_data["name"],
                permission_codes=list(dict.fromkeys(serializer.validated_data["permission_codes"])),
                actor_public_id=self.tenant_context.principal.user.public_id,
                correlation_id=correlation_id(request),
            )
        except DjangoValidationError as error:
            raise translate_validation_error(error) from error
        return Response(
            {"public_id": str(role.public_id), "code": role.code, "name": role.name, "version": role.version},
            status=201,
        )


class CompanyPeopleView(CompanyAccessAPIView):
    required_permission = "access.view"

    def get(self, request: Request) -> Response:
        return Response(company_overview(self.tenant_context.company))


class CompanyManagedAccessMatrixView(CompanyAccessAPIView):
    required_permission = "access.user.manage"

    def get(self, request: Request) -> Response:
        return Response(managed_access_matrix(self.tenant_context.company))


class CompanyMembershipManagedAccessView(CompanyAccessAPIView):
    required_permission = "access.user.manage"

    def post(self, request: Request, membership_id: uuid.UUID) -> Response:
        membership = Membership.objects.select_related("company", "user").filter(
            public_id=membership_id,
            company=self.tenant_context.company,
        ).first()
        if membership is None:
            raise NotFound("Resource not found")
        serializer = ManagedAccessProfileSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            levels = set_membership_managed_access(
                membership=membership,
                access_levels=serializer.validated_data["access_levels"],
                actor_public_id=self.tenant_context.principal.user.public_id,
                correlation_id=correlation_id(request),
                reason_code=serializer.validated_data["reason_code"],
            )
        except DjangoValidationError as error:
            raise translate_validation_error(error) from error
        return Response(
            {
                "membership_public_id": str(membership.public_id),
                "access_levels": levels,
            }
        )


class CompanyMembershipManagedAccessHistoryView(CompanyAccessAPIView):
    required_permission = "access.user.manage"

    def get(self, request: Request, membership_id: uuid.UUID) -> Response:
        membership = Membership.objects.select_related("company", "user").filter(
            public_id=membership_id,
            company=self.tenant_context.company,
        ).first()
        if membership is None:
            raise NotFound("Resource not found")
        return Response(
            managed_access_history(
                company=self.tenant_context.company,
                membership=membership,
                limit=50,
            )
        )


class CompanyInvitationListCreateView(CompanyAccessAPIView):
    required_permission = "access.user.manage"

    def get(self, request: Request) -> Response:
        return Response(company_overview(self.tenant_context.company))

    def post(self, request: Request) -> Response:
        serializer = InvitationCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        can_manage_roles = "access.role.manage" in self.tenant_context.permission_codes()
        supplied_role_ids = uuid_list(serializer.validated_data.get("role_public_ids", []))
        access_levels = serializer.validated_data.get("access_levels")
        if access_levels is not None:
            try:
                role_public_ids, _ = managed_role_public_ids_for_levels(
                    company=self.tenant_context.company,
                    access_levels=access_levels,
                    actor_public_id=self.tenant_context.principal.user.public_id,
                    correlation_id=correlation_id(request),
                )
            except DjangoValidationError as error:
                raise translate_validation_error(error) from error
        elif can_manage_roles and supplied_role_ids:
            role_public_ids = supplied_role_ids
        else:
            default_role = current_company_user_role(self.tenant_context.company)
            if default_role is None:
                raise ValidationError("Default Company User access level is not provisioned. Ask Build360 Super Admin to re-apply the company SaaS package.")
            role_public_ids = [default_role.public_id]
        try:
            invitation, raw_token = create_invitation(
                company=self.tenant_context.company,
                email=serializer.validated_data["email"],
                display_name=serializer.validated_data["display_name"],
                invitation_type_code=serializer.validated_data["invitation_type_code"],
                role_public_ids=role_public_ids,
                employee_number=serializer.validated_data.get("employee_number", ""),
                job_title=serializer.validated_data.get("job_title", ""),
                invited_by_public_id=self.tenant_context.principal.user.public_id,
                correlation_id=correlation_id(request),
                ttl_hours=serializer.validated_data["ttl_hours"],
            )
        except DjangoValidationError as error:
            raise translate_validation_error(error) from error
        return Response(invitation_response(invitation, raw_token), status=201)


class CompanyInvitationRegenerateView(CompanyAccessAPIView):
    required_permission = "access.user.manage"

    def post(self, request: Request, invitation_id: uuid.UUID) -> Response:
        invitation = AccessInvitation.objects.select_related("company").filter(
            public_id=invitation_id, company=self.tenant_context.company
        ).first()
        if not invitation:
            raise NotFound("Resource not found")
        serializer = PrimaryAdminInviteRegenerateSerializer(data=request.data or {})
        serializer.is_valid(raise_exception=True)
        try:
            regenerated, raw_token = regenerate_company_user_invitation(
                invitation=invitation,
                actor_public_id=self.tenant_context.principal.user.public_id,
                correlation_id=correlation_id(request),
                ttl_hours=serializer.validated_data["ttl_hours"],
            )
        except DjangoValidationError as error:
            raise translate_validation_error(error) from error
        return Response(invitation_response(regenerated, raw_token), status=201)


class CompanyInvitationRevokeView(CompanyAccessAPIView):
    required_permission = "access.user.manage"

    def post(self, request: Request, invitation_id: uuid.UUID) -> Response:
        invitation = AccessInvitation.objects.filter(
            public_id=invitation_id, company=self.tenant_context.company
        ).first()
        if not invitation:
            raise NotFound("Resource not found")
        try:
            revoke_invitation(
                invitation=invitation,
                actor_public_id=self.tenant_context.principal.user.public_id,
                correlation_id=correlation_id(request),
            )
        except DjangoValidationError as error:
            raise translate_validation_error(error) from error
        return Response(status=204)


class CompanyMembershipRolesView(CompanyAccessAPIView):
    required_permission = "access.role.manage"

    def post(self, request: Request, membership_id: uuid.UUID) -> Response:
        membership = Membership.objects.select_related("company").filter(
            public_id=membership_id, company=self.tenant_context.company
        ).first()
        if not membership:
            raise NotFound("Resource not found")
        serializer = MembershipRolesSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            replace_membership_roles(
                membership=membership,
                role_public_ids=uuid_list(serializer.validated_data["role_public_ids"]),
                actor_public_id=self.tenant_context.principal.user.public_id,
                correlation_id=correlation_id(request),
            )
        except DjangoValidationError as error:
            raise translate_validation_error(error) from error
        return Response(status=204)


class CompanyMembershipStatusView(CompanyAccessAPIView):
    required_permission = "access.user.manage"

    def patch(self, request: Request, membership_id: uuid.UUID) -> Response:
        membership = Membership.objects.filter(
            public_id=membership_id, company=self.tenant_context.company
        ).first()
        if not membership:
            raise NotFound("Resource not found")
        serializer = MembershipStatusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        status_code = serializer.validated_data["status_code"]
        try:
            set_membership_status(
                membership=membership,
                status_code=status_code,
                actor_public_id=self.tenant_context.principal.user.public_id,
                correlation_id=correlation_id(request),
                reason_code=serializer.validated_data.get("reason_code", ""),
            )
        except DjangoValidationError as error:
            raise translate_validation_error(error) from error
        return Response({"membership_public_id": str(membership.public_id), "status_code": status_code})


class InvitationPreviewView(APIView):
    permission_classes = [AllowAny]
    authentication_classes: list = []

    def get(self, request: Request) -> Response:
        raw_token = str(request.query_params.get("token", "")).strip()
        if len(raw_token) < 20:
            raise NotFound("Invitation is invalid or has expired")
        payload = preview_invitation(raw_token)
        if payload is None:
            raise NotFound("Invitation is invalid or has expired")
        return Response(payload)


class InvitationAcceptView(APIView):
    permission_classes = [AllowAny]
    authentication_classes: list[type] = []

    def post(self, request: Request) -> Response:
        serializer = InvitationAcceptSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            user, membership = accept_invitation(
                raw_token=serializer.validated_data["token"],
                password=serializer.validated_data["password"],
                correlation_id=correlation_id(request),
            )
        except DjangoValidationError as error:
            raise translate_validation_error(error) from error
        return Response(
            {
                "accepted": True,
                "user_public_id": str(user.public_id),
                "membership_public_id": str(membership.public_id),
                "company_public_id": str(membership.company.public_id),
            },
            status=201,
        )
