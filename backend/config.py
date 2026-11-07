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
    MIN_CHARS = 200
    MAX_CHARS = 30000
    MAX_FILE_MB = 10
    DAILY_SUMMARY_LIMIT = 20
    DAILY_QUIZ_LIMIT = 20

    # Chống spam theo IP (SPEC 5.5). Quota nghiệp vụ theo ngày nằm ở bảng usage_quota (GĐ2).
    RATE_LIMIT_PER_MINUTE = int(os.getenv("RATE_LIMIT_PER_MINUTE", 30))
    RATELIMIT_ENABLED = os.getenv("RATELIMIT_ENABLED", "1").lower() in ("1", "true")
    RATELIMIT_STORAGE_URI = os.getenv("RATELIMIT_STORAGE_URI", "memory://")
