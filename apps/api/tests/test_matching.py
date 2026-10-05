"""Ghép bạn ở: thuật toán thuần (không cần DB) + API (DB thật, không mock).

Chia hai phần có chủ đích:
  · Phần THUẦN chạy được mà không có Postgres — đó là lý do filters/score/stable
    không chạm DB. Notebook eval dùng đúng các hàm này.
  · Phần API dùng DB thật như test_chat.py, mỗi test tự tạo user mới nên chạy lặp được.
"""
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.matching import filters as F
from app.matching import survey_map as SM
from app.matching.profile import DEAL_BREAKER, HANH_VI, Profile
from app.matching.score import harmonic, pair_score
from app.matching.stable import blocking_pairs, irving, stable_roommates
from app.matching.weights import DEFAULT, UNIFORM, sensitivity

client = TestClient(app)


def P(uid: int, **kw) -> Profile:
    base = dict(gender="nam", sleep_time=1, cleanliness=4, noise_tolerance=3,
                budget_band=1, scenario=2)
    base.update(kw)
    return Profile.from_row({"user_id": uid, **base})


# ─────────────────────────────── survey_map ────────────────────────────────

def test_budget_band_khong_bi_chuoi_con_an_mat():
    """'2 – 2,5 triệu' CHỨA chuỗi con '2,5' — khớp-chuỗi-con sẽ trả band 3 (sai).

    Lệch 1 bậc làm lọc cứng ngân sách loại oan/bỏ sót cặp mà không báo lỗi.
    """
    assert SM.budget_band("Dưới 1,5 triệu") == 0
    assert SM.budget_band("1,5 – 2 triệu") == 1
    assert SM.budget_band("2 – 2,5 triệu") == 2      # KHÔNG phải 3
    assert SM.budget_band("2,5 – 3,5 triệu") == 3
    assert SM.budget_band("Trên 3,5 triệu") == 4
    assert SM.budget_band("") is None


def test_split_multi_khong_bam_option_chua_dau_phay():
    """split(',') sẽ băm 'Ở bẩn, không dọn dẹp' thành 2 mảnh không khớp option nào
    ⇒ mất sạch deal-breaker ⇒ lọc cứng thành vô hiệu TRONG IM LẶNG."""
    raw = "Hút thuốc trong phòng, Ở bẩn, không dọn dẹp, Ồn ào khuya"
    found, leftover = SM.split_multi(raw, DEAL_BREAKER)
    assert set(found) == {"Hút thuốc trong phòng", "Ở bẩn, không dọn dẹp", "Ồn ào khuya"}
    assert leftover == []

    raw2 = "Tối muộn mình hay còn hoạt động (xem phim, gọi điện, nói chuyện)"
    found2, leftover2 = SM.split_multi(raw2, HANH_VI)
    assert found2 == [raw2] and leftover2 == []


def test_split_multi_tra_ve_token_la():
    """Token lạ = form đã đổi lựa chọn. Phải trả về, không bỏ im."""
    found, leftover = SM.split_multi("Ồn ào khuya, Một lựa chọn mới nào đó", DEAL_BREAKER)
    assert found == ["Ồn ào khuya"]
    assert leftover == ["Một lựa chọn mới nào đó"]


def test_smoking_tach_smoke_khoi_smoke_in_room():
    """Gộp 2 cột thành 1 cờ nhị phân là loại OAN người hút thuốc ra ngoài hút."""
    assert SM.smoking("Mình có hút nhưng ra ngoài hút") == (True, False, False)
    # "không chịu được người ở chung hút" là deal-breaker khai NGẦM — phải suy ra,
    # nếu không người đó mất đúng lớp bảo vệ mình vừa yêu cầu.
    assert SM.smoking("Mình không hút, và KHÔNG chịu được người ở chung hút") == (False, False, True)
    assert SM.smoking("Mình không hút, nhưng người khác hút thì cũng được") == (False, False, False)


def test_gender_chi_nhan_nam_nu():
    assert SM.gender("Nam") == "nam"
    assert SM.gender("Nữ") == "nu"
    assert SM.gender("Không muốn nêu") is None    # ⇒ ngoài pool ghép


# ───────────────────────────────── profile ─────────────────────────────────

def test_gender_null_thi_ngoai_pool():
    """Chính sách chỉ ghép cùng giới: không đoán giới tính của ai."""
    assert not P(1, gender=None).in_pool
    assert P(1, gender="nam").in_pool


def test_ho_so_khong_co_loi_song_thi_ngoai_pool():
    assert not Profile.from_row({"user_id": 1, "gender": "nam"}).in_pool


def test_hanh_vi_la_bi_loc_bo():
    """Lựa chọn sai chính tả lọt vào TEXT[] sẽ không đối chiếu được với
    DB_TO_HANHVI ⇒ deal-breaker nằm im. Chuẩn hoá phải loại nó ngay."""
    p = P(1, hanh_vi=["Mình hay nấu ăn trong phòng", "rác lạ"])
    assert p.hanh_vi == frozenset({"Mình hay nấu ăn trong phòng"})


def test_sentinel_khong_tinh_la_hanh_vi():
    assert P(1, hanh_vi=["Không điều nào ở trên đúng với mình"]).hanh_vi == frozenset()
    assert P(1, deal_breakers=["Mình dễ tính, không có điều nào"]).deal_breakers == frozenset()


def test_share_stuff_suy_tu_hanh_vi():
    assert P(1, hanh_vi=[]).share_stuff is None          # chưa khai ≠ không muốn
    assert P(1, hanh_vi=["Mình hay nấu ăn trong phòng"]).share_stuff == 0
    assert P(1, hanh_vi=["Mình sẵn sàng dùng chung đồ (đồ ăn, đồ dùng)"]).share_stuff == 1


# ───────────────────────────────── filters ─────────────────────────────────

def test_chi_ghep_cung_gioi():
    assert F.hard_filter_reason(P(1, gender="nam"), P(2, gender="nu")) == "gender_mismatch"
    assert F.passes_hard_filters(P(1, gender="nam"), P(2, gender="nam"))


def test_deal_breaker_doi_chieu_qua_DB_TO_HANHVI():
    """Pseudocode gốc giao set(hanh_vi) & set(deal_breakers) — HAI VỐN TỪ KHÁC
    NHAU ('Mình hay nấu ăn trong phòng' vs 'Nấu ăn trong phòng') nên luôn rỗng.
    Lỗi im lặng: API vẫn trả kết quả, chỉ là kết quả sai."""
    victim = P(1, deal_breakers=["Nấu ăn trong phòng"])
    cook = P(2, hanh_vi=["Mình hay nấu ăn trong phòng"])
    assert F.soft_violations(victim, cook) == ["Nấu ăn trong phòng"]


def test_hut_thuoc_ngoai_phong_khong_bi_loai():
    victim = P(1, deal_breakers=["Hút thuốc trong phòng"])
    outside = P(2, smoke=True, smoke_in_room=False)
    inside = P(3, smoke=True, smoke_in_room=True)
    assert F.passes_hard_filters(victim, outside)
    assert F.hard_filter_reason(victim, inside) == "hard_db_a:Hút thuốc trong phòng"


def test_o_ban_la_tang_CUNG_theo_nguong_cleanliness():
    victim = P(1, deal_breakers=["Ở bẩn, không dọn dẹp"])
    assert F.hard_filter_reason(victim, P(2, cleanliness=1)).startswith("hard_db_a:")
    assert F.passes_hard_filters(victim, P(3, cleanliness=4))


def test_deal_breaker_hanh_vi_la_tang_MEM_khong_loai():
    """Nếu mọi deal-breaker là cứng thì 13/19 hồ sơ thật có pool RỖNG (xem
    docstring filters.py). Tầng mềm giữ tính năng sống mà vẫn cảnh báo rõ chữ."""
    victim = P(1, deal_breakers=["Ồn ào khuya"])
    noisy = P(2, hanh_vi=["Tối muộn mình hay còn hoạt động (xem phim, gọi điện, nói chuyện)"])
    assert F.passes_hard_filters(victim, noisy)              # KHÔNG bị loại
    assert F.soft_violations(victim, noisy) == ["Ồn ào khuya"]


def test_deal_breaker_kiem_HAI_CHIEU():
    """Cặp 'A chịu được B nhưng B không chịu được A' vẫn phải bị loại."""
    a = P(1, smoke_in_room=True)
    b = P(2, deal_breakers=["Hút thuốc trong phòng"])
    assert F.hard_filter_reason(a, b) == "hard_db_b:Hút thuốc trong phòng"
    assert F.hard_filter_reason(b, a) == "hard_db_a:Hút thuốc trong phòng"


def test_ngan_sach_lech_qua_1_bac_bi_loai_con_NULL_thi_khong():
    assert F.hard_filter_reason(P(1, budget_band=0), P(2, budget_band=2)) == "budget_gap"
    assert F.passes_hard_filters(P(1, budget_band=0), P(2, budget_band=1))
    # thiếu dữ liệu KHÔNG phải lý do loại ở chiều này (khác giới tính)
    assert F.passes_hard_filters(P(1, budget_band=None), P(2, budget_band=4))


def test_o_mot_minh_khong_ghep_voi_ai():
    assert F.hard_filter_reason(P(1, scenario=1), P(2, scenario=2)) == "scenario_alone"


# ────────────────────────────────── score ──────────────────────────────────

def test_harmonic_khong_chia_cho_0():
    """Công thức trong doc chia cho 0 khi cả hai chiều đều ra s=0."""
    assert harmonic(0.0, 0.0) == 0.0
    assert harmonic(0.5, 0.0) == 0.0


def test_harmonic_trung_phat_cap_mot_chieu():
    """0.9/0.3 → 0.45, trong khi trung bình cộng ra 0.60."""
    assert harmonic(0.9, 0.3) == pytest.approx(0.45, abs=1e-3)
    assert harmonic(0.9, 0.3) < (0.9 + 0.3) / 2


def test_harmonic_doi_xung():
    assert harmonic(0.8, 0.4) == pytest.approx(harmonic(0.4, 0.8))


def test_chieu_on_ao_la_BAT_DOI_XUNG():
    """noise_tolerance của A đụng hành vi ồn của B thì CHỈ A bị ảnh hưởng.
    Điểm đối xứng sẽ che mất đúng cái làm cặp đó tệ."""
    quiet = P(1, noise_tolerance=1, hanh_vi=["Mình hay nấu ăn trong phòng"])
    noisy = P(2, noise_tolerance=5,
              hanh_vi=["Tối muộn mình hay còn hoạt động (xem phim, gọi điện, nói chuyện)"])
    ps = pair_score(quiet, noisy, DEFAULT)
    assert ps.breakdown["noise"] == pytest.approx(1.0)   # quiet bị ảnh hưởng tối đa
    assert pair_score(noisy, quiet, DEFAULT).breakdown["noise"] == 0.0
    assert ps.s_ab < ps.s_ba


def test_thieu_du_lieu_thi_BO_QUA_chieu_khong_coi_la_giong_nhau():
    """Cách Gower gốc xử lý missing. Gán d_k=0 sẽ thành 'giống nhau' giả và đẩy
    điểm lên cho hai hồ sơ trống rỗng."""
    full = P(1, ac_usage=2)
    noac = P(2, ac_usage=None)
    assert "ac_usage" not in pair_score(full, noac, DEFAULT).breakdown
    assert "ac_usage" in pair_score(full, P(3, ac_usage=0), DEFAULT).breakdown


def test_khong_chieu_nao_tinh_duoc_thi_diem_0_khong_phai_0_5():
    """0.0 là trung thực: ta KHÔNG có bằng chứng nào cho rằng cặp này phù hợp."""
    bare_a = Profile.from_row({"user_id": 1, "gender": "nam"})
    bare_b = Profile.from_row({"user_id": 2, "gender": "nam"})
    assert pair_score(bare_a, bare_b, DEFAULT).score == 0.0


def test_diem_giong_het_nhau_phai_cao():
    a, b = P(1), P(2)
    assert pair_score(a, b, DEFAULT).score > 0.9


def test_ly_do_va_luu_y_duoc_sinh_ra():
    a = P(1, don_vi="Trường CNTT&TT")
    b = P(2, don_vi="Trường CNTT&TT")
    ps = pair_score(a, b, DEFAULT)
    assert len(ps.reasons) == 3
    assert any("cùng" in r for r in ps.reasons)


def test_vi_pham_mem_LUON_thang_vi_tri_canh_bao():
    """Người dùng đã nói rõ họ không chấp nhận điều đó — ẩn nó đi là lừa họ."""
    victim = P(1, deal_breakers=["Ồn ào khuya"])
    noisy = P(2, hanh_vi=["Tối muộn mình hay còn hoạt động (xem phim, gọi điện, nói chuyện)"])
    ps = pair_score(victim, noisy, DEFAULT)
    assert ps.soft_flags == ["Ồn ào khuya"]
    assert "không chấp nhận" in ps.caveat


def test_cosine_khong_the_thay_the_khoang_cach_co_trong_so():
    """Chứng minh ĐỊNH LƯỢNG cho việc bác ngưỡng cosine 0.7 của SRS FR-5.2.

    Mọi chiều đều dương và thang ngắn ⇒ cosine dồn vào dải hẹp sát 1, mà cosine
    lại BỎ QUA độ lớn — đúng phần chứa thông tin 'bạn sạch 5, tôi sạch 2'.
    Đo trên 19 hồ sơ thật: cosine ≥ 0.7 cho 93% cặp đi qua.
    """
    import math
    clean, dirty = P(1, cleanliness=5), P(2, cleanliness=1)
    vec = lambda p: [p.sleep_time, p.cleanliness, p.noise_tolerance, p.budget_band]
    u, v = vec(clean), vec(dirty)
    cos = sum(x * y for x, y in zip(u, v)) / (
        math.sqrt(sum(x * x for x in u)) * math.sqrt(sum(y * y for y in v)))
    assert cos > 0.7                                       # cosine cho đi qua
    assert pair_score(clean, dirty, DEFAULT).breakdown["cleanliness"] == 1.0


def test_bo_trong_so_khac_nhau_cho_diem_khac_nhau():
    """Nếu hai bộ cho cùng kết quả thì bảng ablation không chứng minh được gì."""
    a = P(1, cleanliness=5, don_vi="X")
    b = P(2, cleanliness=2, don_vi="Y")
    assert pair_score(a, b, DEFAULT).score != pair_score(a, b, UNIFORM).score


def test_sensitivity_sinh_du_bien_the():
    v = sensitivity(DEFAULT, 0.2)
    assert len(v) == 2 * len(DEFAULT)
    names = {n for n, _ in v}
    assert "cleanliness_up" in names and "cleanliness_down" in names


# ────────────────────────────────── stable ─────────────────────────────────

def test_vi_du_kinh_dien_n4_khong_co_ghep_on_dinh():
    """Stable Roommates (non-bipartite) CÓ THỂ vô nghiệm — khác Stable Marriage
    (Gale-Shapley) luôn có nghiệm. Đây là ví dụ kinh điển."""
    prefs = {1: [2, 3, 4], 2: [3, 1, 4], 3: [1, 2, 4], 4: [1, 2, 3]}
    assert irving(prefs) is None


def test_irving_tim_duoc_ghep_on_dinh_khi_ton_tai():
    prefs = {1: [2, 3, 4], 2: [1, 3, 4], 3: [4, 1, 2], 4: [3, 1, 2]}
    m = irving(prefs)
    assert m is not None
    assert blocking_pairs(m, prefs) == []
    assert all(m[m[x]] == x for x in m)        # phải đối xứng


def test_blocking_pairs_phat_hien_cap_cung_thich_nhau_hon():
    prefs = {1: [2, 3], 2: [1, 3], 3: [1, 2]}
    bad = {1: 3, 3: 1}                          # 2 lẻ ra, mà 1 và 2 thích nhau nhất
    assert (1, 2) in blocking_pairs(bad, prefs)


def test_stable_roommates_tren_pool_thuc():
    pool = [P(i, cleanliness=(i % 5) + 1, sleep_time=i % 3, budget_band=1) for i in range(1, 7)]
    res = stable_roommates(pool, DEFAULT)
    assert all(res.matching[res.matching[x]] == x for x in res.matching)
    # stable=True thì BẮT BUỘC 0 blocking pair — không được báo ổn định hờ
    assert res.stable == (len(res.blocking_pairs) == 0)


# ──────────────────────────────── API (DB thật) ────────────────────────────

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


def test_api_thieu_auth_tra_403_khong_phai_401():
    """HTTPBearer trả 403 khi thiếu header — khác 401 khi token sai."""
    assert client.get("/matching/deck").status_code == 403
    assert client.get("/matching/profile").status_code == 403


def test_api_profile_upsert_va_tra_preview():
    u = _user()
    r = client.get("/matching/profile", headers=u["h"])
    assert r.status_code == 200
    d = r.json()
    assert d["in_pool"] is True
    assert d["profile"]["src"] == "app"
    # client KHÔNG được tự nhận mình là hồ sơ mô phỏng
    assert d["profile"]["is_simulated"] is False
    assert len(d["options"]["hanh_vi"]) == len(HANH_VI)


def test_api_profile_chan_gia_tri_hanh_vi_la():
    """Thà 422 ở biên còn hơn mất lớp an toàn trong im lặng."""
    u = _user()
    r = client.post("/matching/profile", json={"hanh_vi": ["không-có-trong-form"]}, headers=u["h"])
    assert r.status_code == 422


def test_api_profile_khong_the_tu_nhan_la_simulated():
    u = _user()
    client.post("/matching/profile", json={"is_simulated": True, "src": "form"}, headers=u["h"])
    d = client.get("/matching/profile", headers=u["h"]).json()["profile"]
    assert d["is_simulated"] is False and d["src"] == "app"


def test_api_deck_tra_200_khi_chua_co_ho_so():
    """200 + reason, KHÔNG 404 — nếu không FE hiện màn hình lỗi cho người mới."""
    email = f"mt_{uuid4().hex[:8]}@example.com"
    r = client.post("/auth/register", json={"email": email, "password": "testpass123"})
    h = {"Authorization": f"Bearer {r.json()['access_token']}"}
    d = client.get("/matching/deck", headers=h)
    assert d.status_code == 200
    assert d.json()["items"] == [] and d.json()["reason"] == "no_profile"


def test_api_deck_xep_hang_va_ghi_telemetry_phia_SERVER():
    a = _user(gender="nam", don_vi="Trường CNTT&TT")
    _user(gender="nam", don_vi="Trường CNTT&TT")
    d = client.get("/matching/deck?limit=5", headers=a["h"]).json()
    assert d["deck_mode"] == "ranked" and d["weights_ver"] == "survey"
    assert d["items"], d
    first = d["items"][0]
    assert first["position"] == 0
    assert 0.0 <= first["score"] <= 1.0
    assert isinstance(first["reasons"], list)
    assert first["profile"] is not None
    # T1 ẩn danh: KHÔNG lộ email/SĐT/MSSV trên thẻ
    assert "email" not in first["profile"] and "phone" not in first["profile"]


def test_api_deck_mode_random_an_moi_tin_hieu_thuat_toan():
    """Deck xếp theo điểm thì thẻ đầu được like nhiều hơn VÌ NÓ Ở ĐẦU ⇒ mô hình
    học chính thiên lệch vị trí đó. Buổi thử nghiệm phải ẩn %/lý do."""
    a = _user(gender="nu")
    _user(gender="nu")
    d = client.get("/matching/deck?limit=5&mode=random", headers=a["h"]).json()
    assert d["deck_mode"] == "random"
    for it in d["items"]:
        assert it["score"] is None
        assert it["reasons"] == [] and it["caveat"] is None and it["soft_flags"] == []


def test_api_swipe_CHAN_ghep_khac_gioi():
    """Lỗi blocker đã sửa: bản trước chỉ kiểm 'user tồn tại' ⇒ bất kỳ client đã
    đăng nhập nào cũng ghép được khác giới bằng cách POST thẳng target_id, phá
    cam kết 'chỉ ghép cùng giới' đã hứa trong form khảo sát."""
    nam, nu = _user(gender="nam"), _user(gender="nu")
    r = client.post("/matching/swipe", json={"target_id": nu["id"], "decision": "like"},
                    headers=nam["h"])
    assert r.status_code == 409
    assert "cùng giới" in r.json()["detail"]


def test_api_swipe_doi_hoi_ho_so():
    email = f"mt_{uuid4().hex[:8]}@example.com"
    rr = client.post("/auth/register", json={"email": email, "password": "testpass123"})
    h = {"Authorization": f"Bearer {rr.json()['access_token']}"}
    other = _user()
    r = client.post("/matching/swipe", json={"target_id": other["id"], "decision": "like"}, headers=h)
    assert r.status_code == 409 and "hồ sơ" in r.json()["detail"]


def test_api_swipe_user_khong_ton_tai_404_khac_voi_thieu_ho_so_409():
    u = _user()
    r = client.post("/matching/swipe", json={"target_id": 99_999_999, "decision": "like"},
                    headers=u["h"])
    assert r.status_code == 404


def test_api_swipe_chan_deal_breaker_CUNG():
    victim = _user(gender="nam", deal_breakers=["Hút thuốc trong phòng"])
    smoker = _user(gender="nam", smoke=True, smoke_in_room=True)
    r = client.post("/matching/swipe", json={"target_id": smoker["id"], "decision": "like"},
                    headers=victim["h"])
    assert r.status_code == 409


def test_api_swipe_khong_nhan_telemetry_tu_FE():
    """deck_position/deck_mode do FE gửi bị BỎ QUA — chính dữ liệu dùng để chứng
    minh đã khử thiên lệch vị trí, để client tự khai là mất giá trị bằng chứng."""
    a, b = _user(gender="nam"), _user(gender="nam")
    r = client.post(
        "/matching/swipe",
        json={"target_id": b["id"], "decision": "pass", "deck_position": 99, "deck_mode": "random"},
        headers=a["h"],
    )
    assert r.status_code == 200
    from sqlalchemy import text as _t

    from app.main import engine
    with engine.connect() as conn:
        row = conn.execute(
            _t("SELECT deck_position, deck_mode FROM swipes WHERE user_id=:u AND target_id=:t"),
            {"u": a["id"], "t": b["id"]},
        ).mappings().one()
    assert row["deck_position"] != 99          # không lấy số của FE


def test_api_deck_ghi_telemetry_that_khi_swipe_tu_deck():
    a = _user(gender="nu", don_vi="Trường Kinh tế")
    _user(gender="nu", don_vi="Trường Kinh tế")
    d = client.get("/matching/deck?limit=1", headers=a["h"]).json()
    assert d["items"]
    target = d["items"][0]["user_id"]
    assert client.post("/matching/swipe", json={"target_id": target, "decision": "pass"},
                       headers=a["h"]).status_code == 200
    from sqlalchemy import text as _t

    from app.main import engine
    with engine.connect() as conn:
        row = conn.execute(
            _t("SELECT deck_position, deck_mode, score_at_swipe, features FROM swipes "
               "WHERE user_id=:u AND target_id=:t"),
            {"u": a["id"], "t": target},
        ).mappings().one()
    assert row["deck_position"] == 0
    assert row["deck_mode"] == "ranked"
    assert row["score_at_swipe"] is not None
    assert row["features"] is not None          # BẮT BUỘC để huấn luyện lại


def test_api_swipe_2_chieu_tao_match_va_hoi_thoai():
    a, b = _user(gender="nam"), _user(gender="nam")
    assert client.post("/matching/swipe", json={"target_id": b["id"], "decision": "like"},
                       headers=a["h"]).json()["matched"] is False
    res = client.post("/matching/swipe", json={"target_id": a["id"], "decision": "like"},
                      headers=b["h"]).json()
    assert res["matched"] is True and res["conversation_id"]
    # idempotent: gọi lại trả ĐÚNG hội thoại đó
    again = client.post("/matching/swipe", json={"target_id": a["id"], "decision": "like"},
                        headers=b["h"]).json()
    assert again["conversation_id"] == res["conversation_id"]


def test_api_nguoi_da_match_khong_con_trong_deck():
    a, b = _user(gender="nu"), _user(gender="nu")
    client.post("/matching/swipe", json={"target_id": b["id"], "decision": "like"}, headers=a["h"])
    client.post("/matching/swipe", json={"target_id": a["id"], "decision": "like"}, headers=b["h"])
    d = client.get("/matching/deck?limit=30", headers=a["h"]).json()
    assert b["id"] not in [i["user_id"] for i in d["items"]]


def test_api_likes_va_passed():
    a, b = _user(gender="nam"), _user(gender="nam")
    client.post("/matching/swipe", json={"target_id": b["id"], "decision": "like"}, headers=a["h"])
    # /matching/likes trả người đã thích MÌNH ⇒ trong hộp thư của b phải là a
    assert a["id"] in [i["user_id"] for i in client.get("/matching/likes", headers=b["h"]).json()["items"]]

    c = _user(gender="nam")
    client.post("/matching/swipe", json={"target_id": c["id"], "decision": "pass"}, headers=a["h"])
    assert c["id"] in [i["user_id"] for i in client.get("/matching/passed", headers=a["h"]).json()["items"]]


def test_api_pass_loai_khoi_deck_nhung_KHONG_vinh_vien():
    """Ở pool nhỏ, xoá vĩnh viễn là đốt pool ⇒ pass chỉ hạ ưu tiên 7 ngày."""
    a, b = _user(gender="nu"), _user(gender="nu")
    client.post("/matching/swipe", json={"target_id": b["id"], "decision": "pass"}, headers=a["h"])
    d = client.get("/matching/deck?limit=30", headers=a["h"]).json()
    assert b["id"] not in [i["user_id"] for i in d["items"]]
    # vẫn truy lại được qua /matching/passed (nút "Xem lại thẻ đã bỏ qua")
    assert b["id"] in [i["user_id"] for i in client.get("/matching/passed", headers=a["h"]).json()["items"]]
