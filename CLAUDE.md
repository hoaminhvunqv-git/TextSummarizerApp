# CLAUDE.md — Quy tắc làm việc cho AI (TextSummarizer AI)

> Đặt file này ở **gốc repo**. (Nếu dùng công cụ khác, đổi tên thành `AGENTS.md` / `.cursorrules` / tương đương.)
> Tài liệu chi tiết: `docs/SPEC.md` (nguồn sự thật), `docs/API.md`, `docs/PROMPTS.md`, `docs/PHASES.md`, `backend/database/schema.sql`.

## Dự án
Ứng dụng **Android** (Flutter) tóm tắt văn bản Anh–Việt + tạo quiz ABCD. Backend Flask + PostgreSQL cloud (Neon/Supabase), AI = Gemini, fallback = TF-IDF.

## Quy trình bắt buộc
1. **Chỉ làm đúng giai đoạn/bước được yêu cầu.** Không tự thêm tính năng, không làm trước giai đoạn sau.
2. **Trước khi viết code:** nêu kế hoạch ngắn + liệt kê file sẽ tạo/sửa. Chờ người dùng đồng ý.
3. **Mỗi bước một mục tiêu kiểm chứng được.** Kết thúc bước phải ghi: (a) cách chạy, (b) cách test (lệnh curl / thao tác trên app), (c) kết quả mong đợi.
4. Gợi ý commit message sau mỗi bước xong.
5. Khi không chắc về yêu cầu: **hỏi**, đừng tự đoán. Khi tên model/API/package có thể đã đổi: nói rõ cần kiểm tra tài liệu chính thức.

## Quy tắc code
- **Không đổi tên** file, bảng, cột, endpoint, error_code đã định nghĩa trong docs. Muốn thêm thì thêm, không sửa tên.
- Mọi response API theo đúng `docs/API.md` (`success`, `message`, `data` / `error_code`). Dùng helper chung ở `backend/utils/responses.py`.
- **Không hard-code secret.** Luôn đọc từ biến môi trường (`config.py`). `.env` phải nằm trong `.gitignore`; cập nhật `.env.example` khi thêm biến mới.
- **Không log nội dung văn bản người dùng** (original text, summary, câu hỏi, OTP, mật khẩu, token). Chỉ log: id, độ dài, thời gian xử lý, `source` (gemini/tfidf), mã lỗi.
- DB: dùng **psycopg2** + SQL thuần có tham số (`%s`). **Cấm** nối chuỗi SQL. Không dùng SQLAlchemy. Thay đổi schema = thêm file migration mới trong `backend/database/migrations/`, không sửa tay DB.
- Mã hóa: **AES-256-GCM** (`cryptography` → `AESGCM`), nonce 12 byte ngẫu nhiên mỗi lần, lưu `base64(nonce+ciphertext)`. **Cấm** dùng Fernet.
- Mọi endpoint đọc/xóa bản ghi phải **kiểm tra quyền sở hữu** (user_id hoặc device_id). Không thuộc về người gọi → trả `NOT_FOUND`.
- Validate ở backend là quyết định cuối cùng; app chỉ validate sơ bộ.
- Chuẩn hóa Unicode **NFC** + `strip()` trước khi đếm ký tự.
- Flutter: `provider` cho state, `Navigator` cơ bản (không go_router), `dio` có interceptor, font **Roboto**, chỉ Android.
- Không tạo thêm package/thư viện ngoài danh sách trong SPEC mục 3 mà không hỏi.

## Ngoài phạm vi (không tự làm)
Dark mode, đa ngôn ngữ giao diện, đăng nhập Google/Facebook, iOS, cache offline, push notification, thanh toán, chia sẻ lịch sử giữa người dùng, refresh token.

## Lệnh thường dùng
```bash
# Backend
cd backend && python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python app.py                      # dev
pytest                             # test
# Mobile
cd mobile && flutter pub get && flutter run
flutter build apk --release --split-per-abi
```
