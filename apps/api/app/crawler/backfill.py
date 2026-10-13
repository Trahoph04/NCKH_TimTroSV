"""Backfill: re-geocode + re-extract area cho listing đã có address trong DB.

Dùng khi cải tiến geocode/area logic mà KHÔNG muốn crawl lại nguồn (nhanh hơn,
không tốn request phongtro123). Chỉ đọc address/description sẵn có → cập nhật
geom / distance_to_ctu / geocode_confidence / area.

Chạy: python -m app.crawler.backfill
"""
import asyncio

from sqlalchemy import create_engine, text

from ..config import settings
from .geocode import CTU_LAT, CTU_LNG, Geocoder, haversine_m
from .normalize import extract_area_from_text


async def backfill() -> dict:
    engine = create_engine(settings.database_url, pool_pre_ping=True)
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT id, title, address, description, area FROM aggregated_listings "
                 "WHERE address IS NOT NULL ORDER BY id")
        ).mappings().all()

    stats = {"total": len(rows), "geocoded": 0, "area_filled": 0,
             "high": 0, "medium": 0, "low": 0, "failed": 0}

    async with Geocoder() as geo:
        for r in rows:
            lat, lng, conf = await geo.geocode(r["address"])
            stats[conf] = stats.get(conf, 0) + 1
            dist = haversine_m(lat, lng, CTU_LAT, CTU_LNG) if lat is not None else None

            area = r["area"]
            if area is None:
                new_area = extract_area_from_text(r["description"], r["title"])
                if new_area is not None:
                    area = new_area
                    stats["area_filled"] += 1

            with engine.begin() as conn:
                conn.execute(
                    text(
                        "UPDATE aggregated_listings SET "
                        "geom = CASE WHEN CAST(:lat AS DOUBLE PRECISION) IS NULL THEN geom "
                        "  ELSE ST_SetSRID(ST_MakePoint(CAST(:lng AS DOUBLE PRECISION), "
                        "  CAST(:lat AS DOUBLE PRECISION)), 4326) END, "
                        "distance_to_ctu = COALESCE(CAST(:dist AS REAL), distance_to_ctu), "
                        # toạ độ đổi ⇒ phút tới trường cũ không còn đúng; route_backfill/auto_route tính lại
                        "route_time_campus = CASE WHEN CAST(:lat AS DOUBLE PRECISION) IS NOT NULL AND (geom IS NULL "
                        "  OR NOT ST_DWithin(geom, ST_SetSRID(ST_MakePoint(CAST(:lng AS DOUBLE PRECISION), "
                        "  CAST(:lat AS DOUBLE PRECISION)), 4326), 0.00005)) THEN NULL ELSE route_time_campus END, "
                        "geocode_confidence = :conf, "
                        "area = CAST(:area AS REAL) "
                        "WHERE id = :id"
                    ),
                    {"lat": lat, "lng": lng, "dist": dist, "conf": conf,
                     "area": area, "id": r["id"]},
                )
            if lat is not None:
                stats["geocoded"] += 1

    engine.dispose()
    return stats


if __name__ == "__main__":
    result = asyncio.run(backfill())
    print("BACKFILL DONE:", result)
