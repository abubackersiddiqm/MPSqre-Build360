from __future__ import annotations

import uuid

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.request import Request
from rest_framework.response import Response

from modules.employee.models import Employee
from modules.orgops.application.selectors import organization_overview
from modules.orgops.application.services import (
    bulk_import_people,
    create_assignment,
    create_department,
    create_designation,
    create_leave_type,
    create_work_calendar,
    review_leave_request,
    set_employee_manager,
    submit_leave_request,
    update_employee_profile,
    upsert_attendance,
)
from modules.orgops.models import Department, Designation, LeaveRequest, LeaveType, WorkCalendar
from modules.tenant.api.base import TenantScopedAPIView
from modules.tenant.models import Location

from .serializers import (
    AssignmentCreateSerializer,
    AttendanceSerializer,
    BulkImportSerializer,
    DepartmentCreateSerializer,
    DesignationCreateSerializer,
    EmployeeProfileSerializer,
    LeaveRequestCreateSerializer,
    LeaveReviewSerializer,
    LeaveTypeCreateSerializer,
    ManagerSetSerializer,
    WorkCalendarCreateSerializer,
)


def correlation_id(request: Request) -> uuid.UUID:
    return getattr(request, "request_id", uuid.uuid4())


def translate(error: DjangoValidationError) -> ValidationError:
    if hasattr(error, "message_dict"):
        return ValidationError(error.message_dict)
    return ValidationError(getattr(error, "messages", [str(error)]))


class OrgAPIView(TenantScopedAPIView):
    required_permission = "peopleorg.view"

    def initial(self, request: Request, *args: object, **kwargs: object) -> None:
        super().initial(request, *args, **kwargs)
        self.tenant_context.require(self.required_permission)

    @property
    def actor(self) -> uuid.UUID:
        return self.tenant_context.principal.user.public_id


class OverviewView(OrgAPIView):
    def get(self, request: Request) -> Response:
        return Response(organization_overview(self.tenant_context.company))


class DepartmentView(OrgAPIView):
    required_permission = "peopleorg.structure.manage"

    def post(self, request: Request) -> Response:
        serializer = DepartmentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        parent = None
        location = None
        if data.get("parent_public_id"):
            parent = Department.objects.filter(
                company=self.tenant_context.company, public_id=data["parent_public_id"]
            ).first()
            if not parent:
                raise NotFound("Department parent not found")
        if data.get("location_public_id"):
            location = Location.objects.filter(
                company=self.tenant_context.company, public_id=data["location_public_id"]
            ).first()
            if not location:
                raise NotFound("Location not found")
        try:
            item = create_department(
                company=self.tenant_context.company,
                code=data["code"],
                name=data["name"],
                parent=parent,
                location=location,
                cost_center_code=data.get("cost_center_code", ""),
                actor_public_id=self.actor,
                correlation_id=correlation_id(request),
            )
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(item.public_id), "code": item.code}, status=201)


class DesignationView(OrgAPIView):
    required_permission = "peopleorg.structure.manage"

    def post(self, request: Request) -> Response:
        serializer = DesignationCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = create_designation(
                company=self.tenant_context.company,
                actor_public_id=self.actor,
                correlation_id=correlation_id(request),
                **serializer.validated_data,
            )
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(item.public_id), "code": item.code}, status=201)


class WorkCalendarView(OrgAPIView):
    required_permission = "peopleorg.structure.manage"

    def post(self, request: Request) -> Response:
        serializer = WorkCalendarCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            item = create_work_calendar(
                company=self.tenant_context.company,
                code=data["code"],
                name=data["name"],
                timezone_name=data["timezone"],
                working_days=data["working_days"],
                standard_hours_per_day=data["standard_hours_per_day"],
                actor_public_id=self.actor,
                correlation_id=correlation_id(request),
            )
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(item.public_id), "code": item.code}, status=201)


class EmployeeProfileView(OrgAPIView):
    required_permission = "peopleorg.manage"

    def patch(self, request: Request, employee_id: uuid.UUID) -> Response:
        employee = Employee.objects.filter(
            company=self.tenant_context.company, public_id=employee_id
        ).first()
        if not employee:
            raise NotFound("Employee not found")
        serializer = EmployeeProfileSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        department = Department.objects.filter(
            company=self.tenant_context.company, public_id=data.get("department_public_id")
        ).first() if data.get("department_public_id") else None
        designation = Designation.objects.filter(
            company=self.tenant_context.company, public_id=data.get("designation_public_id")
        ).first() if data.get("designation_public_id") else None
        calendar = WorkCalendar.objects.filter(
            company=self.tenant_context.company, public_id=data.get("work_calendar_public_id")
        ).first() if data.get("work_calendar_public_id") else None
        try:
            profile = update_employee_profile(
                company=self.tenant_context.company,
                employee=employee,
                department=department,
                designation=designation,
                work_calendar=calendar,
                actor_public_id=self.actor,
                correlation_id=correlation_id(request),
                job_title=data["job_title"],
                employment_type_code=data["employment_type_code"],
                worker_category_code=data.get("worker_category_code", ""),
                mobile=data.get("mobile", ""),
                status_code=data["status_code"],
                probation_end=data.get("probation_end"),
                confirmation_date=data.get("confirmation_date"),
            )
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(profile.public_id), "version": profile.version})


class EmployeeManagerView(OrgAPIView):
    required_permission = "peopleorg.manage"

    def post(self, request: Request, employee_id: uuid.UUID) -> Response:
        employee = Employee.objects.filter(company=self.tenant_context.company, public_id=employee_id).first()
        if not employee:
            raise NotFound("Employee not found")
        serializer = ManagerSetSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        manager = Employee.objects.filter(
            company=self.tenant_context.company,
            public_id=serializer.validated_data["manager_public_id"],
        ).first()
        if not manager:
            raise NotFound("Manager not found")
        try:
            line = set_employee_manager(
                company=self.tenant_context.company,
                employee=employee,
                manager=manager,
                effective_from=serializer.validated_data["effective_from"],
                actor_public_id=self.actor,
                correlation_id=correlation_id(request),
            )
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(line.public_id)}, status=201)


class AssignmentView(OrgAPIView):
    required_permission = "peopleorg.assignment.manage"

    def post(self, request: Request) -> Response:
        serializer = AssignmentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        employee = Employee.objects.filter(
            company=self.tenant_context.company, public_id=data["employee_public_id"]
        ).first()
        if not employee:
            raise NotFound("Employee not found")
        location = Location.objects.filter(
            company=self.tenant_context.company, public_id=data.get("location_public_id")
        ).first() if data.get("location_public_id") else None
        try:
            item = create_assignment(
                company=self.tenant_context.company,
                employee=employee,
                location=location,
                assignment_type_code=data["assignment_type_code"],
                project_code=data.get("project_code", ""),
                site_code=data.get("site_code", ""),
                work_package_code=data.get("work_package_code", ""),
                allocation_percent=data["allocation_percent"],
                effective_from=data["effective_from"],
                effective_to=data.get("effective_to"),
                is_primary=data["is_primary"],
                actor_public_id=self.actor,
                correlation_id=correlation_id(request),
            )
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(item.public_id)}, status=201)


class LeaveTypeView(OrgAPIView):
    required_permission = "peopleorg.leave.manage"

    def post(self, request: Request) -> Response:
        serializer = LeaveTypeCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = create_leave_type(
                company=self.tenant_context.company,
                actor_public_id=self.actor,
                correlation_id=correlation_id(request),
                **serializer.validated_data,
            )
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(item.public_id), "code": item.code}, status=201)


class LeaveRequestView(OrgAPIView):
    required_permission = "peopleorg.leave.manage"

    def post(self, request: Request) -> Response:
        serializer = LeaveRequestCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        employee = Employee.objects.filter(company=self.tenant_context.company, public_id=data["employee_public_id"]).first()
        leave_type = LeaveType.objects.filter(company=self.tenant_context.company, public_id=data["leave_type_public_id"]).first()
        if not employee or not leave_type:
            raise NotFound("Employee or leave type not found")
        try:
            item = submit_leave_request(
                company=self.tenant_context.company,
                employee=employee,
                leave_type=leave_type,
                start_date=data["start_date"],
                end_date=data["end_date"],
                quantity=data["quantity"],
                reason=data.get("reason", ""),
                actor_public_id=self.actor,
                correlation_id=correlation_id(request),
            )
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(item.public_id), "status_code": item.status_code}, status=201)


class LeaveReviewView(OrgAPIView):
    required_permission = "peopleorg.leave.manage"

    def post(self, request: Request, leave_id: uuid.UUID) -> Response:
        item = LeaveRequest.objects.filter(company=self.tenant_context.company, public_id=leave_id).first()
        if not item:
            raise NotFound("Leave request not found")
        serializer = LeaveReviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = review_leave_request(
                company=self.tenant_context.company,
                leave_request=item,
                actor_public_id=self.actor,
                correlation_id=correlation_id(request),
                **serializer.validated_data,
            )
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(item.public_id), "status_code": item.status_code, "version": item.version})


class AttendanceView(OrgAPIView):
    required_permission = "peopleorg.attendance.manage"

    def post(self, request: Request) -> Response:
        serializer = AttendanceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        employee = Employee.objects.filter(company=self.tenant_context.company, public_id=data["employee_public_id"]).first()
        if not employee:
            raise NotFound("Employee not found")
        try:
            item = upsert_attendance(
                company=self.tenant_context.company,
                employee=employee,
                work_date=data["work_date"],
                status_code=data["status_code"],
                hours_worked=data["hours_worked"],
                source_code=data["source_code"],
                notes=data.get("notes", ""),
                actor_public_id=self.actor,
                correlation_id=correlation_id(request),
            )
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(item.public_id), "version": item.version})


class BulkImportView(OrgAPIView):
    required_permission = "peopleorg.import"

    def post(self, request: Request) -> Response:
        serializer = BulkImportSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        job, results = bulk_import_people(
            company=self.tenant_context.company,
            source_name=serializer.validated_data["source_name"],
            rows=serializer.validated_data["rows"],
            actor_public_id=self.actor,
            correlation_id=correlation_id(request),
        )
        return Response(
            {
                "job_public_id": str(job.public_id),
                "status_code": job.status_code,
                "success_rows": job.success_rows,
                "failed_rows": job.failed_rows,
                "results": results,
            },
            status=201,
        )
