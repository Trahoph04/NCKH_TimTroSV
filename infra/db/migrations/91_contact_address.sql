-- 91: thông tin liên hệ (SĐT/Zalo/tên chủ) + địa chỉ chuẩn hoá + SĐT của place Google.
-- Idempotent: chạy lại được trên DB đang có dữ liệu.
--   docker compose exec -T db psql -U nckh -d nckh < infra/db/migrations/91_contact_address.sql

-- ── 1. Liên hệ (app/crawler/contact.py) ─────────────────────────────────────
-- CHỈ lưu thông tin người đăng TỰ GHI công khai trong tin, hoặc SĐT doanh nghiệp
-- do Google Places API trả về. KHÔNG bỏ qua cơ chế che số của nguồn.
-- Dữ liệu cá nhân (NĐ 13/2023): không công khai SĐT trên UI cho người chưa đăng nhập.
ALTER TABLE aggregated_listings
    ADD COLUMN IF NOT EXISTS contact_phone      VARCHAR(15),   -- đã chuẩn hoá 0xxxxxxxxx
    ADD COLUMN IF NOT EXISTS contact_phone_alt  VARCHAR(15),
    ADD COLUMN IF NOT EXISTS contact_zalo       VARCHAR(15),
    ADD COLUMN IF NOT EXISTS contact_name       VARCHAR(80),   -- "Chị Hạnh", "A Tuấn"
    ADD COLUMN IF NOT EXISTS contact_facebook   TEXT,
    ADD COLUMN IF NOT EXISTS contact_source     VARCHAR(20),   -- description|detail_page|listing_field|google_places|ugc
    ADD COLUMN IF NOT EXISTS contact_extracted_at TIMESTAMPTZ;

-- Tin cùng SĐT = cùng chủ trọ → dùng để gộp tin trùng & đếm "chủ đăng nhiều tin".
CREATE INDEX IF NOT EXISTS idx_listings_contact_phone ON aggregated_listings (contact_phone)
    WHERE contact_phone IS NOT NULL;

-- ── 2. Địa chỉ rõ ràng (app/crawler/address.py) ─────────────────────────────
ALTER TABLE aggregated_listings
    ADD COLUMN IF NOT EXISTS address_full       TEXT,          -- "85/26 Phạm Ngũ Lão, P. Thới Bình, Q. Ninh Kiều, Cần Thơ"
    ADD COLUMN IF NOT EXISTS street             TEXT,          -- "Phạm Ngũ Lão" (kèm hẻm/số nhà nếu có)
    ADD COLUMN IF NOT EXISTS ward               VARCHAR(60),   -- "Thới Bình"
    ADD COLUMN IF NOT EXISTS district_norm      VARCHAR(30),   -- "Ninh Kiều" — 1 dạng duy nhất, thay cột district tự do
    ADD COLUMN IF NOT EXISTS address_confidence VARCHAR(10),   -- exact | street | ward | district | none
    ADD COLUMN IF NOT EXISTS address_source     VARCHAR(20),   -- source | detail_page | description | reverse_geocode
    ADD COLUMN IF NOT EXISTS address_normalized_at TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS idx_listings_district_norm ON aggregated_listings (district_norm);
CREATE INDEX IF NOT EXISTS idx_listings_ward ON aggregated_listings (ward);

-- ── 3. Place Google: SĐT + website + giờ mở cửa ─────────────────────────────
ALTER TABLE places
    ADD COLUMN IF NOT EXISTS phone           VARCHAR(20),
    ADD COLUMN IF NOT EXISTS phone_intl      VARCHAR(25),
    ADD COLUMN IF NOT EXISTS website         TEXT,
    ADD COLUMN IF NOT EXISTS business_status VARCHAR(30),
    ADD COLUMN IF NOT EXISTS opening_hours   TEXT[],
    ADD COLUMN IF NOT EXISTS ward            VARCHAR(60),
    ADD COLUMN IF NOT EXISTS district_norm   VARCHAR(30);

-- ── 4. Sửa lỗi UNIQUE của place_reviews (migration 90) ──────────────────────
-- provider_review_id NULL được phép lặp trong Postgres → review không có `name`
-- bị nhân bản mỗi lần chạy lại script. Ràng buộc mới: duy nhất theo (place, tác giả, thời điểm).
DELETE FROM place_reviews a USING place_reviews b
    WHERE a.id > b.id AND a.place_id = b.place_id
      AND a.provider_review_id IS NOT DISTINCT FROM b.provider_review_id
      AND a.author_name IS NOT DISTINCT FROM b.author_name
      AND a.published_at IS NOT DISTINCT FROM b.published_at;

CREATE UNIQUE INDEX IF NOT EXISTS uq_place_reviews_fallback
    ON place_reviews (place_id, coalesce(author_name, ''), coalesce(published_at, 'epoch'::timestamptz))
    WHERE provider_review_id IS NULL;
