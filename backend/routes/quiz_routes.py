"""Endpoints quiz theo docs/API.md: `/summaries/{id}/quizzes`, `/quizzes/{id}`, `/quizzes/{id}/attempts`.

Thứ tự một request tạo quiz là **chủ sở hữu -> độ dài -> đặt chỗ -> gọi AI -> lưu DB**:
hai bước đầu chặn trước nên yêu cầu sai không đốt lượt, và mọi lỗi từ AI hoặc
ghi DB được hoàn lại đúng một lượt (SPEC 5.5). Nộp bài thì ngược lại: **không** chạm
`usage_quota` vì làm bài không tốn lượt (SPEC 5.4), chỉ không được tin điểm từ client.
"""

import logging

from flask import Blueprint, g, request

try:
    from backend.config import Config
    from backend.services import history_service, quiz_service, quota_service
    from backend.services.gemini_service import GeminiService
    from backend.utils.errors import AppError, ErrorCode
    from backend.utils.responses import success_response
    from backend.utils.validators import (
        require_device_and_version,
        validate_quiz_answers,
    )
except ImportError:
    from services import history_service, quiz_service, quota_service
    from services.gemini_service import GeminiService
    from utils.errors import AppError, ErrorCode
    from utils.responses import success_response
    from utils.validators import require_device_and_version, validate_quiz_answers

quiz_bp = Blueprint("quiz", __name__)
logger = logging.getLogger("text_summarizer.quiz")


def _usage_block(owner: str, day=None) -> dict:
    usage = quota_service.get_usage(owner, day)
    return {
        "summary_remaining": usage["summary"]["remaining"],
        "quiz_remaining": usage["quiz"]["remaining"],
    }


def _refund_quietly(owner: str, day) -> None:
    """Lỗi hoàn lượt không được che lỗi gốc của request."""
    try:
        quota_service.refund(owner, quota_service.USAGE_QUIZ, day)
    except Exception as exc:
        logger.error(f"Hoàn quota quiz thất bại: {type(exc).__name__}")


@quiz_bp.route("/api/v1/summaries/<int:summary_id>/quizzes", methods=["POST"])
@require_device_and_version
def create_quiz(summary_id: int):
    """Sinh quiz từ văn bản gốc của bản tóm tắt và lưu kèm đáp án đã xáo trộn."""
    # get_summary kiểm quyền sở hữu ngay trong SELECT -> bản của thiết bị khác là 404.
    summary = history_service.get_summary(summary_id, device_id=g.device_id)

    # SPEC 5.4 đo bằng cột original_length, không giải mã lại để đếm.
    if summary["original_length"] < Config.MIN_CHARS:
        raise AppError(ErrorCode.QUIZ_TEXT_TOO_SHORT)

    owner = quota_service.owner_key(device_id=g.device_id)
    day = quota_service.today_vn()
    quota_service.reserve(owner, quota_service.USAGE_QUIZ, day)

    try:
        quiz = GeminiService.generate_quiz(
            summary["original_text"], summary["summary"], summary["language"]
        )
        saved = quiz_service.save_quiz(summary_id, quiz, device_id=g.device_id)
    except Exception:
        _refund_quietly(owner, day)
        raise

    saved["usage"] = _usage_block(owner, day)
    return success_response(data=saved, status_code=201)


@quiz_bp.route("/api/v1/summaries/<int:summary_id>/quizzes", methods=["GET"])
@require_device_and_version
def list_quizzes(summary_id: int):
    """Liệt kê các quiz của một bản tóm tắt (không kèm nội dung câu hỏi)."""
    return success_response(
        data=quiz_service.list_quizzes(summary_id, device_id=g.device_id)
    )


@quiz_bp.route("/api/v1/quizzes/<int:quiz_id>", methods=["GET"])
@require_device_and_version
def get_quiz(quiz_id: int):
    """Chi tiết quiz + toàn bộ câu hỏi đã giải mã, xếp theo `position` tăng dần."""
    return success_response(data=quiz_service.get_quiz(quiz_id, device_id=g.device_id))


@quiz_bp.route("/api/v1/quizzes/<int:quiz_id>/attempts", methods=["POST"])
@require_device_and_version
def submit_attempt(quiz_id: int):
    """Nhận index đã chọn rồi server tự chấm (SPEC 5.4): `score` trong body bị bỏ qua.

    `get_quiz` chạy trước cả validate để quiz của thiết bị khác là 404 chứ không phải
    400 — 400 trên id lạ sẽ xác nhận gián tiếp rằng id đó tồn tại.
    """
    quiz = quiz_service.get_quiz(quiz_id, device_id=g.device_id)

    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        raise AppError(ErrorCode.VALIDATION_ERROR)

    answers = validate_quiz_answers(body.get("answers"), len(quiz["questions"]))
    data = quiz_service.submit_attempt(quiz, answers, device_id=g.device_id)
    return success_response(data=data, status_code=201)


@quiz_bp.route("/api/v1/quizzes/<int:quiz_id>/attempts", methods=["GET"])
@require_device_and_version
def list_attempts(quiz_id: int):
    """Lịch sử làm bài của một quiz (điểm từng lượt, mới nhất trước; không kèm đáp án)."""
    return success_response(data=quiz_service.list_attempts(quiz_id, device_id=g.device_id))
