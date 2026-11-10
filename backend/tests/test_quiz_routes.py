"""Route quiz (GĐ3.3): thứ tự chặn trước khi đốt lượt, hoàn lượt khi lỗi và cô lập thiết bị.

Cả ba tầng `history_service`, `quiz_service`, `GeminiService` và quota đều là giả
trong bộ nhớ: test không chạm Neon lẫn Gemini, nhưng đi đúng đường đi thật của
request nên "yêu cầu sai không mất lượt" và "AI lỗi được hoàn đúng một lượt"
được kiểm bằng số lần gọi, không bằng lời hứa.
"""

from unittest.mock import patch

import pytest

try:
    from backend.app import create_app
    from backend.config import Config
    from backend.services import history_service, quiz_service, quota_service
    from backend.services.gemini_service import GeminiService
    from backend.utils.errors import AppError, ErrorCode
except ImportError:
    from app import create_app
    from config import Config
    from services import history_service, quiz_service, quota_service
    from services.gemini_service import GeminiService
    from utils.errors import AppError, ErrorCode

DEVICE_A = "3f2504e0-4f89-41d3-9a0c-0305e82c3301"
DEVICE_B = "7c9e6679-7425-40de-944b-e07fc1f90ae7"
ORIGINAL = "Văn bản gốc dùng cho test quiz." + "x" * 400
SUMMARY_TEXT = "AI cá nhân hoá lộ trình học nhưng cũng tạo rủi ro lệ thuộc công cụ."
CREATE_PATH = "/api/v1/summaries/12/quizzes"
ATTEMPTS_PATH = "/api/v1/quizzes/5/attempts"

QUESTIONS = [
    {
        "id": 31,
        "position": 1,
        "question": "Lợi ích chính của AI trong giáo dục là gì?",
        "options": ["Cá nhân hóa việc học", "Giảm số giáo viên", "Tăng học phí", "Bỏ kiểm tra"],
        "correct_index": 0,
        "explanation": "Văn bản nhấn mạnh khả năng điều chỉnh nội dung theo từng học sinh.",
    }
]
QUIZ_FROM_AI = {
    "questions": [
        {k: q[k] for k in ("question", "options", "correct_index", "explanation")}
        for q in QUESTIONS
    ],
    "question_count": 1,
    "language": "vi",
    "source": "gemini",
}
SAVED_QUIZ = {
    "id": 5,
    "summary_id": 12,
    "question_count": 1,
    "language": "vi",
    "created_at": "2026-11-10T09:30:00+07:00",
    "questions": QUESTIONS,
}


def headers(device_id):
    return {"X-Device-ID": device_id, "X-App-Version": "1.0.0"}


class FakeStore:
    """Bản tóm tắt + quiz + quota trong bộ nhớ, ghi lại mọi lượt gọi theo thứ tự."""

    def __init__(self):
        self.calls = []
        self.quiz_used = 0
        self.summary_limit = Config.DAILY_SUMMARY_LIMIT
        self.quiz_limit = Config.DAILY_QUIZ_LIMIT
        self.original_length = len(ORIGINAL)
        self.save_error = None

    # --- history_service ---

    def get_summary(self, summary_id, device_id=None, user_id=None):
        self.calls.append(("get_summary", device_id, summary_id))
        if summary_id != 12 or device_id != DEVICE_A:
            raise AppError(ErrorCode.NOT_FOUND, message="Không tìm thấy bản tóm tắt này.")
        return {
            "id": summary_id,
            "title": "Tác động của AI tới giáo dục",
            "description": "Bài viết phân tích lợi ích và rủi ro của AI trong lớp học.",
            "summary": SUMMARY_TEXT,
            "original_text": ORIGINAL,
            "original_length": self.original_length,
            "language": "vi",
            "source": "gemini",
            "created_at": "2026-11-10T09:00:00+07:00",
        }

    # --- quota_service ---

    def reserve(self, owner, usage_type, day=None):
        self.calls.append(("reserve", owner, usage_type))
        if usage_type != quota_service.USAGE_QUIZ:
            raise AssertionError("Tạo quiz phải trừ lượt QUIZ, không phải lượt khác")
        if self.quiz_used >= self.quiz_limit:
            raise AppError(ErrorCode.QUOTA_EXCEEDED)
        self.quiz_used += 1
        return self.quiz_used

    def refund(self, owner, usage_type, day=None):
        self.calls.append(("refund", owner, usage_type))
        if usage_type == quota_service.USAGE_QUIZ:
            self.quiz_used = max(self.quiz_used - 1, 0)

    def get_usage(self, owner, day=None):
        return {
            "summary": {"used": 1, "limit": self.summary_limit, "remaining": 19},
            "quiz": {"used": self.quiz_used, "limit": self.quiz_limit,
                     "remaining": max(self.quiz_limit - self.quiz_used, 0)},
            "resets_at": quota_service.resets_at(),
        }

    # --- quiz_service ---

    def save_quiz(self, summary_id, quiz, device_id=None, user_id=None):
        self.calls.append(("save", device_id, summary_id, quiz["question_count"]))
        if self.save_error:
            raise self.save_error
        return {**SAVED_QUIZ, "summary_id": summary_id}

    def list_quizzes(self, summary_id, device_id=None, user_id=None):
        self.calls.append(("list", device_id, summary_id))
        if summary_id != 12 or device_id != DEVICE_A:
            raise AppError(ErrorCode.NOT_FOUND, message="Không tìm thấy bản tóm tắt này.")
        return {"summary_id": summary_id, "items": [SAVED_QUIZ], "total": 1}

    def get_quiz(self, quiz_id, device_id=None, user_id=None):
        self.calls.append(("detail", device_id, quiz_id))
        if quiz_id != 5 or device_id != DEVICE_A:
            raise AppError(ErrorCode.NOT_FOUND, message="Không tìm thấy quiz này.")
        return SAVED_QUIZ

    # --- quiz_attempts ---

    def submit_attempt(self, quiz, answers, device_id=None, user_id=None):
        """Chấm đơn giản tại chỗ để test route vẫn thấy shape thật của response."""
        self.calls.append(("submit", device_id, quiz["id"], tuple(answers)))
        results = [
            {
                "position": question["position"],
                "selected": selected,
                "correct_index": question["correct_index"],
                "is_correct": selected == question["correct_index"],
            }
            for question, selected in zip(quiz["questions"], answers)
        ]
        correct = sum(1 for r in results if r["is_correct"])
        total = len(results)
        return {
            "attempt_id": 9,
            "score": round(correct / total * 10, 1),
            "correct_count": correct,
            "total_count": total,
            "results": results,
            "submitted_at": "2026-11-10T09:35:00+07:00",
        }

    def list_attempts(self, quiz_id, device_id=None, user_id=None):
        self.calls.append(("attempts", device_id, quiz_id))
        if quiz_id != 5 or device_id != DEVICE_A:
            raise AppError(ErrorCode.NOT_FOUND, message="Không tìm thấy quiz này.")
        return {
            "quiz_id": quiz_id,
            "items": [
                {"id": 9, "score": 10.0, "correct_count": 1, "total_count": 1,
                 "submitted_at": "2026-11-10T09:35:00+07:00"}
            ],
            "total": 1,
        }


class TestConfig(Config):
    TESTING = True
    # Limiter 30 request/phút theo device dùng chung RAM với cả tiến trình test.
    RATELIMIT_ENABLED = False


@pytest.fixture
def client():
    return create_app(TestConfig).test_client()


@pytest.fixture(autouse=True)
def store(monkeypatch):
    fake = FakeStore()
    monkeypatch.setattr(history_service, "get_summary", fake.get_summary)
    monkeypatch.setattr(quota_service, "reserve", fake.reserve)
    monkeypatch.setattr(quota_service, "refund", fake.refund)
    monkeypatch.setattr(quota_service, "get_usage", fake.get_usage)
    monkeypatch.setattr(quiz_service, "save_quiz", fake.save_quiz)
    monkeypatch.setattr(quiz_service, "list_quizzes", fake.list_quizzes)
    monkeypatch.setattr(quiz_service, "get_quiz", fake.get_quiz)
    monkeypatch.setattr(quiz_service, "submit_attempt", fake.submit_attempt)
    monkeypatch.setattr(quiz_service, "list_attempts", fake.list_attempts)
    return fake


@pytest.fixture
def ai():
    """Gemini giả: mặc định trả 1 câu hợp lệ, test nào cần lỗi sẽ đổi side_effect."""
    with patch.object(GeminiService, "generate_quiz", return_value=QUIZ_FROM_AI) as mocked:
        yield mocked


def kinds(store):
    return [c[0] for c in store.calls]


# ---------- POST /summaries/{id}/quizzes ----------


def test_create_quiz_returns_the_api_shape(client, store, ai):
    resp = client.post(CREATE_PATH, headers=headers(DEVICE_A))

    assert resp.status_code == 201
    data = resp.get_json()["data"]
    assert set(data) == {
        "id", "summary_id", "question_count", "language", "created_at", "questions", "usage",
    }
    assert data["id"] == 5 and data["summary_id"] == 12
    assert data["questions"] == QUESTIONS
    assert data["usage"] == {"summary_remaining": 19, "quiz_remaining": 19}


def test_create_quiz_accepts_empty_json_body(client, store, ai):
    resp = client.post(CREATE_PATH, json={}, headers=headers(DEVICE_A))

    assert resp.status_code == 201


def test_create_quiz_passes_stored_text_to_ai(client, store, ai):
    client.post(CREATE_PATH, headers=headers(DEVICE_A))

    ai.assert_called_once_with(ORIGINAL, SUMMARY_TEXT, "vi")


def test_create_quiz_order_is_owner_then_length_then_reserve(client, store, ai):
    client.post(CREATE_PATH, headers=headers(DEVICE_A))

    assert kinds(store) == ["get_summary", "reserve", "save"]
    assert store.calls[1] == ("reserve", f"d:{DEVICE_A}", quota_service.USAGE_QUIZ)


def test_short_text_is_rejected_before_reserve(client, store, ai):
    """400 ký tự là điều kiện tiên quyết: chưa đặt chỗ thì chưa có gì để hoàn."""
    store.original_length = Config.MIN_CHARS - 1

    resp = client.post(CREATE_PATH, headers=headers(DEVICE_A))

    assert resp.status_code == 400
    assert resp.get_json()["error_code"] == ErrorCode.QUIZ_TEXT_TOO_SHORT
    assert kinds(store) == ["get_summary"]
    ai.assert_not_called()


def test_foreign_summary_is_404_before_reserve(client, store, ai):
    resp = client.post("/api/v1/summaries/12/quizzes", headers=headers(DEVICE_B))

    assert resp.status_code == 404
    assert resp.get_json()["error_code"] == ErrorCode.NOT_FOUND
    assert kinds(store) == ["get_summary"]
    ai.assert_not_called()


def test_missing_summary_is_404(client, store, ai):
    resp = client.post("/api/v1/summaries/999999/quizzes", headers=headers(DEVICE_A))

    assert resp.status_code == 404
    ai.assert_not_called()


@pytest.mark.parametrize(
    "error",
    [
        AppError(ErrorCode.AI_UNAVAILABLE),
        RuntimeError("connection reset"),
    ],
)
def test_ai_failure_refunds_exactly_one_quiz_slot(client, store, ai, error):
    ai.side_effect = error

    resp = client.post(CREATE_PATH, headers=headers(DEVICE_A))

    assert resp.status_code == (503 if isinstance(error, AppError) else 500)
    assert kinds(store) == ["get_summary", "reserve", "refund"]
    assert store.quiz_used == 0


def test_save_failure_refunds_even_though_ai_succeeded(client, store, ai):
    store.save_error = RuntimeError("deadlock detected")

    resp = client.post(CREATE_PATH, headers=headers(DEVICE_A))

    assert resp.status_code == 500
    assert kinds(store) == ["get_summary", "reserve", "save", "refund"]
    assert store.quiz_used == 0


def test_exhausted_quiz_quota_calls_no_ai(client, store, ai):
    store.quiz_used = Config.DAILY_QUIZ_LIMIT

    resp = client.post(CREATE_PATH, headers=headers(DEVICE_A))

    assert resp.status_code == 429
    assert resp.get_json()["error_code"] == ErrorCode.QUOTA_EXCEEDED
    assert kinds(store) == ["get_summary", "reserve"]
    ai.assert_not_called()


def test_failed_reserve_is_not_refunded(client, store, ai):
    """Chưa đặt được chỗ thì không được hoàn: hoàn sẽ trừ nhầm lượt của lần trước."""
    store.quiz_used = Config.DAILY_QUIZ_LIMIT

    client.post(CREATE_PATH, headers=headers(DEVICE_A))

    assert "refund" not in kinds(store)


def test_refund_error_does_not_hide_ai_error(client, store, ai, monkeypatch):
    ai.side_effect = AppError(ErrorCode.AI_UNAVAILABLE)

    def broken_refund(*args, **kwargs):
        raise RuntimeError("db down")

    monkeypatch.setattr(quota_service, "refund", broken_refund)

    resp = client.post(CREATE_PATH, headers=headers(DEVICE_A))

    assert resp.status_code == 503
    assert resp.get_json()["error_code"] == ErrorCode.AI_UNAVAILABLE


def test_quiz_body_never_echoes_original_text(client, store, ai):
    body = client.post(CREATE_PATH, headers=headers(DEVICE_A)).get_json()

    assert ORIGINAL not in str(body)


# ---------- GET /summaries/{id}/quizzes ----------


def test_list_quizzes_shape(client, store):
    resp = client.get(CREATE_PATH, headers=headers(DEVICE_A))

    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert set(data) == {"summary_id", "items", "total"}
    assert data["summary_id"] == 12 and data["total"] == 1


def test_list_quizzes_never_calls_ai_or_quota(client, store, ai):
    client.get(CREATE_PATH, headers=headers(DEVICE_A))

    assert kinds(store) == ["list"]
    ai.assert_not_called()


def test_list_quizzes_of_another_device_is_404(client, store):
    resp = client.get(CREATE_PATH, headers=headers(DEVICE_B))

    assert resp.status_code == 404
    assert resp.get_json()["error_code"] == ErrorCode.NOT_FOUND


@pytest.mark.parametrize("bad_id", ["abc", "1.5"])
def test_non_integer_summary_id_is_json_404(client, store, bad_id):
    resp = client.get(f"/api/v1/summaries/{bad_id}/quizzes", headers=headers(DEVICE_A))

    assert resp.status_code == 404
    assert resp.get_json()["error_code"] == ErrorCode.NOT_FOUND


# ---------- GET /quizzes/{id} ----------


def test_quiz_detail_returns_decrypted_questions(client, store):
    resp = client.get("/api/v1/quizzes/5", headers=headers(DEVICE_A))

    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert set(data) == {
        "id", "summary_id", "question_count", "language", "created_at", "questions",
    }
    assert set(data["questions"][0]) == {
        "id", "position", "question", "options", "correct_index", "explanation",
    }
    assert len(data["questions"][0]["options"]) == 4


def test_quiz_detail_never_calls_ai_or_quota(client, store, ai):
    client.get("/api/v1/quizzes/5", headers=headers(DEVICE_A))

    assert kinds(store) == ["detail"]
    ai.assert_not_called()


def test_quiz_detail_of_another_device_is_404(client, store):
    resp = client.get("/api/v1/quizzes/5", headers=headers(DEVICE_B))

    assert resp.status_code == 404
    assert resp.get_json()["message"] == "Không tìm thấy quiz này."


def test_quiz_detail_of_missing_id_is_404(client, store):
    resp = client.get("/api/v1/quizzes/999999", headers=headers(DEVICE_A))

    assert resp.status_code == 404


# ---------- POST /quizzes/{id}/attempts ----------


def test_submit_attempt_returns_the_documented_shape(client, store):
    resp = client.post(ATTEMPTS_PATH, json={"answers": [0]}, headers=headers(DEVICE_A))

    assert resp.status_code == 201
    data = resp.get_json()["data"]
    assert set(data) == {"attempt_id", "score", "correct_count", "total_count", "results",
                         "submitted_at"}
    assert data["attempt_id"] == 9
    assert data["score"] == 10.0 and data["correct_count"] == 1 and data["total_count"] == 1
    assert data["results"] == [
        {"position": 1, "selected": 0, "correct_index": 0, "is_correct": True}
    ]
    assert data["submitted_at"] == "2026-11-10T09:35:00+07:00"


def test_submit_attempt_grades_against_stored_correct_index(client, store):
    """Câu 1 có `correct_index` = 0 trong DB; chọn 1 phải 0 điểm dù client tin là đúng."""
    resp = client.post(ATTEMPTS_PATH, json={"answers": [1]}, headers=headers(DEVICE_A))

    data = resp.get_json()["data"]
    assert data["score"] == 0.0
    assert data["results"][0]["is_correct"] is False
    assert data["results"][0]["correct_index"] == 0


def test_submit_attempt_ignores_numbers_sent_by_client(client, store):
    resp = client.post(
        ATTEMPTS_PATH,
        json={"answers": [2], "score": 10.0, "correct_count": 99, "total_count": 1,
              "results": [{"position": 1, "is_correct": True}]},
        headers=headers(DEVICE_A),
    )

    data = resp.get_json()["data"]
    assert data["score"] == 0.0 and data["correct_count"] == 0
    # Việc duy nhất xuống tầng lưu trữ là mảng index đã chọn, không phải điểm.
    assert store.calls[-1] == ("submit", DEVICE_A, 5, (2,))


def test_submit_attempt_passes_the_device_of_the_caller(client, store):
    client.post(ATTEMPTS_PATH, json={"answers": [0]}, headers=headers(DEVICE_A))

    assert store.calls[-1][1] == DEVICE_A


def test_submit_attempt_never_touches_quota_or_ai(client, store, ai):
    client.post(ATTEMPTS_PATH, json={"answers": [0]}, headers=headers(DEVICE_A))

    assert kinds(store) == ["detail", "submit"]
    ai.assert_not_called()


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"answers": None},
        {"answers": "0"},
        {"answers": {}},
        {"answers": []},
        {"answers": [0, 1]},
        {"answers": [4]},
        {"answers": [-1]},
        {"answers": ["0"]},
        {"answers": [0.0]},
        {"answers": [True]},
        {"answers": [None, 0]},
    ],
)
def test_invalid_answers_are_validation_error_without_grading(client, store, body):
    resp = client.post(ATTEMPTS_PATH, json=body, headers=headers(DEVICE_A))

    assert resp.status_code == 400
    assert resp.get_json()["error_code"] == ErrorCode.VALIDATION_ERROR
    assert "submit" not in kinds(store)


def test_skipped_question_is_accepted_as_null(client, store):
    resp = client.post(ATTEMPTS_PATH, json={"answers": [None]}, headers=headers(DEVICE_A))

    assert resp.status_code == 201
    assert resp.get_json()["data"]["score"] == 0.0
    assert store.calls[-1] == ("submit", DEVICE_A, 5, (None,))


@pytest.mark.parametrize("body", [None, [0], "abc"])
def test_body_must_be_a_json_object(client, store, body):
    resp = client.post(ATTEMPTS_PATH, json=body, headers=headers(DEVICE_A))

    assert resp.status_code == 400
    assert resp.get_json()["error_code"] == ErrorCode.VALIDATION_ERROR


def test_submit_attempt_of_another_device_is_404_before_grading(client, store):
    resp = client.post(ATTEMPTS_PATH, json={"answers": [0]}, headers=headers(DEVICE_B))

    assert resp.status_code == 404
    assert resp.get_json()["error_code"] == ErrorCode.NOT_FOUND
    assert kinds(store) == ["detail"]


def test_submit_attempt_of_missing_quiz_is_404(client, store):
    resp = client.post("/api/v1/quizzes/999999/attempts", json={"answers": [0]},
                       headers=headers(DEVICE_A))

    assert resp.status_code == 404
    assert "submit" not in kinds(store)


# ---------- GET /quizzes/{id}/attempts ----------


def test_list_attempts_returns_scores_without_answers(client, store):
    resp = client.get(ATTEMPTS_PATH, headers=headers(DEVICE_A))

    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert set(data) == {"quiz_id", "items", "total"}
    assert data["quiz_id"] == 5 and data["total"] == 1
    assert set(data["items"][0]) == {"id", "score", "correct_count", "total_count", "submitted_at"}


def test_list_attempts_never_touches_quota_or_ai(client, store, ai):
    client.get(ATTEMPTS_PATH, headers=headers(DEVICE_A))

    assert kinds(store) == ["attempts"]
    ai.assert_not_called()


def test_list_attempts_of_another_device_is_404(client, store):
    resp = client.get(ATTEMPTS_PATH, headers=headers(DEVICE_B))

    assert resp.status_code == 404
    assert resp.get_json()["message"] == "Không tìm thấy quiz này."


@pytest.mark.parametrize("bad_id", ["abc", "1.5"])
def test_non_integer_quiz_id_for_attempts_is_json_404(client, store, bad_id):
    resp = client.get(f"/api/v1/quizzes/{bad_id}/attempts", headers=headers(DEVICE_A))

    assert resp.status_code == 404
    assert resp.get_json()["error_code"] == ErrorCode.NOT_FOUND


# ---------- headers và đăng ký route ----------


@pytest.mark.parametrize(
    ("method", "path"),
    [("post", CREATE_PATH), ("get", CREATE_PATH), ("get", "/api/v1/quizzes/5"),
     ("post", ATTEMPTS_PATH), ("get", ATTEMPTS_PATH)],
)
def test_quiz_routes_require_device_id(client, store, method, path):
    resp = getattr(client, method)(path, headers={"X-App-Version": "1.0.0"})

    assert resp.status_code == 400
    assert resp.get_json()["error_code"] == ErrorCode.INVALID_DEVICE_ID


@pytest.mark.parametrize(
    ("method", "path"),
    [("post", CREATE_PATH), ("get", CREATE_PATH), ("get", "/api/v1/quizzes/5"),
     ("post", ATTEMPTS_PATH), ("get", ATTEMPTS_PATH)],
)
def test_quiz_routes_require_current_app_version(client, store, method, path):
    resp = getattr(client, method)(path, headers={"X-Device-ID": DEVICE_A, "X-App-Version": "0.9.0"})

    assert resp.status_code == 426
    assert resp.get_json()["error_code"] == ErrorCode.UPDATE_REQUIRED


def test_quiz_routes_are_registered():
    rules = {
        (str(rule), tuple(sorted(rule.methods)))
        for rule in create_app().url_map.iter_rules()
        if rule.endpoint.startswith("quiz.")
    }

    assert ("/api/v1/summaries/<int:summary_id>/quizzes", ("OPTIONS", "POST")) in rules
    assert ("/api/v1/summaries/<int:summary_id>/quizzes", ("GET", "HEAD", "OPTIONS")) in rules
    assert ("/api/v1/quizzes/<int:quiz_id>", ("GET", "HEAD", "OPTIONS")) in rules
    assert ("/api/v1/quizzes/<int:quiz_id>/attempts", ("OPTIONS", "POST")) in rules
    assert ("/api/v1/quizzes/<int:quiz_id>/attempts", ("GET", "HEAD", "OPTIONS")) in rules
