-- 93_matching_deck.sql — Deck log + hồ sơ ở ghép: 2 cột còn thiếu cho lọc cứng.
-- Thiết kế: docs/tech_specs/Matching_Messaging_Design.md (II 2.10, III 3.6/3.8)
-- Chạy SAU 92_matching_chat.sql. Idempotent để apply tay vào DB đang chạy.

-- ---------------------------------------------------------------------------
-- 1. deck_log — server ghi lại ĐÚNG những gì đã hiển thị cho ai.
--
--    VÌ SAO CẦN BẢNG NÀY (không phải "ghi log cho vui"): bản trước nhận
--    deck_position / deck_mode / score TỪ BODY DO FE GỬI. Đó chính là dữ liệu
--    dùng để chứng minh đã khử thiên lệch vị trí (doc 3.6) — để client tự khai
--    thì bằng chứng mất giá trị, và client sửa được số liệu nghiên cứu.
--    Giờ: GET /matching/deck ghi vào đây, POST /matching/swipe ĐỌC lại từ đây.
--
--    Bảng này cũng là nguồn đo CONGESTION: đếm số lần một hồ sơ được đưa ra
--    (times_shown) → hệ số Gini của exposure. Ở pool nhỏ, vài hồ sơ "trung tính
--    mọi chiều" sẽ xuất hiện trong deck của tất cả mọi người và hứng hết lời
--    mời — xem Fair Reciprocal Recommendation (RecSys 2024).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS deck_log (
    id            BIGSERIAL PRIMARY KEY,
    user_id       INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    target_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    position      SMALLINT NOT NULL,          -- 0-based, thứ tự thật đã render
    score         REAL,                       -- harmonic mean lúc hiển thị
    s_ab          REAL,                       -- điểm có hướng A→B
    s_ba          REAL,                       -- điểm có hướng B→A
    features      JSONB,                      -- {d_k} snapshot — BẮT BUỘC để huấn luyện lại
    deck_mode     VARCHAR(10) NOT NULL,       -- 'ranked' | 'random' (random = buổi thử nghiệm)
    weights_ver   VARCHAR(20),                -- bộ trọng số nào đã sinh ra điểm này
    served_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (user_id <> target_id)
);
-- Tra cứu lúc swipe: lần hiển thị GẦN NHẤT của đúng cặp đó
CREATE INDEX IF NOT EXISTS idx_deck_log_pair ON deck_log (user_id, target_id, served_at DESC);
-- Đo exposure/congestion
CREATE INDEX IF NOT EXISTS idx_deck_log_target ON deck_log (target_id, served_at DESC);

-- ---------------------------------------------------------------------------
-- 2. Hai cột lọc cứng mà form v2 đã hỏi nhưng mig 92 bỏ sót.
--    need_from: thời điểm cần phòng — hai người lệch quá xa thì không đi thuê
--    cùng nhau được, dù hồ sơ lối sống khớp 100%.
-- ---------------------------------------------------------------------------
ALTER TABLE roommate_profiles
    ADD COLUMN IF NOT EXISTS need_from      VARCHAR(40),  -- nguyên văn lựa chọn câu E1
    ADD COLUMN IF NOT EXISTS roommate_status VARCHAR(60); -- 'đã có phòng' | 'chưa có phòng' | ...

-- Pool scan: deck quét toàn bộ hồ sơ cùng giới mỗi request. Ở N nhỏ thì seq scan
-- cũng nhanh, nhưng index này giữ cho truy vấn không xấu đi khi pool lớn dần.
CREATE INDEX IF NOT EXISTS idx_roommate_pool
    ON roommate_profiles (gender) WHERE gender IS NOT NULL;

-- Hạ ưu tiên 'pass' 7 ngày (doc 3.5 mục 2): pass KHÔNG vĩnh viễn vì ở pool nhỏ
-- xoá vĩnh viễn là đốt pool. Cần truy vấn theo thời điểm quyết định.
CREATE INDEX IF NOT EXISTS idx_swipes_user_decision
    ON swipes (user_id, decision, updated_at DESC);
