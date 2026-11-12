"""Test giữ chân các lỗi tìm ra khi audit toàn repo ngày 2026-11-12.

Mỗi test ở đây tương ứng một lỗi đã sửa; xoá test là lỗi quay lại mà không ai biết.
"""

import json
import uuid
from unittest.mock import patch

import pytest
from psycopg2 import pool as pg_pool

try:
    from backend.app import create_app
    from backend.config import Config
    from backend.database import db
    from backend.services import gemini_service, history_service, quota_service
    from backend.services.gemini_service import GeminiService
    from backend.utils.errors import AppError, ErrorCode
    from backend.utils.time_utils import iso_in_vn, now_vn
except ImportError:
    from app import create_app
    from config import Config
    from database import db
    from services import gemini_service, history_service, quota_service
    from services.gemini_service import GeminiService
    from utils.errors import AppError, ErrorCode
    from utils.time_utils import iso_in_vn, now_vn

DEVICE_ID = "3f2504e0-4f89-41d3-9a0c-0305e82c3301"
HEADERS = {"X-Device-ID": DEVICE_ID, "X-App-Version": "1.0.0"}


class _NoRetryConfig(Config):
    TESTING = True
    RATELIMIT_ENABLED = True


def _fake_ai_result():
    return {
        "title": "Tiêu đề",
        "description": "Mô tả.",
        "summary": "Một đoạn tóm tắt liền mạch.",
        "language": "vi",
        "source": "gemini",
        "original_length": 450,
    }


# ---------------------------------------------------------------- limiter key


def test_rotating_garbage_device_ids_cannot_bypass_the_minute_limit():
    """Flask-Limiter chạy trước validate_device_id: nếu key lấy header thô thì
    mỗi request một `X-Device-ID` rác là vô hiệu hoá hoàn toàn 30 req/phút.
    Key rác phải rơi về IP, nên trần 30 vẫn chặn được."""
    app = create_app(_NoRetryConfig)
    client = app.test_client()

    codes = []
    for _ in range(Config.RATE_LIMIT_PER_MINUTE + 5):
        junk = uuid.uuid4().hex  # không phải UUID chuẩn 8-4-4-4-12
        resp = client.get(
            "/api/v1/config",
            headers={"X-Device-ID": junk.upper(), "X-App-Version": "1.0.0"},
        )
        codes.append(resp.status_code)
        if resp.status_code == 429:
            break

    from backend.extensions import limiter

    limiter.reset()
    assert 429 in codes, "header rác vẫn được dùng làm key chống spam"


# ---------------------------------------------------------------- thời gian


def test_iso_in_vn_survives_a_missing_timestamp():
    """Hàm này chạy SAU khi commit; nổ ở đây làm route hoàn lượt => tóm tắt miễn phí."""
    assert iso_in_vn(None) is None
    assert iso_in_vn(now_vn()).endswith("+07:00")


# ---------------------------------------------------------------- usage block


def test_summary_route_still_succeeds_when_usage_read_fails():
    app = create_app(_NoRetryConfig)
    client = app.test_client()

    with patch.object(GeminiService, "summarize", return_value=_fake_ai_result()), patch.object(
        history_service, "save_summary", return_value=(12, iso_in_vn(now_vn()))
    ), patch.object(quota_service, "reserve"), patch.object(
        quota_service, "get_usage", side_effect=RuntimeError("DB đứt")
    ), patch.object(quota_service, "refund") as refund:
        resp = client.post(
            "/api/v1/summaries",
            headers=HEADERS,
            json={"text": "a" * 450, "length": "short"},
        )

    assert resp.status_code == 201
    data = resp.get_json()["data"]
    assert data["usage"] == {"summary_remaining": None, "quiz_remaining": None}
    # Bản ghi đã lưu thành công thì tuyệt đối không được hoàn lượt.
    refund.assert_not_called()


# ---------------------------------------------------------------- SDK retries


def _call_and_capture(call):
    """Gọi `call()` với client giả và trả về GenerateContentConfig đã gửi."""
    payload = {
        "language": "vi",
        "title": "Tiêu đề",
        "description": "Mô tả.",
        "summary": "Một đoạn tóm tắt liền mạch.",
    }

    captured = {}

    class _Resp:
        text = json.dumps(payload)

    class _Models:
        def generate_content(self, **kwargs):
            captured.update(kwargs)
            return _Resp()

    class _Client:
        models = _Models()

    GeminiService.set_client(_Client())
    try:
        call()
    except Exception:
        # Bài test chỉ quan tâm config đã gửi đi; payload giả không qua được
        # `normalize_quiz_questions` thì vẫn phải đọc được config.
        pass
    finally:
        GeminiService.set_client(None)
    assert captured, "không có request nào được gửi nên không kiểm chứng được config"
    return captured["config"]


def test_summarize_disables_hidden_sdk_retries():
    """Mặc định SDK retry 5 lần với backoff 1/2/4/8s, nên `timeout` KHÔNG phải trần
    thời gian chờ (đo thật: 122,1s cho một request trong khi app bỏ ở 60s)."""
    config = _call_and_capture(
        lambda: gemini_service.GeminiService._call_gemini_api("văn bản " * 100, "short")
    )
    assert config.http_options.retry_options.attempts == 1


def test_quiz_disables_hidden_sdk_retries():
    config = _call_and_capture(
        lambda: gemini_service.GeminiService._call_quiz_api(
            "văn bản " * 100, "tóm tắt", "vi", 3
        )
    )
    assert config.http_options.retry_options.attempts == 1


# ---------------------------------------------------------------- pool


def test_exhausted_pool_is_reported_as_overload_not_generic_500():
    def boom():
        raise pg_pool.PoolError("connection pool exhaused")

    with patch.object(db, "get_pool", boom):
        with pytest.raises(AppError) as excinfo:
            db._checkout()

    assert excinfo.value.status_code == 503
    assert "bận" in excinfo.value.message
