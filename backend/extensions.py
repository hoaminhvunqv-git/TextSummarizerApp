import uuid

try:
    from backend.config import Config
except ImportError:
    from config import Config

from flask import request
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# Header dài tuỳ ý sẽ trở thành key của bộ đếm, nên phải cắt trước khi validate.
_MAX_DEVICE_HEADER = 64


def get_rate_limit_key() -> str:
    """Chốt chặn theo thiết bị thay vì IP.

    Sau proxy (Render) mọi request chung một IP egress nên key theo IP sẽ gộp
    toàn bộ người dùng thành một; X-Device-ID luôn có vì app gắn interceptor.

    Flask-Limiter chạy ở `before_request`, tức TRƯỚC `validate_device_id`, nên không
    được tin header: client đổi `X-Device-ID` mỗi lần là vô hiệu hoá hết 30 req/phút
    và làm kho RAM phình theo số header lạ. Chỉ nhận đúng UUID v4 chuẩn viết thường,
    còn lại rơi về IP.
    """
    raw = (request.headers.get("X-Device-ID") or "").strip()[:_MAX_DEVICE_HEADER]
    try:
        parsed = uuid.UUID(raw, version=4)
    except ValueError:
        return f"ip:{get_remote_address()}"
    if str(parsed) != raw.lower():
        return f"ip:{get_remote_address()}"
    return f"device:{parsed}"


# Khởi tạo chưa gắn app để routes có thể import mà không gây import vòng với app.py.
# Storage RAM chỉ đúng khi chạy 1 worker (SPEC 2.2: gunicorn --workers 1 --threads 4).
limiter = Limiter(
    key_func=get_rate_limit_key,
    default_limits=[f"{Config.RATE_LIMIT_PER_MINUTE} per minute"],
    storage_uri=Config.RATELIMIT_STORAGE_URI,
)