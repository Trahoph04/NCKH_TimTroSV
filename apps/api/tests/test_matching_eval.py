"""Phần ghép bạn bổ sung phiên 05/10: thời điểm cần phòng, chọn thẻ (thật trước ·
trần thẻ mô phỏng · ε-greedy), độ tản, decided_ms, ghép lại không mất vết,
pass sau match, lời mời kèm lời nhắn, chấm điểm làm mù, rate limit.
"""
from __future__ import annotations

import random
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app import ratelimit
from app.main import app, engine
from app.matching import filters as F
from app.matching.profile import Profile
from app.matching.repo import MIN_SIM_SLOTS, _choose
from app.matching.score import pair_score
from app.matching.weights import DEFAULT

client = TestClient(app)

SOON = "Càng sớm càng tốt (trong tháng này)"
NEXT_TERM = "Đầu học kỳ tới"
TWO_MONTHS = "Trong 2–3 tháng tới"
NOT_URGENT = "Chưa gấp, đang tìm hiểu trước"


@pytest.fixture(autouse=True)
def _fresh_limits():
    ratelimit.reset()
    yield
    ratelimit.reset()


def P(uid: int, **kw) -> Profile:
    base = dict(gender="nam", sleep_time=1, cleanliness=4, noise_tolerance=3,
                budget_band=1, scenario=2)
    base.update(kw)
    return Profile.from_row({"user_id": uid, **base})


# ─────────────────────────── lọc thời điểm cần phòng ─────────────────────────

def test_need_from_lech_qua_2_thang_bi_loai():
    assert F.hard_filter_reason(P(1, need_from=SOON), P(2, need_from=NEXT_TERM)) == "need_from_gap"


def test_need_from_lech_2_thang_van_qua():
    assert F.passes_hard_filters(P(1, need_from=SOON), P(2, need_from=TWO_MONTHS))


def test_need_from_chua_gap_hoac_null_khong_bao_gio_loai():
    """'Chưa gấp' = linh hoạt; thiếu dữ liệu không phải lý do loại (như ngân sách)."""
    assert F.passes_hard_filters(P(1, need_from=SOON), P(2, need_from=NOT_URGENT))
    assert F.passes_hard_filters(P(1, need_from=SOON), P(2, need_from=None))


def test_only_feasibility_gap_khong_bao_gio_noi_loc_an_toan():
    assert F.only_feasibility_gap(P(1, budget_band=0), P(2, budget_band=4))
    assert F.only_feasibility_gap(P(1, need_from=SOON), P(2, need_from=NEXT_TERM))
    # khác giới / deal-breaker cứng / ở một mình ⇒ KHÔNG được coi là "chỉ lệch khả thi"
    assert not F.only_feasibility_gap(P(1), P(2, gender="nu"))
    assert not F.only_feasibility_gap(
        P(1, deal_breakers=["Hút thuốc trong phòng"], budget_band=0),
        P(2, smoke=True, smoke_in_room=True, budget_band=4),
    )
    # budget_gap trả về trước scenario_alone — vẫn phải chặn người muốn ở một mình
    assert not F.only_feasibility_gap(P(1, budget_band=0), P(2, budget_band=4, scenario=1))
    # cặp qua lọc thì không thuộc diện "độ tản"
    assert not F.only_feasibility_gap(P(1), P(2))


# ─────────────────────────────── chọn thẻ ────────────────────────────────────

def _scored(me: Profile, others: list[Profile]) -> list:
    s = [(pair_score(me, p, DEFAULT), p) for p in others]
    s.sort(key=lambda t: (-t[0].score, t[1].user_id))
    return s


def test_choose_ho_so_that_truoc_the_mo_phong_khong_qua_so_the_that():
    me = P(0)
    real = [P(i, cleanliness=1 + i % 2) for i in range(1, 4)]          # 3 thật, điểm thấp hơn
    sims = [P(100 + i, is_simulated=True) for i in range(12)]         # 12 mô phỏng, khớp hoàn hảo
    picked = _choose(_scored(me, real + sims), 10, epsilon=0.0, rng=random.Random(1))
    ids = {p.user_id for _, p, _ in picked}
    assert {1, 2, 3} <= ids, "hồ sơ thật phải luôn được chọn dù điểm thấp hơn"
    n_sim = sum(p.is_simulated for _, p, _ in picked)
    assert n_sim == 3, "thẻ mô phỏng ≤ số thẻ thật (≤ 50% deck)"


def test_choose_khong_co_ho_so_that_van_co_san_the_mo_phong():
    picked = _choose(_scored(P(0), [P(100 + i, is_simulated=True) for i in range(6)]), 10,
                     epsilon=0.0, rng=random.Random(1))
    assert len(picked) == MIN_SIM_SLOTS


def test_choose_epsilon_lay_dung_20_phan_tram_tu_ngoai_top():
    me = P(0)
    real = [P(i, cleanliness=5 - (i % 5), sleep_time=i % 3) for i in range(1, 31)]
    scored = _scored(me, real)
    top10 = {p.user_id for _, p in scored[:10]}
    picked = _choose(scored, 10, epsilon=0.2, rng=random.Random(7))
    explore = [p for _, p, ex in picked if ex == "epsilon"]
    assert len(picked) == 10 and len(explore) == 2
    assert all(p.user_id not in top10 for p in explore), "thẻ khám phá phải nằm NGOÀI top"


def test_choose_epsilon_tat_dinh_theo_seed():
    scored = _scored(P(0), [P(i, cleanliness=1 + i % 5) for i in range(1, 21)])
    a = _choose(scored, 8, epsilon=0.2, rng=random.Random("x"))
    b = _choose(scored, 8, epsilon=0.2, rng=random.Random("x"))
    assert [p.user_id for _, p, _ in a] == [p.user_id for _, p, _ in b]


def test_choose_pool_nho_hon_deck_thi_khong_kham_pha():
    picked = _choose(_scored(P(0), [P(1), P(2), P(3)]), 10, epsilon=0.2, rng=random.Random(1))
    assert len(picked) == 3 and all(ex is None for _, _, ex in picked)


# ──────────────────────────────── API (DB thật) ──────────────────────────────

def _user(gender: str = "nam", **prof) -> dict:
    email = f"mt_{uuid4().hex[:8]}@example.com"
    r = client.post("/auth/register", json={"email": email, "password": "testpass123", "name": "SV"})
    assert r.status_code == 201, r.text
    h = {"Authorization": f"Bearer {r.json()['access_token']}"}
    uid = client.get("/auth/me", headers=h).json()["id"]
    body = {"gender": gender, "sleep_time": 1, "cleanliness": 4, "noise_tolerance": 3,
            "budget_band": 1, "scenario": 2}
    body.update(prof)
    assert client.post("/matching/profile", json=body, headers=h).status_code == 200
    return {"id": uid, "h": h}


def _swipe(a: dict, b: dict, decision: str = "like"):
    return client.post("/matching/swipe", json={"target_id": b["id"], "decision": decision},
                       headers=a["h"])


def test_api_decided_ms_tinh_phia_server_tu_deck_log():
    a = _user(gender="nu")
    d = client.get("/matching/deck?limit=1", headers=a["h"]).json()
    assert d["items"]
    t = d["items"][0]["user_id"]
    assert client.post("/matching/swipe", json={"target_id": t, "decision": "pass",
                                                "decided_ms": 1},
                       headers=a["h"]).status_code == 200
    with engine.connect() as conn:
        ms = conn.execute(text("SELECT decided_ms FROM swipes WHERE user_id=:u AND target_id=:t"),
                          {"u": a["id"], "t": t}).scalar()
    assert ms is not None and ms >= 0 and ms != 1   # không lấy số client gửi


def test_api_ghep_lai_sau_khi_huy_giu_vet_unmatched():
    a, b = _user(), _user()
    assert _swipe(a, b).status_code == 200
    conv1 = _swipe(b, a).json()["conversation_id"]
    assert client.delete(f"/chat/conversations/{conv1}", headers=a["h"]).status_code == 204
    _swipe(a, b)
    res = _swipe(b, a).json()
    assert res["matched"] is True and res["conversation_id"] != conv1
    with engine.connect() as conn:
        statuses = sorted(conn.execute(text(
            "SELECT status FROM match_requests WHERE (from_user=:a AND to_user=:b) "
            "OR (from_user=:b AND to_user=:a)"), {"a": a["id"], "b": b["id"]}).scalars())
    assert statuses == ["accepted", "unmatched"], "lần ghép trước phải còn vết 'unmatched'"


def test_api_pass_nguoi_dang_ghep_thi_xoa_hoi_thoai():
    a, b = _user(), _user()
    _swipe(a, b)
    conv = _swipe(b, a).json()["conversation_id"]
    r = _swipe(a, b, "pass")
    assert r.status_code == 200 and r.json().get("unmatched") is True
    assert client.get(f"/chat/conversations/{conv}", headers=b["h"]).status_code == 404
    with engine.connect() as conn:
        st = conn.execute(text("SELECT mr.status FROM match_requests mr WHERE "
                               "(from_user=:a AND to_user=:b) OR (from_user=:b AND to_user=:a)"),
                          {"a": a["id"], "b": b["id"]}).scalar()
    assert st == "unmatched"


def test_api_like_lech_ngan_sach_bi_chan_tru_khi_the_do_tan():
    a, b = _user(budget_band=0), _user(budget_band=4)
    assert _swipe(a, b).status_code == 409
    with engine.begin() as conn:   # giả lập deck buổi thử nghiệm đã đưa b cho a như thẻ độ tản
        conn.execute(text("INSERT INTO deck_log (user_id, target_id, position, deck_mode, explore) "
                          "VALUES (:u, :t, 0, 'random', 'spread')"), {"u": a["id"], "t": b["id"]})
    assert _swipe(a, b).status_code == 200
    # b đáp lại lời thích của a: được nới vì a đã tự chấp nhận độ lệch
    res = _swipe(b, a)
    assert res.status_code == 200 and res.json()["matched"] is True


def test_api_the_do_tan_khong_noi_khac_gioi():
    a, b = _user(gender="nam", budget_band=0), _user(gender="nu", budget_band=4)
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO deck_log (user_id, target_id, position, deck_mode, explore) "
                          "VALUES (:u, :t, 0, 'random', 'spread')"), {"u": a["id"], "t": b["id"]})
    assert _swipe(a, b).status_code == 409


def test_api_loi_moi_kem_loi_nhan_hien_trong_likes_va_nhan_thi_thanh_doi():
    a, b = _user(), _user()
    r = client.post("/matching/invite", json={"target_id": b["id"], "note": "Mình ở gần Khu 2"},
                    headers=a["h"])
    assert r.status_code == 200, r.text
    inv = r.json()["invite_id"]
    assert inv and r.json()["matched"] is False

    likes = client.get("/matching/likes", headers=b["h"]).json()["items"]
    mine = [x for x in likes if x["user_id"] == a["id"]]
    assert mine and mine[0]["note"] == "Mình ở gần Khu 2" and mine[0]["invite_id"] == inv
    got = client.get("/matching/invites", headers=b["h"]).json()
    assert any(x["invite_id"] == inv for x in got["received"])
    assert any(x["invite_id"] == inv for x in client.get("/matching/invites", headers=a["h"]).json()["sent"])

    # người khác không trả lời hộ được
    c = _user()
    assert client.post(f"/matching/invites/{inv}/respond", json={"accept": True},
                       headers=c["h"]).status_code == 404

    res = client.post(f"/matching/invites/{inv}/respond", json={"accept": True}, headers=b["h"])
    assert res.status_code == 200 and res.json()["matched"] is True
    with engine.connect() as conn:
        row = conn.execute(text("SELECT status, note FROM match_requests WHERE id=:i"),
                           {"i": inv}).mappings().one()
    assert row["status"] == "accepted" and row["note"] == "Mình ở gần Khu 2"
    # đã xử lý rồi thì không trả lời lại được
    assert client.post(f"/matching/invites/{inv}/respond", json={"accept": False},
                       headers=b["h"]).status_code == 409


def test_api_tu_choi_loi_moi():
    a, b = _user(), _user()
    inv = client.post("/matching/invite", json={"target_id": b["id"]}, headers=a["h"]).json()["invite_id"]
    r = client.post(f"/matching/invites/{inv}/respond", json={"accept": False}, headers=b["h"])
    assert r.status_code == 200 and r.json()["matched"] is False
    with engine.connect() as conn:
        assert conn.execute(text("SELECT status FROM match_requests WHERE id=:i"),
                            {"i": inv}).scalar() == "rejected"


def test_api_loi_moi_van_qua_loc_an_toan():
    a, b = _user(gender="nam"), _user(gender="nu")
    assert client.post("/matching/invite", json={"target_id": b["id"]}, headers=a["h"]).status_code == 409


def test_api_cham_diem_lam_mu_5_the_on_dinh_va_khong_lo_nhom():
    u = _user(gender="nam")
    d = client.get("/matching/rate", headers=u["h"]).json()
    assert len(d["items"]) == 5, d
    for it in d["items"]:
        assert "arm" not in it and "score" not in it and "algo_rank" not in it
        assert it["rating"] is None and it["profile"] is not None
    again = client.get("/matching/rate", headers=u["h"]).json()
    assert [i["card_code"] for i in again["items"]] == [i["card_code"] for i in d["items"]]

    with engine.connect() as conn:
        arms = sorted(conn.execute(text("SELECT arm FROM roommate_ratings WHERE rater_id=:u"),
                                   {"u": u["id"]}).scalars())
    assert arms == ["algo"] * 3 + ["random"] * 2

    code = d["items"][0]["card_code"]
    assert client.post("/matching/rate", json={"card_code": code, "rating": 4},
                       headers=u["h"]).status_code == 204
    assert client.post("/matching/rate", json={"card_code": code, "rating": 6},
                       headers=u["h"]).status_code == 422
    assert client.post("/matching/rate", json={"card_code": "ZZZZ", "rating": 3},
                       headers=u["h"]).status_code == 404
    after = client.get("/matching/rate", headers=u["h"]).json()
    assert after["items"][0]["rating"] == 4 and after["done"] is False


def test_api_rate_limit_swipe_tra_429():
    a = _user()
    limit, _ = ratelimit.LIMITS["swipe"]
    for _ in range(limit):
        ratelimit.check_rate("swipe", a["id"])
    b = _user()
    r = _swipe(a, b)
    assert r.status_code == 429 and "Retry-After" in r.headers
