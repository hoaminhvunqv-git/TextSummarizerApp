# PROGRESS.md

> AI cập nhật file này sau MỖI bước xong, trước khi đề xuất commit.

## Đang ở
Giai đoạn 1A — Bước 1A.1 đã xong. Chuẩn bị bước 1A.2.

## Đã xong
- Bước 0: .gitignore, CLAUDE.md, docs/, testdata/, schema.sql, .env, .env.example
- Đã thêm 4 font Roboto vào mobile/fonts, thêm app_icon.png vào mobile/assets/images/
- Đã thêm GEMINI_API_KEY, GEMINI_MODEL, DATABASE_URL, JWT_SECRET, ENCRYPTION_KEY vào trong backend/.env
- Đã cài Flutter, Python 3.15.2, Android SDK, Đã có điện thoại Android.
- Bước 1A.1: Khởi tạo khung Flask (`app.py`, `config.py`, `utils/responses.py`, `utils/errors.py`, `routes/system_routes.py`, `tests/test_system.py`, `pytest.ini`). Các endpoint `/health` và `/api/v1/config` đã hoạt động và pass kiểm thử.

## Đang dở / bước tiếp theo
- 1A.2: `utils/text_utils.py` + `validators.py`: NFC, strip, kiểm tra 200–30.000, kiểm tra header `X-Device-ID`/`X-App-Version`.

## Quyết định đã chốt khi code
- Cấu hình `sys.path` và `pytest.ini` (`pythonpath = . ..`) để code backend có thể chạy mượt mà từ cả thư mục `backend/` lẫn thư mục gốc repo.
- Format response và error code tuân thủ nghiêm ngặt mục 2 và mục 5 trong `docs/API.md`.
- Cấu hình `app.json.ensure_ascii = False` để JSON trả về tiếng Việt UTF-8 trực tiếp, không bị mã hoá thành `\u...`.

## Lỗi đã biết / việc cần nhớ
- (chưa có)

## Cách chạy và test hiện tại
- Chạy backend:
  ```bash
  cd backend
  .\.venv\Scripts\activate   # Windows
  python app.py
  ```
- Chạy test tự động:
  ```bash
  cd backend
  pytest
  ```
