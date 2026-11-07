import json
from pathlib import Path
from unittest.mock import MagicMock
import pytest

try:
    from backend.config import Config
    from backend.services.gemini_service import GeminiService
except ImportError:
    from config import Config
    from services.gemini_service import GeminiService

TESTDATA_DIR = Path(__file__).resolve().parent.parent.parent / "testdata"


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


def test_gemini_mock_success():
    """Kiểm tra gọi Gemini thành công và phân tích JSON đúng chuẩn."""
    mock_response = MagicMock()
    mock_response.text = json.dumps({
        "language": "vi",
        "title": "Tác động của AI",
        "description": "Bài viết phân tích ảnh hưởng của AI đối với xã hội.",
        "summary": "Trí tuệ nhân tạo đang làm thay đổi thế giới.\n\n- Tự động hóa sản xuất\n- Tối ưu hóa giáo dục\n- Nâng cao hiệu suất y tế",
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
        assert "- Tự động hóa" in result["summary"]
    finally:
        GeminiService.set_client(original_client)


def test_gemini_mock_retry_then_success():
    """Kiểm tra cơ chế retry 1 lần: lần đầu lỗi, lần 2 thành công -> vẫn trả về source=gemini."""
    mock_response = MagicMock()
    mock_response.text = json.dumps({
        "language": "en",
        "title": "Machine Learning Overview",
        "description": "An overview of modern machine learning techniques.",
        "summary": "Machine learning is advancing rapidly.\n\n- Deep neural networks\n- Reinforcement learning\n- Transfer learning",
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
        sample_text = read_testdata("en_250.txt")
        result = GeminiService.summarize(sample_text, length="short")

        assert result["source"] == "gemini"
        assert result["language"] == "en"
        assert mock_client.models.generate_content.call_count == 2
    finally:
        GeminiService.set_client(original_client)


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


@pytest.mark.live
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
