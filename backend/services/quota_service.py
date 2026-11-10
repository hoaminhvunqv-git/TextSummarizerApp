"""Quota theo ngày cho từng chủ thể (docs/SPEC.md 5.5, bảng `usage_quota`).

Một lượt hợp lệ = tăng `count` của dòng `(owner_key, usage_type, usage_date)`.
Đặt chỗ bằng một câu SQL duy nhất có điều kiện `count < limit`, nên hai request
song song không thể cùng vượt trần và request lỗi không ăn lượt (refund).
"""

from datetime import date, datetime, time, timedelta
from typing import Optional

try:
    from backend.config import Config
    from backend.database.db import connection, transaction
    from backend.utils.errors import AppError, ErrorCode
    from backend.utils.time_utils import VN_TZ, iso_in_vn, now_vn
except ImportError:
    from config import Config
    from database.db import connection, transaction
    from utils.errors import AppError, ErrorCode
    from utils.time_utils import VN_TZ, iso_in_vn, now_vn

USAGE_SUMMARY = "SUMMARY"
USAGE_QUIZ = "QUIZ"

RESERVE_SQL = """
INSERT INTO usage_quota (owner_key, usage_type, usage_date, count)
VALUES (%s, %s, %s, 1)
ON CONFLICT (owner_key, usage_type, usage_date)
DO UPDATE SET count = usage_quota.count + 1
WHERE usage_quota.count < %s
RETURNING count;
"""

REFUND_SQL = """
UPDATE usage_quota SET count = GREATEST(count - 1, 0)
WHERE owner_key = %s AND usage_type = %s AND usage_date = %s;
"""

SELECT_USAGE_SQL = """
SELECT usage_type, count FROM usage_quota
WHERE owner_key = %s AND usage_date = %s;
"""


def now_vn() -> datetime:
    return datetime.now(VN_TZ)


def today_vn() -> date:
    """Ngày nghiệp vụ theo múi giờ +07, đổi ca đúng nửa đêm Việt Nam."""
    return now_vn().date()


def resets_at(day: Optional[date] = None) -> str:
    """Thời điểm quota reset = nửa đêm +07 của ngày kế tiếp."""
    next_day = (day or today_vn()) + timedelta(days=1)
    return iso_in_vn(datetime.combine(next_day, time.min, tzinfo=VN_TZ))


def owner_key(device_id: Optional[str] = None, user_id: Optional[int] = None) -> str:
    """JWT ưu tiên device (SPEC 5.7); quota của khách không gộp vào quota user."""
    if user_id is not None:
        return f"u:{user_id}"
    if device_id:
        return f"d:{device_id}"
    raise ValueError("owner_key cần device_id hoặc user_id.")


def limit_for(usage_type: str) -> int:
    if usage_type == USAGE_SUMMARY:
        return Config.DAILY_SUMMARY_LIMIT
    if usage_type == USAGE_QUIZ:
        return Config.DAILY_QUIZ_LIMIT
    raise ValueError(f"usage_type không hợp lệ: {usage_type}")


def reserve(owner: str, usage_type: str, day: Optional[date] = None) -> int:
    """Đặt trước một lượt và trả số lượt đã dùng sau khi đặt.

    Không có dòng nào trả về nghĩa là trần đã chạm → `QUOTA_EXCEEDED`, và DB
    không bị tăng count.
    """
    day = day or today_vn()
    with transaction() as conn:
        with conn.cursor() as cur:
            cur.execute(RESERVE_SQL, (owner, usage_type, day, limit_for(usage_type)))
            row = cur.fetchone()
    if row is None:
        raise AppError(ErrorCode.QUOTA_EXCEEDED)
    return row[0]


def refund(owner: str, usage_type: str, day: Optional[date] = None) -> None:
    """Hoàn một lượt khi xử lý thất bại; `GREATEST` giữ count không bao giờ âm."""
    day = day or today_vn()
    with transaction() as conn:
        with conn.cursor() as cur:
            cur.execute(REFUND_SQL, (owner, usage_type, day))


def get_usage(owner: str, day: Optional[date] = None) -> dict:
    """Số lượt đã dùng/còn lại hôm nay, đúng shape `GET /api/v1/usage` (API.md)."""
    day = day or today_vn()
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute(SELECT_USAGE_SQL, (owner, day))
            used_by_type = {row[0]: row[1] for row in cur.fetchall()}

    data = {}
    for usage_type, key in ((USAGE_SUMMARY, "summary"), (USAGE_QUIZ, "quiz")):
        limit = limit_for(usage_type)
        used = used_by_type.get(usage_type, 0)
        data[key] = {
            "used": used,
            "limit": limit,
            "remaining": max(limit - used, 0),
        }
    data["resets_at"] = resets_at(day)
    return data
