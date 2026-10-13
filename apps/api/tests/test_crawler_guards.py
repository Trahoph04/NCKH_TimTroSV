"""Chốt chặn crawler (audit 12/10): /crawler/run chỉ admin; lượt full lỗi/thiếu tin KHÔNG quét expired; crawl không
hồi sinh tin bị rà soát loại / tin admin ẩn; đổi toạ độ thì bỏ phút tới trường cũ. Phần DB chạy trên nckh_test."""
import asyncio
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import text

from app.crawler import pipeline
from app.crawler.fetcher import BlockedError
from app.crawler.repo import ListingRepo
from app.crawler.schemas import NormalizedListing
from app.main import app, engine

client = TestClient(app)


def _register(admin: bool = False) -> dict:
    email = f"crawlguard_{uuid4().hex[:8]}@example.com"
    r = client.post("/auth/register", json={"email": email, "password": "testpass123"})
    assert r.status_code == 201, r.text
    headers = {"Authorization": f"Bearer {r.json()['access_token']}"}
    if admin:
        user_id = client.get("/auth/me", headers=headers).json()["id"]
        with engine.begin() as conn:
            conn.execute(text("UPDATE users SET role = 'admin' WHERE id = :id"), {"id": user_id})
    return headers


# ── /crawler/run ──
def test_crawler_run_requires_admin():
    assert client.post("/crawler/run").status_code == 403  # thiếu Authorization ⇒ 403 (HTTPBearer)
    assert client.post("/crawler/run", headers=_register()).status_code == 403


def test_crawler_run_rejects_unknown_source_and_mode_before_crawling():
    admin = _register(admin=True)
    # source ghép vào đường dẫn file selector ⇒ phải nằm trong whitelist; không lượt crawl nào được chạy
    assert client.post("/crawler/run", params={"source": "../../etc/passwd"}, headers=admin).status_code == 400
    assert client.post("/crawler/run", params={"mode": "zzz"}, headers=admin).status_code == 400


# ── quét expired chỉ khi lượt full sạch ──
class _FakeRepo:
    def __init__(self, active: int):
        self.active = active
        self.swept: list | None = None

    def start_run(self, source, mode):
        return 1

    def finish_run(self, run_id, **counts):
        self.counts = counts

    def upsert(self, n):
        return "new"

    def set_extras(self, *a): ...
    def set_contact(self, *a): ...
    def set_address(self, *a): ...
    def refresh_scores(self): ...

    def pending_route(self):
        return []

    def active_count(self, source):
        return self.active

    def mark_misses(self, source, seen_ids):
        self.swept = seen_ids
        return 0


class _NoGeo:
    async def geocode(self, address):
        return None, None, "failed"


class _Fetcher:
    def __init__(self, list_html: str | None, detail_html: str = ""):
        self.list_html, self.detail_html = list_html, detail_html

    async def get(self, url):
        if self.list_html is None:
            raise BlockedError("403 Forbidden")
        return self.list_html if "chi-tiet" not in url and ".html" not in url else self.detail_html


def _run(repo, fetcher):
    return asyncio.run(pipeline.run_source("phongtro123", "full", repo, fetcher=fetcher, geocoder=_NoGeo()))


def test_full_sweep_skipped_when_list_page_blocked():
    repo = _FakeRepo(active=150)
    _run(repo, _Fetcher(None))
    assert repo.swept is None


def test_full_sweep_skipped_when_parse_finds_too_few(phongtro_html, phongtro_detail_html):
    repo = _FakeRepo(active=100_000)  # selector hỏng/ít trang: thấy vài chục tin so với rất nhiều tin đang hiện
    _run(repo, _Fetcher(phongtro_html, phongtro_detail_html))
    assert repo.swept is None


def test_full_sweep_runs_when_clean(phongtro_html, phongtro_detail_html):
    repo = _FakeRepo(active=1)
    _run(repo, _Fetcher(phongtro_html, phongtro_detail_html))
    assert repo.swept  # lượt sạch, thấy đủ tin ⇒ được quét


# ── upsert: không hồi sinh tin bị loại, đổi toạ độ thì bỏ phút cũ ──
def _listing(src: str, sid: str, lat: float, lng: float) -> NormalizedListing:
    return NormalizedListing(source=src, source_id=sid, title="Phòng trọ test guard", price=2_000_000,
                             content_hash="h1", lat=lat, lng=lng, geocode_confidence="medium")


def _row(src: str, sid: str) -> dict:
    with engine.connect() as conn:
        return dict(conn.execute(text(
            "SELECT status, route_time_campus FROM aggregated_listings WHERE source = :s AND source_id = :i"),
            {"s": src, "i": sid}).mappings().one())


def test_upsert_keeps_audited_listing_expired_and_resets_route_on_move():
    src, repo = "test-guard", ListingRepo(engine)
    a, b = uuid4().hex[:10], uuid4().hex[:10]
    try:
        repo.upsert(_listing(src, a, 10.03, 105.77))
        repo.upsert(_listing(src, b, 10.03, 105.77))
        with engine.begin() as conn:
            conn.execute(text("UPDATE aggregated_listings SET route_time_campus = ARRAY[4, 0, 3.4]::real[] "
                              "WHERE source = :s"), {"s": src})
            conn.execute(text("UPDATE aggregated_listings SET status = 'expired', audit_reason = 'test' "
                              "WHERE source = :s AND source_id = :i"), {"s": src, "i": a})

        repo.upsert(_listing(src, a, 10.03, 105.77))
        assert _row(src, a)["status"] == "expired"  # bị audit loại ⇒ gặp lại vẫn không sống lại

        repo.upsert(_listing(src, b, 10.03, 105.77))
        assert _row(src, b)["route_time_campus"] is not None  # toạ độ y nguyên ⇒ giữ phút
        repo.upsert(_listing(src, b, 10.034, 105.78))
        assert _row(src, b)["route_time_campus"] is None  # dời toạ độ ⇒ phút cũ bị bỏ để tính lại
    finally:
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM aggregated_listings WHERE source = :s"), {"s": src})


def test_mark_misses_leaves_hidden_listing_alone():
    src, repo = "test-guard-hidden", ListingRepo(engine)
    sid = uuid4().hex[:10]
    try:
        repo.upsert(_listing(src, sid, 10.03, 105.77))
        with engine.begin() as conn:
            conn.execute(text("UPDATE aggregated_listings SET status = 'hidden', miss_count = 5 WHERE source = :s"),
                         {"s": src})
        repo.mark_misses(src, [])
        assert _row(src, sid)["status"] == "hidden"  # admin ẩn ⇒ không chuyển expired (rồi bị upsert bật lại)
    finally:
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM aggregated_listings WHERE source = :s"), {"s": src})
