from rest_framework import serializers


class WorkflowStartSerializer(serializers.Serializer):
    subject_type = serializers.CharField(max_length=100)
    subject_public_id = serializers.UUIDField()


class WorkflowTransitionSerializer(serializers.Serializer):
    transition_code = serializers.CharField(max_length=100)
    expected_version = serializers.IntegerField(min_value=1)
    comment = serializers.CharField(max_length=1000, required=False, allow_blank=True)


class ApprovalDecisionSerializer(serializers.Serializer):
    approved = serializers.BooleanField()
    comment = serializers.CharField(max_length=1000, required=False, allow_blank=True)


class WorkflowDefinitionCreateSerializer(serializers.Serializer):
    code = serializers.RegexField(r"^[a-z0-9][a-z0-9._-]{1,149}$")
    name = serializers.CharField(max_length=200)
    description = serializers.CharField(max_length=500, required=False, allow_blank=True)


class WorkflowVersionCreateSerializer(serializers.Serializer):
    initial_state_code = serializers.CharField(max_length=100)
    states = serializers.ListField(child=serializers.DictField())
    transitions = serializers.ListField(child=serializers.DictField())
