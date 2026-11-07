from pathlib import Path
import pytest

try:
    from backend.services.tfidf_service import TfidfService
    from backend.utils.text_utils import split_sentences
except ImportError:
    from services.tfidf_service import TfidfService
    from utils.text_utils import split_sentences

TESTDATA_DIR = Path(__file__).resolve().parent.parent.parent / "testdata"


def read_testdata(filename: str) -> str:
    """Đọc nội dung file kiểm thử từ testdata."""
    file_path = TESTDATA_DIR / filename
    return file_path.read_text(encoding="utf-8")


def test_tfidf_vietnamese_summary():
    """Kiểm tra tóm tắt TF-IDF với văn bản tiếng Việt mẫu vi_500.txt."""
    vi_text = read_testdata("vi_500.txt")
    result = TfidfService.summarize(vi_text, length="medium")

    assert result["source"] == "tfidf"
    assert result["language"] == "vi"
    assert len(result["title"]) <= 60
    assert len(result["description"]) <= 120
    assert len(result["summary"]) > 0
    assert result["original_length"] == len(vi_text.strip())


def test_tfidf_english_summary():
    """Kiểm tra tóm tắt TF-IDF với văn bản tiếng Anh mẫu en_250.txt."""
    en_text = read_testdata("en_250.txt")
    result = TfidfService.summarize(en_text, length="short")

    assert result["source"] == "tfidf"
    assert result["language"] == "en"
    assert len(result["summary"]) > 0


def test_tfidf_preserves_original_sentence_order():
    """Kiểm tra quy định bắt buộc (SPEC 5.6 & DoD):

    Các câu được chọn bởi TF-IDF PHẢI GIỮ NGUYÊN THỨ TỰ GỐC ban đầu.
    """
    text = (
        "Câu thứ nhất nói về mở đầu vấn đề học máy. "
        "Câu thứ hai phân tích dữ liệu và thuật toán số học. "
        "Câu thứ ba giải thích mạng nơ-ron nhân tạo sâu sắc. "
        "Câu thứ tư nêu lên ứng dụng của trí tuệ nhân tạo. "
        "Câu thứ năm tổng kết các thành tựu của công nghệ thông tin. "
        "Câu thứ sáu dự đoán xu hướng tương lai của AI."
    )
    all_sentences = split_sentences(text)
    result = TfidfService.summarize(text, length="medium")

    summary_sentences = split_sentences(result["summary"])
    assert len(summary_sentences) >= 2

    # Lấy vị trí xuất hiện của từng câu tóm tắt trong danh sách câu gốc
    indices = [all_sentences.index(s) for s in summary_sentences if s in all_sentences]

    # Kiểm tra danh sách chỉ số tăng dần nghiêm ngặt (tức là giữ đúng thứ tự ban đầu)
    assert indices == sorted(indices), "Các câu tóm tắt không giữ đúng thứ tự xuất hiện ban đầu!"


def test_tfidf_lengths_scaling():
    """Kiểm tra số lượng câu thay đổi theo short, medium, long."""
    long_text = (
        "Câu số 1 bàn về việc ứng dụng trí tuệ nhân tạo. "
        "Câu số 2 đánh giá tác động của AI trong chuyển đổi số doanh nghiệp. "
        "Câu số 3 phân tích quy trình xử lý ngôn ngữ tự nhiên. "
        "Câu số 4 tập trung vào thuật toán học có giám sát. "
        "Câu số 5 phân tích mô hình học tăng cường hiện đại. "
        "Câu số 6 trình bày các giải pháp an toàn thông tin số. "
        "Câu số 7 xem xét tác động xã hội của công nghệ tự động hóa. "
        "Câu số 8 dự báo thị trường phần mềm trong thập kỷ tới."
    )

    res_short = TfidfService.summarize(long_text, length="short")
    res_medium = TfidfService.summarize(long_text, length="medium")
    res_long = TfidfService.summarize(long_text, length="long")

    count_short = len(split_sentences(res_short["summary"]))
    count_medium = len(split_sentences(res_medium["summary"]))
    count_long = len(split_sentences(res_long["summary"]))

    assert count_short <= count_medium <= count_long
    assert count_short >= 2
    assert count_long <= 8


def test_tfidf_very_short_text():
    """Kiểm tra văn bản chỉ có 1-2 câu không bị lỗi và trích xuất đúng."""
    short_text = "Trí tuệ nhân tạo đang phát triển nhanh. Nó mang lại nhiều lợi ích lớn."
    result = TfidfService.summarize(short_text, length="medium")

    assert result["source"] == "tfidf"
    assert "Trí tuệ nhân tạo" in result["summary"]
