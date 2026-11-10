"""Tầng lưu trữ quiz (GĐ3.3): một transaction cho session + N câu hỏi, mã hóa từng cột văn bản.

Cursor được thay bằng bảng trả lời định trước để test không chạm Neon. Điều kiện
sở hữu nằm trong câu SELECT nên "quiz của thiết bị khác" và "quiz không tồn tại"
cho cùng một kết quả — đúng SPEC 5.7.
"""

import base64
import json
import os
import re
from contextlib import contextmanager
from datetime import datetime, timezone

import pytest

try:
    from backend.config import Config
    from backend.services import quiz_service
    from backend.services.crypto_service import CryptoService, KEY_BYTES
    from backend.utils.errors import AppError, ErrorCode
except ImportError:
    from config import Config
    from services import quiz_service
    from services.crypto_service import CryptoService, KEY_BYTES
    from utils.errors import AppError, ErrorCode

WHEN = datetime(2026, 11, 10, 2, 30, tzinfo=timezone.utc)
QUESTION_TEXT = "Lợi ích chính của AI trong giáo dục là gì?"
OPTIONS = ["Cá nhân hóa việc học", "Giảm số giáo viên", "Tăng học phí", "Bỏ kiểm tra"]
EXPLANATION = "Văn bản nhấn mạnh khả năng điều chỉnh nội dung theo từng học sinh."


def question_payload(index):
    return {
        "question": f"{QUESTION_TEXT} {index}",
        "options": list(OPTIONS),
        "correct_index": 2,
        "explanation": EXPLANATION,
    }


QUIZ = {
    "questions": [question_payload(i) for i in range(1, 4)],
    "question_count": 3,
    "language": "vi",
    "source": "gemini",
}


class FakeCursor:
    """Mỗi execute() lấy kết quả kế tiếp: tuple = một dòng, list = nhiều dòng, Exception = lỗi DB."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []
        self._last = None
        self.commits = 0

    def execute(self, sql, params=None):
        self.calls.append((sql, params))
        if not self.responses:
            raise AssertionError("Service gửi thêm truy vấn ngoài dự kiến của test")
        self._last = self.responses.pop(0)
        if isinstance(self._last, Exception):
            raise self._last

    def fetchone(self):
        if isinstance(self._last, list):
            return self._last[0] if self._last else None
        return self._last

    def fetchall(self):
        if isinstance(self._last, list):
            return self._last
        return [] if self._last is None else [self._last]

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


@pytest.fixture
def key(monkeypatch):
    key_b64 = base64.b64encode(os.urandom(KEY_BYTES)).decode("ascii")
    monkeypatch.setattr(Config, "ENCRYPTION_KEY", key_b64)
    return CryptoService.from_b64_key(key_b64)


@pytest.fixture
def db(monkeypatch):
    """Thay `transaction()` của quiz_service, mô phỏng đúng commit/rollback của database.db."""
    holder = {"cur": None, "commits": 0, "rollbacks": 0}

    @contextmanager
    def _cm():
        class _Conn:
            def cursor(self):
                return holder["cur"]

            def commit(self):
                holder["commits"] += 1

            def rollback(self):
                holder["rollbacks"] += 1

        conn = _Conn()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    monkeypatch.setattr(quiz_service, "transaction", _cm)

    def use(responses):
        holder["cur"] = FakeCursor(responses)
        return holder["cur"]

    use.stats = holder
    return use


def stored_question(cur, index=0):
    """params của câu INSERT quiz_questions thứ `index`."""
    inserts = [c for c in cur.calls if "INSERT INTO quiz_questions" in c[0]]
    return inserts[index]


# ---------- save_quiz ----------


def test_save_quiz_writes_one_session_and_every_question(db, key):
    cur = db([(5, WHEN), (31,), (32,), (33,)])

    data = quiz_service.save_quiz(12, QUIZ, device_id="device-1")

    session_sql, session_params = cur.calls[0]
    assert "INSERT INTO quiz_sessions" in session_sql
    assert "RETURNING id, created_at" in session_sql
    assert session_params == (None, "device-1", 12, 3, "vi")

    question_calls = [c for c in cur.calls if "INSERT INTO quiz_questions" in c[0]]
    assert len(question_calls) == 3
    assert [c[1][1] for c in question_calls] == [1, 2, 3]
    assert all(c[1][0] == 5 for c in question_calls)
    assert data["id"] == 5 and data["summary_id"] == 12
    assert data["question_count"] == 3
    assert data["created_at"] == "2026-11-10T09:30:00+07:00"
    assert [q["id"] for q in data["questions"]] == [31, 32, 33]
    assert [q["position"] for q in data["questions"]] == [1, 2, 3]


def test_save_quiz_commits_once_for_the_whole_quiz(db, key):
    """Session và câu hỏi phải nằm trong MỘT transaction: không bao giờ có quiz thiếu câu."""
    db([(5, WHEN), (31,), (32,), (33,)])

    quiz_service.save_quiz(12, QUIZ, device_id="device-1")

    assert db.stats["commits"] == 1
    assert db.stats["rollbacks"] == 0


def test_save_quiz_rolls_back_when_a_question_insert_fails(db, key):
    """Lỗi ở câu thứ 3 phải hủy cả quiz, không để lại session cụt trên Neon."""
    cur = db([(5, WHEN), (31,), (32,), RuntimeError("duplicate key")])

    with pytest.raises(RuntimeError, match="duplicate key"):
        quiz_service.save_quiz(12, QUIZ, device_id="device-1")

    assert db.stats["commits"] == 0
    assert db.stats["rollbacks"] == 1
    assert len([c for c in cur.calls if "INSERT INTO quiz_questions" in c[0]]) == 3


def test_save_quiz_encrypts_question_options_and_explanation(db, key):
    cur = db([(5, WHEN), (31,), (32,), (33,)])

    quiz_service.save_quiz(12, QUIZ, device_id="device-1")

    _, params = stored_question(cur)
    quiz_id, position, question_enc, options_enc, correct_index, explanation_enc = params

    assert position == 1
    assert correct_index == 2
    for token in (question_enc, options_enc, explanation_enc):
        assert QUESTION_TEXT not in token
        assert OPTIONS[0] not in token
        base64.b64decode(token, validate=True)

    assert key.decrypt(question_enc) == f"{QUESTION_TEXT} 1"
    assert key.decrypt(explanation_enc) == EXPLANATION
    # options_enc là JSON mảng 4 đáp án, giữ nguyên dấu tiếng Việt (không escape \u).
    assert json.loads(key.decrypt(options_enc)) == OPTIONS
    assert "\\u" not in key.decrypt(options_enc)


def test_save_quiz_returns_plaintext_question_shape_from_api(db, key):
    db([(5, WHEN), (31,), (32,), (33,)])

    data = quiz_service.save_quiz(12, QUIZ, device_id="device-1")

    assert set(data) == {
        "id", "summary_id", "question_count", "language", "created_at", "questions",
    }
    assert set(data["questions"][0]) == {
        "id", "position", "question", "options", "correct_index", "explanation",
    }
    assert data["questions"][0]["question"] == f"{QUESTION_TEXT} 1"
    assert data["questions"][0]["options"] == OPTIONS


def test_save_quiz_stops_before_database_when_key_missing(db, monkeypatch):
    cur = db([(5, WHEN)])
    monkeypatch.setattr(Config, "ENCRYPTION_KEY", "")

    with pytest.raises(ValueError, match="ENCRYPTION_KEY"):
        quiz_service.save_quiz(12, QUIZ, device_id="device-1")

    assert cur.calls == []
    assert db.stats["commits"] == 0


# ---------- quyền sở hữu ----------


SQL_CONSTANTS = {
    name: value
    for name, value in vars(quiz_service).items()
    # OWNER_MATCH_SQL bị loại: nó là mảnh điều kiện ghép vào câu khác, không đứng một mình.
    if name.endswith("_SQL") and value.strip().upper().startswith(("SELECT", "INSERT", "DELETE"))
}


@pytest.mark.parametrize("name", sorted(SQL_CONSTANTS))
def test_alias_used_in_a_statement_is_declared_in_that_statement(name):
    """Chuôi `s.` đến từ JOIN nên mọi câu dùng nó phải tự khai báo alias.

    Cursor giả không parses SQL, lỗi này chỉ lộ ra khi chạm PostgreSQL thật
    (`missing FROM-clause entry`), nên kiểm tra tĩnh ngay ở đây.
    """
    sql = SQL_CONSTANTS[name]
    for alias, table in (("s", "summaries"), ("qs", "quiz_sessions")):
        if re.search(rf"\b{alias}\.", sql):
            assert f"{table} {alias}" in sql, f"{name} dùng {alias}. nhưng không khai báo alias"


def test_owner_predicate_is_on_the_parent_summary(db, key):
    """Quiz theo `/summaries/{id}/quizzes`: quyền sở hữu lấy từ dòng `summaries` (GĐ4 gộp user)."""
    cur = db([(1,), [(5, 12, 3, "vi", WHEN)]])

    quiz_service.list_quizzes(12, device_id="device-1", user_id=42)

    sql, params = cur.calls[-1]
    assert "JOIN summaries s ON s.id = qs.summary_id" in sql
    assert "(s.user_id = %s OR (s.user_id IS NULL AND s.device_id = %s))" in sql
    assert params == (12, 42, "device-1")


def test_every_quiz_select_carries_the_owner_predicate(db, key):
    cur = db([(1,), [(5, 12, 3, "vi", WHEN)]])

    quiz_service.list_quizzes(12, device_id="device-1")

    for sql, _ in cur.calls:
        if "FROM quiz_sessions" in sql or "FROM summaries" in sql:
            assert "s.user_id = %s OR (s.user_id IS NULL AND s.device_id = %s)" in sql


def test_get_quiz_selects_through_join_not_by_own_user_id(db, key):
    cur = db([(5, 12, 3, "vi", WHEN), []])

    quiz_service.get_quiz(5, device_id="device-1")

    sql = cur.calls[0][0]
    assert "JOIN summaries s" in sql
    assert "qs.user_id" not in sql


# ---------- list_quizzes ----------


def test_list_quizzes_returns_items_without_question_bodies(db, key):
    cur = db([(1,), [(5, 12, 3, "vi", WHEN), (4, 12, 5, "vi", WHEN)]])

    data = quiz_service.list_quizzes(12, device_id="device-1")

    assert data == {
        "summary_id": 12,
        "items": [
            {"id": 5, "summary_id": 12, "question_count": 3, "language": "vi",
             "created_at": "2026-11-10T09:30:00+07:00"},
            {"id": 4, "summary_id": 12, "question_count": 5, "language": "vi",
             "created_at": "2026-11-10T09:30:00+07:00"},
        ],
        "total": 2,
    }
    sql = cur.calls[1][0]
    assert "question_text_enc" not in sql and "options_enc" not in sql
    assert "ORDER BY qs.created_at DESC, qs.id DESC" in sql


def test_list_quizzes_of_foreign_summary_is_404_before_reading_quiz(db, key):
    cur = db([None])

    with pytest.raises(AppError) as excinfo:
        quiz_service.list_quizzes(12, device_id="trộm-1")

    assert excinfo.value.error_code == ErrorCode.NOT_FOUND
    assert excinfo.value.status_code == 404
    assert excinfo.value.message == "Không tìm thấy bản tóm tắt này."
    assert len(cur.calls) == 1


def test_list_quizzes_empty_is_not_404(db, key):
    db([(1,), []])

    assert quiz_service.list_quizzes(12, device_id="device-1") == {
        "summary_id": 12, "items": [], "total": 0,
    }


# ---------- get_quiz ----------


def encrypted_question_rows(key, count=3):
    return [
        (30 + i, i, key.encrypt(f"{QUESTION_TEXT} {i}"),
         key.encrypt(json.dumps(OPTIONS, ensure_ascii=False)), 2,
         key.encrypt(EXPLANATION))
        for i in range(1, count + 1)
    ]


def test_get_quiz_returns_decrypted_questions_ordered_by_position(db, key):
    cur = db([(5, 12, 3, "vi", WHEN), encrypted_question_rows(key)])

    data = quiz_service.get_quiz(5, device_id="device-1")

    assert data["id"] == 5 and data["summary_id"] == 12
    assert data["question_count"] == 3
    assert [q["position"] for q in data["questions"]] == [1, 2, 3]
    assert data["questions"][0]["question"] == f"{QUESTION_TEXT} 1"
    assert data["questions"][0]["options"] == OPTIONS
    assert data["questions"][0]["correct_index"] == 2
    assert "qs.id = %s" in cur.calls[0][0]
    assert cur.calls[0][1] == (5, None, "device-1")
    assert cur.calls[1][1] == (5,)


def test_get_quiz_of_missing_or_foreign_id_is_404(db, key):
    cur = db([None])

    with pytest.raises(AppError) as excinfo:
        quiz_service.get_quiz(999999, device_id="device-1")

    assert excinfo.value.error_code == ErrorCode.NOT_FOUND
    assert excinfo.value.status_code == 404
    assert excinfo.value.message == "Không tìm thấy quiz này."
    assert len(cur.calls) == 1


def test_get_quiz_stops_before_database_when_key_missing(db, monkeypatch):
    cur = db([(5, 12, 3, "vi", WHEN)])
    monkeypatch.setattr(Config, "ENCRYPTION_KEY", "")

    with pytest.raises(ValueError, match="ENCRYPTION_KEY"):
        quiz_service.get_quiz(5, device_id="device-1")

    assert cur.calls == []
