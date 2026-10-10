-- Đánh giá mù hệ gợi ý nhà trọ (docs/specs/Recommendation.md R10). Idempotent.
-- Pooling kiểu TREC: mọi tin nằm trong top-10 của BẤT KỲ hệ nào (đề xuất / B-giá / B-cosine) thành 1 thẻ,
-- xáo trộn, SV chấm 0–2. Hạng của từng hệ lưu ở server — FE không biết thẻ nào của hệ nào.

CREATE TABLE IF NOT EXISTS rec_eval_sessions (
    id            BIGSERIAL PRIMARY KEY,
    user_id       INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    criteria      JSONB NOT NULL,              -- Query đã dùng (ngân sách, khu, phút, loại, tiện ích, top-3)
    relaxed       TEXT[],                      -- ràng buộc hệ đề xuất đã nới (nếu có)
    algo_ver      VARCHAR(20) NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at  TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_rec_eval_sessions_user ON rec_eval_sessions (user_id, created_at DESC);

-- listing_id KHÔNG khoá ngoại: tin có thể bị gỡ sau buổi thử nghiệm nhưng phán đoán vẫn phải giữ nguyên.
CREATE TABLE IF NOT EXISTS rec_eval_cards (
    session_id      BIGINT NOT NULL REFERENCES rec_eval_sessions(id) ON DELETE CASCADE,
    listing_id      INTEGER NOT NULL,
    card_code       VARCHAR(8) NOT NULL UNIQUE,  -- mã in trên thẻ, không lộ hệ
    display_pos     SMALLINT NOT NULL,           -- 0-based, thứ tự đã hiển thị
    rank_proposed   SMALLINT,                    -- 1..10; NULL = hệ đó không xếp tin này vào top-10
    rank_price      SMALLINT,
    rank_cosine     SMALLINT,
    utility         REAL,                        -- điểm MAUT của tin (để phân tích, không hiển thị)
    relevance       SMALLINT CHECK (relevance BETWEEN 0 AND 2),  -- 0 không quan tâm · 1 có thể xem · 2 sẽ liên hệ
    judged_at       TIMESTAMPTZ,
    PRIMARY KEY (session_id, listing_id)
);
