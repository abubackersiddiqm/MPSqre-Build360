from rest_framework import serializers


class TicketCreateSerializer(serializers.Serializer):
    catalog_item_public_id = serializers.UUIDField(required=False, allow_null=True)
    code = serializers.CharField(max_length=80)
    title = serializers.CharField(max_length=240)
    description = serializers.CharField(required=False, allow_blank=True)
    category_code = serializers.CharField(max_length=80, default="GENERAL")
    priority_code = serializers.ChoiceField(choices=["P0", "P1", "P2", "P3", "P4"], default="P3")
    channel_code = serializers.CharField(max_length=30, default="PORTAL")
    requester_name = serializers.CharField(max_length=180)
    requester_email = serializers.EmailField(required=False, allow_blank=True)
    requester_public_id = serializers.UUIDField(required=False, allow_null=True)
    assigned_to_public_id = serializers.UUIDField(required=False, allow_null=True)
    tags = serializers.ListField(child=serializers.CharField(max_length=80), required=False, default=list)


class TicketTransitionSerializer(serializers.Serializer):
    status_code = serializers.ChoiceField(
        choices=["TRIAGED", "IN_PROGRESS", "WAITING_CUSTOMER", "WAITING_INTERNAL", "RESOLVED", "CLOSED", "REOPENED", "CANCELLED"]
    )
    expected_version = serializers.IntegerField(min_value=1)
    assigned_to_public_id = serializers.UUIDField(required=False, allow_null=True)
    resolution_summary = serializers.CharField(required=False, allow_blank=True)


class InteractionCreateSerializer(serializers.Serializer):
    ticket_public_id = serializers.UUIDField()
    interaction_type_code = serializers.ChoiceField(choices=["COMMENT", "RESPONSE", "CALL", "EMAIL", "STATUS", "NOTE"], default="COMMENT")
    visibility_code = serializers.ChoiceField(choices=["INTERNAL", "CUSTOMER", "PARTNER"], default="INTERNAL")
    body = serializers.CharField()
    customer_visible = serializers.BooleanField(default=False)
    occurred_at = serializers.DateTimeField(required=False)
    attachments = serializers.ListField(child=serializers.DictField(), required=False, default=list)


class ProblemCreateSerializer(serializers.Serializer):
    source_ticket_public_id = serializers.UUIDField(required=False, allow_null=True)
    code = serializers.CharField(max_length=80)
    title = serializers.CharField(max_length=240)
    impact_summary = serializers.CharField(required=False, allow_blank=True)
    root_cause = serializers.CharField(required=False, allow_blank=True)
    workaround = serializers.CharField(required=False, allow_blank=True)
    permanent_fix = serializers.CharField(required=False, allow_blank=True)
    priority_code = serializers.ChoiceField(choices=["P0", "P1", "P2", "P3", "P4"], default="P2")
    owner_public_id = serializers.UUIDField(required=False, allow_null=True)


class ProblemTransitionSerializer(serializers.Serializer):
    status_code = serializers.ChoiceField(choices=["INVESTIGATING", "KNOWN_ERROR", "RESOLVED", "CLOSED", "CANCELLED"])
    expected_version = serializers.IntegerField(min_value=1)
    root_cause = serializers.CharField(required=False, allow_blank=True)
    permanent_fix = serializers.CharField(required=False, allow_blank=True)


class ChangeCreateSerializer(serializers.Serializer):
    source_ticket_public_id = serializers.UUIDField(required=False, allow_null=True)
    problem_public_id = serializers.UUIDField(required=False, allow_null=True)
    code = serializers.CharField(max_length=80)
    title = serializers.CharField(max_length=240)
    description = serializers.CharField(required=False, allow_blank=True)
    change_type_code = serializers.ChoiceField(choices=["STANDARD", "NORMAL", "EMERGENCY"], default="NORMAL")
    risk_code = serializers.ChoiceField(choices=["LOW", "MEDIUM", "HIGH", "CRITICAL"], default="MEDIUM")
    planned_start_at = serializers.DateTimeField(required=False, allow_null=True)
    planned_end_at = serializers.DateTimeField(required=False, allow_null=True)
    rollback_plan = serializers.CharField(required=False, allow_blank=True)


class ChangeTransitionSerializer(serializers.Serializer):
    status_code = serializers.ChoiceField(
        choices=["ASSESSMENT", "PENDING_APPROVAL", "APPROVED", "REJECTED", "SCHEDULED", "IMPLEMENTING", "IMPLEMENTED", "ROLLED_BACK", "CLOSED", "CANCELLED", "DRAFT"]
    )
    expected_version = serializers.IntegerField(min_value=1)
    rollback_plan = serializers.CharField(required=False, allow_blank=True)
    test_evidence = serializers.JSONField(required=False, default=dict)


class ArticleCreateSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=80)
    title = serializers.CharField(max_length=240)
    summary = serializers.CharField(required=False, allow_blank=True)
    content = serializers.CharField()
    category_code = serializers.CharField(max_length=80, default="GENERAL")
    audience_code = serializers.ChoiceField(choices=["INTERNAL", "CUSTOMER", "PARTNER", "PUBLIC"], default="INTERNAL")
    keywords = serializers.ListField(child=serializers.CharField(max_length=80), required=False, default=list)


class ArticleTransitionSerializer(serializers.Serializer):
    status_code = serializers.ChoiceField(choices=["DRAFT", "IN_REVIEW", "PUBLISHED", "ARCHIVED"])
    expected_version = serializers.IntegerField(min_value=1)


class FeedbackCreateSerializer(serializers.Serializer):
    ticket_public_id = serializers.UUIDField()
    rating = serializers.IntegerField(min_value=1, max_value=5)
    comments = serializers.CharField(required=False, allow_blank=True)
    submitted_by_name = serializers.CharField(max_length=180, required=False, allow_blank=True)
    submitted_by_email = serializers.EmailField(required=False, allow_blank=True)
    submitted_at = serializers.DateTimeField(required=False)
    follow_up_required = serializers.BooleanField(default=False)
    follow_up_notes = serializers.CharField(required=False, allow_blank=True)


class ImprovementCreateSerializer(serializers.Serializer):
    source_ticket_public_id = serializers.UUIDField(required=False, allow_null=True)
    source_problem_public_id = serializers.UUIDField(required=False, allow_null=True)
    source_feedback_public_id = serializers.UUIDField(required=False, allow_null=True)
    code = serializers.CharField(max_length=80)
    title = serializers.CharField(max_length=240)
    description = serializers.CharField(required=False, allow_blank=True)
    theme_code = serializers.CharField(max_length=80, default="SERVICE_QUALITY")
    priority_code = serializers.ChoiceField(choices=["P0", "P1", "P2", "P3", "P4"], default="P3")
    expected_benefit = serializers.CharField(required=False, allow_blank=True)
    owner_public_id = serializers.UUIDField(required=False, allow_null=True)
    due_at = serializers.DateTimeField(required=False, allow_null=True)


class ImprovementTransitionSerializer(serializers.Serializer):
    status_code = serializers.ChoiceField(choices=["PLANNED", "IN_PROGRESS", "BLOCKED", "VALIDATING", "COMPLETED", "CANCELLED", "BACKLOG"])
    expected_version = serializers.IntegerField(min_value=1)
    measured_benefit = serializers.CharField(required=False, allow_blank=True)
