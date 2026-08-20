from django.test import SimpleTestCase

from modules.accessops.application.managed_access import (
    changed_access_levels,
    filter_permission_codes_for_level,
)


class ManagedAccessPermissionClassifierTests(SimpleTestCase):
    def test_view_only_excludes_write_and_sensitive_permissions(self) -> None:
        codes = [
            "crm.dashboard.read",
            "crm.contact.read",
            "crm.contact.manage",
            "crm.contact.reveal",
            "crm.lead.assign",
            "crm.lead.transition",
            "crm.lead.convert",
        ]
        self.assertEqual(
            filter_permission_codes_for_level(codes, "VIEW"),
            ["crm.contact.read", "crm.dashboard.read"],
        )

    def test_edit_keeps_manage_but_not_sensitive_actions(self) -> None:
        codes = [
            "crm.contact.read",
            "crm.contact.manage",
            "crm.contact.reveal",
            "crm.lead.read",
            "crm.lead.manage",
            "crm.lead.assign",
            "crm.lead.transition",
            "crm.lead.convert",
        ]
        self.assertEqual(
            filter_permission_codes_for_level(codes, "EDIT"),
            [
                "crm.contact.manage",
                "crm.contact.read",
                "crm.lead.manage",
                "crm.lead.read",
            ],
        )

    def test_full_keeps_all_package_permissions(self) -> None:
        codes = ["crm.contact.read", "crm.contact.manage", "crm.contact.reveal"]
        self.assertEqual(filter_permission_codes_for_level(codes, "FULL"), sorted(codes))


class ManagedAccessAuditDiffTests(SimpleTestCase):
    def test_changed_access_levels_only_returns_semantic_differences(self) -> None:
        self.assertEqual(
            changed_access_levels(
                {"CRM": "FULL", "PROJECTS": "VIEW"},
                {"CRM": "VIEW", "PROJECTS": "VIEW", "FINANCE": "EDIT"},
            ),
            [
                {"area_code": "CRM", "before": "FULL", "after": "VIEW"},
                {"area_code": "FINANCE", "before": "NONE", "after": "EDIT"},
            ],
        )
