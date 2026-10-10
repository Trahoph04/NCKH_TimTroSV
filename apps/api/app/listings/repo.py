from sqlalchemy import text
from sqlalchemy.engine import Engine

from .schemas import (
    HousingType,
    ListingOut,
    SearchParams,
    SortBy,
    freshness_label,
    risk_level,
)

# cột select chung; geom → tách lat/lng qua ST_X/ST_Y
_COLS = (
    "id, title, price, area, address, district, description, "
    "ST_Y(geom) AS lat, ST_X(geom) AS lng, distance_to_ctu, images, "
    "source, source_url, risk_score, geocode_confidence, freshness_score, "
    "quality_score, last_seen, route_time_campus, listing_type, offer_kind, location_precise"
)

_SORT_SQL = {
    SortBy.price_asc: "price ASC NULLS LAST",
    SortBy.price_desc: "price DESC NULLS LAST",
    SortBy.newest: "last_seen DESC",
    SortBy.nearest: "distance_to_ctu ASC NULLS LAST",
    SortBy.freshness: "freshness_score DESC",
    # tin chất lượng cao (đủ field, area thật, geocode tốt) lên trước
    SortBy.quality: "quality_score DESC, last_seen DESC",
}


def visible_clause(housing: HousingType | None) -> str:
    """Tin SV xem được: đã làm sạch + là chỗ ở cho thuê (ẩn nhà nguyên căn/mặt bằng/raw/rejected).

    Tin user tự đăng (source='user') chưa qua cleaner nhưng form đăng là phòng trọ → hiện khi không
    lọc hoặc lọc phòng trọ. Dùng chung cho search() và nearby() để map = list.
    """
    if housing is None:
        return ("(source = 'user' OR (cleaning_status = 'cleaned' "
                "AND listing_type IN ('phong_tro', 'nha_mini')))")
    if housing == HousingType.phong_tro:
        return "(source = 'user' OR (cleaning_status = 'cleaned' AND listing_type = 'phong_tro'))"
    return "(source <> 'user' AND cleaning_status = 'cleaned' AND listing_type = 'nha_mini')"


def build_filters(p: SearchParams) -> tuple[str, dict]:
    """Dựng mệnh đề WHERE + params. Tách riêng để unit-test không cần DB.

    Luôn ẩn tin status='expired' (FR-2.8) và 'hidden' (user tự ẩn).
    """
    clauses = [
        "status NOT IN ('expired', 'hidden')",
        visible_clause(p.housing),
    ]
    params: dict = {}

    if p.q:
        clauses.append("(title ILIKE :q OR description ILIKE :q OR address ILIKE :q)")
        params["q"] = f"%{p.q}%"
    if p.min_price is not None:
        clauses.append("price >= :min_price")
        params["min_price"] = p.min_price
    if p.max_price is not None:
        clauses.append("price <= :max_price")
        params["max_price"] = p.max_price
    if p.min_area is not None:
        clauses.append("area >= :min_area")
        params["min_area"] = p.min_area
    if p.district:
        clauses.append("district ILIKE :district")
        params["district"] = f"%{p.district}%"
    if p.max_distance_ctu is not None:
        clauses.append("distance_to_ctu <= :max_dist")
        params["max_dist"] = p.max_distance_ctu
    # amenities: JSONB chứa key = true
    for i, am in enumerate(p.amenities):
        key = f"am{i}"
        clauses.append(f"(parsed_amenities ->> :{key})::boolean IS TRUE")
        params[key] = am

    return " AND ".join(clauses), params


def _to_out(row) -> ListingOut:
    d = dict(row)
    d["images"] = d.get("images") or []
    d["risk_level"] = risk_level(d.get("risk_score"))
    d["freshness_label"] = freshness_label(d.get("last_seen"))
    return ListingOut(**d)


class ListingQueryRepo:
    """Đọc listings phục vụ search/detail/nearby (FR-2)."""

    def __init__(self, engine: Engine):
        self.engine = engine

    def search(self, p: SearchParams) -> tuple[int, list[ListingOut]]:
        where, params = build_filters(p)
        order = _SORT_SQL[p.sort]
        offset = (p.page - 1) * p.size

        with self.engine.connect() as conn:
            total = conn.execute(
                text(f"SELECT count(*) FROM aggregated_listings WHERE {where}"), params
            ).scalar_one()
            rows = conn.execute(
                text(
                    f"SELECT {_COLS} FROM aggregated_listings WHERE {where} "
                    f"ORDER BY {order} LIMIT :limit OFFSET :offset"
                ),
                {**params, "limit": p.size, "offset": offset},
            ).mappings().all()
        return total, [_to_out(r) for r in rows]

    def get(self, listing_id: int) -> ListingOut | None:
        with self.engine.connect() as conn:
            row = conn.execute(
                text(f"SELECT {_COLS} FROM aggregated_listings WHERE id = :id"),
                {"id": listing_id},
            ).mappings().first()
        return _to_out(row) if row else None

    def managed(self) -> list[ListingOut]:
        """Tin admin nhập tay (trang "Quản lý nhà trọ"). Ẩn tin đã xoá mềm ('hidden')."""
        with self.engine.connect() as conn:
            rows = conn.execute(
                text(
                    f"SELECT {_COLS} FROM aggregated_listings "
                    "WHERE source = 'user' AND status <> 'hidden' "
                    "ORDER BY last_seen DESC"
                ),
            ).mappings().all()
        return [_to_out(r) for r in rows]

    def get_visible(self, listing_id: int) -> ListingOut | None:
        """Detail công khai — ẩn tin expired/hidden (dùng cho GET /listings/{id})."""
        with self.engine.connect() as conn:
            row = conn.execute(
                text(
                    f"SELECT {_COLS} FROM aggregated_listings "
                    "WHERE id = :id AND status NOT IN ('expired', 'hidden')"
                ),
                {"id": listing_id},
            ).mappings().first()
        return _to_out(row) if row else None

    def contact(self, listing_id: int) -> dict | None:
        """SĐT/Zalo/Facebook công khai trong tin (crawler/contact.py) hoặc nhóm khảo sát thu — chỉ tin đang hiển thị."""
        with self.engine.connect() as conn:
            row = conn.execute(
                text(
                    "SELECT contact_phone AS phone, contact_zalo AS zalo, contact_facebook AS facebook, "
                    "source, source_url FROM aggregated_listings "
                    "WHERE id = :id AND status NOT IN ('expired', 'hidden')"
                ),
                {"id": listing_id},
            ).mappings().first()
        return dict(row) if row else None

    def get_many(self, ids: list[int]) -> dict[int, ListingOut]:
        """Nhiều tin theo id (giữ cả tin đã ẩn — thẻ đánh giá cũ vẫn phải hiển thị được)."""
        if not ids:
            return {}
        with self.engine.connect() as conn:
            rows = conn.execute(
                text(f"SELECT {_COLS} FROM aggregated_listings WHERE id = ANY(:ids)"), {"ids": list(ids)}
            ).mappings().all()
        return {r["id"]: _to_out(r) for r in rows}

    def nearby(
        self,
        lat: float,
        lng: float,
        radius_m: float,
        limit: int = 1000,
        housing: HousingType | None = None,
    ) -> list[ListingOut]:
        """Tin trong bán kính (FR-2.5) — PostGIS ST_DWithin trên geography.

        limit 1000 (trước 300): sau khi nạp gói Chợ Tốt, 3 km quanh khu II đã vượt 300 tin → bản đồ
        cắt mất tin mà không báo. MapLibre vẽ GPU nên 1000 điểm không thành vấn đề.
        """
        with self.engine.connect() as conn:
            rows = conn.execute(
                text(
                    f"SELECT {_COLS}, "
                    "ST_Distance(geom::geography, ST_SetSRID(ST_MakePoint(:lng,:lat),4326)::geography) AS dist "
                    "FROM aggregated_listings "
                    "WHERE status NOT IN ('expired', 'hidden') AND geom IS NOT NULL "
                    # đồng bộ filter sạch với search() (build_filters): map = list
                    f"AND {visible_clause(housing)} "
                    "AND ST_DWithin(geom::geography, ST_SetSRID(ST_MakePoint(:lng,:lat),4326)::geography, :r) "
                    "ORDER BY dist ASC LIMIT :limit"
                ),
                {"lat": lat, "lng": lng, "r": radius_m, "limit": limit},
            ).mappings().all()
        return [_to_out(r) for r in rows]


# cột được phép sửa qua PUT (partial update) — khớp field của ListingUpdate
_UPDATABLE_COLS = ("title", "price", "area", "address", "district", "description", "images")

_INSERT_UGC = text(
    """
    INSERT INTO aggregated_listings
        (title, price, area, address, district, images, description,
         source, source_url, source_id, posted_by,
         geom, distance_to_ctu, geocode_confidence,
         status, first_seen, last_seen, updated_at)
    VALUES
        (:title, :price, :area, :address, :district, :images, :description,
         'user', NULL, NULL, :posted_by,
         CASE WHEN CAST(:lat AS DOUBLE PRECISION) IS NULL THEN NULL
              ELSE ST_SetSRID(ST_MakePoint(CAST(:lng AS DOUBLE PRECISION), CAST(:lat AS DOUBLE PRECISION)), 4326) END,
         CAST(:distance_to_ctu AS REAL), :geocode_confidence,
         'active', now(), now(), now())
    RETURNING id
    """
)


class ListingWriteRepo:
    """Ghi listings UGC (đăng/sửa/xoá tin của user) — tách khỏi ListingQueryRepo (chỉ đọc)."""

    def __init__(self, engine: Engine):
        self.engine = engine

    def create(self, data: dict, user_id: int, lat, lng, conf, dist) -> int:
        with self.engine.begin() as conn:
            new_id = conn.execute(
                _INSERT_UGC,
                {
                    "title": data["title"],
                    "price": data.get("price"),
                    "area": data.get("area"),
                    "address": data.get("address"),
                    "district": data.get("district"),
                    "images": data.get("images") or [],
                    "description": data.get("description"),
                    "posted_by": user_id,
                    "lat": lat,
                    "lng": lng,
                    "distance_to_ctu": dist,
                    "geocode_confidence": conf,
                },
            ).scalar_one()
        return new_id

    def get_owner(self, listing_id: int):
        """Trả row {posted_by, status, source} hoặc None nếu id không tồn tại (dùng cho check 404/409)."""
        with self.engine.connect() as conn:
            row = conn.execute(
                text("SELECT posted_by, status, source FROM aggregated_listings WHERE id = :id"),
                {"id": listing_id},
            ).mappings().first()
        return row

    def update(self, listing_id: int, fields: dict, lat, lng, conf, dist) -> None:
        """Update partial — chỉ set cột có trong fields (khoá đã whitelist qua ListingUpdate)."""
        set_clauses = [f"{col} = :{col}" for col in fields if col in _UPDATABLE_COLS]
        params: dict = {**fields, "id": listing_id}

        if "address" in fields and lat is not None and lng is not None:
            set_clauses.append(
                "geom = ST_SetSRID(ST_MakePoint(CAST(:lng AS DOUBLE PRECISION), "
                "CAST(:lat AS DOUBLE PRECISION)), 4326)"
            )
            set_clauses.append("distance_to_ctu = CAST(:distance_to_ctu AS REAL)")
            set_clauses.append("geocode_confidence = :geocode_confidence")
            params["lat"] = lat
            params["lng"] = lng
            params["distance_to_ctu"] = dist
            params["geocode_confidence"] = conf

        if not set_clauses:
            return

        set_clauses.append("updated_at = now()")
        sql = f"UPDATE aggregated_listings SET {', '.join(set_clauses)} WHERE id = :id"
        with self.engine.begin() as conn:
            conn.execute(text(sql), params)

    def set_route_time(self, listing_id: int, times: list[float]) -> None:
        """Ghi route_time_campus cho 1 tin (sau khi geocode address UGC). Xem routing.py."""
        with self.engine.begin() as conn:
            conn.execute(
                text("UPDATE aggregated_listings SET route_time_campus = :t WHERE id = :id"),
                {"t": times, "id": listing_id},
            )

    def soft_delete(self, listing_id: int) -> None:
        """Ẩn tin (status='hidden') thay vì xoá cứng — user có thể khôi phục sau (không làm ở đây)."""
        with self.engine.begin() as conn:
            conn.execute(
                text(
                    "UPDATE aggregated_listings SET status = 'hidden', updated_at = now() "
                    "WHERE id = :id"
                ),
                {"id": listing_id},
            )


class RouteCacheRepo:
    """Đường đi ORS đã tính (bảng route_cache, migration 95) — khoá = toạ độ gốc làm tròn 5 chữ số."""

    def __init__(self, engine: Engine):
        self.engine = engine

    def get(self, lat: float, lng: float, campus: int, profile: str) -> list[list[float]] | None:
        with self.engine.connect() as conn:
            row = conn.execute(
                text(
                    "SELECT path FROM route_cache WHERE origin_lat = round(CAST(:lat AS NUMERIC), 5) "
                    "AND origin_lng = round(CAST(:lng AS NUMERIC), 5) AND campus = :c AND profile = :p"
                ),
                {"lat": lat, "lng": lng, "c": campus, "p": profile},
            ).first()
        return row.path if row else None

    def put(self, lat: float, lng: float, campus: int, profile: str, path: list[list[float]]) -> None:
        import json

        with self.engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO route_cache (origin_lat, origin_lng, campus, profile, path) "
                    "VALUES (round(CAST(:lat AS NUMERIC), 5), round(CAST(:lng AS NUMERIC), 5), :c, :p, "
                    "CAST(:path AS JSONB)) "
                    "ON CONFLICT (origin_lat, origin_lng, campus, profile) "
                    "DO UPDATE SET path = EXCLUDED.path, fetched_at = now()"
                ),
                {"lat": lat, "lng": lng, "c": campus, "p": profile, "path": json.dumps(path)},
            )

    def missing_origins(self, *profiles: str) -> list[tuple[float, float, int]]:
        """(lat, lng, campus) của tin đang hiển thị mà chưa có đường đi trong cache theo BẤT KỲ profile nào cho trước."""
        with self.engine.connect() as conn:
            rows = conn.execute(
                text(
                    f"""
                    WITH o AS (
                        SELECT DISTINCT round(CAST(ST_Y(geom) AS NUMERIC), 5) AS lat,
                                        round(CAST(ST_X(geom) AS NUMERIC), 5) AS lng
                        FROM aggregated_listings
                        WHERE geom IS NOT NULL AND status NOT IN ('expired', 'hidden')
                          AND {visible_clause(None)}
                    )
                    SELECT o.lat, o.lng, c.campus FROM o CROSS JOIN generate_series(0, 2) AS c(campus)
                    WHERE NOT EXISTS (
                        SELECT 1 FROM route_cache r WHERE r.origin_lat = o.lat AND r.origin_lng = o.lng
                          AND r.campus = c.campus AND r.profile = ANY(:p))
                    -- khu II (mặc định của bản đồ) và điểm gần trường trước: quota ORS Directions có
                    -- thể cạn giữa chừng, phần quan trọng cho demo phải xong trước.
                    ORDER BY (c.campus <> 1), (o.lat - 10.0322) ^ 2 + (o.lng - 105.7683) ^ 2, c.campus
                    """
                ),
                {"p": list(profiles)},
            ).all()
        return [(float(r.lat), float(r.lng), r.campus) for r in rows]
