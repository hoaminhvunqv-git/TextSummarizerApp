"""Lớp kết nối PostgreSQL dùng chung cho toàn backend.

Theo docs/SPEC.md 2.2: psycopg2 + SQL thuần có tham số, không ORM.
Pool tạo lười ở lần gọi đầu tiên để backend vẫn boot được khi thiếu
DATABASE_URL — đó là điều kiện để "dừng ở giai đoạn nào cũng deploy được".
"""

import threading
from contextlib import contextmanager
from typing import Optional

from psycopg2 import pool

try:
    from backend.config import Config
    from backend.utils.errors import AppError, ErrorCode
except ImportError:
    from config import Config
    from utils.errors import AppError, ErrorCode

# psycopg2 chỉ GIỮ lại connection khi số connection nhàn rỗi còn dưới minconn,
# nên minconn=1 biến mỗi burst thành một lần bắt tay TLS mới với Neon.
POOL_MIN_CONN = 4
# render.yaml chạy 1 worker x 4 threads, cộng thêm dự phòng cho request chồng nhau.
POOL_MAX_CONN = 8

_pool: Optional[pool.ThreadedConnectionPool] = None
_pool_lock = threading.Lock()


def _checkout():
    """Mượn một connection; pool hết chỗ là quá tải, không phải lỗi code."""
    try:
        return get_pool().getconn()
    except pool.PoolError as exc:
        raise AppError(
            ErrorCode.INTERNAL_ERROR,
            message="Máy chủ đang bận, vui lòng thử lại sau ít phút.",
            status_code=503,
        ) from exc


def db_configured() -> bool:
    """DATABASE_URL có tồn tại hay không (chưa mở kết nối thật)."""
    return bool((Config.DATABASE_URL or "").strip())


def get_pool() -> pool.ThreadedConnectionPool:
    """Trả về pool dùng chung, khởi tạo ở lần gọi đầu tiên."""
    global _pool
    if _pool is not None:
        return _pool
    with _pool_lock:
        if _pool is None:
            if not db_configured():
                raise RuntimeError("DATABASE_URL chưa được cấu hình")
            _pool = pool.ThreadedConnectionPool(
                POOL_MIN_CONN, POOL_MAX_CONN, dsn=Config.DATABASE_URL
            )
    return _pool


@contextmanager
def connection():
    """Mượn một connection từ pool; caller tự quyết định commit/rollback."""
    conn = _checkout()
    try:
        yield conn
    finally:
        get_pool().putconn(conn)


@contextmanager
def transaction():
    """Commit khi khối thành công, rollback khi có lỗi, luôn trả connection về pool."""
    with connection() as conn:
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise


def close_pool() -> None:
    """Đóng pool (dùng trong test và khi process thoát)."""
    global _pool
    with _pool_lock:
        if _pool is not None:
            _pool.closeall()
            _pool = None
