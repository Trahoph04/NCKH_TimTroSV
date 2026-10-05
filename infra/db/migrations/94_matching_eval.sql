-- 94_matching_eval.sql — Dữ liệu cho đánh giá ghép bạn ở (buổi thử nghiệm 10/2026).
-- Thiết kế: docs/tech_specs/Matching_Messaging_Design.md (II 2.7, II 2.10, III 3.4/3.6)
-- Chạy SAU 93_matching_deck.sql. Idempotent để apply tay vào DB đang chạy.

-- ---------------------------------------------------------------------------
-- 1. deck_log.explore — thẻ nào KHÔNG được chọn theo điểm.
--      'epsilon' : ε-greedy, thẻ ngoài top được kéo vào (3.4 [R3])
--      'spread'  : deck buổi thử nghiệm, ứng viên lệch tiêu chí KHẢ THI (3.6)
--      NULL      : chọn theo điểm như thường
--    Notebook PHẢI tách hai nhóm này khi tính P@k/NDCG, nếu không thẻ khám phá
--    (cố ý chọn điểm thấp) sẽ kéo tụt số đo của thuật toán.
-- ---------------------------------------------------------------------------
ALTER TABLE deck_log ADD COLUMN IF NOT EXISTS explore VARCHAR(10);

-- ---------------------------------------------------------------------------
-- 2. match_requests: cho phép ghép LẠI sau khi huỷ mà không mất vết.
--    UNIQUE (from_user, to_user) cũ buộc create_match() phải UPDATE dòng cũ từ
--    'unmatched' về 'accepted' ⇒ thống kê "bao nhiêu cặp huỷ ghép" mất dữ liệu.
--    Giờ: mỗi lần ghép là một dòng; chỉ cấm HAI dòng ĐANG HIỆU LỰC cho một cặp
--    (không phụ thuộc chiều).
-- ---------------------------------------------------------------------------
ALTER TABLE match_requests DROP CONSTRAINT IF EXISTS match_requests_from_user_to_user_key;
CREATE UNIQUE INDEX IF NOT EXISTS uq_match_active_pair
    ON match_requests (LEAST(from_user, to_user), GREATEST(from_user, to_user))
    WHERE status IN ('pending', 'accepted');

-- ---------------------------------------------------------------------------
-- 3. Chấm điểm làm mù 1–5 (doc 2.7): 5 thẻ/người = 3 của thuật toán + 2 ngẫu
--    nhiên trong pool, xáo thứ tự, ẩn %. So hai nhóm bằng Wilcoxon; P@3/NDCG@3
--    tính trên nhóm 'algo'. Xuất CSV: python -m app.matching.export_ratings
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS roommate_ratings (
    id            BIGSERIAL PRIMARY KEY,
    rater_id      INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    target_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    round         SMALLINT NOT NULL DEFAULT 1,
    card_code     VARCHAR(8) NOT NULL,          -- mã in trên thẻ, không lộ nhóm
    arm           VARCHAR(6) NOT NULL CHECK (arm IN ('algo', 'random')),
    algo_rank     SMALLINT,                     -- 1..3 với 'algo', NULL với 'random'
    display_pos   SMALLINT NOT NULL,            -- 0-based, thứ tự đã hiển thị
    score         REAL,                         -- điểm thuật toán của cặp (cả 2 nhóm)
    s_ab          REAL,
    s_ba          REAL,
    weights_ver   VARCHAR(20),
    target_is_simulated BOOLEAN NOT NULL DEFAULT FALSE,
    rating        SMALLINT CHECK (rating BETWEEN 1 AND 5),
    served_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    rated_at      TIMESTAMPTZ,
    UNIQUE (rater_id, round, target_id),
    UNIQUE (rater_id, round, card_code),
    CHECK (rater_id <> target_id)
);
CREATE INDEX IF NOT EXISTS idx_ratings_rater ON roommate_ratings (rater_id, round);

-- ---------------------------------------------------------------------------
-- 4. Hai hồ sơ seed (user 2, 3) bị kẹt ngoài pool vĩnh viễn: 80_seeds.sql chạy
--    TRƯỚC 92 (thứ tự COPY trong infra/db/Dockerfile) nên chỉ ghi được
--    gender_pref (cột đã ngưng dùng), không có gender. Suy gender từ bio/seed.
--    Gắn is_simulated = TRUE: đây là tài khoản mẫu, không bao giờ quẹt lại —
--    để lẫn vào nhóm "thật" thì làm hỏng đúng số liệu ưu tiên hồ sơ thật (1.3).
-- ---------------------------------------------------------------------------
UPDATE roommate_profiles
   SET gender = CASE user_id WHEN 2 THEN 'nam' WHEN 3 THEN 'nu' END,
       is_simulated = TRUE,
       src = COALESCE(src, 'seed')
 WHERE user_id IN (2, 3) AND gender IS NULL;
