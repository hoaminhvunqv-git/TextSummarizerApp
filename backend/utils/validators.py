import functools
import uuid
from typing import Optional, Tuple
from flask import request, g

try:
    from backend.config import Config
    from backend.utils.errors import AppError, ErrorCode
    from backend.utils.text_utils import normalize_text, count_characters
except ImportError:
    from config import Config
    from utils.errors import AppError, ErrorCode
    from utils.text_utils import normalize_text, count_characters

VALID_SUMMARY_LENGTHS = {"short", "medium", "long"}


def parse_version(version_str: str) -> Tuple[int, ...]:
    """Chuyển chuỗi phiên bản dạng '1.0.0' hoặc '1.0.0+1' thành tuple số để so sánh."""
    if not version_str:
        return (0, 0, 0)
    try:
        # Bỏ phần build metadata (+...) và pre-release (-...) nếu có
        clean_v = version_str.strip().split("+")[0].split("-")[0]
        parts = [int(p) for p in clean_v.split(".")]
        return tuple(parts)
    except Exception:
        return (0, 0, 0)


def validate_summary_input(text: Optional[str], length: Optional[str] = "medium") -> Tuple[str, str]:
    """Kiểm tra và chuẩn hóa văn bản đầu vào và tham số độ dài theo SPEC 5.1 & API.md.

    - Tối thiểu 200, tối đa 30.000 ký tự (sau khi NFC + strip).
    - length nhận: short | medium | long (mặc định medium).
    """
    if text is None:
        raise AppError(ErrorCode.TEXT_TOO_SHORT)

    normalized_text = normalize_text(text)
    char_count = len(normalized_text)

    if char_count < Config.MIN_CHARS:
        raise AppError(ErrorCode.TEXT_TOO_SHORT)

    if char_count > Config.MAX_CHARS:
        raise AppError(ErrorCode.TEXT_TOO_LONG)

    # Validate tham số length
    selected_length = (length or "medium").strip().lower()
    if selected_length not in VALID_SUMMARY_LENGTHS:
        raise AppError(
            ErrorCode.VALIDATION_ERROR,
            message="Tham số độ dài không hợp lệ (chỉ chấp nhận: short, medium, long).",
        )

    return normalized_text, selected_length


def validate_device_id(device_id: Optional[str]) -> str:
    """Kiểm tra Header X-Device-ID: bắt buộc có và phải đúng chuẩn UUID v4 (SPEC 5.5)."""
    if not device_id or not isinstance(device_id, str):
        raise AppError(ErrorCode.INVALID_DEVICE_ID)

    clean_id = device_id.strip()
    try:
        parsed_uuid = uuid.UUID(clean_id, version=4)
        if str(parsed_uuid).lower() != clean_id.lower():
            raise AppError(ErrorCode.INVALID_DEVICE_ID)
    except Exception:
        raise AppError(ErrorCode.INVALID_DEVICE_ID)

    return clean_id


def validate_app_version(app_version: Optional[str]) -> str:
    """Kiểm tra Header X-App-Version: nếu thấp hơn MIN_APP_VERSION thì trả HTTP 426 (SPEC 5.10)."""
    if not app_version:
        # Nếu app không gửi header phiên bản, yêu cầu cập nhật
        raise AppError(ErrorCode.UPDATE_REQUIRED, status_code=426)

    clean_version = app_version.strip()
    client_ver = parse_version(clean_version)
    min_ver = parse_version(Config.MIN_APP_VERSION)

    if client_ver < min_ver:
        raise AppError(ErrorCode.UPDATE_REQUIRED, status_code=426)

    return clean_version


def require_device_and_version(f):
    """Decorator kiểm tra tự động 2 headers X-Device-ID và X-App-Version trên các route nghiệp vụ."""
    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        device_id = request.headers.get("X-Device-ID")
        app_version = request.headers.get("X-App-Version")

        # Validate headers
        valid_did = validate_device_id(device_id)
        valid_ver = validate_app_version(app_version)

        # Lưu vào g để các service phía sau sử dụng
        g.device_id = valid_did
        g.app_version = valid_ver

        return f(*args, **kwargs)

    return decorated_function
