-- 90: thuộc tính mềm (điện/nước/cọc/giới tính/giờ giấc) + review từ Google Maps + review UGC.
-- Idempotent: chạy lại được trên DB đang có dữ liệu.
--   docker compose exec -T db psql -U nckh -d nckh < infra/db/migrations/90_extras_reviews.sql

-- ── 1. Thuộc tính mềm trích từ mô tả (apps/api/app/crawler/extras.py) ────────
ALTER TABLE aggregated_listings
    ADD COLUMN IF NOT EXISTS electricity_price   INTEGER,      -- VND/kWh
    ADD COLUMN IF NOT EXISTS water_price         INTEGER,      -- VND, xem water_unit
    ADD COLUMN IF NOT EXISTS water_unit          VARCHAR(10),  -- 'm3' | 'person' | 'month'
    ADD COLUMN IF NOT EXISTS utility_state_price BOOLEAN,      -- điện nước giá nhà nước
    ADD COLUMN IF NOT EXISTS deposit_amount      INTEGER,      -- VND
    ADD COLUMN IF NOT EXISTS deposit_months      REAL,         -- 0 = không cọc
    ADD COLUMN IF NOT EXISTS gender_only         VARCHAR(5),   -- 'nu' | 'nam' | NULL
    ADD COLUMN IF NOT EXISTS curfew_hour         SMALLINT,     -- 23 = khoá cổng 23h
    ADD COLUMN IF NOT EXISTS free_hours          BOOLEAN,      -- giờ giấc tự do
    ADD COLUMN IF NOT EXISTS extras_extracted_at TIMESTAMPTZ;  -- NULL = chưa trích (backfill)

CREATE INDEX IF NOT EXISTS idx_listings_gender_only ON aggregated_listings (gender_only)
    WHERE gender_only IS NOT NULL;

-- ── 2. Địa điểm nhà trọ trên Google Maps (Places API New) ────────────────────
-- 1 place = 1 nhà trọ vật lý có trên Google Maps (khác với listing = 1 tin đăng).
CREATE TABLE IF NOT EXISTS places (
    id                  SERIAL PRIMARY KEY,
    provider            VARCHAR(20) NOT NULL DEFAULT 'google',
    provider_place_id   TEXT NOT NULL,
    name                TEXT,
    address             TEXT,
    geom                GEOMETRY(Point, 4326),
    rating              REAL,
    rating_count        INTEGER,
    maps_uri            TEXT,
    primary_type        VARCHAR(50),
    -- ghép với tin đăng gần nhất (≤ match_distance_m) — NULL nếu không có tin nào gần
    listing_id          INTEGER REFERENCES aggregated_listings(id) ON DELETE SET NULL,
    match_distance_m    REAL,
    fetched_at          TIMESTAMPTZ DEFAULT now(),
    UNIQUE (provider, provider_place_id)
);
CREATE INDEX IF NOT EXISTS idx_places_geom ON places USING GIST (geom);
CREATE INDEX IF NOT EXISTS idx_places_listing ON places (listing_id);

-- Review Google (tối đa 5/place theo API). sentiment suy từ rating để risk engine dùng nhanh.
CREATE TABLE IF NOT EXISTS place_reviews (
    id                  SERIAL PRIMARY KEY,
    place_id            INTEGER NOT NULL REFERENCES places(id) ON DELETE CASCADE,
    provider_review_id  TEXT,                     -- reviews[].name (ổn định)
    rating              SMALLINT,
    text                TEXT,
    language            VARCHAR(8),
    author_name         TEXT,
    published_at        TIMESTAMPTZ,
    relative_time       TEXT,
    sentiment           VARCHAR(10),              -- 'negative' (≤2) | 'neutral' (3) | 'positive' (≥4)
    fetched_at          TIMESTAMPTZ DEFAULT now(),
    UNIQUE (provider_review_id)
);
CREATE INDEX IF NOT EXISTS idx_place_reviews_place ON place_reviews (place_id);
CREATE INDEX IF NOT EXISTS idx_place_reviews_negative ON place_reviews (place_id)
    WHERE sentiment = 'negative';

-- ── 3. Review do sinh viên đăng trên hệ thống (UGC) ─────────────────────────
-- Gắn vào listing HOẶC place (trọ có trên Maps nhưng chưa có tin đăng).
CREATE TABLE IF NOT EXISTS reviews (
    id          SERIAL PRIMARY KEY,
    listing_id  INTEGER REFERENCES aggregated_listings(id) ON DELETE CASCADE,
    place_id    INTEGER REFERENCES places(id) ON DELETE CASCADE,
    user_id     INTEGER REFERENCES users(id) ON DELETE SET NULL,
    rating      SMALLINT NOT NULL CHECK (rating BETWEEN 1 AND 5),
    -- tag chuẩn hoá để risk engine đếm được, FE render chip:
    -- coc_khong_tra | gia_khong_dung | dien_nuoc_cao | an_ninh_kem | on_ao | ngap_nuoc
    -- | chu_kho_chiu | chu_tot | sach_se | yen_tinh
    tags        TEXT[] DEFAULT '{}',
    content     TEXT,
    stay_period VARCHAR(20),                      -- vd '2025-2026'
    status      VARCHAR(20) DEFAULT 'visible',    -- visible | hidden | flagged
    created_at  TIMESTAMPTZ DEFAULT now(),
    CHECK (listing_id IS NOT NULL OR place_id IS NOT NULL)
);
CREATE INDEX IF NOT EXISTS idx_reviews_listing ON reviews (listing_id, status);
CREATE INDEX IF NOT EXISTS idx_reviews_place ON reviews (place_id, status);
