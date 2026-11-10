# API.md — TextSummarizer AI

Base URL: `https://<host>/api/v1`  ·  Content-Type: `application/json` (trừ upload file/ảnh: `multipart/form-data`)

## 1. Header chung
| Header | Bắt buộc | Ý nghĩa |
|---|---|---|
| `X-Device-ID` | Có (mọi endpoint nghiệp vụ) | UUID v4 do app tạo, lưu trong `flutter_secure_storage`; từ 2026-11-10 còn là **khóa tính giới hạn 20 lượt/ngày** (thay cho IP, vì backend chạy sau proxy Render) |
| `X-App-Version` | Có | Ví dụ `1.0.0`; thấp hơn `min_app_version` → 426 |
| `Authorization: Bearer <JWT>` | Tùy chọn | Có → định danh theo user; không có → theo device |

## 2. Định dạng response chuẩn
**Thành công (200/201):**
```json
{ "success": true, "message": "Xử lý thành công", "data": { } }
```
**Lỗi:**
```json
{ "success": false, "error_code": "TEXT_TOO_SHORT", "message": "Văn bản quá ngắn để tóm tắt. Hãy nhập ít nhất 400 ký tự." }
```
Mọi exception không lường trước → `500 INTERNAL_ERROR` (không lộ stack trace).
App **hiển thị nguyên văn `message`** cho mọi lỗi mà request đi tới được backend (kể cả 4xx/5xx, tức cả 429 hết lượt); thông điệp "chưa thể kết nối tới máy chủ AI" chỉ dùng khi không nhận được response nào.

## 3. Danh sách endpoint

| Method | Path | Auth | Giai đoạn | Mô tả |
|---|---|---|---|---|
| GET | `/health` *(không có prefix `/api/v1`)* | Không | 1 | Kiểm tra sống (Render, ping) |
| GET | `/config` | Không | 1 | `min_app_version`, giới hạn |
| POST | `/summaries` | Device/JWT | 1 (GĐ2 lưu DB) | Tóm tắt văn bản |
| POST | `/files/extract` | Device/JWT | 1 | Trích text từ TXT/DOCX/PDF |
| GET | `/usage` | Device/JWT | 2 | Lượt còn lại hôm nay |
| GET | `/summaries?page=&limit=` | Device/JWT | 2 | Danh sách lịch sử (phân trang) |
| GET | `/summaries/{id}` | Device/JWT | 2 | Chi tiết (gồm văn bản gốc) |
| DELETE | `/summaries/{id}` | Device/JWT | 2 | Xóa (cascade quiz) |
| POST | `/summaries/{id}/quizzes` | Device/JWT | 3 | Tạo quiz |
| GET | `/summaries/{id}/quizzes` | Device/JWT | 3 | Danh sách quiz của bản tóm tắt |
| GET | `/quizzes/{id}` | Device/JWT | 3 | Chi tiết quiz + câu hỏi |
| POST | `/quizzes/{id}/attempts` | Device/JWT | 3 | Nộp bài, chấm điểm |
| GET | `/quizzes/{id}/attempts` | Device/JWT | 3 | Lịch sử làm bài |
| POST | `/auth/register` | Không | 4 | Đăng ký, gửi OTP |
| POST | `/auth/verify-otp` | Không | 4 | Xác thực OTP đăng ký, trả JWT |
| POST | `/auth/resend-otp` | Không | 4 | Gửi lại OTP |
| POST | `/auth/login` | Không | 4 | Đăng nhập, trả JWT, gộp dữ liệu khách |
| POST | `/auth/forgot-password` | Không | 4 | Gửi OTP đặt lại mật khẩu |
| POST | `/auth/reset-password` | Không | 4 | Đặt mật khẩu mới bằng OTP |
| GET | `/auth/me` | JWT | 4 | Thông tin tài khoản |
| POST | `/ocr` | Device/JWT | 1 | Gemini Vision OCR |

## 4. Chi tiết & JSON mẫu

### POST `/summaries`
Request:
```json
{ "text": "<400–30000 ký tự>", "length": "medium" }
```
`length`: `short | medium | long`, mặc định `medium`.
Giới hạn theo `X-Device-ID`: **20 lượt/ngày** (hết → 429 `QUOTA_EXCEEDED`) và 30 request/phút (→ 429 `RATE_LIMITED`). Ở GĐ1 hai con số này do Flask-Limiter giữ trong RAM với cửa sổ rolling 24h; sang GĐ2 chuyển sang bảng `usage_quota` (đúng mốc nửa đêm +07, đặt chỗ nguyên tử).
Độ dài bản tóm tắt = tỷ lệ số từ bản gốc (12% / 22% / 35%, kẹp trong 25–120 / 40–260 / 60–450 từ). Mốc `medium` cần bản gốc ≥ 1.000 ký tự, `long` cần ≥ 2.000 ký tự; chưa đạt thì trả `LENGTH_NOT_UNLOCKED`.

Response 201 (GĐ2 trở đi có `id`; GĐ1 `id` = `null`):
```json
{
  "success": true, "message": "Xử lý thành công",
  "data": {
    "id": 12,
    "title": "Tác động của AI tới giáo dục",
    "description": "Bài viết phân tích lợi ích và rủi ro của AI trong lớp học.",
    "summary": "AI đang thay đổi cách dạy và học bằng cách cá nhân hoá lộ trình, nhưng cũng tạo rủi ro người học lệ thuộc công cụ và cần quy minh bạch.",
    "language": "vi",
    "source": "gemini",
    "original_length": 1840,
    "created_at": "2026-11-03T09:30:00+07:00",
    "usage": { "summary_remaining": 19, "quiz_remaining": 20 }
  }
}
```

Ghi chú GĐ1: `id` = `null` (chưa lưu DB), `usage.summary_remaining` và `usage.quiz_remaining` = `null` (chưa theo dõi quota). Có giá trị thật từ GĐ2.

### POST `/files/extract` (multipart, field `file`)
Response:
```json
{ "success": true, "message": "Xử lý thành công",
  "data": { "text": "...", "char_count": 5230, "filename": "bai.docx" } }
```
Lỗi: `FILE_TOO_LARGE` (413), `FILE_UNSUPPORTED`, `PDF_SCANNED`, `TEXT_TOO_LONG`, `FILE_EMPTY`.

### POST `/ocr` (multipart, field `image`)
Request: Ảnh chụp văn bản (jpeg/png/webp, tối đa 4MB).
Response:
```json
{ "success": true, "message": "Xử lý thành công",
  "data": { "text": "Nội dung văn bản trích xuất từ ảnh...", "char_count": 1234 } }
```
Lỗi: `FILE_TOO_LARGE` (413), `FILE_UNSUPPORTED` (sai định dạng), `OCR_NO_TEXT` (không nhận diện được chữ), `QUOTA_EXCEEDED` (429, vượt 20 lượt/ngày/thiết bị).

Ghi chú: OCR dùng Gemini Vision API, chịu giới hạn riêng (20 lượt/ngày theo `X-Device-ID`) và không trừ vào giới hạn tóm tắt.

### GET `/usage`
```json
{ "success": true, "message": "Xử lý thành công",
  "data": { "summary": { "used": 1, "limit": 20, "remaining": 19 },
            "quiz":    { "used": 0, "limit": 20, "remaining": 20 },
            "resets_at": "2026-11-04T00:00:00+07:00" } }
```

### GET `/summaries?page=1&limit=20`
`limit` mặc định 20, tối đa 50. Không trả `original_text`/`summary` đầy đủ.
```json
{ "success": true, "message": "Xử lý thành công",
  "data": { "items": [ { "id": 12, "title": "...", "description": "...", "language": "vi", "source": "gemini", "created_at": "..." } ],
            "page": 1, "limit": 20, "total": 37 } }
```

### GET `/summaries/{id}`
`data` = như response tạo summary + `original_text`.

### DELETE `/summaries/{id}`
`data`: `{ "deleted": true }`.

### POST `/summaries/{id}/quizzes`
Request body rỗng `{}`. Lỗi: `QUIZ_TEXT_TOO_SHORT`, `QUOTA_EXCEEDED`, `AI_UNAVAILABLE`, `NOT_FOUND`.
```json
{ "success": true, "message": "Xử lý thành công",
  "data": {
    "id": 5, "summary_id": 12, "question_count": 5, "language": "vi",
    "created_at": "...",
    "questions": [
      { "id": 31, "position": 1,
        "question": "Lợi ích chính của AI trong giáo dục là gì?",
        "options": ["Cá nhân hóa việc học", "Giảm số giáo viên", "Tăng học phí", "Bỏ kiểm tra"],
        "correct_index": 0,
        "explanation": "Văn bản nhấn mạnh khả năng điều chỉnh nội dung theo từng học sinh." }
    ],
    "usage": { "summary_remaining": 19, "quiz_remaining": 19 }
  } }
```

### POST `/quizzes/{id}/attempts`
Request (mảng độ dài = `question_count`, `null` = bỏ qua):
```json
{ "answers": [0, 2, null, 1, 3] }
```
Response:
```json
{ "success": true, "message": "Xử lý thành công",
  "data": { "attempt_id": 9, "score": 6.0, "correct_count": 3, "total_count": 5,
            "results": [ { "position": 1, "selected": 0, "correct_index": 0, "is_correct": true } ],
            "submitted_at": "..." } }
```
Lỗi: `VALIDATION_ERROR` (sai độ dài mảng / giá trị ngoài 0–3). Backend tự tính điểm, không tin điểm từ client. Nộp bài **không** tốn quota.

### POST `/auth/register`
```json
{ "email": "a@example.com", "password": "Min8chars!" }
```
→ 201 `{ "email": "a@example.com", "otp_expires_in": 300 }`. Lỗi: `EMAIL_EXISTS`, `VALIDATION_ERROR`.
Nếu email đã tồn tại nhưng **chưa xác thực**: cập nhật mật khẩu mới và gửi lại OTP.

### POST `/auth/verify-otp`
```json
{ "email": "a@example.com", "otp": "123456", "purpose": "REGISTER" }
```
→ `{ "token": "<JWT>", "user": { "id": 1, "email": "a@example.com" } }` và gộp dữ liệu khách (nếu có `X-Device-ID`). Lỗi: `OTP_INVALID`, `OTP_EXPIRED`, `OTP_TOO_MANY_ATTEMPTS`.

### POST `/auth/resend-otp`
`{ "email": "...", "purpose": "REGISTER" }` → lỗi `OTP_RESEND_COOLDOWN` nếu < 60s.

### POST `/auth/login`
`{ "email": "...", "password": "..." }` → `{ "token": "<JWT>", "user": {...}, "merged": { "summaries": 3 } }`.
Lỗi: `INVALID_CREDENTIALS`, `EMAIL_NOT_VERIFIED`.

### POST `/auth/forgot-password`
`{ "email": "..." }` → luôn 200 (không tiết lộ email tồn tại hay không).

### POST `/auth/reset-password`
`{ "email": "...", "otp": "123456", "new_password": "..." }` → 200. Lỗi OTP như trên.

### GET `/config`
```json
{ "success": true, "message": "Xử lý thành công",
  "data": { "min_app_version": "1.0.0",
            "limits": { "min_chars": 400, "max_chars": 30000, "max_file_mb": 10, "daily_summary": 20, "daily_quiz": 20 },
            "length_unlock_chars": { "short": 400, "medium": 1000, "long": 2000 } } }
```

### GET `/health`
`{ "status": "ok" }` (không cần header, không đụng DB nặng).

## 5. Bảng error_code

| error_code | HTTP | Message (tiếng Việt, hiển thị cho người dùng) |
|---|---|---|
| `TEXT_TOO_SHORT` | 400 | Văn bản quá ngắn để tóm tắt. Hãy nhập ít nhất 400 ký tự. |
| `LENGTH_NOT_UNLOCKED` | 400 | Mốc tóm tắt bạn chọn cần văn bản dài hơn. Hãy nhập thêm nội dung hoặc chọn mốc Ngắn. |
| `TEXT_TOO_LONG` | 400 | Văn bản vượt quá giới hạn 30.000 ký tự. Vui lòng chia nhỏ nội dung. |
| `QUIZ_TEXT_TOO_SHORT` | 400 | Văn bản quá ngắn để tạo quiz (cần ít nhất 400 ký tự). |
| `FILE_TOO_LARGE` | 413 | Dung lượng file vượt quá 10MB. |
| `FILE_UNSUPPORTED` | 400 | Chỉ hỗ trợ file .txt, .docx, .pdf. |
| `FILE_EMPTY` | 400 | File không có nội dung văn bản. |
| `PDF_SCANNED` | 400 | Không thể đọc văn bản từ file này. Hãy dùng tính năng Quét ảnh OCR. |
| `VALIDATION_ERROR` | 400 | Dữ liệu gửi lên không hợp lệ. |
| `INVALID_DEVICE_ID` | 400 | Thiết bị không hợp lệ. Hãy khởi động lại ứng dụng. |
| `UNAUTHORIZED` | 401 | Phiên đăng nhập hết hạn. Vui lòng đăng nhập lại. |
| `INVALID_CREDENTIALS` | 401 | Email hoặc mật khẩu không đúng. |
| `EMAIL_NOT_VERIFIED` | 403 | Email chưa được xác thực. |
| `NOT_FOUND` | 404 | Không tìm thấy dữ liệu. |
| `EMAIL_EXISTS` | 409 | Email đã được đăng ký. |
| `OTP_INVALID` | 400 | Mã OTP không đúng. |
| `OTP_EXPIRED` | 400 | Mã OTP đã hết hạn. Hãy yêu cầu mã mới. |
| `OTP_TOO_MANY_ATTEMPTS` | 429 | Nhập sai quá nhiều lần. Hãy yêu cầu mã mới. |
| `OTP_RESEND_COOLDOWN` | 429 | Vui lòng đợi 60 giây trước khi gửi lại mã. |
| `QUOTA_EXCEEDED` | 429 | Bạn đã dùng hết quota trong ngày. Vui lòng quay lại vào ngày mai. *(GĐ1: do Flask-Limiter theo `X-Device-ID`, rolling 24h; GĐ2: do bảng `usage_quota`.)* |
| `RATE_LIMITED` | 429 | Bạn thao tác quá nhanh. Vui lòng thử lại sau ít phút. *(chỉ giới hạn số request/phút)* |
| `UPDATE_REQUIRED` | 426 | Vui lòng cập nhật ứng dụng lên phiên bản mới. |
| `AI_UNAVAILABLE` | 503 | Tính năng tạo quiz tạm thời không khả dụng. Vui lòng thử lại sau. |
| `INTERNAL_ERROR` | 500 | Đã có lỗi xảy ra. Vui lòng thử lại. |

Ghi chú: tóm tắt **không bao giờ** trả `AI_UNAVAILABLE` (đã có fallback TF-IDF).
