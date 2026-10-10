import json

from sqlalchemy import text
from sqlalchemy.engine import Engine

from .categories import LABELS
from .schemas import CategorySummary, PoiOut, PoiSummary

_POINT = "ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography"


class PoiRepo:
    """Tiện ích OSM (bảng pois, migration 95). Khoảng cách = đường chim bay trên geography."""

    def __init__(self, engine: Engine):
        self.engine = engine

    def near(self, lat: float, lng: float, radius: int, category: str | None = None,
             limit: int = 300) -> list[PoiOut]:
        with self.engine.connect() as conn:
            rows = conn.execute(
                text(
                    "SELECT id, category, name, ST_Y(geom) AS lat, ST_X(geom) AS lng, "
                    f"ST_Distance(geom::geography, {_POINT}) AS distance_m "
                    "FROM pois "
                    f"WHERE ST_DWithin(geom::geography, {_POINT}, :r) "
                    "AND (CAST(:cat AS TEXT) IS NULL OR category = :cat) "
                    "ORDER BY distance_m LIMIT :limit"
                ),
                {"lat": lat, "lng": lng, "r": radius, "cat": category, "limit": limit},
            ).mappings().all()
        return [PoiOut(**r) for r in rows]

    def summary(self, lat: float, lng: float, radius: int) -> PoiSummary:
        """Mỗi nhóm: số tiện ích trong bán kính + cái gần nhất. Nhóm 0 cái vẫn trả (count=0)."""
        with self.engine.connect() as conn:
            rows = conn.execute(
                text(
                    f"""
                    WITH p AS (
                        SELECT id, category, name, ST_Y(geom) AS lat, ST_X(geom) AS lng,
                               ST_Distance(geom::geography, {_POINT}) AS distance_m
                        FROM pois WHERE ST_DWithin(geom::geography, {_POINT}, :r)
                    )
                    SELECT category, count(*) AS n,
                           (array_agg(json_build_object('id', id, 'category', category, 'name', name,
                                      'lat', lat, 'lng', lng, 'distance_m', distance_m)
                                      ORDER BY distance_m))[1] AS nearest
                    FROM p GROUP BY category
                    """
                ),
                {"lat": lat, "lng": lng, "r": radius},
            ).mappings().all()
        found = {r["category"]: r for r in rows}
        cats = []
        for key, label in LABELS.items():
            r = found.get(key)
            nearest = r["nearest"] if r else None
            if isinstance(nearest, str):
                nearest = json.loads(nearest)
            cats.append(CategorySummary(
                category=key, label=label, count=r["n"] if r else 0,
                nearest=PoiOut(**nearest) if nearest else None,
            ))
        return PoiSummary(radius=radius, categories=cats)

    def upsert_many(self, items: list[dict]) -> int:
        """items: {osm_type, osm_id, category, name, lat, lng, tags}. Trả số dòng ghi."""
        if not items:
            return 0
        with self.engine.begin() as conn:
            for it in items:
                conn.execute(
                    text(
                        "INSERT INTO pois (osm_type, osm_id, category, name, geom, tags) "
                        "VALUES (:osm_type, :osm_id, :category, :name, "
                        "ST_SetSRID(ST_MakePoint(:lng, :lat), 4326), CAST(:tags AS JSONB)) "
                        "ON CONFLICT (osm_type, osm_id) DO UPDATE SET category = EXCLUDED.category, "
                        "name = EXCLUDED.name, geom = EXCLUDED.geom, tags = EXCLUDED.tags, fetched_at = now()"
                    ),
                    {**it, "tags": json.dumps(it["tags"], ensure_ascii=False)},
                )
        return len(items)
