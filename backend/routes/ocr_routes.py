from flask import Blueprint, request

try:
    from backend.utils.errors import AppError, ErrorCode
    from backend.utils.responses import success_response
    from backend.utils.validators import require_device_and_version
    from backend.services.ocr_service import OcrService
    from backend.extensions import limiter
except ImportError:
    from utils.errors import AppError, ErrorCode
    from utils.responses import success_response
    from utils.validators import require_device_and_version
    from services.ocr_service import OcrService
    from extensions import limiter

ocr_bp = Blueprint("ocr", __name__)

ALLOWED_MIME_TYPES = {"image/jpeg", "image/jpg", "image/png", "image/webp"}
MAX_IMAGE_SIZE = 4 * 1024 * 1024  # 4MB


@ocr_bp.route("/api/v1/ocr", methods=["POST"])
@require_device_and_version
@limiter.limit("20 per day")
def extract_ocr():
    """Trích xuất văn bản từ ảnh bằng Gemini Vision OCR.

    Request: multipart/form-data, field 'image' (JPEG/PNG/WebP, tối đa 4MB).
    Response: {text, char_count}.
    Rate limit: 20 lượt/ngày/thiết bị (riêng biệt, không trừ vào giới hạn tóm tắt).
    """
    if "image" not in request.files:
        raise AppError(ErrorCode.VALIDATION_ERROR, message="Thiếu field 'image' trong request.")

    file = request.files["image"]
    
    if file.filename == "":
        raise AppError(ErrorCode.FILE_EMPTY, message="File rỗng.")

    # Kiểm tra MIME type
    mime_type = file.mimetype.lower() if file.mimetype else ""
    if mime_type not in ALLOWED_MIME_TYPES:
        raise AppError(
            ErrorCode.FILE_UNSUPPORTED,
            message=f"Định dạng ảnh không hỗ trợ. Chỉ chấp nhận JPEG, PNG, WebP."
        )

    # Đọc nội dung file
    image_bytes = file.read()
    
    if len(image_bytes) == 0:
        raise AppError(ErrorCode.FILE_EMPTY, message="File rỗng.")

    # Kiểm tra kích thước (Flask đã có MAX_CONTENT_LENGTH nhưng kiểm tra lại cho chắc)
    if len(image_bytes) > MAX_IMAGE_SIZE:
        raise AppError(
            ErrorCode.FILE_TOO_LARGE,
            message=f"Ảnh vượt quá giới hạn 4MB (hiện tại {len(image_bytes) / 1024 / 1024:.1f}MB)."
        )

    # Gọi OCR service
    result = OcrService.extract_text(image_bytes, mime_type)

    return success_response(
        data=result,
        message="Trích xuất văn bản thành công.",
    )
