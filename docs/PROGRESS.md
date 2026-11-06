# PROGRESS.md

> AI cập nhật file này sau MỖI bước xong, trước khi đề xuất commit.

## Đang ở
Giai đoạn 1B (Khung Flutter) đã xong. Chuẩn bị bước tiếp theo: Giai đoạn 1A.2 (Backend logic validate).

## Đã xong
- Bước 0: .gitignore, CLAUDE.md, docs/, testdata/, schema.sql, .env, .env.example
- Đã thêm 4 font Roboto vào mobile/fonts, thêm app_icon.png vào mobile/assets/images/
- Đã thêm GEMINI_API_KEY, GEMINI_MODEL, DATABASE_URL, JWT_SECRET, ENCRYPTION_KEY vào trong backend/.env
- Đã cài Flutter, Python 3.15.2, Android SDK, Đã có điện thoại Android.
- Bước 1A.1: Khởi tạo khung Flask (`app.py`, `config.py`, `utils/responses.py`, `utils/errors.py`, `routes/system_routes.py`, `tests/test_system.py`, `pytest.ini`). Các endpoint `/health` và `/api/v1/config` đã hoạt động và pass kiểm thử.
- Bước 1B (Khung Flutter):
  - Thiết lập `pubspec.yaml` với `dio`, `provider`, `flutter_secure_storage`, `uuid`, `intl`, `flutter_spinkit` và 4 font `Roboto`.
  - Cấp quyền `INTERNET` và bật `usesCleartextTraffic` trong `AndroidManifest.xml`.
  - Cấu hình Theme Navy `#143C64` chuẩn, typography Roboto.
  - Xây dựng `StorageService` (lưu và sinh UUID v4 cho `device_id`) và `ApiClient` (Dio interceptor tự động gắn `X-Device-ID`, `X-App-Version`, timeout 60s).
  - Hoàn thiện giao diện `HomeView` dạng tích hợp: thanh 3 nút thao tác nhanh (Dán chữ, Quét ảnh, Chọn tệp), khung soạn thảo kèm bộ đếm ký tự (200 - 30.000 ký tự), bộ chọn độ dài (Ngắn, Vừa, Chi tiết), nút tóm tắt tự động vô hiệu hoá khi đang xử lý / chưa đủ ký tự.
  - Đã bỏ dòng lưu ý quyền riêng tư.
  - `flutter analyze` và `flutter test` đạt 100% không lỗi.

## Đang dở / bước tiếp theo
- 1A.2: `utils/text_utils.py` + `validators.py` (Backend): NFC, strip, kiểm tra 200–30.000, kiểm tra header `X-Device-ID`/`X-App-Version`.

## Quyết định đã chốt khi code
- Cấu hình `sys.path` và `pytest.ini` (`pythonpath = . ..`) để code backend có thể chạy mượt mà từ cả thư mục `backend/` lẫn thư mục gốc repo.
- Format response và error code tuân thủ nghiêm ngặt mục 2 và mục 5 trong `docs/API.md`.
- Cấu hình `app.json.ensure_ascii = False` để JSON trả về tiếng Việt UTF-8 trực tiếp, không bị mã hoá thành `\u...`.
- Thiết kế giao diện `HomeView` dạng 1 màn hình tích hợp (Unified Screen), đặt 3 nút thao tác trên ribbon phía trên khung soạn thảo.
- Đã loại bỏ dòng chữ lưu ý quyền riêng tư theo yêu cầu.

## Lỗi đã biết / việc cần nhớ
- (chưa có)

## Cách chạy và test hiện tại
- Chạy backend:
  ```bash
  cd backend
  .\.venv\Scripts\activate   # Windows
  python app.py
  ```
- Test backend:
  ```bash
  cd backend
  pytest
  ```
- Kiểm tra mã nguồn Flutter:
  ```bash
  cd mobile
  flutter analyze
  flutter test
  ```
- Chạy app Flutter trên thiết bị/emulator:
  ```bash
  cd mobile
  flutter run
  ```
