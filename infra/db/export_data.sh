#!/usr/bin/env bash
# Xuất dữ liệu đã crawl ra CSV (kèm liên hệ + địa chỉ chuẩn của migration 91).
#   bash infra/db/export_data.sh            → exports/ cạnh repo
#   OUT=/duong/dan bash infra/db/export_data.sh
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
OUT="${OUT:-$ROOT/exports}"; mkdir -p "$OUT"
DB="${DB_CONTAINER:-nckh-db-1}"
docker inspect "$DB" >/dev/null 2>&1 || { echo "Không thấy container '$DB':"; docker ps --format '  {{.Names}}'; exit 1; }
q(){ if docker exec -i "$DB" psql -U nckh -d nckh -q -c "COPY ($2) TO STDOUT WITH CSV HEADER" > "$OUT/$1" 2>"$OUT/.err"; then
       echo "  ✓ $1  ($(( $(wc -l < "$OUT/$1") - 1 )) dòng)"
     else echo "  ✗ $1 — $(head -2 "$OUT/.err" | tr '\n' ' ')"; rm -f "$OUT/$1"; fi; }

q listings.csv "SELECT id, source, source_id, source_url, title, price, area, listing_type,
  address_full, street, ward, district_norm, address_confidence, address_source,
  contact_phone, contact_phone_alt, contact_zalo, contact_name, contact_facebook, contact_source,
  ST_Y(geom) AS lat, ST_X(geom) AS lng, geocode_confidence, distance_to_ctu,
  electricity_price, water_price, water_unit, utility_state_price,
  deposit_amount, deposit_months, gender_only, curfew_hour, free_hours,
  status, quality_score, first_seen, last_seen
  FROM aggregated_listings ORDER BY id"

q places.csv "SELECT id, provider_place_id, name, address, ward, district_norm, phone, website,
  business_status, ST_Y(geom) AS lat, ST_X(geom) AS lng, rating, rating_count,
  primary_type, listing_id, match_distance_m, maps_uri, fetched_at FROM places ORDER BY id"

q place_reviews.csv "SELECT r.id, r.place_id, p.name AS place_name, r.rating, r.sentiment,
  replace(replace(coalesce(r.text,''), chr(10), ' '), chr(13), ' ') AS text,
  r.author_name, r.published_at, r.relative_time
  FROM place_reviews r LEFT JOIN places p ON p.id = r.place_id ORDER BY r.id"

q reviews_ugc.csv "SELECT id, listing_id, place_id, user_id, rating, tags, content, stay_period,
  status, created_at FROM reviews ORDER BY id"

q crawl_runs.csv "SELECT source, mode, started_at, finished_at, fetched, new_count, updated_count,
  expired_count, error FROM crawl_runs ORDER BY started_at DESC LIMIT 200"

q summary_by_source.csv "SELECT source, count(*) AS tin,
  count(*) FILTER (WHERE status='active') AS active,
  count(*) FILTER (WHERE geocode_confidence='high') AS toado_high,
  count(address_full) AS co_dia_chi,
  count(*) FILTER (WHERE address_confidence IN ('exact','street')) AS dia_chi_ro,
  count(contact_phone) AS co_sdt, count(contact_zalo) AS co_zalo, count(contact_name) AS co_ten,
  count(electricity_price) AS co_gia_dien, count(water_price) AS co_gia_nuoc,
  count(gender_only) AS co_gioi_tinh, round(avg(price)) AS gia_tb
  FROM aggregated_listings GROUP BY source ORDER BY tin DESC"

# SĐT xuất hiện ở nhiều tin: hoặc là chủ trọ đăng nhiều tin, HOẶC là hotline của chính
# trang rao vặt bị bắt nhầm → thêm vào "ignore_phones" trong crawler/sources/<nguồn>.json.
q phone_duplicates.csv "SELECT contact_phone, count(*) AS so_tin,
  count(DISTINCT source) AS so_nguon, string_agg(DISTINCT source, ',') AS nguon
  FROM aggregated_listings WHERE contact_phone IS NOT NULL
  GROUP BY contact_phone HAVING count(*) > 1 ORDER BY so_tin DESC"

rm -f "$OUT/.err"; echo; echo "Xong → $OUT"
