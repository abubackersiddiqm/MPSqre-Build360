import uuid

from django.test import Client, SimpleTestCase


class LiveHealthTests(SimpleTestCase):
    def test_live_returns_request_id(self) -> None:
        response = Client().get("/api/v1/health/live")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
        uuid.UUID(response["X-Request-Id"])

    def test_valid_request_id_is_preserved(self) -> None:
        request_id = uuid.uuid4()
        response = Client().get(
            "/api/v1/health/live",
            headers={"X-Request-Id": str(request_id)},
        )
        assert response["X-Request-Id"] == str(request_id)

    def test_invalid_request_id_is_replaced(self) -> None:
        response = Client().get(
            "/api/v1/health/live",
            headers={"X-Request-Id": "not-a-uuid"},
        )
        assert response["X-Request-Id"] != "not-a-uuid"
        uuid.UUID(response["X-Request-Id"])

