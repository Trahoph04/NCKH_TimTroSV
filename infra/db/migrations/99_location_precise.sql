-- Cờ vị trí chính xác (app.cleaner.audit, ADR-022 sửa đổi 07/10): TRUE = người đăng tự ghim / có số nhà và nằm đúng
-- đường; FALSE = chỉ tới cấp phường/đường. Bản đồ mặc định chỉ cắm ghim tin TRUE (tin FALSE dồn cục ở điểm phường);
-- danh sách/gợi ý vẫn dùng tin FALSE kèm nhãn "vị trí tương đối". NULL = chưa rà soát.
ALTER TABLE aggregated_listings ADD COLUMN IF NOT EXISTS location_precise BOOLEAN;
