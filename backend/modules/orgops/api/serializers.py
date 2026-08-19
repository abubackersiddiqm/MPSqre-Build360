from rest_framework import serializers


class DepartmentCreateSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=50)
    name = serializers.CharField(max_length=200)
    parent_public_id = serializers.UUIDField(required=False, allow_null=True)
    location_public_id = serializers.UUIDField(required=False, allow_null=True)
    cost_center_code = serializers.CharField(max_length=100, required=False, allow_blank=True)


class DesignationCreateSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=50)
    name = serializers.CharField(max_length=200)
    level_code = serializers.CharField(max_length=100, required=False, allow_blank=True)
    description = serializers.CharField(required=False, allow_blank=True)


class WorkCalendarCreateSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=50)
    name = serializers.CharField(max_length=200)
    timezone = serializers.CharField(max_length=64)
    working_days = serializers.ListField(
        child=serializers.IntegerField(min_value=1, max_value=7),
        allow_empty=False,
        max_length=7,
    )
    standard_hours_per_day = serializers.DecimalField(max_digits=4, decimal_places=2)


class EmployeeProfileSerializer(serializers.Serializer):
    job_title = serializers.CharField(max_length=150)
    department_public_id = serializers.UUIDField(required=False, allow_null=True)
    designation_public_id = serializers.UUIDField(required=False, allow_null=True)
    work_calendar_public_id = serializers.UUIDField(required=False, allow_null=True)
    employment_type_code = serializers.CharField(max_length=100, default="FULL_TIME")
    worker_category_code = serializers.CharField(max_length=100, required=False, allow_blank=True)
    mobile = serializers.CharField(max_length=32, required=False, allow_blank=True)
    status_code = serializers.CharField(max_length=100, default="ACTIVE")
    probation_end = serializers.DateField(required=False, allow_null=True)
    confirmation_date = serializers.DateField(required=False, allow_null=True)


class ManagerSetSerializer(serializers.Serializer):
    manager_public_id = serializers.UUIDField()
    effective_from = serializers.DateField()


class AssignmentCreateSerializer(serializers.Serializer):
    employee_public_id = serializers.UUIDField()
    assignment_type_code = serializers.CharField(max_length=100, default="PRIMARY")
    project_code = serializers.CharField(max_length=100, required=False, allow_blank=True)
    site_code = serializers.CharField(max_length=100, required=False, allow_blank=True)
    location_public_id = serializers.UUIDField(required=False, allow_null=True)
    work_package_code = serializers.CharField(max_length=100, required=False, allow_blank=True)
    allocation_percent = serializers.DecimalField(max_digits=5, decimal_places=2)
    effective_from = serializers.DateField()
    effective_to = serializers.DateField(required=False, allow_null=True)
    is_primary = serializers.BooleanField(default=False)


class LeaveTypeCreateSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=50)
    name = serializers.CharField(max_length=200)
    unit_code = serializers.CharField(max_length=50, default="DAYS")
    requires_approval = serializers.BooleanField(default=True)
    is_paid = serializers.BooleanField(default=True)
    annual_entitlement = serializers.DecimalField(
        max_digits=8, decimal_places=2, required=False, allow_null=True
    )


class LeaveRequestCreateSerializer(serializers.Serializer):
    employee_public_id = serializers.UUIDField()
    leave_type_public_id = serializers.UUIDField()
    start_date = serializers.DateField()
    end_date = serializers.DateField()
    quantity = serializers.DecimalField(max_digits=8, decimal_places=2)
    reason = serializers.CharField(required=False, allow_blank=True)


class LeaveReviewSerializer(serializers.Serializer):
    decision_code = serializers.ChoiceField(choices=("APPROVED", "REJECTED"))
    review_note = serializers.CharField(required=False, allow_blank=True)
    expected_version = serializers.IntegerField(min_value=1)


class AttendanceSerializer(serializers.Serializer):
    employee_public_id = serializers.UUIDField()
    work_date = serializers.DateField()
    status_code = serializers.CharField(max_length=100)
    hours_worked = serializers.DecimalField(max_digits=5, decimal_places=2)
    source_code = serializers.CharField(max_length=100, default="MANUAL")
    notes = serializers.CharField(required=False, allow_blank=True)


class BulkImportSerializer(serializers.Serializer):
    source_name = serializers.CharField(max_length=250, default="people-import")
    rows = serializers.ListField(child=serializers.DictField(), allow_empty=False, max_length=500)
