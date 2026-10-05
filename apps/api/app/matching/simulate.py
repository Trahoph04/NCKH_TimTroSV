"""Sinh hồ sơ ở ghép MÔ PHỎNG CÓ NHÃN bằng bootstrap từ phân bố thật.

    docker cp eval/data/survey_v2.csv "$(docker compose ps -q api)":/tmp/survey.csv
    docker compose exec -T api python -m app.matching.simulate --count 24 --dry-run
    docker compose exec -T api python -m app.matching.simulate --count 24
    docker compose exec -T api python -m app.matching.simulate --reset --count 0

VÌ SAO CẦN (đo 2026-10-04): pool thật chỉ có 3 hồ sơ nữ ⇒ mỗi SV nữ thấy pool 2
người TRƯỚC lọc cứng, buổi thử nghiệm sẽ ra 0 match ở phía nữ và không đo được
gì. Matching_Messaging_Design.md mục 2.8 ý 3 cho phép đúng việc này: "sinh 30-40
hồ sơ mô phỏng bằng bootstrap từ phân bố hồ sơ thật (GIỮ TƯƠNG QUAN giữa các
câu), hiển thị nhãn trên UI, loại khỏi mọi số liệu eval".

═══ BOOTSTRAP THEO PHÂN BỐ ĐỒNG THỜI, KHÔNG PHẢI TỪNG CỘT ═══
Lấy mẫu độc lập từng cột là sai về bản chất, không chỉ "kém đẹp": nó phá tương
quan giữa các câu (người ngủ muộn cũng hay là người còn hoạt động khuya; người
rửa chén ngay cũng hay khai 'ở bẩn' là deal-breaker). Pool sinh ra sẽ có đúng
marginal nhưng SAI cấu trúc — tức không giống mẫu thật ở đúng cái ta cần nó
giống, và hội đồng chỉ cần bảng chéo 2 cột là thấy.

Cách làm ở đây: **resample NGUYÊN người** (bootstrap có hoàn lại) rồi **nhiễu
nhẹ** vài trường. Tương quan được giữ theo cấu trúc (mỗi hồ sơ gốc là một vector
quan sát thật), nhiễu chỉ làm hồ sơ không trùng khít người thật.

═══ BA RÀNG BUỘC CỦA PHÉP NHIỄU (không phải tinh chỉnh cho đẹp) ═══
1. Nhiễu nhảy MỘT BẬC trong danh sách mức của form, KHÔNG ±1 trên thang số.
   Thang cleanliness thiếu mức 3 và noise_tolerance thiếu mức 4 (xem survey_map
   _DISHES/_NOISE) ⇒ ±1 sẽ sinh giá trị không ứng với lựa chọn nào của form.
2. Nhiễu KHÔNG BAO GIỜ tạo ra tác nhân lọc CỨNG mà hồ sơ gốc không có: không đẩy
   cleanliness xuống vùng "ở bẩn" (<= DIRTY_MAX) và không bật smoke_in_room.
   Hai thứ đó là veto tuyệt đối của 15/19 và 18/19 người thật ⇒ sinh ra là sinh
   rác không ghép được với ai. Hồ sơ gốc VỐN ở bẩn thì giữ nguyên (2/19) để
   marginal không bị bóp méo thêm.
3. Deal-breaker chỉ bật/tắt trong tầng MỀM. Bật thêm một deal-breaker CỨNG là tự
   cho hồ sơ mô phỏng quyền veto mà người gốc không khai.

═══ ĐẠO ĐỨC / AN TOÀN (đọc cùng ghi chú đạo đức ở import_survey.py) ═══
· `is_simulated = TRUE` + `src = 'sim'` được viết THẲNG TRONG CÂU SQL (không qua
  tham số) ⇒ không có đường nào sinh ra hàng thiếu nhãn. Eval lọc bằng
  `WHERE NOT is_simulated`, UI gắn badge từ cùng cột đó.
· Email `sim+<giới><n>@simulated.invalid` — `.invalid` do RFC 2606 giữ lại, không
  bao giờ là địa chỉ thật. `password_hash = NULL` và KHÔNG tạo `user_identities`
  ⇒ không có đường đăng nhập vào người mô phỏng.
· Donor là cả 19 hồ sơ có phần D (kể cả người trả lời "không muốn dùng thử") —
  đó là phân bố mà mục 2.8 nói tới. Bù lại: (a) hồ sơ sinh ra bắt buộc KHÔNG
  trùng khít bất kỳ donor nào (`_signature`), (b) `don_vi` lấy mẫu ĐỘC LẬP và chỉ
  từ các Trường/Khoa xuất hiện >= 2 lần — đơn vị n=1 cộng giới tính cộng lối sống
  là đủ để nhận ra một người cụ thể, mà `don_vi` chỉ là chiều nhị phân w=0,15
  nên phá tương quan của nó không đổi thứ hạng.
"""
from __future__ import annotations

import argparse
import csv
import random
import sys
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy import create_engine, text

from ..config import settings
from . import survey_map as sm
from .filters import SOFT_DEAL_BREAKERS, hard_filter_reason
from .profile import (
    DEAL_BREAKER,
    DEAL_BREAKER_NONE,
    DIRTY_MAX,
    GENDERS,
    HANH_VI,
    HANH_VI_NONE,
    Profile,
)

# Nhãn — hằng số, mọi chỗ phải dùng chung (test khẳng định lại bộ này).
SIM_SRC = "sim"
SIM_EMAIL_DOMAIN = "simulated.invalid"          # RFC 2606: không bao giờ phân giải được
SIM_EMAIL_LIKE = f"sim+%@{SIM_EMAIL_DOMAIN}"    # dùng cho --reset, LIKE coi '+'/'@' là ký tự thường

DEFAULT_SEED = 2026         # để pool trong báo cáo tái lập được mà không cần truyền --seed
DEFAULT_CSV = Path("/tmp/survey.csv")

# Mức THẬT của từng cột thứ bậc (đúng tập giá trị survey_map sinh ra). Nhiễu nhảy
# một bậc TRONG danh sách này — xem ràng buộc 1 ở docstring.
LEVELS: dict[str, tuple[int, ...]] = {
    "sleep_time": (0, 1, 2),
    "cleanliness": (1, 2, 4, 5),
    "noise_tolerance": (1, 2, 3, 5),
    "ac_usage": (0, 1, 2),
    "budget_band": (0, 1, 2, 3, 4),
}

# Xác suất nhiễu mỗi trường. Đặt thấp có chủ đích: nhiễu mạnh thì hồ sơ sinh ra
# tiến về phân bố ĐỘC LẬP từng cột — đúng cái docstring nói phải tránh.
P_STEP = 0.35           # mỗi cột thứ bậc
P_HANH_VI = 0.45        # bật/tắt 1 hành vi
P_SOFT_DB = 0.30        # bật/tắt 1 deal-breaker MỀM

SCENARIO_ALONE = 1      # khai "ở một mình" ⇒ lọc cứng loại với mọi người

# Sentinel KHÔNG được coi là deal-breaker để bật/tắt: SOFT_DEAL_BREAKERS vẫn chứa
# 'Mình dễ tính, không có điều nào' (nó nằm trong DEAL_BREAKER và không thuộc tầng
# cứng). Bật nó như một deal-breaker thật là ghi vào DB một hàng vô nghĩa.
_SOFT_TOGGLE: tuple[str, ...] = tuple(sorted(SOFT_DEAL_BREAKERS - {DEAL_BREAKER_NONE}))
_HANH_VI_TOGGLE: tuple[str, ...] = tuple(h for h in HANH_VI if h != HANH_VI_NONE)

DON_VI_MIN_COUNT = 2    # xem ghi chú đạo đức: đơn vị n=1 là tay cầm để nhận dạng

# Tên tiếng Việt cho hồ sơ mô phỏng. Họ ghép với tên theo rng ⇒ không phải tên
# của ai trong mẫu khảo sát (CSV có full_name thật, KHÔNG được lấy ra dùng).
_HO = ("Nguyễn", "Trần", "Lê", "Phạm", "Huỳnh", "Võ", "Đặng", "Bùi", "Đỗ", "Hồ", "Ngô", "Dương")
_TEN = {
    "nam": ("Gia Huy", "Đức Anh", "Minh Quân", "Hoàng Long", "Thành Đạt", "Quốc Bảo",
            "Tấn Phát", "Nhật Nam", "Hữu Tài", "Trọng Nghĩa", "Khánh Duy", "Văn Hậu"),
    "nu": ("Minh Thư", "Ngọc Hân", "Bảo Trân", "Khánh Linh", "Thanh Ngân", "Thuý Vy",
           "Kim Ngân", "Nhã Phương", "Tuyết Nhi", "Mỹ Duyên", "Hồng Nhung", "Phương Thảo"),
}

# bio dựng từ chính trait đã sinh — không bịa chuyện cá nhân. Câu đuôi nói rõ đây
# là hồ sơ mô phỏng: cột text đi xa hơn cái cờ (log, ảnh chụp màn hình, export),
# nên nhãn phải có mặt ở cả hai chỗ chứ không chỉ ở `is_simulated`.
_BIO_SLEEP = {0: "Ngủ sớm trước 22h", 1: "Ngủ tầm 22-24h", 2: "Thường thức sau 0h"}
_BIO_CLEAN = {1: "ít dọn dẹp", 2: "hay để 1-2 ngày mới rửa chén",
              4: "dọn trong ngày", 5: "rửa chén ngay sau khi ăn"}
_BIO_NOISE = {1: "cần yên tĩnh để học", 2: "hơi khó chịu khi ồn",
              3: "ồn thì nhắc nhẹ một câu", 5: "không ngại ồn"}
BIO_TAIL = "(Hồ sơ mô phỏng, phục vụ thử nghiệm.)"

# Cột ghi vào roommate_profiles. is_simulated/src KHÔNG có ở đây — chúng là literal
# trong câu SQL, xem _write_profile.
PROFILE_KEYS = (
    "gender", "don_vi", "budget_band", "scenario", "sleep_time", "cleanliness",
    "noise_tolerance", "ac_usage", "money_style", "smoke", "smoke_in_room",
    "hanh_vi", "deal_breakers", "persona", "bio", "need_from", "roommate_status",
)


@dataclass(slots=True)
class SimRow:
    """Một hồ sơ mô phỏng sẵn sàng ghi DB. `profile` chỉ chứa PROFILE_KEYS."""

    email: str
    name: str
    donor_row: str | None           # row_no của donor — vết audit, KHÔNG ghi vào DB
    profile: dict = field(default_factory=dict)

    def as_profile(self, user_id: int) -> Profile:
        """Đổi sang Profile để chạy thử lọc cứng/tính điểm trước khi ghi DB.

        `user_id` âm khi chưa ghi DB (dry-run) để chắc chắn không trùng id thật.
        """
        return Profile.from_row({"user_id": user_id, "is_simulated": True, **self.profile})


# ───────────────────────────── Donor (phân bố thật) ──────────────────────────

def load_donors(csv_path: Path) -> tuple[list[dict], list[str], dict[str, int]]:
    """CSV khảo sát → (donors, don_vi_pool, thống kê bỏ qua).

    Donor = hồ sơ CÓ phần D và CÓ khai giới tính (đúng điều kiện `Profile.in_pool`).
    Người trả lời "không muốn dùng thử" vẫn là donor — ta dùng PHÂN BỐ của họ, không
    tạo tài khoản cho họ (xem ghi chú đạo đức ở đầu file và ở import_survey.py).
    """
    rows = list(csv.DictReader(csv_path.open(encoding="utf-8")))
    donors: list[dict] = []
    skipped = {"khong_co_phan_D": 0, "khong_khai_gioi": 0, "o_mot_minh": 0}
    unknown: list[tuple[str, list[str]]] = []
    don_vi_count: dict[str, int] = {}

    for r in rows:
        sleep = sm.sleep_time(r.get("sleep_time"))
        clean = sm.cleanliness(r.get("dishes"))
        if sleep is None and clean is None:
            skipped["khong_co_phan_D"] += 1
            continue
        gender = sm.gender(r.get("gender"))
        if gender not in GENDERS:
            skipped["khong_khai_gioi"] += 1
            continue

        hanh_vi, extra_hv = sm.split_multi(r.get("behaviors"), HANH_VI)
        dbs, extra_db = sm.split_multi(r.get("deal_breakers"), DEAL_BREAKER)
        if extra_hv or extra_db:
            unknown.append((r.get("row_no") or "?", extra_hv + extra_db))
            continue
        smoke, smoke_in_room, infer_db = sm.smoking(r.get("smoking"))
        dbs = sm.deal_breakers_with_smoking(dbs, infer_db)

        scenario = sm.scenario(r.get("plan"))
        if scenario == SCENARIO_ALONE:
            # Donor khai "ở một mình" sinh ra hồ sơ bị lọc cứng loại với TẤT CẢ
            # (filters.py mục 4) ⇒ hồ sơ mô phỏng vô dụng. Loại khỏi donor pool và
            # báo số: việc này LÀM LỆCH marginal cột scenario, phải nói ra.
            skipped["o_mot_minh"] += 1
            continue

        don_vi = (r.get("don_vi") or "").strip() or None
        if don_vi:
            don_vi_count[don_vi] = don_vi_count.get(don_vi, 0) + 1

        donors.append({
            "row_no": r.get("row_no"),
            "gender": gender,
            "budget_band": sm.budget_band(r.get("budget")),
            "scenario": scenario,
            "sleep_time": sleep,
            "cleanliness": clean,
            "noise_tolerance": sm.noise_tolerance(r.get("noise_reaction")),
            "ac_usage": sm.ac_usage(r.get("ac_usage")),
            "money_style": sm.money_style(r.get("money_style")),
            "persona": sm.persona(r.get("persona")),
            "smoke": smoke,
            "smoke_in_room": smoke_in_room,
            "hanh_vi": [h for h in hanh_vi if h != HANH_VI_NONE],
            "deal_breakers": [d for d in dbs if d != DEAL_BREAKER_NONE],
            "need_from": (r.get("need_from") or "").strip()[:40] or None,
            "roommate_status": (r.get("roommate_status") or "").strip()[:60] or None,
        })

    if unknown:
        # Giống import_survey: token lạ = form đã đổi lựa chọn ⇒ deal-breaker
        # không đối chiếu được nữa và lọc cứng mất hiệu lực TRONG IM LẶNG.
        raise ValueError(
            "lựa chọn không khớp option form v2: "
            + "; ".join(f"dòng {rn}: {toks}" for rn, toks in unknown)
        )

    # Chỉ các Trường/Khoa xuất hiện >= DON_VI_MIN_COUNT (chống nhận dạng lại).
    # Mẫu quá nhỏ để có đơn vị nào đạt ngưỡng thì mới lùi về dùng tất cả.
    pool = sorted(k for k, c in don_vi_count.items() if c >= DON_VI_MIN_COUNT)
    return donors, (pool or sorted(don_vi_count)), skipped


# ──────────────────────────────── Phép nhiễu ─────────────────────────────────

def _step(rng: random.Random, key: str, value: int | None, *, floor: int | None = None) -> int | None:
    """Nhảy một bậc trong LEVELS[key]. `floor` = chặn dưới (dùng cho cleanliness)."""
    if value is None:
        return None
    levels = LEVELS[key]
    if value not in levels:
        return value        # giá trị ngoài bộ mức của form: không đoán, giữ nguyên
    i = levels.index(value)
    cand = [levels[j] for j in (i - 1, i + 1) if 0 <= j < len(levels)]
    if floor is not None:
        cand = [v for v in cand if v >= floor]
    return rng.choice(cand) if cand else value


def _signature(p: dict) -> tuple:
    """Vân tay lối sống — dùng để bảo đảm hồ sơ sinh ra KHÔNG trùng khít donor nào.

    Không gồm `don_vi` (lấy mẫu độc lập) và `bio`/tên (sinh ra sau).
    """
    return (
        p.get("gender"), p.get("budget_band"), p.get("scenario"), p.get("sleep_time"),
        p.get("cleanliness"), p.get("noise_tolerance"), p.get("ac_usage"),
        p.get("money_style"), p.get("persona"), p.get("smoke"), p.get("smoke_in_room"),
        tuple(sorted(p.get("hanh_vi") or ())), tuple(sorted(p.get("deal_breakers") or ())),
    )


def _perturb(rng: random.Random, donor: dict) -> dict:
    """Một lần nhiễu. Ba ràng buộc ở docstring đầu file được giữ ở đây."""
    p = {k: donor.get(k) for k in PROFILE_KEYS if k in donor}
    p["hanh_vi"] = list(donor["hanh_vi"])
    p["deal_breakers"] = list(donor["deal_breakers"])

    for key in LEVELS:
        if rng.random() >= P_STEP:
            continue
        floor = None
        if key == "cleanliness" and (donor["cleanliness"] or 0) > DIRTY_MAX:
            # Ràng buộc 2: donor sạch thì hồ sơ sinh ra không được rơi vào vùng
            # "ở bẩn" — đó là veto cứng của 15/19 người thật.
            floor = DIRTY_MAX + 1
        p[key] = _step(rng, key, p.get(key), floor=floor)

    if rng.random() < P_HANH_VI:
        hv = rng.choice(_HANH_VI_TOGGLE)
        if hv in p["hanh_vi"]:
            p["hanh_vi"].remove(hv)
        else:
            p["hanh_vi"].append(hv)

    if rng.random() < P_SOFT_DB and _SOFT_TOGGLE:
        db = rng.choice(_SOFT_TOGGLE)
        if db in p["deal_breakers"]:
            p["deal_breakers"].remove(db)
        else:
            p["deal_breakers"].append(db)

    # smoke / smoke_in_room: KHÔNG nhiễu (ràng buộc 2 — bật smoke_in_room là tự
    # loại khỏi 18/19 người thật). Lấy nguyên của donor.
    p["smoke"] = donor["smoke"]
    p["smoke_in_room"] = donor["smoke_in_room"]
    return p


def _bio(p: dict) -> str:
    parts = [
        _BIO_SLEEP.get(p.get("sleep_time")),
        _BIO_CLEAN.get(p.get("cleanliness")),
        _BIO_NOISE.get(p.get("noise_tolerance")),
    ]
    head = ", ".join(x for x in parts if x)
    return f"{head}. {BIO_TAIL}" if head else BIO_TAIL


def generate(
    donors: list[dict],
    don_vi_pool: list[str],
    *,
    gender: str,
    count: int,
    seed: int,
) -> list[SimRow]:
    """`count` hồ sơ mô phỏng cùng giới. Tất định theo (seed, gender, chỉ số).

    Mỗi hàng có rng RIÊNG gieo bằng chuỗi f"{seed}:{gender}:{i}" — không dùng
    trạng thái random toàn cục, và nhờ đó `--count 30` chứa đúng 20 hàng đầu của
    `--count 20` (báo cáo tăng pool mà không phải sinh lại từ đầu).
    """
    pool = [d for d in donors if d["gender"] == gender]
    if not pool:
        return []
    donor_sigs = {_signature(d) for d in pool}
    ten = list(_TEN[gender])
    random.Random(f"{seed}:ten:{gender}").shuffle(ten)

    out: list[SimRow] = []
    for i in range(1, count + 1):
        rng = random.Random(f"{seed}:{gender}:{i}")
        donor = rng.choice(pool)

        # Lặp tới khi vân tay khác MỌI donor: hồ sơ mô phỏng không được là bản
        # sao khít của một người thật (ghi chú đạo đức đầu file). 12 lần là đủ
        # rộng; hết lượt thì cưỡng chế nhảy một bậc giờ ngủ.
        p = _perturb(rng, donor)
        for _ in range(12):
            if _signature(p) not in donor_sigs:
                break
            p = _perturb(rng, donor)
        else:
            p["sleep_time"] = _step(rng, "sleep_time", p.get("sleep_time"))

        p["gender"] = gender
        p["don_vi"] = rng.choice(don_vi_pool) if don_vi_pool else None
        p["hanh_vi"] = sorted(p["hanh_vi"]) or [HANH_VI_NONE]
        p["deal_breakers"] = sorted(p["deal_breakers"]) or [DEAL_BREAKER_NONE]
        p["bio"] = _bio(p)

        out.append(SimRow(
            email=f"sim+{gender}{i}@{SIM_EMAIL_DOMAIN}",
            name=f"{rng.choice(_HO)} {ten[(i - 1) % len(ten)]}",
            donor_row=donor.get("row_no"),
            profile={k: p.get(k) for k in PROFILE_KEYS},
        ))
    return out


def split_count(total: int, gender: str) -> dict[str, int]:
    """Chia `--count` cho hai giới. Nữ nhận phần dư: nữ mới là phía thiếu hồ sơ
    (3 thật so với 6 nam), tức là lý do tồn tại của cả file này."""
    if gender in GENDERS:
        return {gender: total}
    nu = (total + 1) // 2
    return {"nu": nu, "nam": total - nu}


# ─────────────────────── Kiểm tra: lọc cứng có cho qua không ─────────────────

def real_profiles(donors: list[dict], csv_path: Path) -> list[Profile]:
    """Hồ sơ THẬT (từ CSV) để đối chứng lọc cứng — id âm, không liên quan DB.

    Dùng CSV chứ không dùng DB: chạy được cả trong `--dry-run` và trong pytest
    không có Postgres, và 19 hồ sơ CSV là siêu tập của 9 hồ sơ đã vào DB.
    `donors` đã bỏ người khai "ở một mình" nên phải đọc lại CSV cho đủ pool thật.
    """
    rows = list(csv.DictReader(csv_path.open(encoding="utf-8")))
    out: list[Profile] = []
    for n, r in enumerate(rows, start=1):
        sleep = sm.sleep_time(r.get("sleep_time"))
        clean = sm.cleanliness(r.get("dishes"))
        gender = sm.gender(r.get("gender"))
        if (sleep is None and clean is None) or gender not in GENDERS:
            continue
        hanh_vi, _ = sm.split_multi(r.get("behaviors"), HANH_VI)
        dbs, _ = sm.split_multi(r.get("deal_breakers"), DEAL_BREAKER)
        smoke, smoke_in_room, infer = sm.smoking(r.get("smoking"))
        out.append(Profile.from_row({
            "user_id": -(10_000 + n),
            "gender": gender,
            "don_vi": (r.get("don_vi") or "").strip() or None,
            "budget_band": sm.budget_band(r.get("budget")),
            "scenario": sm.scenario(r.get("plan")),
            "sleep_time": sleep,
            "cleanliness": clean,
            "noise_tolerance": sm.noise_tolerance(r.get("noise_reaction")),
            "ac_usage": sm.ac_usage(r.get("ac_usage")),
            "money_style": sm.money_style(r.get("money_style")),
            "persona": sm.persona(r.get("persona")),
            "smoke": smoke,
            "smoke_in_room": smoke_in_room,
            "hanh_vi": hanh_vi,
            "deal_breakers": sm.deal_breakers_with_smoking(dbs, infer),
            "is_simulated": False,
        }))
    return out


def pass_report(sims: list[SimRow], reals: list[Profile]) -> dict:
    """Bao nhiêu cặp (mô phỏng × thật) CÙNG GIỚI đi qua lọc cứng.

    Đây là kiểm tra sinh-ra-có-dùng-được-không, không phải chỉ số nghiên cứu: tỉ
    lệ thấp nghĩa là generator đang sinh hồ sơ bị veto, pool to ra mà deck vẫn
    rỗng. Gộp cả lý do loại (hard_filter_reason) để biết phải sửa chỗ nào.
    """
    pairs = passed = 0
    reasons: dict[str, int] = {}
    sim_empty = 0                       # hồ sơ mô phỏng không ghép được với ai thật
    per_real: dict[int, int] = {p.user_id: 0 for p in reals}
    per_gender: dict[str, list[int]] = {g: [0, 0] for g in GENDERS}   # [qua, tổng]

    for i, s in enumerate(sims, start=1):
        sp = s.as_profile(-i)
        same = [r for r in reals if r.gender == sp.gender]
        ok = 0
        for r in same:
            pairs += 1
            per_gender.setdefault(sp.gender, [0, 0])[1] += 1
            why = hard_filter_reason(sp, r)
            if why is None:
                ok += 1
                passed += 1
                per_real[r.user_id] += 1
                per_gender[sp.gender][0] += 1
            else:
                reasons[why] = reasons.get(why, 0) + 1
        if same and ok == 0:
            sim_empty += 1

    # Phân theo giới vì đây là lý do tồn tại của file: pool NỮ mới là chỗ thiếu.
    gender_stats = {}
    for g, (ok_g, tot_g) in per_gender.items():
        added = [per_real[r.user_id] for r in reals if r.gender == g]
        gender_stats[g] = {
            "pairs": tot_g,
            "passed": ok_g,
            "rate": ok_g / tot_g if tot_g else 0.0,
            # Số thật sự quyết định buổi thử nghiệm: mỗi SV thật được thêm bao
            # nhiêu ứng viên vào deck.
            "added_min": min(added) if added else 0,
            "added_max": max(added) if added else 0,
            "added_zero": sum(1 for v in added if v == 0),
        }

    return {
        "pairs": pairs,
        "passed": passed,
        "rate": passed / pairs if pairs else 0.0,
        "sim_empty_pool": sim_empty,
        "reasons": dict(sorted(reasons.items(), key=lambda kv: -kv[1])),
        "by_gender": gender_stats,
    }


def marginals(key: str, sims: list[SimRow], donors: list[dict]) -> str:
    """Một dòng so marginal thật vs mô phỏng — bằng chứng rẻ nhất cho 'giống phân bố'."""
    def hist(vals):
        h: dict = {}
        for v in vals:
            h[v] = h.get(v, 0) + 1
        return " ".join(f"{k}:{h[k]}" for k in sorted(h, key=lambda x: (x is None, x)))

    return (f"  {key:<16} thật  {hist(d.get(key) for d in donors)}\n"
            f"  {'':<16} mô phỏng {hist(s.profile.get(key) for s in sims)}")


# ───────────────────────────────── Ghi DB ────────────────────────────────────

def _write(engine, rows: list[SimRow]) -> tuple[int, int]:
    """Upsert users + roommate_profiles. Trả (mới, cập nhật).

    Idempotent nhờ email tất định: chạy lại `--count N` không sinh thêm hàng nào.
    """
    created = updated = 0
    with engine.begin() as conn:
        for r in rows:
            # password_hash = NULL ở CẢ hai nhánh và KHÔNG tạo user_identities ⇒
            # không có đường đăng nhập vào hồ sơ mô phỏng. email_verified = FALSE:
            # địa chỉ .invalid không thể xác thực, khai TRUE là nói sai trong DB.
            u = conn.execute(
                text(
                    "INSERT INTO users (email, name, password_hash, email_verified) "
                    "VALUES (:e, :n, NULL, FALSE) "
                    "ON CONFLICT (email) DO UPDATE SET name = EXCLUDED.name, password_hash = NULL "
                    "RETURNING id, (created_at > now() - INTERVAL '5 seconds') AS is_new"
                ),
                {"e": r.email, "n": r.name},
            ).mappings().one()
            created += 1 if u["is_new"] else 0
            updated += 0 if u["is_new"] else 1

            cols = sorted(r.profile)
            # is_simulated = TRUE và src = 'sim' là LITERAL trong câu SQL, ở cả
            # INSERT và DO UPDATE: không tham số nào điều khiển được nhãn, nên
            # không có đường sinh ra hàng mô phỏng thiếu nhãn (yêu cầu mục 2.8).
            conn.execute(
                text(
                    f"INSERT INTO roommate_profiles (user_id, {', '.join(cols)}, "
                    "is_simulated, src, updated_at) VALUES "
                    f"(:user_id, {', '.join(':' + c for c in cols)}, TRUE, '{SIM_SRC}', now()) "
                    "ON CONFLICT (user_id) DO UPDATE SET "
                    + ", ".join(f"{c} = EXCLUDED.{c}" for c in cols)
                    + f", is_simulated = TRUE, src = '{SIM_SRC}', updated_at = now()"
                ),
                {"user_id": u["id"], **r.profile},
            )
    return created, updated


def reset(engine, *, dry_run: bool) -> int:
    """Xoá CHỈ user có email khớp SIM_EMAIL_LIKE. Trả số đã (hoặc sẽ) xoá.

    Đếm và in TRƯỚC khi xoá: pattern sai mà xoá im lặng là mất tài khoản thật.
    """
    with engine.begin() as conn:
        n = conn.execute(
            text("SELECT count(*) FROM users WHERE email LIKE :pat"), {"pat": SIM_EMAIL_LIKE}
        ).scalar_one()
        print(f"--reset: {n} tài khoản mô phỏng khớp {SIM_EMAIL_LIKE}")
        if dry_run or not n:
            return int(n)
        conn.execute(text("DELETE FROM users WHERE email LIKE :pat"), {"pat": SIM_EMAIL_LIKE})
        # conversations.match_id là ON DELETE SET NULL, conversation_members thì
        # CASCADE ⇒ hội thoại của hồ sơ mô phỏng còn lại 1 thành viên, mồ côi.
        # Chat sẽ render một hội thoại không có người kia nếu không dọn (giống
        # chat/seed_demo.py --reset).
        conn.execute(
            text(
                "DELETE FROM conversations c WHERE (SELECT count(*) FROM conversation_members m "
                "WHERE m.conversation_id = c.id) < 2"
            )
        )
    return int(n)


def run(csv_path: Path, *, count: int, gender: str, seed: int, dry_run: bool, do_reset: bool) -> int:
    try:
        donors, don_vi_pool, skipped = load_donors(csv_path)
    except ValueError as e:
        print(f"LỖI: {e}", file=sys.stderr)
        print("Cập nhật HANH_VI/DEAL_BREAKER trong matching/profile.py rồi chạy lại.", file=sys.stderr)
        return 2

    by_gender = {g: sum(1 for d in donors if d["gender"] == g) for g in GENDERS}
    print(f"Donor từ {csv_path}: {len(donors)} hồ sơ thật {by_gender}")
    print(f"  bỏ qua: {skipped}")
    print(f"  don_vi lấy mẫu độc lập từ {len(don_vi_pool)} Trường/Khoa (>= {DON_VI_MIN_COUNT} người)")

    engine = None
    if do_reset or not dry_run:
        engine = create_engine(settings.database_url, pool_pre_ping=True)
    if do_reset:
        reset(engine, dry_run=dry_run)

    plan = split_count(count, gender)
    rows: list[SimRow] = []
    for g, n in plan.items():
        if n <= 0:
            continue
        got = generate(donors, don_vi_pool, gender=g, count=n, seed=seed)
        if len(got) < n:
            print(f"CẢNH BÁO: không có donor giới '{g}' ⇒ sinh 0 (cần hồ sơ thật giới này)")
        rows.extend(got)

    if not rows:
        print("Không sinh hồ sơ nào.")
        return 0

    print(f"\nSinh {len(rows)} hồ sơ (seed={seed}): "
          + ", ".join(f"{g}={sum(1 for r in rows if r.profile['gender'] == g)}" for g in GENDERS))
    for r in rows[:5]:
        p = r.profile
        print(f"  {r.email:<34} {r.name:<18} sleep={p['sleep_time']} clean={p['cleanliness']} "
              f"noise={p['noise_tolerance']} budget={p['budget_band']} "
              f"hv={len(p['hanh_vi'])} db={len(p['deal_breakers'])} (donor dòng {r.donor_row})")
    if len(rows) > 5:
        print(f"  … còn {len(rows) - 5} hồ sơ nữa")

    print("\nSo marginal thật vs mô phỏng:")
    for key in ("sleep_time", "cleanliness", "noise_tolerance", "ac_usage", "budget_band"):
        print(marginals(key, rows, donors))

    reals = real_profiles(donors, csv_path)
    rep = pass_report(rows, reals)
    print(f"\nLọc cứng (mô phỏng × {len(reals)} hồ sơ thật, cùng giới):")
    print(f"  qua {rep['passed']}/{rep['pairs']} cặp = {rep['rate']:.1%}")
    print(f"  hồ sơ mô phỏng không ghép được với ai thật: {rep['sim_empty_pool']}")
    for g, st in rep["by_gender"].items():
        print(f"  {g}: qua {st['passed']}/{st['pairs']} = {st['rate']:.1%} · "
              f"mỗi SV thật thêm {st['added_min']}–{st['added_max']} ứng viên "
              f"(còn 0 ứng viên: {st['added_zero']} người)")
    if rep["reasons"]:
        print(f"  lý do loại: {rep['reasons']}")

    if dry_run:
        print("\n--dry-run: không ghi gì vào DB.")
        return 0

    created, updated = _write(engine, rows)
    print(f"\n✓ tài khoản mới {created} · cập nhật {updated} · tất cả is_simulated=TRUE, src='{SIM_SRC}'")
    print("  Không đăng nhập được (password_hash NULL, không có user_identities).")
    print(f"  Xoá: python -m app.matching.simulate --reset --count 0")
    return 0


def main() -> None:
    ap = argparse.ArgumentParser(description="Sinh hồ sơ ở ghép mô phỏng có nhãn (bootstrap)")
    ap.add_argument("--csv", type=Path, default=DEFAULT_CSV, help="CSV khảo sát (docker cp vào container)")
    ap.add_argument("--count", type=int, default=20, help="tổng số hồ sơ; chia cho 2 giới khi --gender both")
    ap.add_argument("--gender", choices=[*GENDERS, "both"], default="both")
    ap.add_argument("--seed", type=int, default=DEFAULT_SEED, help="tái lập đúng pool trong báo cáo")
    ap.add_argument("--dry-run", action="store_true", help="in thống kê, không ghi DB")
    ap.add_argument("--reset", action="store_true", help="xoá hồ sơ mô phỏng cũ trước khi sinh")
    a = ap.parse_args()
    if not a.csv.is_file():
        sys.exit(
            f"Không thấy CSV: {a.csv}\n"
            '  docker cp eval/data/survey_v2.csv "$(docker compose ps -q api)":/tmp/survey.csv'
        )
    sys.exit(run(a.csv, count=a.count, gender=a.gender, seed=a.seed,
                 dry_run=a.dry_run, do_reset=a.reset))


if __name__ == "__main__":
    main()
