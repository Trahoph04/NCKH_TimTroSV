-- Bản đồ v2 (docs/specs/Map_MapLibre_POI.md): loại chỗ ở nhà mini, nhãn sang nhượng,
-- tiện ích OSM, cache đường đi ORS. Idempotent — DB đang chạy apply tay được nhiều lần.

-- Minihouse / căn hộ mini / studio: SV thuê nhiều (3–4,5 tr, đủ nội thất) nhưng classifier cũ
-- dồn vào 'khac' (bị ẩn) hoặc 'phong_tro' nhờ luật dự phòng giá/diện tích.
-- ADD VALUE không dùng được trong cùng transaction với câu dùng nó → file này KHÔNG bọc BEGIN.
ALTER TYPE listing_type_enum ADD VALUE IF NOT EXISTS 'nha_mini';

-- NULL = thuê trực tiếp/không rõ; 'lease_transfer' = pass phòng/sang nhượng — điều khoản cọc
-- và hợp đồng do người thuê cũ nói, phải hiện nhãn riêng.
ALTER TABLE aggregated_listings ADD COLUMN IF NOT EXISTS offer_kind VARCHAR(16);

-- Tiện ích quanh CTU lấy 1 lần từ OpenStreetMap (Overpass). (osm_type, osm_id) là khoá tự nhiên
-- của OSM: node/way/relation có thể trùng số id với nhau.
CREATE TABLE IF NOT EXISTS pois (
    id          SERIAL PRIMARY KEY,
    osm_type    VARCHAR(8)  NOT NULL,
    osm_id      BIGINT      NOT NULL,
    category    VARCHAR(20) NOT NULL,
    name        TEXT,
    geom        geometry(Point, 4326) NOT NULL,
    tags        JSONB,
    fetched_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (osm_type, osm_id)
);
CREATE INDEX IF NOT EXISTS idx_pois_geom ON pois USING GIST (geom);
CREATE INDEX IF NOT EXISTS idx_pois_category ON pois (category);

-- Đường đi ORS đã tính: dữ liệu có ~120 toạ độ phân biệt (geocode cấp phường) nên lưu hết được,
-- demo không phụ thuộc quota/mạng tới ORS. Toạ độ gốc làm tròn 5 chữ số (~1 m).
CREATE TABLE IF NOT EXISTS route_cache (
    origin_lat  NUMERIC(8, 5) NOT NULL,
    origin_lng  NUMERIC(8, 5) NOT NULL,
    campus      SMALLINT      NOT NULL,
    profile     VARCHAR(20)   NOT NULL,
    path        JSONB         NOT NULL,      -- [[lat, lng], ...] — đúng thứ tự FE vẽ
    fetched_at  TIMESTAMPTZ   NOT NULL DEFAULT now(),
    PRIMARY KEY (origin_lat, origin_lng, campus, profile)
);
