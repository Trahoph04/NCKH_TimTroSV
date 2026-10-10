"""Nạp gói Chợ Tốt 789 tin (`student-housing-789-Docker-INTERNAL/catalog/CATALOG.jsonl`) vào DB dev.

Gói kèm cả một DB Docker riêng (cổng 5454) nhưng KHÔNG dùng: lược đồ cũ 33 cột, id 803–1597 đụng id
đang có, thiếu cột route/extras/contact/ghép bạn. Đọc JSONL rồi đi đúng đường crawler nhatot:
upsert → extras → địa chỉ chuẩn hoá → run_cleaner → hạ nhãn toạ độ dùng chung → auto-route.

Quy tắc (theo catalog/README.md của gói, docs/specs/Map_MapLibre_POI.md D1):
  - khớp (nhatot|chotot, source_id) đã có → KHÔNG ghi đè (bản trong DB có extras/contact đã trích);
    chỉ bổ sung offer_kind='lease_transfer' nếu gói gắn
  - last_seen = thời điểm quan sát THẬT trong gói (first_seen/last_seen, hoặc lúc gọi gateway lấy
    metadata người bán) — không lấy now(), không lấy ngày đóng gói
  - tin không có bằng chứng còn tồn tại (metadata 404 / request lỗi, không timestamp) → bỏ qua
  - mô tả giữ nguyên chuỗi "[Liên hệ qua nguồn]" của gói; không thêm SĐT

Chạy (file nằm ngoài image api → đẩy qua stdin):
  docker compose exec -T api python -m app.crawler.import_catalog < .../catalog/CATALOG.jsonl
  ... --apply   để ghi DB (mặc định chỉ đếm)
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from datetime import datetime

from sqlalchemy import create_engine, text

from ..cleaner.pipeline import run_cleaner
from ..config import settings
from .address import normalize_address
from .extras import extract_extras
from .geocode import CTU_LAT, CTU_LNG, haversine_m
from .normalize import compute_content_hash, parse_amenities
from .pipeline import auto_route
from .repo import ListingRepo
from .schemas import NormalizedListing

log = logging.getLogger("crawler.import_catalog")

SOURCE = "nhatot"  # cùng tên nguồn với crawler nhatot.py để khớp trùng theo source_id


def observed_at(row: dict) -> tuple[datetime | None, datetime | None]:
    """(first_seen, last_seen) thật của tin trong gói; (None, None) nếu không có bằng chứng."""
    meta = row.get("seller_metadata") or {}
    obs = meta.get("observed_at") if row.get("seller_metadata_status") == "OBSERVED" else None
    first = row.get("first_seen") or obs
    last = row.get("last_seen") or obs
    if not first or not last:
        return None, None
    return datetime.fromisoformat(first), datetime.fromisoformat(last)


def row_to_listing(row: dict) -> NormalizedListing:
    """1 dòng CATALOG.jsonl → NormalizedListing (cùng quy ước field với nhatot.ad_to_listing)."""
    title = (row.get("title") or "").strip()
    desc = row.get("description")
    district = (row.get("district") or "").replace("Quận ", "").replace("Huyện ", "").strip() or None
    n = NormalizedListing(
        source=SOURCE,
        source_id=str(row["source_id"]),
        source_url=row.get("source_url"),
        title=title,
        price=int(row["price"]) if row.get("price") else None,
        area=float(row["area"]) if row.get("area") else None,  # gói để NULL khi không có số đo
        address=row.get("address"),
        district=district,
        description=desc,
        images=list(row.get("images") or []),
        amenities=parse_amenities(desc, title),
    )
    lat, lng = row.get("latitude"), row.get("longitude")
    if lat is not None and lng is not None:
        # 'high' tạm — mark_shared_coords hạ về 'medium' nếu là điểm mặc định của phường
        n.lat, n.lng, n.geocode_confidence = float(lat), float(lng), "high"
        n.distance_to_ctu = haversine_m(n.lat, n.lng, CTU_LAT, CTU_LNG)
    n.content_hash = compute_content_hash(n)
    return n


def import_rows(engine, rows: list[dict], apply: bool) -> dict:
    repo = ListingRepo(engine)
    with engine.connect() as conn:
        existing = {
            r.source_id for r in conn.execute(text(
                "SELECT source_id FROM aggregated_listings WHERE source IN ('nhatot', 'chotot')"
            ))
        }

    stats = {"rows": len(rows), "existing": 0, "no_evidence": 0, "inserted": 0, "lease_transfer": 0}
    for row in rows:
        sid = str(row["source_id"])
        lease = row.get("offer_kind") == "lease_transfer"
        if sid in existing:
            stats["existing"] += 1
            if lease and apply:
                with engine.begin() as conn:
                    conn.execute(text(
                        "UPDATE aggregated_listings SET offer_kind = 'lease_transfer' "
                        "WHERE source IN ('nhatot', 'chotot') AND source_id = :sid AND offer_kind IS NULL"
                    ), {"sid": sid})
            continue
        first, last = observed_at(row)
        if first is None:
            stats["no_evidence"] += 1
            continue
        stats["inserted"] += 1
        stats["lease_transfer"] += lease
        if not apply:
            continue

        n = row_to_listing(row)
        repo.upsert(n)
        with engine.begin() as conn:
            conn.execute(text(
                "UPDATE aggregated_listings SET first_seen = :f, last_seen = :l, updated_at = :l, "
                "offer_kind = :offer WHERE source = :s AND source_id = :sid"
            ), {"f": first, "l": last, "offer": "lease_transfer" if lease else None,
                "s": SOURCE, "sid": sid})
        repo.set_extras(SOURCE, sid, extract_extras(n.title, n.description).as_dict())
        repo.set_address(SOURCE, sid, normalize_address(n.address, n.district, n.title, n.description))

    if apply and stats["inserted"]:
        run_cleaner(engine)
        stats["coords_downgraded"] = repo.mark_shared_coords(SOURCE)
        repo.refresh_scores()
        stats["routed"] = asyncio.run(auto_route(repo, SOURCE))
    return stats


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="ghi DB (mặc định chỉ đếm)")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO)
    rows = [json.loads(line) for line in sys.stdin if line.strip()]
    engine = create_engine(settings.database_url, pool_pre_ping=True)
    print(json.dumps(import_rows(engine, rows, args.apply), ensure_ascii=False))
    if not args.apply:
        print("(dry-run — thêm --apply để ghi DB)")


if __name__ == "__main__":
    main()
