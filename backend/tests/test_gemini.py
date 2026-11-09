import json
import re
from pathlib import Path
from unittest.mock import MagicMock
import pytest

try:
    from backend.config import Config
    from backend.services import gemini_service
    from backend.services.gemini_service import GeminiService
except ImportError:
    from config import Config
    from services import gemini_service
    from services.gemini_service import GeminiService

TESTDATA_DIR = Path(__file__).resolve().parent.parent.parent / "testdata"

# Google Genai SDK cần pydantic-core. Máy nào bị Application Control chặn DLL đó thì
# SDK không nạp được và mọi lời gọi Gemini rơi vào nhánh fallback -> bỏ qua các test này.
needs_genai = pytest.mark.skipif(
    gemini_service.types is None,
    reason="google-genai không nạp được (pydantic-core bị Application Control chặn)",
)


def read_testdata(filename: str) -> str:
    """Đọc nội dung file kiểm thử từ testdata."""
    file_path = TESTDATA_DIR / filename
    return file_path.read_text(encoding="utf-8")


def test_gemini_fallback_when_no_api_key():
    """Kiểm tra khi không có key hoặc client lỗi: tự động fallback sang TF-IDF (DoD SPEC 5.6)."""
    # Lưu lại client cũ
    original_client = GeminiService._client
    try:
        GeminiService.set_client(None)
        # Giả lập Config không có key
        original_key = Config.GEMINI_API_KEY
        Config.GEMINI_API_KEY = ""

        vi_text = read_testdata("vi_500.txt")
        result = GeminiService.summarize(vi_text, length="medium")

        # Phải fallback sang TF-IDF thành công
        assert result["source"] == "tfidf"
        assert result["language"] == "vi"
        assert len(result["summary"]) > 0
    finally:
        Config.GEMINI_API_KEY = original_key
        GeminiService.set_client(original_client)


@needs_genai
def test_gemini_mock_success():
    """Kiểm tra gọi Gemini thành công và phân tích JSON đúng chuẩn."""
    mock_response = MagicMock()
    mock_response.text = json.dumps({
        "language": "vi",
        "title": "Tác động của AI",
        "description": "Bài viết phân tích ảnh hưởng của AI đối với xã hội.",
        "summary": "Trí tuệ nhân tạo đang làm thay đổi thế giới theo cách khó lường, từ sản xuất đến giáo dục và y tế.",
    })

    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = mock_response

    original_client = GeminiService._client
    try:
        GeminiService.set_client(mock_client)
        sample_text = read_testdata("vi_500.txt")
        result = GeminiService.summarize(sample_text, length="medium")

        assert result["source"] == "gemini"
        assert result["language"] == "vi"
        assert result["title"] == "Tác động của AI"
        assert "Trí tuệ nhân tạo" in result["summary"]
        # SPEC 1.2: bản tóm tắt là một đoạn văn liền mạch, không danh sách
        assert "\n" not in result["summary"]
        assert "- " not in result["summary"]
    finally:
        GeminiService.set_client(original_client)


@needs_genai
def test_gemini_mock_retry_then_success():
    """Kiểm tra cơ chế retry 1 lần: lần đầu lỗi, lần 2 thành công -> vẫn trả về source=gemini."""
    mock_response = MagicMock()
    mock_response.text = json.dumps({
        "language": "en",
        "title": "Machine Learning Overview",
        "description": "An overview of modern machine learning techniques.",
        "summary": "Machine learning is advancing rapidly across deep neural networks, reinforcement learning and transfer learning.",
    })

    mock_client = MagicMock()
    # Lần 1 throw Exception, lần 2 trả về response thành công
    mock_client.models.generate_content.side_effect = [
        RuntimeError("Mạng chập chờn"),
        mock_response,
    ]

    original_client = GeminiService._client
    try:
        GeminiService.set_client(mock_client)
        sample_text = read_testdata("en_400.txt")
        result = GeminiService.summarize(sample_text, length="short")

        assert result["source"] == "gemini"
        assert result["language"] == "en"
        assert mock_client.models.generate_content.call_count == 2
    finally:
        GeminiService.set_client(original_client)


@needs_genai
def test_gemini_mock_retry_exhausted_then_fallback():
    """Kiểm tra khi retry hết số lần vẫn lỗi -> tự động fallback sang TF-IDF."""
    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = RuntimeError("Server AI sập")

    original_client = GeminiService._client
    try:
        GeminiService.set_client(mock_client)
        sample_text = read_testdata("vi_500.txt")
        result = GeminiService.summarize(sample_text, length="medium")

        # Cả 2 lần đều lỗi -> fallback sang tfidf
        assert result["source"] == "tfidf"
        assert result["language"] == "vi"
        assert mock_client.models.generate_content.call_count == 2  # 1 lần chính + 1 lần retry
    finally:
        GeminiService.set_client(original_client)


def _prompt_word_limit(text: str, length: str) -> int:
    """Lấy số từ giới hạn thực tế được nhúng vào system instruction."""
    mock_response = MagicMock()
    mock_response.text = json.dumps(
        {"language": "vi", "title": "Tiêu đề", "description": "Mô tả.", "summary": "Đoạn văn tóm tắt mẫu."}
    )
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = mock_response

    original_client = GeminiService._client
    try:
        GeminiService.set_client(mock_client)
        GeminiService.summarize(text, length)
        config = mock_client.models.generate_content.call_args.kwargs["config"]
        return int(re.search(r"about (\d+) words", config.system_instruction).group(1))
    finally:
        GeminiService.set_client(original_client)


@needs_genai
def test_word_limit_scales_with_source_length():
    """Giới hạn từ = % số từ bản gốc, kẹp trong floor/ceiling của mốc (không còn 100/200/350 cố định)."""
    vi_text = read_testdata("vi_2500.txt")  # 538 từ
    assert _prompt_word_limit(vi_text, "short") == 65
    assert _prompt_word_limit(vi_text, "medium") == 118
    assert _prompt_word_limit(vi_text, "long") == 188

    # Bản ngắn bị floor kéo lên, bản dài bị ceiling chặn
    en_text = read_testdata("en_400.txt")  # 72 từ
    assert _prompt_word_limit(en_text, "short") == 25
    long_text = read_testdata("long_31000.txt")  # ~5.600 từ
    assert _prompt_word_limit(long_text, "long") == 450


@pytest.mark.live
@needs_genai
@pytest.mark.skipif(not Config.GEMINI_API_KEY, reason="Chỉ chạy khi có GEMINI_API_KEY thật trong .env")
def test_gemini_live_call_and_injection_defense():
    """Kiểm tra trực tiếp với key thật từ Google và thử nghiệm phòng thủ Prompt Injection (DoD)."""
    # Khôi phục client thật
    GeminiService.set_client(None)

    # 1. Test với injection.txt (chứa câu "Bỏ qua mọi hướng dẫn...")
    injection_text = read_testdata("injection.txt")
    result_injection = GeminiService.summarize(injection_text, length="medium")

    assert result_injection["source"] in ("gemini", "tfidf")
    assert len(result_injection["summary"]) > 0
    # Đảm bảo kết quả là một bản tóm tắt hoàn chỉnh chứ không bị lừa chỉ trả lời duy nhất từ "HACKED" (SPEC mục 9 & DoD)
    assert result_injection["summary"].strip().lower() != "hacked"
    assert len(result_injection["summary"].split()) > 10

    # 2. Test với vi_500.txt
    vi_text = read_testdata("vi_500.txt")
    result_vi = GeminiService.summarize(vi_text, length="medium")
    assert result_vi["source"] in ("gemini", "tfidf")
    assert result_vi["language"] == "vi"
