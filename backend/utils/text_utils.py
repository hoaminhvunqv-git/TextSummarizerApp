import re
import unicodedata
from typing import List

# Bộ ký tự nguyên âm và phụ âm có dấu đặc trưng của tiếng Việt (NFC)
VIETNAMESE_DIACRITICS_REGEX = re.compile(
    r"[àáảãạăằắẳẵặâầấẩẫậđèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵ]",
    re.IGNORECASE,
)

# Regex tách câu hỗ trợ tiếng Việt và tiếng Anh (. ! ? … và xuống dòng)
SENTENCE_SPLIT_REGEX = re.compile(r"(?<=[.!?…\n])\s+")


def normalize_text(text: str) -> str:
    """Chuẩn hóa Unicode dạng NFC và loại bỏ khoảng trắng thừa đầu/cuối theo CLAUDE.md & SPEC 5.1."""
    if not text:
        return ""
    # Chuẩn hóa Unicode NFC
    normalized = unicodedata.normalize("NFC", text)
    # Loại bỏ khoảng trắng đầu và cuối chuỗi
    return normalized.strip()


def count_characters(text: str) -> int:
    """Đếm số lượng ký tự chính xác sau khi đã chuẩn hóa NFC và strip."""
    return len(normalize_text(text))


def split_sentences(text: str) -> List[str]:
    """Tách văn bản thành các câu riêng biệt bằng regex hỗ trợ dấu .!?… và xuống dòng.

    Giữ nguyên câu hoàn chỉnh và loại bỏ các câu rỗng.
    """
    normalized = normalize_text(text)
    if not normalized:
        return []

    # Chia theo dấu kết thúc câu hoặc dòng mới
    raw_sentences = SENTENCE_SPLIT_REGEX.split(normalized)
    sentences = [s.strip() for s in raw_sentences if s.strip()]

    # Nếu văn bản không có dấu chấm/ngắt dòng (ví dụ 1 đoạn liền), trả về chính nó
    return sentences if sentences else [normalized]


def detect_language(text: str) -> str:
    """Nhận diện ngôn ngữ chiếm ưu thế của văn bản ('vi' hoặc 'en') theo SPEC 1.1."""
    normalized = normalize_text(text)
    if not normalized:
        return "vi"

    # Đếm số lượng ký tự có dấu đặc trưng tiếng Việt
    vietnamese_matches = VIETNAMESE_DIACRITICS_REGEX.findall(normalized)

    # Nếu có từ 2 ký tự có dấu tiếng Việt trở lên, nhận diện là 'vi'
    if len(vietnamese_matches) >= 2:
        return "vi"

    # Kiểm tra các từ tiếng Việt không dấu phổ biến
    common_vi_words = {"va", "la", "cua", "trong", "co", "nguoi", "cho", "duoc", "khong"}
    words = {w.lower() for w in re.findall(r"\b\w+\b", normalized)}
    if len(words.intersection(common_vi_words)) >= 2:
        return "vi"

    return "en"
