"""Hồ sơ mô phỏng: bất biến nhãn, tính tất định, và ràng buộc của phép nhiễu.

Donor dựng NỘI TUYẾN (không đọc eval/data/survey_v2.csv, không cần Postgres):
container test chỉ có /app/app và /app/tests, còn CSV chứa PII thật nên không
đưa vào image. Các test đọc CSV sẽ tự skip nếu không thấy file.
"""
from pathlib import Path

import pytest

from app.matching import simulate as S
from app.matching.filters import HARD_DEAL_BREAKERS, passes_hard_filters
from app.matching.profile import DEAL_BREAKER_NONE, DIRTY_MAX, HANH_VI_NONE, Profile

CSV = Path("/tmp/survey.csv")   # chỉ có khi đã docker cp; test dùng nó đều skip được


def donor(**kw) -> dict:
    base = dict(
        row_no="9", gender="nu", budget_band=1, scenario=2, sleep_time=1,
        cleanliness=4, noise_tolerance=3, ac_usage=1, money_style=1, persona="A",
        smoke=False, smoke_in_room=False,
        hanh_vi=["Mình hay nấu ăn trong phòng"],
        deal_breakers=["Ồn ào khuya"],
        need_from=None, roommate_status=None,
    )
    base.update(kw)
    return base


DON_VI = ["Trường Bách khoa", "Trường Kinh tế"]


def gen(donors=None, *, gender="nu", count=8, seed=2026):
    return S.generate(donors or [donor()], DON_VI, gender=gender, count=count, seed=seed)


# ───────────────────────────── Bất biến về NHÃN ──────────────────────────────

def test_nhan_khong_the_bi_tham_so_dieu_khien():
    """is_simulated/src là LITERAL trong câu SQL, không phải tham số.

    Nếu chúng lọt vào PROFILE_KEYS thì có đường ghi hàng mô phỏng THIẾU nhãn —
    và hàng thiếu nhãn sẽ lọt vào số liệu eval (WHERE NOT is_simulated) lẫn mất
    badge trên UI, âm thầm.
    """
    assert "is_simulated" not in S.PROFILE_KEYS
    assert "src" not in S.PROFILE_KEYS
    assert S.SIM_SRC == "sim"


def test_moi_ho_so_sinh_ra_deu_duoc_danh_dau():
    for r in gen(count=12):
        assert r.as_profile(-1).is_simulated is True


def test_bio_mang_nhan_bang_chu():
    """Cột text đi xa hơn cái cờ (log, ảnh chụp màn hình, export CSV) nên nhãn
    phải có mặt ở cả hai chỗ."""
    for r in gen(count=6):
        assert S.BIO_TAIL in r.profile["bio"]


def test_email_khong_the_la_dia_chi_that():
    # .invalid do RFC 2606 giữ lại — không bao giờ phân giải được
    for r in gen(count=6):
        assert r.email.endswith("@simulated.invalid")
        assert r.email.startswith("sim+")


# ──────────────────────────── Tính TẤT ĐỊNH ──────────────────────────────────

def test_cung_seed_cho_ket_qua_y_het():
    """Pool trong báo cáo phải tái lập được mà không cần lưu lại dữ liệu."""
    a = [(r.email, r.name, r.profile) for r in gen(count=10, seed=7)]
    b = [(r.email, r.name, r.profile) for r in gen(count=10, seed=7)]
    assert a == b


def test_doi_seed_thi_doi_ket_qua():
    a = [r.profile for r in gen(count=10, seed=7)]
    b = [r.profile for r in gen(count=10, seed=8)]
    assert a != b


def test_count_lon_chua_dung_tien_to_cua_count_nho():
    """Mỗi hàng có rng riêng gieo bằng f"{seed}:{gender}:{i}" ⇒ tăng pool không
    phải sinh lại từ đầu, và số liệu đã báo cáo ở N nhỏ vẫn đúng."""
    nho = [(r.email, r.profile) for r in gen(count=5)]
    lon = [(r.email, r.profile) for r in gen(count=20)]
    assert lon[:5] == nho


def test_khong_dung_trang_thai_random_toan_cuc():
    import random
    random.seed(1)
    a = [r.profile for r in gen(count=6)]
    random.seed(999)
    b = [r.profile for r in gen(count=6)]
    assert a == b


# ─────────────────── Ba ràng buộc của phép NHIỄU (docstring) ─────────────────

def test_chi_sinh_gia_tri_CO_TRONG_form():
    """Thang cleanliness thiếu mức 3 và noise_tolerance thiếu mức 4: nhiễu ±1
    trên thang số sẽ sinh giá trị không ứng với lựa chọn nào của form, rồi
    survey_map không map ngược được và nhãn UI hiện '—'."""
    for r in gen(donors=[donor(), donor(cleanliness=5, noise_tolerance=5)], count=30):
        for key, levels in S.LEVELS.items():
            v = r.profile.get(key)
            assert v is None or v in levels, f"{key}={v} không có trong {levels}"


def test_donor_sach_thi_khong_bao_gio_sinh_ra_ho_so_o_ban():
    """'Ở bẩn' là veto CỨNG của 15/19 người thật — sinh ra là sinh rác không ghép
    được với ai."""
    for r in gen(donors=[donor(cleanliness=4), donor(cleanliness=5)], count=40):
        assert r.profile["cleanliness"] > DIRTY_MAX


def test_donor_o_ban_thi_GIU_NGUYEN_khong_bop_meo_marginal():
    for r in gen(donors=[donor(cleanliness=1)], count=20):
        assert r.profile["cleanliness"] <= DIRTY_MAX


def test_khong_bao_gio_bat_smoke_in_room():
    """Veto cứng của 18/19 người thật."""
    for r in gen(donors=[donor(smoke=False, smoke_in_room=False)], count=40):
        assert r.profile["smoke_in_room"] is False
        assert r.profile["smoke"] is False


def test_khong_bao_gio_them_deal_breaker_CUNG():
    """Nhiễu chỉ bật/tắt trong tầng MỀM: thêm một deal-breaker cứng là tự cho hồ
    sơ mô phỏng quyền veto mà người gốc không khai."""
    d = donor(deal_breakers=["Ồn ào khuya"])
    for r in gen(donors=[d], count=40):
        them = set(r.profile["deal_breakers"]) - set(d["deal_breakers"])
        assert not (them & HARD_DEAL_BREAKERS), f"nhiễu thêm deal-breaker cứng: {them}"


def test_khong_sinh_sentinel_lan_voi_gia_tri_that():
    """Sentinel chỉ được dùng khi danh sách RỖNG, không lẫn cùng lựa chọn thật —
    lẫn vào thì Profile.from_row lọc mất và số liệu đếm bị sai."""
    for r in gen(donors=[donor(), donor(hanh_vi=[], deal_breakers=[])], count=30):
        hv, db = r.profile["hanh_vi"], r.profile["deal_breakers"]
        assert HANH_VI_NONE not in hv or hv == [HANH_VI_NONE]
        assert DEAL_BREAKER_NONE not in db or db == [DEAL_BREAKER_NONE]


# ───────────────────────── Chống nhận dạng lại ───────────────────────────────

def test_khong_la_ban_sao_khit_cua_donor_nao():
    donors = [donor(), donor(sleep_time=2, cleanliness=5, noise_tolerance=5)]
    sigs = {S._signature(d) for d in donors}
    for r in gen(donors=donors, count=30):
        assert S._signature(r.profile) not in sigs


def test_don_vi_chi_lay_tu_pool_da_loc():
    """don_vi lấy mẫu ĐỘC LẬP và chỉ từ Trường/Khoa có >= 2 người: đơn vị n=1
    cộng giới tính cộng lối sống là đủ để nhận ra một người cụ thể."""
    for r in gen(count=20):
        assert r.profile["don_vi"] in DON_VI


def test_ten_khong_lay_tu_mau_khao_sat():
    """CSV có full_name thật — tên mô phỏng phải ghép từ bộ hằng số trong file."""
    ho = set(S._HO)
    for r in gen(count=12):
        assert r.name.split()[0] in ho


# ───────────────────────── Dùng được cho thuật toán ──────────────────────────

def test_profile_from_row_tuong_thich_va_vao_duoc_pool():
    for i, r in enumerate(gen(count=12)):
        p = r.as_profile(-(i + 1))
        assert isinstance(p, Profile)
        assert p.in_pool is True


def test_ho_so_mo_phong_ghep_duoc_voi_nhau():
    """Sinh ra một pool mà không ai ghép được với ai thì vô dụng."""
    rows = gen(count=12)
    ps = [r.as_profile(-(i + 1)) for i, r in enumerate(rows)]
    qua = sum(1 for a in ps for b in ps if a.user_id != b.user_id and passes_hard_filters(a, b))
    tong = len(ps) * (len(ps) - 1)
    assert qua / tong > 0.5, f"chỉ {qua}/{tong} cặp qua lọc cứng"


def test_split_count_uu_tien_nu():
    """Nữ mới là phía thiếu hồ sơ (3 thật so với 6 nam) — lý do tồn tại của file."""
    assert S.split_count(25, "both") == {"nu": 13, "nam": 12}
    assert S.split_count(10, "nu") == {"nu": 10}


# ─────────────────────── An toàn của --reset (quan trọng) ────────────────────

def test_reset_pattern_khong_the_khop_email_that():
    """Pattern sai mà xoá im lặng là mất tài khoản SV thật.

    LIKE: '%' là wildcard, '_' khớp 1 ký tự bất kỳ, '+' và '@' là ký tự thường.
    """
    import re
    pat = S.SIM_EMAIL_LIKE
    assert "_" not in pat, "'_' trong LIKE là wildcard 1 ký tự — nới pattern ngoài ý muốn"
    rx = re.compile("^" + re.escape(pat).replace("%", ".*") + "$")

    for that in (
        "phub2303891@student.ctu.edu.vn", "trahoph0404k5@gmail.com",
        "linh.demo@example.com", "sim@simulated.invalid.ctu.edu.vn",
        "x+sim+1@simulated.invalid.vn",
    ):
        assert not rx.match(that), f"pattern khớp email thật: {that}"
    assert rx.match("sim+nu1@simulated.invalid")
    assert rx.match("sim+nam12@simulated.invalid")


# ───────────────── Donor thật (skip khi không có CSV trong container) ────────

@pytest.mark.skipif(not CSV.is_file(), reason="chưa docker cp survey_v2.csv vào /tmp")
def test_donor_that_loai_dung_nguoi_o_mot_minh():
    donors, don_vi_pool, skipped = S.load_donors(CSV)
    assert donors, "không đọc được donor nào"
    # khai "ở một mình" ⇒ lọc cứng loại với mọi người ⇒ hồ sơ mô phỏng vô dụng
    assert all(d["scenario"] != S.SCENARIO_ALONE for d in donors)
    assert skipped["o_mot_minh"] >= 0
    assert don_vi_pool


@pytest.mark.skipif(not CSV.is_file(), reason="chưa docker cp survey_v2.csv vào /tmp")
def test_ho_so_mo_phong_ghep_duoc_voi_nguoi_THAT():
    donors, don_vi_pool, _ = S.load_donors(CSV)
    reals = S.real_profiles(donors, CSV)
    rows = S.generate(donors, don_vi_pool, gender="nu", count=12, seed=2026)
    sims = [r.as_profile(-(i + 1)) for i, r in enumerate(rows)]
    co_lap = [s.user_id for s in sims
              if not any(passes_hard_filters(s, rp) for rp in reals if rp.gender == s.gender)]
    assert not co_lap, f"hồ sơ mô phỏng không ghép được với ai thật: {co_lap}"
