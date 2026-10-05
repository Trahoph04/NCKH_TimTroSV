"""Backfill extras (điện/nước/cọc/giới tính/giờ giấc) cho tin ĐÃ có trong DB.

Không crawl lại — chỉ đọc title/description sẵn có → regex (extras.py) → UPDATE.
Chạy được nhiều lần (idempotent). Tin chưa trích = extras_extracted_at IS NULL.

Chạy:   docker compose exec api python -m app.crawler.backfill_extras
        docker compose exec api python -m app.crawler.backfill_extras --all   # trích lại toàn bộ
"""
from __future__ import annotations

import sys
from collections import Counter

from sqlalchemy import create_engine, text

from ..config import settings
from .extras import extract_extras
from .repo import ListingRepo


def main(force_all: bool = False) -> dict:
    engine = create_engine(settings.database_url, pool_pre_ping=True)
    repo = ListingRepo(engine)
    if force_all:
        with engine.connect() as conn:
            rows = [dict(r) for r in conn.execute(text(
                "SELECT source, source_id, title, description FROM aggregated_listings "
                "WHERE source_id IS NOT NULL ORDER BY id")).mappings().all()]
    else:
        rows = repo.pending_extras()

    hit = Counter()
    for r in rows:
        ex = extract_extras(r["title"], r["description"]).as_dict()
        repo.set_extras(r["source"], r["source_id"], ex)
        for k, v in ex.items():
            if v is not None:
                hit[k] += 1

    stats = {"total": len(rows), **{f"has_{k}": v for k, v in sorted(hit.items())}}
    print("backfill_extras:", stats)
    return stats


if __name__ == "__main__":
    main(force_all="--all" in sys.argv)
