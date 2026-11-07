import io
from pathlib import Path

import pytest

try:
    from backend.app import create_app
    from backend.config import Config
except ImportError:
    from app import create_app
    from config import Config

TESTDATA_DIR = Path(__file__).resolve().parent.parent.parent / "testdata"
ENDPOINT = "/api/v1/files/extract"
DEVICE_ID = "3f2504e0-4f89-41d3-9a0c-0305e82c3301"
HEADERS = {"X-Device-ID": DEVICE_ID, "X-App-Version": "1.0.0"}


class TestConfig(Config):
    TESTING = True
    RATELIMIT_ENABLED = False


@pytest.fixture
def client():
    return create_app(TestConfig).test_client()


def upload(client, filename, content, headers=None):
    data = {"file": (io.BytesIO(content), filename)}
    return client.post(
        ENDPOINT,
        data=data,
        content_type="multipart/form-data",
        headers=HEADERS if headers is None else headers,
    )


def upload_file(client, filename, headers=None):
    path = TESTDATA_DIR / filename
    return upload(client, filename, path.read_bytes(), headers)


def test_extract_txt(client):
    resp = upload_file(client, "sample.txt")

    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert data["filename"] == "sample.txt"
    assert len(data["text"]) > 0
    assert data["char_count"] == len(data["text"])


def test_extract_docx(client):
    resp = upload_file(client, "sample.docx")

    assert resp.status_code == 200
    assert len(resp.get_json()["data"]["text"]) > 0


def test_extract_pdf(client):
    resp = upload_file(client, "sample_text.pdf")

    assert resp.status_code == 200
    assert len(resp.get_json()["data"]["text"]) > 0


def test_scanned_pdf_returns_pdf_scanned(client):
    resp = upload_file(client, "scanned.pdf")

    assert resp.status_code == 400
    assert resp.get_json()["error_code"] == "PDF_SCANNED"


def test_oversized_file_returns_413(client):
    resp = upload_file(client, "big_11mb.pdf")

    assert resp.status_code == 413
    assert resp.get_json()["error_code"] == "FILE_TOO_LARGE"


def test_unsupported_extension(client):
    resp = upload(client, "tai_lieu.doc", "nội dung giả".encode("utf-8"))

    assert resp.status_code == 400
    assert resp.get_json()["error_code"] == "FILE_UNSUPPORTED"


def test_empty_file(client):
    resp = upload(client, "empty.txt", b"")

    assert resp.status_code == 400
    assert resp.get_json()["error_code"] == "FILE_EMPTY"


def test_text_over_max_chars(client):
    resp = upload_file(client, "long_31000.txt")

    assert resp.status_code == 400
    assert resp.get_json()["error_code"] == "TEXT_TOO_LONG"


def test_short_text_is_allowed(client):
    """Không chặn tối thiểu 200 ký tự ở bước extract (API.md không liệt kê TEXT_TOO_SHORT)."""
    resp = upload_file(client, "short_100.txt")

    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert data["char_count"] == 100


def test_missing_file_field(client):
    resp = client.post(ENDPOINT, data={}, content_type="multipart/form-data", headers=HEADERS)

    assert resp.status_code == 400
    assert resp.get_json()["error_code"] == "VALIDATION_ERROR"


def test_missing_device_id(client):
    resp = upload_file(client, "sample.txt", headers={"X-App-Version": "1.0.0"})

    assert resp.status_code == 400
    assert resp.get_json()["error_code"] == "INVALID_DEVICE_ID"


def test_old_app_version(client):
    resp = upload_file(client, "sample.txt", headers={"X-Device-ID": DEVICE_ID, "X-App-Version": "0.9.0"})

    assert resp.status_code == 426
    assert resp.get_json()["error_code"] == "UPDATE_REQUIRED"


def test_filename_preserved_with_unicode(client):
    resp = upload(client, "tài_liệu tiếng Việt.txt", "Nội dung ngắn".encode("utf-8"))

    # Tên file dài hơn 255 sẽ bị cắt; ở đây giữ nguyên vì ngắn
    assert resp.get_json()["data"]["filename"] == "tài_liệu tiếng Việt.txt"