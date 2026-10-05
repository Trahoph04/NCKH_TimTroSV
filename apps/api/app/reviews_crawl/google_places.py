"""Lấy nhà trọ + review từ Google Maps quanh 3 khu CTU qua **Places API (New)**.

Vì sao dùng API chính thức thay vì cào giao diện Google Maps:
  - cào giao diện vi phạm ToS Google, dễ bị chặn, không tái lập được → hội đồng hỏi "dữ liệu lấy hợp lệ không?"
  - Places API trả đúng: tên, địa chỉ, toạ độ, rating, số lượt đánh giá và **tối đa 5 review/place**
  - Text Search (Enterprise + Atmosphere SKU vì có `places.reviews`) có hạn mức miễn phí hàng tháng
    (~1.000 request); toàn bộ script này ≈ 5 query × 3 khu × ≤3 trang = ≤45 request → 0 đồng.

Cần: GOOGLE_PLACES_API_KEY trong .env (Google Cloud Console → bật "Places API (New)").

Chạy:
  docker compose exec api python -m app.reviews_crawl.google_places --dry-run     # chỉ in, không ghi DB
  docker compose exec api python -m app.reviews_crawl.google_places               # ghi DB + CSV
  docker compose exec api python -m app.reviews_crawl.google_places --radius 3000 --csv /app/google_reviews.csv

Output DB: bảng `places`, `place_reviews` (migration 90). Mỗi place được ghép với tin đăng
gần nhất trong ≤ MATCH_M mét (ưu tiên tin có toạ độ 'high', tức nhatot/survey/user).
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import json
import logging
import sys
from datetime import datetime, timezone

import httpx
from sqlalchemy import create_engine, text

from ..config import settings
from ..crawler.address import canon_district, canon_ward
from ..crawler.contact import normalize_phone
from ..crawler.geocode import haversine_m

# 3 khu CTU (lat, lng) — NGUỒN CHUẨN ở listings/routing.py CAMPUSES; copy để script không kéo
# theo fastapi/auth khi chạy CLI. Đổi ở đó thì đổi ở đây.
CAMPUSES: list[tuple[float, float]] = [
    (10.0159, 105.7656),  # khu I
    (10.0322, 105.7683),  # khu II
    (10.0340, 105.7798),  # khu III
]

log = logging.getLogger("reviews.google")

TEXT_SEARCH = "https://places.googleapis.com/v1/places:searchText"
FIELD_MASK = ",".join([
    "places.id", "places.displayName", "places.formattedAddress", "places.location",
    "places.rating", "places.userRatingCount", "places.googleMapsUri", "places.primaryType",
    "places.reviews",
    # liên hệ + địa chỉ rõ ràng (migration 91)
    "places.nationalPhoneNumber", "places.internationalPhoneNumber", "places.websiteUri",
    "places.businessStatus", "places.regularOpeningHours.weekdayDescriptions",
    "places.addressComponents",
    "nextPageToken",
])
QUERIES = ["nhà trọ", "phòng trọ", "nhà trọ sinh viên", "khu trọ", "ký túc xá"]
# Review Google ở Cần Thơ thưa → chỉ quét quanh 3 cổng trường sẽ sót phần lớn khu trọ.
# Thêm vành đai 4 điểm cách mỗi khu ~1.5 km (≈0.0135° lat, 0.0137° lng).
RING_OFFSETS = [(0.0135, 0.0), (-0.0135, 0.0), (0.0, 0.0137), (0.0, -0.0137)]


def search_points(grid: bool) -> list[tuple[float, float]]:
    """3 khu CTU, cộng vành đai nếu --grid (nhiều request hơn, phủ rộng hơn)."""
    pts = list(CAMPUSES)
    if grid:
        for lat, lng in CAMPUSES:
            for dlat, dlng in RING_OFFSETS:
                p = (round(lat + dlat, 5), round(lng + dlng, 5))
                if all(haversine_m(p[0], p[1], q[0], q[1]) > 800 for q in pts):
                    pts.append(p)
    return pts
MAX_PAGES = 3          # 3 × 20 = 60 place / (query, khu)
MATCH_M = 60.0         # place ↔ listing coi là cùng nhà nếu ≤ 60 m
MAX_DIST_CAMPUS_M = 4000.0  # loại place quá xa mọi khu CTU (lưới quét rộng hơn bán kính bias)
CAMPUS_NAMES = ["khu I", "khu II", "khu III"]


def _sentiment(rating: int | None) -> str | None:
    if rating is None:
        return None
    return "negative" if rating <= 2 else "neutral" if rating == 3 else "positive"


async def search_text(client: httpx.AsyncClient, query: str, lat: float, lng: float,
                      radius_m: float, page_token: str | None = None) -> dict:
    body = {
        "textQuery": query,
        "languageCode": "vi",
        "regionCode": "VN",
        "pageSize": 20,
        "locationBias": {"circle": {"center": {"latitude": lat, "longitude": lng},
                                    "radius": float(radius_m)}},
    }
    if page_token:
        body["pageToken"] = page_token
    r = await client.post(
        TEXT_SEARCH, json=body,
        headers={"X-Goog-Api-Key": settings.google_places_api_key,
                 "X-Goog-FieldMask": FIELD_MASK, "Content-Type": "application/json"},
    )
    if r.status_code != 200:
        raise RuntimeError(f"Places API {r.status_code}: {r.text[:300]}")
    return r.json()


async def collect(radius_m: float, grid: bool = False) -> dict[str, dict]:
    """Chạy mọi (query × khu), gộp theo place id. Trả {place_id: place_json + _near_campus}."""
    if not settings.google_places_api_key:
        raise RuntimeError("GOOGLE_PLACES_API_KEY chưa set trong .env")
    found: dict[str, dict] = {}
    requests = 0
    points = search_points(grid)
    log.info("quét %d điểm × %d query, bán kính %.0f m", len(points), len(QUERIES), radius_m)
    async with httpx.AsyncClient(timeout=30.0) as client:
        for ci, (clat, clng) in enumerate(points):
            for q in QUERIES:
                token = None
                for _ in range(MAX_PAGES):
                    data = await search_text(client, q, clat, clng, radius_m, token)
                    requests += 1
                    for p in data.get("places", []):
                        loc = p.get("location") or {}
                        plat, plng = loc.get("latitude"), loc.get("longitude")
                        if plat is None:
                            continue
                        # locationBias chỉ "ưu tiên" — tự lọc theo bán kính thật
                        dmin = min(haversine_m(plat, plng, a, b) for a, b in CAMPUSES)
                        if dmin > MAX_DIST_CAMPUS_M:
                            continue
                        if p["id"] not in found:
                            p["_dist_campus_m"] = dmin
                            found[p["id"]] = p
                    token = data.get("nextPageToken")
                    if not token:
                        break
                    await asyncio.sleep(2.0)  # token cần vài giây mới dùng được
                label = CAMPUS_NAMES[ci] if ci < len(CAMPUS_NAMES) else f"điểm {ci + 1}"
                log.info("%-9s | %-18s | tổng place duy nhất: %d", label, q, len(found))
    log.info("Places API requests: %d", requests)
    return found


# ── DB ────────────────────────────────────────────────────────────────────────
_UPSERT_PLACE = text("""
    INSERT INTO places (provider, provider_place_id, name, address, geom, rating, rating_count,
                        maps_uri, primary_type, listing_id, match_distance_m, fetched_at,
                        phone, phone_intl, website, business_status, opening_hours, ward, district_norm)
    VALUES ('google', :pid, :name, :address,
            ST_SetSRID(ST_MakePoint(:lng, :lat), 4326), :rating, :rating_count,
            :maps_uri, :ptype, :listing_id, :match_m, :now,
            :phone, :phone_intl, :website, :bstatus, :hours, :ward, :district)
    ON CONFLICT (provider, provider_place_id) DO UPDATE SET
        name = EXCLUDED.name, address = EXCLUDED.address, geom = EXCLUDED.geom,
        rating = EXCLUDED.rating, rating_count = EXCLUDED.rating_count,
        maps_uri = EXCLUDED.maps_uri, primary_type = EXCLUDED.primary_type,
        listing_id = COALESCE(EXCLUDED.listing_id, places.listing_id),
        match_distance_m = COALESCE(EXCLUDED.match_distance_m, places.match_distance_m),
        phone = COALESCE(EXCLUDED.phone, places.phone),
        phone_intl = COALESCE(EXCLUDED.phone_intl, places.phone_intl),
        website = COALESCE(EXCLUDED.website, places.website),
        business_status = COALESCE(EXCLUDED.business_status, places.business_status),
        opening_hours = COALESCE(EXCLUDED.opening_hours, places.opening_hours),
        ward = COALESCE(EXCLUDED.ward, places.ward),
        district_norm = COALESCE(EXCLUDED.district_norm, places.district_norm),
        fetched_at = EXCLUDED.fetched_at
    RETURNING id
""")
_UPSERT_REVIEW = text("""
    INSERT INTO place_reviews (place_id, provider_review_id, rating, text, language, author_name,
                               published_at, relative_time, sentiment, fetched_at)
    VALUES (:place_id, :rid, :rating, :text, :lang, :author, :published_at, :rel, :sentiment, :now)
    ON CONFLICT (provider_review_id) DO UPDATE SET
        rating = EXCLUDED.rating, text = EXCLUDED.text, relative_time = EXCLUDED.relative_time,
        sentiment = EXCLUDED.sentiment, fetched_at = EXCLUDED.fetched_at
""")
# SĐT doanh nghiệp do Google trả về → điền cho tin đã ghép nếu tin chưa có số nào.
_FILL_LISTING_CONTACT = text("""
    UPDATE aggregated_listings
    SET contact_phone = :phone,
        contact_source = COALESCE(contact_source, 'google_places'),
        contact_extracted_at = :now
    WHERE id = :listing_id AND contact_phone IS NULL AND :phone IS NOT NULL
""")
_NEAREST_LISTING = text("""
    SELECT id,
           ST_Distance(geom::geography, ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography) AS d
    FROM aggregated_listings
    WHERE geom IS NOT NULL AND status = 'active'
      AND ST_DWithin(geom::geography, ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography, :match_m)
    ORDER BY (geocode_confidence = 'high') DESC,
             geom <-> ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)
    LIMIT 1
""")


def _addr_parts(p: dict) -> tuple[str | None, str | None]:
    """(ward, district_norm) từ addressComponents của Places, fallback formattedAddress."""
    comps = p.get("addressComponents") or []
    by_type: dict[str, str] = {}
    for c in comps:
        for t in c.get("types") or []:
            by_type.setdefault(t, c.get("longText") or c.get("shortText") or "")
    ward = canon_ward(by_type.get("sublocality_level_1"), by_type.get("sublocality"),
                      by_type.get("administrative_area_level_3"), p.get("formattedAddress"))
    dist = canon_district(by_type.get("administrative_area_level_2"),
                          by_type.get("locality"), p.get("formattedAddress"))
    return ward, dist


def save(found: dict[str, dict]) -> dict:
    engine = create_engine(settings.database_url, pool_pre_ping=True)
    now = datetime.now(timezone.utc)
    stats = {"places": 0, "matched": 0, "reviews": 0, "negative": 0, "with_phone": 0,
             "listing_phone_filled": 0}
    with engine.begin() as conn:
        for pid, p in found.items():
            lat, lng = p["location"]["latitude"], p["location"]["longitude"]
            near = conn.execute(_NEAREST_LISTING,
                                {"lat": lat, "lng": lng, "match_m": MATCH_M}).mappings().first()
            listing_id, match_m = (None, None)
            if near and near["d"] is not None:
                listing_id, match_m = near["id"], float(near["d"])
                stats["matched"] += 1
            ward, dist = _addr_parts(p)
            phone = normalize_phone(p.get("nationalPhoneNumber") or "") or None
            hours = ((p.get("regularOpeningHours") or {}).get("weekdayDescriptions")) or None
            place_id = conn.execute(_UPSERT_PLACE, {
                "pid": pid, "name": (p.get("displayName") or {}).get("text"),
                "address": p.get("formattedAddress"), "lat": lat, "lng": lng,
                "rating": p.get("rating"), "rating_count": p.get("userRatingCount"),
                "maps_uri": p.get("googleMapsUri"), "ptype": p.get("primaryType"),
                "listing_id": listing_id, "match_m": match_m, "now": now,
                "phone": phone, "phone_intl": p.get("internationalPhoneNumber"),
                "website": p.get("websiteUri"), "bstatus": p.get("businessStatus"),
                "hours": hours, "ward": ward, "district": dist,
            }).scalar_one()
            stats["places"] += 1
            if phone:
                stats["with_phone"] += 1
            if listing_id and phone:
                r = conn.execute(_FILL_LISTING_CONTACT,
                                 {"listing_id": listing_id, "phone": phone, "now": now})
                stats["listing_phone_filled"] += r.rowcount or 0
            for rv in p.get("reviews") or []:
                rating = rv.get("rating")
                txt = (rv.get("originalText") or rv.get("text") or {}).get("text")
                pub = rv.get("publishTime")
                conn.execute(_UPSERT_REVIEW, {
                    "place_id": place_id, "rid": rv.get("name"), "rating": rating, "text": txt,
                    "lang": (rv.get("originalText") or {}).get("languageCode"),
                    "author": (rv.get("authorAttribution") or {}).get("displayName"),
                    "published_at": datetime.fromisoformat(pub.replace("Z", "+00:00")) if pub else None,
                    "rel": rv.get("relativePublishTimeDescription"),
                    "sentiment": _sentiment(rating), "now": now,
                })
                stats["reviews"] += 1
                if rating is not None and rating <= 2:
                    stats["negative"] += 1
    return stats


def export_csv(found: dict[str, dict], path: str) -> int:
    """CSV phẳng 1 dòng/review (place không có review vẫn ra 1 dòng) — cho eval/data + báo cáo."""
    n = 0
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["place_id", "name", "address", "ward", "district", "phone", "website",
                    "lat", "lng", "dist_campus_m", "place_rating", "rating_count", "maps_uri",
                    "review_rating", "review_text", "review_time", "author"])
        for pid, p in found.items():
            ward, dist = _addr_parts(p)
            base = [pid, (p.get("displayName") or {}).get("text"), p.get("formattedAddress"),
                    ward, dist, p.get("nationalPhoneNumber"), p.get("websiteUri"),
                    p["location"]["latitude"], p["location"]["longitude"], round(p["_dist_campus_m"]),
                    p.get("rating"), p.get("userRatingCount"), p.get("googleMapsUri")]
            reviews = p.get("reviews") or [None]
            for rv in reviews:
                if rv is None:
                    w.writerow(base + ["", "", "", ""])
                else:
                    w.writerow(base + [rv.get("rating"),
                                       (rv.get("originalText") or rv.get("text") or {}).get("text"),
                                       rv.get("publishTime"),
                                       (rv.get("authorAttribution") or {}).get("displayName")])
                n += 1
    return n


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--radius", type=float, default=2500, help="bán kính quanh mỗi khu CTU (m)")
    ap.add_argument("--grid", action="store_true",
                    help="quét thêm vành đai quanh mỗi khu CTU (nhiều request hơn, phủ rộng hơn)")
    ap.add_argument("--dry-run", action="store_true", help="chỉ in thống kê + JSON, không ghi DB")
    ap.add_argument("--csv", default="google_reviews.csv", help="đường dẫn CSV xuất ra")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    found = asyncio.run(collect(args.radius, grid=args.grid))
    with_reviews = sum(1 for p in found.values() if p.get("reviews"))
    n_reviews = sum(len(p.get("reviews") or []) for p in found.values())
    n_neg = sum(1 for p in found.values() for rv in p.get("reviews") or [] if (rv.get("rating") or 5) <= 2)
    n_phone = sum(1 for p in found.values() if p.get("nationalPhoneNumber"))
    print(json.dumps({"places": len(found), "places_with_reviews": with_reviews,
                      "reviews": n_reviews, "negative_reviews": n_neg,
                      "places_with_phone": n_phone}, ensure_ascii=False))
    rows = export_csv(found, args.csv)
    print(f"CSV: {args.csv} ({rows} dòng)")
    if args.dry_run:
        for p in list(found.values())[:5]:
            print(json.dumps({k: v for k, v in p.items() if k != "reviews"}, ensure_ascii=False)[:300])
        return
    print("DB:", save(found))


if __name__ == "__main__":
    main(sys.argv[1:])
