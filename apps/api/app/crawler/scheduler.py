import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy.engine import Engine

from .nhatot import run_nhatot
from .pipeline import run_source
from .repo import ListingRepo

log = logging.getLogger("crawler.scheduler")

# Nguồn đang hoạt động
ENABLED_SOURCES = [
    "phongtro123",
    "tromoi",
    "mogi",
    "bds123",
    "nhadatcantho",
    "nhadatcantho247",
    "nhatot",  # JSON gateway — toạ độ thật, có deposit (xem nhatot.py)
]


async def _job(engine: Engine, source: str, mode: str) -> None:
    repo = ListingRepo(engine)
    try:
        if source == "nhatot":
            await run_nhatot(repo, mode)   # JSON gateway, không dùng selector HTML
        else:
            await run_source(source, mode, repo)
        
        # Làm sạch sau khi crawl. PHẢI qua threadpool: run_cleaner là SQLAlchemy
        # đồng bộ, gọi thẳng trong `async def` sẽ chặn event loop — mà đó đúng là
        # event loop đang giữ MỌI WebSocket chat (/chat/ws). Hệ quả cũ: cứ 5 giờ,
        # lúc crawl xong, toàn bộ chat realtime đứng im vài chục giây (tin nhắn,
        # "đang nhập", presence) mà không có lỗi nào trong log.
        from starlette.concurrency import run_in_threadpool

        from app.cleaner.pipeline import run_cleaner
        await run_in_threadpool(run_cleaner, engine)

    except Exception:  # noqa: BLE001 — job không được làm chết scheduler
        log.exception("crawl job failed source=%s mode=%s", source, mode)


def build_scheduler(engine: Engine) -> AsyncIOScheduler:
    """
    Near-fresh batch, KHÔNG real-time:
      - incremental mỗi 5h (trang 1-2): bắt tin mới nhanh, ít request
      - full sweep 3h sáng: quét sâu + đánh dấu expired
    """
    sched = AsyncIOScheduler(timezone="Asia/Ho_Chi_Minh")
    for source in ENABLED_SOURCES:
        sched.add_job(
            _job, CronTrigger(hour="*/5"), args=[engine, source, "incremental"],
            id=f"{source}-incremental", max_instances=1, coalesce=True,
        )
        sched.add_job(
            _job, CronTrigger(hour=3, minute=0), args=[engine, source, "full"],
            id=f"{source}-full", max_instances=1, coalesce=True,
        )
    return sched
