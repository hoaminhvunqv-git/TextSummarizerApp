"""Ghi và đọc bảng `quiz_sessions` + `quiz_questions` + `quiz_attempts` (docs/SPEC.md 5.4 và 6).

Quyền sở hữu của quiz được kiểm **thông qua bản tóm tắt cha** vì đường đi của API
là `/summaries/{id}/quizzes`: người được xem bản tóm tắt thì xem được quiz của nó.
Nhờ vậy dữ liệu không "mất" khi GĐ4 gộp khách vào tài khoản (lúc đó `summaries.user_id`
đổi, còn `quiz_sessions.user_id` của bản ghi cũ vẫn NULL). Lượt làm bài cũng đi cùng
một mẫu điều kiện, không có bộ kiểm tra quyền riêng.
"""

import json
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Dict, List, Optional

try:
    from backend.config import Config
    from backend.database.db import transaction
    from backend.services.crypto_service import CryptoService
    from backend.utils.errors import AppError, ErrorCode
    from backend.utils.time_utils import iso_in_vn
except ImportError:
    from config import Config
    from database.db import transaction
    from services.crypto_service import CryptoService
    from utils.errors import AppError, ErrorCode
    from utils.time_utils import iso_in_vn

# SPEC 5.7: cùng một mẫu điều kiện sở hữu với history_service, áp cho dòng summaries.
OWNER_MATCH_SQL = "(s.user_id = %s OR (s.user_id IS NULL AND s.device_id = %s))"

INSERT_QUIZ_SQL = """
INSERT INTO quiz_sessions (user_id, device_id, summary_id, question_count, language)
VALUES (%s, %s, %s, %s, %s)
RETURNING id, created_at;
"""

INSERT_QUESTION_SQL = """
INSERT INTO quiz_questions
    (quiz_session_id, position, question_text_enc, options_enc, correct_index, explanation_enc)
VALUES (%s, %s, %s, %s, %s, %s)
RETURNING id;
"""

SELECT_QUIZ_PAGE_SQL = f"""
SELECT qs.id, qs.summary_id, qs.question_count, qs.language, qs.created_at
FROM quiz_sessions qs
JOIN summaries s ON s.id = qs.summary_id
WHERE qs.summary_id = %s AND {OWNER_MATCH_SQL}
ORDER BY qs.created_at DESC, qs.id DESC;
"""

SELECT_QUIZ_SQL = f"""
SELECT qs.id, qs.summary_id, qs.question_count, qs.language, qs.created_at
FROM quiz_sessions qs
JOIN summaries s ON s.id = qs.summary_id
WHERE qs.id = %s AND {OWNER_MATCH_SQL};
"""

SELECT_QUESTIONS_SQL = """
SELECT id, position, question_text_enc, options_enc, correct_index, explanation_enc
FROM quiz_questions
WHERE quiz_session_id = %s
ORDER BY position;
"""

# Kiểm bản tóm tắt cha có thuộc người gọi hay không trước khi liệt kê quiz, để
# id của người khác trả 404 y hệt các endpoint khác thay vì "trống" khó phân biệt.
# Alias `s` là bắt buộc: OWNER_MATCH_SQL viết cho câu có JOIN nên luôn mang `s.`.
SELECT_SUMMARY_OWNER_SQL = f"""
SELECT 1 FROM summaries s
WHERE s.id = %s AND {OWNER_MATCH_SQL};
"""

INSERT_ATTEMPT_SQL = """
INSERT INTO quiz_attempts
    (user_id, device_id, quiz_session_id, answers_json_enc, score, correct_count, total_count)
VALUES (%s, %s, %s, %s, %s, %s, %s)
RETURNING id, submitted_at;
"""

SELECT_ATTEMPTS_SQL = f"""
SELECT qa.id, qa.score, qa.correct_count, qa.total_count, qa.submitted_at
FROM quiz_attempts qa
JOIN quiz_sessions qs ON qs.id = qa.quiz_session_id
JOIN summaries s ON s.id = qs.summary_id
WHERE qa.quiz_session_id = %s AND {OWNER_MATCH_SQL}
ORDER BY qa.submitted_at DESC, qa.id DESC;
"""


def _not_found() -> AppError:
    """Cùng một thông điệp cho "không tồn tại" và "của người khác" (SPEC 5.7)."""
    return AppError(ErrorCode.NOT_FOUND, message="Không tìm thấy quiz này.")


def _summary_not_found() -> AppError:
    """Đúng chữ đã dùng ở `history_service` để app không cần phân biệt hai nơi."""
    return AppError(ErrorCode.NOT_FOUND, message="Không tìm thấy bản tóm tắt này.")


def _decrypt_question(crypto, row: tuple) -> Dict[str, Any]:
    question_id, position, question_enc, options_enc, correct_index, explanation_enc = row
    return {
        "id": question_id,
        "position": position,
        "question": crypto.decrypt(question_enc),
        "options": json.loads(crypto.decrypt(options_enc)),
        "correct_index": correct_index,
        "explanation": crypto.decrypt(explanation_enc),
    }


def save_quiz(summary_id: int, quiz: Dict[str, Any], device_id: Optional[str] = None,
              user_id: Optional[int] = None) -> Dict[str, Any]:
    """Ghi một quiz kèm từng câu hỏi đã mã hóa trong **một transaction**.

    Hoặc đủ cả session lẫn toàn bộ câu hỏi, hoặc không có gì — để không bao giờ
    tồn tại quiz thiếu câu (DoD GĐ3 yêu cầu số câu đúng theo độ dài văn bản).
    """
    crypto = CryptoService.from_b64_key(Config.ENCRYPTION_KEY)

    with transaction() as conn:
        with conn.cursor() as cur:
            cur.execute(
                INSERT_QUIZ_SQL,
                (user_id, device_id, summary_id, quiz["question_count"], quiz["language"]),
            )
            quiz_id, created_at = cur.fetchone()

            questions: List[Dict[str, Any]] = []
            for position, question in enumerate(quiz["questions"], start=1):
                cur.execute(
                    INSERT_QUESTION_SQL,
                    (
                        quiz_id,
                        position,
                        crypto.encrypt(question["question"]),
                        # options_enc là JSON mảng 4 đáp án (schema.sql mục quiz_questions)
                        crypto.encrypt(json.dumps(question["options"], ensure_ascii=False)),
                        question["correct_index"],
                        crypto.encrypt(question["explanation"]),
                    ),
                )
                questions.append({**question, "id": cur.fetchone()[0], "position": position})

    return {
        "id": quiz_id,
        "summary_id": summary_id,
        "question_count": quiz["question_count"],
        "language": quiz["language"],
        "created_at": iso_in_vn(created_at),
        "questions": questions,
    }


def list_quizzes(summary_id: int, device_id: Optional[str] = None,
                 user_id: Optional[int] = None) -> dict:
    """Mọi quiz từng tạo từ một bản tóm tắt, mới nhất trước; không có -> `items` rỗng.

    Danh sách này cố ý không kèm câu hỏi: app cần `id` để mở, nội dung nằm ở
    `GET /quizzes/{id}` để trang này nhẹ và không giải mã hàng loạt.
    """
    owner = (user_id, device_id)
    with transaction() as conn:
        with conn.cursor() as cur:
            cur.execute(SELECT_SUMMARY_OWNER_SQL, (summary_id,) + owner)
            if cur.fetchone() is None:
                raise _summary_not_found()
            cur.execute(SELECT_QUIZ_PAGE_SQL, (summary_id,) + owner)
            rows = cur.fetchall()

    items = [
        {
            "id": quiz_id,
            "summary_id": summary_id_row,
            "question_count": question_count,
            "language": language,
            "created_at": iso_in_vn(created_at),
        }
        for quiz_id, summary_id_row, question_count, language, created_at in rows
    ]
    return {"summary_id": summary_id, "items": items, "total": len(items)}


def get_quiz(quiz_id: int, device_id: Optional[str] = None,
             user_id: Optional[int] = None) -> dict:
    """Chi tiết quiz + toàn bộ câu hỏi đã giải mã; không thuộc người gọi -> 404."""
    crypto = CryptoService.from_b64_key(Config.ENCRYPTION_KEY)

    with transaction() as conn:
        with conn.cursor() as cur:
            cur.execute(SELECT_QUIZ_SQL, (quiz_id,) + (user_id, device_id))
            row = cur.fetchone()
            if row is None:
                raise _not_found()
            quiz_id_db, summary_id, question_count, language, created_at = row

            cur.execute(SELECT_QUESTIONS_SQL, (quiz_id,))
            questions = [_decrypt_question(crypto, q_row) for q_row in cur.fetchall()]

    return {
        "id": quiz_id_db,
        "summary_id": summary_id,
        "question_count": question_count,
        "language": language,
        "created_at": iso_in_vn(created_at),
        "questions": questions,
    }


def _score(correct_count: int, total_count: int) -> float:
    """Điểm thang 10, làm tròn 1 chữ số theo hướng **làm tròn lên** khi đúng 0,05.

    `round(1.25, 1)` của Python cho 1.2 (banker's rounding) trong khi người dùng trông
    đợi 1.3; mẫu số 8 xuất hiện thật (văn bản 1040–1169 ký tự -> 8 câu) nên phải dùng
    `Decimal` + `ROUND_HALF_UP` thay vì `round` rồi giải thích sau.
    """
    raw = Decimal(correct_count * 10) / Decimal(total_count)
    return float(raw.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))


def grade_quiz(questions: List[Dict[str, Any]], answers: List[Optional[int]]) -> Dict[str, Any]:
    """Chấm một lượt làm bài hoàn toàn từ `correct_index` trong DB (SPEC 5.4).

    Server không nhận `score`/`correct_count` do client gửi lên; câu bỏ qua (`null`)
    tính là sai nhưng vẫn có mặt trong `results` để app tô đúng vị trí.
    """
    results: List[Dict[str, Any]] = []
    correct_count = 0
    for question, selected in zip(questions, answers):
        is_correct = selected is not None and selected == question["correct_index"]
        if is_correct:
            correct_count += 1
        results.append({
            "position": question["position"],
            "selected": selected,
            "correct_index": question["correct_index"],
            "is_correct": is_correct,
        })

    total_count = len(questions)
    return {
        "score": _score(correct_count, total_count),
        "correct_count": correct_count,
        "total_count": total_count,
        "results": results,
    }


def submit_attempt(quiz: Dict[str, Any], answers: List[Optional[int]],
                   device_id: Optional[str] = None,
                   user_id: Optional[int] = None) -> Dict[str, Any]:
    """Ghi một lượt làm bài đã chấm; `answers_json_enc` lưu nguyên mảng, kể cả `null`.

    `quiz` là kết quả `get_quiz()`: route đã đọc một lần để kiểm quyền thì dùng lại,
    không SELECT toàn bộ câu hỏi lần thứ hai chỉ để chấm.
    """
    crypto = CryptoService.from_b64_key(Config.ENCRYPTION_KEY)
    graded = grade_quiz(quiz["questions"], answers)

    with transaction() as conn:
        with conn.cursor() as cur:
            cur.execute(
                INSERT_ATTEMPT_SQL,
                (
                    user_id,
                    device_id,
                    quiz["id"],
                    crypto.encrypt(json.dumps(answers, ensure_ascii=False)),
                    graded["score"],
                    graded["correct_count"],
                    graded["total_count"],
                ),
            )
            attempt_id, submitted_at = cur.fetchone()

    return {"attempt_id": attempt_id, **graded, "submitted_at": iso_in_vn(submitted_at)}


def list_attempts(quiz_id: int, device_id: Optional[str] = None,
                  user_id: Optional[int] = None) -> dict:
    """Mọi lượt làm bài của một quiz, mới nhất trước — chỉ điểm số, không giải mã đáp án.

    `answers_json_enc` của nhiều lượt cũ không cần tải về mỗi lần mở quiz; muốn xem lại
    từng câu thì dùng chính response của lần nộp bài.
    """
    owner = (user_id, device_id)
    with transaction() as conn:
        with conn.cursor() as cur:
            cur.execute(SELECT_QUIZ_SQL, (quiz_id,) + owner)
            if cur.fetchone() is None:
                raise _not_found()
            cur.execute(SELECT_ATTEMPTS_SQL, (quiz_id,) + owner)
            rows = cur.fetchall()

    items = [
        {
            "id": attempt_id,
            "score": score,
            "correct_count": correct_count,
            "total_count": total_count,
            "submitted_at": iso_in_vn(submitted_at),
        }
        for attempt_id, score, correct_count, total_count, submitted_at in rows
    ]
    return {"quiz_id": quiz_id, "items": items, "total": len(items)}
