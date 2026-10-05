-- 92_matching_chat.sql — Ghép bạn ở (swipe) + Nhắn tin realtime giữa SV đã ghép.
-- Thiết kế: docs/tech_specs/Matching_Messaging_Design.md (Phần I 1.5, Phần II 2.9, Phần III 3.8)
--           docs/tech_specs/Chat_Realtime.md (WebSocket + Redis pub/sub, fallback polling)
-- Runs AFTER 91_contact_address.sql. Idempotent (IF NOT EXISTS) để apply tay vào DB đang chạy.

-- ---------------------------------------------------------------------------
-- 1. Hồ sơ ở ghép — mở rộng cho form v2 (Phần II 2.9). Chat chỉ ĐỌC các cột này
--    (cột phải "Hồ sơ ở ghép"); thuật toán ghép sẽ dùng sau.
--    gender_pref (mig 30) giữ để tương thích, NGỪNG dùng: chính sách là chỉ ghép cùng giới.
-- ---------------------------------------------------------------------------
ALTER TABLE roommate_profiles
    ADD COLUMN IF NOT EXISTS gender          VARCHAR(3),      -- 'nam'|'nu'; NULL = ngoài pool ghép
    ADD COLUMN IF NOT EXISTS don_vi          VARCHAR(100),    -- Trường/Khoa (cấp trường)
    ADD COLUMN IF NOT EXISTS budget_band     SMALLINT,        -- 0..4 theo C1
    ADD COLUMN IF NOT EXISTS scenario        SMALLINT,        -- 1 mình | ghép 2 | ghép 3+
    ADD COLUMN IF NOT EXISTS hanh_vi         TEXT[],
    ADD COLUMN IF NOT EXISTS deal_breakers   TEXT[],
    ADD COLUMN IF NOT EXISTS smoke_in_room   BOOLEAN,
    ADD COLUMN IF NOT EXISTS wake_time       SMALLINT,
    ADD COLUMN IF NOT EXISTS ac_usage        SMALLINT,
    ADD COLUMN IF NOT EXISTS money_style     SMALLINT,
    ADD COLUMN IF NOT EXISTS share_stuff     SMALLINT,
    ADD COLUMN IF NOT EXISTS persona         CHAR(1),
    ADD COLUMN IF NOT EXISTS is_simulated    BOOLEAN DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS src             VARCHAR(10);     -- 'form' | 'app' | 'seed'

ALTER TABLE match_requests
    ADD COLUMN IF NOT EXISTS note            TEXT,
    ADD COLUMN IF NOT EXISTS score_breakdown JSONB,
    ADD COLUMN IF NOT EXISTS responded_at    TIMESTAMPTZ;
-- status: pending | accepted | rejected | unmatched (hủy ghép từ khung chat)

-- "Hoạt động X phút trước" khi người kia offline
ALTER TABLE users ADD COLUMN IF NOT EXISTS last_seen_at TIMESTAMPTZ;

-- ---------------------------------------------------------------------------
-- 2. Swipe (Phần III 3.8). Hai 'like' đối nhau ⇒ match (match_requests accepted)
--    + conversation, trong CÙNG transaction (matching/repo.py).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS swipes (
    id             SERIAL PRIMARY KEY,
    user_id        INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    target_id      INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    decision       VARCHAR(6) NOT NULL CHECK (decision IN ('like', 'pass')),
    score_at_swipe REAL,
    features       JSONB,                      -- {d_k} snapshot — server ghi, không tin FE
    deck_position  SMALLINT,
    deck_mode      VARCHAR(10),                -- 'ranked' | 'random'
    decided_ms     INTEGER,
    created_at     TIMESTAMPTZ DEFAULT now(),
    updated_at     TIMESTAMPTZ DEFAULT now(),
    UNIQUE (user_id, target_id),
    CHECK (user_id <> target_id)
);
CREATE INDEX IF NOT EXISTS idx_swipes_target ON swipes (target_id, decision);

-- ---------------------------------------------------------------------------
-- 3. Hội thoại. conversations + members (hỗ trợ N người — UI phiên này chỉ 1-1).
--    KHÔNG tạo bằng tay: chỉ sinh khi match (không nhắn được cho người chưa ghép).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS conversations (
    id          SERIAL PRIMARY KEY,
    kind        VARCHAR(10) NOT NULL DEFAULT 'pair',   -- 'pair' | 'group' (group: chưa mở UI)
    match_id    INTEGER UNIQUE REFERENCES match_requests(id) ON DELETE SET NULL,
    created_at  TIMESTAMPTZ DEFAULT now(),
    last_message_at TIMESTAMPTZ DEFAULT now()          -- sắp xếp danh sách hội thoại
);

CREATE TABLE IF NOT EXISTS conversation_members (
    conversation_id      INTEGER NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    user_id              INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    last_read_message_id INTEGER NOT NULL DEFAULT 0,   -- "Đã xem" + đếm chưa đọc
    last_read_at         TIMESTAMPTZ,
    contact_consent      BOOLEAN DEFAULT FALSE,        -- T3 (lộ liên hệ) — để dành, chưa mở UI
    joined_at            TIMESTAMPTZ DEFAULT now(),
    PRIMARY KEY (conversation_id, user_id)
);
CREATE INDEX IF NOT EXISTS idx_conv_members_user ON conversation_members (user_id);

CREATE TABLE IF NOT EXISTS messages (
    id               SERIAL PRIMARY KEY,
    conversation_id  INTEGER NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    sender_id        INTEGER REFERENCES users(id) ON DELETE CASCADE,  -- NULL = tin hệ thống
    kind             VARCHAR(10) NOT NULL DEFAULT 'text',             -- text | image | listing | system
    body             TEXT,
    payload          JSONB,       -- image: {images:[{id,w,h}]} · listing: snapshot tin trọ
    client_id        VARCHAR(40), -- idempotency cho optimistic send (FE tự sinh)
    created_at       TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_messages_conv ON messages (conversation_id, id);   -- id tăng dần = cursor
CREATE UNIQUE INDEX IF NOT EXISTS uq_messages_client
    ON messages (conversation_id, sender_id, client_id) WHERE client_id IS NOT NULL;

-- Ảnh gửi trong chat: file nằm ở MEDIA_DIR/chat/<id>.jpg (đã re-encode, xoá EXIF/GPS).
-- Tải ảnh phải qua GET /chat/media/{id} — kiểm tra thành viên hội thoại, không public.
CREATE TABLE IF NOT EXISTS chat_media (
    id               UUID PRIMARY KEY,
    conversation_id  INTEGER NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    uploader_id      INTEGER REFERENCES users(id) ON DELETE SET NULL,
    width            INTEGER,
    height           INTEGER,
    bytes            INTEGER,
    created_at       TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_chat_media_conv ON chat_media (conversation_id);

-- Báo cáo người dùng từ khung chat (khác `reports` của tin trọ)
CREATE TABLE IF NOT EXISTS user_reports (
    id               SERIAL PRIMARY KEY,
    reporter_id      INTEGER REFERENCES users(id) ON DELETE SET NULL,
    target_id        INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    conversation_id  INTEGER REFERENCES conversations(id) ON DELETE SET NULL,
    reason           VARCHAR(30) NOT NULL,   -- spam | harass | fake | scam | other
    note             TEXT,
    status           VARCHAR(20) DEFAULT 'pending',
    created_at       TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_user_reports_status ON user_reports (status);
