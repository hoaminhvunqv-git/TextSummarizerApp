import uuid
from pathlib import Path
import pytest

try:
    from backend.utils.errors import AppError, ErrorCode
    from backend.utils.text_utils import (
        normalize_text,
        count_characters,
        split_sentences,
        detect_language,
    )
    from backend.utils.validators import (
        validate_summary_input,
        validate_device_id,
        validate_app_version,
    )
except ImportError:
    from utils.errors import AppError, ErrorCode
    from utils.text_utils import (
        normalize_text,
        count_characters,
        split_sentences,
        detect_language,
    )
    from utils.validators import (
        validate_summary_input,
        validate_device_id,
        validate_app_version,
    )

# Đường dẫn tới thư mục testdata
TESTDATA_DIR = Path(__file__).resolve().parent.parent.parent / "testdata"


def read_testdata(filename: str) -> str:
    """Đọc nội dung file kiểm thử từ testdata."""
    file_path = TESTDATA_DIR / filename
    return file_path.read_text(encoding="utf-8")


# ============================================================================
# 1. TEST TEXT UTILS (NFC, ĐẾM KÝ TỰ, TÁCH CÂU, NHẬN DIỆN NGÔN NGỮ)
# ============================================================================

def test_nfc_normalization():
    """Kiểm tra chuẩn hóa Unicode NFC tiếng Việt (tổ hợp vs dựng sẵn)."""
    # 'tiếng việt' gõ bằng ký tự tổ hợp (NFD)
    nfd_text = "tiếng việt"
    normalized = normalize_text(nfd_text)
    assert normalized == "tiếng việt"
    assert count_characters("   tiếng việt   ") == len("tiếng việt")


def test_emoji_and_special_chars():
    """Kiểm tra file testdata/emoji.txt không crash và đếm đúng."""
    content = read_testdata("emoji.txt")
    normalized = normalize_text(content)
    assert len(normalized) > 0
    assert count_characters(content) == len(content.strip())


def test_detect_language():
    """Kiểm tra tự nhận diện ngôn ngữ vi/en theo SPEC 1.1."""
    vi_text = read_testdata("vi_500.txt")
    en_text = read_testdata("en_250.txt")
    assert detect_language(vi_text) == "vi"
    assert detect_language(en_text) == "en"


def test_split_sentences():
    """Kiểm tra tách câu với các loại dấu ngắt . ! ? … và xuống dòng."""
    sample = "Câu thứ nhất. Câu thứ hai! Câu thứ ba? Câu thứ tư…\nCâu thứ năm sau khi xuống dòng."
    sentences = split_sentences(sample)
    assert len(sentences) == 5
    assert sentences[0] == "Câu thứ nhất."
    assert sentences[1] == "Câu thứ hai!"
    assert sentences[2] == "Câu thứ ba?"
    assert sentences[3] == "Câu thứ tư…"
    assert sentences[4] == "Câu thứ năm sau khi xuống dòng."


# ============================================================================
# 2. TEST VALIDATORS (ĐỘ DÀI, LENGTH PARAM, DEVICE ID, APP VERSION)
# ============================================================================

def test_validate_summary_input_valid():
    """Kiểm tra văn bản hợp lệ 250 và 500 ký tự."""
    en_250 = read_testdata("en_250.txt")
    vi_500 = read_testdata("vi_500.txt")

    text, length = validate_summary_input(en_250, "short")
    assert length == "short"
    assert len(text) >= 200

    text_vi, length_vi = validate_summary_input(vi_500, None)
    assert length_vi == "medium"  # Mặc định là medium
    assert len(text_vi) >= 200


def test_validate_summary_input_too_short():
    """Kiểm tra file testdata/short_100.txt (100 ký tự) trả về TEXT_TOO_SHORT."""
    short_text = read_testdata("short_100.txt")
    with pytest.raises(AppError) as exc_info:
        validate_summary_input(short_text)
    assert exc_info.value.error_code == ErrorCode.TEXT_TOO_SHORT
    assert exc_info.value.status_code == 400


def test_validate_summary_input_too_long():
    """Kiểm tra file testdata/long_31000.txt (31.000 ký tự) trả về TEXT_TOO_LONG."""
    long_text = read_testdata("long_31000.txt")
    with pytest.raises(AppError) as exc_info:
        validate_summary_input(long_text)
    assert exc_info.value.error_code == ErrorCode.TEXT_TOO_LONG
    assert exc_info.value.status_code == 400


def test_validate_summary_length_param_invalid():
    """Kiểm tra tham số length sai giá trị trả về VALIDATION_ERROR."""
    vi_500 = read_testdata("vi_500.txt")
    with pytest.raises(AppError) as exc_info:
        validate_summary_input(vi_500, "extra_long")
    assert exc_info.value.error_code == ErrorCode.VALIDATION_ERROR


def test_validate_device_id():
    """Kiểm tra header X-Device-ID UUID v4 hợp lệ vs không hợp lệ."""
    valid_uuid_v4 = str(uuid.uuid4())
    assert validate_device_id(valid_uuid_v4) == valid_uuid_v4

    # Không phải UUID
    with pytest.raises(AppError) as exc1:
        validate_device_id("invalid-device-123")
    assert exc1.value.error_code == ErrorCode.INVALID_DEVICE_ID

    # Để trống hoặc None
    with pytest.raises(AppError) as exc2:
        validate_device_id(None)
    assert exc2.value.error_code == ErrorCode.INVALID_DEVICE_ID


def test_validate_app_version():
    """Kiểm tra header X-App-Version so sánh với MIN_APP_VERSION = 1.0.0."""
    # Phiên bản hợp lệ
    assert validate_app_version("1.0.0") == "1.0.0"
    assert validate_app_version("1.0.1") == "1.0.1"
    assert validate_app_version("2.0.0") == "2.0.0"

    # Phiên bản cũ hơn (ví dụ 0.9.0) -> HTTP 426 UPDATE_REQUIRED
    with pytest.raises(AppError) as exc1:
        validate_app_version("0.9.5")
    assert exc1.value.error_code == ErrorCode.UPDATE_REQUIRED
    assert exc1.value.status_code == 426

    # Không gửi header version
    with pytest.raises(AppError) as exc2:
        validate_app_version(None)
    assert exc2.value.error_code == ErrorCode.UPDATE_REQUIRED
    assert exc2.value.status_code == 426
