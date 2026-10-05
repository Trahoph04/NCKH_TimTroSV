"""Trọng số w_k — và NGUỒN GỐC của từng con số.

Vì sao file này tồn tại riêng: `03_ThietKe_KyThuat_Va_AI.md` ghi 25/20/15/15/10
mà không nói ở đâu ra. Hội đồng chỉ cần hỏi "ở đâu ra?" là mất điểm. Ở đây mỗi
trọng số mang kèm `source` nói rõ nó là SỐ ĐO hay LỰA CHỌN THIẾT KẾ — và ta báo
cả hai loại một cách trung thực thay vì trộn lẫn rồi gọi chung là "từ khảo sát".

ĐO ĐƯỢC TỪ KHẢO SÁT (n = 19 hồ sơ có phần D, eval/data/survey_v2.csv):
    tần suất chọn deal-breaker                tần suất khai hành vi
    Hút thuốc trong phòng     18/19 = 0.95    rủ bạn về phòng      11/19 = 0.58
    Ở bẩn, không dọn dẹp      15/19 = 0.79    tối muộn còn hoạt động 10/19 = 0.53
    Người yêu ở lại qua đêm   14/19 = 0.74    nấu ăn trong phòng   10/19 = 0.53
    Ồn ào khuya               12/19 = 0.63    đi chơi về khuya      8/19 = 0.42
    Nhậu nhẹt trong phòng     10/19 = 0.53    dùng chung đồ         8/19 = 0.42
    Hay dẫn bạn về phòng       7/19 = 0.37    nuôi thú cưng         5/19 = 0.26
    Nuôi thú cưng              5/19 = 0.26    người yêu ở lại       5/19 = 0.26
    Đi chơi về khuya           4/19 = 0.21    nhậu/tụ tập           5/19 = 0.26
    Nấu ăn trong phòng         2/19 = 0.11

LƯU Ý PHƯƠNG PHÁP: phần lớn deal-breaker đã là LỌC CỨNG (filters.py), nên lấy
tần suất của chúng làm trọng số TÍNH ĐIỂM không phải để lọc lần hai — mà vì tần
suất đó đo đúng một thứ: *mức độ dân số SV quan tâm tới chiều đó*. Người chỉ
chọn 'Ở bẩn' ở mức mềm vẫn muốn chiều sạch sẽ nặng hơn chiều cùng-Trường.

CÁC CHIỀU KHÔNG CÓ CÂU HỎI ĐO ĐỘ QUAN TRỌNG (sleep_time, ac_usage, money_style,
budget_band, don_vi, persona) nhận trọng số GÁN, ghi rõ `source='design'`. Không
giả vờ đó là số đo. Bù lại bằng kiểm tra độ nhạy ±20% (sensitivity()) → nếu thứ
hạng top-5 ổn định thì kết luận được "kết quả không phụ thuộc cách chọn trọng số
cụ thể" — một câu mạnh hơn nhiều so với một bảng trọng số không có nguồn.
"""
from __future__ import annotations

from dataclasses import dataclass

from .profile import DEAL_BREAKER_NONE, HANH_VI_SHARE, Profile

# Deal-breaker nào "soi" chiều tính điểm nào. 'Hút thuốc trong phòng' KHÔNG có
# mặt: nó thuần lọc cứng (smoke_in_room), không có chiều điểm tương ứng.
_PROBES: dict[str, tuple[str, ...]] = {
    "cleanliness": ("Ở bẩn, không dọn dẹp",),
    "noise": ("Ồn ào khuya",),
    "hanh_vi": (
        "Người yêu ở lại qua đêm",
        "Nhậu nhẹt trong phòng",
        "Hay dẫn bạn về phòng",
        "Nuôi thú cưng",
        "Đi chơi về khuya",
        "Nấu ăn trong phòng",
    ),
}

# Trọng số gán cho các chiều không đo được. Thang cố ý ĐẶT THẤP HƠN các chiều
# xung đột: lệch giờ ngủ gây khó chịu, nhưng không ai dọn ra vì bạn cùng phòng
# học khác Trường.
_DESIGN: dict[str, float] = {
    "sleep_time": 0.50,    # nhịp sinh hoạt — nguồn xung đột gián tiếp lớn nhất sau sạch/ồn
    "ac_usage": 0.30,      # tiền điện: gây tranh chấp thật nhưng chia được bằng thoả thuận
    "money_style": 0.30,
    "budget_band": 0.25,   # đã có lọc cứng ±1 bậc nên phần mềm còn lại nhẹ
    "persona": 0.20,       # câu forced-choice, dùng như tín hiệu tổng hợp yếu
    "don_vi": 0.15,        # tiện lợi (đi học cùng giờ), không phải nguồn xung đột
}


@dataclass(slots=True)
class Weight:
    value: float
    source: str   # 'survey' = đo được từ khảo sát · 'design' = lựa chọn thiết kế
    note: str = ""


# Bản ĐÃ ĐO trên 19 hồ sơ thật (2026-10-04). Hard-code để API không phải quét DB
# mỗi request và để kết quả tái lập được; chạy lại derive_weights() khi có thêm
# hồ sơ, rồi cập nhật ở đây kèm ngày + n.
SURVEY_N = 19
SURVEY_WEIGHTS: dict[str, Weight] = {
    "cleanliness": Weight(0.79, "survey", "15/19 chọn 'Ở bẩn' là deal-breaker"),
    "noise": Weight(0.63, "survey", "12/19 chọn 'Ồn ào khuya'"),
    "hanh_vi": Weight(0.37, "survey", "trung bình 6 deal-breaker nhóm hành vi"),
    "share_stuff": Weight(0.42, "survey", "8/19 khai 'sẵn sàng dùng chung đồ'"),
    # Chiều nặng nhất, và có chủ đích: câu hỏi nguồn hỏi thẳng "điều bạn KHÔNG
    # chấp nhận được" ⇒ cường độ là tối đa theo cách hỏi, khác với các chiều
    # còn lại chỉ đo mức ưa thích. Đặt trên cleanliness (0.79) vì đây là điều
    # người dùng tự khai là không chấp nhận, còn 0.79 chỉ là tần suất khai.
    # Tầng CỨNG đã lọc hút-thuốc/ở-bẩn trước (filters.py), nên chiều này chỉ
    # mang phần MỀM — không trừ hai lần.
    "deal_breaker_soft": Weight(0.85, "design", "veto mềm; cường độ tối đa theo cách hỏi"),
    **{k: Weight(v, "design") for k, v in _DESIGN.items()},
}

# Baseline cho bảng ablation: mọi chiều bằng nhau. Dòng đối chứng bắt buộc —
# không có nó thì không chứng minh được trọng số có tác dụng gì.
UNIFORM_WEIGHTS: dict[str, Weight] = {
    k: Weight(1.0, "uniform") for k in SURVEY_WEIGHTS
}


def as_dict(weights: dict[str, Weight]) -> dict[str, float]:
    """score.py chỉ cần {key: float}."""
    return {k: w.value for k, w in weights.items()}


DEFAULT = as_dict(SURVEY_WEIGHTS)
UNIFORM = as_dict(UNIFORM_WEIGHTS)


def derive_weights(profiles: list[Profile]) -> dict[str, Weight]:
    """Tính lại trọng số 'survey' từ tập hồ sơ hiện có — dùng khi pool lớn thêm.

    Chỉ các chiều trong _PROBES được tính lại; chiều 'design' giữ nguyên. Hồ sơ
    mô phỏng bị LOẠI: trọng số phải đến từ người thật, nếu không ta đang học lại
    chính phân bố mình vừa sinh ra.
    """
    real = [p for p in profiles if not p.is_simulated and p.deal_breakers is not None]
    # Người chọn 'Mình dễ tính, không có điều nào' đã bị profile.from_row lọc khỏi
    # deal_breakers, nên mẫu số vẫn phải là TOÀN BỘ người có trả lời phần D.
    n = sum(1 for p in real if p.sleep_time is not None or p.cleanliness is not None)
    if n == 0:
        return dict(SURVEY_WEIGHTS)

    out: dict[str, Weight] = dict(SURVEY_WEIGHTS)
    for dim, probes in _PROBES.items():
        freqs = []
        for probe in probes:
            hits = sum(1 for p in real if probe in p.deal_breakers)
            freqs.append(hits / n)
        val = sum(freqs) / len(freqs)
        out[dim] = Weight(round(val, 4), "survey", f"n={n}, probes={len(probes)}")

    share_hits = sum(1 for p in real if HANH_VI_SHARE in p.hanh_vi)
    out["share_stuff"] = Weight(round(share_hits / n, 4), "survey", f"{share_hits}/{n}")
    return out


def sensitivity(base: dict[str, float], pct: float = 0.20) -> list[tuple[str, dict[str, float]]]:
    """Sinh các biến thể ±pct cho TỪNG chiều — đầu vào của kiểm tra độ ổn định thứ hạng.

    Trả [(tên biến thể, weights)]. Notebook eval chạy top-5 trên từng biến thể rồi
    đo Kendall tau với bản gốc. Doc 2.5 gọi đây là "kiểm tra độ nhạy".
    """
    variants: list[tuple[str, dict[str, float]]] = []
    for key in sorted(base):
        for sign, tag in ((1 + pct, "up"), (1 - pct, "down")):
            v = dict(base)
            v[key] = round(base[key] * sign, 4)
            variants.append((f"{key}_{tag}", v))
    return variants
