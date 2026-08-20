from __future__ import annotations

import uuid

from rest_framework import serializers


class CompanyCreateSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=50)
    legal_name = serializers.CharField(max_length=250)
    display_name = serializers.CharField(max_length=250)
    locale = serializers.CharField(max_length=35, default="en-IN")
    timezone = serializers.CharField(max_length=64, default="Asia/Kolkata")
    currency = serializers.CharField(min_length=3, max_length=3, default="INR")
    unit_system_code = serializers.CharField(max_length=50, default="METRIC")
    fiscal_year_start_month = serializers.IntegerField(min_value=1, max_value=12, default=4)
    plan_code = serializers.CharField(max_length=100, required=False, allow_blank=True)
    admin_email = serializers.EmailField(max_length=254)
    admin_display_name = serializers.CharField(max_length=200)
    admin_employee_number = serializers.CharField(max_length=50, required=False, allow_blank=True)
    preset_code = serializers.ChoiceField(choices=("CRM_ONLY", "CONSTRUCTION_CORE", "FULL_BUILD360"), default="FULL_BUILD360")


class CompanyStatusSerializer(serializers.Serializer):
    is_active = serializers.BooleanField()
    reason_code = serializers.CharField(max_length=100, required=False, allow_blank=True)


class CompanyFeatureOverrideSerializer(serializers.Serializer):
    feature_code = serializers.CharField(max_length=150)
    enabled = serializers.BooleanField()
    reason_code = serializers.CharField(max_length=100)


class CompanyFeaturePresetSerializer(serializers.Serializer):
    preset_code = serializers.ChoiceField(choices=("CRM_ONLY", "CONSTRUCTION_CORE", "FULL_BUILD360"))
    reason_code = serializers.CharField(max_length=100)


class InvitationCreateSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=254)
    display_name = serializers.CharField(max_length=200)
    invitation_type_code = serializers.CharField(max_length=100, default="EMPLOYEE")
    role_public_ids = serializers.ListField(
        child=serializers.UUIDField(), allow_empty=True, max_length=20, required=False, default=list
    )
    access_levels = serializers.DictField(
        child=serializers.ChoiceField(choices=("NONE", "VIEW", "EDIT", "FULL")),
        required=False,
    )
    employee_number = serializers.CharField(max_length=50, required=False, allow_blank=True)
    job_title = serializers.CharField(max_length=150, required=False, allow_blank=True)
    ttl_hours = serializers.IntegerField(min_value=1, max_value=168, default=72)


class RoleCreateSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=100)
    name = serializers.CharField(max_length=200)
    permission_codes = serializers.ListField(
        child=serializers.CharField(max_length=150), allow_empty=True, max_length=1000
    )


class MembershipRolesSerializer(serializers.Serializer):
    role_public_ids = serializers.ListField(
        child=serializers.UUIDField(), allow_empty=True, max_length=20
    )


class MembershipStatusSerializer(serializers.Serializer):
    status_code = serializers.ChoiceField(choices=("ACTIVE", "SUSPENDED", "TERMINATED"))
    reason_code = serializers.CharField(max_length=100, required=False, allow_blank=True)


class InvitationAcceptSerializer(serializers.Serializer):
    token = serializers.CharField(min_length=20, max_length=500, trim_whitespace=True)
    password = serializers.CharField(min_length=12, max_length=256, trim_whitespace=False)

    def validate_password(self, value: str) -> str:
        if value.lower() == value or value.upper() == value:
            raise serializers.ValidationError("Password must contain mixed letter case")
        if not any(character.isdigit() for character in value):
            raise serializers.ValidationError("Password must contain a number")
        return value


def uuid_list(values: list[uuid.UUID]) -> list[uuid.UUID]:
    return list(dict.fromkeys(values))


class PrimaryAdminInviteRegenerateSerializer(serializers.Serializer):
    ttl_hours = serializers.IntegerField(min_value=1, max_value=168, default=72)


class PrimaryAdminTransferSerializer(serializers.Serializer):
    membership_public_id = serializers.UUIDField()
    reason_code = serializers.CharField(min_length=3, max_length=100)


class ManagedAccessProfileSerializer(serializers.Serializer):
    access_levels = serializers.DictField(
        child=serializers.ChoiceField(choices=("NONE", "VIEW", "EDIT", "FULL")),
        allow_empty=True,
    )
    reason_code = serializers.CharField(
        min_length=3,
        max_length=100,
        required=False,
        default="company-admin-permission-change",
    )
