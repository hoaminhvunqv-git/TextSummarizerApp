import logging

from flask import Blueprint, g, request

try:
    from backend.services import history_service, quota_service
    from backend.services.gemini_service import GeminiService
    from backend.utils.errors import AppError, ErrorCode
    from backend.utils.responses import success_response
    from backend.utils.validators import require_device_and_version, validate_summary_input
except ImportError:
    from services import history_service, quota_service
    from services.gemini_service import GeminiService
    from utils.errors import AppError, ErrorCode
    from utils.responses import success_response
    from utils.validators import require_device_and_version, validate_summary_input

summary_bp = Blueprint("summary", __name__)
logger = logging.getLogger("text_summarizer.summary")


def _refund_quietly(owner: str, day) -> None:
    """DB có thể đang chết chính vì lý do khiến request fail — lỗi hoàn không được che lỗi gốc."""
    try:
        quota_service.refund(owner, quota_service.USAGE_SUMMARY, day)
    except Exception as exc:
        logger.error(f"Hoàn quota thất bại: {type(exc).__name__}")


@summary_bp.route("/api/v1/summaries", methods=["POST"])
@require_device_and_version
def create_summary():
    """Đặt chỗ quota -> gọi AI -> lưu bản ghi mã hóa (SPEC 5.5, 5.8).

    Validate chạy trước khi đặt chỗ nên yêu cầu sai không ăn lượt; lỗi khi gọi
    AI hoặc khi ghi DB được hoàn lại đúng một lượt.
    """
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        raise AppError(ErrorCode.VALIDATION_ERROR)

    text, length = validate_summary_input(body.get("text"), body.get("length"))

    owner = quota_service.owner_key(device_id=g.device_id)
    day = quota_service.today_vn()
    quota_service.reserve(owner, quota_service.USAGE_SUMMARY, day)

    try:
        result = GeminiService.summarize(text, length)
        summary_id, created_at = history_service.save_summary(
            result, text, device_id=g.device_id
        )
    except Exception:
        _refund_quietly(owner, day)
        raise

    usage = quota_service.get_usage(owner, day)
    data = {
        "id": summary_id,
        "title": result["title"],
        "description": result["description"],
        "summary": result["summary"],
        "language": result["language"],
        "source": result["source"],
        "original_length": len(text),
        "created_at": created_at,
        "usage": {
            "summary_remaining": usage["summary"]["remaining"],
            "quiz_remaining": usage["quiz"]["remaining"],
        },
    }
    return success_response(data=data, status_code=201)
