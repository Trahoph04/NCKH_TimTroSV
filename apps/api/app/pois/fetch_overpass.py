"""Lấy tiện ích quanh CTU từ OpenStreetMap (Overpass API) → bảng `pois` hoặc file seed SQL.

Chạy 1 lần (dữ liệu OSM đổi chậm), không đưa vào scheduler: Overpass là dịch vụ cộng đồng, giới hạn
tải — gọi định kỳ từ app là lạm dụng.

  docker compose exec api python -m app.pois.fetch_overpass                 # chỉ đếm theo nhóm
  docker compose exec api python -m app.pois.fetch_overpass --apply         # ghi bảng pois
  docker compose exec -T api python -m app.pois.fetch_overpass --sql > infra/db/migrations/96_pois_seed.sql
  ... --from-file /tmp/overpass.json   # dùng JSON đã tải sẵn (khi máy chủ Overpass quá tải)

Dữ liệu © OpenStreetMap contributors, giấy phép ODbL — ghi nguồn trên bản đồ và trong báo cáo.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from collections import Counter
from datetime import datetime, timezone

import httpx

from .categories import KEEP_TAGS, category_of, overpass_query

log = logging.getLogger("pois.fetch_overpass")

# (S, W, N, E): Ninh Kiều + Cái Răng + phần Bình Thuỷ — chứa ~95% tin đang hiển thị
BBOX = (9.96, 105.68, 10.10, 105.84)
# Máy chủ chính hay trả 504 khi quá tải → thử lần lượt các mirror công khai
MIRRORS = (
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
)
USER_AGENT = "TroCTU-NCKH/1.0 (contact: phub2303891@student.ctu.edu.vn)"


def fetch(query: str) -> dict:
    last: Exception | None = None
    for attempt in range(2):
        for url in MIRRORS:
            try:
                r = httpx.post(url, data={"data": query}, headers={"User-Agent": USER_AGENT},
                               timeout=120.0)
                r.raise_for_status()
                return r.json()
            except Exception as exc:  # noqa: BLE001 — mirror này hỏng thì thử mirror sau
                log.warning("overpass %s fail: %s", url, exc)
                last = exc
        time.sleep(10 * (attempt + 1))
    raise RuntimeError(f"mọi máy chủ Overpass đều lỗi: {last}")


def to_items(data: dict) -> list[dict]:
    """Phần tử Overpass → dòng bảng pois. Way/relation lấy tâm (`out center`)."""
    items = []
    for e in data.get("elements", []):
        tags = e.get("tags") or {}
        cat = category_of(tags)
        lat = e.get("lat", (e.get("center") or {}).get("lat"))
        lng = e.get("lon", (e.get("center") or {}).get("lon"))
        if cat is None or lat is None or lng is None:
            continue
        items.append({
            "osm_type": e["type"], "osm_id": e["id"], "category": cat,
            "name": tags.get("name") or tags.get("brand"),
            "lat": lat, "lng": lng,
            "tags": {k: v for k, v in tags.items() if k in KEEP_TAGS},
        })
    return items


def _q(v) -> str:
    """Literal SQL an toàn cho text (nhân đôi nháy đơn)."""
    if v is None:
        return "NULL"
    return "'" + str(v).replace("'", "''") + "'"


def to_sql(items: list[dict]) -> str:
    """1 câu INSERT duy nhất → nạp nguyên khối (reset_and_seed chờ bảng có dòng là đủ)."""
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    head = (
        f"-- Snapshot tiện ích OSM (Overpass) bbox {BBOX}, tải {stamp}, {len(items)} điểm.\n"
        "-- © OpenStreetMap contributors (ODbL). Sinh bằng: python -m app.pois.fetch_overpass --sql\n"
        "-- Idempotent: trùng (osm_type, osm_id) thì bỏ qua.\n"
    )
    if not items:
        return head
    rows = ",\n".join(
        f"({_q(it['osm_type'])}, {it['osm_id']}, {_q(it['category'])}, {_q(it['name'])}, "
        f"ST_SetSRID(ST_MakePoint({it['lng']}, {it['lat']}), 4326), "
        f"{_q(json.dumps(it['tags'], ensure_ascii=False))}::jsonb)"
        for it in sorted(items, key=lambda x: (x["osm_type"], x["osm_id"]))
    )
    return (head + "INSERT INTO pois (osm_type, osm_id, category, name, geom, tags) VALUES\n"
            + rows + "\nON CONFLICT (osm_type, osm_id) DO NOTHING;\n")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="ghi bảng pois")
    ap.add_argument("--sql", action="store_true", help="in seed SQL ra stdout")
    ap.add_argument("--from-file", help="đọc JSON Overpass đã tải thay vì gọi mạng")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, stream=sys.stderr)

    if args.from_file:
        with open(args.from_file, encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = fetch(overpass_query(BBOX))
    items = to_items(data)
    log.info("theo nhóm: %s", dict(Counter(it["category"] for it in items)))

    if args.sql:
        sys.stdout.write(to_sql(items))
    if args.apply:
        from sqlalchemy import create_engine

        from ..config import settings
        from .repo import PoiRepo

        n = PoiRepo(create_engine(settings.database_url)).upsert_many(items)
        log.info("đã ghi %d POI", n)


if __name__ == "__main__":
    main()
