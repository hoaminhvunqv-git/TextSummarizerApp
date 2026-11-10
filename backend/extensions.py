try:
    from backend.config import Config
except ImportError:
    from config import Config

from flask import request
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address


def get_rate_limit_key() -> str:
    """Chốt chặn theo thiết bị thay vì IP.

    Sau proxy (Render) mọi request chung một IP egress nên key theo IP sẽ gộp
    toàn bộ người dùng thành một; X-Device-ID luôn có vì app gắn interceptor.
    """
    device_id = (request.headers.get("X-Device-ID") or "").strip()
    if device_id:
        return f"device:{device_id}"
    return f"ip:{get_remote_address()}"


# Khởi tạo chưa gắn app để routes có thể import mà không gây import vòng với app.py.
# Storage RAM chỉ đúng khi chạy 1 worker (SPEC 2.2: gunicorn --workers 1 --threads 4).
limiter = Limiter(
    key_func=get_rate_limit_key,
    default_limits=[f"{Config.RATE_LIMIT_PER_MINUTE} per minute"],
    storage_uri=Config.RATELIMIT_STORAGE_URI,
)