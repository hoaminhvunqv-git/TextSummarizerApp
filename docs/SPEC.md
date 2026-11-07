# SPEC.md — TextSummarizer AI (Đặc tả yêu cầu phần mềm v2)

> Nguồn sự thật duy nhất của dự án. Tài liệu đi kèm: `CLAUDE.md` (quy tắc cho AI), `API.md`, `PROMPTS.md`, `PHASES.md`, `schema.sql`.

---

## 1. Tổng quan

- **Tên:** TextSummarizer AI
- **Nền tảng:** **Android only** (Flutter/Dart) + Backend REST API (Python Flask) + PostgreSQL cloud.
- **Phương pháp:** AI-Assisted Incremental Development, chiến lược **Core-First** (cốt lõi trước, tài khoản sau).
- **Mục tiêu:**
  1. Tóm tắt văn bản Anh–Việt qua 3 cách nhập: dán chữ, quét ảnh OCR, tải file (TXT/DOCX/PDF).
  2. Lưu lịch sử tóm tắt, mã hóa dữ liệu trong DB.
  3. Tạo quiz trắc nghiệm ABCD để ôn tập.
  4. Tài khoản người dùng + xác thực OTP email (giai đoạn cuối).
- **Quy mô dự kiến:** ~2 người dùng, chạy 24/7 trên free tier.

### 1.1. Định nghĩa "tóm tắt Anh–Việt" (đã chốt)
- Hệ thống **tự nhận diện ngôn ngữ của văn bản đầu vào** (`vi` hoặc `en`) và **tóm tắt bằng chính ngôn ngữ đó**. Văn bản trộn ngôn ngữ: lấy ngôn ngữ chiếm ưu thế.
- **Không dịch.** Giá trị lưu vào cột `language`.
- Người dùng chọn độ dài tóm tắt: `short` / `medium` (mặc định) / `long` (tham số `length`).

### 1.2. Định dạng bản tóm tắt (đã chốt)
Một chuỗi văn bản gồm: 1 đoạn tóm tắt duy nhất (không có bullet points hay ý chính riêng).

| length | Độ dài đoạn tóm tắt (ước lượng) |
|---|---|
| short | ≤ 100 từ (~10% bản gốc) |
| medium | ≤ 200 từ (~20% bản gốc) |
| long | ≤ 350 từ (~30% bản gốc) |

### 1.3. Giới hạn đã biết (chấp nhận, KHÔNG tự "sửa")
- `Device_ID` mất khi gỡ app/xóa dữ liệu → quota reset, lịch sử khách cũ không truy cập được.
- Người dùng kỹ thuật có thể đổi `X-Device-ID` để lách quota. Lớp phụ: giới hạn theo IP.
- Văn bản được gửi **không mã hóa** tới Gemini (mã hóa AES chỉ áp dụng cho dữ liệu lưu trong DB). Gói miễn phí của Gemini API có thể dùng dữ liệu để cải thiện sản phẩm của Google (kiểm tra điều khoản hiện hành) → hiển thị 1 dòng lưu ý trong app.
- Dữ liệu mã hóa **không tìm kiếm được bằng SQL**; tìm kiếm lịch sử (nếu làm) chỉ thực hiện phía app sau khi tải về.
- Quiz **không có fallback** (TF-IDF không sinh được câu hỏi) → báo `AI_UNAVAILABLE`.
- Hạn mức free của Gemini tính theo **cả API key**, không theo từng người dùng.
- Lịch sử cần mạng (không cache offline).

---

## 2. Tech stack (đã chốt, không dùng "hoặc")

### 2.1. Mobile (Flutter)
| Mục đích | Package |
|---|---|
| HTTP | `dio` (HTTPS bắt buộc, interceptor) |
| Lưu bảo mật | `flutter_secure_storage` (JWT, Device_ID) |
| Sinh Device_ID | `uuid` |
| OCR | Gemini Vision API (gọi qua backend) |
| Chọn/chụp ảnh | `image_picker` |
| Chọn file | `file_picker`, `path_provider` |
| State | `provider` |
| Điều hướng | `Navigator` cơ bản (KHÔNG go_router) |
| Loading | `shimmer`, `flutter_spinkit` |
| Icon | `font_awesome_flutter`, `cupertino_icons` |
| Copy/Chia sẻ | `Clipboard` (có sẵn), `share_plus` |
| Định dạng ngày | `intl` |
| App icon (dev) | `flutter_launcher_icons` (trỏ `assets/images/app_icon.png`) |
| Font | **Roboto** (đóng gói trong `assets/fonts/`). Không dùng Segoe UI. |

### 2.2. Backend (Flask)
| Mục đích | Thư viện |
|---|---|
| Web | `Flask`, `Flask-Cors` (app mobile không cần CORS; chỉ bật nếu test web), `Flask-Limiter` |
| Chạy production | `gunicorn` (`--workers 1 --threads 4`, để Limiter lưu RAM vẫn đúng) |
| DB | **`psycopg2-binary`** + SQL thuần, `ThreadedConnectionPool`. Migration = file SQL đánh số + `database/migrate.py` |
| AI | `google-genai` (Gemini), `scikit-learn` (TF-IDF fallback) |
| Mã hóa | `cryptography` (**AES-256-GCM**), `bcrypt`, `PyJWT` |
| File | `python-docx`, **`pypdf`** (chọn 1 thư viện PDF) |
| Config | `python-dotenv` |
| Gửi email | **Brevo REST API** qua HTTPS (dùng `requests`). Không dùng SMTP vì free tier Render chặn các cổng SMTP — kiểm tra lại chính sách hiện hành |
| Test | `pytest` |

### 2.3. Hạ tầng
- **DB:** Neon , chuỗi kết nối có `sslmode=require`. **Không** dùng Postgres miễn phí của Render (có thời hạn).
- **API:** Render (HTTPS mặc định). Có `render.yaml` + `GET /health`.
- Local test: HTTPS qua Ngrok nếu cần.
- **Render free ngủ khi rảnh → cold start 30–60s.** Dio `connectTimeout`/`receiveTimeout` ≥ 60s; nếu request > 8s chưa phản hồi, hiện "Đang đánh thức máy chủ...".

---

## 3. Cấu trúc thư mục

```
TextSummarizerAI/
├── .gitignore                  # có .env, *.jks, key.properties, .venv, build/
├── CLAUDE.md
├── docs/                       # SPEC.md, API.md, PROMPTS.md, PHASES.md
├── testdata/                   # bộ dữ liệu test cố định (mục 9)
├── backend/
│   ├── app.py                  # entry point, đăng ký blueprint, error handler
│   ├── config.py               # đọc env: DATABASE_URL, GEMINI_API_KEY, GEMINI_MODEL, ENCRYPTION_KEY, JWT_SECRET, BREVO_API_KEY...
│   ├── .env                    # KHÔNG commit
│   ├── .env.example            # commit, chỉ có tên biến
│   ├── requirements.txt
│   ├── render.yaml
│   ├── routes/                 # summary_routes.py, quiz_routes.py, auth_routes.py, file_routes.py, system_routes.py
│   ├── services/               # gemini_service.py, tfidf_service.py, crypto_service.py,
│   │                           # file_service.py, quota_service.py, email_service.py, auth_service.py
│   ├── utils/                  # responses.py, errors.py, validators.py, text_utils.py, auth_utils.py
│   ├── database/
│   │   ├── db.py               # connection pool
│   │   ├── migrate.py          # chạy các file trong migrations/ chưa áp dụng
│   │   ├── schema.sql          # ảnh chụp schema tổng hợp (tham chiếu)
│   │   └── migrations/         # 001_init.sql, 002_...
│   └── tests/                  # test_validators.py, test_crypto.py, test_quiz_count.py, ...
└── mobile/
    ├── pubspec.yaml
    ├── assets/images/app_icon.png (1024x1024)
    ├── assets/fonts/Roboto-*.ttf
    └── lib/
        ├── main.dart
        ├── core/               # api_client.dart, constants.dart, storage_service.dart, theme.dart, text_utils.dart
        ├── models/             # summary_model.dart, quiz_model.dart, user_model.dart
        ├── providers/          # summary_provider.dart, quiz_provider.dart, auth_provider.dart
        ├── widgets/            # component dùng lại (SummaryCard, LoadingOverlay, EmptyState, ...)
        └── views/              # home_view, history_view, summary_detail_view, quiz_view, auth_view
```
> `ocr_service.py` ở backend **đã bỏ** vì OCR chạy trên thiết bị. Chỉ thêm lại nếu dùng phương án B (Gemini Vision, mục 5.3).

---

## 4. Thiết kế giao diện

- **Phong cách:** Modern Clean UI, tối giản, padding rộng, phù hợp cảm ứng.
- **Màu:**
  - Primary `#143C64` (header, nút chính, nền app icon)
  - Secondary `#2D5A87` (tab bar, icon phụ)
  - Background `#F4F6F9`
  - Card `#FFFFFF`, bo góc 12, `BoxShadow` nhẹ
  - Success `#28A745`, Error `#DC3545`, Warning `#FFC107` (**chữ trên nền Warning dùng màu tối**, không dùng chữ trắng)
- **Chữ:** Roboto. Title 18–20 Bold, Subtitle 14–16 SemiBold, Body 13–14 Regular.
- **Phản hồi:**
  - OCR/File: sau khi trích xuất, hiển thị ô văn bản **cho xem và sửa** trước khi bấm Tóm tắt.
  - Đang xử lý: Shimmer/Spinner + "Đang phân tích văn bản...". **Vô hiệu hóa nút gửi** trong lúc xử lý (chống bấm đúp tốn quota).
  - Lỗi: SnackBar màu theo mức độ + icon. Lỗi mạng/timeout có nút **Thử lại**.
  - **Empty state** cho Lịch sử ("Chưa có bản tóm tắt nào").
  - Hiển thị **số lượt còn lại** hôm nay (từ `GET /api/v1/usage`).
  - Màn kết quả có: **Copy**, **Chia sẻ**, **Tạo Quiz**, **Xóa**. Lịch sử có pull-to-refresh và xóa từng mục (vuốt hoặc menu).
- **Dòng lưu ý quyền riêng tư** ở màn Home (nội dung được gửi tới dịch vụ AI để xử lý).

---

## 5. Quy tắc nghiệp vụ

### 5.1. Văn bản đầu vào
- Chuẩn hóa **Unicode NFC**, `strip()`, rồi đếm bằng `len()` của Python (backend quyết định cuối; app chỉ kiểm tra sơ bộ).
- Tối thiểu **200**, tối đa **30.000** ký tự.
- Lỗi: `TEXT_TOO_SHORT` — *"Văn bản quá ngắn để tóm tắt. Hãy nhập ít nhất 200 ký tự."*; `TEXT_TOO_LONG` — *"Văn bản vượt quá giới hạn 30.000 ký tự. Vui lòng chia nhỏ nội dung."*

### 5.2. Tệp tải lên
- Cho phép `.txt`, `.docx`, `.pdf`, tối đa **10 MB** (`MAX_CONTENT_LENGTH`). File `.doc` cũ **không** hỗ trợ.
- Lỗi: `FILE_TOO_LARGE` (413) — *"Dung lượng file vượt quá 10MB."*; `FILE_UNSUPPORTED` (400).
- PDF không trích xuất được chữ (scan) → `PDF_SCANNED` — *"Không thể đọc văn bản từ file này. Hãy dùng tính năng Quét ảnh OCR."*
- Luồng: `POST /files/extract` trả text → app hiển thị cho xem/sửa → gọi `POST /summaries`.
- TXT: thử UTF-8, nếu lỗi thử `utf-8-sig`, `cp1258`, `latin-1`.

### 5.3. OCR
- Mặc định: ML Kit on-device (model Latin).
- **Phải test ngay ở Giai đoạn 1 với ảnh tiếng Việt có dấu.** Nếu độ chính xác dấu kém → **Phương án B**: app gửi ảnh (nén, ≤ 4MB) tới `POST /api/v1/ocr` (Gemini Vision, prompt ở `PROMPTS.md`); khi đó mới thêm `ocr_service.py`. Không tự chuyển sang phương án B nếu chưa được người dùng đồng ý.

### 5.4. Tạo Quiz (đã chốt)
- **Nguồn:** văn bản gốc của bản tóm tắt (giải mã từ `original_text_enc`); bản tóm tắt làm ngữ cảnh phụ.
- Điều kiện: độ dài văn bản gốc **≥ 400 ký tự** (dùng cột `original_length`), nếu không → `QUIZ_TEXT_TOO_SHORT`.
- **Số câu:** `N = clamp(floor(len / 130), 3, 10)`. Không còn "mặc định 5".
- Mỗi câu: 4 đáp án A–D khác nhau, **đúng 1** đáp án đúng, có giải thích ngắn. Ngôn ngữ câu hỏi = `language` của bản tóm tắt.
- Backend **kiểm tra** JSON Gemini trả về (đủ N câu, mỗi câu 4 đáp án không trùng, `correct_index` 0–3), **xáo trộn đáp án** và tính lại `correct_index` (Gemini hay đặt đáp án đúng ở vị trí cố định). JSON hỏng/thiếu: retry 1 lần, vẫn lỗi → `AI_UNAVAILABLE`.
- Một bản tóm tắt có thể tạo nhiều quiz (mỗi lần tốn 1 lượt quiz).
- API trả luôn `correct_index` và `explanation` (ứng dụng tự học, hiển thị đáp án ngay sau khi chọn). Khi nộp bài, backend **tính lại điểm** từ đáp án người dùng.
- **Điểm:** thang 10, làm tròn 1 chữ số: `score = correct / total * 10`.

### 5.5. Quota & định danh
- **20 tóm tắt/ngày** và **20 quiz/ngày** cho mỗi chủ thể.
- Chủ thể (`owner_key`): người đã đăng nhập → `u:<user_id>`; khách → `d:<device_id>`.
- Ngày tính theo múi giờ **Asia/Ho_Chi_Minh**.
- Cách tính (chống bấm đúp/race): **đặt chỗ nguyên tử** trước khi gọi AI (SQL `INSERT ... ON CONFLICT DO UPDATE ... WHERE count < limit RETURNING`), nếu xử lý **thất bại** (lỗi validate sau đặt chỗ, lỗi hệ thống, `AI_UNAVAILABLE` của quiz) thì **hoàn lại** 1 lượt. Thành công (kể cả bằng fallback TF-IDF) thì giữ.
- Hết quota: `QUOTA_EXCEEDED` (429) — *"Bạn đã dùng hết quota trong ngày. Vui lòng quay lại vào ngày mai."*
- Lưu trong **bảng DB `usage_quota`** (không dùng bộ nhớ RAM). `Flask-Limiter` chỉ chống spam theo IP (ví dụ 30 request/phút/IP; auth endpoints chặt hơn: 5/phút/IP).
- Header `X-Device-ID` (UUID v4) bắt buộc với mọi endpoint nghiệp vụ; sai định dạng → `INVALID_DEVICE_ID`.

### 5.6. Fallback tóm tắt
- Điều kiện chuyển sang TF-IDF: Gemini timeout (15s), lỗi mạng, hết hạn mức, bị chặn safety, trả rỗng, hoặc JSON hỏng sau 1 lần retry.
- Thuật toán: tách câu bằng regex (hỗ trợ dấu `.!?…` và xuống dòng), chấm điểm câu bằng TF-IDF, lấy top-k theo `length`, **giữ nguyên thứ tự gốc**. Không dùng stopword tiếng Anh cho tiếng Việt.
- `title` fallback = câu đầu cắt ≤ 60 ký tự; `description` = 120 ký tự đầu của bản tóm tắt. Phần "ý chính" có thể bỏ.
- Response luôn có `source: "gemini" | "tfidf"`.

### 5.7. Quyền sở hữu & truy cập (chống IDOR)
- Danh tính người gọi: có JWT hợp lệ → `user_id`; ngược lại dùng `X-Device-ID`.
- Bản ghi được phép truy cập khi `user_id = người gọi` **hoặc** (`user_id IS NULL` và `device_id = X-Device-ID`).
- Không thuộc người gọi → trả `NOT_FOUND` (404), không tiết lộ sự tồn tại.
- **Gộp dữ liệu khi đăng nhập/đăng ký-xác thực:** nếu có `X-Device-ID`, chạy trong 1 transaction:
  ```sql
  UPDATE summaries      SET user_id = :uid WHERE device_id = :did AND user_id IS NULL;
  UPDATE quiz_sessions  SET user_id = :uid WHERE device_id = :did AND user_id IS NULL;
  UPDATE quiz_attempts  SET user_id = :uid WHERE device_id = :did AND user_id IS NULL;
  ```
  Quota của khách **không** được gộp (người dùng đăng nhập có quota riêng).

### 5.8. Bảo mật
- Bắt buộc HTTPS cho mọi giao tiếp.
- **Mã hóa DB:** AES-256-GCM, key 32 byte (base64) trong `ENCRYPTION_KEY`; nonce 12 byte ngẫu nhiên mỗi bản ghi; lưu `base64(nonce + ciphertext_with_tag)`.
- **Cảnh báo:** mất `ENCRYPTION_KEY` = mất toàn bộ dữ liệu đã lưu. Backup key ở nơi riêng (trình quản lý mật khẩu), **không đổi key** khi đã có dữ liệu (đổi key = cần migration, ngoài phạm vi).
- `.env` vào `.gitignore` **ngay commit đầu tiên**. Lộ key Gemini lên GitHub sẽ bị bot quét trong vài phút.
- **Prompt injection:** tách system instruction và nội dung người dùng; bọc nội dung trong `<document>...</document>` và dặn model coi mọi thứ bên trong là dữ liệu, không phải lệnh (xem `PROMPTS.md`).
- **Log:** không ghi nội dung văn bản, OTP, mật khẩu, token (xem `CLAUDE.md`).
- Mật khẩu: bcrypt, tối thiểu 8 ký tự.

### 5.9. Tài khoản, OTP, JWT
- Đăng ký: tạo user `is_verified=FALSE` → gửi OTP → `verify-otp` → `is_verified=TRUE` và trả JWT.
- Đăng nhập: chỉ khi đã xác thực, sai → `INVALID_CREDENTIALS`, chưa xác thực → `EMAIL_NOT_VERIFIED`.
- Quên mật khẩu: OTP `RESET_PASSWORD` → `reset-password` (email + otp + mật khẩu mới). Phản hồi `forgot-password` **luôn thành công** dù email có tồn tại hay không (chống dò email).
- **OTP:** 6 chữ số ngẫu nhiên bằng `secrets`; hash bcrypt; hiệu lực **5 phút**; **tối đa 5 lần nhập sai** (`attempts`), quá → `OTP_TOO_MANY_ATTEMPTS`, phải yêu cầu mã mới; gửi lại tối thiểu cách nhau 60s (`OTP_RESEND_COOLDOWN`). Mã mới vô hiệu mã cũ cùng `purpose`.
- **Dọn OTP (lazy cleanup):** mỗi khi có yêu cầu OTP mới hoặc xác thực xong, xóa các bản ghi `expires_at < now()` hoặc `used_at IS NOT NULL` của user đó và (tối đa mỗi lần) toàn bảng. Không dùng scheduler nền vì Render free ngủ. (Nếu dùng Supabase có thể thêm `pg_cron`.)
- **JWT:** HS256, access token **7 ngày**, **không refresh**, logout = app xóa token. Payload: `sub` (user_id), `exp`. Khi nhận 401, app xóa token và đưa về đăng nhập.

### 5.10. Phiên bản API & cập nhật app
- Mọi endpoint dưới prefix **`/api/v1`**.
- App gửi header `X-App-Version`. `GET /api/v1/config` trả `min_app_version`; nếu app thấp hơn → HTTP 426 `UPDATE_REQUIRED` và app hiện "Vui lòng cập nhật".

### 5.11. Đồng bộ Dart ↔ Python
- App kiểm tra sơ bộ bằng `characters`/`runes` sau khi NFC, **không** coi là quyết định cuối. Backend trả lỗi nào thì hiển thị lỗi đó.

---

## 6. Cơ sở dữ liệu

Xem `schema.sql` (đã gồm index, `ON DELETE CASCADE`, check constraint). Điểm khác so với bản v1:

- Thống nhất `BIGSERIAL`/`BIGINT`.
- `summaries` thêm: `original_length`, `source`.
- `quiz_sessions`, `quiz_attempts` thêm `device_id`.
- `quiz_questions` thêm `position`. `quiz_attempts` thêm `correct_count`, `total_count`.
- `otp_codes` thêm `attempts`, `created_at`, `used_at`.
- Bảng mới: `usage_quota`, `schema_migrations`.
- Mọi bảng nghiệp vụ có `user_id` **NULLABLE** + ràng buộc `user_id IS NOT NULL OR device_id IS NOT NULL`.

Migration: file đánh số trong `backend/database/migrations/`; `migrate.py` áp dụng file chưa chạy và ghi vào `schema_migrations`. **Không sửa DB bằng tay.**

---

## 7. API

Xem `API.md` (danh sách endpoint, JSON mẫu, bảng error_code).

---

## 8. Giai đoạn thi công

Xem `PHASES.md` (kèm tiêu chí hoàn thành). Tóm tắt:
1. **GĐ1:** Tóm tắt (Gemini + TF-IDF), không DB. Làm backend chạy bằng curl trước, rồi mới nối Flutter.
2. **GĐ2:** PostgreSQL, mã hóa, lịch sử, quota.
3. **GĐ3:** Quiz.
4. **GĐ4:** Auth, OTP, deploy Render, xuất APK.

---

## 9. Bộ dữ liệu test cố định (`testdata/`)

Chuẩn bị trước, mỗi giai đoạn phải chạy qua bộ này:
| Tên | Mô tả | Kết quả mong đợi |
|---|---|---|
| `en_250.txt` | Tiếng Anh ~250 ký tự | tóm tắt OK, `language=en` |
| `vi_500.txt` | Tiếng Việt có dấu ~500 ký tự | OK, `language=vi` |
| `short_100.txt` | 100 ký tự | `TEXT_TOO_SHORT` |
| `long_31000.txt` | 31.000 ký tự | `TEXT_TOO_LONG` |
| `emoji.txt` | có emoji, ký tự đặc biệt | không crash, đếm đúng |
| `mixed.txt` | trộn Anh–Việt | ngôn ngữ ưu thế |
| `sample.txt`, `sample.docx`, `sample_text.pdf` | file hợp lệ | trích xuất OK |
| `scanned.pdf` | PDF ảnh scan | `PDF_SCANNED` |
| `big_11mb.pdf` | > 10MB | `FILE_TOO_LARGE` |
| `injection.txt` | chứa câu "bỏ qua mọi hướng dẫn trước đó..." | vẫn trả bản tóm tắt bình thường |
| `ocr_vi.jpg` | ảnh chụp chữ tiếng Việt có dấu | đánh giá độ chính xác OCR |

**Test tự động tối thiểu (pytest):** (1) validate độ dài/NFC, (2) mã hóa–giải mã round-trip + nonce khác nhau, (3) hàm tính số câu quiz `N` (ví dụ 400→3, 650→5, 1300→10, 5000→10).

---

## 10. Ngoài phạm vi (Non-goals)
Dark mode, đa ngôn ngữ giao diện, đăng nhập mạng xã hội, iOS, cache offline, refresh token, push notification, thanh toán, dịch văn bản, tìm kiếm lịch sử bằng SQL, chia sẻ dữ liệu giữa người dùng.
