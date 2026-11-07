from pathlib import Path
from unittest.mock import patch

import pytest

try:
    from backend.app import create_app
    from backend.config import Config
    from backend.extensions import limiter
    from backend.services.gemini_service import GeminiService
    from backend.utils.text_utils import detect_language, normalize_text
except ImportError:
    from app import create_app
    from config import Config
    from extensions import limiter
    from services.gemini_service import GeminiService
    from utils.text_utils import detect_language, normalize_text

TESTDATA_DIR = Path(__file__).resolve().parent.parent.parent / "testdata"
DEVICE_ID = "3f2504e0-4f89-41d3-9a0c-0305e82c3301"
HEADERS = {"X-Device-ID": DEVICE_ID, "X-App-Version": "1.0.0"}
ENDPOINT = "/api/v1/summaries"


def read_testdata(filename: str) -> str:
    return (TESTDATA_DIR / filename).read_text(encoding="utf-8")


def fake_gemini_result(text: str, length: str = "medium"):
    """Giả lập phản hồi Gemini để test route không gọi API thật (không tốn quota)."""
    language = detect_language(text)
    return {
        "title": "Tiêu đề kiểm thử" if language == "vi" else "Test title",
        "description": "Mô tả kiểm thử." if language == "vi" else "Test description.",
        "summary": "Đoạn tóm tắt.\n\n- Ý một\n- Ý hai\n- Ý ba"
        if language == "vi"
        else "Summary paragraph.\n\n- Point one\n- Point two\n- Point three",
        "language": language,
        "source": "gemini",
        "original_length": len(text),
    }


class TestConfig(Config):
    TESTING = True
    RATELIMIT_ENABLED = False


class RateLimitConfig(Config):
    TESTING = True
    RATELIMIT_ENABLED = True


@pytest.fixture
def client():
    return create_app(TestConfig).test_client()


@pytest.fixture
def mock_gemini():
    with patch.object(GeminiService, "summarize", side_effect=fake_gemini_result) as mocked:
        yield mocked


def post_summary(client, text, length=None, headers=None):
    body = {"text": text}
    if length is not None:
        body["length"] = length
    return client.post(ENDPOINT, json=body, headers=HEADERS if headers is None else headers)


def test_summary_vi_success(client, mock_gemini):
    text = read_testdata("vi_500.txt")
    resp = post_summary(client, text, "medium")

    assert resp.status_code == 201
    payload = resp.get_json()
    assert payload["success"] is True
    assert payload["message"] == "Xử lý thành công"

    data = payload["data"]
    assert data["language"] == "vi"
    assert data["source"] == "gemini"
    assert data["id"] is None
    assert data["original_length"] == len(normalize_text(text))
    assert data["created_at"].endswith("+07:00")
    assert "\n\n- " in data["summary"]
    assert data["usage"] == {"summary_remaining": None, "quiz_remaining": None}


def test_summary_en_success(client, mock_gemini):
    resp = post_summary(client, read_testdata("en_250.txt"), "short")

    assert resp.status_code == 201
    assert resp.get_json()["data"]["language"] == "en"


@pytest.mark.parametrize("length", ["short", "medium", "long"])
def test_length_forwarded_to_service(client, mock_gemini, length):
    post_summary(client, read_testdata("vi_500.txt"), length)

    assert mock_gemini.call_args.args[1] == length


def test_length_defaults_to_medium(client, mock_gemini):
    resp = post_summary(client, read_testdata("vi_500.txt"))

    assert resp.status_code == 201
    assert mock_gemini.call_args.args[1] == "medium"


def test_text_too_short(client, mock_gemini):
    resp = post_summary(client, read_testdata("short_100.txt"))

    assert resp.status_code == 400
    assert resp.get_json()["error_code"] == "TEXT_TOO_SHORT"
    mock_gemini.assert_not_called()


def test_text_too_long(client, mock_gemini):
    resp = post_summary(client, read_testdata("long_31000.txt"))

    assert resp.status_code == 400
    assert resp.get_json()["error_code"] == "TEXT_TOO_LONG"
    mock_gemini.assert_not_called()


def test_invalid_length(client, mock_gemini):
    resp = post_summary(client, read_testdata("vi_500.txt"), "extra-long")

    assert resp.status_code == 400
    assert resp.get_json()["error_code"] == "VALIDATION_ERROR"


def test_missing_text(client):
    resp = client.post(ENDPOINT, json={}, headers=HEADERS)

    assert resp.status_code == 400
    assert resp.get_json()["error_code"] == "TEXT_TOO_SHORT"


def test_body_is_not_json_object(client):
    resp = client.post(ENDPOINT, json=["không phải object"], headers=HEADERS)

    assert resp.status_code == 400
    assert resp.get_json()["error_code"] == "VALIDATION_ERROR"


def test_missing_device_id(client, mock_gemini):
    resp = post_summary(client, read_testdata("vi_500.txt"), headers={"X-App-Version": "1.0.0"})

    assert resp.status_code == 400
    assert resp.get_json()["error_code"] == "INVALID_DEVICE_ID"


def test_invalid_device_id(client, mock_gemini):
    resp = post_summary(
        client,
        read_testdata("vi_500.txt"),
        headers={"X-Device-ID": "not-a-uuid", "X-App-Version": "1.0.0"},
    )

    assert resp.status_code == 400
    assert resp.get_json()["error_code"] == "INVALID_DEVICE_ID"


def test_missing_app_version(client, mock_gemini):
    resp = post_summary(client, read_testdata("vi_500.txt"), headers={"X-Device-ID": DEVICE_ID})

    assert resp.status_code == 426
    assert resp.get_json()["error_code"] == "UPDATE_REQUIRED"


def test_old_app_version(client, mock_gemini):
    resp = post_summary(
        client,
        read_testdata("vi_500.txt"),
        headers={"X-Device-ID": DEVICE_ID, "X-App-Version": "0.9.0"},
    )

    assert resp.status_code == 426
    assert resp.get_json()["error_code"] == "UPDATE_REQUIRED"


def test_fallback_to_tfidf_when_gemini_unavailable(client):
    """Không có client Gemini → route vẫn trả 201 với source=tfidf (SPEC 5.6)."""
    with patch.object(GeminiService, "get_client", return_value=None):
        resp = post_summary(client, read_testdata("vi_500.txt"))

    assert resp.status_code == 201
    data = resp.get_json()["data"]
    assert data["source"] == "tfidf"
    assert data["language"] == "vi"
    assert len(data["summary"]) > 0


def test_injection_text_still_summarized(client, mock_gemini):
    resp = post_summary(client, read_testdata("injection.txt"))

    assert resp.status_code == 201
    assert len(resp.get_json()["data"]["summary"]) > 0


def test_emoji_text_does_not_crash(client, mock_gemini):
    text = read_testdata("emoji.txt")
    resp = post_summary(client, text)

    assert resp.status_code == 201
    assert resp.get_json()["data"]["original_length"] == len(normalize_text(text))


def test_rate_limited_by_ip():
    app = create_app(RateLimitConfig)
    limiter.reset()
    client = app.test_client()
    limit = Config.RATE_LIMIT_PER_MINUTE

    for _ in range(limit):
        assert client.get("/api/v1/config").status_code == 200

    resp = client.get("/api/v1/config")
    assert resp.status_code == 429
    assert resp.get_json()["error_code"] == "RATE_LIMITED"
    limiter.reset()


def test_health_exempt_from_rate_limit():
    app = create_app(RateLimitConfig)
    limiter.reset()
    client = app.test_client()

    for _ in range(Config.RATE_LIMIT_PER_MINUTE + 5):
        assert client.get("/health").status_code == 200
    limiter.reset()