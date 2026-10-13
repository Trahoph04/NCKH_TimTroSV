from contextlib import asynccontextmanager
import asyncio
import logging

from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy import create_engine, text
import httpx
import redis

from .config import settings
from .crawler import ListingRepo, build_scheduler
from .crawler.run_once import MODES, run_crawl_once
from .crawler.scheduler import ENABLED_SOURCES
from .listings import init_listings, listings_router
from .admin_users import admin_users_router, init_admin_users
from .reviews import init_reviews, reviews_router
from .auth import AuthRepo, auth_router, init_auth, init_auth_deps
from .auth.deps import require_admin
from .auth.schemas import UserOut
from .chat import ChatHub, chat_router, init_chat
from .chat.body_limit import ChatUploadLimit
from .matching import init_matching, matching_router
from .pois import init_pois, pois_router
from .recommend import init_recommend, recommend_router
from .room_service import chatbot_router, init_chatbot
from .room_service.chatbot.router import close_chatbot, warmup_chatbot
from .room_service.legal_knowledge.admin import router as documents_admin_router

log = logging.getLogger("app.main")

# psycopg3 sync engine; pre_ping avoids stale conns after db restart
engine = create_engine(settings.database_url, pool_pre_ping=True)
redis_client = redis.from_url(settings.redis_url, decode_responses=True)
init_listings(engine)
init_pois(engine)
init_recommend(engine)
init_auth(engine)
init_reviews(engine)
init_auth_deps(AuthRepo(engine))
# hub realtime chat: WebSocket tại chỗ + Redis pub/sub cho nhiều worker (Redis chết ⇒ local-only)
chat_hub = ChatHub(settings.redis_url)
init_chat(engine, chat_hub)
init_admin_users(engine, chat_hub)
init_matching(engine, chat_hub)
init_chatbot(engine)


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler = None
    # nạp E5 + gọi Ollama 1 lần ở thread nền: câu hỏi đầu không phải chờ tải model, mà khởi động
    # API cũng không chờ (Ollama trên host có thể đang tắt — warmup tự nuốt lỗi)
    warmup = (
        asyncio.create_task(asyncio.to_thread(warmup_chatbot))
        if settings.chatbot_warmup_enabled else None
    )
    if settings.crawler_enabled:
        scheduler = build_scheduler(engine)
        scheduler.start()
    try:
        yield
    finally:
        if scheduler:
            scheduler.shutdown(wait=False)
        if warmup:
            await warmup
        close_chatbot()
        engine.dispose()
        redis_client.close()


app = FastAPI(title="NCKH API", version="0.1.0", lifespan=lifespan)
app.add_middleware(ChatUploadLimit)
app.include_router(listings_router)
app.include_router(pois_router)
app.include_router(recommend_router)
app.include_router(auth_router)
app.include_router(admin_users_router)
app.include_router(reviews_router)
app.include_router(matching_router)
app.include_router(chat_router)
app.include_router(chatbot_router)
app.include_router(documents_admin_router)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/health/deps")
def health_deps():
    checks: dict[str, str] = {}

    try:
        with engine.connect() as conn:
            postgis = conn.execute(text("SELECT PostGIS_Version()")).scalar()
            has_vector = conn.execute(
                text("SELECT 1 FROM pg_extension WHERE extname = 'vector'")
            ).scalar()
        checks["postgres"] = "ok"
        checks["postgis"] = postgis or "missing"
        checks["pgvector"] = "ok" if has_vector else "missing"
    except Exception as exc:  # surface the failing dep instead of 500
        checks["postgres"] = f"error: {exc}"

    try:
        checks["redis"] = "ok" if redis_client.ping() else "down"
    except Exception as exc:
        checks["redis"] = f"error: {exc}"

    return checks


@app.get("/health/ai")
def health_ai():
    """Chatbot dùng được tới đâu — không lộ key: chỉ provider/model, Ollama có model chưa, corpus đã nạp chưa."""
    qwen_status = "not-selected"
    if settings.chatbot_llm_provider in ("auto", "qwen"):
        try:
            response = httpx.get(f"{settings.ollama_base_url.rstrip('/')}/api/tags", timeout=3)
            response.raise_for_status()
            models = {item.get("name") for item in response.json().get("models", [])}
            qwen_status = "ok" if settings.ollama_model in models else "model-missing"
        except Exception:
            qwen_status = "unreachable"
    corpus: dict[str, int | str] = {"schema": settings.chatbot_legal_schema}
    try:
        from .room_service.legal_knowledge.storage import legal_sql

        with engine.connect() as conn:
            row = conn.execute(legal_sql(
                "SELECT count(DISTINCT d.id) AS documents, count(c.id) AS chunks, count(c.embedding_vector) AS vectors "
                "FROM legal_documents d LEFT JOIN legal_chunks c ON c.document_id = d.id "
                "WHERE d.status = 'ready' AND d.admin_enabled", settings.chatbot_legal_schema)).mappings().one()
        corpus.update(row)
    except Exception:
        log.warning("health/ai: chưa đọc được corpus %s", settings.chatbot_legal_schema)
        corpus["status"] = "missing"
    return {
        "provider_mode": settings.chatbot_llm_provider,
        "qwen": {"status": qwen_status, "model": settings.ollama_model},
        "gemini": {"configured": bool(settings.configured_gemini_keys), "model": settings.gemini_model},
        "embedding_model": settings.chatbot_embedding_model,
        "legal_corpus": corpus,
    }


@app.get("/crawler/status")
def crawler_status(limit: int = 10):
    """Lần crawl gần nhất mỗi nguồn — health check cho Admin Dashboard (C2.1/C2.3)."""
    return {"enabled": settings.crawler_enabled, "runs": ListingRepo(engine).latest_runs(limit)}


# Một lượt mỗi nguồn: mỗi request tạo Fetcher riêng nên khoảng nghỉ chống chặn IP chỉ có tác dụng trong một lượt.
_crawl_locks: dict[str, asyncio.Lock] = {}


@app.post("/crawler/run")
async def crawler_run(
    source: str = "phongtro123",
    mode: str = "incremental",
    _admin: UserOut = Depends(require_admin),
):
    """Trigger thủ công 1 nguồn — CHỈ admin (crawl full ghi DB, gọi site ngoài + Nominatim + quota ORS).
    Script trên máy host dùng `python -m app.crawler.run_once` trong container thay vì gọi endpoint này."""
    if mode not in MODES:
        raise HTTPException(400, "mode phải là 'incremental' hoặc 'full'")
    if source not in ENABLED_SOURCES:
        raise HTTPException(400, f"source phải là một trong {ENABLED_SOURCES}")
    lock = _crawl_locks.setdefault(source, asyncio.Lock())
    if lock.locked():
        raise HTTPException(409, f"Nguồn {source} đang được crawl")
    async with lock:
        return await run_crawl_once(engine, source, mode)
