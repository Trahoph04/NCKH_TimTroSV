"""Lõi gợi ý nhà trọ — THUẦN (không DB, không FastAPI): API và notebook 01 gọi đúng cùng một code.

Knowledge-based recommender 3 tầng (docs/specs/Recommendation.md, ADR-021):
  1. lọc cứng + tự nới ràng buộc khi quá ít ứng viên (McSherry 2004)
  2. hữu dụng đa thuộc tính MAUT: U = Σ w_k·u_k, trọng số từ khảo sát (31 SV chọn top-3)
  3. đa dạng hoá MMR (Carbonell & Goldstein 1998), λ = 0,7
Kèm 2 hệ đối chứng cho buổi đánh giá mù: B-giá (lọc + sắp giá) và B-cosine (thiết kế gốc 03_ThietKe).

Mọi hằng số ở đây là THIẾT KẾ (không phải số đo) trừ SURVEY_TOP3 — notebook 01 kiểm độ nhạy ±20%.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

ALGO_VERSION = "maut-mmr-v1"

THETA = 0.5        # điểm của thuộc tính "chưa rõ": tin không nhắc ≠ không có (trung tính cho biến nhị phân)
LAMBDA = 0.7       # MMR: 0,7 phần độ phù hợp, 0,3 phần khác biệt
SHRINK = 0.5       # w = SHRINK·w_khảo_sát + (1 − SHRINK)·w_bản_thân
PRICE_TOL = 1.2    # vượt ngân sách tới 20% còn xét (thương lượng được), điểm giá giảm về 0
PRICE_KNEE = 0.6   # điểm giá đúng bằng ngân sách
MISSING_MINUTES_U = 0.3  # tin chưa route được: không loại hẳn nhưng không cho điểm cao
MARKET_RADIUS_M = 500
POOL_FOR_MMR = 200       # chỉ chạy MMR trên 200 ứng viên điểm cao nhất (đủ đa dạng, tránh O(n·k) thừa)

# Tần suất chọn "3 yếu tố quan trọng nhất" — eval/data/survey_v2.csv cột top3_factors, N = 31 người trả lời
# (07/10/2026). "An ninh khu vực" (19/31) BỎ: chưa có nguồn dữ liệu an ninh đáng tin (quyết định 07/10).
# Notebook 01 tính lại từ CSV và assert khớp bảng này.
SURVEY_TOP3: dict[str, int] = {
    "gia": 20,
    "gan_truong": 19,
    "gio_tu_do": 15,
    "tien_nghi": 13,
    "cho_de_xe": 6,
    "gan_cho": 1,
}
FACTOR_LABELS: dict[str, str] = {
    "gia": "Giá thuê rẻ",
    "gan_truong": "Gần trường / đi lại nhanh",
    "gio_tu_do": "Giờ giấc tự do",
    "tien_nghi": "Tiện nghi (máy lạnh, wifi, WC riêng…)",
    "cho_de_xe": "Có chỗ để xe",
    "gan_cho": "Gần chợ / quán ăn",
}
# Khớp AMENITY_KEYWORDS của crawler (crawler/normalize.py) và câu C5 khảo sát.
AMENITY_LABELS: dict[str, str] = {
    "wifi": "Wifi",
    "air_conditioner": "Máy lạnh",
    "private_wc": "WC riêng",
    "parking": "Chỗ để xe",
    "kitchen": "Được nấu ăn",
    "fridge": "Tủ lạnh",
    "washing_machine": "Máy giặt",
    "free_hours": "Giờ giấc tự do",
}
COMFORT = ("air_conditioner", "wifi", "private_wc", "fridge", "washing_machine", "kitchen")
CAMPUS_LABELS = ("khu I", "khu II", "khu III")


@dataclass(frozen=True)
class Candidate:
    id: int
    price: int
    minutes: tuple[float | None, float | None, float | None]  # phút ORS tới khu I/II/III
    amenities: frozenset[str]          # tiện ích TIN CÓ NHẮC (không nhắc = chưa rõ)
    free_hours: bool | None            # None = tin không nói
    listing_type: str | None
    gender_only: str | None            # 'nam' | 'nu' | None
    lat: float
    lng: float
    market_pois: int = 0               # chợ + siêu thị/tiện lợi trong 500 m (bảng pois)
    quality: float = 0.0               # chỉ để phá hoà, không phải yếu tố


@dataclass(frozen=True)
class Query:
    budget: int                        # VND/tháng, chưa điện nước (như câu C1)
    campus: int = 1
    max_minutes: float = 10.0          # câu C4
    housing: str | None = None         # 'phong_tro' | 'nha_mini' | None = cả hai
    required: tuple[str, ...] = ()     # câu C5 — tiện ích "bắt buộc" (xử lý MỀM, xem R5)
    top_factors: tuple[str, ...] = ()  # ≤ 3 key của SURVEY_TOP3
    gender: str | None = None


@dataclass
class Scored:
    c: Candidate
    utility: float
    parts: dict[str, float]            # w_k·u_k
    utilities: dict[str, float]        # u_k
    unknown: list[str] = field(default_factory=list)  # tiện ích người dùng cần mà tin không nhắc


# ── Tầng 2: hàm hữu dụng ─────────────────────────────────────────────────────

def u_price(p: int, budget: int) -> float:
    """Rẻ hơn ngân sách tốt hơn (bão hoà ở 50% ngân sách); vượt ngân sách bị phạt dốc."""
    if p <= budget:
        return min(1.0, PRICE_KNEE + (1 - PRICE_KNEE) * (budget - p) / (0.5 * budget))
    if p <= PRICE_TOL * budget:
        return PRICE_KNEE * (PRICE_TOL * budget - p) / ((PRICE_TOL - 1) * budget)
    return 0.0


def minutes_cap(max_minutes: float) -> float:
    """Trần thời gian đi của lọc cứng — rộng hơn T vì SV khai theo khoảng (5–10, 10–15…)."""
    return max(1.5 * max_minutes, max_minutes + 5)


def u_commute(m: float | None, max_minutes: float) -> float:
    if m is None:
        return MISSING_MINUTES_U
    half = 0.5 * max_minutes
    if m <= half:
        return 1.0
    if m <= max_minutes:
        return 1.0 - 0.4 * (m - half) / half
    cap = minutes_cap(max_minutes)
    if m <= cap:
        return 0.6 * (cap - m) / (cap - max_minutes)
    return 0.0


def u_free_hours(c: Candidate) -> float:
    if c.free_hours is True or "free_hours" in c.amenities:
        return 1.0
    if c.free_hours is False:
        return 0.0
    return THETA


def u_comfort(c: Candidate, required: tuple[str, ...]) -> float:
    need = [a for a in required if a in COMFORT]
    if need:
        return sum(1.0 if a in c.amenities else THETA for a in need) / len(need)
    return min(1.0, len(c.amenities & set(COMFORT)) / 3)


def u_parking(c: Candidate) -> float:
    return 1.0 if "parking" in c.amenities else THETA


def u_market(c: Candidate) -> float:
    return min(1.0, c.market_pois / 3)


def weights(top_factors: tuple[str, ...] = ()) -> dict[str, float]:
    """Trọng số khảo sát co rút về lựa chọn của chính người dùng (ước lượng co rút kiểu Bayes:
    tiên nghiệm quần thể + tín hiệu cá nhân). Không chọn gì ⇒ đúng trọng số khảo sát."""
    total = sum(SURVEY_TOP3.values())
    base = {k: v / total for k, v in SURVEY_TOP3.items()}
    chosen = [f for f in dict.fromkeys(top_factors) if f in base][:3]
    if not chosen:
        return base
    own = {k: (1 / len(chosen) if k in chosen else 0.0) for k in base}
    return {k: SHRINK * base[k] + (1 - SHRINK) * own[k] for k in base}


def score(c: Candidate, q: Query, w: dict[str, float] | None = None) -> Scored:
    w = w or weights(q.top_factors)
    u = {
        "gia": u_price(c.price, q.budget),
        "gan_truong": u_commute(c.minutes[q.campus], q.max_minutes),
        "gio_tu_do": u_free_hours(c),
        "tien_nghi": u_comfort(c, q.required),
        "cho_de_xe": u_parking(c),
        "gan_cho": u_market(c),
    }
    parts = {k: w[k] * u[k] for k in w}
    unknown = [a for a in q.required if a not in c.amenities and not (a == "free_hours" and c.free_hours)]
    return Scored(c=c, utility=sum(parts.values()), parts=parts, utilities=u, unknown=unknown)


# ── Tầng 1: lọc cứng + nới ràng buộc ─────────────────────────────────────────

# (phút cộng thêm vào trần, hệ số giá, còn lọc loại chỗ ở). Nới thời gian trước giá vì trọng số
# khảo sát của giá (20) cao hơn của khoảng cách (19); bỏ lọc loại chỗ ở là bước cuối.
RELAX_PLAN: tuple[tuple[float, float, bool], ...] = (
    (0, PRICE_TOL, True),
    (5, PRICE_TOL, True),
    (10, PRICE_TOL, True),
    (20, PRICE_TOL, True),
    (20, 1.35, True),
    (20, 1.5, True),
    (20, 1.5, False),
)


def passes(c: Candidate, q: Query, extra_min: float = 0, price_tol: float = PRICE_TOL,
           use_housing: bool = True) -> bool:
    m = c.minutes[q.campus]
    if m is None or m > minutes_cap(q.max_minutes) + extra_min:
        return False
    if c.price > price_tol * q.budget:
        return False
    if use_housing and q.housing and c.listing_type != q.housing:
        return False
    if q.gender and c.gender_only in ("nam", "nu") and c.gender_only != q.gender:
        return False
    return True


def filter_with_relaxation(cands: list[Candidate], q: Query, k: int = 10) -> tuple[list[Candidate], list[str]]:
    pool: list[Candidate] = []
    step = RELAX_PLAN[0]
    for step in RELAX_PLAN:
        pool = [c for c in cands if passes(c, q, *step)]
        if len(pool) >= k:
            break
    extra, tol, use_h = step
    relaxed = []
    if extra:
        relaxed.append(f"thời gian đi tới {minutes_cap(q.max_minutes) + extra:.0f} phút")
    if tol > PRICE_TOL:
        relaxed.append(f"giá tới {tol * q.budget / 1e6:.1f} triệu")
    if q.housing and not use_h:
        relaxed.append("mọi loại chỗ ở")
    return pool, relaxed


# ── Tầng 3: đa dạng hoá ──────────────────────────────────────────────────────

def haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    r = 6_371_000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def similarity(a: Candidate, b: Candidate, budget: int) -> float:
    """Độ giống 2 tin ∈ [0, 1] — dùng cho MMR và ILS. Cùng vị trí (≤ 150 m: thường là cùng điểm mặc
    định của phường) nặng nhất vì đó là kiểu trùng lặp hay gặp nhất trong dữ liệu."""
    geo = 1.0 if haversine_m(a.lat, a.lng, b.lat, b.lng) <= 150 else 0.0
    price = max(0.0, 1 - abs(a.price - b.price) / (0.25 * budget))
    typ = 1.0 if a.listing_type == b.listing_type else 0.0
    return 0.5 * geo + 0.3 * price + 0.2 * typ


def mmr(scored: list[Scored], k: int, budget: int, lam: float | None = None) -> list[Scored]:
    # đọc LAMBDA lúc chạy (không gắn làm mặc định khi định nghĩa) để notebook đổi được khi kiểm độ nhạy
    lam = LAMBDA if lam is None else lam
    rest = sorted(scored, key=lambda s: (-s.utility, -s.c.quality, s.c.id))[:POOL_FOR_MMR]
    chosen: list[Scored] = []
    while rest and len(chosen) < k:
        def gain(s: Scored) -> float:
            red = max((similarity(s.c, t.c, budget) for t in chosen), default=0.0)
            return lam * s.utility - (1 - lam) * red
        best = max(rest, key=gain)
        chosen.append(best)
        rest.remove(best)
    return chosen


def ils(items: list[Candidate], budget: int) -> float:
    """Intra-List Similarity (Ziegler et al. 2005): trung bình độ giống theo cặp — thấp = đa dạng."""
    pairs = [(a, b) for i, a in enumerate(items) for b in items[i + 1:]]
    if not pairs:
        return 0.0
    return sum(similarity(a, b, budget) for a, b in pairs) / len(pairs)


# ── Hệ đề xuất + 2 hệ đối chứng ─────────────────────────────────────────────

def recommend(cands: list[Candidate], q: Query, k: int = 10) -> tuple[list[Scored], list[str], int]:
    """(top-k, ràng buộc đã nới, số ứng viên qua lọc cứng). MMR chỉ CHỌN TẬP k tin; thứ tự trả về theo U
    giảm dần — hiển thị theo thứ tự chọn của MMR làm tin 94% đứng sau tin 87%, người dùng đọc như lỗi.
    Đánh giá (NDCG) dùng đúng thứ tự trả về này."""
    pool, relaxed = filter_with_relaxation(cands, q, k)
    w = weights(q.top_factors)
    scored = [score(c, q, w) for c in pool]
    chosen = mmr(scored, k, q.budget)
    return sorted(chosen, key=lambda s: (-s.utility, -s.c.quality, s.c.id)), relaxed, len(pool)


def baseline_price(cands: list[Candidate], q: Query, k: int = 10) -> list[Candidate]:
    """B-giá: đúng cách SV dùng bộ lọc hiện có — giá ≤ ngân sách, phút ≤ T, sắp giá tăng. Không nới,
    nên có thể trả < k tin (đó cũng là trải nghiệm thật của bộ lọc)."""
    pool = [
        c for c in cands
        if c.minutes[q.campus] is not None and c.minutes[q.campus] <= q.max_minutes
        and c.price <= q.budget and (not q.housing or c.listing_type == q.housing)
        and not (q.gender and c.gender_only in ("nam", "nu") and c.gender_only != q.gender)
    ]
    return sorted(pool, key=lambda c: (c.price, c.minutes[q.campus], c.id))[:k]


def baseline_cosine(cands: list[Candidate], q: Query, k: int = 10) -> list[Candidate]:
    """B-cosine: Module 2 của planning/03_ThietKe — vector SV [ngân sách, phút mong muốn, tiện ích cần]
    vs vector phòng [giá, phút, có tiện ích], chuẩn hoá min-max trên danh mục, xếp theo cosine. Không lọc
    giá/phút (thiết kế gốc không có); chỉ giữ lựa chọn loại chỗ ở vì đó là thao tác UI, không phải thuật toán."""
    pool = [c for c in cands if c.minutes[q.campus] is not None
            and (not q.housing or c.listing_type == q.housing)]
    if not pool:
        return []
    prices = [c.price for c in pool]
    mins = [c.minutes[q.campus] for c in pool]
    pmin, pmax = min(prices), max(prices)
    mmin, mmax = min(mins), max(mins)

    def norm(x: float, lo: float, hi: float) -> float:
        return (x - lo) / (hi - lo) if hi > lo else 0.0

    need = [a for a in q.required if a in AMENITY_LABELS]
    user = [norm(q.budget, pmin, pmax), norm(q.max_minutes, mmin, mmax)] + [1.0] * len(need)

    def vec(c: Candidate) -> list[float]:
        has = [1.0 if (a in c.amenities or (a == "free_hours" and c.free_hours)) else 0.0 for a in need]
        return [norm(c.price, pmin, pmax), norm(c.minutes[q.campus], mmin, mmax)] + has

    def cos(a: list[float], b: list[float]) -> float:
        na, nb = math.sqrt(sum(x * x for x in a)), math.sqrt(sum(x * x for x in b))
        return sum(x * y for x, y in zip(a, b)) / (na * nb) if na and nb else 0.0

    return sorted(pool, key=lambda c: (-cos(user, vec(c)), c.id))[:k]


# ── Giải thích ───────────────────────────────────────────────────────────────

def _fmt_money(v: float) -> str:
    return f"{v / 1e6:.1f}".replace(".", ",") + " triệu" if v >= 1e6 else f"{round(v / 1000)}k"


def explain(s: Scored, q: Query) -> tuple[list[str], list[str]]:
    """(lý do, nên hỏi chủ trọ). Lý do = các yếu tố đóng góp w·u lớn nhất mà u ≥ 0,6 và có dữ liệu thật."""
    c, u = s.c, s.utilities
    text: dict[str, str] = {}
    diff = q.budget - c.price
    if diff >= 0:
        text["gia"] = f"Giá {_fmt_money(c.price)}" + (f", thấp hơn ngân sách {_fmt_money(diff)}" if diff >= 50_000 else "")
    m = c.minutes[q.campus]
    if m is not None:
        text["gan_truong"] = f"{round(m)} phút xe máy tới {CAMPUS_LABELS[q.campus]}"
    if u["gio_tu_do"] == 1.0:
        text["gio_tu_do"] = "Tin ghi giờ giấc tự do"
    have = [AMENITY_LABELS[a] for a in COMFORT if a in c.amenities]
    if have and u["tien_nghi"] >= 0.6:
        text["tien_nghi"] = "Có " + ", ".join(have[:3]).lower()
    if "parking" in c.amenities:
        text["cho_de_xe"] = "Có chỗ để xe"
    if c.market_pois:
        text["gan_cho"] = f"{c.market_pois} chợ/siêu thị trong {MARKET_RADIUS_M} m (chim bay)"

    ranked = sorted((k for k in text if u[k] >= 0.6), key=lambda k: -s.parts[k])
    reasons = [text[k] for k in ranked[:3]]
    if c.price > q.budget:
        reasons.append(f"Vượt ngân sách {_fmt_money(c.price - q.budget)}")
    ask = [AMENITY_LABELS[a] for a in s.unknown]
    return reasons, ask
