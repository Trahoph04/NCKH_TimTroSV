"""Backfill liên hệ + địa chỉ chuẩn hoá cho tin ĐÃ có trong DB (migration 91).

Không crawl lại — đọc title/description/address/toạ độ sẵn có:
  1. contact.py  → SĐT/Zalo/Facebook/tên người đăng (chỉ text người đăng tự ghi)
  2. address.py  → street/ward/district_norm/address_full + độ tin cậy
  3. reverse geocode Nominatim cho tin CÓ toạ độ nhưng địa chỉ còn yếu (none/district)
     — 1 request/giây theo usage policy, dùng --no-reverse để bỏ qua.

Chạy:
  docker compose exec api python -m app.crawler.backfill_contact_address
  docker compose exec api python -m app.crawler.backfill_contact_address --all
  docker compose exec api python -m app.crawler.backfill_contact_address --no-reverse
"""
from __future__ import annotations

import asyncio
import sys
from collections import Counter

from sqlalchemy import create_engine

from ..config import settings
from .address import ReverseGeocoder, normalize_address
from .contact import extract_contact
from .repo import ListingRepo

WEAK = (None, "none", "district")


async def main(force_all: bool = False, reverse: bool = True) -> dict:
    engine = create_engine(settings.database_url, pool_pre_ping=True)
    repo = ListingRepo(engine)
    stats = Counter()

    # ── 1. liên hệ ───────────────────────────────────────────────────────────
    rows = repo.pending_address(force_all=True) if force_all else repo.pending_contact()
    for r in rows:
        c = extract_contact(r.get("title"), r.get("description"), source="description").as_dict()
        repo.set_contact(r["source"], r["source_id"], c)
        stats["contact_rows"] += 1
        for k, v in c.items():
            if v and k != "contact_source":
                stats[k] += 1

    # ── 2. địa chỉ ───────────────────────────────────────────────────────────
    rows = repo.pending_address(force_all=force_all)
    need_reverse: list[tuple[dict, dict]] = []
    for r in rows:
        a = normalize_address(r.get("address"), r.get("district"), r.get("title"), r.get("description"))
        repo.set_address(r["source"], r["source_id"], a)
        stats["address_rows"] += 1
        stats[f"conf_{a['address_confidence']}"] += 1
        if a["address_confidence"] in WEAK and r.get("lat") is not None:
            need_reverse.append((r, a))

    # ── 3. reverse geocode cho tin có toạ độ mà địa chỉ còn yếu ──────────────
    if reverse and need_reverse:
        async with ReverseGeocoder() as rg:
            for r, _ in need_reverse:
                a = await rg.normalize(float(r["lat"]), float(r["lng"]))
                if a["address_confidence"] not in WEAK:
                    repo.set_address(r["source"], r["source_id"], a)
                    stats["reverse_ok"] += 1
                else:
                    stats["reverse_miss"] += 1

    out = dict(sorted(stats.items()))
    print("backfill_contact_address:", out)
    return out


if __name__ == "__main__":
    asyncio.run(main(force_all="--all" in sys.argv, reverse="--no-reverse" not in sys.argv))
