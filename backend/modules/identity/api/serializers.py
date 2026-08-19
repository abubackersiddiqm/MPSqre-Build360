from typing import Any

from rest_framework import serializers


class LoginSerializer(serializers.Serializer[dict[str, Any]]):
    email = serializers.EmailField(max_length=254)
    password = serializers.CharField(max_length=256, trim_whitespace=False, write_only=True)
    device_id = serializers.UUIDField()
    device_name = serializers.CharField(max_length=200, allow_blank=True, default="")


class RefreshSerializer(serializers.Serializer[dict[str, Any]]):
    refresh_token = serializers.CharField(max_length=4096, trim_whitespace=False)


class RevokeSessionSerializer(serializers.Serializer[dict[str, Any]]):
    reason_code = serializers.CharField(max_length=100, default="user_logout")


class PasswordResetRequestSerializer(serializers.Serializer[dict[str, Any]]):
    email = serializers.EmailField(max_length=254)


class PasswordResetConfirmSerializer(serializers.Serializer[dict[str, Any]]):
    uid = serializers.CharField(max_length=256)
    token = serializers.CharField(max_length=256)
    password = serializers.CharField(min_length=12, max_length=256, trim_whitespace=False, write_only=True)

    def validate_password(self, value: str) -> str:
        if value.lower() == value or value.upper() == value:
            raise serializers.ValidationError("Password must contain mixed letter case")
        if not any(character.isdigit() for character in value):
            raise serializers.ValidationError("Password must contain a number")
        return value
