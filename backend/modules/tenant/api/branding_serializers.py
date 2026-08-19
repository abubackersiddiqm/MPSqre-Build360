from rest_framework import serializers


class BrandingUpdateSerializer(serializers.Serializer):
    expected_version = serializers.IntegerField(min_value=1)
    product_name = serializers.CharField(max_length=120, required=False, allow_blank=True)
    tagline = serializers.CharField(max_length=220, required=False, allow_blank=True)
    logo_url = serializers.URLField(max_length=1000, required=False, allow_blank=True)
    compact_logo_url = serializers.URLField(max_length=1000, required=False, allow_blank=True)
    favicon_url = serializers.URLField(max_length=1000, required=False, allow_blank=True)
    login_background_url = serializers.URLField(max_length=1000, required=False, allow_blank=True)
    primary_color = serializers.RegexField(r"^#[0-9A-Fa-f]{6}$", required=False)
    accent_color = serializers.RegexField(r"^#[0-9A-Fa-f]{6}$", required=False)
    sidebar_style = serializers.ChoiceField(choices=["LIGHT", "DARK", "BRAND"], required=False)
    sender_name = serializers.CharField(max_length=160, required=False, allow_blank=True)
    support_email = serializers.EmailField(max_length=254, required=False, allow_blank=True)
    document_footer = serializers.CharField(max_length=500, required=False, allow_blank=True)
    powered_by_build360 = serializers.BooleanField(required=False)


class DomainCreateSerializer(serializers.Serializer):
    domain = serializers.CharField(max_length=253)
    domain_type = serializers.ChoiceField(choices=["PLATFORM_SUBDOMAIN", "CUSTOM_DOMAIN"])
    make_primary = serializers.BooleanField(default=False)


class DomainActionSerializer(serializers.Serializer):
    expected_version = serializers.IntegerField(min_value=1)


class BrandingAssetAttachSerializer(serializers.Serializer):
    expected_version = serializers.IntegerField(min_value=1)
    slot = serializers.ChoiceField(choices=["logo", "compact_logo", "favicon", "login_background"])
    file_public_id = serializers.UUIDField()


class BrandingAssetListSerializer(serializers.Serializer):
    slot = serializers.ChoiceField(choices=["logo", "compact_logo", "favicon", "login_background"], required=False)
