from pathlib import Path

from flask import Blueprint, request

try:
    from backend.config import Config
    from backend.services.file_service import extract_text
    from backend.utils.errors import AppError, ErrorCode
    from backend.utils.responses import success_response
    from backend.utils.validators import require_device_and_version
except ImportError:
    from config import Config
    from services.file_service import extract_text
    from utils.errors import AppError, ErrorCode
    from utils.responses import success_response
    from utils.validators import require_device_and_version

file_bp = Blueprint("file", __name__)


@file_bp.route("/api/v1/files/extract", methods=["POST"])
@require_device_and_version
def extract_file():
    """Trích văn bản từ file để app hiển thị cho xem/sửa trước khi gọi /summaries.

    Không chặn tối thiểu 400 ký tự ở bước này (API.md không liệt kê TEXT_TOO_SHORT),
    chỉ chặn tối đa 30.000 vì người dùng còn sửa nội dung sau khi trích.
    """
    upload = request.files.get("file")
    if upload is None:
        raise AppError(ErrorCode.VALIDATION_ERROR)

    text = extract_text(upload.filename, upload.read())
    if len(text) > Config.MAX_CHARS:
        raise AppError(ErrorCode.TEXT_TOO_LONG)

    # Chỉ lấy tên cuối, không dùng secure_filename vì nó xoá dấu tiếng Việt; không ghi xuống đĩa
    filename = Path(upload.filename or "").name[:255]
    return success_response(data={"text": text, "char_count": len(text), "filename": filename})