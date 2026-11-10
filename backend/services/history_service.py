"""Ghi và đọc bảng `summaries` (docs/SPEC.md 5.8 và 6).

Route không tự viết SQL: mọi truy vấn chạm `summaries` nằm ở đây để bước 2.6
dùng lại đúng câu kiểm tra quyền sở hữu (SPEC 5.7), tránh mỗi endpoint một kiểu.
"""

from typing import Optional

try:
    from backend.config import Config
    from backend.database.db import transaction
    from backend.services.crypto_service import CryptoService
    from backend.utils.time_utils import iso_in_vn
except ImportError:
    from config import Config
    from database.db import transaction
    from services.crypto_service import CryptoService
    from utils.time_utils import iso_in_vn

INSERT_SUMMARY_SQL = """
INSERT INTO summaries
    (user_id, device_id, title_enc, description_enc, original_text_enc, summary_enc,
     original_length, language, source)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
RETURNING id, created_at;
"""


def save_summary(result: dict, text: str, device_id: Optional[str] = None,
                 user_id: Optional[int] = None) -> tuple:
    """Mã hóa 4 trường văn bản rồi ghi một dòng, trả `(id, created_at ISO +07)`.

    `result` là output của GeminiService/TfidfService: `title`, `description`,
    `summary`, `language`, `source`. `text` là bản gốc đã NFC + strip.
    """
    crypto = CryptoService.from_b64_key(Config.ENCRYPTION_KEY)
    params = (
        user_id,
        device_id,
        crypto.encrypt(result["title"]),
        crypto.encrypt(result["description"]),
        crypto.encrypt(text),
        crypto.encrypt(result["summary"]),
        len(text),
        result["language"],
        result["source"],
    )

    with transaction() as conn:
        with conn.cursor() as cur:
            cur.execute(INSERT_SUMMARY_SQL, params)
            summary_id, created_at = cur.fetchone()

    return summary_id, iso_in_vn(created_at)
