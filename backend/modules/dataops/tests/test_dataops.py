from decimal import Decimal

from modules.dataops.application.services import validate_import_row
from modules.dataops.models import ImportTemplate


def test_import_preview_normalizes_values_and_rejects_unknown_fields():
    template = ImportTemplate(
        code="TEST",
        name="Test",
        destination_code="projects.project",
        schema={
            "fields": [
                {"name": "code", "required": True, "type": "upper_string"},
                {"name": "approved_budget", "required": False, "type": "decimal"},
                {"name": "tags", "required": False, "type": "list"},
            ]
        },
    )
    normalized, errors = validate_import_row(
        template,
        {
            "code": " prj-1 ",
            "approved_budget": Decimal("1250.50"),
            "tags": "civil, priority",
            "unexpected": "secret-value",
        },
    )
    assert normalized == {
        "code": "PRJ-1",
        "approved_budget": "1250.50",
        "tags": ["civil", "priority"],
    }
    assert errors[0]["error_code"] == "unknown_field"
    assert "secret-value" not in errors[0]["masked_value"]


def test_import_preview_reports_missing_required_values():
    template = ImportTemplate(
        code="TEST",
        name="Test",
        destination_code="vendor.vendor",
        schema={"fields": [{"name": "legal_name", "required": True, "type": "string"}]},
    )
    normalized, errors = validate_import_row(template, {})
    assert normalized == {}
    assert errors == [{
        "field_name": "legal_name",
        "error_code": "required",
        "message": "Required value is missing",
        "masked_value": "",
    }]
