from decimal import Decimal

from rest_framework import serializers


class ProjectCreateSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=50)
    name = serializers.CharField(max_length=250)
    description = serializers.CharField(required=False, allow_blank=True)
    project_type_code = serializers.CharField(max_length=100, default="CONSTRUCTION")
    priority_code = serializers.CharField(max_length=50, default="NORMAL")
    manager_public_id = serializers.UUIDField(required=False, allow_null=True)
    location_public_id = serializers.UUIDField(required=False, allow_null=True)
    start_date = serializers.DateField()
    target_end_date = serializers.DateField()
    currency = serializers.CharField(max_length=3, required=False, allow_blank=True)
    budget = serializers.DecimalField(max_digits=18, decimal_places=2, required=False, allow_null=True, min_value=Decimal("0"))


class StatusTransitionSerializer(serializers.Serializer):
    status_code = serializers.CharField(max_length=50)
    expected_version = serializers.IntegerField(min_value=1)


class SiteCreateSerializer(serializers.Serializer):
    project_public_id = serializers.UUIDField()
    code = serializers.CharField(max_length=50)
    name = serializers.CharField(max_length=200)
    location_public_id = serializers.UUIDField(required=False, allow_null=True)
    address = serializers.DictField(required=False)
    start_date = serializers.DateField(required=False, allow_null=True)
    target_end_date = serializers.DateField(required=False, allow_null=True)


class WBSCreateSerializer(serializers.Serializer):
    project_public_id = serializers.UUIDField()
    code = serializers.CharField(max_length=100)
    name = serializers.CharField(max_length=250)
    parent_public_id = serializers.UUIDField(required=False, allow_null=True)
    sequence = serializers.IntegerField(min_value=1, default=1)


class WorkPackageCreateSerializer(serializers.Serializer):
    project_public_id = serializers.UUIDField()
    wbs_node_public_id = serializers.UUIDField()
    code = serializers.CharField(max_length=100)
    name = serializers.CharField(max_length=250)
    description = serializers.CharField(required=False, allow_blank=True)
    owner_public_id = serializers.UUIDField(required=False, allow_null=True)
    planned_start = serializers.DateField()
    planned_end = serializers.DateField()
    progress_weight = serializers.DecimalField(max_digits=5, decimal_places=2, min_value=Decimal("0.01"), max_value=Decimal("100"), default=Decimal("1.00"))


class MilestoneCreateSerializer(serializers.Serializer):
    project_public_id = serializers.UUIDField()
    code = serializers.CharField(max_length=100)
    name = serializers.CharField(max_length=250)
    target_date = serializers.DateField()
    owner_public_id = serializers.UUIDField(required=False, allow_null=True)


class WorkItemCreateSerializer(serializers.Serializer):
    project_public_id = serializers.UUIDField()
    site_public_id = serializers.UUIDField(required=False, allow_null=True)
    work_package_public_id = serializers.UUIDField(required=False, allow_null=True)
    code = serializers.CharField(max_length=100)
    title = serializers.CharField(max_length=300)
    description = serializers.CharField(required=False, allow_blank=True)
    work_type_code = serializers.CharField(max_length=100, default="TASK")
    priority_code = serializers.CharField(max_length=50, default="NORMAL")
    planned_start = serializers.DateField(required=False, allow_null=True)
    due_date = serializers.DateField(required=False, allow_null=True)
    estimated_hours = serializers.DecimalField(max_digits=8, decimal_places=2, required=False, allow_null=True, min_value=Decimal("0"))
    primary_assignee_public_id = serializers.UUIDField(required=False, allow_null=True)
    reviewer_public_id = serializers.UUIDField(required=False, allow_null=True)


class AssignmentCreateSerializer(serializers.Serializer):
    work_item_public_id = serializers.UUIDField()
    employee_public_id = serializers.UUIDField()
    assignment_role_code = serializers.CharField(max_length=50, default="ASSIGNEE")
    allocation_percent = serializers.DecimalField(max_digits=5, decimal_places=2, min_value=Decimal("0.01"), max_value=Decimal("100"), default=Decimal("100.00"))
    effective_from = serializers.DateField()
    effective_to = serializers.DateField(required=False, allow_null=True)
    make_primary = serializers.BooleanField(default=False)


class DependencyCreateSerializer(serializers.Serializer):
    predecessor_public_id = serializers.UUIDField()
    successor_public_id = serializers.UUIDField()
    dependency_type_code = serializers.CharField(max_length=50, default="FINISH_TO_START")
    lag_days = serializers.IntegerField(default=0)


class ChecklistCreateSerializer(serializers.Serializer):
    work_item_public_id = serializers.UUIDField()
    sequence = serializers.IntegerField(min_value=1)
    title = serializers.CharField(max_length=300)
    is_required = serializers.BooleanField(default=True)


class ChecklistCompletionSerializer(serializers.Serializer):
    is_completed = serializers.BooleanField()
    expected_version = serializers.IntegerField(min_value=1)


class ProgressCreateSerializer(serializers.Serializer):
    project_public_id = serializers.UUIDField()
    site_public_id = serializers.UUIDField(required=False, allow_null=True)
    work_item_public_id = serializers.UUIDField(required=False, allow_null=True)
    recorded_by_public_id = serializers.UUIDField(required=False, allow_null=True)
    progress_date = serializers.DateField()
    quantity_completed = serializers.DecimalField(max_digits=18, decimal_places=3, min_value=Decimal("0"), default=Decimal("0"))
    unit_code = serializers.CharField(max_length=50, required=False, allow_blank=True)
    progress_percent = serializers.DecimalField(max_digits=5, decimal_places=2, required=False, allow_null=True, min_value=Decimal("0"), max_value=Decimal("100"))
    hours_worked = serializers.DecimalField(max_digits=8, decimal_places=2, min_value=Decimal("0"), default=Decimal("0"))
    note = serializers.CharField(required=False, allow_blank=True)
    blockers = serializers.CharField(required=False, allow_blank=True)


class TimesheetCreateSerializer(serializers.Serializer):
    employee_public_id = serializers.UUIDField()
    project_public_id = serializers.UUIDField()
    work_item_public_id = serializers.UUIDField(required=False, allow_null=True)
    work_date = serializers.DateField()
    hours = serializers.DecimalField(max_digits=5, decimal_places=2, min_value=Decimal("0.01"), max_value=Decimal("24"))
    description = serializers.CharField(required=False, allow_blank=True)
    submit_now = serializers.BooleanField(default=False)


class TimesheetReviewSerializer(serializers.Serializer):
    decision_code = serializers.ChoiceField(choices=("APPROVED", "REJECTED"))
    review_note = serializers.CharField(required=False, allow_blank=True)
    expected_version = serializers.IntegerField(min_value=1)


class VersionSerializer(serializers.Serializer):
    expected_version = serializers.IntegerField(min_value=1)


class ApprovalRequestSerializer(serializers.Serializer):
    work_item_public_id = serializers.UUIDField()
    reviewer_public_id = serializers.UUIDField()
    approval_type_code = serializers.CharField(max_length=100, default="WORK_COMPLETION")
    request_note = serializers.CharField(required=False, allow_blank=True)


class ApprovalReviewSerializer(serializers.Serializer):
    decision_code = serializers.ChoiceField(choices=("APPROVED", "REJECTED"))
    decision_note = serializers.CharField(required=False, allow_blank=True)
    expected_version = serializers.IntegerField(min_value=1)
