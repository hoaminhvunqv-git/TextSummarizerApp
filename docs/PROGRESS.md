# PROGRESS.md

> AI cập nhật file này sau MỖI bước xong, trước khi đề xuất commit.

## Đang ở
Giai đoạn 1A — Bước 1A.6 đã xong. Chuẩn bị bước 1C (nối Flutter với backend và đánh giá OCR tiếng Việt).

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
  - Thêm nút "Chia sẻ" bên cạnh nút "Sao chép" trong màn kết quả tóm tắt (dùng `share_plus` package).
  - Thay nút icon "Xóa nội dung" nhỏ bằng nút ribbon "Xóa tất cả" có nhãn rõ ràng, chỉ hiện khi ô soạn thảo có nội dung.
- Bước 1A.2 (Text utils & Validators Backend):
  - Xây dựng `backend/utils/text_utils.py`: Chuẩn hóa Unicode NFC, đếm ký tự thực tế, tách câu regex tiếng Việt/Anh, nhận diện ngôn ngữ ưu thế (`vi`/`en`).
  - Xây dựng `backend/utils/validators.py`: Validate độ dài 200–30.000 ký tự (`TEXT_TOO_SHORT`, `TEXT_TOO_LONG`), validate tham số `length` (`short`, `medium`, `long`), validate `X-Device-ID` chuẩn UUID v4 (`INVALID_DEVICE_ID`), validate `X-App-Version` so sánh phiên bản semver với `MIN_APP_VERSION` (HTTP 426 `UPDATE_REQUIRED`), và decorator `@require_device_and_version`.
  - Tạo `backend/tests/test_validators.py` kiểm thử toàn diện với bộ `testdata/` (`short_100.txt`, `long_31000.txt`, `vi_500.txt`, `en_250.txt`, `emoji.txt`). Toàn bộ 13 tests trong `pytest` đạt 100% xanh.
- Bước 1A.3 (TF-IDF Fallback Service):
  - Thêm `scikit-learn>=1.3.0` vào `backend/requirements.txt`.
  - Xây dựng `backend/services/tfidf_service.py`: Thuật toán tóm tắt trích xuất câu bằng TF-IDF, lọc top-k câu theo tỷ lệ `short` (~15%), `medium` (~25%), `long` (~40%). Giữ nguyên thứ tự câu gốc ban đầu (SPEC 5.6). Sinh `title` (câu đầu <= 60 ký tự), `description` (120 ký tự đầu), `summary`, `language`, và `source="tfidf"`.
  - Xây dựng `backend/tests/test_tfidf.py` kiểm thử tóm tắt tiếng Việt, tiếng Anh, bảo toàn thứ tự câu gốc, và tỷ lệ số câu theo độ dài. Toàn bộ 18 tests trong `pytest` đạt 100% xanh trong 1.4s.
- Bước 1A.4 (Gemini Service):
  - Thêm `google-genai>=1.0.0` vào `backend/requirements.txt`.
  - Xây dựng `backend/services/gemini_service.py`: gọi Gemini theo đúng `docs/PROMPTS.md` (system instruction tách biệt, bọc nội dung trong `<document>...</document>` để chống prompt injection, `response_mime_type="application/json"` + `response_schema`, `temperature=0.3`, timeout 15s qua `http_options`).
  - Kiểm tra JSON trả về: đủ 4 trường `language`/`title`/`description`/`summary`, `language` ∈ {vi, en}, không rỗng; cắt `title` ≤ 120 ký tự, `description` ≤ 300 ký tự. Trả kèm `source="gemini"` và `original_length`.
  - Retry 1 lần (`GEMINI_MAX_RETRY`), hết retry vẫn lỗi → tự động fallback sang `TfidfService.summarize`. Tóm tắt không bao giờ trả `AI_UNAVAILABLE`.
  - Client Gemini là singleton, có `set_client()` để mock trong unit test.
  - Xây dựng `backend/tests/test_gemini.py`: fallback khi không có API key, mock thành công, retry lần 2 thành công, hết retry → fallback, và 1 test gọi API thật kiểm tra phòng thủ prompt injection với `injection.txt`.
  - Toàn bộ 22 tests trong `pytest` đạt 100% xanh trong 2.23s (test gọi API thật đã được tách riêng, xem mục "Cách chạy và test").
- Bước 1A.5 (Endpoint tóm tắt + chống spam IP):
  - Thêm `Flask-Limiter>=3.5.0` vào `backend/requirements.txt` (bản cài thực tế 4.1.1).
  - Tạo `backend/extensions.py` chứa `limiter` khởi tạo chưa gắn app để routes import được mà không gây import vòng với `app.py`; `app.py` gọi `limiter.init_app(app)`.
  - Tạo `backend/routes/summary_routes.py`: `POST /api/v1/summaries` → `@require_device_and_version` → `validate_summary_input` → `GeminiService.summarize` → 201. Trả `id: null`, `original_length` sau NFC, `created_at` offset `+07:00`, `usage` gồm 2 trường `null`.
  - `@limiter.exempt` cho `/health` để Render ping không bị đếm. Giới hạn mặc định 30 request/phút/IP, vượt → 429 `RATE_LIMITED` (handler 429 có sẵn trong `app.py`).
  - Thêm `RATE_LIMIT_PER_MINUTE`, `RATELIMIT_ENABLED`, `RATELIMIT_STORAGE_URI` vào `config.py` và `.env.example`.
  - Tạo `backend/tests/test_summary_routes.py` (20 tests, mock `GeminiService` nên không tốn quota): 201 vi/en, chuyển tiếp `length`, mặc định `medium`, `TEXT_TOO_SHORT`/`TEXT_TOO_LONG`, `VALIDATION_ERROR`, `INVALID_DEVICE_ID`, `UPDATE_REQUIRED`, fallback tfidf, injection, emoji, 429 theo IP và `/health` được exempt. Toàn bộ **42 tests xanh trong 2.19s**.
  - Đã kiểm thử bằng curl thật trên server dev: `vi_500` → 201 `source=gemini` `language=vi` (đoạn + 4 gạch đầu dòng); `en_250` → 201 `source=gemini` `language=en`; `injection.txt` → 201 vẫn tóm tắt bình thường, không bị lừa; `short_100` → 400 `TEXT_TOO_SHORT`; `long_31000` → 400 `TEXT_TOO_LONG`; thiếu `X-Device-ID` → 400 `INVALID_DEVICE_ID`; `X-App-Version: 0.9.0` → 426 `UPDATE_REQUIRED`; request thứ 31 trong 1 phút → 429 `RATE_LIMITED`; 35 request `/health` đều 200; chạy server với key sai → vẫn 201 `source=tfidf` trong 0.65s.
- Bước 1A.6 (Trích xuất văn bản từ file):
  - Thêm `python-docx>=1.1.0` và `pypdf>=4.0.0` vào `backend/requirements.txt` (bản cài thực tế 1.2.0 và 7.0.0).
  - Thêm `MAX_CONTENT_LENGTH = MAX_FILE_MB * 1024 * 1024` vào `config.py` để Flask tự ném 413 khi file vượt 10MB (handler 413 có sẵn trong `app.py` đổi thành `FILE_TOO_LARGE`).
  - Xây dựng `backend/services/file_service.py`: TXT thử 4 encoding theo thứ tự `utf-8` → `utf-8-sig` → `cp1258` → `latin-1` (SPEC 5.2); DOCX lấy cả paragraph và nội dung ô bảng (`| ` phân cách hàng); PDF dùng `pypdf.PdfReader`, nếu không trích được chữ hoặc file lỗi → `PDF_SCANNED`. Chuẩn hóa NFC + strip trước khi trả về.
  - Xây dựng `backend/routes/file_routes.py`: `POST /api/v1/files/extract` nhận multipart field `file`, `@require_device_and_version`, trả `{text, char_count, filename}`. Không chặn tối thiểu 200 ký tự (API.md không liệt kê `TEXT_TOO_SHORT`), chỉ chặn tối đa 30.000. Tên file giữ nguyên dấu tiếng Việt (không dùng `secure_filename` vì không ghi xuống đĩa).
  - Tạo `backend/tests/test_file_routes.py` (13 tests) dùng thẳng bộ `testdata/` thật, không cần mock: `sample.txt`/`docx`/`pdf` → 200; `scanned.pdf` → 400 `PDF_SCANNED`; `big_11mb.pdf` → 413 `FILE_TOO_LARGE`; file `.doc` → 400 `FILE_UNSUPPORTED`; file rỗng → 400 `FILE_EMPTY`; `long_31000.txt` → 400 `TEXT_TOO_LONG`; `short_100.txt` → 200; thiếu `file` → 400 `VALIDATION_ERROR`; thiếu/sai header → 400/426; tên file tiếng Việt được giữ nguyên.
  - Toàn bộ **55 tests xanh trong 1.64s**.
  - Đã kiểm thử bằng curl multipart trên server dev: tất cả 7 file `sample.txt`/`docx`/`pdf`, `scanned.pdf`, `big_11mb.pdf`, `long_31000.txt`, `short_100.txt` đều trả đúng mã HTTP và `error_code` như dự kiến; nội dung trích ra tiếng Việt có dấu nguyên vẹn.
- Bước 1C.1 (Kết nối Chọn tệp với backend):
  - Thêm `file_picker: ^6.0.0` vào `mobile/pubspec.yaml`.
  - Xây dựng `extractFile()` trong `mobile/lib/providers/summary_provider.dart`: mở file picker chỉ cho chọn `.txt`/`.docx`/`.pdf`, gọi API `/api/v1/files/extract` với multipart form data, nhận text và hiển thị trong ô soạn thảo để người dùng có thể sửa trước khi tóm tắt. Xử lý lỗi DioException và hiển thị message tiếng Việt.
  - Cập nhật nút "Chọn tệp" trong `mobile/lib/views/home_view.dart` gọi `provider.extractFile()` và hiển thị SnackBar nếu có lỗi.
  - `flutter analyze` đạt 100% không lỗi.
- Bước 1C.2 (Thêm OCR với ML Kit on-device):
  - Thêm `google_mlkit_text_recognition: ^0.11.0` và `image_picker: ^1.0.0` vào `mobile/pubspec.yaml`.
  - Cấu hình `mobile/android/app/src/main/AndroidManifest.xml`: thêm quyền `CAMERA`, `READ_EXTERNAL_STORAGE` (maxSdkVersion 32), `READ_MEDIA_IMAGES`.
  - Cấu hình `mobile/android/app/build.gradle.kts`: đặt `minSdk = 21` (ML Kit yêu cầu tối thiểu 21).
  - Xây dựng `recognizeText(ImageSource source)` trong `mobile/lib/providers/summary_provider.dart`: chọn ảnh từ camera hoặc gallery, xử lý bằng ML Kit TextRecognizer với script Latin, trích xuất văn bản và hiển thị trong ô soạn thảo. Nếu không nhận diện được → hiển thị message gợi ý thử ảnh khác hoặc dùng Phương án B.
  - Cập nhật nút "Quét ảnh" trong `mobile/lib/views/home_view.dart`: hiện bottom sheet chọn "Chụp ảnh" hoặc "Chọn từ thư viện", sau đó gọi `provider.recognizeText()` với ImageSource tương ứng.
  - `flutter analyze` đạt 100% không lỗi.

## Đang dở / bước tiếp theo
- 1C.3: Triển khai Gemini Vision OCR (thay thế ML Kit on-device) và kiểm thử với `ocr_vi.jpg`.
- 1C.4: Kiểm thử end-to-end trên máy Android thật (build debug APK, test 3 luồng nhập liệu, test các ca lỗi).

## Thay đổi thiết kế (2026-11-07)
- **OCR: ML Kit on-device → Gemini Vision API**
  - Lý do: ML Kit Latin script không chính xác cho tiếng Việt (sai dấu nhiều, tự xuống dòng vô lý).
  - Gemini Vision hiểu ngữ cảnh tiếng Việt tốt hơn, ít sai dấu.
  - Chi phí: ~$0.0016/lượt OCR, free tier đủ cho 50-100 lượt/ngày.
  - Rate limit riêng: 20 lượt OCR/ngày/IP (không trừ vào quota tóm tắt).
  
- **Định dạng tóm tắt: Đoạn văn + Bullet points → Chỉ đoạn văn**
  - Lý do: User yêu cầu (Plan A) - chỉ trả về 1 đoạn văn tóm tắt, không có 3-5 ý chính riêng.
  - Đã cập nhật prompt Gemini trong PROMPTS.md mục 1.
  - Ảnh hưởng: SPEC.md mục 1.2, PROMPTS.md mục 1, PHASES.md DoD GĐ1.

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
- Giảm timeout Gemini AI từ 30s xuống 15s để tối ưu tốc độ phản hồi cho người dùng, cập nhật đồng bộ toàn bộ tài liệu dự án (`SPEC.md`, `PROMPTS.md`, `PHASES.md`, `PROGRESS.md`, `backend/.env.example`, `backend/config.py`).
- Không log `str(e)` khi gọi Gemini thất bại, chỉ log `type(e).__name__`: thông báo lỗi của SDK có thể chứa lại nội dung văn bản người dùng (CLAUDE.md cấm log nội dung).
- Tách test gọi Gemini API thật sang marker `live` trong `pytest.ini` và mặc định loại trừ (`addopts = -m "not live"`) để `pytest` thường không tốn quota và chạy nhanh (75s → 2.2s).
- Giữ trường `usage` trong response GĐ1 với giá trị `null` (không bỏ, không trả hằng 20/20): cùng nguyên tắc "định nghĩa đủ cấu trúc, phần chưa dùng để NULL" như `schema.sql` làm với `user_id`, và giống cách `API.md` đã quy định `id = null` ở GĐ1. Sang GĐ2 chỉ điền giá trị, không phải sửa model Dart hay UI.
- `created_at` dùng `timezone(timedelta(hours=7))` thay vì `ZoneInfo("Asia/Ho_Chi_Minh")`: Việt Nam không có DST nên kết quả y hệt, tránh phải thêm package `tzdata` trên Windows (ngoài danh sách SPEC 2.2).
- Đặt `limiter` trong `extensions.py` thay vì `app.py` để routes import được, tránh import vòng.
- Đổi model mặc định sang `gemini-3.5-flash`. Kiểm tra qua `models.list()` ngày 2026-11-07: `gemini-2.5-flash` (default cũ) đã bị khai tử, trả **404 NOT_FOUND**; `gemini-3.7-flash` và `gemini-3.8-flash` trả 504 hoặc rất chậm (prompt "Say OK" mất 38s); `gemini-3.5-flash` phản hồi 2.8s, `gemini-3.1-flash-lite` 1.1s.
- PDF hỏng hoặc bị mã hóa → trả `PDF_SCANNED` (không có mã lỗi riêng trong API.md; message *"Không thể đọc văn bản từ file này. Hãy dùng tính năng Quét ảnh OCR."* vẫn đúng với người dùng).
- DOCX trích cả nội dung ô bảng, phân cách hàng bằng ` | ` để tài liệu tiếng Việt dạng biểu mẫu không mất chữ.
- `filename` trả về giữ nguyên dấu tiếng Việt: chỉ lấy phần tên cuối (`Path(...).name`) và cắt 255 ký tự, không dùng `secure_filename` vì không ghi file xuống đĩa.

## Lỗi đã biết / việc cần nhớ
- Gemini thỉnh thoảng trả 503/504 tạm thời: trong lúc test, `vi_500` bị 503 hai lần liên tiếp nên fallback tfidf, gọi lại ngay sau đó thì 200 `source=gemini`. Fallback hoạt động đúng SPEC 5.6, nhưng cần chạy lại vài lần khi đối chiếu DoD `source=gemini`, đừng kết luận sai là lỗi code.
- Model Gemini 3.x mặc định bật "thinking" nên dễ chậm; chưa thêm `thinking_config` vì `gemini-3.5-flash` đã đủ nhanh (~8–12s cho văn bản 250–500 ký tự). Nếu sau này gặp văn bản 30.000 ký tự vượt timeout 15s thì cân nhắc lại.

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
  .\.venv\Scripts\pytest -v          # 22 tests, không gọi API thật
  .\.venv\Scripts\pytest -m live -v  # chỉ test gọi Gemini thật (tốn quota, cần GEMINI_API_KEY trong .env)
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
- Kiểm thử endpoint tóm tắt bằng curl (Git Bash, chạy từ `backend/`):
  ```bash
  # Tạo body JSON từ testdata (Windows: ghi vào thư mục temp, không có /tmp)
  ./.venv/Scripts/python -c "
  import json, pathlib, tempfile
  d = pathlib.Path(tempfile.gettempdir())/'tsa_curl'; d.mkdir(exist_ok=True)
  for n in ['vi_500','en_250','short_100','long_31000','injection']:
      t = pathlib.Path('../testdata/'+n+'.txt').read_text(encoding='utf-8')
      (d/(n+'.json')).write_text(json.dumps({'text':t,'length':'medium'}, ensure_ascii=False), encoding='utf-8')
  print(d.as_posix())"

  D=C:/Users/X/AppData/Local/Temp/tsa_curl
  curl -s -X POST http://localhost:5000/api/v1/summaries \
    -H "Content-Type: application/json" \
    -H "X-Device-ID: 3f2504e0-4f89-41d3-9a0c-0305e82c3301" \
    -H "X-App-Version: 1.0.0" -d @"$D/vi_500.json"
  ```
  Mong đợi: 201, `data.source=gemini`, `data.language=vi`, `id=null`, `usage` gồm 2 trường `null`.
  Test fallback: chạy server khác cổng với key sai — `PORT=5001 GEMINI_API_KEY=sai python app.py` → vẫn 201 nhưng `source=tfidf`.
  Lưu ý giới hạn 30 request/phút/IP khi curl nhiều lần liên tiếp (nghỉ 1 phút hoặc đặt `RATELIMIT_ENABLED=0`).
