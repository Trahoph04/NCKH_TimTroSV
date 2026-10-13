"""Crawl thủ công 1 nguồn — dùng chung cho POST /crawler/run (chỉ admin) và dòng lệnh:

    docker compose exec -T api python -m app.crawler.run_once --source phongtro123 --mode incremental

Dòng lệnh chạy TRONG container nên không cần token: recrawl_all.sh gọi đường này thay vì curl vào API (trước 12/10
endpoint không đòi đăng nhập ⇒ ai trong LAN demo cũng kích được crawl full hàng loạt).
"""
import argparse
import asyncio
import json
import logging

from sqlalchemy.engine import Engine
from starlette.concurrency import run_in_threadpool

from .nhatot import run_nhatot
from .pipeline import run_source
from .repo import ListingRepo
from .scheduler import ENABLED_SOURCES

MODES = ("incremental", "full")


async def run_crawl_once(engine: Engine, source: str, mode: str) -> dict:
    if mode not in MODES:
        raise ValueError(f"mode phải là một trong {MODES}")
    # whitelist: source ghép thẳng vào đường dẫn file selector (parser.load_source_config)
    if source not in ENABLED_SOURCES:
        raise ValueError(f"source phải là một trong {ENABLED_SOURCES}")
    repo = ListingRepo(engine)
    counts = await run_nhatot(repo, mode) if source == "nhatot" else await run_source(source, mode, repo)
    # làm sạch ngay để manual run cũng cho ra data 'cleaned' (không kẹt ở 'raw').
    # Qua threadpool vì cùng lý do ở crawler/scheduler.py: SQLAlchemy đồng bộ gọi
    # thẳng trong `async def` sẽ chặn event loop đang giữ mọi WebSocket chat.
    from ..cleaner.pipeline import run_cleaner
    await run_in_threadpool(run_cleaner, engine)
    return {"source": source, "mode": mode, **counts}


def main() -> None:
    from sqlalchemy import create_engine

    from ..config import settings

    ap = argparse.ArgumentParser(description="Crawl thủ công 1 nguồn rồi chạy cleaner")
    ap.add_argument("--source", required=True, choices=ENABLED_SOURCES)
    ap.add_argument("--mode", default="incremental", choices=MODES)
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO)
    engine = create_engine(settings.database_url, pool_pre_ping=True)
    try:
        print(json.dumps(asyncio.run(run_crawl_once(engine, args.source, args.mode)), ensure_ascii=False, default=str))
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
