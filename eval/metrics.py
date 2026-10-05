"""Metric helpers dùng chung cho eval THS2026-66.

Recommendation: precision_at_k, ndcg_at_k, intra_list_similarity
Retrieval/Risk: recall, precision, false_rate
Matching: mean_absolute_error, cosine_similarity, gini, kendall_tau,
          wilcoxon_signed_rank, coverage_at_least_one

CHỈ dùng thư viện chuẩn — có chủ đích. File này là nguồn công thức DUY NHẤT cho
báo cáo, nên nó phải chạy được ở mọi nơi: trong notebook (có numpy/scipy), trong
container api (không có), và trong pytest. Phụ thuộc numpy ở đây sẽ biến một
công thức dùng chung thành công thức chỉ chạy được trong notebook.

Công thức mà SẢN PHẨM cũng dùng (Gower có trọng số, điểm có hướng, harmonic
mean, lọc cứng 2 tầng, Stable Roommates) KHÔNG nằm ở đây: notebook import thẳng
`app.matching.*`. Cài lại chúng lần hai là cách chắc chắn nhất để số trong báo
cáo và số trong API lệch nhau mà không ai phát hiện.
"""
from __future__ import annotations
import math
from typing import Sequence, Callable


def precision_at_k(recommended: Sequence, relevant: set, k: int = 10) -> float:
    """Tỉ lệ item liên quan trong top-k gợi ý."""
    if k <= 0:
        return 0.0
    topk = list(recommended)[:k]
    hits = sum(1 for item in topk if item in relevant)
    return hits / k


def dcg_at_k(gains: Sequence[float], k: int) -> float:
    return sum(g / math.log2(i + 2) for i, g in enumerate(list(gains)[:k]))


def ndcg_at_k(recommended: Sequence, relevance: dict, k: int = 10) -> float:
    """NDCG@k. relevance: {item: gain}. Item không có trong dict gain=0."""
    gains = [relevance.get(item, 0.0) for item in recommended]
    ideal = sorted(relevance.values(), reverse=True)
    idcg = dcg_at_k(ideal, k)
    if idcg == 0:
        return 0.0
    return dcg_at_k(gains, k) / idcg


def intra_list_similarity(items: Sequence, sim_fn: Callable[[object, object], float]) -> float:
    """ILS = trung bình similarity từng cặp trong danh sách. Thấp = đa dạng."""
    items = list(items)
    n = len(items)
    if n < 2:
        return 0.0
    total = 0.0
    cnt = 0
    for i in range(n):
        for j in range(i + 1, n):
            total += sim_fn(items[i], items[j])
            cnt += 1
    return total / cnt if cnt else 0.0


def recall(tp: int, fn: int) -> float:
    denom = tp + fn
    return tp / denom if denom else 0.0


def precision(tp: int, fp: int) -> float:
    denom = tp + fp
    return tp / denom if denom else 0.0


def false_merge_rate(false_merges: int, total_merges: int) -> float:
    return false_merges / total_merges if total_merges else 0.0


def mean_absolute_error(pred: Sequence[float], true: Sequence[float]) -> float:
    pairs = list(zip(pred, true))
    if not pairs:
        return 0.0
    return sum(abs(p - t) for p, t in pairs) / len(pairs)



# ─────────────────────────────────────────────────────────────────────────────
# Matching / ghép bạn ở (notebook 06)
# ─────────────────────────────────────────────────────────────────────────────

def cosine_similarity(
    a: Sequence[float | None],
    b: Sequence[float | None],
    weights: Sequence[float] | None = None,
) -> float | None:
    """Cosine (có thể có trọng số) giữa hai vector thuộc tính, BỎ QUA chiều thiếu.

    Có mặt ở đây để BÁC BỎ SRS FR-5.2 ("Weighted Cosine ≥ 0,7") bằng số đo, chứ
    không phải để dùng trong sản phẩm. Muốn phản biện một ngưỡng thì phải tính
    đúng đại lượng mà ngưỡng đó nói tới — nên công thức này phải tồn tại và phải
    nằm cùng chỗ với các metric khác.

    Chiều None bị bỏ qua (giống cách Gower gốc xử lý missing, xem
    app/matching/score.py). Gán 0 cho chiều thiếu thì nó vẫn tham gia mẫu số và
    kéo cosine xuống — tức tạo ra "khác nhau" từ chỗ không có dữ liệu.

    None khi không còn chiều nào chung, hoặc một vector có norm 0 (cosine không
    xác định — trả 0.0 ở đây sẽ bị đọc thành "hoàn toàn khác nhau").
    """
    idx = [i for i in range(min(len(a), len(b))) if a[i] is not None and b[i] is not None]
    if not idx:
        return None
    w = [1.0] * min(len(a), len(b)) if weights is None else list(weights)
    num = sum(w[i] * a[i] * b[i] for i in idx)
    na = math.sqrt(sum(w[i] * a[i] * a[i] for i in idx))
    nb = math.sqrt(sum(w[i] * b[i] * b[i] for i in idx))
    if na == 0.0 or nb == 0.0:
        return None
    return num / (na * nb)


def gini(values: Sequence[float]) -> float:
    """Gini của một phân bố không âm. 0 = đều tuyệt đối, →1 = một người hứng hết.

    Dùng đo CONGESTION: số lần mỗi hồ sơ xuất hiện trong top-K của người khác. Ở
    pool nhỏ, vài hồ sơ "trung tính mọi chiều" nằm trong deck của tất cả mọi
    người và hứng hết lời mời (Fair Reciprocal Recommendation, RecSys 2024).
    Trung bình/độ lệch chuẩn KHÔNG thấy được điều đó — hai phân bố cùng trung
    bình có thể một bên đều, một bên dồn hết vào 2 người.

    Công thức mean-difference, không phải xấp xỉ theo đường Lorenz: ở n ≈ 20 sai
    số của xấp xỉ đủ lớn để đổi kết luận.
    """
    xs = [float(v) for v in values]
    n = len(xs)
    if n == 0 or any(x < 0 for x in xs):
        return 0.0
    total = sum(xs)
    if total == 0.0:
        return 0.0   # không ai được hiển thị ⇒ "đều" một cách tầm thường
    diff = sum(abs(x - y) for x in xs for y in xs)
    return diff / (2 * n * total)


def kendall_tau(a: Sequence, b: Sequence) -> float | None:
    """Kendall tau-b giữa hai thứ hạng trên CÙNG tập phần tử. None khi n < 2.

    tau-b (không phải tau-a) vì thứ hạng ở đây CÓ TIES thật: hai ứng viên cùng
    điểm sau khi làm tròn là chuyện thường ở pool 5-7 người. tau-a coi tie là
    discordant ⇒ báo thứ hạng bất ổn trong khi thực tế nó chỉ đang bằng nhau.

    Nhận hai dãy GIÁ TRỊ song song (a[i], b[i] là hai phép đo của cùng phần tử
    i), không nhận hai dãy thứ tự — truyền thứ tự vào sẽ ra số vô nghĩa mà không
    báo lỗi.
    """
    xs, ys = list(a), list(b)
    if len(xs) != len(ys):
        raise ValueError("kendall_tau: hai dãy phải cùng độ dài")
    n = len(xs)
    if n < 2:
        return None
    conc = disc = tie_x = tie_y = 0
    for i in range(n):
        for j in range(i + 1, n):
            dx, dy = xs[i] - xs[j], ys[i] - ys[j]
            if dx == 0 and dy == 0:
                tie_x += 1
                tie_y += 1
            elif dx == 0:
                tie_x += 1
            elif dy == 0:
                tie_y += 1
            elif (dx > 0) == (dy > 0):
                conc += 1
            else:
                disc += 1
    n0 = n * (n - 1) / 2
    denom = math.sqrt((n0 - tie_x) * (n0 - tie_y))
    if denom == 0:
        return None   # một bên hoàn toàn tie ⇒ tương quan không xác định
    return (conc - disc) / denom


def _normal_sf(z: float) -> float:
    """P(Z > z) cho Z ~ N(0,1). math.erfc có sẵn, không cần scipy."""
    return 0.5 * math.erfc(z / math.sqrt(2))


def wilcoxon_signed_rank(x: Sequence[float], y: Sequence[float]) -> dict:
    """Wilcoxon signed-rank GHÉP CẶP (xấp xỉ chuẩn, có hiệu chỉnh ties) + effect size r.

    Vì sao không dùng t-test ghép cặp: P@3/NDCG@3 chỉ nhận vài giá trị rời rạc
    (0, 1/3, 2/3, 1) trên n ≈ 20 người — không có cơ sở nào cho giả định chuẩn.
    Wilcoxon chỉ cần phân bố hiệu đối xứng.

    Cặp có hiệu BẰNG 0 bị loại trước khi xếp hạng (quy ước Wilcoxon gốc) ⇒ n
    trong kết quả là số cặp CÒN LẠI, không phải số người. Hai thuật toán cho
    cùng top-3 ở nhiều người là chuyện bình thường ở pool nhỏ, nên n có thể tụt
    rất sâu — và khi đó p-value nói rất ít. Trả cả `n_zero` để báo cáo nêu thẳng
    điều đó thay vì chỉ in p.

    r = |z| / sqrt(n) — effect size cho kiểm định phi tham số (Rosenthal 1991).
    Báo kèm vì ở n nhỏ, p > 0,05 KHÔNG đồng nghĩa "không có khác biệt"; r cho
    biết khác biệt lớn cỡ nào bất kể p.

    Xấp xỉ chuẩn (không phải phân bố chính xác) để file này không cần scipy;
    notebook 06 đối chiếu lại với scipy.stats.wilcoxon(method='approx') và dừng
    nếu lệch. Ở n < 10 nên đọc p chính xác của scipy, không đọc p ở đây.
    """
    xs, ys = list(x), list(y)
    if len(xs) != len(ys):
        raise ValueError("wilcoxon_signed_rank: hai dãy phải cùng độ dài")
    diffs = [a - b for a, b in zip(xs, ys)]
    nz = [d for d in diffs if d != 0]
    n_zero = len(diffs) - len(nz)
    n = len(nz)
    out = {"n": n, "n_zero": n_zero, "w_plus": 0.0, "w_minus": 0.0,
           "w": 0.0, "z": None, "p_two_sided": None, "r": None}
    if n == 0:
        return out

    # Xếp hạng |d| với hạng TRUNG BÌNH cho các giá trị bằng nhau; giữ kích cỡ
    # nhóm tie để hiệu chỉnh phương sai bên dưới.
    order = sorted(range(n), key=lambda i: abs(nz[i]))
    ranks = [0.0] * n
    tie_groups: list[int] = []
    i = 0
    while i < n:
        j = i
        while j + 1 < n and abs(nz[order[j + 1]]) == abs(nz[order[i]]):
            j += 1
        avg = (i + j) / 2 + 1
        for k in range(i, j + 1):
            ranks[order[k]] = avg
        tie_groups.append(j - i + 1)
        i = j + 1

    w_plus = sum(r for d, r in zip(nz, ranks) if d > 0)
    w_minus = sum(r for d, r in zip(nz, ranks) if d < 0)
    mean = n * (n + 1) / 4
    var = n * (n + 1) * (2 * n + 1) / 24 - sum(t**3 - t for t in tie_groups) / 48
    out.update(w_plus=w_plus, w_minus=w_minus, w=min(w_plus, w_minus))
    if var <= 0:
        return out   # mọi hiệu bằng nhau ⇒ z không xác định
    z = (w_plus - mean) / math.sqrt(var)
    out.update(z=z, p_two_sided=min(1.0, 2 * _normal_sf(abs(z))), r=abs(z) / math.sqrt(n))
    return out


def coverage_at_least_one(pool_sizes: Sequence[int]) -> float:
    """Tỉ lệ người có ÍT NHẤT 1 ứng viên sau lọc cứng.

    Đây là metric sống/chết của tính năng ghép: pool rỗng thì điểm xếp hạng tốt
    đến đâu cũng không ai thấy gì. Đo riêng khỏi "pool size trung bình" vì trung
    bình che mất đúng nhóm nguy hiểm — vài người pool 7 kéo trung bình lên trong
    khi 3 người pool 0 vẫn không dùng được app.
    """
    sizes = list(pool_sizes)
    if not sizes:
        return 0.0
    return sum(1 for s in sizes if s > 0) / len(sizes)


if __name__ == "__main__":
    # smoke test
    rec = ["a", "b", "c", "d", "e"]
    rel = {"a", "c", "e"}
    assert abs(precision_at_k(rec, rel, 5) - 0.6) < 1e-9
    relevance = {"a": 3, "b": 0, "c": 2, "d": 0, "e": 1}
    print("P@5 =", precision_at_k(rec, rel, 5))
    print("NDCG@5 =", round(ndcg_at_k(rec, relevance, 5), 4))
    print("MAE =", mean_absolute_error([1, 2, 3], [1, 2, 5]))

    # Các metric của notebook 06 — kiểm bằng trường hợp có đáp án biết trước,
    # không chỉ "chạy không lỗi": sai dấu / sai mẫu số ở gini và tau-b là loại
    # lỗi vẫn ra số đẹp.
    assert abs(cosine_similarity([1, 0], [1, 0]) - 1.0) < 1e-12
    assert abs(cosine_similarity([1, 0], [0, 1]) - 0.0) < 1e-12
    assert cosine_similarity([1, None], [None, 1]) is None       # không chiều nào chung
    assert abs(cosine_similarity([3, 4, None], [3, 4, 9]) - 1.0) < 1e-12
    assert abs(gini([5, 5, 5, 5])) < 1e-12                       # đều tuyệt đối
    assert abs(gini([0, 0, 0, 20]) - 0.75) < 1e-12               # 1 người hứng hết, n=4
    assert abs(kendall_tau([1, 2, 3], [1, 2, 3]) - 1.0) < 1e-12
    assert abs(kendall_tau([1, 2, 3], [3, 2, 1]) + 1.0) < 1e-12
    assert kendall_tau([1, 1, 1], [1, 2, 3]) is None             # một bên toàn tie
    w = wilcoxon_signed_rank([1, 2, 3, 4], [1, 2, 3, 4])
    assert w["n"] == 0 and w["n_zero"] == 4 and w["z"] is None    # mọi hiệu = 0
    w = wilcoxon_signed_rank([5, 6, 7, 8, 9], [1, 2, 3, 4, 5])
    assert w["w_minus"] == 0.0 and w["r"] is not None             # lệch một phía
    assert abs(coverage_at_least_one([0, 0, 3, 7]) - 0.5) < 1e-12

    print("gini([0,0,0,20]) =", round(gini([0, 0, 0, 20]), 4))
    print("tau-b dao nguoc  =", kendall_tau([1, 2, 3], [3, 2, 1]))
    print("Wilcoxon r       =", round(w["r"], 4), "(n =", w["n"], ")")
    print("OK")
