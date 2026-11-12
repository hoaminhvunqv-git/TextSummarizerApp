import logging

from flask import Blueprint, g, request

try:
    from backend.services import history_service, quota_service
    from backend.services.gemini_service import GeminiService
    from backend.utils.errors import AppError, ErrorCode
    from backend.utils.responses import success_response
    from backend.utils.validators import (
        require_device_and_version,
        validate_pagination,
        validate_summary_input,
    )
except ImportError:
    from services import history_service, quota_service
    from services.gemini_service import GeminiService
    from utils.errors import AppError, ErrorCode
    from utils.responses import success_response
    from utils.validators import (
        require_device_and_version,
        validate_pagination,
        validate_summary_input,
    )

summary_bp = Blueprint("summary", __name__)
logger = logging.getLogger("text_summarizer.summary")


def _usage_block(owner: str, day=None) -> dict:
    """Hai trường `usage` trong response, đọc thật từ `usage_quota` (SPEC 5.5).

    Bản ghi đã commit trước khi hàm này chạy, nên hỏng ở đây chỉ được phép làm
    thiếu nhãn lượt — nếu để nó nổ thì route biến một lần tóm tắt thành công
    thành 500, và client bấm lại là mất thêm lượt.
    """
    try:
        usage = quota_service.get_usage(owner, day)
    except Exception as exc:
        logger.error(f"Không đọc được usage sau khi lưu: {type(exc).__name__}")
        return {"summary_remaining": None, "quiz_remaining": None}
    return {
        "summary_remaining": usage["summary"]["remaining"],
        "quiz_remaining": usage["quiz"]["remaining"],
    }


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

    data = {
        "id": summary_id,
        "title": result["title"],
        "description": result["description"],
        "summary": result["summary"],
        "language": result["language"],
        "source": result["source"],
        "original_length": len(text),
        "created_at": created_at,
        "usage": _usage_block(owner, day),
    }
    return success_response(data=data, status_code=201)


@summary_bp.route("/api/v1/summaries", methods=["GET"])
@require_device_and_version
def list_summaries():
    """Trang lịch sử của chính thiết bị đang gọi, mới nhất trước (API.md, SPEC 5.7)."""
    page, limit = validate_pagination(request.args.get("page"), request.args.get("limit"))
    return success_response(
        data=history_service.list_summaries(device_id=g.device_id, page=page, limit=limit)
    )


@summary_bp.route("/api/v1/summaries/<int:summary_id>", methods=["GET"])
@require_device_and_version
def get_summary(summary_id: int):
    """Chi tiết một bản tóm tắt kèm văn bản gốc; bản của thiết bị khác -> 404."""
    data = history_service.get_summary(summary_id, device_id=g.device_id)
    data["usage"] = _usage_block(quota_service.owner_key(device_id=g.device_id))
    return success_response(data=data)


@summary_bp.route("/api/v1/summaries/<int:summary_id>", methods=["DELETE"])
@require_device_and_version
def delete_summary(summary_id: int):
    """Xóa bản ghi của chính thiết bị gọi; quiz kèm theo bị cascade trong DB."""
    history_service.delete_summary(summary_id, device_id=g.device_id)
    return success_response(data={"deleted": True})
