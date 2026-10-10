-- Rà soát chất lượng dữ liệu (07/10/2026, app.cleaner.audit): tin bị loại vẫn nằm trong DB với lý do, để báo cáo
-- đếm được "loại bao nhiêu, vì sao" và khôi phục được. Tin đã gỡ khỏi nguồn → status 'expired' (crawler tự bật lại
-- nếu tin xuất hiện lại); tin bẩn khác → status 'hidden' (upsert của crawler không đụng tới 'hidden').
ALTER TABLE aggregated_listings ADD COLUMN IF NOT EXISTS audit_reason TEXT;
ALTER TABLE aggregated_listings ADD COLUMN IF NOT EXISTS audit_at TIMESTAMPTZ;
