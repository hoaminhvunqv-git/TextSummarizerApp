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

### 1.2. Định dạng bản tóm tắt (đã chốt 2026-11-07)
Một chuỗi văn bản gồm: 1 đoạn tóm tắt duy nhất (không có bullet points, không danh sách, không xuống dòng giữa đoạn).

Độ dài bản tóm tắt **không** còn là con số từ cố định, mà theo **tỷ lệ % số từ của bản gốc**, kẹp giữa ngưỡng dưới và ngưỡng trên:

| length | Tỷ lệ bản gốc | Ngưỡng dưới | Ngưỡng trên | Bản gốc tối thiểu |
|---|---|---|---|---|
| short | 12% | 25 từ | 120 từ | 400 ký tự |
| medium | 22% | 40 từ | 260 từ | 1.000 ký tự |
| long | 35% | 60 từ | 450 từ | 2.000 ký tự |

- Công thức: `target_words = clamp(round(source_words × ratio), floor, ceiling)`.
- Cột "Bản gốc tối thiểu" là ngưỡng **mở khoá mốc**: văn bản chưa đạt thì mốc đó không chọn được (app xám nút, backend trả `LENGTH_NOT_UNLOCKED`). Ngưỡng short trùng `MIN_CHARS` nên luôn mở khi văn bản hợp lệ.
- TF-IDF fallback dùng cùng tỷ lệ % nhưng tính theo **số câu**: `[2–5]` / `[3–8]` / `[5–12]` câu.

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
- **API:** Render (HTTPS mặc định). Có `render.yaml` (blueprint, `rootDir: backend`, `healthCheckPath: /health`) + `GET /health`.
- **Bắt buộc khi sau proxy:** `ProxyFix(x_for=1, x_proto=1, x_host=1)` để `request.remote_addr` là IP thật, và mọi giới hạn chốt theo `X-Device-ID` (xem 5.5).
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
│   ├── routes/                 # system_routes.py, summary_routes.py, file_routes.py, ocr_routes.py,
│   │                           # usage_routes.py, quiz_routes.py, auth_routes.py
│   ├── services/               # gemini_service.py, tfidf_service.py, ocr_service.py, file_service.py,
│   │                           # crypto_service.py, quota_service.py, history_service.py, quiz_service.py,
│   │                           # email_service.py, auth_service.py
│   ├── utils/                  # responses.py, errors.py, validators.py, text_utils.py, time_utils.py, auth_utils.py
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
        ├── core/               # api_client.dart, constants.dart, storage_service.dart, theme.dart
        ├── models/             # history_models.dart, quiz_models.dart (user_model.dart thuộc GĐ4)
        ├── providers/          # summary_provider.dart, history_provider.dart, quiz_provider.dart (auth_provider.dart thuộc GĐ4)
        └── views/              # home_view, history_view, summary_detail_view, quiz_view, quiz_result_view (auth_view thuộc GĐ4)
```
> `widgets/` không tồn tại: mỗi component chỉ dùng trong một màn nên nằm dạng private ngay trong file view (`_SummaryCard`, `_OptionTile`, `_ResultTile`), tránh một thư mục chứa toàn widget một lần dùng.
> `ocr_service.py` **đang dùng** vì OCR đã chọn phương án B — Gemini Vision (mục 5.3, kiểm chứng trên `ocr_vi.jpg` ngày 2026-11-09); ML Kit on-device đã bỏ vì sai dấu tiếng Việt.

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
- **Màn quiz (từ bước 3.5, GĐ3):**
  - Nút **Tạo quiz mới** nằm ở card *Trắc nghiệm* trong màn chi tiết tóm tắt, tắt khi văn bản gốc dưới 400 ký tự và hiện "Đang tạo quiz, khoảng 30 giây..." trong lúc chờ; quiz đã có liệt kê ngay bên dưới để mở lại **không tốn lượt**.
  - Làm bài theo từng câu: chọn A–D là biết đúng/sai **ngay tại máy** kèm giải thích, có nút **Bỏ qua câu này** (server tính là sai). Đã chọn thì khoá câu đó, đổi ý sẽ lệch với mảng nộp đi.
  - Điểm trên màn kết quả là điểm **server chấm** (`POST /quizzes/{id}/attempts`), không phải điểm app tự cộng; nút **Làm lại** xoá sạch đáp án tại chỗ và nộp thành một lượt mới.
  - Màn kết quả có mục **"Các lần làm trước"** (`GET /quizzes/{id}/attempts`, gọi ngay sau khi nộp): điểm thang 10 + số câu đúng + thời điểm từng lượt cũ, lượt vừa nộp bị loại vì đã hiển thị đầy đủ phía trên. Lỗi tải chỉ ẩn mục này đi, không chặn màn điểm và không hiện SnackBar.
  - Riêng lời gọi tạo quiz dùng `receiveTimeout` **150s** thay vì 60s mặc định của Dio: `GEMINI_QUIZ_TIMEOUT_SECONDS=30` cộng 1 lần retry là kịch bản xấu chạm trần 60s (đo thật 2026-11-10: 54,6s và 59,1s).

---

## 5. Quy tắc nghiệp vụ

### 5.1. Văn bản đầu vào
- Chuẩn hóa **Unicode NFC**, `strip()`, rồi đếm bằng `len()` của Python (backend quyết định cuối; app chỉ kiểm tra sơ bộ).
- Tối thiểu **400** (nâng từ 200 ngày 2026-11-07: bản 200 ký tự quá ngắn nên AI dễ bịa/verbatim), tối đa **30.000** ký tự.
- Ngưỡng mở khoá mốc tóm tắt theo số ký tự bản gốc: `short` **400** / `medium` **1.000** / `long` **2.000** (ước lượng ~120 ký tự/câu → tối thiểu 3 / 8 / 15 câu).
- Lỗi: `TEXT_TOO_SHORT` — *"Văn bản quá ngắn để tóm tắt. Hãy nhập ít nhất 400 ký tự."*; `TEXT_TOO_LONG` — *"Văn bản vượt quá giới hạn 30.000 ký tự. Vui lòng chia nhỏ nội dung."*; `LENGTH_NOT_UNLOCKED` (400) — *"Mốc tóm tắt này cần văn bản dài ít nhất N ký tự (hiện có M ký tự)."*

### 5.2. Tệp tải lên
- Cho phép `.txt`, `.docx`, `.pdf`, tối đa **10 MB** (`MAX_CONTENT_LENGTH`). File `.doc` cũ **không** hỗ trợ.
- Lỗi: `FILE_TOO_LARGE` (413) — *"Dung lượng file vượt quá 10MB."*; `FILE_UNSUPPORTED` (400).
- PDF không trích xuất được chữ (scan) → `PDF_SCANNED` — *"Không thể đọc văn bản từ file này. Hãy dùng tính năng Quét ảnh OCR."*
- Luồng: `POST /files/extract` trả text → app hiển thị cho xem/sửa → gọi `POST /summaries`.
- TXT: thử UTF-8, nếu lỗi thử `utf-8-sig`, `cp1258`, `latin-1`.

### 5.3. OCR
- **Đã chốt (2026-11-07): Gemini Vision qua `POST /api/v1/ocr`** — app gửi ảnh (nén, ≤ 4MB, jpeg/png/webp) lên backend, backend dùng prompt trong `PROMPTS.md` và `ocr_service.py`. Không dùng ML Kit on-device vì script Latin sai dấu tiếng Việt nhiều.
- Rate limit riêng 20 lượt/ngày/IP, không trừ quota tóm tắt; lỗi `FILE_TOO_LARGE` (413), `FILE_UNSUPPORTED`, `OCR_NO_TEXT`, `RATE_LIMITED` (429).
- **Đã kiểm chứng (2026-11-09)** với `testdata/ocr_vi.jpg`: 200, 251 ký tự, 7,2s, dấu tiếng Việt chính xác toàn bộ.

### 5.4. Tạo Quiz (đã chốt)
- **Nguồn:** văn bản gốc của bản tóm tắt (giải mã từ `original_text_enc`); bản tóm tắt làm ngữ cảnh phụ.
- Điều kiện: độ dài văn bản gốc **≥ 400 ký tự** (dùng cột `original_length`), nếu không → `QUIZ_TEXT_TOO_SHORT`.
- **Số câu:** `N = clamp(floor(len / 130), 3, 10)`, `len` là số ký tự **sau khi chuẩn hóa NFC**. Không còn "mặc định 5". *(GĐ3.1: hàm `Config.quiz_question_count(char_count)`, test `tests/test_quiz_count.py`.)*
- Mỗi câu: 4 đáp án A–D khác nhau, **đúng 1** đáp án đúng, có giải thích ngắn. Ngôn ngữ câu hỏi = `language` của bản tóm tắt.
- Backend **kiểm tra** JSON Gemini trả về (đủ N câu, mỗi câu 4 đáp án không trùng, `correct_index` 0–3), **xáo trộn đáp án** và tính lại `correct_index` (Gemini hay đặt đáp án đúng ở vị trí cố định). JSON hỏng/thiếu: retry 1 lần, vẫn lỗi → `AI_UNAVAILABLE`.
- **Tham số gọi quiz (GĐ3.2):** `temperature=0.7` và timeout riêng `GEMINI_QUIZ_TIMEOUT_SECONDS=30` — không dùng 15s của tóm tắt vì đo thật ngày 2026-11-10, bản 2.500 ký tự sinh 10 câu hết 28,8s. `usage_type` QUIZ đã có sẵn trong schema nên không cần migration.
- Một bản tóm tắt có thể tạo nhiều quiz (mỗi lần tốn 1 lượt quiz).
- **Lưu (từ bước 3.3):** `quiz_service.save_quiz()` ghi một dòng `quiz_sessions` rồi N dòng `quiz_questions`
  trong **cùng một transaction**, `position` đánh từ 1; `options_enc` là `json.dumps` mảng 4 đáp án (giữ dấu tiếng Việt,
  không escape `\u`) rồi mới mã hóa. Hoặc đủ cả quiz, hoặc không có gì — DB không bao giờ giữ quiz thiếu câu.
  Thứ tự chặn trong route là *chủ sở hữu → `original_length` ≥ 400 → đặt chỗ QUIZ → gọi AI → lưu*; AI lỗi hoặc DB lỗi thì hoàn đúng một lượt.
- API trả luôn `correct_index` và `explanation` (ứng dụng tự học, hiển thị đáp án ngay sau khi chọn). Khi nộp bài, backend **tính lại điểm** từ đáp án người dùng.
- **Điểm:** thang 10, 1 chữ số thập phân: `score = correct / total * 10`, làm tròn **nửa lên** bằng `Decimal` + `ROUND_HALF_UP`.
  Bắt buộc dùng `Decimal` chứ không `round()`: `round(1/8*10, 1)` ra `1.2` (banker's rounding) trong khi 1/8 câu là độ dài quiz hoàn toàn bình thường.
  Câu `null` (bỏ qua) tính là **sai**.
- **Nộp bài (từ bước 3.4):** `quiz_service.submit_attempt()` chỉ dùng `correct_index` đọc từ DB — mọi `score`/`correct_count`/`results`
  client gửi lên bị bỏ qua, nên không thể xin điểm. Một lần nộp = một dòng `quiz_attempts`, trả 201 kèm `results` đủ mọi câu theo `position`.
  `answers_json_enc` là `json.dumps(answers, ensure_ascii=False)` rồi mã hóa (`null` vẫn nằm nguyên trong mảng).
  **Không đặt chỗ quota, không gọi AI** — làm lại bao nhiêu lần tuỳ ý; `reserve`/`refund` không được phép xuất hiện trên đường này.
  Route đọc quiz trước khi validate (cùng nguyên tắc bước 3.3): quiz của người khác → 404 chứ không phải 400,
  độ dài mảng tiết lộ `question_count` của bản ghi người khác. Mảng sai chỉ số/độ dài → 400 và không ghi dòng nào.
- **Lịch sử làm bài:** `GET /quizzes/{id}/attempts` trả `{quiz_id, items, total}`, `items` chỉ có `id`/`score`/`correct_count`/`total_count`/`submitted_at`
  (không kèm đáp án, không `answers_json_enc`), thứ tự `submitted_at DESC, id DESC`; chưa làm lần nào → 200 mảng rỗng.
  Kiểm chứng thật trên Neon 2026-11-10: 9 câu → đúng hết 10.0, sai hết kèm `score: 10.0` giả → vẫn 0.0, bỏ qua 1 câu → 8.9,
  `usage.quiz.used` vẫn 0, thiết bị khác 404 cả POST lẫn GET, `DELETE /summaries/{id}` xoá sạch `quiz_attempts` qua CASCADE.

### 5.5. Quota & định danh
- **20 tóm tắt/ngày** và **20 quiz/ngày** cho mỗi chủ thể.
- **Hai con số này là trần phía người dùng, không phải năng lực phía server.** Key Gemini free tier chỉ 20 request/ngày cho một model, **cộng chung** tóm tắt + quiz + OCR (429 đo thật 2026-11-10: `generate_content_free_tier_requests, limit: 20`), và mỗi lần quiz retry tốn thêm 1, nghĩa là một mình `/summaries` cũng đủ làm key cạn trước khi hết quota của bất kỳ ai. Khi bật billing thì trần này tăng theo cấp paid; `usage_quota` vẫn là chỗ duy nhất chặn theo chủ thể.
- Chủ thể (`owner_key`): người đã đăng nhập → `u:<user_id>`; khách → `d:<device_id>`.
- Ngày tính theo múi giờ **Asia/Ho_Chi_Minh**, hiện thực bằng **offset cố định `+07:00`** (`timezone(timedelta(hours=7))`), không dùng `ZoneInfo`: Windows không có hệ thống zone database nên `ZoneInfo("Asia/Ho_Chi_Minh")` fail tới khi cài thêm `tzdata`, còn Render (Linux) lại chạy được — lệch môi trường như vậy dễ gây "test local hỏng, production đúng" và ngược lại. Việt Nam không có DST từ 1977 nên offset cố định cho ra cùng một mốc nửa đêm. Nếu sau này cần múi giờ theo từng người dùng thì chỉ đổi hằng số `VN_TZ` thành `ZoneInfo(user_tz)`.
- Cách tính (chống bấm đúp/race): **đặt chỗ nguyên tử** trước khi gọi AI (SQL `INSERT ... ON CONFLICT DO UPDATE ... WHERE count < limit RETURNING`), nếu xử lý **thất bại** (lỗi validate sau đặt chỗ, lỗi hệ thống, `AI_UNAVAILABLE` của quiz) thì **hoàn lại** 1 lượt. Thành công (kể cả bằng fallback TF-IDF) thì giữ.
- Hết quota: `QUOTA_EXCEEDED` (429) — *"Bạn đã dùng hết quota trong ngày. Vui lòng quay lại vào ngày mai."*
- Lưu trong **bảng DB `usage_quota`** (không dùng bộ nhớ RAM). `Flask-Limiter` chỉ chống spam theo IP (ví dụ 30 request/phút/IP; auth endpoints chặt hơn: 5/phút/IP).
- **Ngoại lệ tạm thời (2026-11-10, phục vụ deploy sớm trước GĐ2):** vì GĐ1 chưa có DB, `Flask-Limiter` được dùng luôn cho mức **20 tóm tắt/ngày** và **20 OCR/ngày**, với `key_func` lấy **`X-Device-ID`** (fallback IP khi header vắng) chứ không theo IP — đứng sau proxy Render thì mọi user chung một IP egress, key theo IP sẽ gộp toàn bộ người dùng thành một. Hai giới hạn `per day` này là **cửa sổ rolling 24h trong RAM**, không phải mốc nửa đêm +07, và **Reset khi server khởi động lại hoặc thức dậy sau cold start**. Sang GĐ2, `quota_service.py` + bảng `usage_quota` thay thế hoàn toàn (đặt chỗ nguyên tử, đúng mốc nửa đêm +07, không mất khi restart); `Flask-Limiter` khi đó quay về đúng vai trò chống spam phút. **Trạng thái từ bước 2.5:** `POST /summaries` đã chuyển hẳn sang `quota_service` + bảng `usage_quota` (đặt chỗ trước khi gọi AI, hoàn lại khi xử lý thất bại) và `@limiter.limit("20 per day")` trên route bị bỏ trong chính bước đó — không có lúc nào endpoint bị hai bộ đếm cùng chặn, hoặc không bộ đếm nào. `POST /ocr` vẫn dùng `20 per day` của Flask-Limiter vì ràng buộc `usage_type` trong schema chỉ nhận `SUMMARY`/`QUIZ`; thêm giá trị OCR là sửa schema nên để GĐ3.
- Header `X-Device-ID` (UUID v4) bắt buộc với mọi endpoint nghiệp vụ; sai định dạng → `INVALID_DEVICE_ID`.

### 5.6. Fallback tóm tắt
- Điều kiện chuyển sang TF-IDF: Gemini timeout (15s), lỗi mạng, hết hạn mức, bị chặn safety, trả rỗng, hoặc JSON hỏng sau 1 lần retry.
- Thuật toán: tách câu bằng regex (hỗ trợ dấu `.!?…` và xuống dòng), chấm điểm câu bằng TF-IDF, lấy top-k theo `length`, **giữ nguyên thứ tự gốc**. Không dùng stopword tiếng Anh cho tiếng Việt.
- Số câu lấy = tỷ lệ % số câu bản gốc theo mốc (12% / 22% / 35%), kẹp trong `[2–5]` / `[3–8]` / `[5–12]`; văn bản chỉ có 1–2 câu thì lấy toàn bộ.
- **Định dạng output fallback (chốt 2026-11-07):** các câu được đánh số `1. `, `2. ` trên từng dòng. Bản Gemini mới là đoạn văn liền mạch, nên người dùng nhìn là biết kết quả đến từ thuật toán chứ không phải AI. Đây là ngoại lệ có chủ đích của quy tắc "1 đoạn văn duy nhất" ở mục 1.2.
- `title` fallback = câu đầu cắt ≤ 60 ký tự; `description` = 120 ký tự đầu của bản tóm tắt. Phần "ý chính" có thể bỏ.
- Response luôn có `source: "gemini" | "tfidf"`.

### 5.7. Quyền sở hữu & truy cập (chống IDOR)
- Danh tính người gọi: có JWT hợp lệ → `user_id`; ngược lại dùng `X-Device-ID`.
- Bản ghi được phép truy cập khi `user_id = người gọi` **hoặc** (`user_id IS NULL` và `device_id = X-Device-ID`).
- Không thuộc người gọi → trả `NOT_FOUND` (404), không tiết lộ sự tồn tại.
- **Cách cài đặt (từ bước 2.6):** điều kiện sở hữu là một mẫu SQL duy nhất trong `history_service.py`
  `(user_id = %s OR (user_id IS NULL AND device_id = %s))` và nằm **trong chính câu SELECT/DELETE**,
  không kiểm tra bằng `if` sau khi đọc. Route không tự viết `WHERE` riêng, nên không thể quên bước kiểm tra.
  Khi chưa có JWT, `user_id = NULL` làm vế đầu không bao giờ đúng — cùng một câu lệnh dùng được cho cả 4 giai đoạn.
- **Quiz kiểm sở hữu qua bản tóm tắt cha (từ bước 3.3):** mọi câu đọc `quiz_sessions` đều
  `JOIN summaries s ON s.id = qs.summary_id` rồi áp cùng mẫu điều kiện cho `s.`
  (`(s.user_id = %s OR (s.user_id IS NULL AND s.device_id = %s))`), không lọc theo `qs.user_id`.
  Lý do: GĐ4 gộp khách vào tài khoản chỉ sửa `summaries.user_id`, còn `quiz_sessions.user_id` của bản ghi cũ
  vẫn `NULL` — nếu quiz tự kiểm tra cột của nó thì dữ liệu cũ "biến mất" khỏi mắt người dùng ngay sau khi đăng nhập.
  Cách này cũng khớp ý nghĩa của API: người xem được bản tóm tắt thì xem được quiz của nó.
  `list_quizzes` chạy thêm một câu `SELECT 1 FROM summaries s WHERE s.id = %s AND …` **trước** khi liệt kê,
  để id của người khác trả 404 chứ không phải danh sách rỗng.
  Ràng buộc của mẫu điều kiện này có một mặt trái phải nhớ: nó **mang alias `s.`**, nên mọi câu dùng nó phải tự khai báo
  `summaries s`; PostgreSQL báo `missing FROM-clause entry for table "s"` mà cursor giả trong unit test không phát hiện được
  (đúng lỗi mà smoke Neon ngày 2026-11-10 bắt ra) — `tests/test_quiz_service.py` có test kiểm tra alias tĩnh cho `s.` và `qs.` để không tái phạm.
- **Lượt làm bài cũng đi qua bản tóm tắt cha (từ bước 3.4):** `quiz_attempts` không tự kiểm tra cột của nó mà
  `JOIN quiz_sessions qs … JOIN summaries s` rồi áp cùng mẫu điều kiện cho `s.`; hai endpoint attempts đều chạy
  một câu kiểm tra quiz trước (`get_quiz`) nên id của người khác 404 ở cả POST lẫn GET.
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

`database/db.py` tạo `ThreadedConnectionPool` **lười** (ở lần mượn connection đầu tiên): backend phải boot được khi thiếu `DATABASE_URL` để dừng ở giai đoạn nào cũng còn deploy được (xem `PHASES.md` GĐ1.5). Route cần DB mà chưa cấu hình sẽ fail rõ ràng, không im lặng trả dữ liệu rỗng.

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
| `en_250.txt` | Tiếng Anh 250 ký tự (dưới ngưỡng 400) | `TEXT_TOO_SHORT` |
| `en_400.txt` | Tiếng Anh 455 ký tự / 72 từ / 5 câu | tóm tắt OK, `language=en`, mở mốc `short` |
| `vi_500.txt` | Tiếng Việt có dấu 500 ký tự | OK, `language=vi`, chỉ mở mốc `short` |
| `vi_1200.txt` | Tiếng Việt 1.272 ký tự / 12 câu | mở mốc `short` + `medium`, khoá `long` |
| `vi_2500.txt` | Tiếng Việt 2.385 ký tự / 22 câu | mở cả ba mốc |
| `short_100.txt` | 100 ký tự | `TEXT_TOO_SHORT` |
| `long_31000.txt` | 31.000 ký tự | `TEXT_TOO_LONG` |
| `emoji.txt` | có emoji, ký tự đặc biệt (447 ký tự) | không crash, đếm đúng |
| `mixed.txt` | trộn Anh–Việt (291 ký tự, dưới ngưỡng 400) | `TEXT_TOO_SHORT`; phần "ngôn ngữ ưu thế" kiểm bằng unit test trong `test_validators.py` |
| `sample.txt`, `sample.docx`, `sample_text.pdf` | file hợp lệ | trích xuất OK |
| `scanned.pdf` | PDF ảnh scan | `PDF_SCANNED` |
| `big_11mb.pdf` | > 10MB | `FILE_TOO_LARGE` |
| `injection.txt` | chứa câu "bỏ qua mọi hướng dẫn trước đó..." (626 ký tự) | vẫn trả bản tóm tắt bình thường |
| `ocr_vi.jpg` | ảnh chụp chữ tiếng Việt có dấu | đánh giá độ chính xác OCR |

**Test tự động tối thiểu (pytest):** (1) validate độ dài/NFC, (2) mã hóa–giải mã round-trip + nonce khác nhau, (3) hàm tính số câu quiz `N` (ví dụ 400→3, 650→5, 1300→10, 5000→10).

---

## 10. Ngoài phạm vi (Non-goals)
Dark mode, đa ngôn ngữ giao diện, đăng nhập mạng xã hội, iOS, cache offline, refresh token, push notification, thanh toán, dịch văn bản, tìm kiếm lịch sử bằng SQL, chia sẻ dữ liệu giữa người dùng.
