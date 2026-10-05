"""Hằng số form v2 + chuẩn hoá hồ sơ ở ghép thành dạng thuật toán dùng được.

Vì sao có file này thay vì nhúng thẳng vào score.py: ba thứ dưới đây PHẢI khớp
nhau từng chữ, và khi lệch thì lỗi hoàn toàn im lặng (deal-breaker nằm trong DB
mà không bao giờ loại được ai):

    1. HANH_VI / DEAL_BREAKER — nguyên văn lựa chọn trong docs/planning/tao_google_form_v2.gs
    2. DB_TO_HANHVI           — cầu nối "deal-breaker của A ↔ trường của B"
    3. Thang số của các cột thứ bậc trong roommate_profiles

Bảng ĐỐI CHIẾU gốc nằm ở cuối tao_google_form_v2.gs. Sửa form ⇒ sửa cả 3 chỗ.

CỰC TÍNH (nguồn gốc nhiều lỗi — ghi rõ một lần ở đây):
    cleanliness      1..5, 5 = sạch nhất  (5 = rửa chén ngay, 1 = để đến khi hết chén)
    noise_tolerance  1..5, 5 = CHỊU ồn tốt nhất (1 = rất khó chịu, phải nói ngay)
    sleep_time       0..2, 0 = ngủ sớm (<22h), 2 = ngủ muộn (>0h)
    ac_usage         0..2, 0 = ít bật máy lạnh, 2 = bật gần cả đêm
    money_style      1|2  — DANH NGHĨA, không phải thứ bậc (xem score.py)
"""
from __future__ import annotations

from dataclasses import dataclass, field

# ─── Nguyên văn lựa chọn form v2 (tao_google_form_v2.gs:110-133) ──────────────
HANH_VI: tuple[str, ...] = (
    "Mình hay nấu ăn trong phòng",
    "Mình hay rủ bạn bè về phòng chơi",
    "Người yêu / bạn thân thỉnh thoảng ở lại qua đêm",
    "Mình muốn nuôi thú cưng trong phòng",
    "Mình hay nhậu / tụ tập trong phòng",
    "Mình hay đi chơi về khuya",
    "Tối muộn mình hay còn hoạt động (xem phim, gọi điện, nói chuyện)",
    "Mình sẵn sàng dùng chung đồ (đồ ăn, đồ dùng)",
    "Không điều nào ở trên đúng với mình",
)

DEAL_BREAKER: tuple[str, ...] = (
    "Hút thuốc trong phòng",
    "Nấu ăn trong phòng",
    "Hay dẫn bạn về phòng",
    "Người yêu ở lại qua đêm",
    "Nuôi thú cưng",
    "Nhậu nhẹt trong phòng",
    "Đi chơi về khuya",
    "Ồn ào khuya",
    "Ở bẩn, không dọn dẹp",
    "Mình dễ tính, không có điều nào",
)

# Hai sentinel: chọn chúng nghĩa là "không khai gì", không được coi là hành vi /
# deal-breaker thật. Lọc cứng phải bỏ qua, nếu không sẽ loại oan toàn bộ pool.
HANH_VI_NONE = "Không điều nào ở trên đúng với mình"
DEAL_BREAKER_NONE = "Mình dễ tính, không có điều nào"

# ─── BẢNG ĐỐI CHIẾU: deal-breaker của A ↔ hành vi của B ───────────────────────
# Chỉ gồm các cặp đối chiếu được bằng cột hanh_vi. Ba deal-breaker còn lại cần
# cột riêng nên xử lý tay trong filters.py:
#   'Hút thuốc trong phòng' → cột smoke_in_room
#   'Ở bẩn, không dọn dẹp'  → cột cleanliness (ngưỡng DIRTY_MAX)
#   'Mình dễ tính...'       → sentinel, không lọc
DB_TO_HANHVI: dict[str, str] = {
    "Nấu ăn trong phòng": "Mình hay nấu ăn trong phòng",
    "Hay dẫn bạn về phòng": "Mình hay rủ bạn bè về phòng chơi",
    "Người yêu ở lại qua đêm": "Người yêu / bạn thân thỉnh thoảng ở lại qua đêm",
    "Nuôi thú cưng": "Mình muốn nuôi thú cưng trong phòng",
    "Nhậu nhẹt trong phòng": "Mình hay nhậu / tụ tập trong phòng",
    "Đi chơi về khuya": "Mình hay đi chơi về khuya",
    "Ồn ào khuya": "Tối muộn mình hay còn hoạt động (xem phim, gọi điện, nói chuyện)",
}

DB_SMOKE_IN_ROOM = "Hút thuốc trong phòng"
DB_DIRTY = "Ở bẩn, không dọn dẹp"

# cleanliness <= 2 mới bị coi là "ở bẩn": form chỉ có 2 mức dưới mức "rửa trong
# ngày" ('để 1-2 ngày' = 2, 'để đến khi hết chén sạch' = 1). Ngưỡng 3 sẽ loại oan
# người rửa trong ngày — tức gần nửa mẫu khảo sát.
DIRTY_MAX = 2

# Hành vi gây ồn đêm — dùng cho chiều BẤT ĐỐI XỨNG trong score.py: chỉ người có
# noise_tolerance thấp bị trừ điểm khi người kia có hành vi này, không ngược lại.
HANH_VI_ON_AO: frozenset[str] = frozenset({
    "Tối muộn mình hay còn hoạt động (xem phim, gọi điện, nói chuyện)",
    "Mình hay nhậu / tụ tập trong phòng",
    "Mình hay rủ bạn bè về phòng chơi",
})

HANH_VI_SHARE = "Mình sẵn sàng dùng chung đồ (đồ ăn, đồ dùng)"

# Miền giá trị các cột thứ bậc — dùng chuẩn hoá d_k = |a-b| / range.
# Khảo sát KHÔNG có câu hỏi nào sinh ra wake_time ⇒ cột luôn NULL, không đưa vào
# tính điểm (xem score.py DIMENSIONS). Giữ cột cho tương thích lược đồ.
ORDINAL_RANGE: dict[str, int] = {
    "sleep_time": 2,        # 0..2
    "cleanliness": 4,       # 1..5
    "noise_tolerance": 4,   # 1..5
    "ac_usage": 2,          # 0..2
    "budget_band": 4,       # 0..4
}

GENDERS = ("nam", "nu")

# Câu E1 (thời điểm cần phòng) → số tháng tính từ lúc khảo sát. Chỉ cần đủ để
# so LỆCH giữa hai người, không cần chính xác theo lịch. "Chưa gấp" = linh hoạt
# ⇒ không đưa vào map ⇒ None ⇒ không bao giờ bị loại vì thời điểm.
NEED_FROM_MONTHS: dict[str, int] = {
    "Càng sớm càng tốt (trong tháng này)": 0,
    "Trong 2–3 tháng tới": 2,
    "Đầu học kỳ tới": 3,
}


@dataclass(slots=True)
class Profile:
    """Hồ sơ đã chuẩn hoá. Thuật toán CHỈ nhận kiểu này, không nhận Row/dict thô.

    Lý do: cột trong DB nullable gần hết (khảo sát có 2 nhánh rẽ bỏ qua phần D),
    nên mọi chỗ tính điểm đều phải xử lý None. Gom việc đó về một chỗ ở `from_row`
    rẻ hơn là rải `if x is None` khắp score.py.
    """

    user_id: int
    gender: str | None = None
    don_vi: str | None = None
    budget_band: int | None = None
    scenario: int | None = None
    sleep_time: int | None = None
    cleanliness: int | None = None
    noise_tolerance: int | None = None
    ac_usage: int | None = None
    money_style: int | None = None
    smoke: bool | None = None
    smoke_in_room: bool | None = None
    hanh_vi: frozenset[str] = field(default_factory=frozenset)
    deal_breakers: frozenset[str] = field(default_factory=frozenset)
    persona: str | None = None
    bio: str | None = None
    need_from: str | None = None
    is_simulated: bool = False

    @property
    def share_stuff(self) -> int | None:
        """Suy từ hanh_vi — form v2 không có câu hỏi riêng cho cột share_stuff.

        None khi người này chưa khai hành vi nào (phân biệt "không sẵn sàng dùng
        chung" với "chưa trả lời"); score.py bỏ qua chiều None.
        """
        if not self.hanh_vi:
            return None
        return 1 if HANH_VI_SHARE in self.hanh_vi else 0

    @property
    def need_month(self) -> int | None:
        """Thời điểm cần phòng quy ra tháng; None = linh hoạt / không khai."""
        return NEED_FROM_MONTHS.get((self.need_from or "").strip())

    @property
    def noisy(self) -> bool:
        return bool(self.hanh_vi & HANH_VI_ON_AO)

    @property
    def in_pool(self) -> bool:
        """Đủ điều kiện vào pool ghép hay chưa.

        gender NULL ⇒ ngoài pool, tuyệt đối (chính sách chỉ ghép cùng giới, xem
        BẢNG ĐỐI CHIẾU trong tao_google_form_v2.gs). Thiếu toàn bộ phần lối sống
        thì có cho vào pool cũng không tính được điểm ⇒ cũng loại.
        """
        if self.gender not in GENDERS:
            return False
        return self.sleep_time is not None or self.cleanliness is not None

    @classmethod
    def from_row(cls, row) -> "Profile":
        """Dựng từ một hàng roommate_profiles JOIN users (mapping/dict-like)."""
        r = dict(row)

        def arr(key: str, allowed: tuple[str, ...], sentinel: str) -> frozenset[str]:
            # Postgres TEXT[] về dạng list; lọc theo `allowed` để một lựa chọn
            # cũ/sai chính tả không âm thầm thành deal-breaker không ai đối chiếu được.
            vals = r.get(key) or []
            return frozenset(v for v in vals if v in allowed and v != sentinel)

        gender = (r.get("gender") or "").strip().lower() or None
        return cls(
            user_id=int(r["user_id"]),
            gender=gender if gender in GENDERS else None,
            don_vi=r.get("don_vi"),
            budget_band=r.get("budget_band"),
            scenario=r.get("scenario"),
            sleep_time=r.get("sleep_time"),
            cleanliness=r.get("cleanliness"),
            noise_tolerance=r.get("noise_tolerance"),
            ac_usage=r.get("ac_usage"),
            money_style=r.get("money_style"),
            smoke=r.get("smoke"),
            smoke_in_room=r.get("smoke_in_room"),
            hanh_vi=arr("hanh_vi", HANH_VI, HANH_VI_NONE),
            deal_breakers=arr("deal_breakers", DEAL_BREAKER, DEAL_BREAKER_NONE),
            persona=r.get("persona"),
            bio=r.get("bio"),
            need_from=r.get("need_from"),
            is_simulated=bool(r.get("is_simulated") or False),
        )
