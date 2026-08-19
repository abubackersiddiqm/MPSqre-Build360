from __future__ import annotations

from uuid import uuid4

from django.test import SimpleTestCase

from modules.crm.api.serializers import ActivityCreateSerializer
from modules.crm.models import Activity


class ActivityLocationContractTests(SimpleTestCase):
    def payload(self, activity_type: str) -> dict[str, object]:
        return {
            "activity_type": activity_type,
            "status": "planned",
            "subject": "UAT activity",
            "lead_public_id": str(uuid4()),
        }

    def test_model_location_is_optional_for_non_site_activity(self) -> None:
        field = Activity._meta.get_field("location")
        self.assertTrue(field.blank)
        self.assertIs(field.default, dict)

    def test_call_does_not_require_location(self) -> None:
        serializer = ActivityCreateSerializer(data=self.payload("call"))
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["location"], {})

    def test_follow_up_does_not_require_location(self) -> None:
        serializer = ActivityCreateSerializer(data=self.payload("follow_up"))
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["location"], {})

    def test_site_visit_requires_location(self) -> None:
        serializer = ActivityCreateSerializer(data=self.payload("site_visit"))
        self.assertFalse(serializer.is_valid())
        self.assertIn("location", serializer.errors)

    def test_site_visit_accepts_location(self) -> None:
        payload = self.payload("site_visit")
        payload["location"] = {"address": "UAT Project Site"}
        serializer = ActivityCreateSerializer(data=payload)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(
            serializer.validated_data["location"],
            {"address": "UAT Project Site"},
        )
