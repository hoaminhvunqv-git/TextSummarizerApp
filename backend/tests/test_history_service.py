import base64
import os
from contextlib import contextmanager
from datetime import datetime, timezone

import pytest

try:
    from backend.config import Config
    from backend.services import history_service
    from backend.services.crypto_service import CryptoService, KEY_BYTES
except ImportError:
    from config import Config
    from services import history_service
    from services.crypto_service import CryptoService, KEY_BYTES

PLAINTEXT = "AI đang thay đổi cách dạy và học ở Việt Nam, kèm emoji 🎓."
RESULT = {
    "title": "Tác động của AI tới giáo dục",
    "description": "Bài viết phân tích lợi ích và rủi ro của AI trong lớp học.",
    "summary": "AI cá nhân hoá lộ trình học nhưng cũng tạo rủi ro lệ thuộc công cụ.",
    "language": "vi",
    "source": "gemini",
}


class FakeCursor:
    def __init__(self, one=None):
        self.one = one
        self.calls = []

    def execute(self, sql, params=None):
        self.calls.append((sql, params))

    def fetchone(self):
        return self.one

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


@pytest.fixture
def key(monkeypatch):
    """Key test riêng, không đụng ENCRYPTION_KEY thật trong .env."""
    key_b64 = base64.b64encode(os.urandom(KEY_BYTES)).decode("ascii")
    monkeypatch.setattr(Config, "ENCRYPTION_KEY", key_b64)
    return CryptoService.from_b64_key(key_b64)


@pytest.fixture
def cursor(monkeypatch):
    fake = FakeCursor(one=(12, datetime(2026, 11, 10, 2, 30, tzinfo=timezone.utc)))

    @contextmanager
    def _cm():
        class _Conn:
            def cursor(self):
                return fake

            def commit(self):
                pass

            def rollback(self):
                pass

        yield _Conn()

    monkeypatch.setattr(history_service, "transaction", _cm)
    return fake


def test_save_summary_encrypts_all_four_text_fields(cursor, key):
    summary_id, created_at = history_service.save_summary(RESULT, PLAINTEXT, device_id="device-1")

    sql, params = cursor.calls[0]
    assert summary_id == 12
    assert created_at == "2026-11-10T09:30:00+07:00"
    assert "INSERT INTO summaries" in sql and "RETURNING id, created_at" in sql

    user_id, device_id, title_enc, desc_enc, original_enc, summary_enc, length, language, source = params
    assert (user_id, device_id) == (None, "device-1")
    assert (length, language, source) == (len(PLAINTEXT), "vi", "gemini")

    # Không cột nào được chứa plaintext, kể cả tên biến trong SQL cũng không có giá trị nội dung.
    for token in (title_enc, desc_enc, original_enc, summary_enc):
        assert PLAINTEXT not in token
        base64.b64decode(token, validate=True)
    assert key.decrypt(title_enc) == RESULT["title"]
    assert key.decrypt(desc_enc) == RESULT["description"]
    assert key.decrypt(original_enc) == PLAINTEXT
    assert key.decrypt(summary_enc) == RESULT["summary"]


def test_saved_tokens_are_unique_per_row(cursor, key):
    """Cùng một văn bản ghi hai lần phải ra hai chuỗi khác nhau (nonce ngẫu nhiên)."""
    history_service.save_summary(RESULT, PLAINTEXT, device_id="device-1")
    history_service.save_summary(RESULT, PLAINTEXT, device_id="device-1")

    first = cursor.calls[0][1][5]
    second = cursor.calls[1][1][5]

    assert first != second
    assert key.decrypt(first) == key.decrypt(second) == RESULT["summary"]


def test_missing_encryption_key_stops_before_database(cursor, monkeypatch):
    monkeypatch.setattr(Config, "ENCRYPTION_KEY", "")

    with pytest.raises(ValueError, match="ENCRYPTION_KEY"):
        history_service.save_summary(RESULT, PLAINTEXT, device_id="device-1")

    assert cursor.calls == []


def test_created_at_keeps_the_same_instant(cursor):
    moment = cursor.one[1]
    _, created_at = history_service.save_summary(RESULT, PLAINTEXT, device_id="device-1")

    assert datetime.fromisoformat(created_at) == moment
