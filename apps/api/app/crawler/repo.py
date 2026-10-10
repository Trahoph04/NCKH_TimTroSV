from datetime import datetime, timezone
import json

from sqlalchemy import text
from sqlalchemy.engine import Engine

from .schemas import NormalizedListing

# Upsert: match theo (source, source_id). content_hash đổi → cập nhật field + updated_at.
_UPSERT = text(
    """
    INSERT INTO aggregated_listings
        (title, price, area, address, district, images, description,
         source, source_url, source_id, content_hash, parsed_amenities,
         geom, distance_to_ctu, geocode_confidence,
         status, first_seen, last_seen, miss_count, freshness_score, updated_at)
    VALUES
        (:title, :price, :area, :address, :district, :images, :description,
         :source, :source_url, :source_id, :content_hash, CAST(:amenities AS JSONB),
         CASE WHEN CAST(:lat AS DOUBLE PRECISION) IS NULL THEN NULL
              ELSE ST_SetSRID(ST_MakePoint(CAST(:lng AS DOUBLE PRECISION), CAST(:lat AS DOUBLE PRECISION)), 4326) END,
         CAST(:distance_to_ctu AS REAL), :geocode_confidence,
         'active', :now, :now, 0, 1.0, :now)
    ON CONFLICT (source, source_id) DO UPDATE SET
        last_seen = :now,
        miss_count = 0,
        freshness_score = 1.0,
        status = CASE WHEN aggregated_listings.status = 'expired'
                      THEN 'active' ELSE aggregated_listings.status END,
        title = CASE WHEN aggregated_listings.content_hash <> :content_hash
                     THEN :title ELSE aggregated_listings.title END,
        price = CASE WHEN aggregated_listings.content_hash <> :content_hash
                     THEN :price ELSE aggregated_listings.price END,
        area = CASE WHEN aggregated_listings.content_hash <> :content_hash
                    THEN :area ELSE aggregated_listings.area END,
        district = COALESCE(:district, aggregated_listings.district),
        description = CASE WHEN aggregated_listings.content_hash <> :content_hash
                          THEN :description ELSE aggregated_listings.description END,
        address = CASE WHEN aggregated_listings.content_hash <> :content_hash
                       THEN :address ELSE aggregated_listings.address END,
        images = CASE WHEN aggregated_listings.content_hash <> :content_hash
                      THEN :images ELSE aggregated_listings.images END,
        geom = CASE WHEN CAST(:lat AS DOUBLE PRECISION) IS NULL THEN aggregated_listings.geom
                    ELSE ST_SetSRID(ST_MakePoint(CAST(:lng AS DOUBLE PRECISION), CAST(:lat AS DOUBLE PRECISION)), 4326) END,
        distance_to_ctu = COALESCE(CAST(:distance_to_ctu AS REAL), aggregated_listings.distance_to_ctu),
        geocode_confidence = :geocode_confidence,
        content_hash = :content_hash,
        cleaning_status = CASE WHEN aggregated_listings.content_hash <> :content_hash
                               THEN 'raw' ELSE aggregated_listings.cleaning_status END,
        updated_at = CASE WHEN aggregated_listings.content_hash <> :content_hash
                          THEN :now ELSE aggregated_listings.updated_at END
    RETURNING (xmax = 0) AS inserted,
              (xmax <> 0 AND updated_at = :now) AS updated
    """
)

# Extras (migration 90): COALESCE(new, old) — không xoá giá trị đã có bằng None.
_SET_EXTRAS = text(
    """
    UPDATE aggregated_listings SET
        electricity_price   = COALESCE(CAST(:electricity_price AS INTEGER), electricity_price),
        water_price         = COALESCE(CAST(:water_price AS INTEGER), water_price),
        water_unit          = COALESCE(:water_unit, water_unit),
        utility_state_price = COALESCE(CAST(:utility_state_price AS BOOLEAN), utility_state_price),
        deposit_amount      = COALESCE(CAST(:deposit_amount AS INTEGER), deposit_amount),
        deposit_months      = COALESCE(CAST(:deposit_months AS REAL), deposit_months),
        gender_only         = COALESCE(:gender_only, gender_only),
        curfew_hour         = COALESCE(CAST(:curfew_hour AS SMALLINT), curfew_hour),
        free_hours          = COALESCE(CAST(:free_hours AS BOOLEAN), free_hours),
        extras_extracted_at = :now
    WHERE source = :source AND source_id = :source_id
    """
)


# ── Liên hệ (migration 91) ───────────────────────────────────────────────────
# COALESCE(new, old): lần trích sau ra None không xoá số đã có.
_SET_CONTACT = text(
    """
    UPDATE aggregated_listings SET
        contact_phone      = COALESCE(:contact_phone, contact_phone),
        contact_phone_alt  = COALESCE(:contact_phone_alt, contact_phone_alt),
        contact_zalo       = COALESCE(:contact_zalo, contact_zalo),
        contact_name       = COALESCE(:contact_name, contact_name),
        contact_facebook   = COALESCE(:contact_facebook, contact_facebook),
        contact_source     = COALESCE(:contact_source, contact_source),
        contact_extracted_at = :now
    WHERE source = :source AND source_id = :source_id
    """
)

# ── Địa chỉ chuẩn hoá (migration 91) ────────────────────────────────────────
# Chỉ ghi khi độ tin cậy mới >= độ tin cậy đang có (không hạ cấp địa chỉ tốt).
_CONF_RANK = {"none": 0, "district": 1, "ward": 2, "street": 3, "exact": 4}
_SET_ADDRESS = text(
    """
    UPDATE aggregated_listings SET
        address_full       = COALESCE(:address_full, address_full),
        street             = COALESCE(:street, street),
        ward               = COALESCE(:ward, ward),
        district_norm      = COALESCE(:district_norm, district_norm),
        address_confidence = :address_confidence,
        address_source     = COALESCE(:address_source, address_source),
        address_normalized_at = :now
    WHERE source = :source AND source_id = :source_id
      AND CAST(:conf_rank AS INTEGER) >= COALESCE(
            CASE address_confidence WHEN 'exact' THEN 4 WHEN 'street' THEN 3
                                    WHEN 'ward' THEN 2 WHEN 'district' THEN 1 ELSE 0 END, 0)
    """
)


class ListingRepo:
    """DB I/O cho listings + crawl_runs. Tách khỏi pipeline để pipeline test được."""

    def __init__(self, engine: Engine):
        self.engine = engine

    def upsert(self, n: NormalizedListing) -> str:
        """Trả 'new' | 'updated' | 'seen'."""
        import json

        now = datetime.now(timezone.utc)
        with self.engine.begin() as conn:
            row = conn.execute(
                _UPSERT,
                {
                    "title": n.title,
                    "price": n.price,
                    "area": n.area,
                    "address": n.address,
                    "district": n.district,
                    "images": n.images,
                    "description": n.description,
                    "source": n.source,
                    "source_url": n.source_url,
                    "source_id": n.source_id,
                    "content_hash": n.content_hash,
                    "amenities": json.dumps(n.amenities),
                    "lat": n.lat,
                    "lng": n.lng,
                    "distance_to_ctu": n.distance_to_ctu,
                    "geocode_confidence": n.geocode_confidence,
                    "now": now,
                },
            ).one()
        if row.inserted:
            return "new"
        return "updated" if row.updated else "seen"

    def set_extras(self, source: str, source_id: str, extras: dict) -> None:
        """Ghi thuộc tính mềm (extras.py) theo (source, source_id). Chỉ ghi đè khi có giá trị mới —
        COALESCE giữ giá trị cũ nếu lần trích này ra None (mô tả bị cắt ngắn...)."""
        with self.engine.begin() as conn:
            conn.execute(
                _SET_EXTRAS,
                {"source": source, "source_id": source_id, **extras,
                 "now": datetime.now(timezone.utc)},
            )

    def set_contact(self, source: str, source_id: str, contact: dict) -> None:
        """Ghi SĐT/Zalo/tên người đăng (contact.py) — chỉ dữ liệu công khai trong tin."""
        if not any(contact.values()):
            return
        with self.engine.begin() as conn:
            conn.execute(_SET_CONTACT, {"source": source, "source_id": source_id,
                                        **contact, "now": datetime.now(timezone.utc)})

    def set_address(self, source: str, source_id: str, addr: dict) -> None:
        """Ghi địa chỉ chuẩn hoá (address.py); không hạ cấp địa chỉ đang có."""
        with self.engine.begin() as conn:
            conn.execute(_SET_ADDRESS, {
                "source": source, "source_id": source_id, **addr,
                "conf_rank": _CONF_RANK.get(addr.get("address_confidence") or "none", 0),
                "now": datetime.now(timezone.utc)})

    def pending_contact(self) -> list[dict]:
        """Tin chưa trích liên hệ (backfill)."""
        with self.engine.connect() as conn:
            return [dict(r) for r in conn.execute(text(
                "SELECT source, source_id, title, description FROM aggregated_listings "
                "WHERE contact_extracted_at IS NULL AND source_id IS NOT NULL ORDER BY id"
            )).mappings().all()]

    def pending_address(self, force_all: bool = False) -> list[dict]:
        """Tin cần chuẩn hoá địa chỉ, kèm toạ độ để reverse geocode khi thiếu address."""
        where = "TRUE" if force_all else "address_normalized_at IS NULL"
        with self.engine.connect() as conn:
            return [dict(r) for r in conn.execute(text(
                "SELECT source, source_id, title, address, district, description, "
                "ST_Y(geom) AS lat, ST_X(geom) AS lng "
                f"FROM aggregated_listings WHERE {where} AND source_id IS NOT NULL ORDER BY id"
            )).mappings().all()]

    def pending_extras(self) -> list[dict]:
        """Tin chưa từng trích extras (backfill) — có mô tả hoặc tiêu đề."""
        with self.engine.connect() as conn:
            return [dict(r) for r in conn.execute(text(
                "SELECT source, source_id, title, description FROM aggregated_listings "
                "WHERE extras_extracted_at IS NULL AND source_id IS NOT NULL ORDER BY id"
            )).mappings().all()]

    def mark_misses(self, source: str, seen_ids: list[str]) -> int:
        """Sau full run: tin của nguồn không nằm trong seen_ids → miss_count++ và có thể expired."""
        with self.engine.begin() as conn:
            rows = conn.execute(
                text(
                    """
                    UPDATE aggregated_listings
                    SET miss_count = miss_count + 1,
                        status = CASE
                            WHEN status = 'flagged' THEN status
                            WHEN miss_count + 1 >= 2 THEN 'expired'::listing_status
                            ELSE status END
                    WHERE source = :source
                      AND (source_id IS NULL OR source_id <> ALL(:ids))
                      AND status <> 'expired'
                    RETURNING status
                    """
                ),
                {"source": source, "ids": seen_ids or [""]},
            ).fetchall()
        return sum(1 for r in rows if r.status == "expired")

    def pending_route(self) -> list[dict]:
        """Tin có geom nhưng chưa route_time_campus (mới crawl, hoặc backfill sót)."""
        with self.engine.connect() as conn:
            rows = conn.execute(
                text(
                    "SELECT id, ST_Y(geom) AS lat, ST_X(geom) AS lng "
                    "FROM aggregated_listings "
                    "WHERE geom IS NOT NULL AND route_time_campus IS NULL"
                )
            ).mappings().all()
        return [dict(r) for r in rows]

    def set_route_times(self, updates: list[tuple[int, list[float]]]) -> None:
        """Batch UPDATE route_time_campus. updates = [(listing_id, [khuI,II,III]), ...]."""
        if not updates:
            return
        with self.engine.begin() as conn:
            for listing_id, times in updates:
                conn.execute(
                    text("UPDATE aggregated_listings SET route_time_campus = :t WHERE id = :id"),
                    {"t": times, "id": listing_id},
                )

    def mark_shared_coords(self, source: str) -> int:
        """Hạ 'high' → 'medium' cho toạ độ mà ≥ 2 tin cùng nguồn dùng chung. Trả số tin bị hạ.

        Chợ Tốt trả toạ độ cho MỌI tin nhưng tin không được người đăng ghim nhận điểm mặc định của
        phường: đo 07/10, 610 tin nhatot nằm trên 61 điểm, 1 điểm Hưng Lợi gom 183 tin. Điểm chung
        đó tương đương tầng 'medium' (toạ độ phường) của geocode.py — bản đồ phải hiện "vị trí tương
        đối". Điểm chỉ 1 tin dùng = người đăng tự ghim → giữ 'high'.
        """
        with self.engine.begin() as conn:
            return conn.execute(
                text(
                    """
                    UPDATE aggregated_listings a SET geocode_confidence = 'medium'
                    FROM (SELECT geom FROM aggregated_listings
                          WHERE source = :s AND geom IS NOT NULL
                          GROUP BY geom HAVING count(*) >= 2) g
                    WHERE a.source = :s AND a.geom = g.geom AND a.geocode_confidence = 'high'
                    """
                ),
                {"s": source},
            ).rowcount

    def refresh_scores(self) -> None:
        """Tính lại freshness_score theo tuổi last_seen (gọi định kỳ)."""
        with self.engine.begin() as conn:
            conn.execute(
                text(
                    "UPDATE aggregated_listings "
                    "SET freshness_score = EXP(-EXTRACT(EPOCH FROM (now() - last_seen)) / 86400.0 / 7.0) "
                    "WHERE status <> 'expired'"
                )
            )

    def start_run(self, source: str, mode: str) -> int:
        with self.engine.begin() as conn:
            return conn.execute(
                text(
                    "INSERT INTO crawl_runs (source, mode) VALUES (:s, :m) RETURNING id"
                ),
                {"s": source, "m": mode},
            ).scalar_one()

    def finish_run(self, run_id: int, **counts) -> None:
        with self.engine.begin() as conn:
            conn.execute(
                text(
                    "UPDATE crawl_runs SET finished_at = now(), fetched = :fetched, "
                    "new_count = :new_count, updated_count = :updated_count, "
                    "expired_count = :expired_count, error = :error WHERE id = :id"
                ),
                {"id": run_id, **counts},
            )

    def latest_runs(self, limit: int = 10) -> list[dict]:
        with self.engine.connect() as conn:
            rows = conn.execute(
                text(
                    "SELECT source, mode, started_at, finished_at, fetched, "
                    "new_count, updated_count, expired_count, error "
                    "FROM crawl_runs ORDER BY started_at DESC LIMIT :n"
                ),
                {"n": limit},
            ).mappings().all()
        return [dict(r) for r in rows]
