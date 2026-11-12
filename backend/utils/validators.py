import functools
import uuid
from typing import List, Optional, Tuple
from flask import request, g

try:
    from backend.config import Config
    from backend.utils.errors import AppError, ErrorCode
    from backend.utils.text_utils import normalize_text
except ImportError:
    from config import Config
    from utils.errors import AppError, ErrorCode
    from utils.text_utils import normalize_text

VALID_SUMMARY_LENGTHS = {"short", "medium", "long"}


def parse_version(version_str: str) -> Tuple[int, ...]:
    """Chuyển chuỗi phiên bản dạng '1.0.0' hoặc '1.0.0+1' thành tuple số để so sánh.

    Bóp gọn về đúng 3 số hạng: tuple ngắn hơn luôn nhỏ hơn tuple dài hơn trong Python,
    nên '1.0' so với '1.0.0' từng trả 426 dù app không hề cũ.
    """
    if not version_str:
        return (0, 0, 0)
    try:
        # Bỏ phần build metadata (+...) và pre-release (-...) nếu có
        clean_v = version_str.strip().split("+")[0].split("-")[0]
        parts = [int(p) for p in clean_v.split(".")]
    except Exception:
        return (0, 0, 0)
    return tuple((parts + [0, 0, 0])[:3])


def validate_summary_input(text: Optional[str], length: Optional[str] = "medium") -> Tuple[str, str]:
    """Kiểm tra và chuẩn hóa văn bản đầu vào và tham số độ dài theo SPEC 5.1 & API.md.

    - Tối thiểu 400, tối đa 30.000 ký tự (sau khi NFC + strip).
    - length nhận: short | medium | long (mặc định medium).
    - Mốc medium/long còn bị khoá cho tới khi bản gốc đạt ngưỡng ký tự tương ứng.
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

    required_chars = Config.LENGTH_UNLOCK_CHARS[selected_length]
    if char_count < required_chars:
        raise AppError(
            ErrorCode.LENGTH_NOT_UNLOCKED,
            message=(
                f"Mốc tóm tắt này cần văn bản dài ít nhất {required_chars} ký tự "
                f"(hiện có {char_count} ký tự)."
            ),
        )

    return normalized_text, selected_length


def validate_quiz_answers(answers: Optional[list], question_count: int) -> List[Optional[int]]:
    """Kiểm mảng đáp án nộp lên theo docs/API.md: đủ `question_count` phần tử, mỗi ô là `null` hoặc 0–3.

    Chỉ chuẩn hóa kiểu, **không** chấm điểm: mọi con số điểm do `quiz_service` tính từ
    `correct_index` trong DB. `bool` bị loại vì trong Python `True` là `int` và sẽ thành
    đáp án B nếu để lọt.
    """
    if not isinstance(answers, list):
        raise AppError(
            ErrorCode.VALIDATION_ERROR,
            message=f"Cần gửi mảng `answers` đủ {question_count} phần tử (null nếu bỏ qua câu đó).",
        )

    if len(answers) != question_count:
        raise AppError(
            ErrorCode.VALIDATION_ERROR,
            message=(
                f"Mảng answers phải có đúng {question_count} phần tử "
                f"(hiện có {len(answers)}; gửi null cho câu bỏ qua)."
            ),
        )

    clean: List[Optional[int]] = []
    for position, value in enumerate(answers, start=1):
        if value is None:
            clean.append(None)
            continue
        if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 3:
            raise AppError(
                ErrorCode.VALIDATION_ERROR,
                message=f"Câu {position} phải là số nguyên từ 0 đến 3 hoặc null.",
            )
        clean.append(value)

    return clean


def validate_pagination(page: Optional[str], limit: Optional[str]) -> Tuple[int, int]:
    """Chuẩn hóa query params `page`/`limit` cho GET /summaries (API.md).

    Mặc định trang 1, 20 mục/trang; `limit` tối đa 50 để một trang không kéo cả
    bảng lịch sử về thiết bị. Tham số lạ hoặc ngoài khoảng -> VALIDATION_ERROR.
    """
    raw_page = (page if page is not None else "1").strip()
    raw_limit = (limit if limit is not None else str(Config.HISTORY_PAGE_SIZE_DEFAULT)).strip()

    try:
        page_num = int(raw_page)
        limit_num = int(raw_limit)
    except ValueError:
        raise AppError(
            ErrorCode.VALIDATION_ERROR,
            message="Tham số phân trang không hợp lệ (page và limit phải là số nguyên).",
        )

    if page_num < 1 or limit_num < 1 or limit_num > Config.HISTORY_PAGE_SIZE_MAX:
        raise AppError(
            ErrorCode.VALIDATION_ERROR,
            message=(
                f"page phải từ 1 trở lên và limit từ 1 đến {Config.HISTORY_PAGE_SIZE_MAX}."
            ),
        )

    return page_num, limit_num


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

    # Trả về dạng chuẩn viết thường: `D:UUID-THUONG` và `d:uuid-thuong` mà giữ nguyên
    # như nhau thì Flask-Limiter và `usage_quota.owner_key` coi là hai thiết bị,
    # tức một người đổi chữ hoa/thường là được gấp đôi lượt.
    return str(parsed_uuid)


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
