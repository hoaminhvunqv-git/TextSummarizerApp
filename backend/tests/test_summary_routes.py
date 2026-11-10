from pathlib import Path
from unittest.mock import patch

import pytest

try:
    from backend.app import create_app
    from backend.config import Config
    from backend.extensions import limiter
    from backend.services import history_service, quota_service
    from backend.services.gemini_service import GeminiService
    from backend.utils.errors import AppError, ErrorCode
    from backend.utils.text_utils import detect_language, normalize_text
except ImportError:
    from app import create_app
    from config import Config
    from extensions import limiter
    from services import history_service, quota_service
    from services.gemini_service import GeminiService
    from utils.errors import AppError, ErrorCode
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
        "summary": "Đoạn tóm tắt liền mạch, không gạch đầu dòng."
        if language == "vi"
        else "A single flowing summary paragraph with no bullet points.",
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


class FakeStore:
    """quota_service + history_service trong bộ nhớ.

    Test route không được chạm Neon thật và cũng không được đốt Gemini key, nên
    mọi lời gọi xuống tầng lưu trữ đều đi qua đây.
    """

    def __init__(self):
        self.used = {}
        self.rows = []
        self.calls = []
        self.summary_limit = Config.DAILY_SUMMARY_LIMIT

    def reserve(self, owner, usage_type, day=None):
        self.calls.append(("reserve", owner))
        if usage_type != quota_service.USAGE_SUMMARY:
            return 0
        count = self.used.get(owner, 0)
        if count >= self.summary_limit:
            raise AppError(ErrorCode.QUOTA_EXCEEDED)
        self.used[owner] = count + 1
        return count + 1

    def refund(self, owner, usage_type, day=None):
        self.calls.append(("refund", owner))
        if usage_type == quota_service.USAGE_SUMMARY:
            self.used[owner] = max(self.used.get(owner, 0) - 1, 0)

    def get_usage(self, owner, day=None):
        used = self.used.get(owner, 0)
        limit = self.summary_limit
        return {
            "summary": {"used": used, "limit": limit, "remaining": max(limit - used, 0)},
            "quiz": {"used": 0, "limit": Config.DAILY_QUIZ_LIMIT, "remaining": Config.DAILY_QUIZ_LIMIT},
            "resets_at": quota_service.resets_at(),
        }

    def save_summary(self, result, text, device_id=None, user_id=None):
        self.calls.append(("save", device_id))
        self.rows.append({"result": result, "text": text, "device_id": device_id})
        return len(self.rows), "2026-11-10T09:30:00+07:00"


@pytest.fixture(autouse=True)
def store(monkeypatch):
    fake = FakeStore()
    monkeypatch.setattr(quota_service, "reserve", fake.reserve)
    monkeypatch.setattr(quota_service, "refund", fake.refund)
    monkeypatch.setattr(quota_service, "get_usage", fake.get_usage)
    monkeypatch.setattr(history_service, "save_summary", fake.save_summary)
    return fake


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
    text = read_testdata("vi_1200.txt")
    resp = post_summary(client, text, "medium")

    assert resp.status_code == 201
    payload = resp.get_json()
    assert payload["success"] is True
    assert payload["message"] == "Xử lý thành công"

    data = payload["data"]
    assert data["language"] == "vi"
    assert data["source"] == "gemini"
    assert data["id"] == 1
    assert data["original_length"] == len(normalize_text(text))
    assert data["created_at"].endswith("+07:00")
    # SPEC 1.2 (Phương án A): bản tóm tắt chỉ là 1 đoạn văn, không gạch đầu dòng
    assert "\n" not in data["summary"]
    assert "- " not in data["summary"]
    assert data["usage"] == {"summary_remaining": 19, "quiz_remaining": 20}


def test_summary_persists_for_the_calling_device(client, mock_gemini, store):
    """Bản tóm tắt phải được lưu cho đúng `X-Device-ID`, với văn bản đã NFC + strip."""
    text = read_testdata("vi_1200.txt")
    resp = post_summary(client, text, "medium")

    assert resp.status_code == 201
    row = store.rows[0]
    assert row["device_id"] == DEVICE_ID
    assert row["text"] == normalize_text(text)
    assert row["result"]["source"] == "gemini"


def test_summary_en_success(client, mock_gemini):
    resp = post_summary(client, read_testdata("en_400.txt"), "short")

    assert resp.status_code == 201
    assert resp.get_json()["data"]["language"] == "en"


@pytest.mark.parametrize("length", ["short", "medium", "long"])
def test_length_forwarded_to_service(client, mock_gemini, length):
    post_summary(client, read_testdata("vi_2500.txt"), length)

    assert mock_gemini.call_args.args[1] == length


@pytest.mark.parametrize("length", ["medium", "long"])
def test_locked_length_returns_error(client, mock_gemini, length):
    """Bản gốc 455 ký tự chưa mở mốc Vừa/Dài → 400 LENGTH_NOT_UNLOCKED, không gọi AI."""
    resp = post_summary(client, read_testdata("en_400.txt"), length)

    assert resp.status_code == 400
    assert resp.get_json()["error_code"] == "LENGTH_NOT_UNLOCKED"
    mock_gemini.assert_not_called()


def test_length_defaults_to_medium(client, mock_gemini):
    resp = post_summary(client, read_testdata("vi_1200.txt"))

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
        resp = post_summary(client, read_testdata("vi_1200.txt"))

    assert resp.status_code == 201
    data = resp.get_json()["data"]
    assert data["source"] == "tfidf"
    assert data["language"] == "vi"
    assert len(data["summary"]) > 0


def test_injection_text_still_summarized(client, mock_gemini):
    resp = post_summary(client, read_testdata("injection.txt"), "short")

    assert resp.status_code == 201
    assert len(resp.get_json()["data"]["summary"]) > 0


def test_emoji_text_does_not_crash(client, mock_gemini):
    text = read_testdata("emoji.txt")
    resp = post_summary(client, text, "short")

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


def test_daily_summary_limit_is_per_device(client, mock_gemini, store):
    """20 lượt/ngày do `usage_quota` chặn (không còn Flask-Limiter), vẫn chốt theo X-Device-ID."""
    text = read_testdata("en_400.txt")
    other_device = "7c9e6679-7425-40de-944b-e07fc1f90ae7"

    for i in range(Config.DAILY_SUMMARY_LIMIT):
        resp = post_summary(client, text, "short")
        assert resp.status_code == 201, f"lượt {i + 1} bị chặn sớm"

    resp = post_summary(client, text, "short")
    assert resp.status_code == 429
    assert resp.get_json()["error_code"] == "QUOTA_EXCEEDED"
    # Hết lượt phải chặn trước khi gọi AI, không đốt key Gemini cho request vô ích.
    assert mock_gemini.call_count == Config.DAILY_SUMMARY_LIMIT

    resp = post_summary(
        client, text, "short",
        headers={"X-Device-ID": other_device, "X-App-Version": "1.0.0"},
    )
    assert resp.status_code == 201


def test_day_limiter_removed_from_summaries(mock_gemini, store):
    """Flask-Limiter chỉ còn vai trò 30 request/phút: 25 lượt trong một phút phải trót."""
    store.summary_limit = 1000
    app = create_app(RateLimitConfig)
    limiter.reset()
    client = app.test_client()
    text = read_testdata("en_400.txt")

    statuses = [post_summary(client, text, "short").status_code for _ in range(25)]

    assert statuses == [201] * 25
    limiter.reset()


def test_invalid_request_does_not_consume_quota(client, mock_gemini, store):
    resp = post_summary(client, read_testdata("short_100.txt"))

    assert resp.status_code == 400
    assert store.used == {}
    assert store.calls == []


def test_gemini_failure_refunds_the_slot(client, store):
    with patch.object(GeminiService, "summarize", side_effect=RuntimeError("Gemini 503")):
        resp = post_summary(client, read_testdata("vi_1200.txt"), "short")

    assert resp.status_code == 500
    assert resp.get_json()["error_code"] == "INTERNAL_ERROR"
    assert ("refund", f"d:{DEVICE_ID}") in store.calls
    assert store.used.get(f"d:{DEVICE_ID}", 0) == 0


def test_save_failure_refunds_the_slot(client, mock_gemini, store, monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("DB từ chối ghi")

    monkeypatch.setattr(history_service, "save_summary", boom)
    resp = post_summary(client, read_testdata("vi_1200.txt"), "short")

    assert resp.status_code == 500
    assert store.used.get(f"d:{DEVICE_ID}", 0) == 0


def test_quota_is_booked_before_calling_ai(client, mock_gemini, store):
    post_summary(client, read_testdata("vi_1200.txt"), "short")

    assert store.calls[0] == ("reserve", f"d:{DEVICE_ID}")
    assert store.calls[1] == ("save", DEVICE_ID)
    mock_gemini.assert_called_once()