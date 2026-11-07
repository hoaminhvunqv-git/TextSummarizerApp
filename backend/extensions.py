try:
    from backend.config import Config
except ImportError:
    from config import Config

from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# Khởi tạo chưa gắn app để routes có thể import mà không gây import vòng với app.py.
# Storage RAM chỉ đúng khi chạy 1 worker (SPEC 2.2: gunicorn --workers 1 --threads 4).
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[f"{Config.RATE_LIMIT_PER_MINUTE} per minute"],
)