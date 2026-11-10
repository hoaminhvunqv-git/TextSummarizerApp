import pytest

try:
    from backend.app import create_app
    from backend.config import Config
    from backend.database import db, migrate
except ImportError:
    from app import create_app
    from config import Config
    from database import db, migrate


@pytest.fixture(autouse=True)
def no_pool():
    """Mỗi test bắt đầu và kết thúc ở trạng thái chưa có pool."""
    db.close_pool()
    yield
    db.close_pool()


def test_backend_boots_without_database_url(monkeypatch):
    """Bất biến deploy: thiếu DATABASE_URL thì app vẫn khởi tạo và /health vẫn 200."""
    monkeypatch.setattr(Config, "DATABASE_URL", "")
    assert db.db_configured() is False

    client = create_app().test_client()
    assert client.get("/health").status_code == 200
    assert client.get("/api/v1/config").status_code == 200


def test_get_pool_raises_without_database_url(monkeypatch):
    """Route cần DB phải thấy lỗi rõ ràng, không im lặng trả dữ liệu rỗng."""
    monkeypatch.setattr(Config, "DATABASE_URL", "   ")
    with pytest.raises(RuntimeError, match="DATABASE_URL"):
        db.get_pool()


def test_plan_migrations_skips_applied_and_sorts_by_name(monkeypatch, tmp_path):
    """Migrate chỉ áp file chưa có trong ledger, theo thứ tự số thứ tự trong tên."""
    for name in ["002_quiz.sql", "001_init.sql", "003_quota.sql"]:
        (tmp_path / name).write_text("SELECT 1;", encoding="utf-8")
    (tmp_path / "notes.txt").write_text("", encoding="utf-8")
    monkeypatch.setattr(migrate, "MIGRATIONS_DIR", tmp_path)

    pending = migrate.plan_migrations({"001_init.sql"})
    assert [path.name for path in pending] == ["002_quiz.sql", "003_quota.sql"]


def test_ledger_sql_is_idempotent_text():
    """Bảng ledger phải dùng IF NOT EXISTS vì 001_init.sql cũng tạo nó."""
    assert "CREATE TABLE IF NOT EXISTS schema_migrations" in migrate.LEDGER_SQL
