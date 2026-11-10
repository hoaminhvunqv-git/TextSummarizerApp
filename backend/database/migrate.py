"""Chạy các file migration chưa áp dụng trong backend/database/migrations/.

Cách dùng (từ thư mục backend/):
    python database/migrate.py
Mỗi file được áp trong một transaction cùng dòng ghi vào schema_migrations,
nên chạy lại lần hai là no-op. Xem docs/SPEC.md mục 6.
"""

import sys
from pathlib import Path
from typing import List

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

# Console Windows mặc định cp1252, không in nổi tiếng Việt có dấu.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from database.db import connection, db_configured  # noqa: E402

MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"

# 001_init.sql cũng tạo bảng này với IF NOT EXISTS; chạy trước để đọc được ledger.
LEDGER_SQL = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    filename   VARCHAR(255) PRIMARY KEY,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""


def plan_migrations(applied: set) -> List[Path]:
    """Các file .sql chưa có trong schema_migrations, sắp xếp theo tên."""
    files = sorted(MIGRATIONS_DIR.glob("*.sql"))
    return [path for path in files if path.name not in applied]


def run_migrations() -> List[str]:
    """Áp dụng mọi migration còn nợ và trả về tên các file vừa áp dụng."""
    applied_now: List[str] = []
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute(LEDGER_SQL)
            conn.commit()

            cur.execute("SELECT filename FROM schema_migrations")
            applied = {row[0] for row in cur.fetchall()}

            for path in plan_migrations(applied):
                # File SQL tĩnh, không chứa tham số người dùng nên chạy nguyên khối.
                cur.execute(path.read_text(encoding="utf-8"))
                cur.execute(
                    "INSERT INTO schema_migrations (filename) VALUES (%s)", (path.name,)
                )
                conn.commit()
                applied_now.append(path.name)
    return applied_now


def main() -> int:
    if not db_configured():
        print("Thiếu DATABASE_URL trong backend/.env — không chạy migrate được.")
        return 1

    applied_now = run_migrations()
    if applied_now:
        for name in applied_now:
            print(f"Đã áp dụng: {name}")
    else:
        print("Không có migration nào mới. Lược đồ đã ở bản hiện tại.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
