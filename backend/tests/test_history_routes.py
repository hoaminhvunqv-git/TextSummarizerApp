"""Route đọc/xóa lịch sử (GĐ2.6): phân trang, hình dạng response và cô lập theo thiết bị.

Tầng lưu trữ được thay bằng bảng trong bộ nhớ để test không chạm Neon; quy tắc
sở hữu mô phỏng lại đúng SPEC 5.7 nên "device khác không thấy/không xóa được"
được kiểm thật chứ không chỉ giả vờ.
"""

import pytest

try:
    from backend.app import create_app
    from backend.config import Config
    from backend.services import history_service, quota_service
    from backend.utils.errors import AppError, ErrorCode
except ImportError:
    from app import create_app
    from config import Config
    from services import history_service, quota_service
    from utils.errors import AppError, ErrorCode

DEVICE_A = "3f2504e0-4f89-41d3-9a0c-0305e82c3301"
DEVICE_B = "7c9e6679-7425-40de-944b-e07fc1f90ae7"
TITLE = "Tác động của AI tới giáo dục"
DESCRIPTION = "Bài viết phân tích lợi ích và rủi ro của AI trong lớp học."
SUMMARY = "AI cá nhân hoá lộ trình học nhưng cũng tạo rủi ro lệ thuộc công cụ."
ORIGINAL = "Văn bản gốc dài hơn 400 ký tự, chỉ dùng cho test lịch sử." + "x" * 400


def headers(device_id):
    return {"X-Device-ID": device_id, "X-App-Version": "1.0.0"}


class FakeHistory:
    def __init__(self):
        self.rows = {}
        self.queries = []

    def add(self, device_id, created_at="2026-11-10T09:30:00+07:00", title=TITLE):
        summary_id = max(self.rows, default=0) + 1
        self.rows[summary_id] = {
            "id": summary_id,
            "user_id": None,
            "device_id": device_id,
            "title": title,
            "description": DESCRIPTION,
            "summary": SUMMARY,
            "original_text": ORIGINAL,
            "original_length": len(ORIGINAL),
            "language": "vi",
            "source": "gemini",
            "created_at": created_at,
        }
        return summary_id

    def _owned(self, row, device_id, user_id):
        if user_id is not None and row["user_id"] == user_id:
            return True
        return row["user_id"] is None and row["device_id"] == device_id

    def _visible(self, device_id, user_id):
        rows = [r for r in self.rows.values() if self._owned(r, device_id, user_id)]
        return sorted(rows, key=lambda r: r["created_at"], reverse=True)

    def list_summaries(self, device_id=None, user_id=None, page=1, limit=20):
        self.queries.append(("list", device_id, page, limit))
        rows = self._visible(device_id, user_id)
        start = (page - 1) * limit
        return {
            "items": [
                {k: r[k] for k in ("id", "title", "description", "language", "source", "created_at")}
                for r in rows[start:start + limit]
            ],
            "page": page,
            "limit": limit,
            "total": len(rows),
        }

    def get_summary(self, summary_id, device_id=None, user_id=None):
        self.queries.append(("get", device_id, summary_id, None))
        row = self.rows.get(summary_id)
        if row is None or not self._owned(row, device_id, user_id):
            raise AppError(ErrorCode.NOT_FOUND, message="Không tìm thấy bản tóm tắt này.")
        return {k: v for k, v in row.items() if k != "user_id"}

    def delete_summary(self, summary_id, device_id=None, user_id=None):
        self.queries.append(("delete", device_id, summary_id, None))
        row = self.rows.get(summary_id)
        if row is None or not self._owned(row, device_id, user_id):
            raise AppError(ErrorCode.NOT_FOUND, message="Không tìm thấy bản tóm tắt này.")
        del self.rows[summary_id]


class TestConfig(Config):
    TESTING = True
    # Limiter 30 request/phút tính theo device và RAM dùng chung cả tiến trình test,
    # bật lên thì vài chục request ở dưới sẽ bị 429 trước khi tới nghiệp vụ.
    RATELIMIT_ENABLED = False


@pytest.fixture
def client():
    return create_app(TestConfig).test_client()


@pytest.fixture(autouse=True)
def fake(monkeypatch):
    store = FakeHistory()
    monkeypatch.setattr(history_service, "list_summaries", store.list_summaries)
    monkeypatch.setattr(history_service, "get_summary", store.get_summary)
    monkeypatch.setattr(history_service, "delete_summary", store.delete_summary)
    monkeypatch.setattr(
        quota_service,
        "get_usage",
        lambda owner, day=None: {
            "summary": {"used": 1, "limit": Config.DAILY_SUMMARY_LIMIT, "remaining": 19},
            "quiz": {"used": 0, "limit": Config.DAILY_QUIZ_LIMIT, "remaining": 20},
            "resets_at": "2026-11-11T00:00:00+07:00",
        },
    )
    monkeypatch.setattr(
        quota_service,
        "reserve",
        lambda *a, **k: pytest.fail("Đọc hoặc xóa lịch sử không được trừ lượt tóm tắt"),
    )
    return store


def test_list_returns_contract_shape(client, fake):
    first = fake.add(DEVICE_A, created_at="2026-11-09T09:30:00+07:00", title="Bản cũ hơn")
    last = fake.add(DEVICE_A, created_at="2026-11-10T09:30:00+07:00")
    fake.add(DEVICE_B)

    resp = client.get("/api/v1/summaries", headers=headers(DEVICE_A))

    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert set(data) == {"items", "page", "limit", "total"}
    assert data["total"] == 2
    assert [i["id"] for i in data["items"]] == [last, first]
    assert set(data["items"][0]) == {
        "id", "title", "description", "language", "source", "created_at",
    }
    assert data["items"][0]["title"] == TITLE


def test_list_never_exposes_summary_or_original_text(client, fake):
    fake.add(DEVICE_A)

    body = client.get("/api/v1/summaries", headers=headers(DEVICE_A)).get_json()

    assert SUMMARY not in body["message"] + str(body["data"])
    assert ORIGINAL not in str(body["data"])


def test_empty_history_returns_empty_page_not_404(client):
    resp = client.get("/api/v1/summaries", headers=headers(DEVICE_A))

    assert resp.status_code == 200
    assert resp.get_json()["data"] == {"items": [], "page": 1, "limit": 20, "total": 0}


def test_pagination_defaults_are_forwarded(client, fake):
    client.get("/api/v1/summaries", headers=headers(DEVICE_A))

    assert fake.queries == [("list", DEVICE_A, 1, Config.HISTORY_PAGE_SIZE_DEFAULT)]


@pytest.mark.parametrize("query", ["page=0", "page=abc", "limit=0", "limit=-1", "page=1&limit=x"])
def test_invalid_pagination_returns_validation_error(client, fake, query):
    fake.add(DEVICE_A)

    resp = client.get(f"/api/v1/summaries?{query}", headers=headers(DEVICE_A))

    assert resp.status_code == 400
    assert resp.get_json()["error_code"] == ErrorCode.VALIDATION_ERROR
    assert fake.queries == []


def test_limit_above_max_is_rejected(client):
    resp = client.get(
        f"/api/v1/summaries?limit={Config.HISTORY_PAGE_SIZE_MAX + 1}", headers=headers(DEVICE_A)
    )

    assert resp.status_code == 400
    assert resp.get_json()["error_code"] == ErrorCode.VALIDATION_ERROR


def test_page_2_returns_the_remainder(client, fake):
    ids = [fake.add(DEVICE_A, created_at=f"2026-11-{d:02d}T09:30:00+07:00") for d in range(1, 6)]

    resp = client.get("/api/v1/summaries?page=2&limit=2", headers=headers(DEVICE_A))

    data = resp.get_json()["data"]
    newest_first = list(reversed(ids))
    assert data["total"] == 5
    assert [i["id"] for i in data["items"]] == newest_first[2:4]


def test_other_device_sees_nothing(client, fake):
    fake.add(DEVICE_A)

    data = client.get("/api/v1/summaries", headers=headers(DEVICE_B)).get_json()["data"]

    assert data == {"items": [], "page": 1, "limit": 20, "total": 0}


def test_detail_returns_original_text_and_usage(client, fake):
    summary_id = fake.add(DEVICE_A)

    resp = client.get(f"/api/v1/summaries/{summary_id}", headers=headers(DEVICE_A))

    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert data["id"] == summary_id
    assert data["original_text"] == ORIGINAL
    assert data["summary"] == SUMMARY
    assert data["original_length"] == len(ORIGINAL)
    assert data["usage"] == {"summary_remaining": 19, "quiz_remaining": 20}


def test_detail_of_another_device_is_404(client, fake):
    summary_id = fake.add(DEVICE_A)

    resp = client.get(f"/api/v1/summaries/{summary_id}", headers=headers(DEVICE_B))

    assert resp.status_code == 404
    assert resp.get_json()["error_code"] == ErrorCode.NOT_FOUND
    assert ORIGINAL not in resp.get_json()["message"]


def test_detail_of_missing_id_is_404(client):
    resp = client.get("/api/v1/summaries/999999", headers=headers(DEVICE_A))

    assert resp.status_code == 404
    assert resp.get_json()["error_code"] == ErrorCode.NOT_FOUND


@pytest.mark.parametrize("bad_id", ["abc", "1.5", "1;DROP"])
def test_non_integer_id_still_answers_json_404(client, bad_id):
    resp = client.get(f"/api/v1/summaries/{bad_id}", headers=headers(DEVICE_A))

    assert resp.status_code == 404
    assert resp.get_json()["error_code"] == ErrorCode.NOT_FOUND


def test_delete_removes_only_own_row(client, fake):
    mine = fake.add(DEVICE_A)
    theirs = fake.add(DEVICE_B)

    resp = client.delete(f"/api/v1/summaries/{mine}", headers=headers(DEVICE_A))

    assert resp.status_code == 200
    assert resp.get_json()["data"] == {"deleted": True}
    assert list(fake.rows) == [theirs]


def test_delete_of_another_device_is_404_and_keeps_row(client, fake):
    theirs = fake.add(DEVICE_A)

    resp = client.delete(f"/api/v1/summaries/{theirs}", headers=headers(DEVICE_B))

    assert resp.status_code == 404
    assert resp.get_json()["error_code"] == ErrorCode.NOT_FOUND
    assert theirs in fake.rows


def test_delete_twice_second_is_404(client, fake):
    summary_id = fake.add(DEVICE_A)
    client.delete(f"/api/v1/summaries/{summary_id}", headers=headers(DEVICE_A))

    resp = client.delete(f"/api/v1/summaries/{summary_id}", headers=headers(DEVICE_A))

    assert resp.status_code == 404


@pytest.mark.parametrize(
    ("method", "path"),
    [("get", "/api/v1/summaries"), ("get", "/api/v1/summaries/1"), ("delete", "/api/v1/summaries/1")],
)
def test_history_reads_require_device_id(client, fake, method, path):
    fake.add(DEVICE_A)

    resp = getattr(client, method)(path, headers={"X-App-Version": "1.0.0"})

    assert resp.status_code == 400
    assert resp.get_json()["error_code"] == ErrorCode.INVALID_DEVICE_ID


@pytest.mark.parametrize(
    ("method", "path"),
    [("get", "/api/v1/summaries"), ("get", "/api/v1/summaries/1"), ("delete", "/api/v1/summaries/1")],
)
def test_history_reads_require_current_app_version(client, fake, method, path):
    fake.add(DEVICE_A)

    resp = getattr(client, method)(path, headers={"X-Device-ID": DEVICE_A, "X-App-Version": "0.9.0"})

    assert resp.status_code == 426
    assert resp.get_json()["error_code"] == ErrorCode.UPDATE_REQUIRED


def test_history_routes_are_registered():
    rules = {
        (str(rule), tuple(sorted(rule.methods)))
        for rule in create_app().url_map.iter_rules()
        if rule.endpoint.startswith("summary.")
    }

    assert ("/api/v1/summaries", ("GET", "HEAD", "OPTIONS")) in rules
    assert ("/api/v1/summaries/<int:summary_id>", ("GET", "HEAD", "OPTIONS")) in rules
    assert ("/api/v1/summaries/<int:summary_id>", ("DELETE", "OPTIONS")) in rules
