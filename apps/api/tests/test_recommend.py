"""Gợi ý nhà trọ (docs/specs/Recommendation.md): hàm hữu dụng, trọng số khảo sát, nới ràng buộc, MMR,
2 hệ đối chứng, API và luồng đánh giá mù. Phần DB chạy trên nckh_test."""
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.main import app, engine
from app.recommend import core
from app.recommend.core import Candidate, Query
from app.recommend.repo import RecommendRepo, clear_cache

client = TestClient(app)


def cand(i: int, price: int, m: float | None, **kw) -> Candidate:
    base = dict(amenities=frozenset(), free_hours=None, listing_type="phong_tro", gender_only=None,
                lat=10.03 + i * 0.01, lng=105.77, market_pois=0, quality=0.5)
    base.update(kw)
    return Candidate(id=i, price=price, minutes=(m, m, m), **base)


# ── Hàm hữu dụng ──
def test_price_utility_monotone_and_anchored():
    b = 2_000_000
    assert core.u_price(b, b) == pytest.approx(0.6)
    assert core.u_price(b // 2, b) == pytest.approx(1.0)
    assert core.u_price(int(1.2 * b), b) == pytest.approx(0.0)
    prices = range(500_000, 2_600_000, 50_000)
    us = [core.u_price(p, b) for p in prices]
    assert all(a >= c for a, c in zip(us, us[1:]))  # rẻ hơn không bao giờ tệ hơn


def test_commute_utility_monotone_and_missing():
    assert core.u_commute(4, 10) == 1.0
    assert core.u_commute(10, 10) == pytest.approx(0.6)
    assert core.u_commute(core.minutes_cap(10), 10) == pytest.approx(0.0)
    us = [core.u_commute(m / 2, 10) for m in range(0, 40)]
    assert all(a >= c for a, c in zip(us, us[1:]))
    assert core.u_commute(None, 10) == core.MISSING_MINUTES_U


def test_unknown_amenity_is_neutral_not_absent():
    q = Query(budget=2_000_000, required=("wifi", "private_wc"))
    silent = core.score(cand(1, 1_800_000, 5), q)
    stated = core.score(cand(2, 1_800_000, 5, amenities=frozenset({"wifi", "private_wc"})), q)
    assert silent.utilities["tien_nghi"] == core.THETA
    assert stated.utilities["tien_nghi"] == 1.0
    assert silent.unknown == ["wifi", "private_wc"] and stated.unknown == []
    _, ask = core.explain(silent, q)
    assert ask == ["Wifi", "WC riêng"]


def test_weights_from_survey_and_personal_shrinkage():
    base = core.weights()
    assert sum(base.values()) == pytest.approx(1.0)
    assert base["gia"] == pytest.approx(20 / 74)
    mine = core.weights(("gan_cho", "cho_de_xe", "tien_nghi"))
    assert sum(mine.values()) == pytest.approx(1.0)
    assert mine["gan_cho"] > base["gan_cho"] and mine["gia"] < base["gia"]
    assert core.weights(("an_ninh",)) == base  # yếu tố đã bỏ không làm lệch trọng số


# ── Lọc cứng + nới ──
def test_relaxation_reports_what_was_loosened():
    cands = [cand(i, 2_300_000, 22) for i in range(12)]  # vượt cả giá (×1,15) lẫn thời gian
    q = Query(budget=2_000_000, max_minutes=10)
    pool, relaxed = core.filter_with_relaxation(cands, q, k=10)
    assert len(pool) == 12
    assert any("thời gian" in r for r in relaxed)
    pool2, relaxed2 = core.filter_with_relaxation([cand(i, 1_500_000, 5) for i in range(12)], q, k=10)
    assert relaxed2 == []


def test_gender_only_listing_hidden_from_other_gender():
    q = Query(budget=2_000_000, gender="nam")
    assert not core.passes(cand(1, 1_500_000, 5, gender_only="nu"), q)
    assert core.passes(cand(2, 1_500_000, 5, gender_only="nam"), q)
    assert core.passes(cand(3, 1_500_000, 5, gender_only="nu"), Query(budget=2_000_000))


# ── MMR + thứ tự ──
def test_mmr_spreads_duplicates_and_result_sorted_by_utility():
    same = [cand(i, 1_000_000, 3, lat=10.0146, lng=105.7615) for i in range(12)]  # 12 tin chung 1 điểm phường
    spread = [cand(100 + i, 1_100_000, 4) for i in range(6)]
    q = Query(budget=2_000_000, max_minutes=10)
    top, _, n = core.recommend(same + spread, q, k=10)
    pts = {(c.c.lat, c.c.lng) for c in top}
    plain = sorted((core.score(c, q) for c in same + spread), key=lambda s: -s.utility)[:10]
    assert len(pts) > len({(s.c.lat, s.c.lng) for s in plain})
    assert [s.utility for s in top] == sorted((s.utility for s in top), reverse=True)
    assert n == 18
    assert core.ils([s.c for s in top], q.budget) < core.ils([s.c for s in plain], q.budget)


# ── Hệ đối chứng ──
def test_baseline_price_respects_raw_constraints():
    cands = [cand(1, 2_100_000, 3), cand(2, 1_900_000, 12), cand(3, 1_200_000, 8), cand(4, 900_000, 9)]
    out = core.baseline_price(cands, Query(budget=2_000_000, max_minutes=10))
    assert [c.id for c in out] == [4, 3]


def test_baseline_cosine_ignores_budget_like_original_design():
    cands = [cand(1, 4_000_000, 20), cand(2, 1_000_000, 2), cand(3, 2_000_000, 10)]
    out = core.baseline_cosine(cands, Query(budget=2_000_000, max_minutes=10))
    assert len(out) == 3  # không lọc — chính là lỗi đo được ở spec


# ── API ──
def _insert(n: int, tag: str) -> list[int]:
    ids = []
    with engine.begin() as conn:
        for i in range(n):
            ids.append(conn.execute(text(
                "INSERT INTO aggregated_listings (title, price, source, source_id, cleaning_status, listing_type, "
                "geocode_confidence, route_time_campus, parsed_amenities, geom) VALUES "
                "(:t, :p, :s, :sid, 'cleaned', 'phong_tro', 'medium', :rt, CAST(:am AS JSONB), "
                "ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)) RETURNING id"
            ), {"t": f"Phòng trọ gợi ý test {i}", "p": 1_200_000 + 50_000 * i, "s": tag, "sid": f"{tag}{i}",
                "rt": [6.0 + i % 4, 4.0 + i % 5, 7.0], "am": '{"wifi": true}' if i % 2 else "{}",
                "lng": 105.76 + 0.004 * i, "lat": 10.02 + 0.003 * i}).scalar_one())
    clear_cache()
    return ids


def _cleanup(tag: str) -> None:
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM aggregated_listings WHERE source = :s"), {"s": tag})
    clear_cache()


def _user_headers() -> tuple[dict, int]:
    email = f"rec_{uuid4().hex[:8]}@example.com"
    r = client.post("/auth/register", json={"email": email, "password": "testpass123"})
    assert r.status_code == 201, r.text
    h = {"Authorization": f"Bearer {r.json()['access_token']}"}
    return h, client.get("/auth/me", headers=h).json()["id"]


CRITERIA = {"budget": 2_000_000, "campus": 1, "max_minutes": 10, "required": ["wifi"],
            "top_factors": ["gia", "gan_truong"]}


def test_recommend_endpoint_returns_explained_items():
    tag = f"rt_{uuid4().hex[:6]}"
    ids = _insert(14, tag)
    try:
        r = client.post("/recommend", json=CRITERIA)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["algo_ver"] == core.ALGO_VERSION and len(body["items"]) == 10
        mine = [it for it in body["items"] if it["listing"]["id"] in ids]
        assert mine, "tin test thoả tiêu chí phải được gợi ý"
        it = mine[0]
        assert 0 <= it["match"] <= 100 and it["reasons"]
        assert sum(body["weights"].values()) == pytest.approx(1.0, abs=0.01)
    finally:
        _cleanup(tag)


@pytest.mark.parametrize("bad", [
    {**CRITERIA, "required": ["ho_boi"]},
    {**CRITERIA, "top_factors": ["gia", "gan_truong", "gan_cho", "tien_nghi"]},
    {**CRITERIA, "budget": 100},
    {**CRITERIA, "housing": "khac"},
])
def test_recommend_rejects_bad_input(bad):
    assert client.post("/recommend", json=bad).status_code == 422


def test_blind_eval_session_and_judging():
    tag = f"re_{uuid4().hex[:6]}"
    _insert(14, tag)
    h, uid = _user_headers()
    other, _ = _user_headers()
    try:
        r = client.post("/recommend/eval/session", json=CRITERIA, headers=h)
        assert r.status_code == 200, r.text
        sess = r.json()
        assert 10 <= len(sess["cards"]) <= 30 and sess["judged"] == 0 and not sess["completed"]
        card = sess["cards"][0]
        assert set(card) == {"card_code", "listing", "minutes", "relevance"}  # không lộ hệ/hạng/điểm

        # thẻ của người khác → 404
        assert client.post("/recommend/eval/judge", json={"card_code": card["card_code"], "relevance": 2},
                           headers=other).status_code == 404
        for i, c in enumerate(sess["cards"]):
            assert client.post("/recommend/eval/judge", json={"card_code": c["card_code"], "relevance": i % 3},
                               headers=h).status_code == 204
        done = client.get("/recommend/eval/session", headers=h).json()
        assert done["completed"] and done["judged"] == len(sess["cards"])

        rows = [r for r in RecommendRepo(engine).export_rows() if r["session_id"] == sess["session_id"]]
        assert len(rows) == len(sess["cards"])
        assert sum(1 for r in rows if r["rank_proposed"]) == 10  # đủ top-10 của hệ đề xuất trong pool
        assert all(r["rank_proposed"] or r["rank_price"] or r["rank_cosine"] for r in rows)
    finally:
        _cleanup(tag)
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM rec_eval_sessions WHERE user_id = :u"), {"u": uid})


def test_eval_requires_login():
    assert client.post("/recommend/eval/session", json=CRITERIA).status_code == 403
