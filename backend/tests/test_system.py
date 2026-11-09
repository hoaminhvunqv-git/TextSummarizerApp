import pytest

try:
    from backend.app import create_app
    from backend.utils.errors import AppError, ErrorCode
except ImportError:
    from app import create_app
    from utils.errors import AppError, ErrorCode


@pytest.fixture
def client():
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


def test_health_endpoint(client):
    """Kiểm tra GET /health trả về status ok."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}


def test_config_endpoint(client):
    """Kiểm tra GET /api/v1/config trả về đúng cấu trúc chuẩn."""
    response = client.get("/api/v1/config")
    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert data["message"] == "Xử lý thành công"
    assert "min_app_version" in data["data"]
    assert data["data"]["min_app_version"] == "1.0.0"

    limits = data["data"]["limits"]
    assert limits["min_chars"] == 400
    assert limits["max_chars"] == 30000
    assert limits["max_file_mb"] == 10
    assert limits["daily_summary"] == 20
    assert limits["daily_quiz"] == 20

    assert data["data"]["length_unlock_chars"] == {
        "short": 400,
        "medium": 1000,
        "long": 2000,
    }


def test_not_found_endpoint(client):
    """Kiểm tra route không tồn tại trả về lỗi NOT_FOUND dạng JSON chuẩn."""
    response = client.get("/api/v1/non_existent_route")
    assert response.status_code == 404
    data = response.get_json()
    assert data["success"] is False
    assert data["error_code"] == ErrorCode.NOT_FOUND
    assert "Không tìm thấy dữ liệu" in data["message"]
