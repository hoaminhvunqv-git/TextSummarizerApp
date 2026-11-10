from contextlib import contextmanager
from datetime import date, datetime, timedelta

import pytest

try:
    from backend.config import Config
    from backend.services import quota_service
    from backend.utils.errors import AppError, ErrorCode
except ImportError:
    from config import Config
    from services import quota_service
    from utils.errors import AppError, ErrorCode


class FakeCursor:
    def __init__(self, one=None, rows=None):
        self.one = one
        self.rows = rows or []
        self.calls = []

    def execute(self, sql, params=None):
        self.calls.append((sql, params))

    def fetchone(self):
        return self.one

    def fetchall(self):
        return self.rows

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class FakeConn:
    def __init__(self, cursor):
        self._cursor = cursor
        self.committed = 0

    def cursor(self):
        return self._cursor

    def commit(self):
        self.committed += 1

    def rollback(self):
        pass


def use_fake_db(monkeypatch, name, cursor):
    """Thay `transaction`/`connection` của quota_service bằng conn giả, không cần Postgres."""
    conn = FakeConn(cursor)

    @contextmanager
    def _cm():
        yield conn

    monkeypatch.setattr(quota_service, name, _cm)
    return conn


def test_owner_key_prefers_user_over_device():
    assert quota_service.owner_key(device_id="abc", user_id=7) == "u:7"
    assert quota_service.owner_key(device_id="abc") == "d:abc"


def test_owner_key_requires_an_owner():
    with pytest.raises(ValueError):
        quota_service.owner_key()


def test_limit_for_reads_config():
    assert quota_service.limit_for(quota_service.USAGE_SUMMARY) == Config.DAILY_SUMMARY_LIMIT
    assert quota_service.limit_for(quota_service.USAGE_QUIZ) == Config.DAILY_QUIZ_LIMIT
    with pytest.raises(ValueError):
        quota_service.limit_for("OCR")


def test_resets_at_is_next_midnight_plus_seven():
    assert quota_service.resets_at(date(2026, 11, 10)) == "2026-11-11T00:00:00+07:00"


def test_resets_at_without_day_is_in_the_future():
    stamp = datetime.fromisoformat(quota_service.resets_at())
    assert stamp.hour == 0 and stamp.minute == 0
    assert stamp.utcoffset() == timedelta(hours=7)
    assert stamp > datetime.now(quota_service.VN_TZ)
    assert stamp.date() == quota_service.today_vn() + timedelta(days=1)


def test_reserve_returns_count_after_booking(monkeypatch):
    cursor = FakeCursor(one=(5,))
    use_fake_db(monkeypatch, "transaction", cursor)

    day = date(2026, 11, 10)
    assert quota_service.reserve("d:abc", quota_service.USAGE_SUMMARY, day) == 5

    sql, params = cursor.calls[0]
    assert params == ("d:abc", "SUMMARY", day, Config.DAILY_SUMMARY_LIMIT)
    assert "ON CONFLICT" in sql and "RETURNING count" in sql
    # Điều kiện count < limit nằm trong chính câu UPDATE xung đột: hết lượt là không có dòng nào.
    assert "WHERE usage_quota.count < %s" in sql


def test_reserve_raises_quota_exceeded_when_ceiling_hit(monkeypatch):
    use_fake_db(monkeypatch, "transaction", FakeCursor(one=None))
    with pytest.raises(AppError) as exc:
        quota_service.reserve("d:abc", quota_service.USAGE_SUMMARY, date(2026, 11, 10))
    assert exc.value.error_code == ErrorCode.QUOTA_EXCEEDED
    assert exc.value.status_code == 429


def test_refund_never_goes_below_zero(monkeypatch):
    cursor = FakeCursor()
    use_fake_db(monkeypatch, "transaction", cursor)
    day = date(2026, 11, 10)

    quota_service.refund("d:abc", quota_service.USAGE_QUIZ, day)

    sql, params = cursor.calls[0]
    assert params == ("d:abc", "QUIZ", day)
    assert "GREATEST(count - 1, 0)" in sql


def test_get_usage_shape_matches_api_md(monkeypatch):
    cursor = FakeCursor(rows=[("SUMMARY", 3)])
    use_fake_db(monkeypatch, "connection", cursor)

    data = quota_service.get_usage("d:abc", date(2026, 11, 10))

    assert data["summary"] == {"used": 3, "limit": 20, "remaining": 17}
    assert data["quiz"] == {"used": 0, "limit": 20, "remaining": 20}
    assert data["resets_at"] == "2026-11-11T00:00:00+07:00"


def test_get_usage_clamps_remaining_at_zero(monkeypatch):
    """Dữ liệu cũ còn sót (limit đã hạ) không được trả remaining âm cho app."""
    cursor = FakeCursor(rows=[("SUMMARY", 25)])
    use_fake_db(monkeypatch, "connection", cursor)

    data = quota_service.get_usage("d:abc", date(2026, 11, 10))
    assert data["summary"]["remaining"] == 0
