import pytest

try:
    from backend.app import create_app
    from backend.config import Config
    from backend.services import quota_service
    from backend.utils.errors import AppError
except ImportError:
    from app import create_app
    from config import Config
    from services import quota_service
    from utils.errors import AppError

DEVICE_ID = "3f2504e0-4f89-41d3-9a0c-0305e82c3301"
HEADERS = {"X-Device-ID": DEVICE_ID, "X-App-Version": "1.0.0"}
ENDPOINT = "/api/v1/usage"

SAMPLE = {
    "summary": {"used": 1, "limit": 20, "remaining": 19},
    "quiz": {"used": 0, "limit": 20, "remaining": 20},
    "resets_at": "2026-11-11T00:00:00+07:00",
}


class TestConfig(Config):
    TESTING = True
    RATELIMIT_ENABLED = False


@pytest.fixture
def client():
    return create_app(TestConfig).test_client()


def test_usage_requires_device_header(client):
    response = client.get(ENDPOINT, headers={"X-App-Version": "1.0.0"})
    assert response.status_code == 400
    assert response.get_json()["error_code"] == "INVALID_DEVICE_ID"


def test_usage_returns_contract_shape(client, monkeypatch):
    seen = {}

    def fake_get_usage(owner, day=None):
        seen["owner"] = owner
        return SAMPLE

    monkeypatch.setattr(quota_service, "get_usage", fake_get_usage)

    response = client.get(ENDPOINT, headers=HEADERS)
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["success"] is True
    assert payload["data"] == SAMPLE
    assert seen["owner"] == f"d:{DEVICE_ID}"


def test_usage_reports_server_error_when_db_missing(client, monkeypatch):
    """Thiếu DATABASE_URL phải ra 500, không được trả 'còn 20 lượt' giả."""

    def boom(owner, day=None):
        raise RuntimeError("DATABASE_URL chưa được cấu hình")

    monkeypatch.setattr(quota_service, "get_usage", boom)

    response = client.get(ENDPOINT, headers=HEADERS)
    assert response.status_code == 500
    assert response.get_json()["error_code"] == "INTERNAL_ERROR"


def test_usage_route_is_registered(client):
    """Route phải có trong url_map với đúng prefix /api/v1."""
    rules = {rule.rule for rule in client.application.url_map.iter_rules()}
    assert ENDPOINT in rules
