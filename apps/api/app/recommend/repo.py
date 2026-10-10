import json
import random
import secrets
import time
import threading

from sqlalchemy import text
from sqlalchemy.engine import Engine

from ..listings.repo import visible_clause
from .core import MARKET_RADIUS_M, Candidate

# Danh mục ứng viên đọc lại tối đa mỗi 60 s: 1 lượt đánh giá chạy 3 hệ liền nhau, và ~1.300 tin +
# đếm POI quanh ~140 toạ độ không cần tính lại từng request.
_CACHE_TTL = 60.0
_cache: tuple[float, list[Candidate]] | None = None
_cache_lock = threading.Lock()

def clear_cache() -> None:
    """Test/CLI vừa ghi tin mới thì gọi để lần xếp hạng sau đọc lại danh mục."""
    global _cache
    with _cache_lock:
        _cache = None


_BUDGET_BAND_MAX = {0: 1_500_000, 1: 2_000_000, 2: 2_500_000, 3: 3_500_000, 4: 4_500_000}  # câu C1


class RecommendRepo:
    def __init__(self, engine: Engine):
        self.engine = engine

    def candidates(self) -> list[Candidate]:
        global _cache
        with _cache_lock:
            if _cache and time.monotonic() - _cache[0] < _CACHE_TTL:
                return _cache[1]
        with self.engine.connect() as conn:
            rows = conn.execute(
                text(
                    f"""
                    WITH v AS (
                        SELECT id, price, route_time_campus, parsed_amenities, free_hours, listing_type,
                               gender_only, geom, quality_score
                        FROM aggregated_listings
                        WHERE status NOT IN ('expired', 'hidden') AND {visible_clause(None)}
                          AND price IS NOT NULL AND price > 0 AND geom IS NOT NULL
                    ),
                    pts AS (SELECT DISTINCT geom FROM v),
                    mk AS (
                        SELECT pts.geom, (
                            SELECT count(*) FROM pois p
                            WHERE p.category IN ('cho', 'sieu_thi')
                              AND ST_DWithin(p.geom::geography, pts.geom::geography, :r)
                        ) AS n
                        FROM pts
                    )
                    SELECT v.id, v.price, v.route_time_campus, v.parsed_amenities, v.free_hours,
                           v.listing_type::text AS listing_type, v.gender_only, v.quality_score,
                           ST_Y(v.geom) AS lat, ST_X(v.geom) AS lng, mk.n AS market
                    FROM v JOIN mk ON mk.geom = v.geom
                    """
                ),
                {"r": MARKET_RADIUS_M},
            ).mappings().all()
        cands = []
        for r in rows:
            rt = list(r["route_time_campus"] or [])
            rt = (rt + [None, None, None])[:3]
            am = r["parsed_amenities"] or {}
            cands.append(Candidate(
                id=r["id"], price=r["price"], minutes=tuple(rt),
                amenities=frozenset(k for k, v in am.items() if v is True),
                free_hours=r["free_hours"], listing_type=r["listing_type"], gender_only=r["gender_only"],
                lat=r["lat"], lng=r["lng"], market_pois=r["market"] or 0, quality=r["quality_score"] or 0.0,
            ))
        with _cache_lock:
            _cache = (time.monotonic(), cands)
        return cands

    def prefill(self, user_id: int) -> dict:
        with self.engine.connect() as conn:
            r = conn.execute(
                text("SELECT budget_band, gender FROM roommate_profiles WHERE user_id = :u"), {"u": user_id}
            ).mappings().first()
        if not r:
            return {}
        return {"budget": _BUDGET_BAND_MAX.get(r["budget_band"]), "gender": r["gender"]}

    # ── đánh giá mù ──

    def create_session(self, user_id: int, criteria: dict, relaxed: list[str], algo_ver: str,
                       rankings: dict[str, list[int]], utilities: dict[int, float]) -> int:
        """rankings: {'proposed'|'price'|'cosine': [listing_id theo hạng]} → gộp, xáo, ghi thẻ."""
        pool: dict[int, dict[str, int]] = {}
        for system, ids in rankings.items():
            for rank, lid in enumerate(ids, start=1):
                pool.setdefault(lid, {})[system] = rank
        order = list(pool)
        random.SystemRandom().shuffle(order)  # thứ tự hiển thị không được lộ hệ/hạng
        with self.engine.begin() as conn:
            sid = conn.execute(
                text(
                    "INSERT INTO rec_eval_sessions (user_id, criteria, relaxed, algo_ver) "
                    "VALUES (:u, CAST(:c AS JSONB), :rx, :v) RETURNING id"
                ),
                {"u": user_id, "c": json.dumps(criteria, ensure_ascii=False), "rx": relaxed, "v": algo_ver},
            ).scalar_one()
            for pos, lid in enumerate(order):
                ranks = pool[lid]
                conn.execute(
                    text(
                        "INSERT INTO rec_eval_cards (session_id, listing_id, card_code, display_pos, "
                        "rank_proposed, rank_price, rank_cosine, utility) "
                        "VALUES (:s, :l, :code, :pos, :rp, :rpr, :rc, :ut)"
                    ),
                    {"s": sid, "l": lid, "code": secrets.token_hex(3).upper(), "pos": pos,
                     "rp": ranks.get("proposed"), "rpr": ranks.get("price"), "rc": ranks.get("cosine"),
                     "ut": utilities.get(lid)},
                )
        return sid

    def latest_session(self, user_id: int) -> dict | None:
        with self.engine.connect() as conn:
            s = conn.execute(
                text(
                    "SELECT id, criteria, completed_at FROM rec_eval_sessions WHERE user_id = :u "
                    "ORDER BY created_at DESC, id DESC LIMIT 1"
                ),
                {"u": user_id},
            ).mappings().first()
            if not s:
                return None
            cards = conn.execute(
                text(
                    "SELECT card_code, listing_id, relevance FROM rec_eval_cards "
                    "WHERE session_id = :s ORDER BY display_pos"
                ),
                {"s": s["id"]},
            ).mappings().all()
        return {"id": s["id"], "criteria": s["criteria"], "completed": s["completed_at"] is not None,
                "cards": [dict(c) for c in cards]}

    def judge(self, user_id: int, card_code: str, relevance: int) -> bool:
        """False nếu thẻ không thuộc phiên của user. Chấm lại được (đổi ý) — giữ lần cuối."""
        with self.engine.begin() as conn:
            sid = conn.execute(
                text(
                    "UPDATE rec_eval_cards c SET relevance = :r, judged_at = now() "
                    "FROM rec_eval_sessions s WHERE c.card_code = :code AND c.session_id = s.id "
                    "AND s.user_id = :u RETURNING c.session_id"
                ),
                {"r": relevance, "code": card_code, "u": user_id},
            ).scalar()
            if sid is None:
                return False
            conn.execute(
                text(
                    "UPDATE rec_eval_sessions SET completed_at = now() WHERE id = :s AND completed_at IS NULL "
                    "AND NOT EXISTS (SELECT 1 FROM rec_eval_cards WHERE session_id = :s AND relevance IS NULL)"
                ),
                {"s": sid},
            )
        return True

    def export_rows(self) -> list[dict]:
        with self.engine.connect() as conn:
            return [dict(r) for r in conn.execute(text(
                """
                SELECT s.id AS session_id, s.user_id, s.algo_ver, s.criteria, s.relaxed, s.created_at,
                       s.completed_at, c.listing_id, c.card_code, c.display_pos, c.rank_proposed,
                       c.rank_price, c.rank_cosine, c.utility, c.relevance, c.judged_at
                FROM rec_eval_sessions s JOIN rec_eval_cards c ON c.session_id = s.id
                ORDER BY s.id, c.display_pos
                """
            )).mappings()]
