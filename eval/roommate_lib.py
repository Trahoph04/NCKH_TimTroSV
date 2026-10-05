"""Cầu nối notebook 06 ↔ thuật toán ghép THẬT trong apps/api/app/matching.

Vì sao không tự cài lại công thức trong notebook: số trong báo cáo phải là số
của sản phẩm. Notebook import đúng filters/score/weights/stable/simulate mà API
đang chạy.

Vì sao phải "đi vòng" khi import: app/matching/__init__.py import repo + router
⇒ kéo theo FastAPI. Venv eval không cần (và không nên cần) FastAPI, nên ta đăng
ký sẵn package rỗng `app` / `app.matching` trong sys.modules rồi mới import các
module con THUẦN — __init__.py không chạy.

KHÔNG in họ tên/email/MSSV ở bất kỳ đâu: CSV có PII, notebook (kèm output) có
thể bị commit. Hồ sơ thật mang id âm (simulate.real_profiles), không có tên.
"""
from __future__ import annotations

import csv
import math
import random
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API = ROOT / "apps" / "api"
DATA = ROOT / "eval" / "data"
SURVEY_CSV = DATA / "survey_v2.csv"
RATINGS_CSV = DATA / "ratings.csv"
DECK_LOG_CSV = DATA / "deck_log.csv"


def _bootstrap_imports() -> None:
    if "app.matching.filters" in sys.modules:
        return
    sys.path.insert(0, str(API))
    for name, path in (("app", API / "app"), ("app.matching", API / "app" / "matching")):
        if name not in sys.modules:
            mod = types.ModuleType(name)
            mod.__path__ = [str(path)]  # package rỗng: __init__.py KHÔNG chạy
            sys.modules[name] = mod


_bootstrap_imports()

from app.matching import filters as F  # noqa: E402
from app.matching import score as S  # noqa: E402
from app.matching import simulate as SIM  # noqa: E402
from app.matching import stable as ST  # noqa: E402
from app.matching import weights as W  # noqa: E402
from app.matching.profile import ORDINAL_RANGE, Profile  # noqa: E402

__all__ = ["F", "S", "SIM", "ST", "W", "Profile", "ORDINAL_RANGE",
           "load_real", "load_sims", "cosine_vector", "arith_score", "mean_score",
           "pool_sizes", "topk", "bootstrap_pool"]


# ──────────────────────────────── dữ liệu ────────────────────────────────────

def load_real(csv_path: Path = SURVEY_CSV) -> list[Profile]:
    """Hồ sơ thật từ khảo sát (id âm). Gồm cả người KHÔNG đồng ý dùng thử: dữ liệu
    lối sống của họ nằm trong phạm vi đồng ý của khảo sát (import_survey.py)."""
    return SIM.real_profiles([], csv_path)


def load_sims(count: int = 24, seed: int = SIM.DEFAULT_SEED, csv_path: Path = SURVEY_CSV) -> list[Profile]:
    """Hồ sơ mô phỏng đúng như `python -m app.matching.simulate` sinh (cùng seed)."""
    donors, don_vi, _ = SIM.load_donors(csv_path)
    out: list[Profile] = []
    uid = 1
    for g, n in SIM.split_count(count, "both").items():
        for row in SIM.generate(donors, don_vi, gender=g, count=n, seed=seed):
            out.append(Profile.from_row({"user_id": uid, **row.profile, "is_simulated": True}))
            uid += 1
    return out


def survey_rows(csv_path: Path = SURVEY_CSV) -> int:
    with csv_path.open(encoding="utf-8") as f:
        return sum(1 for _ in csv.DictReader(f))


# ─────────────────────────────── baseline ────────────────────────────────────

# Thứ tự chiều cho baseline cosine — chỉ các chiều thứ bậc (cosine không định
# nghĩa được trên tập hợp hanh_vi/deal_breakers).
COS_KEYS = ("sleep_time", "cleanliness", "noise_tolerance", "ac_usage", "budget_band")


def cosine_vector(p: Profile) -> list[float | None]:
    """Vector thô (không chuẩn hoá) — đúng thứ SRS FR-5.2 'Weighted Cosine' mô tả."""
    return [None if getattr(p, k) is None else float(getattr(p, k)) for k in COS_KEYS]


def arith_score(a: Profile, b: Profile, weights: dict[str, float]) -> float:
    """Biến thể ablation: gộp hai chiều bằng TRUNG BÌNH CỘNG thay vì harmonic."""
    ps = S.pair_score(a, b, weights)
    return (ps.s_ab + ps.s_ba) / 2


def mean_score(a: Profile, b: Profile, weights: dict[str, float], combine: str = "harmonic") -> float:
    ps = S.pair_score(a, b, weights)
    return ps.score if combine == "harmonic" else (ps.s_ab + ps.s_ba) / 2


# ─────────────────────────── pool / xếp hạng ────────────────────────────────

def pool_sizes(profiles: list[Profile], *, hard: bool = True, filt=None) -> dict[int, int]:
    """Số ứng viên qua lọc của mỗi người (chỉ cùng giới — chính sách tuyệt đối)."""
    f = filt or (F.passes_hard_filters if hard else (lambda a, b: a.gender == b.gender and a.user_id != b.user_id))
    return {a.user_id: sum(1 for b in profiles if b.user_id != a.user_id and f(a, b)) for a in profiles}


def topk(me: Profile, others: list[Profile], weights: dict[str, float], k: int = 5,
         *, combine: str = "harmonic", hard: bool = True) -> list[int]:
    cands = [o for o in others if o.user_id != me.user_id and o.gender == me.gender
             and (not hard or F.passes_hard_filters(me, o))]
    cands.sort(key=lambda o: (-mean_score(me, o, weights, combine), o.user_id))
    return [o.user_id for o in cands[:k]]


def bootstrap_pool(real: list[Profile], n: int, rng: random.Random) -> list[Profile]:
    """Pool N người lấy mẫu CÓ HOÀN LẠI từ hồ sơ thật (id mới cho mỗi bản sao).

    Đây là MÔ PHỎNG: giả định người mới tham gia có phân bố giống 19 người đã
    khảo sát. Báo cáo phải ghi rõ giả định này cạnh đường cong độ phủ.
    """
    out = []
    for i in range(n):
        src = rng.choice(real)
        d = {f: getattr(src, f) for f in src.__slots__}
        d["user_id"] = i + 1
        d["hanh_vi"] = list(src.hanh_vi)
        d["deal_breakers"] = list(src.deal_breakers)
        out.append(Profile.from_row(d))
    return out


def pct(x: float) -> str:
    return "—" if x is None or (isinstance(x, float) and math.isnan(x)) else f"{100 * x:.1f}%"
