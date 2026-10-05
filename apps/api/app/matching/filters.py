"""Lọc cứng 2 tầng — và lý do ĐỊNH LƯỢNG vì sao không thể để 1 tầng.

Đây là phần làm cho ghép bạn ở AN TOÀN: cặp bị loại ở đây thì không điểm nào cứu
được. Tách khỏi score.py để test riêng và để báo cáo trình bày nó như một mục
độc lập (Chương 3), không phải bước tiền xử lý.

═══ VÌ SAO 2 TẦNG (đo trên 19 hồ sơ thật, eval/data/survey_v2.csv) ═══
Coi MỌI deal-breaker được khai là veto tuyệt đối thì tính năng CHẾT:

    cấu hình lọc cứng                        người có pool > 0
    tất cả 9 deal-breaker là cứng                  6/19
    bỏ 'Ồn ào khuya' khỏi tầng cứng               12/19
    chỉ giữ an toàn (hút trong phòng + ở bẩn)     16/19
    không deal-breaker nào cứng                   17/19

Chỉ 2,3% cặp có hướng đi qua được, 13/19 người pool RỖNG. Nguyên nhân là SỐ HỌC,
không phải lỗi cài đặt: trung bình mỗi người khai 4,63/9 deal-breaker và tự khai
làm 3,26 hành vi ⇒ xác suất một cặp không trùng gì là rất nhỏ. 'Ồn ào khuya' một
mình gây 35,5% lượt loại và là lý do DUY NHẤT ở 34 cặp.

═══ TIÊU CHÍ CHIA TẦNG (không phải tinh chỉnh ngưỡng cho đẹp số) ═══
CỨNG = ngoại ứng sức khoẻ/vệ sinh, không thương lượng được trong thời gian thuê:
  · hút thuốc TRONG PHÒNG — khói là ngoại ứng sức khoẻ, 18/19 khai không chịu được
  · ở bẩn                 — ngưỡng vệ sinh, 15/19 khai, đo được từ hành vi
MỀM = nội quy nhà THƯƠNG LƯỢNG ĐƯỢC (dẫn bạn về, người yêu ngủ lại, ồn khuya,
  nhậu, thú cưng, đi khuya): bạn ở ghép thật vẫn thoả thuận được với nhau. Một ô
  tick là SỞ THÍCH ĐƯỢC KHAI, không phải ràng buộc an toàn.

Vi phạm MỀM không bị ẩn đi — nó thành chiều trừ điểm nặng nhất (score.py,
`deal_breaker_soft`) VÀ hiện thành cảnh báo rõ chữ trên thẻ ("bạn ấy có N điều
bạn từng nói không chấp nhận: ..."). Quyền quyết định vẫn ở người dùng — trung
thực hơn là im lặng loại họ khỏi pool.
"""
from __future__ import annotations

from .profile import (
    DB_DIRTY,
    DB_SMOKE_IN_ROOM,
    DB_TO_HANHVI,
    DEAL_BREAKER,
    DIRTY_MAX,
    Profile,
)

# Tầng CỨNG — veto tuyệt đối. Giữ bộ này NHỎ là quyết định có chủ đích.
HARD_DEAL_BREAKERS: frozenset[str] = frozenset({DB_SMOKE_IN_ROOM, DB_DIRTY})

# Tầng MỀM — phần còn lại, đi vào tính điểm chứ không loại.
SOFT_DEAL_BREAKERS: frozenset[str] = frozenset(DEAL_BREAKER) - HARD_DEAL_BREAKERS

BUDGET_MAX_GAP = 1      # 1 bậc ≈ nửa triệu: còn thuê chung được phòng ở giữa
SCENARIO_ALONE = 1      # 1 = ở một mình · 2 = ghép 2 · 3 = ghép 3+


def _triggered(db: str, other: Profile) -> bool:
    """Hành vi/thuộc tính của `other` có kích hoạt deal-breaker `db` không?

    Ba nhánh vì ba nguồn dữ liệu khác nhau — gộp lại là chỗ dễ sai nhất:
      (a) đối chiếu qua cột hanh_vi, phải đi qua DB_TO_HANHVI
      (b) hút thuốc: cột riêng smoke_in_room
      (c) ở bẩn: ngưỡng trên thang cleanliness, không có hanh_vi tương ứng
    """
    hv = DB_TO_HANHVI.get(db)
    if hv is not None:
        return hv in other.hanh_vi
    if db == DB_SMOKE_IN_ROOM:
        # smoke=True + smoke_in_room=False = người ra ngoài hút ⇒ KHÔNG kích hoạt.
        # Gộp hai cột thành một cờ nhị phân là loại oan người hút có ý thức.
        return bool(other.smoke_in_room)
    if db == DB_DIRTY:
        return other.cleanliness is not None and other.cleanliness <= DIRTY_MAX
    return False


def _hard_violation(victim: Profile, other: Profile) -> str | None:
    for db in victim.deal_breakers & HARD_DEAL_BREAKERS:
        if _triggered(db, other):
            return db
    return None


def soft_violations(victim: Profile, other: Profile) -> list[str]:
    """Deal-breaker MỀM của `victim` mà `other` kích hoạt. Một chiều.

    Dùng cho cả tính điểm (score.py) và hiển thị cảnh báo trên thẻ.
    """
    return sorted(db for db in victim.deal_breakers & SOFT_DEAL_BREAKERS if _triggered(db, other))


def hard_filter_reason(a: Profile, b: Profile) -> str | None:
    """None = cặp đi qua. Ngược lại trả lý do loại (chuỗi ổn định, dùng cho test + eval).

    Thứ tự kiểm = rẻ/tuyệt đối trước, và cũng là thứ tự nên trình bày trong báo
    cáo: an toàn (giới tính) → sức khoẻ/vệ sinh → khả thi (ngân sách, kịch bản).
    """
    if a.user_id == b.user_id:
        return "self"

    # 1. Chỉ ghép cùng giới — tuyệt đối, người dùng không có tuỳ chọn.
    #    gender NULL ⇒ ngoài pool: không đoán giới tính của ai.
    if not a.in_pool:
        return "a_not_in_pool"
    if not b.in_pool:
        return "b_not_in_pool"
    if a.gender != b.gender:
        return "gender_mismatch"

    # 2. Deal-breaker CỨNG, hai chiều. Cặp "A chịu được B nhưng B không chịu được
    #    A" vẫn phải bị loại — đây là chỗ điểm đối xứng sẽ bỏ sót.
    db = _hard_violation(a, b)
    if db is not None:
        return f"hard_db_a:{db}"
    db = _hard_violation(b, a)
    if db is not None:
        return f"hard_db_b:{db}"

    # 3. Ngân sách. NULL ⇒ bỏ qua kiểm: thiếu dữ liệu KHÔNG phải lý do loại ở đây
    #    (khác giới tính ở trên, nơi thiếu dữ liệu LÀ lý do loại vì là ràng buộc
    #    an toàn — phân biệt này có chủ đích).
    if a.budget_band is not None and b.budget_band is not None:
        if abs(a.budget_band - b.budget_band) > BUDGET_MAX_GAP:
            return "budget_gap"

    # 4. Đã khai "ở một mình" thì không ghép với ai.
    if a.scenario == SCENARIO_ALONE or b.scenario == SCENARIO_ALONE:
        return "scenario_alone"

    return None


def passes_hard_filters(a: Profile, b: Profile) -> bool:
    return hard_filter_reason(a, b) is None


def eligible_pool(me: Profile, others: list[Profile]) -> list[Profile]:
    """Pool của `me` sau lọc cứng. Giữ thứ tự đầu vào — xếp hạng là việc của score.py."""
    return [p for p in others if passes_hard_filters(me, p)]
