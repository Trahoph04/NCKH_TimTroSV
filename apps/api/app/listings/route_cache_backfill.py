"""Lưu sẵn đường đi ORS (polyline) từ mọi toạ độ tin đang hiển thị tới 3 khu CTU → bảng route_cache.

Vì sao: dữ liệu chỉ có ~120 toạ độ phân biệt (geocode cấp phường) nên lưu hết được; buổi demo bấm tin
nào cũng vẽ đường ngay, không phụ thuộc quota ORS (free 2.000 directions/ngày, 40/phút) hay mạng.

  docker compose exec api python -m app.listings.route_cache_backfill            # chỉ đếm
  docker compose exec api python -m app.listings.route_cache_backfill --apply    # gọi ORS + ghi
"""
import argparse
import asyncio
import logging

import httpx

from sqlalchemy import create_engine

from app.config import settings
from app.listings.repo import RouteCacheRepo
from app.listings.routing import CAMPUSES, OSRM_PROFILE, PROFILE, route_geometry, route_geometry_osrm

DELAY_S = 1.6  # ORS free: 40 request/phút cho directions

log = logging.getLogger("listings.route_cache_backfill")


async def backfill(apply: bool, ids: list[int] | None = None, engine_name: str = "ors") -> dict:
    """engine_name 'osrm': điền chỗ trống bằng OSRM công khai (khi ORS hết quota) — chỉ các điểm chưa có đường theo
    CẢ HAI engine."""
    use_osrm = engine_name == "osrm"
    profile = OSRM_PROFILE if use_osrm else PROFILE
    fetch = route_geometry_osrm if use_osrm else route_geometry
    engine = create_engine(settings.database_url, pool_pre_ping=True)
    cache = RouteCacheRepo(engine)
    todo = cache.missing_origins(PROFILE, OSRM_PROFILE)
    if ids:
        # tin demo trước: quota ORS có thể cạn giữa chừng
        from sqlalchemy import text
        with engine.connect() as conn:
            pts = {(round(r.lat, 5), round(r.lng, 5)) for r in conn.execute(text(
                "SELECT ST_Y(geom) AS lat, ST_X(geom) AS lng FROM aggregated_listings WHERE id = ANY(:ids) AND geom IS NOT NULL"
            ), {"ids": ids})}
        todo = [t for t in todo if (round(t[0], 5), round(t[1], 5)) in pts] + \
               [t for t in todo if (round(t[0], 5), round(t[1], 5)) not in pts]
    stats = {"missing": len(todo), "saved": 0, "failed": 0}
    if not apply:
        return stats
    if not use_osrm and not settings.ors_api_key:
        raise SystemExit("ORS_API_KEY rỗng — không gọi được ORS (thử --engine osrm)")
    for i, (lat, lng, campus) in enumerate(todo):
        try:
            path = await fetch(CAMPUSES[campus], (lat, lng))
            cache.put(lat, lng, campus, profile, path)
            stats["saved"] += 1
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code in (403, 429):
                # ORS "Quota exceeded" (403) / OSRM quá tải (429) — gọi tiếp chỉ toàn lỗi.
                # Chạy lại sau khi quota hồi (0h UTC); phần đã lưu được bỏ qua.
                stats["stopped"] = "ORS quota exceeded"
                break
            stats["failed"] += 1
            log.warning("route fail (%s, %s) → khu %d: %s", lat, lng, campus, exc)
        except Exception as exc:  # noqa: BLE001 — 1 điểm lỗi (ORS không tới được) không dừng cả lượt
            stats["failed"] += 1
            log.warning("route fail (%s, %s) → khu %d: %s", lat, lng, campus, exc)
        if (i + 1) % 30 == 0:
            log.info("%d/%d", i + 1, len(todo))
        await asyncio.sleep(DELAY_S)
    engine.dispose()
    return stats


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="gọi ORS + ghi cache (mặc định chỉ đếm)")
    ap.add_argument("--ids", type=lambda v: [int(x) for x in v.split(",")], help="id tin ưu tiên, vd 1598,1635")
    ap.add_argument("--engine", choices=("ors", "osrm"), default="ors", help="osrm: máy chủ công khai, không cần key")
    logging.basicConfig(level=logging.INFO)
    args = ap.parse_args()
    print("ROUTE CACHE:", asyncio.run(backfill(args.apply, args.ids, args.engine)))
