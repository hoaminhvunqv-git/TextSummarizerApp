# PHASES.md — Lộ trình thi công & Tiêu chí hoàn thành (Definition of Done)

> Mỗi lượt làm việc với AI: đưa `CLAUDE.md` + `SPEC.md` + `API.md` + **chỉ phần giai đoạn hiện tại** trong file này.
> Mỗi bước nhỏ: AI lập kế hoạch → bạn duyệt → code → test → commit.

## Bước 0 — Chuẩn bị (trước khi code)
- [ ] Tạo repo Git, **commit đầu tiên chứa `.gitignore`** (`.env`, `*.jks`, `key.properties`, `.venv/`, `build/`, `__pycache__/`).
- [ ] Lấy Gemini API key; tạo `.env` (không commit) và `.env.example`.
- [ ] Sinh `ENCRYPTION_KEY` (32 byte base64) và `JWT_SECRET`; **backup `ENCRYPTION_KEY` vào trình quản lý mật khẩu**.
- [ ] Chuẩn bị `testdata/` theo SPEC mục 9.
- [ ] Chuẩn bị `app_icon.png` 1024×1024, font Roboto.
- [ ] Cài Flutter, Python 3.11+, Android SDK. Có điện thoại Android hoặc emulator.

---

## Giai đoạn 1 — Tóm tắt văn bản (không DB)

### 1A. Backend chạy bằng curl
1. Khung Flask: `app.py`, `config.py`, `utils/responses.py`, `utils/errors.py`, error handler toàn cục, `GET /health`, `GET /api/v1/config`.
2. `utils/text_utils.py` + `validators.py`: NFC, strip, kiểm tra 200–30.000, kiểm tra header `X-Device-ID`/`X-App-Version`.
3. `services/tfidf_service.py` (fallback) — viết **trước** Gemini để có đường chạy ngay.
4. `services/gemini_service.py` theo `PROMPTS.md` (JSON schema, timeout 15s, retry 1 lần, fallback).
5. `POST /api/v1/summaries` (chưa lưu DB, `id: null`), `Flask-Limiter` theo IP.
6. `POST /api/v1/files/extract` (TXT/DOCX/PDF, 10MB, `PDF_SCANNED`).
7. `pytest`: validate độ dài/NFC; TF-IDF trả đúng số câu và giữ thứ tự.

### 1B. Flutter
1. Khung app, theme (Navy `#143C64`, Roboto), `flutter_launcher_icons`.
2. `core/api_client.dart` (Dio): gắn `X-Device-ID` (uuid lưu secure storage), `X-App-Version`; timeout ≥ 60s; thông báo "Đang đánh thức máy chủ..." sau 8s; xử lý lỗi → SnackBar.
3. `AndroidManifest.xml`: **thêm quyền INTERNET**, quyền camera nếu cần; `minSdkVersion` theo yêu cầu của ML Kit (≥ 21, kiểm tra README package).
4. HomeView 1 tab: Dán chữ / Quét ảnh (OCR, có ô sửa) / Chọn file (extract → ô sửa). Chọn độ dài Ngắn/Vừa/Dài. Hiển thị kết quả + Copy/Chia sẻ.
5. Nút gửi bị vô hiệu hóa khi đang xử lý.

### 1C. Nối và kiểm thử
Chạy bộ `testdata/`; **kiểm thử OCR tiếng Việt** qua Gemini Vision API (`ocr_vi.jpg`).

### ✅ DoD Giai đoạn 1
- [ ] curl: `en_250.txt` → 201, `language=en`, `source=gemini`.
- [ ] curl: `vi_500.txt` → bản tóm tắt tiếng Việt, đúng định dạng (1 đoạn văn duy nhất).
- [ ] curl: `short_100.txt` → 400 `TEXT_TOO_SHORT`; `long_31000.txt` → 400 `TEXT_TOO_LONG`.
- [ ] Đặt sai `GEMINI_API_KEY` → vẫn 201 với `source=tfidf`.
- [ ] `injection.txt` → vẫn ra bản tóm tắt bình thường.
- [ ] Upload: `scanned.pdf` → `PDF_SCANNED`; `big_11mb.pdf` → `FILE_TOO_LARGE`; DOCX/TXT/PDF thường → trích xuất đúng.
- [ ] App (debug trên máy thật): dán chữ, quét ảnh (sửa được), chọn file → đều ra kết quả; lỗi hiển thị đúng message.
- [ ] Không có secret nào trong git (`git log -p | grep -i key` sạch); `pytest` xanh.

---

## Giai đoạn 2 — Lịch sử, mã hóa, quota (PostgreSQL)

1. Tạo DB Neon/Supabase, `DATABASE_URL` (có `sslmode=require`) vào `.env`.
2. `database/db.py` (ThreadedConnectionPool), `database/migrate.py`, chép `schema.sql` → `migrations/001_init.sql`, chạy migrate.
3. `services/crypto_service.py` AES-256-GCM + `pytest` round-trip (nonce khác nhau mỗi lần, sai key → lỗi).
4. `services/quota_service.py`: đặt chỗ nguyên tử + hoàn lại (SPEC 5.5), múi giờ `Asia/Ho_Chi_Minh`. `GET /usage`.
5. Cập nhật `POST /summaries`: đặt chỗ quota → xử lý → lưu bản ghi mã hóa (`original_length`, `source`) → hoàn lại quota nếu lỗi.
6. `GET /summaries` (phân trang), `GET /summaries/{id}`, `DELETE /summaries/{id}` — **có kiểm tra quyền sở hữu** (device/user), không thuộc → `NOT_FOUND`.
7. Flutter: HistoryView (pull-to-refresh, empty state, xóa), SummaryDetailView, hiển thị lượt còn lại.

### ✅ DoD Giai đoạn 2
- [ ] Xem trực tiếp bảng `summaries` trên dashboard: các cột `*_enc` là chuỗi base64 khó đọc, không có plaintext.
- [ ] Tạo bản tóm tắt → xuất hiện trong lịch sử với nội dung giải mã đúng.
- [ ] Đổi `X-Device-ID` khác → **không** thấy/đọc được/xóa được bản ghi của device cũ (404).
- [ ] Gửi 21 lần → lần 21 trả `QUOTA_EXCEEDED`; request lỗi (ví dụ quá ngắn) **không** làm tăng số lượt; bấm 2 request song song không vượt quota.
- [ ] Xóa 1 bản tóm tắt → biến mất khỏi DB.
- [ ] Log server không chứa nội dung văn bản.
- [ ] `pytest` (crypto, validators) xanh.

---

## Giai đoạn 3 — Quiz

1. Hàm tính `N = clamp(floor(len/130), 3, 10)` + `pytest` (400→3, 650→5, 1300→10, 5000→10).
2. `gemini_service.generate_quiz` theo `PROMPTS.md`: validate JSON, xáo trộn đáp án, tính lại `correct_index`, retry 1 lần.
3. `POST /summaries/{id}/quizzes` (đặt chỗ quota QUIZ, hoàn lại nếu lỗi), `GET /summaries/{id}/quizzes`, `GET /quizzes/{id}`.
4. `POST /quizzes/{id}/attempts` (server tự chấm), `GET /quizzes/{id}/attempts`.
5. Flutter QuizView: từng câu, chọn A–D, hiện đúng/sai + giải thích ngay, màn kết quả/điểm thang 10, nút làm lại, nút "Tạo Quiz" ở chi tiết tóm tắt.

### ✅ DoD Giai đoạn 3
- [ ] Văn bản gốc < 400 ký tự → `QUIZ_TEXT_TOO_SHORT`, không tốn quota.
- [ ] Văn bản ~650 ký tự → đúng 5 câu; văn bản ≥ 1300 → 10 câu; mỗi câu 4 đáp án khác nhau.
- [ ] Vị trí đáp án đúng phân bố ngẫu nhiên giữa A–D qua nhiều lần tạo.
- [ ] Tắt/sai Gemini key → quiz trả `AI_UNAVAILABLE` (503) + quota được hoàn lại; app hiện thông báo thân thiện.
- [ ] Nộp bài: sửa tay điểm trong request không ảnh hưởng (server tự tính); điểm lưu đúng thang 10.
- [ ] Xóa bản tóm tắt → quiz/câu hỏi/lượt làm liên quan bị xóa theo.

---

## Giai đoạn 4 — Tài khoản, OTP, Deploy, APK

1. `utils/auth_utils.py`: JWT HS256 7 ngày, decorator xác định chủ thể (JWT ưu tiên, sau đó device).
2. `services/email_service.py` (Brevo REST API, người gửi đã xác minh), `services/auth_service.py` (bcrypt, OTP bcrypt, `secrets`).
3. Các endpoint `/auth/*` theo `API.md`: giới hạn OTP (5 lần sai, 60s gửi lại, 5 phút hiệu lực), **lazy cleanup** OTP.
4. Gộp dữ liệu khách khi `verify-otp`/`login` (SPEC 5.7) trong 1 transaction.
5. Flutter: AuthView (Đăng ký, nhập OTP, Đăng nhập, Quên mật khẩu), `AuthProvider`, lưu JWT trong secure storage, interceptor tự gắn JWT và xử lý 401, nút Đăng xuất.
6. Deploy backend lên Render: `render.yaml`/Start Command `gunicorn app:app --workers 1 --threads 4`, biến môi trường, `/health`. Kiểm tra `DATABASE_URL` có `sslmode=require`.
7. Flutter: đặt `baseUrl` = URL Render (HTTPS). Ký APK (keystore, `key.properties` **không commit**), `minSdkVersion`, xác nhận quyền INTERNET trong manifest, rồi `flutter build apk --release --split-per-abi`.
8. Kiểm tra `/config` + `min_app_version` (426 khi app cũ).

### ✅ DoD Giai đoạn 4
- [ ] Đăng ký → nhận OTP email → xác thực → vào app; nhập sai 5 lần → khóa, phải xin mã mới; mã sau 5 phút → `OTP_EXPIRED`.
- [ ] Bảng `otp_codes` không còn bản ghi hết hạn/đã dùng sau khi thực hiện các thao tác OTP mới.
- [ ] Khách tạo 2 bản tóm tắt → đăng ký/đăng nhập → 2 bản tóm tắt xuất hiện trong tài khoản (`user_id` được cập nhật).
- [ ] Đăng nhập trên máy thứ 2 → thấy cùng lịch sử; người dùng B không truy cập được dữ liệu người dùng A.
- [ ] `forgot-password` với email không tồn tại → vẫn 200; reset mật khẩu thành công và đăng nhập được bằng mật khẩu mới.
- [ ] **APK release** cài trên máy thật (không cắm cáp debug) → gọi được API Render; lần đầu có thể chậm (cold start) nhưng app hiển thị "Đang đánh thức máy chủ...".
- [ ] APK được ký, không chứa secret (Gemini key, JWT secret chỉ ở server).
- [ ] Bộ `testdata/` chạy lại toàn bộ trên bản production vẫn đạt.

---

## Quy trình mỗi bước (nhắc lại)
1. Dán yêu cầu: "Làm Giai đoạn X, bước Y. Lập kế hoạch + liệt kê file sẽ sửa trước, chưa viết code."
2. Duyệt kế hoạch → AI viết code → bạn chạy theo "cách test" AI đưa ra.
3. Lỗi → dán **nguyên văn log/stack trace** + file liên quan.
4. Đạt → `git commit`. Hết giai đoạn → đối chiếu DoD, gắn tag (`v0.1-phase1`...).
