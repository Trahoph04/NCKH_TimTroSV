"""Điểm tương thích hai chiều — Gower có trọng số + gộp bằng harmonic mean.

Thuần Python: KHÔNG chạm DB, KHÔNG chạm FastAPI. Nhờ vậy test được bằng pytest
không cần Postgres, và notebook eval gọi lại được đúng hàm mà API đang dùng (nếu
notebook tự cài lại công thức thì số trong báo cáo sẽ không phải số của sản phẩm).

Họ bài toán: Reciprocal Recommender System — ghép người-người, sở thích HAI
CHIỀU. Không phải collaborative filtering: ma trận tương tác rỗng, và "item"
ở đây cũng có sở thích riêng.
  [R12] Pizzato et al. (2010) RECON — điểm tương thích hai chiều, harmonic mean
  [R14] Gower (1971) — đo tương đồng trên dữ liệu TRỘN KIỂU (thứ bậc/nhị phân/tập hợp)

VÌ SAO KHÔNG DÙNG COSINE (bác SRS FR-5.2 "Weighted Cosine ≥ 0.7"): mọi chiều
đều dương và thang ngắn (sleep_time 0..2, cleanliness 1..5...) nên hai vector
luôn gần cùng hướng ⇒ cosine dồn vào dải rất hẹp sát 1, mà cosine lại BỎ QUA độ
lớn — đúng phần chứa thông tin "bạn sạch 5, tôi sạch 2". Ngưỡng 0,7 khi đó cho
mọi người đi qua. Khoảng cách có trọng số giữ được độ lớn.

XỬ LÝ THIẾU DỮ LIỆU (quan trọng — khảo sát có 2 nhánh rẽ bỏ qua phần D): theo
đúng cách Gower gốc xử lý missing — BỎ QUA chiều đó và chuẩn hoá lại theo tổng
trọng số của các chiều CÓ MẶT, chứ không gán d_k = 0 (thành "giống nhau" giả) và
cũng không gán 1 (thành "khác nhau" giả).
"""
from __future__ import annotations

from dataclasses import dataclass

from .filters import soft_violations
from .profile import HANH_VI_SHARE, ORDINAL_RANGE, Profile


@dataclass(slots=True)
class DimScore:
    key: str
    weight: float
    d: float            # khoảng cách [0,1]; 0 = giống hệt
    label: str          # câu tiếng Việt để render lý do / lưu ý


@dataclass(slots=True)
class PairScore:
    s_ab: float                 # B phù hợp với A bao nhiêu (góc nhìn của A)
    s_ba: float                 # A phù hợp với B bao nhiêu
    score: float                # harmonic mean của hai chiều
    reasons: list[str]          # 3 điểm khớp mạnh nhất (góc nhìn của A)
    caveat: str | None          # 1 điểm lệch nhất (góc nhìn của A)
    breakdown: dict[str, float] # {key: d_k} chiều A→B — snapshot để huấn luyện & audit
    soft_flags: list[str]       # deal-breaker MỀM mà B kích hoạt cho A — PHẢI render rõ chữ


def _ordinal(key: str, av: int | None, bv: int | None) -> float | None:
    if av is None or bv is None:
        return None
    return abs(av - bv) / ORDINAL_RANGE[key]


def _binary(av, bv) -> float | None:
    if av is None or bv is None:
        return None
    return 0.0 if av == bv else 1.0


def _jaccard_distance(a: frozenset[str], b: frozenset[str]) -> float | None:
    # Cả hai rỗng = cả hai chưa khai ⇒ không có thông tin, không phải "giống nhau".
    if not a and not b:
        return None
    union = a | b
    return 1.0 - len(a & b) / len(union)


def _noise_asymmetric(viewer: Profile, target: Profile) -> float | None:
    """Chiều BẤT ĐỐI XỨNG: nhu cầu yên tĩnh của `viewer` vs hành vi ồn của `target`.

    Vì sao phải bất đối xứng: noise_tolerance của A đụng hành vi "tối muộn còn
    hoạt động" của B thì CHỈ A bị ảnh hưởng. Điểm đối xứng sẽ cho cặp
    "A chịu được B nhưng B không chịu được A" một điểm trung bình — che mất
    đúng cái làm cặp đó tệ.

    d = 1 khi viewer cực kỳ cần yên tĩnh (tolerance 1) và target có hành vi ồn;
    d = 0 khi target không ồn, bất kể tolerance của viewer.
    """
    if viewer.noise_tolerance is None:
        return None
    if not target.hanh_vi:
        return None
    if not target.noisy:
        return 0.0
    # tolerance 1..5 → mức bị ảnh hưởng 1.0..0.0
    return (5 - viewer.noise_tolerance) / 4


def _soft_db_distance(viewer: Profile, target: Profile) -> tuple[float | None, list[str]]:
    """Chiều BẤT ĐỐI XỨNG nặng nhất: deal-breaker MỀM của viewer bị target kích hoạt.

    Đây là chỗ tầng mềm của filters.py quay lại thành điểm. Thang: 1 vi phạm →
    d=0.5, từ 2 vi phạm → d=1.0 (bão hoà). Lý do bão hoà ở 2: người khai 4-5
    deal-breaker thì gần như ai cũng đụng 1 cái; phân biệt "đụng 2" với "đụng 5"
    không còn ý nghĩa quyết định, trong khi phân biệt 0/1/2 thì có.

    None khi viewer chưa khai deal-breaker nào HOẶC target chưa khai hành vi nào —
    thiếu dữ liệu, không phải "không vi phạm".
    """
    if not viewer.deal_breakers:
        return None, []
    if not target.hanh_vi and target.cleanliness is None:
        return None, []
    v = soft_violations(viewer, target)
    return min(1.0, len(v) / 2), v


_SLEEP_LABEL = {0: "trước 22h", 1: "22h-24h", 2: "sau 0h"}
_AC_LABEL = {0: "ít bật máy lạnh", 1: "bật máy lạnh có tiết kiệm", 2: "bật máy lạnh gần cả đêm"}
_MONEY_LABEL = {1: "chia sòng phẳng từng khoản", 2: "chia đều cho nhanh"}
_CLEAN_LABEL = {1: "để đến khi hết chén sạch", 2: "để 1-2 ngày rồi rửa",
                3: "rửa trong ngày", 4: "rửa trong ngày", 5: "rửa chén ngay"}

# Ngưỡng phân loại một chiều là "khớp" hay "lệch". Nhãn phải diễn tả QUAN HỆ giữa
# hai người, không phải thuộc tính của người kia: nhãn "sẵn sàng dùng chung đồ"
# gắn vào ô Lưu ý đọc thành vô nghĩa (dùng chung đồ là điều tốt) — phải là
# "bạn ấy sẵn sàng dùng chung đồ, bạn thì giữ riêng" mới nói đúng cái lệch.
MATCH_MAX = 0.34
GAP_MIN = 0.50


def _lbl(d: float, match: str, gap: str) -> str:
    return match if d <= MATCH_MAX else gap


def directional_dims(viewer: Profile, target: Profile, weights: dict[str, float]) -> list[DimScore]:
    """Các chiều CÓ MẶT, theo góc nhìn của `viewer`. Chiều thiếu dữ liệu bị bỏ qua."""
    out: list[DimScore] = []

    def add(key: str, d: float | None, label_fn) -> None:
        if d is None:
            return
        w = weights.get(key, 0.0)
        if w <= 0:
            return
        d = max(0.0, min(1.0, d))
        out.append(DimScore(key=key, weight=w, d=d, label=label_fn(d)))

    def g(table, v, fallback="?"):
        return table.get(v, fallback)

    add("sleep_time", _ordinal("sleep_time", viewer.sleep_time, target.sleep_time),
        lambda d: _lbl(d,
            f"cùng giờ ngủ ({g(_SLEEP_LABEL, target.sleep_time)})",
            f"giờ ngủ lệch nhau (bạn {g(_SLEEP_LABEL, viewer.sleep_time)}, bạn ấy {g(_SLEEP_LABEL, target.sleep_time)})"))

    add("cleanliness", _ordinal("cleanliness", viewer.cleanliness, target.cleanliness),
        lambda d: _lbl(d,
            f"cùng mức sạch sẽ ({g(_CLEAN_LABEL, target.cleanliness)})",
            f"mức sạch sẽ lệch nhau (bạn {g(_CLEAN_LABEL, viewer.cleanliness)}, bạn ấy {g(_CLEAN_LABEL, target.cleanliness)})"))

    add("noise", _noise_asymmetric(viewer, target),
        lambda d: _lbl(d,
            "bạn ấy không hoạt động ồn buổi tối",
            "bạn ấy hay hoạt động khuya, mà bạn cần yên tĩnh"))

    add("ac_usage", _ordinal("ac_usage", viewer.ac_usage, target.ac_usage),
        lambda d: _lbl(d,
            f"cùng cách dùng máy lạnh ({g(_AC_LABEL, target.ac_usage)})",
            f"cách dùng máy lạnh lệch nhau (bạn ấy {g(_AC_LABEL, target.ac_usage)})"))

    add("budget_band", _ordinal("budget_band", viewer.budget_band, target.budget_band),
        lambda d: _lbl(d, "cùng mức ngân sách", "ngân sách lệch nhau"))

    add("money_style", _binary(viewer.money_style, target.money_style),
        lambda d: _lbl(d,
            f"cùng cách chia tiền ({g(_MONEY_LABEL, target.money_style)})",
            f"cách chia tiền khác nhau (bạn ấy {g(_MONEY_LABEL, target.money_style)})"))

    add("don_vi", _binary(viewer.don_vi, target.don_vi),
        lambda d: _lbl(d, f"cùng {target.don_vi}", "khác Trường/Khoa"))

    add("hanh_vi", _jaccard_distance(viewer.hanh_vi, target.hanh_vi),
        lambda d: _lbl(d, "thói quen sinh hoạt giống nhau", "thói quen sinh hoạt khác nhau"))

    add("share_stuff", _binary(viewer.share_stuff, target.share_stuff),
        lambda d: _lbl(d,
            "cùng quan điểm về dùng chung đồ",
            "bạn ấy sẵn sàng dùng chung đồ, bạn thì giữ riêng"
            if HANH_VI_SHARE in target.hanh_vi
            else "bạn sẵn sàng dùng chung đồ, bạn ấy thì giữ riêng"))

    add("persona", _binary(viewer.persona, target.persona),
        lambda d: _lbl(d, "cùng kiểu sinh hoạt", "kiểu sinh hoạt trái nhau"))

    d_soft, flags = _soft_db_distance(viewer, target)
    add("deal_breaker_soft", d_soft,
        lambda d: ("bạn ấy có điều bạn từng nói không chấp nhận: " + ", ".join(flags).lower())
                  if flags else "không đụng điều nào bạn không chấp nhận")
    return out


def directional_score(viewer: Profile, target: Profile, weights: dict[str, float]) -> tuple[float, list[DimScore]]:
    """s(viewer→target) ∈ [0,1]. Chuẩn hoá theo tổng trọng số CÁC CHIỀU CÓ MẶT."""
    dims = directional_dims(viewer, target, weights)
    total_w = sum(d.weight for d in dims)
    if total_w <= 0:
        # Không chiều nào tính được (hai hồ sơ gần như trống) — 0.0 là trung thực,
        # không phải 0.5: ta KHÔNG có bằng chứng nào cho rằng cặp này phù hợp.
        return 0.0, dims
    s = 1.0 - sum(d.weight * d.d for d in dims) / total_w
    return max(0.0, min(1.0, s)), dims


def harmonic(s_ab: float, s_ba: float) -> float:
    """Gộp hai chiều [R12]. Chống đúng cặp một chiều: 0.9/0.3 → 0.45 (cộng: 0.60).

    Guard chia 0: cả hai chiều bằng 0 thì harmonic mean không xác định — trả 0.0
    (Matching_Messaging_Design.md:269 bỏ sót nhánh này ⇒ ZeroDivisionError khi
    hai hồ sơ đều rỗng).
    """
    if s_ab <= 0.0 or s_ba <= 0.0:
        return 0.0
    return 2 * s_ab * s_ba / (s_ab + s_ba)


def pair_score(a: Profile, b: Profile, weights: dict[str, float], *, n_reasons: int = 3) -> PairScore:
    """Điểm cặp + lý do, theo góc nhìn của `a` (người đang xem thẻ của `b`)."""
    s_ab, dims_ab = directional_score(a, b, weights)
    s_ba, _ = directional_score(b, a, weights)

    # Lý do = chiều có w_k*(1-d_k) lớn nhất (khớp nhiều VÀ quan trọng).
    # Lưu ý  = chiều có w_k*d_k lớn nhất, chỉ nêu khi thực sự lệch (d >= 0.5):
    # gắn cảnh báo vào một chiều lệch 0.1 làm người dùng mất tin vào toàn bộ gợi ý.
    matches = sorted(dims_ab, key=lambda d: d.weight * (1 - d.d), reverse=True)
    reasons = [d.label for d in matches if d.d <= MATCH_MAX][:n_reasons]

    gaps = sorted(dims_ab, key=lambda d: d.weight * d.d, reverse=True)
    caveat = gaps[0].label if gaps and gaps[0].d >= GAP_MIN else None

    # Vi phạm deal-breaker mềm LUÔN thắng vị trí cảnh báo, dù trọng số có đổi:
    # người dùng đã nói rõ họ không chấp nhận điều đó, ẩn nó đi là lừa họ.
    _, flags = _soft_db_distance(a, b)
    if flags:
        caveat = "bạn ấy có điều bạn từng nói không chấp nhận: " + ", ".join(flags).lower()

    return PairScore(
        s_ab=round(s_ab, 4),
        s_ba=round(s_ba, 4),
        score=round(harmonic(s_ab, s_ba), 4),
        reasons=reasons,
        caveat=caveat,
        breakdown={d.key: round(d.d, 4) for d in dims_ab},
        soft_flags=flags,
    )
