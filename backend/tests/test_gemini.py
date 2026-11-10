import json
import logging
import re
from pathlib import Path
from unittest.mock import MagicMock
import pytest

try:
    from backend.config import Config
    from backend.services import gemini_service
    from backend.services.gemini_service import GeminiService, normalize_quiz_questions
    from backend.utils.errors import AppError, ErrorCode
    from backend.utils.text_utils import count_characters
except ImportError:
    from config import Config
    from services import gemini_service
    from services.gemini_service import GeminiService, normalize_quiz_questions
    from utils.errors import AppError, ErrorCode
    from utils.text_utils import count_characters

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


# ---------------------------------------------------------------- Quiz (GĐ3.2)
# PROMPTS.md mục 2: backend tự kiểm JSON, cắt còn N, xáo trộn đáp án, retry 1 lần,
# hết lượt vẫn hỏng -> AI_UNAVAILABLE (quiz KHÔNG có fallback TF-IDF).

QUIZ_OPTION_LABELS = ("loan", "chum", "nom", "phach")


def quiz_payload(count: int, correct_index: int = 0) -> dict:
    """JSON giả dạng đúng schema quiz; đáp án đúng luôn ở vị trí `correct_index`."""
    return {
        "questions": [
            {
                "question": f"Cau hoi {i}?",
                "options": [f"{label} {i}" for label in QUIZ_OPTION_LABELS],
                "correct_index": correct_index,
                "explanation": f"Vi cau {i}.",
            }
            for i in range(1, count + 1)
        ]
    }


def quiz_correct_option(index: int, correct_index: int) -> str:
    return f"{QUIZ_OPTION_LABELS[correct_index]} {index}"


def test_quiz_cat_con_dung_n_cau_khi_gemini_tra_du():
    questions = normalize_quiz_questions(quiz_payload(12)["questions"], 5)
    assert len(questions) == 5
    assert [q["question"] for q in questions] == [f"Cau hoi {i}?" for i in range(1, 6)]


def test_quiz_loai_tung_cau_lloi_khong_lam_hoi_ca_phan_hoi():
    valid = quiz_payload(1)["questions"][0]
    invalid = [
        {"question": "Thieu dap an?", "options": ["a", "b", "c"], "correct_index": 0, "explanation": "x"},
        {"question": "Trung dap an?", "options": ["A", "a", "b", "c"], "correct_index": 0, "explanation": "x"},
        {"question": "Dap an rong?", "options": ["a", "b", "c", "  "], "correct_index": 0, "explanation": "x"},
        {"question": "Rong phan giai thich?", "options": ["a", "b", "c", "d"], "correct_index": 0, "explanation": " "},
        {"question": "Index ngoai 0-3?", "options": ["a", "b", "c", "d"], "correct_index": 4, "explanation": "x"},
        {"question": "Index kieu boolean?", "options": ["a", "b", "c", "d"], "correct_index": True, "explanation": "x"},
        {"question": "Index khong phai so?", "options": ["a", "b", "c", "d"], "correct_index": "0", "explanation": "x"},
        {"question": "Thieu truong?", "options": ["a", "b", "c", "d"]},
        "khong phai object",
    ]
    questions = normalize_quiz_questions(invalid + [dict(valid) for _ in range(3)], 10)
    assert len(questions) == 3
    assert all(q["question"] == "Cau hoi 1?" for q in questions)


def test_quiz_duoi_ba_cau_hop_le_thi_bai_bo():
    with pytest.raises(ValueError) as excinfo:
        normalize_quiz_questions(quiz_payload(2)["questions"], 10)
    assert "câu hợp lệ" in str(excinfo.value)
    assert "Cau hoi" not in str(excinfo.value)


@pytest.mark.parametrize("raw", [None, "van ban", {"questions": []}, 42])
def test_quiz_khong_co_mang_questions_thi_bai_bo(raw):
    with pytest.raises(ValueError):
        normalize_quiz_questions(raw, 5)


def test_quiz_xao_tron_dap_an_va_tinh_lai_correct_index():
    """Đáp án đúng phải vẫn là đáp án đúng sau shuffle, và vị trí không cố định."""
    seen_positions = set()
    for _ in range(200):
        questions = normalize_quiz_questions(quiz_payload(4, correct_index=0)["questions"], 4)
        for i, question in enumerate(questions, start=1):
            assert question["options"][question["correct_index"]] == quiz_correct_option(i, 0)
            assert len(set(option.lower() for option in question["options"])) == 4
            seen_positions.add(question["correct_index"])
    assert seen_positions != {0}, "shuffle không chạy: correct_index luôn giữ vị trí cũ"
    assert len(seen_positions) > 1


@needs_genai
def test_quiz_service_tra_dung_n_cau_va_source_gemini():
    text = read_testdata("vi_500.txt")
    n = Config.quiz_question_count(count_characters(text))
    mock_response = MagicMock()
    mock_response.text = json.dumps(quiz_payload(n + 3))

    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = mock_response

    original_client = GeminiService._client
    try:
        GeminiService.set_client(mock_client)
        result = GeminiService.generate_quiz(text, summary="Tom tat mau.", language="vi")
        assert result["question_count"] == n == len(result["questions"])
        assert result["source"] == "gemini"
        assert result["language"] == "vi"
        assert all(q["correct_index"] in (0, 1, 2, 3) for q in result["questions"])
    finally:
        GeminiService.set_client(original_client)


@needs_genai
def test_quiz_service_gui_dung_n_va_boc_document_kin():
    """Prompt phải nhồi đúng {N}, {LANGUAGE}, và văn bản người dùng nằm trong <document>."""
    text = read_testdata("vi_2500.txt")
    n = Config.quiz_question_count(count_characters(text))
    mock_response = MagicMock()
    mock_response.text = json.dumps(quiz_payload(n))

    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = mock_response

    original_client = GeminiService._client
    try:
        GeminiService.set_client(mock_client)
        GeminiService.generate_quiz(text, summary="Tom tat mau.", language="vi")
        kwargs = mock_client.models.generate_content.call_args.kwargs
        system_instruction = kwargs["config"].system_instruction
        user_content = kwargs["contents"]
        assert f"exactly {n} questions" in system_instruction
        assert 'this language: vi' in system_instruction
        assert "<document>" in user_content and "</document>" in user_content
        assert "<summary>\nTom tat mau.\n</summary>" in user_content
        # Quiz không dùng 15s của tóm tắt: đo thật 2026-11-10, 10 câu mất ~29s
        assert kwargs["config"].http_options.timeout == Config.GEMINI_QUIZ_TIMEOUT_SECONDS * 1000
    finally:
        GeminiService.set_client(original_client)


@needs_genai
def test_quiz_service_retry_sau_phan_hoi_hong_roi_thanh_cong():
    """Lần 1 trả 1 câu (dưới 3) -> lần 2 trả đủ; cả hai lần đều là lời gọi API thật."""
    text = read_testdata("vi_500.txt")
    bad = MagicMock()
    bad.text = json.dumps(quiz_payload(1))
    good = MagicMock()
    good.text = json.dumps(quiz_payload(10))

    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = [bad, good]

    original_client = GeminiService._client
    try:
        GeminiService.set_client(mock_client)
        result = GeminiService.generate_quiz(text, summary="Tom tat mau.", language="vi")
        assert result["question_count"] == Config.quiz_question_count(count_characters(text))
        assert mock_client.models.generate_content.call_count == 2
    finally:
        GeminiService.set_client(original_client)


@needs_genai
def test_quiz_service_het_retry_ra_ai_unavailable_khong_fallback():
    """SPEC 5.4: quiz không có TF-IDF -> phải raise AI_UNAVAILABLE (503), không âm thầm trả câu hỏi rỗng."""
    text = read_testdata("vi_500.txt")
    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = RuntimeError("Server AI chập chờn")

    original_client = GeminiService._client
    try:
        GeminiService.set_client(mock_client)
        with pytest.raises(AppError) as excinfo:
            GeminiService.generate_quiz(text, summary="Tom tat mau.", language="vi")
        assert excinfo.value.error_code == ErrorCode.AI_UNAVAILABLE
        assert excinfo.value.status_code == 503
        assert mock_client.models.generate_content.call_count == Config.GEMINI_MAX_RETRY + 1
    finally:
        GeminiService.set_client(original_client)


def test_quiz_service_thieu_key_ra_ai_unavailable():
    original_client = GeminiService._client
    original_key = Config.GEMINI_API_KEY
    try:
        GeminiService.set_client(None)
        Config.GEMINI_API_KEY = ""
        with pytest.raises(AppError) as excinfo:
            GeminiService.generate_quiz(read_testdata("vi_500.txt"), summary="", language="vi")
        assert excinfo.value.error_code == ErrorCode.AI_UNAVAILABLE
    finally:
        Config.GEMINI_API_KEY = original_key
        GeminiService.set_client(original_client)


@needs_genai
def test_quiz_service_khong_log_noi_dung_cau_hoi(caplog):
    """PROMPTS 2.4: log chỉ có số lượng/độ dài/time, không có question, option, explanation."""
    text = read_testdata("vi_500.txt")
    n = Config.quiz_question_count(count_characters(text))
    mock_response = MagicMock()
    mock_response.text = json.dumps(quiz_payload(n))
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = mock_response

    original_client = GeminiService._client
    try:
        GeminiService.set_client(mock_client)
        with caplog.at_level(logging.INFO, logger="text_summarizer.gemini"):
            GeminiService.generate_quiz(text, summary="Tom tat mau.", language="vi")
        assert "Cau hoi 1?" not in caplog.text
        assert "loan 1" not in caplog.text
        assert "Vi cau 1." not in caplog.text
        assert f"questions={n}" in caplog.text
    finally:
        GeminiService.set_client(original_client)
