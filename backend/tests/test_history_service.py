import base64
import os
from contextlib import contextmanager
from datetime import datetime, timezone

import pytest

try:
    from backend.config import Config
    from backend.services import history_service
    from backend.services.crypto_service import CryptoService, KEY_BYTES
    from backend.utils.errors import AppError, ErrorCode
except ImportError:
    from config import Config
    from services import history_service
    from services.crypto_service import CryptoService, KEY_BYTES
    from utils.errors import AppError, ErrorCode

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


class FakeReadCursor:
    """Cursor giả cho chiều đọc: mỗi execute() lấy kết quả kế tiếp trong `responses`."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []
        self._last = None

    def execute(self, sql, params=None):
        self.calls.append((sql, params))
        self._last = self.responses.pop(0)

    def fetchone(self):
        return self._last

    def fetchall(self):
        return self._last or []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


@pytest.fixture
def db(monkeypatch):
    """Patch `transaction()` của history_service, trả hàm dựng cursor theo kết quả định trước."""
    holder = {}

    @contextmanager
    def _cm():
        class _Conn:
            def cursor(self):
                return holder["cur"]

            def commit(self):
                pass

            def rollback(self):
                pass

        yield _Conn()

    monkeypatch.setattr(history_service, "transaction", _cm)

    def use(responses):
        holder["cur"] = FakeReadCursor(responses)
        return holder["cur"]

    return use


def row_for(key, summary_id=12, when=datetime(2026, 11, 10, 2, 30, tzinfo=timezone.utc)):
    return (
        summary_id,
        key.encrypt(RESULT["title"]),
        key.encrypt(RESULT["description"]),
        RESULT["language"],
        RESULT["source"],
        when,
    )


def test_list_summaries_returns_only_title_and_description(db, key):
    older = row_for(key, 11, when=datetime(2026, 11, 9, 2, 30, tzinfo=timezone.utc))
    cur = db([[row_for(key), older], (37,)])

    data = history_service.list_summaries(device_id="device-1", page=1, limit=20)

    assert data["page"] == 1 and data["limit"] == 20 and data["total"] == 37
    assert [i["id"] for i in data["items"]] == [12, 11]
    assert data["items"][0]["title"] == RESULT["title"]
    assert data["items"][0]["created_at"] == "2026-11-10T09:30:00+07:00"
    assert set(data["items"][0]) == {
        "id", "title", "description", "language", "source", "created_at",
    }
    sql = cur.calls[0][0]
    assert "original_text_enc" not in sql and "summary_enc" not in sql


def test_list_summaries_orders_and_offsets(db, key):
    cur = db([[], (0,)])

    history_service.list_summaries(device_id="device-1", page=3, limit=10)

    sql, params = cur.calls[0]
    assert "ORDER BY created_at DESC, id DESC" in sql
    assert "LIMIT %s OFFSET %s" in sql
    assert params == (None, "device-1", 10, 20)
    assert cur.calls[1][1] == (None, "device-1")


def test_owner_predicate_matches_spec_5_7_on_every_query(db, key):
    """Một mẫu điều kiện sở hữu duy nhất, không route nào tự viết WHERE riêng."""
    cur = db([[], (0,)])
    history_service.list_summaries(device_id="device-1", user_id=42, page=1, limit=20)

    expected = "(user_id = %s OR (user_id IS NULL AND device_id = %s))"
    for sql, params in cur.calls:
        assert expected in sql
        assert params[:2] == (42, "device-1")


def test_get_summary_returns_plaintext_with_original_text(db, key):
    detail = (
        key.encrypt(RESULT["title"]),
        key.encrypt(RESULT["description"]),
        key.encrypt(PLAINTEXT),
        key.encrypt(RESULT["summary"]),
        len(PLAINTEXT),
        RESULT["language"],
        RESULT["source"],
        datetime(2026, 11, 10, 2, 30, tzinfo=timezone.utc),
    )
    cur = db([detail])

    data = history_service.get_summary(12, device_id="device-1")

    assert data["id"] == 12
    assert data["original_text"] == PLAINTEXT
    assert data["summary"] == RESULT["summary"]
    assert data["original_length"] == len(PLAINTEXT)
    assert data["created_at"] == "2026-11-10T09:30:00+07:00"
    sql, params = cur.calls[0]
    assert "WHERE id = %s AND" in sql
    assert params == (12, None, "device-1")


def test_get_summary_of_foreign_row_is_not_found(db, key):
    cur = db([None])

    with pytest.raises(AppError) as excinfo:
        history_service.get_summary(12, device_id="trộm-1")

    assert excinfo.value.error_code == ErrorCode.NOT_FOUND
    assert excinfo.value.status_code == 404
    assert cur.calls[0][1] == (12, None, "trộm-1")


def test_delete_summary_checks_owner_in_the_same_statement(db, key):
    cur = db([(12,)])

    assert history_service.delete_summary(12, device_id="device-1") is None

    sql, params = cur.calls[0]
    assert sql.strip().startswith("DELETE FROM summaries")
    assert "WHERE id = %s AND" in sql and "RETURNING id" in sql
    assert params == (12, None, "device-1")


def test_delete_summary_of_foreign_row_is_not_found(db, key):
    db([None])

    with pytest.raises(AppError) as excinfo:
        history_service.delete_summary(12, device_id="trộm-1")

    assert excinfo.value.status_code == 404


def test_reads_stop_before_database_when_key_missing(db, monkeypatch):
    """Không có ENCRYPTION_KEY thì không được gửi SELECT: giải mã chắc chắn fail, DB khỏi tốn kết nối."""
    cur = db([[], (0,)])
    monkeypatch.setattr(Config, "ENCRYPTION_KEY", "")

    with pytest.raises(ValueError, match="ENCRYPTION_KEY"):
        history_service.list_summaries(device_id="device-1")

    assert cur.calls == []

