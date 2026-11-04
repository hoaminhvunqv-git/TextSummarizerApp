-- =====================================================================
-- TextSummarizer AI — schema.sql (PostgreSQL)
-- Dùng làm backend/database/migrations/001_init.sql
-- (và copy sang backend/database/schema.sql để tham chiếu)
-- Mọi cột *_enc lưu base64(nonce12 + ciphertext_with_tag) của AES-256-GCM.
-- =====================================================================

CREATE TABLE IF NOT EXISTS schema_migrations (
    filename   VARCHAR(255) PRIMARY KEY,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 1. users ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS users (
    id            BIGSERIAL PRIMARY KEY,
    email         VARCHAR(255) NOT NULL UNIQUE,   -- lưu lowercase
    password_hash VARCHAR(255) NOT NULL,
    is_verified   BOOLEAN      NOT NULL DEFAULT FALSE,
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 2. summaries --------------------------------------------------------
CREATE TABLE IF NOT EXISTS summaries (
    id                BIGSERIAL PRIMARY KEY,
    user_id           BIGINT REFERENCES users(id) ON DELETE CASCADE,   -- NULLABLE
    device_id         VARCHAR(100),                                    -- NULLABLE
    title_enc         TEXT NOT NULL,
    description_enc   TEXT NOT NULL,
    original_text_enc TEXT NOT NULL,
    summary_enc       TEXT NOT NULL,
    original_length   INT  NOT NULL,                                   -- độ dài văn bản gốc (sau NFC+strip), không nhạy cảm
    language          VARCHAR(10) NOT NULL CHECK (language IN ('vi','en')),
    source            VARCHAR(10) NOT NULL DEFAULT 'gemini' CHECK (source IN ('gemini','tfidf')),
    created_at        TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT summaries_owner_chk CHECK (user_id IS NOT NULL OR device_id IS NOT NULL)
);
CREATE INDEX IF NOT EXISTS idx_summaries_user_created   ON summaries (user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_summaries_device_created ON summaries (device_id, created_at DESC);

-- 3. quiz_sessions ----------------------------------------------------
CREATE TABLE IF NOT EXISTS quiz_sessions (
    id             BIGSERIAL PRIMARY KEY,
    user_id        BIGINT REFERENCES users(id) ON DELETE CASCADE,      -- NULLABLE
    device_id      VARCHAR(100),                                       -- NULLABLE
    summary_id     BIGINT NOT NULL REFERENCES summaries(id) ON DELETE CASCADE,
    question_count INT    NOT NULL,
    language       VARCHAR(10) NOT NULL,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT quiz_sessions_owner_chk CHECK (user_id IS NOT NULL OR device_id IS NOT NULL)
);
CREATE INDEX IF NOT EXISTS idx_quiz_sessions_summary ON quiz_sessions (summary_id);
CREATE INDEX IF NOT EXISTS idx_quiz_sessions_user    ON quiz_sessions (user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_quiz_sessions_device  ON quiz_sessions (device_id, created_at DESC);

-- 4. quiz_questions ---------------------------------------------------
CREATE TABLE IF NOT EXISTS quiz_questions (
    id                BIGSERIAL PRIMARY KEY,
    quiz_session_id   BIGINT NOT NULL REFERENCES quiz_sessions(id) ON DELETE CASCADE,
    position          INT    NOT NULL,                                 -- thứ tự câu, bắt đầu từ 1
    question_text_enc TEXT   NOT NULL,
    options_enc       TEXT   NOT NULL,                                 -- mã hóa JSON mảng 4 đáp án [A,B,C,D]
    correct_index     INT    NOT NULL CHECK (correct_index BETWEEN 0 AND 3),
    explanation_enc   TEXT   NOT NULL,
    UNIQUE (quiz_session_id, position)
);

-- 5. quiz_attempts ----------------------------------------------------
CREATE TABLE IF NOT EXISTS quiz_attempts (
    id               BIGSERIAL PRIMARY KEY,
    quiz_session_id  BIGINT NOT NULL REFERENCES quiz_sessions(id) ON DELETE CASCADE,
    user_id          BIGINT REFERENCES users(id) ON DELETE CASCADE,    -- NULLABLE
    device_id        VARCHAR(100),                                     -- NULLABLE
    answers_json_enc TEXT   NOT NULL,                                  -- mã hóa JSON mảng index đã chọn (null nếu bỏ qua)
    score            REAL   NOT NULL,                                  -- thang 10, làm tròn 1 chữ số
    correct_count    INT    NOT NULL,
    total_count      INT    NOT NULL,
    submitted_at     TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT quiz_attempts_owner_chk CHECK (user_id IS NOT NULL OR device_id IS NOT NULL)
);
CREATE INDEX IF NOT EXISTS idx_quiz_attempts_session ON quiz_attempts (quiz_session_id, submitted_at DESC);
CREATE INDEX IF NOT EXISTS idx_quiz_attempts_user    ON quiz_attempts (user_id, submitted_at DESC);
CREATE INDEX IF NOT EXISTS idx_quiz_attempts_device  ON quiz_attempts (device_id, submitted_at DESC);

-- 6. otp_codes --------------------------------------------------------
CREATE TABLE IF NOT EXISTS otp_codes (
    id         BIGSERIAL PRIMARY KEY,
    user_id    BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    otp_hash   VARCHAR(255) NOT NULL,
    purpose    VARCHAR(50)  NOT NULL CHECK (purpose IN ('REGISTER','RESET_PASSWORD')),
    attempts   INT          NOT NULL DEFAULT 0,        -- khóa khi >= 5
    created_at TIMESTAMPTZ  NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMPTZ  NOT NULL,                  -- created_at + 5 phút
    used_at    TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_otp_user_purpose ON otp_codes (user_id, purpose, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_otp_expires      ON otp_codes (expires_at);

-- 7. usage_quota ------------------------------------------------------
-- owner_key: 'u:<user_id>' (đã đăng nhập) hoặc 'd:<device_id>' (khách)
-- usage_date: ngày theo múi giờ Asia/Ho_Chi_Minh (tính ở tầng ứng dụng)
CREATE TABLE IF NOT EXISTS usage_quota (
    id         BIGSERIAL PRIMARY KEY,
    owner_key  VARCHAR(120) NOT NULL,
    usage_type VARCHAR(20)  NOT NULL CHECK (usage_type IN ('SUMMARY','QUIZ')),
    usage_date DATE         NOT NULL,
    count      INT          NOT NULL DEFAULT 0,
    UNIQUE (owner_key, usage_type, usage_date)
);

-- ---------------------------------------------------------------------
-- Mẫu SQL quota (dùng trong quota_service.py)
-- Đặt chỗ nguyên tử: không có dòng trả về => đã hết quota.
--   INSERT INTO usage_quota (owner_key, usage_type, usage_date, count)
--   VALUES (%s, %s, %s, 1)
--   ON CONFLICT (owner_key, usage_type, usage_date)
--   DO UPDATE SET count = usage_quota.count + 1
--   WHERE usage_quota.count < %s
--   RETURNING count;
-- Hoàn lại khi xử lý thất bại:
--   UPDATE usage_quota SET count = GREATEST(count - 1, 0)
--   WHERE owner_key = %s AND usage_type = %s AND usage_date = %s;
-- Dọn dữ liệu cũ (lazy, thi thoảng gọi): DELETE FROM usage_quota WHERE usage_date < CURRENT_DATE - 30;
-- ---------------------------------------------------------------------
