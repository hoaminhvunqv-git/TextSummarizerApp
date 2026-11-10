"""Ghi và đọc bảng `summaries` (docs/SPEC.md 5.8 và 6).

Route không tự viết SQL: mọi truy vấn chạm `summaries` nằm ở đây để bước 2.6
dùng lại đúng câu kiểm tra quyền sở hữu (SPEC 5.7), tránh mỗi endpoint một kiểu.
"""

from typing import Optional

try:
    from backend.config import Config
    from backend.database.db import transaction
    from backend.services.crypto_service import CryptoService
    from backend.utils.errors import AppError, ErrorCode
    from backend.utils.time_utils import iso_in_vn
except ImportError:
    from config import Config
    from database.db import transaction
    from services.crypto_service import CryptoService
    from utils.errors import AppError, ErrorCode
    from utils.time_utils import iso_in_vn

INSERT_SUMMARY_SQL = """
INSERT INTO summaries
    (user_id, device_id, title_enc, description_enc, original_text_enc, summary_enc,
     original_length, language, source)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
RETURNING id, created_at;
"""

# SPEC 5.7: bản ghi chỉ truy cập được khi thuộc user gọi, hoặc còn là của khách
# (user_id IS NULL) đúng với device gọi. Một mẫu duy nhất cho cả 4 giai đoạn:
# khi user_id = None thì vế đầu không bao giờ đúng, nên không cần nhánh riêng.
OWNER_MATCH_SQL = "(user_id = %s OR (user_id IS NULL AND device_id = %s))"

SELECT_SUMMARY_SQL = f"""
SELECT title_enc, description_enc, original_text_enc, summary_enc,
       original_length, language, source, created_at
FROM summaries
WHERE id = %s AND {OWNER_MATCH_SQL};
"""

SELECT_PAGE_SQL = f"""
SELECT id, title_enc, description_enc, language, source, created_at
FROM summaries
WHERE {OWNER_MATCH_SQL}
ORDER BY created_at DESC, id DESC
LIMIT %s OFFSET %s;
"""

SELECT_TOTAL_SQL = f"""
SELECT COUNT(*) FROM summaries
WHERE {OWNER_MATCH_SQL};
"""

DELETE_SUMMARY_SQL = f"""
DELETE FROM summaries
WHERE id = %s AND {OWNER_MATCH_SQL}
RETURNING id;
"""


def _owner_params(user_id: Optional[int], device_id: Optional[str]) -> tuple:
    return (user_id, device_id)


def _not_found() -> AppError:
    """Lỗi chung cho "không tồn tại" và "không thuộc về bạn" — SPEC 5.7 không cho phân biệt."""
    return AppError(ErrorCode.NOT_FOUND, message="Không tìm thấy bản tóm tắt này.")


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


def list_summaries(device_id: Optional[str] = None, user_id: Optional[int] = None,
                   page: int = 1, limit: int = 20) -> dict:
    """Trang lịch sử của đúng người gọi: `{items, page, limit, total}`, mới nhất trước.

    Chỉ giải mã `title`/`description` vì API.md quy định trang này không trả
    `original_text` và `summary` đầy đủ.
    """
    crypto = CryptoService.from_b64_key(Config.ENCRYPTION_KEY)
    owner = _owner_params(user_id, device_id)

    with transaction() as conn:
        with conn.cursor() as cur:
            cur.execute(SELECT_PAGE_SQL, owner + (limit, (page - 1) * limit))
            rows = cur.fetchall()
            cur.execute(SELECT_TOTAL_SQL, owner)
            total = cur.fetchone()[0]

    items = [
        {
            "id": summary_id,
            "title": crypto.decrypt(title_enc),
            "description": crypto.decrypt(description_enc),
            "language": language,
            "source": source,
            "created_at": iso_in_vn(created_at),
        }
        for summary_id, title_enc, description_enc, language, source, created_at in rows
    ]
    return {"items": items, "page": page, "limit": limit, "total": total}


def get_summary(summary_id: int, device_id: Optional[str] = None,
                user_id: Optional[int] = None) -> dict:
    """Chi tiết một bản tóm tắt kèm văn bản gốc; không thuộc người gọi -> NOT_FOUND (404).

    Điều kiện sở hữu nằm trong chính câu SELECT, nên "không có" và "của người khác"
    trả về cùng một kết quả — kẻ dò không xác định được id nào từng tồn tại.
    """
    crypto = CryptoService.from_b64_key(Config.ENCRYPTION_KEY)

    with transaction() as conn:
        with conn.cursor() as cur:
            cur.execute(SELECT_SUMMARY_SQL, (summary_id,) + _owner_params(user_id, device_id))
            row = cur.fetchone()

    if row is None:
        raise _not_found()

    (title_enc, description_enc, original_text_enc, summary_enc,
     original_length, language, source, created_at) = row

    return {
        "id": summary_id,
        "title": crypto.decrypt(title_enc),
        "description": crypto.decrypt(description_enc),
        "summary": crypto.decrypt(summary_enc),
        "original_text": crypto.decrypt(original_text_enc),
        "original_length": original_length,
        "language": language,
        "source": source,
        "created_at": iso_in_vn(created_at),
    }


def delete_summary(summary_id: int, device_id: Optional[str] = None,
                   user_id: Optional[int] = None) -> None:
    """Xóa bản ghi của đúng người gọi; `quiz_sessions` đi theo nhờ ON DELETE CASCADE."""
    with transaction() as conn:
        with conn.cursor() as cur:
            cur.execute(DELETE_SUMMARY_SQL, (summary_id,) + _owner_params(user_id, device_id))
            row = cur.fetchone()

    if row is None:
        raise _not_found()
