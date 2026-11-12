"""Mốc thời gian nghiệp vụ của toàn backend.

Việt Nam không có DST từ 1977 nên dùng offset cố định +07:00 thay cho
`ZoneInfo("Asia/Ho_Chi_Minh")`: Windows không có hệ thống zone database, sẽ fail
tới khi cài thêm `tzdata`, còn Render (Linux) lại chạy được — lệch môi trường như
vậy khiến quota đổi ngày lúc nửa đêm chỉ đúng ở một nơi. Xem docs/SPEC.md 5.5.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

VN_TZ = timezone(timedelta(hours=7))


def now_vn() -> datetime:
    return datetime.now(VN_TZ)


def iso_in_vn(moment: Optional[datetime]) -> Optional[str]:
    """Đổi một datetime có múi giờ (kể cả UTC từ PostgreSQL) sang ISO `+07:00`.

    Trả `None` khi không có thời gian: hàm này được gọi SAU khi transaction commit,
    mà nổ ở đó thì route coi là thất bại và hoàn lượt — người dùng có bản tóm tắt
    miễn phí. Mất một mốc giờ ít hại hơn mất tiền lượt của người khác.
    """
    if moment is None:
        return None
    return moment.astimezone(VN_TZ).isoformat(timespec="seconds")
