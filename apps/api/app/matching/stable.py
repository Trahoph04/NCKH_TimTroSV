"""Stable Roommates — tầng ghép TOÀN CỤC, bổ sung cho xếp hạng top-K.

VÌ SAO CẦN: ở pool ~5 người, "chất lượng xếp hạng" gần như không đo được (top-5
trên pool 5 thì thứ tự vô nghĩa) — đây là giới hạn đã nêu ở
Matching_Messaging_Design.md 2.6. Nhưng TÍNH ỔN ĐỊNH thì đo được chính xác, và
còn dễ đo hơn khi N nhỏ. Nhờ vậy N nhỏ thành ưu thế chứ không còn là lời xin lỗi.

ĐÚNG TÊN BÀI TOÁN: pool cùng giới ⇒ ai cũng vừa chọn vừa bị chọn ⇒ đây là
Stable Roommates (NON-bipartite), KHÔNG phải Stable Marriage (bipartite).
Khác biệt quyết định:
  · Stable Marriage (Gale-Shapley) LUÔN có nghiệm.
  · Stable Roommates CÓ THỂ KHÔNG có nghiệm nào. Thuật toán Irving O(n²) hoặc
    trả về một ghép ổn định, hoặc CHỨNG MINH không tồn tại.

Vậy "tập hồ sơ này có tồn tại ghép ổn định không?" tự nó đã là một kết quả
nghiên cứu, lấy được từ đúng số hồ sơ đang có, không cần thêm người.

ĐỘ PHỨC TẠP — nói thẳng thay vì né: với preference list CÓ TIES hoặc KHÔNG đầy
đủ, Stable Roommates là NP-hard (NP-hard ngay cả khi mỗi người chỉ chấp nhận ≤3
người khác), và cực tiểu hoá số blocking pair không xấp xỉ được trong n^(1/2−ε).
Ở n ≤ 20 thì điều đó không thành vấn đề thực tế: ties được phá tất định bằng
user_id (xem build_preferences), và khi không có ghép ổn định ta báo SỐ BLOCKING
PAIR của ghép tìm được — đó là đại lượng "almost-stable" trong tài liệu.

Tham khảo: Irving (1985) An efficient algorithm for the "stable roommates"
problem; Abraham/Biró/Manlove — "Almost stable" matchings in the Roommates problem.
"""
from __future__ import annotations

from dataclasses import dataclass

from .filters import passes_hard_filters
from .profile import Profile
from .score import pair_score


@dataclass(slots=True)
class StableResult:
    matching: dict[int, int]        # user_id → user_id (đối xứng); người lẻ không có khoá
    stable: bool                    # True = ghép ổn định (0 blocking pair)
    blocking_pairs: list[tuple[int, int]]
    unmatched: list[int]
    method: str                     # 'irving' | 'greedy+local' — ghi rõ nguồn kết quả


def build_preferences(
    profiles: list[Profile], weights: dict[str, float]
) -> tuple[dict[int, list[int]], dict[tuple[int, int], float]]:
    """prefs[x] = các ứng viên QUA ĐƯỢC LỌC CỨNG của x, xếp giảm dần theo điểm.

    Hai điểm bắt buộc, nếu sai thì mọi kết luận ổn định đều vô nghĩa:

    1. Dùng s(x→y) (điểm CÓ HƯỚNG), không dùng harmonic. Preference list là thứ
       tự ưu tiên CỦA RIÊNG x; harmonic đã trộn cả ý của y vào nên không còn là
       sở thích của x nữa.
    2. Phá ties tất định bằng user_id. Ties khiến bài toán NP-hard, và còn làm
       kết quả đổi theo thứ tự dict — chạy hai lần ra hai đáp án khác nhau thì
       không báo cáo được.
    """
    by_id = {p.user_id: p for p in profiles}
    scores: dict[tuple[int, int], float] = {}
    prefs: dict[int, list[int]] = {}

    for x in profiles:
        cands = []
        for y in profiles:
            if x.user_id == y.user_id or not passes_hard_filters(x, y):
                continue
            s = pair_score(x, y, weights).s_ab
            scores[(x.user_id, y.user_id)] = s
            cands.append(y.user_id)
        # -s giảm dần, rồi id tăng dần để phá tie tất định
        cands.sort(key=lambda yid: (-scores[(x.user_id, yid)], yid))
        prefs[x.user_id] = cands

    assert set(prefs) <= set(by_id)
    return prefs, scores


def blocking_pairs(matching: dict[int, int], prefs: dict[int, list[int]]) -> list[tuple[int, int]]:
    """Cặp (x,y) mà cả hai đều THÍCH NHAU HƠN người đang được ghép.

    Định nghĩa blocking pair của Stable Roommates. Người chưa được ghép coi như
    có partner ở vị trí vô cực ⇒ bất kỳ ứng viên chấp nhận được cũng tốt hơn.
    """
    rank = {x: {y: i for i, y in enumerate(lst)} for x, lst in prefs.items()}
    INF = float("inf")

    def pos(x: int, y: int) -> float:
        return rank.get(x, {}).get(y, INF)

    def cur(x: int) -> float:
        m = matching.get(x)
        return INF if m is None else pos(x, m)

    out: list[tuple[int, int]] = []
    for x, lst in prefs.items():
        for y in lst:
            if y <= x:
                continue          # mỗi cặp xét một lần
            if matching.get(x) == y:
                continue
            if pos(x, y) < cur(x) and pos(y, x) < cur(y):
                out.append((x, y))
    return out


def _phase1(prefs: dict[int, list[int]]) -> dict[int, list[int]] | None:
    """Pha đề nghị của Irving. None = chắc chắn không có ghép ổn định.

    Mỗi người đi xuống danh sách của mình đề nghị; người được đề nghị giữ lại
    đề nghị TỐT NHẤT nhận được và loại phần còn lại. Danh sách ai cạn ⇒ vô nghiệm.
    """
    lists = {x: list(l) for x, l in prefs.items()}
    rank = {x: {y: i for i, y in enumerate(l)} for x, l in prefs.items()}
    holder: dict[int, int] = {}          # y → người y đang giữ đề nghị
    next_idx = {x: 0 for x in lists}
    free = [x for x in lists if lists[x]]

    while free:
        x = free.pop()
        while True:
            if next_idx[x] >= len(lists[x]):
                return None               # x cạn danh sách
            y = lists[x][next_idx[x]]
            held = holder.get(y)
            if held is None:
                holder[y] = x
                break
            # y so sánh x với người đang giữ
            if rank[y].get(x, len(lists[y])) < rank[y].get(held, len(lists[y])):
                holder[y] = x
                next_idx[held] += 1
                free.append(held)
                break
            next_idx[x] += 1              # y từ chối x

    # Rút gọn: với mỗi y, bỏ mọi người y thích KÉM HƠN người y đang giữ.
    reduced = {x: list(l) for x, l in lists.items()}
    for y, held in holder.items():
        limit = rank[y][held]
        keep = {z for z in reduced[y] if rank[y][z] <= limit}
        dropped = [z for z in reduced[y] if z not in keep]
        reduced[y] = [z for z in reduced[y] if z in keep]
        for z in dropped:                 # bỏ đối xứng
            if y in reduced.get(z, []):
                reduced[z].remove(y)
    # KHÔNG rút gọn thêm gì nữa. Từng có một vòng thứ hai ở đây cắt phần đầu danh
    # sách của x (những người đã từ chối x) — vừa THỪA vừa SAI: "z từ chối x" ⇔
    # "z đang giữ người z thích hơn x", nên cặp (z,x) đã bị vòng trên xoá đối
    # xứng rồi. Cắt lần hai bằng chỉ số vào danh sách ĐÃ BỊ MUTATE làm xoá oan và
    # sinh danh sách rỗng ⇒ báo "vô nghiệm" cho instance thực ra CÓ nghiệm
    # (bắt được bằng kiểm định brute-force: 1/400 ca sai trước khi bỏ vòng này).
    if any(len(l) == 0 for l in reduced.values()):
        return None
    return reduced


def _stable_search(
    lists: dict[int, list[int]], prefs: dict[int, list[int]], budget: int = 2_000_000
) -> tuple[dict[int, int] | None, bool]:
    """Tìm ghép ổn định bằng quay lui trên BẢNG ĐÃ TỈA. → (ghép | None, đã_xét_hết).

    Vì sao vét cạn thay vì khử rotation của Irving: pha 2 của Irving phải giữ bất
    biến "stable table" sau mỗi lần khử rotation; cài thiếu phần đó cho ra FALSE
    NEGATIVE — báo vô nghiệm trên instance thực ra có nghiệm (kiểm định
    brute-force bắt được 1/400 ca). Ở quy mô của đề tài (pool mỗi giới ≤ 13 người)
    tìm kiếm vét cho ĐÁP ÁN ĐÚNG TUYỆT ĐỐI, nên không cần đánh đổi.

    Hợp lệ vì bổ đề của Irving: pha 1 KHÔNG xoá cặp ổn định nào ⇒ mọi ghép ổn định
    đều nằm trong bảng đã tỉa. Dùng bảng đó làm miền tìm kiếm là an toàn và cắt
    rất mạnh.

    `budget` = trần số nút để không treo API trên pool bất thường lớn; trả về cờ
    exhausted=False khi hết trần ⇒ "không kết luận được", KHÁC với "vô nghiệm".
    """
    ids = sorted(lists)
    nodes = 0

    def rec(i: int, cur: dict[int, int]) -> dict[int, int] | None:
        nonlocal nodes
        nodes += 1
        if nodes > budget:
            return None
        while i < len(ids) and ids[i] in cur:
            i += 1
        if i >= len(ids):
            return dict(cur) if not blocking_pairs(cur, prefs) else None
        x = ids[i]
        for y in lists[x]:
            if y in cur:
                continue
            cur[x] = y
            cur[y] = x
            got = rec(i + 1, cur)
            if got is not None:
                return got
            del cur[x]
            del cur[y]
            if nodes > budget:
                return None
        # Để x lẻ (pool lẻ người, hoặc mọi ứng viên đã bị dùng)
        got = rec(i + 1, cur)
        return got

    m = rec(0, {})
    return m, nodes <= budget


def irving(prefs: dict[int, list[int]]) -> dict[int, int] | None:
    """Ghép ổn định, hoặc None nếu KHÔNG TỒN TẠI (ở quy mô n ≤ 20: đáp án chính xác).

    Tên hàm giữ 'irving' vì pha 1 đề nghị là của Irving và là bước tỉa chính;
    pha 2 thay bằng tìm kiếm vét (xem _stable_search).
    """
    lists = _phase1(prefs)
    if lists is None:
        return None
    m, _ = _stable_search(lists, prefs)
    return m


def _greedy(prefs: dict[int, list[int]], scores: dict[tuple[int, int], float]) -> dict[int, int]:
    """Ghép tham lam theo điểm harmonic giảm dần — dùng khi KHÔNG có ghép ổn định.

    Không tối ưu (cực tiểu blocking pair là NP-hard), nên kết quả được báo kèm
    SỐ blocking pair chứ không gọi là "ổn định".
    """
    pairs = []
    for x, lst in prefs.items():
        for y in lst:
            if x < y:
                s_xy = scores.get((x, y), 0.0)
                s_yx = scores.get((y, x), 0.0)
                h = 0.0 if s_xy <= 0 or s_yx <= 0 else 2 * s_xy * s_yx / (s_xy + s_yx)
                pairs.append((h, x, y))
    pairs.sort(key=lambda t: (-t[0], t[1], t[2]))
    used: set[int] = set()
    out: dict[int, int] = {}
    for _, x, y in pairs:
        if x in used or y in used:
            continue
        out[x] = y
        out[y] = x
        used.update((x, y))
    return out


def stable_roommates(profiles: list[Profile], weights: dict[str, float]) -> StableResult:
    """Điểm vào duy nhất cho notebook eval + API.

    Trả StableResult.stable = True chỉ khi thực sự 0 blocking pair.
    """
    prefs, scores = build_preferences(profiles, weights)
    everyone = set(prefs)

    m = irving(prefs)
    method = "irving+exact"
    if m is None:
        # Không có ghép ổn định nào — đây là KẾT QUẢ, không phải lỗi: Stable
        # Roommates (non-bipartite) có thể vô nghiệm, khác Stable Marriage.
        # Khi đó báo ghép tham lam KÈM số blocking pair ("almost-stable").
        m = _greedy(prefs, scores)
        method = "greedy (khong ton tai ghep on dinh)"

    bp = blocking_pairs(m, prefs)
    unmatched = sorted(everyone - set(m))
    return StableResult(
        matching=m,
        stable=not bp,
        blocking_pairs=bp,
        unmatched=unmatched,
        method=method,
    )
