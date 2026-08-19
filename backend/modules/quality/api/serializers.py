from rest_framework import serializers


class TemplateCreateSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=80)
    name = serializers.CharField(max_length=200)
    discipline_code = serializers.CharField(max_length=80)
    checklist = serializers.ListField(child=serializers.DictField(), default=list)


class InspectionCreateSerializer(serializers.Serializer):
    project_public_id = serializers.UUIDField()
    template_public_id = serializers.UUIDField()
    inspection_number = serializers.CharField(max_length=80)
    title = serializers.CharField(max_length=250)
    inspector_membership_public_id = serializers.UUIDField()
    scheduled_at = serializers.DateTimeField(required=False, allow_null=True)
    location = serializers.JSONField(required=False, default=dict)
    operation_id = serializers.UUIDField(required=False, allow_null=True)


class InspectionSubmitSerializer(serializers.Serializer):
    checklist_result = serializers.ListField(child=serializers.DictField(), default=list)
    overall_result = serializers.CharField(max_length=30)
    expected_version = serializers.IntegerField(min_value=1)


class NcrCreateSerializer(serializers.Serializer):
    project_public_id = serializers.UUIDField()
    inspection_public_id = serializers.UUIDField(required=False, allow_null=True)
    ncr_number = serializers.CharField(max_length=80)
    title = serializers.CharField(max_length=250)
    description = serializers.CharField()
    severity = serializers.CharField(max_length=30)
    due_date = serializers.DateField(required=False, allow_null=True)
    responsible_membership_public_id = serializers.UUIDField(required=False, allow_null=True)
