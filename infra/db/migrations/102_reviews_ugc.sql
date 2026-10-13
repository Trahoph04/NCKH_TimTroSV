-- Đánh giá nhà trọ do sinh viên viết (thuyết minh THS2026-66, sản phẩm dòng 6 "nhắn tin, trao đổi, đánh giá"; 14.2
-- "cảnh báo thông tin rủi ro"). Dùng lại bảng `reviews` của mig 90 (sao 1–5 + tag chuẩn hoá + nhận xét).
-- Mỗi tài khoản một đánh giá cho mỗi tin (sửa = ghi đè) ⇒ một người không tự đẩy/dìm điểm bằng nhiều lượt.
CREATE UNIQUE INDEX IF NOT EXISTS uq_reviews_listing_user
    ON reviews (listing_id, user_id) WHERE listing_id IS NOT NULL AND user_id IS NOT NULL;
ALTER TABLE reviews ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT now();
