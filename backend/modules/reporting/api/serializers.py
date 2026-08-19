
from rest_framework import serializers

from modules.reporting.models import DataClassification, SavedReport


class MetricCreateSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=100)
    name = serializers.CharField(max_length=200)
    description = serializers.CharField(required=False, allow_blank=True)
    domain_code = serializers.CharField(max_length=80)
    calculation_code = serializers.CharField(max_length=120)
    unit_code = serializers.CharField(max_length=40, required=False, default="count")
    data_classification = serializers.ChoiceField(
        choices=DataClassification.choices,
        required=False,
        default=DataClassification.INTERNAL,
    )


class SavedReportCreateSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=100)
    name = serializers.CharField(max_length=200)
    description = serializers.CharField(required=False, allow_blank=True)
    report_type = serializers.CharField(max_length=80)
    metric_codes = serializers.ListField(
        child=serializers.CharField(max_length=100),
        min_length=1,
        max_length=50,
    )
    filters = serializers.DictField(required=False)
    columns = serializers.ListField(
        child=serializers.CharField(max_length=120),
        required=False,
        max_length=100,
    )
    visibility = serializers.ChoiceField(
        choices=SavedReport.Visibility.choices,
        required=False,
        default=SavedReport.Visibility.PRIVATE,
    )
    role_public_ids = serializers.ListField(
        child=serializers.UUIDField(),
        required=False,
        max_length=50,
    )
    default_export_format = serializers.ChoiceField(
        choices=SavedReport.ExportFormat.choices,
        required=False,
        default=SavedReport.ExportFormat.CSV,
    )
    schedule_expression = serializers.CharField(
        max_length=120,
        required=False,
        allow_blank=True,
    )


class ReportRunCreateSerializer(serializers.Serializer):
    saved_report_public_id = serializers.UUIDField(required=False, allow_null=True)
    metric_codes = serializers.ListField(
        child=serializers.CharField(max_length=100),
        required=False,
        max_length=50,
    )
    export_format = serializers.ChoiceField(
        choices=SavedReport.ExportFormat.choices,
        required=False,
    )
    parameters = serializers.DictField(required=False)
    idempotency_key = serializers.CharField(max_length=120)

    def validate(self, attrs):
        if not attrs.get("saved_report_public_id") and not attrs.get("metric_codes"):
            raise serializers.ValidationError(
                "Provide a saved report or at least one metric code"
            )
        return attrs
