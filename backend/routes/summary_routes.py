from datetime import datetime, timedelta, timezone

from flask import Blueprint, request

try:
    from backend.services.gemini_service import GeminiService
    from backend.utils.errors import AppError, ErrorCode
    from backend.utils.responses import success_response
    from backend.utils.validators import require_device_and_version, validate_summary_input
except ImportError:
    from services.gemini_service import GeminiService
    from utils.errors import AppError, ErrorCode
    from utils.responses import success_response
    from utils.validators import require_device_and_version, validate_summary_input

summary_bp = Blueprint("summary", __name__)

# Việt Nam không có DST nên dùng offset cố định, không cần package tzdata trên Windows.
VN_TZ = timezone(timedelta(hours=7))


@summary_bp.route("/api/v1/summaries", methods=["POST"])
@require_device_and_version
def create_summary():
    """Tóm tắt văn bản. GĐ1 chưa lưu DB nên id = null, quota chưa theo dõi nên usage = null."""
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        raise AppError(ErrorCode.VALIDATION_ERROR)

    text, length = validate_summary_input(body.get("text"), body.get("length"))
    result = GeminiService.summarize(text, length)

    data = {
        "id": None,
        "title": result["title"],
        "description": result["description"],
        "summary": result["summary"],
        "language": result["language"],
        "source": result["source"],
        "original_length": len(text),
        "created_at": datetime.now(VN_TZ).isoformat(timespec="seconds"),
        "usage": {"summary_remaining": None, "quiz_remaining": None},
    }
    return success_response(data=data, status_code=201)