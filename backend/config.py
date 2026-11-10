import os
from pathlib import Path
from dotenv import load_dotenv

# Luôn load file .env trong thư mục backend/
BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / ".env"
if ENV_PATH.exists():
    load_dotenv(dotenv_path=ENV_PATH)
else:
    load_dotenv()


class Config:
    """Cấu hình toàn cục cho Backend TextSummarizer AI."""

    # Server config
    PORT = int(os.getenv("PORT", 5000))
    HOST = os.getenv("HOST", "0.0.0.0")
    ENV = os.getenv("FLASK_ENV", "development")
    DEBUG = os.getenv("FLASK_DEBUG", "0").lower() in ("1", "true")

    # AI (Gemini)
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")
    GEMINI_TIMEOUT_SECONDS = int(os.getenv("GEMINI_TIMEOUT_SECONDS", 15))
    GEMINI_MAX_RETRY = int(os.getenv("GEMINI_MAX_RETRY", 1))

    # Security
    ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY", "")
    JWT_SECRET = os.getenv("JWT_SECRET", "")

    # Database
    DATABASE_URL = os.getenv("DATABASE_URL", "")

    # Email (Brevo)
    BREVO_API_KEY = os.getenv("BREVO_API_KEY", "")
    BREVO_SENDER_EMAIL = os.getenv("BREVO_SENDER_EMAIL", "")
    BREVO_SENDER_NAME = os.getenv("BREVO_SENDER_NAME", "TextSummarizer AI")

    # Business Limits & App Version (theo docs/SPEC.md & docs/API.md)
    MIN_APP_VERSION = "1.0.0"
    MIN_CHARS = 400
    MAX_CHARS = 30000
    MAX_FILE_MB = 10
    MAX_CONTENT_LENGTH = MAX_FILE_MB * 1024 * 1024
    DAILY_SUMMARY_LIMIT = 20
    DAILY_QUIZ_LIMIT = 20

    # Phân trang lịch sử (docs/API.md: GET /summaries?page=&limit=).
    HISTORY_PAGE_SIZE_DEFAULT = 20
    HISTORY_PAGE_SIZE_MAX = 50

    # Ngưỡng số ký tự tối thiểu của bản gốc để mở khoá từng mốc tóm tắt (SPEC 5.1).
    # Derivation: ~120 ký tự/câu -> Ngắn >= 3 câu, Vừa >= 8 câu, Dài >= 15 câu.
    LENGTH_UNLOCK_CHARS = {
        "short": MIN_CHARS,
        "medium": 1000,
        "long": 2000,
    }

    # Độ dài bản tóm tắt = tỷ lệ % độ dài bản gốc, kẹp trong [floor, ceiling].
    # ratio/words dùng cho Gemini, ratio/sentences dùng cho TF-IDF fallback.
    LENGTH_POLICIES = {
        "short": {"ratio": 12, "min_words": 25, "max_words": 120, "min_sentences": 2, "max_sentences": 5},
        "medium": {"ratio": 22, "min_words": 40, "max_words": 260, "min_sentences": 3, "max_sentences": 8},
        "long": {"ratio": 35, "min_words": 60, "max_words": 450, "min_sentences": 5, "max_sentences": 12},
    }

    # Số câu quiz: N = clamp(floor(ký tự gốc / 130), 3, 10) (SPEC 5.4).
    QUIZ_QUESTIONS_PER_CHARS = 130
    QUIZ_QUESTIONS_MIN = 3
    QUIZ_QUESTIONS_MAX = 10

    @classmethod
    def target_words(cls, word_count: int, length: str) -> int:
        """Số từ đích của bản tóm tắt theo mốc length (SPEC 5.1)."""
        policy = cls.LENGTH_POLICIES.get(length) or cls.LENGTH_POLICIES["medium"]
        raw = round(word_count * policy["ratio"] / 100)
        return max(policy["min_words"], min(policy["max_words"], raw))

    @classmethod
    def target_sentences(cls, sentence_count: int, length: str) -> int:
        """Số câu đích của bản tóm tắt TF-IDF theo mốc length (SPEC 5.6)."""
        policy = cls.LENGTH_POLICIES.get(length) or cls.LENGTH_POLICIES["medium"]
        raw = round(sentence_count * policy["ratio"] / 100)
        return max(policy["min_sentences"], min(policy["max_sentences"], raw))

    @classmethod
    def quiz_question_count(cls, char_count: int) -> int:
        """Số câu hỏi quiz cho văn bản gốc `char_count` ký tự đã chuẩn hóa NFC (SPEC 5.4).

        Hàm không kiểm trần 400 ký tự: route chặn bằng `QUIZ_TEXT_TOO_SHORT` trước
        khi gọi, nên giá trị trả về luôn trong [3, 10] dù đầu vào nhỏ.
        """
        raw = char_count // cls.QUIZ_QUESTIONS_PER_CHARS
        return max(cls.QUIZ_QUESTIONS_MIN, min(cls.QUIZ_QUESTIONS_MAX, raw))

    # Chống spam theo IP (SPEC 5.5). Quota nghiệp vụ theo ngày nằm ở bảng usage_quota (GĐ2).
    RATE_LIMIT_PER_MINUTE = int(os.getenv("RATE_LIMIT_PER_MINUTE", 30))
    RATELIMIT_ENABLED = os.getenv("RATELIMIT_ENABLED", "1").lower() in ("1", "true")
    RATELIMIT_STORAGE_URI = os.getenv("RATELIMIT_STORAGE_URI", "memory://")
