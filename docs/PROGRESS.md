# PROGRESS.md

> AI cập nhật file này sau MỖI bước xong, trước khi đề xuất commit.

## Đang ở
Giai đoạn 1A — Bước 1A.3 đã xong. Chuẩn bị bước 1A.4 (services/gemini_service.py).

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
  - Nâng cấp UI/UX theo yêu cầu:
    + Thêm dòng chú thích: "Hỗ trợ tóm tắt văn bản Tiếng Việt & Tiếng Anh" phía trên hàng nút công cụ.
    + Nút "Dán chữ" dán trực tiếp nội dung văn bản từ clipboard vào ô soạn thảo, thông báo nếu clipboard rỗng.
    + Đổi nhãn độ dài từ "Chi tiết" thành "Dài" (giữ nguyên tham số `long`).
    + Tích hợp tính năng "Xem thêm ˅ / Thu gọn ˄" cho ô soạn thảo khi vượt quá 8 dòng, kèm ShaderMask gradient fade ở đáy khi thu gọn.
    + Cập nhật hintText ô soạn thảo: "Nhận tóm tắt từ 200 đến 30.000 ký tự".
  - `flutter analyze` đạt 100% không lỗi.
- Bước 1A.2 (Text utils & Validators Backend):
  - Xây dựng `backend/utils/text_utils.py`: Chuẩn hóa Unicode NFC, đếm ký tự thực tế, tách câu regex tiếng Việt/Anh, nhận diện ngôn ngữ ưu thế (`vi`/`en`).
  - Xây dựng `backend/utils/validators.py`: Validate độ dài 200–30.000 ký tự (`TEXT_TOO_SHORT`, `TEXT_TOO_LONG`), validate tham số `length` (`short`, `medium`, `long`), validate `X-Device-ID` chuẩn UUID v4 (`INVALID_DEVICE_ID`), validate `X-App-Version` so sánh phiên bản semver với `MIN_APP_VERSION` (HTTP 426 `UPDATE_REQUIRED`), và decorator `@require_device_and_version`.
  - Tạo `backend/tests/test_validators.py` kiểm thử toàn diện với bộ `testdata/` (`short_100.txt`, `long_31000.txt`, `vi_500.txt`, `en_250.txt`, `emoji.txt`). Toàn bộ 13 tests trong `pytest` đạt 100% xanh.
- Bước 1A.3 (TF-IDF Fallback Service):
  - Thêm `scikit-learn>=1.3.0` vào `backend/requirements.txt`.
  - Xây dựng `backend/services/tfidf_service.py`: Thuật toán tóm tắt trích xuất câu bằng TF-IDF, lọc top-k câu theo tỷ lệ `short` (~15%), `medium` (~25%), `long` (~40%). Giữ nguyên thứ tự câu gốc ban đầu (SPEC 5.6). Sinh `title` (câu đầu <= 60 ký tự), `description` (120 ký tự đầu), `summary`, `language`, và `source="tfidf"`.
  - Xây dựng `backend/tests/test_tfidf.py` kiểm thử tóm tắt tiếng Việt, tiếng Anh, bảo toàn thứ tự câu gốc, và tỷ lệ số câu theo độ dài. Toàn bộ 18 tests trong `pytest` đạt 100% xanh trong 1.4s.

## Đang dở / bước tiếp theo
- 1A.4: `services/gemini_service.py` (kết nối AI Gemini theo `docs/PROMPTS.md`, JSON schema, timeout 30s, retry 1 lần, tự động fallback sang TF-IDF service).

## Quyết định đã chốt khi code
- Cấu hình `sys.path` và `pytest.ini` (`pythonpath = . ..`) để code backend có thể chạy mượt mà từ cả thư mục `backend/` lẫn thư mục gốc repo.
- Format response và error code tuân thủ nghiêm ngặt mục 2 và mục 5 trong `docs/API.md`.
- Cấu hình `app.json.ensure_ascii = False` để JSON trả về tiếng Việt UTF-8 trực tiếp, không bị mã hoá thành `\u...`.
- Thiết kế giao diện `HomeView` dạng 1 màn hình tích hợp (Unified Screen), đặt 3 nút thao tác trên ribbon phía trên khung soạn thảo.
- Đã loại bỏ dòng chữ lưu ý quyền riêng tư theo yêu cầu.
- Chuẩn hóa Unicode NFC và strip trước khi tính độ dài len() theo đúng quy tắc tại SPEC 5.1 và CLAUDE.md.
- So sánh phiên bản semver chuẩn `(major, minor, patch)` cho header `X-App-Version`.
- TF-IDF extractive summarization: sắp xếp lại các câu trích xuất theo chỉ số gốc ban đầu để câu văn tóm tắt luôn xuôi dòng ngữ cảnh.
- Không áp dụng `stop_words='english'` khi ngôn ngữ là tiếng Việt để tránh lọc sai hoặc ảnh hưởng đến từ tiếng Việt.

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
  .\.venv\Scripts\pytest -v
  ```
- Kiểm tra mã nguồn Flutter:
  ```bash
  cd mobile
  flutter analyze
  ```
- Chạy app Flutter trên thiết bị/emulator:
  ```bash
  cd mobile
  flutter run
  ```
